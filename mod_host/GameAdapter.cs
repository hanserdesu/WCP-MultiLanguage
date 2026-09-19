// WCP Host — 游戏适配层（反射封装）
//
// 为什么全走反射: 游戏更新会改字段名 / 类型。现有插件（JpWordListMod.cs 的 L 段）
// 已经把这条做对了 —— 字段消失时只记一条日志，不抛异常、不崩、不写坏存档。
// 宿主把这条约定提升为通用规则: **任何对游戏内部的访问都必须能"优雅失效"**。
//
// 所有类型/方法都按名字查，查不到返回 null / 空，由调用方按 fail-closed 处理。
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using HarmonyLib;
using UnityEngine;

namespace WcpHost
{
    internal static class GameAdapter
    {
        // 游戏参数类型名单点：作者改类型名（MyParameters → …）时只改这里。
        // 30+ 个静态字段访问都引用此常量；类型缺失时各调用方按 fail-closed 降级。
        internal const string ParametersType = "MyParameters";
        private static readonly Dictionary<string, FieldInfo> _fields =
            new Dictionary<string, FieldInfo>();
        private static readonly Dictionary<string, FieldInfo> _instanceFields =
            new Dictionary<string, FieldInfo>();
        private static MethodInfo _es3LoadString;
        private static MethodInfo _es3LoadDefault;
        private static MethodInfo _es3LoadFile;
        private static MethodInfo _es3Save;
        private static bool _es3Probed;
        // 泛型绑定缓存（原来每次 Es3Load / Es3SaveDirect 都调一次 MakeGenericMethod）。
        private static readonly Dictionary<Type, MethodInfo> _loadDefaultCache =
            new Dictionary<Type, MethodInfo>();
        private static readonly Dictionary<Type, MethodInfo> _loadFileCache =
            new Dictionary<Type, MethodInfo>();
        private static readonly Dictionary<Type, MethodInfo> _saveDirectCache =
            new Dictionary<Type, MethodInfo>();

        internal static object StaticField(string typeName, string fieldName)
        {
            string cacheKey = typeName + "." + fieldName;
            FieldInfo fi;
            if (!_fields.TryGetValue(cacheKey, out fi))
            {
                try
                {
                    Type t = AccessTools.TypeByName(typeName);
                    fi = (t == null) ? null : AccessTools.Field(t, fieldName);
                }
                catch (Exception) { fi = null; }
                _fields[cacheKey] = fi;
                if (fi == null && WcpHostPlugin.Log != null)
                    WcpHostPlugin.Log.LogWarning("WcpHost: 游戏字段不可用 " + cacheKey +
                        "（游戏更新导致？本项功能降级，其余不受影响）");
            }
            if (fi == null) return null;
            try { return fi.GetValue(null); }
            catch (Exception) { return null; }
        }

        internal static bool SetStaticField(string typeName, string fieldName, object value)
        {
            FieldInfo fi = FindField(typeName, fieldName, false);
            if (fi == null || !fi.IsStatic) return false;
            try
            {
                fi.SetValue(null, value);
                return true;
            }
            catch (Exception e)
            {
                Warn("写入游戏静态字段失败 " + typeName + "." + fieldName + ": " + e.Message);
                return false;
            }
        }

        internal static object InstanceField(object instance, string fieldName)
        {
            if (instance == null || string.IsNullOrEmpty(fieldName)) return null;
            FieldInfo fi = FindField(instance.GetType(), fieldName);
            if (fi == null) return null;
            try { return fi.GetValue(instance); }
            catch (Exception) { return null; }
        }

        internal static bool SetInstanceField(object instance, string fieldName, object value)
        {
            if (instance == null || string.IsNullOrEmpty(fieldName)) return false;
            FieldInfo fi = FindField(instance.GetType(), fieldName);
            if (fi == null) return false;
            try
            {
                fi.SetValue(instance, value);
                return true;
            }
            catch (Exception e)
            {
                Warn("写入游戏实例字段失败 " + instance.GetType().Name + "." + fieldName +
                     ": " + e.Message);
                return false;
            }
        }

        internal static IList<string> ToWordList(object raw)
        {
            if (raw == null) return null;
            if (raw is string) return null;                 // 别把 IEnumerable<char> 当词表
            IList<string> typed = raw as IList<string>;
            if (typed != null) return typed;
            IEnumerable seq = raw as IEnumerable;
            if (seq == null) return null;
            List<string> list = new List<string>();
            try
            {
                foreach (object o in seq) list.Add(o == null ? null : o.ToString());
            }
            catch (Exception) { return null; }
            return list;
        }

        // 原生槽位数量：从存档连续探测（作者加槽自动跟随），下限 4。探测一次并缓存。
        private static int _nativeSlotCount;
        // 槽位词表缓存。
        //
        // 第七轮（2026-09-18）改的就是这里：原来只有一个 `_slotCacheSlot` +
        // `_slotCacheWords`，也就是**只缓存最后一次读的那个槽**。而调用方
        // （HostRuntime.SlotByDisplayName / ManifestForSlot）是按 1→2→…→N 的顺序
        // 逐个槽问过去的，于是"上一个槽 == 这次要的槽"几乎从不成立 —— 每次调用都
        // 缓存未命中，都要走一次 ES3 全文档解析。
        //
        // 实测（probes/csbench/Bench2.cs，同代 BCL + 真实存档）：
        //   File.ReadAllBytes(MyBook.es3 2.1MB) + Json.Parse(1409K chars) = 22.6ms
        //   ES3 还要在此基础上加反射与装箱 → 单次 SlotWords 下界 22.6ms
        //   UI 扫描里"4 个槽 × 若干行"= 32 次调用 = 725ms/扫描，每秒一轮。
        // 改成按槽号建字典之后，同一个槽在一次会话里最多读一次（存档 mtime/size 变了才重读）。
        //
        // 键 = 槽号；值 = (词表, 读它时的 MyBook.es3 mtime/size)。null 结果也缓存：
        // 文件不存在时（ticks/size 均为 -1）原来会每次调用都重新尝试一次 ES3 读取 +
        // 抛异常，现在同样退化成 O(1)；文件一旦出现，ticks/size 变化会自动失效。
        private sealed class SlotEntry
        {
            internal IList<string> Words;
            internal long Ticks;
            internal long Size;
            // 第十二轮（2026-09-18）：词表的语言包归属**跟着缓存键一起存**。
            //
            // 为什么这是精确的、不是启发式：FingerprintOf / Match 是 words 的纯函数，
            // 而这份 words 只在 (ticks, size) 变化时才被重新反序列化 —— 也就是说，
            // 只要 (ticks, size) 没变，拿到的就是**同一个实例**、内容逐字节相同，
            // 那么上一轮算出的 profile 必然依然成立。反之缓存键一变这里立刻作废。
            // 没有任何"猜"的成分。
            //
            // 为什么需要它：Host.Evaluate 每秒跑一次，其中 `身份:匹配槽位词表` 在实机
            // 稳态是 11.7ms/s（窗口 592：10 次 116.5ms）。而真实变化频率是"用户切书 /
            // 游戏写档"，量级是分钟。这个比值就是白付的钱。
            internal BookProfile Profile;
            internal BookRegistry ProfileRegistry;
            internal bool ProfileReady;
        }

