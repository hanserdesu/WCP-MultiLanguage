// WCP Host — 20 槽 store 的服务边界检查（P1-4）。
//
// 语义：指纹命中注册表只证明"这是本 mod 发布过的词书"，不证明"用户仍然
// 要它被服务"。服务范围以 CustomSlotsMod 落盘的 20 槽 store
// （WcpCustomSlots.json）为准：
//   - 托管播种行（安装器 slot_manifest 种子，owner=mod, managed=true）→ 在服务范围；
//   - 原生镜像行（owner=external, nativeSlot>0）→ 在服务范围（存量用户兼容）；
//   - 行被用户"移除"（清空复位）或从未登记 → 不在服务范围。
// store 文件不存在 = CustomSlotsMod 未安装/未运行过（纯安装器时代的部署）→
// 按兼容回退放行，保持旧指纹语义（不阻断存量用户）。
// store 存在但一条登记行都没有（20 行全是占位）= 尚未播种 → 同样按兼容回退
// 放行：空表表达不了"撤销服务"语义，fail-closed 只会把装好的词书一起挡掉。
// store 存在但解析失败 = 损坏 → fail-closed，等 CustomSlotsMod 下次保存自愈。
//
// 身份判定与注册表同源：对 store 行的 words 快照计算与 BookRegistry.FingerprintOf
// 相同的指纹，按 mtime 缓存解析结果，避免 1 秒轮询反复读 400KB 文件。
using System;
using System.Collections.Generic;
using System.IO;

namespace WcpHost
{
    internal sealed class SlotOwnership
    {
        private readonly string _storePath;
        private bool _loggedMissing;
        private bool _loggedCorrupt;
        private bool _loggedEmpty;

        // 解析缓存：mtime 未变时直接复用上一轮结论。
        private DateTime _cacheMtimeUtc;
        private bool _cacheValid;
        private readonly List<string> _servedFingerprints = new List<string>();
        private StoreStatus _cacheStatus = StoreStatus.NotPresent;

        // 第十四轮（2026-09-18）：行指纹按内容记忆化。CustomSlotsMod 每次保存都重写
        // 整个 store（mtime 必变），原实现每次重写都对每一行各跑一遍
        // Normalize(FormC)+排序+SHA256（实机 77~123ms，切换帧大头之一；两轮日志
        // 四次切换全部复现 130~165ms 重解析）。这里先对行词表算一个 O(总字符)、
        // 零分配的 FNV-1a 64 位内容键：键命中直接复用上次的全量指纹，未命中才
        // 回退 FingerprintOf。全内容参与散列 + 64 位键空间，碰撞概率可忽略；
        // memo 上限 256 条防膨胀（行数有限，实际远达不到）。
        private readonly Dictionary<ulong, string> _rowFingerprintMemo =
            new Dictionary<ulong, string>();

        /// <summary>测试观测点：行指纹记忆化命中次数（跨 mtime 变化累计）。</summary>
        internal int MemoHits { get { return _memoHits; } }
        private int _memoHits;

        private enum StoreStatus { NotPresent, Corrupt, Ok, Empty }

        internal SlotOwnership(string storePath)
        {
            _storePath = storePath;
        }

        /// <summary>
        /// 该指纹的词书是否在 20 槽服务范围内。reason 仅在返回 false 时有意义。
        /// </summary>
        internal bool IsServed(string fingerprint, out string reason)
        {
            reason = null;
            if (string.IsNullOrEmpty(fingerprint)) return false;

            RefreshCache();
            switch (_cacheStatus)
            {
                case StoreStatus.NotPresent:
                    // 兼容回退：没装 CustomSlotsMod（或它还没跑过第一次保存）的
                    // 环境没有 store。保持安装器时代的行为，不做更强约束。
                    return true;
                case StoreStatus.Empty:
                    // store 已落盘但一条登记行都没有（20 行全是占位：既非托管播种
                    // 行也非原生镜像行）。这是"还没播种"的状态，不是"用户撤销了
                    // 服务范围"——空表无法表达撤销语义，所以按兼容回退放行。
                    // （2026-09-17 实机：新装用户 store 只有占位行，fail-closed 会把
                    // 唯一装好的 ja 词书一起挡在门外 → 宿主完全不接管。）
                    return true;
                case StoreStatus.Corrupt:
                    reason = "20 槽存档不可读（损坏）— 服务边界 fail-closed，等 CustomSlotsMod 自愈";
                    return false;
            }

            for (int i = 0; i < _servedFingerprints.Count; i++)
                if (_servedFingerprints[i] == fingerprint) return true;

            reason = "词书不在 20 槽服务范围（从未登记为托管行/原生镜像行，或已被移除）";
            return false;
        }