        private static readonly Dictionary<int, SlotEntry> _slotCache =
            new Dictionary<int, SlotEntry>();
        // 落盘书名缓存（键同上）
        private static bool _diskNameCached;
        private static string _diskNameCache;
        private static long _diskNameTicks = -1;
        private static long _diskNameSize = -1;
        internal static int NativeSlotCount()
        {
            if (_nativeSlotCount > 0) return _nativeSlotCount;
            // 第十轮加探针：这个循环每次迭代都是一次**完整的 ES3 文档解析**，
            // 而它此前不在任何 span 里 —— 只在首次调用跑一次，但代价藏在
            // 「身份:读槽位词表」的外层标签里，看不出来。有缓存，所以最多一次。
            using (PerfProbe.Begin("ES3:槽位计数探测"))
            {
                int count = 0;
                for (int i = 1; i <= 64; i++)
                {
                    object probe = Es3Load("SelfBookList" + i, typeof(string[]), null,
                                           PersistentBookPath());
                    if (probe == null) break;
                    count = i;
                }
                _nativeSlotCount = count >= 4 ? count : 4;
                return _nativeSlotCount;
            }
        }

        // 存档文件时间戳：Host.Evaluate 每秒跑一次身份判定，其中两次 ES3 读取
        // （落盘书名 / 持久化槽位词表）读的是同一个 MyBook.es3，而它只在"游戏写盘"
        // 或"本 mod 物化写入"时变化。用 (mtime, size) 当缓存判据：一次 stat（O(1)）
        // 换掉一次 ES3 反序列化（8451 个字符串）。NTFS 的 mtime 精度 100ns，任何
        // 写入都会让它变，所以不会漏更新。
        internal static void BookFileStamp(out long ticks, out long size)
        {
            FileStamp(PersistentBookPath(), out ticks, out size);
        }

        // ES3 的**默认存档文件**（SaveFile.es3，本机实测 6.0MB / 341 个键）。
        // 这里单独量它的时间戳，因为 Es3Load/Es3Save 的无路径重载读写的都是这个
        // 文件，而它和 MyBook.es3 是**两个不同的文件**：第七轮之前 DiskBookName()
        // 读的是 SaveFile.es3、缓存判据却挂在 MyBook.es3 的 mtime 上 —— 判据挂错了
        // 文件，两边都会错：
        //   · 游戏写了 SaveFile.es3（换书就会写）而 MyBook.es3 没动 → 缓存不失效
        //     → 落盘书名读到旧值 → 身份判定与游戏实际状态不一致；
        //   · MyBook.es3 动了而 SaveFile.es3 没动 → 白付一次 6MB 整文件解析。
        internal static void SaveFileStamp(out long ticks, out long size)
        {
            FileStamp(PersistentSavePath(), out ticks, out size);
            // 兜底：万一某版本/某机器的 ES3 默认文件不叫 SaveFile.es3，就退化成按
            // MyBook.es3 的时间戳当判据。语义上不如正确判据强，但**不会**让缓存恒
            // 不成立 —— 恒不成立会让判据每轮多付一次 6MB 整文件解析，那是净退步。
            if (ticks < 0) FileStamp(PersistentBookPath(), out ticks, out size);
        }

        private static void FileStamp(string path, out long ticks, out long size)
        {
            ticks = -1;
            size = -1;
            if (string.IsNullOrEmpty(path)) return;
            try
            {
                FileInfo info = new FileInfo(path);
                if (!info.Exists) return;
                ticks = info.LastWriteTimeUtc.Ticks;
                size = info.Length;
            }
            catch { }
        }

        internal static IList<string> SlotWords(int slot)
        {
            SlotEntry entry = SlotEntryFor(slot);
            return entry == null ? null : entry.Words;
        }

        // 槽位词表的语言包归属。缓存语义见 SlotEntry.Profile 的注释。
        // cached 只用于日志/门禁计数（"这条快路径到底有没有吃到"），不参与判定。
        internal static BookProfile SlotProfile(int slot, BookRegistry registry, out bool cached)
        {
            cached = false;
            SlotEntry entry = SlotEntryFor(slot);
            if (entry == null || entry.Words == null || registry == null) return null;
            if (entry.ProfileReady && ReferenceEquals(entry.ProfileRegistry, registry))
            {
                cached = true;
                return entry.Profile;
            }
            BookProfile p = registry.Match(entry.Words);
            entry.Profile = p;
            entry.ProfileRegistry = registry;
            entry.ProfileReady = true;
            return p;
        }

        private static SlotEntry SlotEntryFor(int slot)
        {
            if (slot < 1 || slot > NativeSlotCount()) return null;
            long ticks, size;
            BookFileStamp(out ticks, out size);
            SlotEntry entry;
            if (_slotCache.TryGetValue(slot, out entry) &&
                ticks == entry.Ticks && size == entry.Size)
                return entry;
            using (PerfProbe.Begin("ES3:槽位词表"))
            {
                object value = Es3Load("SelfBookList" + slot, typeof(string[]), null,
                                      PersistentBookPath());
                IList<string> words = ToWordList(value);
                entry = new SlotEntry();
                entry.Words = words;
                entry.Ticks = ticks;
                entry.Size = size;
                _slotCache[slot] = entry;
                return entry;
            }
        }

        internal static int SlotOfBookName(string name)
        {
            if (string.IsNullOrEmpty(name) ||
                !name.StartsWith("自定义词书", StringComparison.Ordinal)) return 0;
            for (int i = 0; i < name.Length; i++)
            {
                char c = name[i];
                if (c == '一' || c == '1') return 1;
                if (c == '二' || c == '2') return 2;
                if (c == '三' || c == '3') return 3;
                if (c == '四' || c == '4') return 4;
            }
            return 0;
        }

        // 落盘书名。ES3 是游戏自带的静态类，这里只找 (string key, T default) 这个重载。
        // 与 SlotWords 同款按文件时间戳缓存（每秒一次的判定没必要重复反序列化）。
        internal static string DiskBookName()
        {
            long ticks, size;
            SaveFileStamp(out ticks, out size);
            if (_diskNameCached && ticks == _diskNameTicks && size == _diskNameSize)
                return _diskNameCache;
            using (PerfProbe.Begin("ES3:落盘书名"))
            {
                MethodInfo m = Es3LoadString();
                // ES3 类型没探到时不要落缓存：那是环境尚未就绪，不是"书名就是空"。
                if (m == null) return null;
                string value = null;
                try { value = m.Invoke(null, new object[] { "ChosenBook_Para", null }) as string; }
                catch (Exception) { value = null; }
                _diskNameCache = value;
                _diskNameCached = true;
                _diskNameTicks = ticks;
                _diskNameSize = size;
                return value;
            }
        }

        internal static object Es3Load(string key, Type valueType, object fallback,
                                       string filePath)
        {
            if (string.IsNullOrEmpty(key) || valueType == null) return fallback;
            // 批量写会话里刚写过的键必须「读到我自己的写」。无路径重载读的就是
            // 批量会话正在改的那个文件（SaveFile.es3），带路径的不受影响。
            if (string.IsNullOrEmpty(filePath))
            {
                Es3WriteBatch batch = _batch;
                if (batch != null && batch.WasWritten(key))
                {
                    object pending;
                    if (batch.TryGet(key, valueType, out pending)) return pending;
                }
            }
            try
            {
                bool hasPath = !string.IsNullOrEmpty(filePath);
                // MakeGenericMethod 不便宜，而这里是每秒都在走的路径（SlotWords /
                // DiskBookName / LoadOwned）。按 (重载, 值类型) 缓存绑定结果。
                Dictionary<Type, MethodInfo> cache = hasPath ? _loadFileCache : _loadDefaultCache;
                MethodInfo bound;
                if (!cache.TryGetValue(valueType, out bound))
                {
                    MethodInfo m = hasPath ? Es3LoadFileMethod() : Es3LoadDefaultMethod();
                    if (m == null) return fallback;
                    bound = m.MakeGenericMethod(valueType);
                    cache[valueType] = bound;
                }
                object[] args = hasPath
                    ? new object[] { key, filePath }
                    : new object[] { key, fallback };
                return bound.Invoke(null, args);
            }
            catch (Exception e)
            {
                Exception cause = e.InnerException ?? e;
                WarnOnce("load:" + key + ":" + valueType.FullName,
                    "读取 ES3 键失败 " + key + ": " + cause.Message);
                return fallback;
            }
        }

        internal static bool Es3Save(string key, object value)
        {
            if (string.IsNullOrEmpty(key) || value == null) return false;
            Es3WriteBatch batch = _batch;
            if (batch != null) return batch.Put(key, value);
            return Es3SaveDirect(key, value);
        }

        private static bool Es3SaveDirect(string key, object value)
        {
            try
            {
                Type valueType = value.GetType();
                MethodInfo bound;
                if (!_saveDirectCache.TryGetValue(valueType, out bound))
                {
                    MethodInfo m = Es3SaveMethod();
                    if (m == null) return false;
                    bound = m.MakeGenericMethod(valueType);
                    _saveDirectCache[valueType] = bound;
                }
                bound.Invoke(null, new object[] { key, value });
                return true;
            }
            catch (Exception e)
            {
                Exception cause = e.InnerException ?? e;
                Warn("写入 ES3 键失败 " + key + ": " + cause.Message);
                return false;
            }
        }

        // ── ES3 整文件写 → 批量写（第八轮，2026-09-18）────────────────────────
        //
        // 问题：ES3 的持久化是**整文件**的。`ES3.Save(key, value)` 每次都是
        // 「读整个存档 + 反序列化 + 序列化整个存档 + 写回」。本机默认存档
        // SaveFile.es3 = 6.0MB / 341 个顶层键。（注意：不是 MyBook.es3(2.1MB) ——
        // 无路径重载读写的从来都是 SaveFile.es3。）
        //
        // 离线实测（probes/es3bench/probe3.cs，**真实 ES3 程序集 + 真实存档副本**）：
        //     45 × ES3.Save<string>(k, v, path) = 5084 ms（首次 195ms，均 113ms/次）
        // 而首次 `Enforce` 要为每个受影响字段写 3 个键（`bak_` + `owned_` + 游戏字段），
        // 15 个字段 = 45 次整文件写 ≈ 5 s —— 这就是「刚进游戏 / 切换词书」那一下
        // 卡顿的主体（实机 `运行态:Tick` 单次 7727 ms，量级吻合）。
        //
        // 修法：用 ES3 自己为这件事提供的公开接口，不发明任何东西 ——
        //     ES3.CacheFile(s)        把文件读进 ES3File 缓存（一次整文件读）
        //     ES3.Save(k, v, s)       s.location == Cache → 只写内存字典
        //     ES3.StoreCachedFile(s)  一次整文件写
        // 同一条件下离线实测 110 ms（CacheFile 74 + 45 次内存写 1 + 提交 35）
        // = **46×**。
        //
        // 等价性（同一份离线 A/B 逐步断言，45 键）：
        //     · 文件大小相同（6042380 = 6042380）
        //     · 键集合相同（386 = 386，无独有键）
        //     · 386 个顶层键的内容块**逐字节相同**（0 个不一致）
        //     · 往返读回 0 失败；既有键 ja_owned_lists 取值相等
        //     · 唯一差别是顶层键的**排列顺序**：批量路径保留原顺序并在尾部追加，
        //       ES3 自己的 Merge 路径会把刚写的键提到最前。顺序不是存储契约 ——
        //       游戏按键读取，且游戏自己每次 ES3.Save 都会重排；两条路径各自都是
        //       确定的（两次相同输入产出的字节完全一致）。
        //     · 从「原始文件顺序」的角度看，批量路径反而**更**保序
        //       （原顺序是它的前缀；现有逐键路径不是）。
        //
        // 为什么不会写坏存档：settings 是从 `ES3Settings.defaultSettings`
        // （也就是游戏自己 `ES3.Save(key,value)` 内部用的那一份）**Clone** 出来的，
        // 只改 `path` 与 `location`。格式 / 压缩 / 加密 / 编码 / prettyPrint 全部
        // 由同一个对象复制而来 —— 这不是猜的。并且 `ES3File.Sync(settings)` 内部
        // 走的是 `ES3Writer.Create(settings, …)`，与逐键路径同一个 writer 工厂，
        // 未改动的键是**按原始序列化字节**回写的（`Write(key, type, bytes)`），
        // 根本不经过反序列化。
        //
        // 退化：批量不可用（ES3 反射拿不到 / defaultSettings 为空 / 提交抛错）时
        // 整个机制自动退回逐键写，语义与今天完全一致。任何一步失败都不会留下
        // 「写了一半」的状态：提交失败时逐键补写全部待写键。
        [ThreadStatic] private static Es3WriteBatch _batch;

        /// <summary>
        /// 开启一个批量写作用域。返回 null = 本次不做批量（调用方照常逐键写）。
        /// 作用域是**惰性**的：直到第一次真正要写才读文件 —— 所以「这一轮没有
        /// 任何字段需要改」这种稳态（每秒一次的 Enforce 绝大多数时候都是）成本为 0。
        /// </summary>
        internal static IDisposable Es3BatchScope()
        {
            if (_batch != null) return null;        // 已在批量里，不嵌套
            Es3WriteBatch probe = Es3WriteBatch.Create();
            if (probe == null) return null;
            return new BatchScope(probe);
        }

        // 第十六轮：写后置消化口（Host.Update 每帧调一次，最多提交一批；
        // 退出路径用 All 版本一次冲干净）。
        internal static void DrainEs3Writes() { Es3WriteBatch.DrainEs3Writes(); }
        internal static void DrainEs3WritesAll() { Es3WriteBatch.DrainEs3WritesAll(); }