        private void RefreshCache()
        {
            DateTime mtime;
            try
            {
                if (!File.Exists(_storePath))
                {
                    if (!_loggedMissing)
                    {
                        HostLog.Info("WcpHost: 槽位存档不存在（CustomSlotsMod 未运行过）— 按兼容回退放行，不启用槽位归属约束");
                        _loggedMissing = true;
                    }
                    _cacheStatus = StoreStatus.NotPresent;
                    _cacheValid = true;
                    return;
                }
                mtime = File.GetLastWriteTimeUtc(_storePath);
            }
            catch (Exception)
            {
                // 文件系统读失败：按损坏处理（fail-closed），下一轮重试。
                _cacheStatus = StoreStatus.Corrupt;
                _cacheValid = true;
                return;
            }

            if (_cacheValid && mtime == _cacheMtimeUtc &&
                (_cacheStatus == StoreStatus.Ok || _cacheStatus == StoreStatus.Empty)) return;
            if (_cacheValid && _cacheStatus != StoreStatus.Ok && _cacheStatus != StoreStatus.NotPresent &&
                _cacheStatus != StoreStatus.Empty)
            {
                // 损坏态每个探针周期都重试读取（自愈后立即恢复）。
            }

            _cacheMtimeUtc = mtime;
            _cacheValid = true;
            _servedFingerprints.Clear();

            // 第十轮加探针：这一段是**唯一**在身份判定路径上会做批量分配的代码 ——
            // store 的每一行都要 Json.StrList 出一份完整的词表快照（20 行 × 8000+ 词
            // ≈ 16 万个字符串对象），再对每份快照跑一次 FingerprintOf。
            // 它只在 mtime 变化时进入，所以平时看不见；而它正好也是"身份:Evaluate
            // 偶发 2712ms"这类尖峰最合理的 GC 来源。切出来，账才算得清。
            using (PerfProbe.Begin("槽位归属:重解析"))
            {
            string raw;
            try { raw = File.ReadAllText(_storePath); }
            catch (Exception e)
            {
                LogCorruptOnce("读取失败: " + e.Message);
                _cacheStatus = StoreStatus.Corrupt;
                return;
            }

            object parsed;
            try { parsed = Json.Parse(raw); }
            catch (Exception)
            {
                LogCorruptOnce("JSON 解析失败");
                _cacheStatus = StoreStatus.Corrupt;
                return;
            }

            Dictionary<string, object> root = parsed as Dictionary<string, object>;
            List<object> rows = null;
            if (root != null)
            {
                object slots;
                if (root.TryGetValue("slots", out slots)) rows = slots as List<object>;
            }
            if (rows == null)
            {
                LogCorruptOnce("缺少 slots 数组");
                _cacheStatus = StoreStatus.Corrupt;
                return;
            }

            for (int i = 0; i < rows.Count; i++)
            {
                Dictionary<string, object> row = rows[i] as Dictionary<string, object>;
                if (row == null) continue;

                bool managed = Json.Bool(row, "managed", false);
                int nativeSlot = Json.Int(row, "nativeSlot", 0);
                if (!managed && nativeSlot <= 0) continue;

                List<string> words = Json.StrList(row, "words");
                if (words == null || words.Count < BookPool.MinPlayable) continue;

                using (PerfProbe.Begin("槽位归属:行指纹"))
                {
                    try
                    {
                        string fp;
                        ulong cheap = CheapRowHash(words);
                        if (!_rowFingerprintMemo.TryGetValue(cheap, out fp))
                        {
                            fp = BookRegistry.FingerprintOf(words);
                            if (fp != null)
                            {
                                if (_rowFingerprintMemo.Count >= 256) _rowFingerprintMemo.Clear();
                                _rowFingerprintMemo[cheap] = fp;
                            }
                        }
                        else
                        {
                            _memoHits++;
                        }
                        _servedFingerprints.Add(fp);
                    }
                    catch (Exception) { /* 单行异常不拖垮整表 */ }
                }
            }

            if (_servedFingerprints.Count == 0)
            {
                if (!_loggedEmpty)
                {
                    HostLog.Info("WcpHost: 槽位存档存在但无登记行（尚未播种）— 按兼容回退放行，不启用槽位归属约束");
                    _loggedEmpty = true;
                }
                _cacheStatus = StoreStatus.Empty;
                return;
            }

            _cacheStatus = StoreStatus.Ok;
            }
        }

        // 行词表的内容键：FNV-1a 64 位，逐字符散列 + 词分隔符 + 行长度参与。
        // 只要求"同一内容 → 同一键"，不要求与 FingerprintOf 同分布；键相同而
        // 内容不同需要 64 位散列碰撞，可忽略。
        internal static ulong CheapRowHash(List<string> words)
        {
            unchecked
            {
                ulong h = 14695981039346656037UL;
                h = (h ^ (ulong)words.Count) * 1099511628211UL;
                for (int i = 0; i < words.Count; i++)
                {
                    string w = words[i];
                    if (w == null)
                    {
                        h = (h ^ 0x9E3779B97F4A7C15UL) * 1099511628211UL;
                        continue;
                    }
                    for (int j = 0; j < w.Length; j++)
                        h = (h ^ (ulong)w[j]) * 1099511628211UL;
                    h = (h ^ 0x1FUL) * 1099511628211UL;
                }
                return h;
            }
        }

        private void LogCorruptOnce(string detail)
        {
            if (_loggedCorrupt) return;
            _loggedCorrupt = true;
            HostLog.Warn("WcpHost: 槽位存档不可读（" + detail + "）— 槽位归属判定 fail-closed，待 CustomSlotsMod 重写后自动恢复");
        }
    }

    /// <summary>
    /// 极薄的日志门面：离线 harness 编译宿主 DLL 时没有 BepInEx Logger，
    /// 这里只走 Console，宿主进程里由 Host 在 Awake 注入真实 Logger。
    /// </summary>
    internal static class HostLog
    {
        internal static Action<string> InfoSink;
        internal static Action<string> WarnSink;

        internal static void Info(string message)
        {
            Action<string> sink = InfoSink;
            if (sink != null) sink(message); else Console.WriteLine(message);
        }

        internal static void Warn(string message)
        {
            Action<string> sink = WarnSink;
            if (sink != null) sink(message); else Console.WriteLine(message);
        }
    }
}