        private sealed class BatchScope : IDisposable
        {
            private readonly Es3WriteBatch _previous;
            private bool _closed;

            internal BatchScope(Es3WriteBatch batch)
            {
                _previous = _batch;
                _batch = batch;
            }

            public void Dispose()
            {
                if (_closed) return;
                _closed = true;
                Es3WriteBatch batch = _batch;
                _batch = _previous;
                if (batch != null) batch.Dispose();
            }
        }

        // 一次批量写会话。第十六轮起为写后置：Create() 只做反射探测与 settings
        // 克隆，Put 只记账（_written），真正的「整文件装载 → 应用写入 → 落盘」
        // 整段发生在下一帧的 DrainEs3Writes()（见 Commit）。
        private sealed class Es3WriteBatch
        {
            private static bool _probed;
            private static MethodInfo _cacheFile;        // ES3.CacheFile(ES3Settings)
            private static MethodInfo _storeCachedFile;  // ES3.StoreCachedFile(ES3Settings)
            private static MethodInfo _saveWithSettings; // ES3.Save<T>(string,T,ES3Settings)
            private static MethodInfo _removeCachedFile; // ES3File.RemoveCachedFile(ES3Settings)（internal，可空）
            private static MethodInfo _clone;            // ES3Settings.Clone()
            private static PropertyInfo _defaultsProp;   // ES3Settings.defaultSettings
            private static PropertyInfo _locationProp;   // ES3Settings.location（可读写）
            private static PropertyInfo _pathProp;       // ES3Settings.path（属性形态）
            private static FieldInfo _pathField;         // ES3Settings.path（字段形态，本作的实际形态）
            private static bool _reportedOk;             // 只报一次「批量已启用」
            private static object _locationCache;        // ES3.Location.Cache（按名字取，不写死序号）
            // 第十五轮（2026-09-18）：跨作用域缓存复用。
            // 实机两轮采样（Player.log 22:54 / 23:13）切书帧账目：ES3:批量写(装载)
            // 130~148ms + 批量写(提交) 47~55ms，每次切书各一次。装载 = CacheFile
            // 整文件读+反序列化 —— 但上一轮提交成功后缓存条目与磁盘**必然一致**，
            // 下一轮再读纯属重复劳动。复用有两个前提，都由我们自己保证：
            //   a) ES3 的缓存字典按 settings 实例作键（引用相等）——所以 settings
            //      实例也跨作用域复用（克隆一次），换了实例就等于换了键；
            //   b) 文件可能被外部改写（游戏自己的 ES3.Save、其他插件）—— 用
            //      (mtime,size) 戳校验：命中才跳过装载，不一致就老实重读。
            // 提交失败 / 从未装载的路径维持旧行为：丢弃缓存条目，下轮整读。
            private static object _sharedSettings;       // 克隆一次、跨作用域复用的 ES3Settings
            private static string _sharedPath;
            private static bool _cacheAlive;             // 我们放进 ES3 全局缓存的条目是否还在
            private static bool _reuseReported;          // 只报一次「缓存复用生效」
            private static readonly Dictionary<string, long[]> _kept =
                new Dictionary<string, long[]>(StringComparer.OrdinalIgnoreCase); // path -> [mtimeTicks, size]
            private static readonly Dictionary<Type, MethodInfo> _saveCache =
                new Dictionary<Type, MethodInfo>();

            private readonly object _settings;
            private readonly string _path;
            private readonly Dictionary<string, object> _written =
                new Dictionary<string, object>(StringComparer.Ordinal);
            private bool _dirty;

            private Es3WriteBatch(object settings, string path)
            {
                _settings = settings;
                _path = path;
            }

            // 第一个缺失的前置条件；null = 全齐。存在的意义是**不许静默失败**：
            // 原来这里是 7 个条件串成的 `if (…) return null;`，一个接收者写错就能让
            // 整个批量机制失效而日志里一个字都没有，藏了整整一轮才被实机日志抓出来。
            private static string Missing()
            {
                if (_cacheFile == null) return "ES3.CacheFile(ES3Settings) 找不到";
                if (_storeCachedFile == null) return "ES3.StoreCachedFile(ES3Settings) 找不到";
                if (_saveWithSettings == null) return "ES3.Save<T>(string,T,ES3Settings) 找不到";
                if (_clone == null) return "ES3Settings.Clone() 找不到";
                if (_defaultsProp == null) return "ES3Settings.defaultSettings 找不到";
                if (_locationProp == null) return "ES3Settings.location 找不到";
                if (_locationCache == null) return "ES3.Location 取不到 Cache 成员";
                return null;
            }

            private static object PathOf(object settings)
            {
                if (_pathProp != null) return _pathProp.GetValue(settings, null);
                if (_pathField != null) return _pathField.GetValue(settings);
                return null;
            }

            internal static Es3WriteBatch Create()
            {
                Probe();
                string missing = Missing();
                if (missing != null)
                {
                    WarnOnce("batch:missing:" + missing,
                        "ES3 批量写不可用（退回逐键写，每次切书要多付约 45 次整档写）：" + missing);
                    return null;
                }
                try
                {
                    // 第十五轮：settings 实例跨作用域复用 —— ES3 缓存字典按实例作键，
                    // 每次克隆新实例等于每次换键，缓存条目就永远命中不了。
                    if (_sharedSettings != null)
                        return new Es3WriteBatch(_sharedSettings, _sharedPath);
                    object defaults = _defaultsProp.GetValue(null, null);
                    if (defaults == null) { WarnOnce("batch:defaults", "ES3 批量写不可用：默认设置读不到"); return null; }
                    // 从游戏自己那份 defaultSettings 克隆 —— 格式 / 压缩 / 加密 /
                    // 编码 / prettyPrint 全部同源，我们只改两项：path 不动，
                    // location 改成 Cache（让 ES3.Save 走内存字典）。
                    object settings = _clone.Invoke(defaults, null);
                    if (settings == null) { WarnOnce("batch:clone", "ES3 批量写不可用：Clone() 返回 null"); return null; }
                    // 没有 path 就不是默认存档 —— 这道门在 `_pathProp` 恒为 null 的时候
                    // 从来没生效过，现在走 PathOf()（属性→字段兜底）才真正跑起来。
                    object path = PathOf(settings);
                    if (path == null) { WarnOnce("batch:path", "ES3 批量写不可用：默认设置没有 path"); return null; }
                    _locationProp.SetValue(settings, _locationCache, null);
                    if (!_locationCache.Equals(_locationProp.GetValue(settings, null)))
                    { WarnOnce("batch:setter", "ES3 批量写不可用：location setter 没生效"); return null; }
                    // 成功也必须出声一次：否则「批量到底有没有生效」只能靠实机跑出来的
                    // 卡顿毫秒数反推（这正是上一轮发生的事）。
                    if (!_reportedOk)
                    {
                        _reportedOk = true;
                        if (WcpHostPlugin.Log != null)
                            WcpHostPlugin.Log.LogInfo("WcpHost: ES3 批量写已启用（一次整档读写" +
                                "替代 N 次逐键写，path=" + Convert.ToString(path) + "）");
                    }
                    _sharedPath = Convert.ToString(path);
                    _sharedSettings = settings;
                    return new Es3WriteBatch(settings, _sharedPath);
                }
                catch (Exception e)
                {
                    WarnOnce("batch:create", "ES3 批量写不可用（退回逐键写）: " + Msg(e));
                    return null;
                }
            }

            internal bool WasWritten(string key) { return _written.ContainsKey(key); }

            internal bool TryGet(string key, Type valueType, out object value)
            {
                value = null;
                object stored;
                if (!_written.TryGetValue(key, out stored)) return false;
                if (stored == null) return true;
                if (valueType.IsInstanceOfType(stored)) { value = stored; return true; }
                // 类型不完全一致时只做无损转换；转不了就交回调用方（退回磁盘读）。
                if (valueType == typeof(string[]) && stored is IEnumerable<string>)
                {
                    value = new List<string>((IEnumerable<string>)stored).ToArray();
                    return true;
                }
                if (valueType == typeof(List<string>) && stored is string[])
                {
                    value = new List<string>((string[])stored);
                    return true;
                }
                return false;
            }

            internal bool Put(string key, object value)
            {
                // 第十六轮（2026-09-18）：写后置（write-behind）。Put 只记账，
                // 不再当场碰 ES3 —— 整文件装载（实机 115~134ms）+ 序列化落盘
                // （41~80ms）整段挪到下一帧的 DrainEs3Writes() 里做。
                // 依据：R15 实机里缓存复用一次都没命中 —— 游戏自己每次答题都
                // 直写 SaveFile.es3，(mtime,size) 戳必然失配，装载躲不掉；
                // 那就别让它站在切书帧上。作用域内的读回由 TryGet（_written
                // 字典）覆盖，语义不变。
                _written[key] = value;
                _dirty = true;
                return true;
            }

            // ── 写后置队列（第十六轮）────────────────────────────────────
            // Dispose 不再当场提交：把整个批次排进 _pending，由 Host.Update
            // 每帧调 DrainEs3Writes() 消化（每帧最多一批，防止搬走一个坑又
            // 挖出另一个）。提交时才做「戳校验 → 整文件装载 → 应用写入 →
            // 序列化落盘」，全程离开切书帧。
            private static readonly List<Es3WriteBatch> _pending =
                new List<Es3WriteBatch>();
            private static bool _deferReported;

            internal static void DrainEs3Writes()
            {
                if (_pending.Count == 0) return;
                Es3WriteBatch batch = _pending[0];
                _pending.RemoveAt(0);
                batch.Commit();
            }

            internal static void DrainEs3WritesAll()
            {
                // 退出路径用：一次性冲干净，不能丢存档。
                while (_pending.Count > 0)
                {
                    Es3WriteBatch batch = _pending[0];
                    _pending.RemoveAt(0);
                    batch.Commit();
                }
            }

            private bool Load()
            {
                try
                {
                    long[] stamp;
                    if (_cacheAlive && _kept.TryGetValue(_path, out stamp) && MatchesFile(stamp))
                    {
                        // 缓存条目还活着，且磁盘文件的 (mtime,size) 与我们上次
                        // 装载/提交时记录的一致 → 缓存内容与磁盘必然一致，
                        // 整文件装载（实机 130~148ms）可以整段跳过。
                        if (!_reuseReported)
                        {
                            _reuseReported = true;
                            if (WcpHostPlugin.Log != null)
                                WcpHostPlugin.Log.LogInfo("WcpHost: ES3 批量写缓存复用生效（跳过整文件装载，路径戳一致）");
                        }
                        return true;
                    }
                    using (PerfProbe.Begin("ES3:批量写(装载)"))
                    {
                        // 缓存条目可能还活着但内容已过期（戳不匹配 = 文件被外部
                        // 改写过）。不赌 CacheFile 对已存在条目的覆盖语义：
                        // 先显式丢条目，再整文件重读 —— 两条语义下都正确。
                        if (_cacheAlive && _removeCachedFile != null)
                        {
                            try { _removeCachedFile.Invoke(null, new object[] { _settings }); }
                            catch (Exception) { }
                            _cacheAlive = false;
                        }
                        _cacheFile.Invoke(null, new object[] { _settings });
                    }
                    _kept[_path] = StampNow();
                    _cacheAlive = true;
                    return true;
                }
                catch (Exception e)
                {
                    Warn("ES3 批量写装载失败，本轮回退逐键写: " + Msg(e));
                    return false;
                }
            }

            /// <summary>写后置提交：装载 → 应用记账的写入 → 序列化落盘。</summary>
            private void Commit()
            {
                if (!_deferReported)
                {
                    _deferReported = true;
                    if (WcpHostPlugin.Log != null)
                        WcpHostPlugin.Log.LogInfo("WcpHost: ES3 批量写已改为写后置（切书帧只记账，" +
                            "装载+落盘在下一帧消化）");
                }
                bool stored = false;
                if (Load())
                {
                    try
                    {
                        foreach (KeyValuePair<string, object> kv in _written)
                        {
                            MethodInfo save;
                            if (!_saveCache.TryGetValue(kv.Value.GetType(), out save))
                            {
                                save = _saveWithSettings.MakeGenericMethod(kv.Value.GetType());
                                _saveCache[kv.Value.GetType()] = save;
                            }
                            save.Invoke(null, new object[] { kv.Key, kv.Value, _settings });
                        }
                        using (PerfProbe.Begin("ES3:批量写(提交)"))
                        {
                            _storeCachedFile.Invoke(null, new object[] { _settings });
                        }
                        stored = true;
                    }
                    catch (Exception e)
                    {
                        Warn("ES3 批量写提交失败，改为逐键补写 " + _written.Count +
                             " 个键: " + Msg(e));
                    }
                }
                if (stored)
                {
                    // 提交成功：缓存条目 == 磁盘内容。留在 ES3 全局缓存里，
                    // 记下新戳，下一次批量据此跳过整文件装载。
                    _kept[_path] = StampNow();
                    _cacheAlive = true;
                }
                else
                {
                    // 兜底：一个键一个键写回去。语义与改前一致（只是慢）。
                    foreach (KeyValuePair<string, object> kv in _written)
                        Es3SaveDirect(kv.Key, kv.Value);
                    DropCache();   // 提交失败：缓存内容不可信，丢弃，下轮老实重读
                }
                _written.Clear();
                _dirty = false;
            }

            internal void Dispose()
            {
                if (_dirty)
                {
                    // 第十六轮：写后置 —— 排队，下一帧 DrainEs3Writes() 里提交。
                    _pending.Add(this);
                    return;
                }
                // 没写过任何东西：无事可做（缓存条目按第十五轮的策略保留给下轮复用）。
            }

            // ── 路径戳与缓存条目管理（第十五轮）────────────────────────────
            private long[] StampNow()
            {
                // [mtimeTicks, size]；文件读不到时用不可能匹配的哨兵值。
                try
                {
                    FileInfo fi = new FileInfo(_path);
                    return new long[] { fi.LastWriteTimeUtc.Ticks, fi.Length };
                }
                catch (Exception) { return new long[] { long.MinValue, -1 }; }
            }

            private bool MatchesFile(long[] stamp)
            {
                try
                {
                    FileInfo fi = new FileInfo(_path);
                    return stamp[1] == fi.Length && stamp[0] == fi.LastWriteTimeUtc.Ticks;
                }
                catch (Exception) { return false; }
            }

            private void DropCache()
            {
                _kept.Remove(_path);
                _cacheAlive = false;
                if (_removeCachedFile == null) return;
                try { _removeCachedFile.Invoke(null, new object[] { _settings }); }
                catch (Exception) { }
            }

            private static string Msg(Exception e)
            {
                Exception c = e.InnerException ?? e;
                return c.GetType().Name + ": " + c.Message;
            }

            private static void Probe()
            {
                if (_probed) return;
                _probed = true;
                try
                {
                    Type es3 = AccessTools.TypeByName("ES3");
                    Type es3Settings = AccessTools.TypeByName("ES3Settings");
                    Type es3File = AccessTools.TypeByName("ES3File");
                    if (es3 == null || es3Settings == null) return;

                    _defaultsProp = es3Settings.GetProperty("defaultSettings",
                        BindingFlags.Public | BindingFlags.Static);
                    _locationProp = es3Settings.GetProperty("location",
                        BindingFlags.Public | BindingFlags.Instance);
                    _pathProp = es3Settings.GetProperty("path",
                        BindingFlags.Public | BindingFlags.Instance);
                    _clone = es3Settings.GetMethod("Clone", BindingFlags.Public | BindingFlags.Instance);
                    // ES3Settings.path 在本作里是**公开字段**（不是属性）：属性查询恒为 null，
                    // 于是 Create() 里那句「没有 path 就放弃」的安全检查**从来没跑过**。
                    // 字段兜底让这道门真正生效。
                    _pathProp = es3Settings.GetProperty("path",
                        BindingFlags.Public | BindingFlags.Instance);
                    if (_pathProp == null)
                        _pathField = es3Settings.GetField("path",
                            BindingFlags.Public | BindingFlags.Instance);

                    // ⚠ 第九轮（2026-09-18）根因修复 —— 这里原来是
                    //     `es3Settings.GetNestedType("Location", …)`
                    //   **接收者写错了**。`Location` 嵌在 `ES3` 里（`ES3+Location`），
                    //   不在 `ES3Settings` 上，所以 GetNestedType 恒返回 null →
                    //   `_locationCache` 恒为 null → `Create()` 在最后一道 null 检查上
                    //   **静默**返回 null（那条路径不写任何日志）。
                    //
                    //   后果：第八轮那一整套 ES3 批量写**在实机从未生效过**，
                    //   45 次 `Es3Save` 全部退化成一键一次整档读写。
                    //   实机代价 = 每次切书 4~8 秒（离线实测：45 次逐键 4216ms
                    //   vs 批量 94ms，44.9×；见 probes/es3bench/probe4_out.txt）。
                    //
                    //   教训：**静默的失败分支等于没有失败分支。** 这一轮把 Create() 的
                    //   每个 return null 都改成点名（见 Missing()），并加一条成功日志，
                    //   这样任何一次会话的 Player.log 都能直接回答「批量到底有没有生效」。
                    Type locationType = es3.GetNestedType("Location", BindingFlags.Public);
                    if (locationType == null)
                        locationType = es3.GetNestedType("Location",
                            BindingFlags.Public | BindingFlags.NonPublic);
                    if (locationType != null && locationType.IsEnum)
                    {
                        try
                        {
                            _locationCache = Enum.Parse(locationType, "Cache", false);
                        }
                        catch (Exception)
                        {
                            // 名字变了就按序数兜底：File, PlayerPrefs, InternalMS,
                            // Resources, Cache（离线核对 5.x 的顺序）。
                            Array values = Enum.GetValues(locationType);
                            if (values.Length > 4) _locationCache = values.GetValue(4);
                        }
                    }

                    MethodInfo[] statics = es3.GetMethods(BindingFlags.Public | BindingFlags.Static);
                    for (int i = 0; i < statics.Length; i++)
                    {
                        MethodInfo m = statics[i];
                        ParameterInfo[] ps = m.GetParameters();
                        if (m.Name == "CacheFile" && ps.Length == 1 &&
                            ps[0].ParameterType == es3Settings)
                            _cacheFile = m;
                        else if (m.Name == "StoreCachedFile" && ps.Length == 1 &&
                                 ps[0].ParameterType == es3Settings)
                            _storeCachedFile = m;
                        else if (m.Name == "Save" && m.IsGenericMethodDefinition && ps.Length == 3 &&
                                 ps[0].ParameterType == typeof(string) &&
                                 ps[1].ParameterType.IsGenericParameter &&
                                 ps[2].ParameterType == es3Settings)
                            _saveWithSettings = m;
                    }
                    if (es3File != null)
                    {
                        MethodInfo[] fs = es3File.GetMethods(BindingFlags.Static |
                            BindingFlags.NonPublic | BindingFlags.Public);
                        for (int i = 0; i < fs.Length; i++)
                            if (fs[i].Name == "RemoveCachedFile" &&
                                fs[i].GetParameters().Length == 1 &&
                                fs[i].GetParameters()[0].ParameterType == es3Settings)
                                _removeCachedFile = fs[i];
                    }
                }
                catch (Exception e)
                {
                    WarnOnce("batch:probe", "ES3 批量写探测失败（退回逐键写）: " + Msg(e));
                }
            }
        }

        internal static string PersistentBookPath()
        {
            try
            {
                return Path.Combine(Application.persistentDataPath, "MyBook.es3");
            }
            catch (Exception) { }
            return null;
        }

        // ES3 的默认存档文件。ES3Settings 的默认 path 就是引擎约定的
        // persistentDataPath + "/SaveFile.es3"（本机实测该文件存在、6.0MB，
        // 且 DiskBookName 读到的 ChosenBook_Para 与 CaptureList 写下的
        // fr_/ja_bak_* 键都在里面 —— 证据一致，见 probes/csbench/Bench2.cs 的 A/B 组）。
        internal static string PersistentSavePath()
        {
            try
            {
                return Path.Combine(Application.persistentDataPath, "SaveFile.es3");
            }
            catch (Exception) { }
            return null;
        }

        private static MethodInfo Es3LoadString()
        {
            if (_es3LoadString != null) return _es3LoadString;
            _es3Probed = true;
            try
            {
                Type es3 = AccessTools.TypeByName("ES3");
                if (es3 == null) return null;
                MethodInfo[] ms = es3.GetMethods(BindingFlags.Public | BindingFlags.Static);
                for (int i = 0; i < ms.Length; i++)
                {
                    MethodInfo m = ms[i];
                    if (m.Name != "Load" || !m.IsGenericMethodDefinition) continue;
                    ParameterInfo[] ps = m.GetParameters();
                    if (ps.Length == 2 && ps[0].ParameterType == typeof(string) &&
                        ps[1].ParameterType.IsGenericParameter)
                    {
                        _es3LoadString = m.MakeGenericMethod(typeof(string));
                        break;
                    }
                }
                if (_es3LoadString == null && WcpHostPlugin.Log != null)
                    WcpHostPlugin.Log.LogWarning("WcpHost: 找不到 ES3.Load<string>(string,T) 重载，" +
                        "落盘书名这一路判定降级（宿主将保持未激活）");
            }
            catch (Exception e)
            {
                if (WcpHostPlugin.Log != null) WcpHostPlugin.Log.LogWarning("WcpHost: ES3 探测失败: " + e.Message);
            }
            return _es3LoadString;
        }

        private static MethodInfo Es3LoadDefaultMethod()
        {
            ProbeEs3();
            return _es3LoadDefault;
        }

        private static MethodInfo Es3LoadFileMethod()
        {
            ProbeEs3();
            return _es3LoadFile;
        }

        private static MethodInfo Es3SaveMethod()
        {
            ProbeEs3();
            return _es3Save;
        }

        private static void ProbeEs3()
        {
            if (_es3Probed && (_es3LoadDefault != null || _es3LoadFile != null || _es3Save != null))
                return;
            _es3Probed = true;
            try
            {
                Type es3 = AccessTools.TypeByName("ES3");
                if (es3 == null) return;
                MethodInfo[] ms = es3.GetMethods(BindingFlags.Public | BindingFlags.Static);
                for (int i = 0; i < ms.Length; i++)
                {
                    MethodInfo m = ms[i];
                    if (!m.IsGenericMethodDefinition) continue;
                    ParameterInfo[] ps = m.GetParameters();
                    if (m.Name == "Load" && ps.Length == 2 &&
                        ps[0].ParameterType == typeof(string))
                    {
                        if (ps[1].ParameterType == typeof(string)) _es3LoadFile = m;
                        else if (ps[1].ParameterType.IsGenericParameter && _es3LoadDefault == null)
                            _es3LoadDefault = m;
                    }
                    else if (m.Name == "Save" && ps.Length == 2 &&
                             ps[0].ParameterType == typeof(string) &&
                             ps[1].ParameterType.IsGenericParameter && _es3Save == null)
                    {
                        _es3Save = m;
                    }
                }
            }
            catch (Exception e)
            {
                Warn("ES3 方法探测失败: " + e.Message);
            }
        }

        private static FieldInfo FindField(string typeName, string fieldName, bool instance)
        {
            if (instance) return null;
            string cacheKey = typeName + "." + fieldName;
            FieldInfo fi;
            if (_fields.TryGetValue(cacheKey, out fi)) return fi;
            try
            {
                Type t = AccessTools.TypeByName(typeName);
                fi = t == null ? null : FindField(t, fieldName);
            }
            catch (Exception) { fi = null; }
            _fields[cacheKey] = fi;
            if (fi == null) WarnMissing(cacheKey);
            return fi;
        }

        private static FieldInfo FindField(Type type, string fieldName)
        {
            string cacheKey = type.FullName + "." + fieldName;
            FieldInfo fi;
            if (_instanceFields.TryGetValue(cacheKey, out fi)) return fi;
            try
            {
                fi = AccessTools.Field(type, fieldName);
            }
            catch (Exception) { fi = null; }
            _instanceFields[cacheKey] = fi;
            if (fi == null) WarnMissing(cacheKey);
            return fi;
        }

        private static void WarnMissing(string key)
        {
            if (WcpHostPlugin.Log != null)
                WcpHostPlugin.Log.LogWarning("WcpHost: 游戏字段不可用 " + key +
                    "（游戏更新导致？本项功能降级，其余不受影响）");
        }

        // 名字叫 Once 就必须真的只报一次。上一版忽略了 key、每次调用都写一行 ——
        // 于是「批量写不可用」这种应当刺眼的告警会淹没在每秒几行的重复里。
        // 键有界（动态键不会把内存撑起来），超限后静默丢弃：宁可少报，不可无限累积。
        private static readonly HashSet<string> _warnedOnce =
            new HashSet<string>(StringComparer.Ordinal);
        private const int WarnOnceLimit = 500;

        private static void WarnOnce(string key, string message)
        {
            if (WcpHostPlugin.Log == null) return;
            if (key != null)
            {
                if (_warnedOnce.Count >= WarnOnceLimit) return;
                if (!_warnedOnce.Add(key)) return;
            }
            WcpHostPlugin.Log.LogWarning("WcpHost: " + message);
        }

        private static void Warn(string message)
        {
            if (WcpHostPlugin.Log != null)
                WcpHostPlugin.Log.LogWarning("WcpHost: " + message);
        }
        // ── 选项 B（2026-09-18）：只在「自定义」分类页美化书名 ────────────────
        // 游戏把自定义槽 4 渲染进每个官方分类页 Son 列表尾部（出厂态那行显示
        // 「自定义词书四」）；宿主/插件的美化只该发生在自定义分类页。
        // 页签判据 = WordChooseButtonS10.clickNum（当前 Father 索引，反编译核对
        // case 20 = 自定义）；兜底/校准 = 游戏原生自定义页行带全角括注「（…）」。
        // 判据缺失一律按「不是自定义页」处理 = 显示游戏原生名（fail-safe）。
        // 纯逻辑部分不引用 Unity 类型（配 _local/audit 的源码同文探针离线验证）。
        internal static class LabelPageGate
        {
            internal const int CustomCategoryDefault = 20;

            internal static int SlotFromCanon(string s, IList<string> canon)
            {
                if (string.IsNullOrEmpty(s) || canon == null) return 0;
                for (int i = 0; i < canon.Count; i++)
                {
                    if (string.IsNullOrEmpty(canon[i])) continue;
                    if (s.StartsWith(canon[i], StringComparison.Ordinal)) return i + 1;
                }
                return 0;
            }

            internal static bool IsCustomSlotLabel(string s, IList<string> canon,
                                                   IList<string> cosmetic)
            {
                if (string.IsNullOrEmpty(s)) return false;
                if (SlotFromCanon(s, canon) > 0) return true;
                for (int i = 0; cosmetic != null && i < cosmetic.Count; i++)
                    if (!string.IsNullOrEmpty(cosmetic[i]) &&
                        s.StartsWith(cosmetic[i], StringComparison.Ordinal)) return true;
                return false;
            }

            internal static string CanonicalAt(IList<string> canon, int slot)
            {
                if (canon == null || slot < 1 || slot > canon.Count) return null;
                return canon[slot - 1];
            }

            internal static bool HasWrapperMark(string s)
            {
                return !string.IsNullOrEmpty(s) && s.IndexOf('\uff08') >= 0;
            }

            internal static bool WrappedCustomRow(IList<string> texts, IList<bool> visible,
                                                  IList<string> canon, IList<string> cosmetic)
            {
                if (texts == null) return false;
                for (int i = 0; i < texts.Count; i++)
                {
                    if (visible != null && i < visible.Count && !visible[i]) continue;
                    if (!HasWrapperMark(texts[i])) continue;
                    if (IsCustomSlotLabel(texts[i], canon, cosmetic)) return true;
                }
                return false;
            }

            // 该行应当显示什么；null = 不动（与自定义槽无关的文字一律不碰）
            internal static string TargetRowText(string current, int slot, string desired,
                                                 bool onCustomPage, IList<string> canon,
                                                 IList<string> cosmetic)
            {
                if (slot < 1 || string.IsNullOrEmpty(current)) return null;
                if (!IsCustomSlotLabel(current, canon, cosmetic)) return null;
                string target = onCustomPage ? desired : CanonicalAt(canon, slot);
                if (string.IsNullOrEmpty(target) || target == current) return null;
                return target;
            }
        }

        // ── 自定义槽的规范名（生成，不写死上限；与 CustomSlotsMod 同规则）──
        private static readonly string[] CnDigits =
        {
            "\u4e00", "\u4e8c", "\u4e09", "\u56db", "\u4e94",
            "\u516d", "\u4e03", "\u516b", "\u4e5d"
        };

        internal static string CnNumber(int n)
        {
            if (n < 1 || n > 99) return null;
            if (n <= 9) return CnDigits[n - 1];
            int tens = n / 10;
            int ones = n % 10;
            string head = tens == 1 ? "\u5341" : CnDigits[tens - 1] + "\u5341";
            return ones == 0 ? head : head + CnDigits[ones - 1];
        }

        internal static string CanonicalBookName(int slot)
        {
            string digits = CnNumber(slot);
            return digits == null ? null : "\u81ea\u5b9a\u4e49\u8bcd\u4e66" + digits;
        }

        // canon[i] = 槽 i+1 的规范名，与 LabelPageGate 的约定一致
        internal static string[] CanonicalNames()
        {
            int count = NativeSlotCount();
            string[] names = new string[count];
            for (int i = 0; i < count; i++) names[i] = CanonicalBookName(i + 1);
            return names;
        }

        // ── 选书页类型（候选名；作者改名时补这里即可，缺失只让本项降级）──
        private static readonly string[] ChooserTypeCandidates =
        {
            "WordChooseButtonS10", "WordChooseButtonS11", "WordChooseButtonS12",
            "WordChooseButtonS13", "WordChooseButtonS9", "WordChooseButton"
        };
        private static bool _chooserProbed;
        private static Type _chooserType;

        internal static Type ChooserType()
        {
            if (_chooserProbed) return _chooserType;
            _chooserProbed = true;
            for (int i = 0; i < ChooserTypeCandidates.Length; i++)
            {
                Type t = null;
                try { t = AccessTools.TypeByName(ChooserTypeCandidates[i]); }
                catch (Exception) { t = null; }
                if (t == null) continue;
                _chooserType = t;
                break;
            }
            if (_chooserType == null)
                Warn("\u627e\u4e0d\u5230\u9009\u4e66\u9875\u7c7b\u578b\uff08\u5019\u9009\uff1a" +
                     string.Join("/", ChooserTypeCandidates) +
                     "\uff09\u2014\u2014 \u300c\u5206\u7c7b\u9875\u663e\u793a\u89c4\u8303\u540d\u300d\u8fd9\u4e00\u9879\u964d\u7ea7");
            return _chooserType;
        }

        // 场景里可见的选书页实例（同一组件可能多份实例；只认激活那份）
        //
        // 第七轮（2026-09-18）：原实现每调用一次就做一次
        // `Resources.FindObjectsOfTypeAll(chooser)` —— 那是全场景对象遍历，
        // 成本 ∝ 已加载对象数（本机日志 23504，峰值 5.5 万+），而调用方
        // HostRuntime.ScanBookLabels 每秒走一次。改成缓存实例 + 廉价判活。
        //
        // 两个必须小心的点：
        //  1) 「还活着吗」必须走 UnityEngine.Object 的 == 重载，所以字段的**静态
        //     类型必须是 Component**（不能是 object）—— 存进 object 再比较等于引用
        //     比较，被销毁的对象会永远被判为"还在"，缓存再也不会刷新。
        //  2) 缓存实例可能只是**失活**而不是销毁（跨页复用的对象就是这种）。判活
        //     必须同时看 activeInHierarchy，否则会在不可见页面上继续写标签。
        // 落空时退避 ChooserFindInterval 秒再找 —— 别在每个每秒轮次里重扫。
        private static Component _chooserCache;
        private static float _chooserNextFind = -1f;
        private const float ChooserFindInterval = 1f;

        internal static object ChooserInstance()
        {
            Type chooser = ChooserType();
            if (chooser == null) return null;

            Component cached = _chooserCache;
            if (cached != null && cached.gameObject != null &&
                cached.gameObject.activeInHierarchy)
                return cached;

            // 缓存失效（被销毁，或只是失活了）= "页面状态变了"的强信号 → **立刻**重查，
            // 不受退避影响。退避只用来压制"查不到"这种空扫：
            // 页面重新出现时若还要等 1 秒，标签会肉眼可见地晚一拍，那是行为回归，
            // 不能拿退避去省这一趟。
            if (_chooserNextFind > 0f && Time.unscaledTime < _chooserNextFind) return null;
            try
            {
                UnityEngine.Object[] all = Resources.FindObjectsOfTypeAll(chooser);
                for (int i = 0; i < all.Length; i++)
                {
                    Component c = all[i] as Component;
                    if (c == null || c.gameObject == null ||
                        !c.gameObject.activeInHierarchy) continue;
                    if (InstanceField(c, "BookNameText") == null) continue;
                    _chooserCache = c;
                    _chooserNextFind = -1f;
                    return c;
                }
            }
            catch (Exception) { }
            _chooserCache = null;
            _chooserNextFind = Time.unscaledTime + ChooserFindInterval;
            return null;
        }

        // 当前 Father(分类) 索引 = 游戏自己存的 clickNum；读不到返回 -1
        internal static int CurrentCategory(object chooser)
        {
            object raw = InstanceField(chooser, "clickNum");
            if (raw == null) return -1;
            try { return Convert.ToInt32(raw); }
            catch (Exception) { return -1; }
        }

        private static int _customCategory = LabelPageGate.CustomCategoryDefault;

        internal static int CustomCategory { get { return _customCategory; } }

        // 当前是不是「自定义」分类页；判据缺失一律按 false（显示游戏原生名）
        internal static bool IsCustomPage(object chooser, IList<string> texts,
                                          IList<bool> visible, IList<string> canon,
                                          IList<string> cosmetic)
        {
            bool wrapped = LabelPageGate.WrappedCustomRow(texts, visible, canon, cosmetic);
            int cur = CurrentCategory(chooser);
            if (cur < 0) return wrapped;
            if (wrapped && cur != _customCategory)
            {
                _customCategory = cur;
                Warn("\u81ea\u5b9a\u4e49\u5206\u7c7b\u7d22\u5f15 = " + cur +
                     "\uff08\u6765\u81ea\u539f\u751f\u62ec\u6ce8\u884c\uff09");
            }
            return cur == _customCategory;
        }

    }
}
