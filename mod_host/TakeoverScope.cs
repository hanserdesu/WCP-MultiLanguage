// WCP Host — 运行态接管与还原协议
//
// 游戏的测试队列是全局单例。这个类把"进入一本受管词书时临时接管，
// 离开时只还原自己写过的字段"做成与语言无关的协议。所有持久化键都
// 使用 manifest.es3_prefix，避免不同语言的接管记录互相覆盖。
//
// 2026-09-15 隔离修正: 队列的**来源**必须换掉，而不是事后过滤。
// 旧实现只把全局队列里"不在本书"的词删掉，剩下的恰好是"英语书里学过的同形词"
// （法语书 20.2% 同形），战斗看起来全是英语；俄语书留下的队列也会一路带进日语。
// 现在: 词池字段一旦发现外部词或长度不足，就整体从当前词书重建
// （BookPool），全局已学词典只用于排序优先级，不再供词。
using System;
using System.Collections;
using System.Collections.Generic;

namespace WcpHost
{
    internal sealed class TakeoverScope
    {
        /// <summary>
        /// 受管字段表。规则只有两类:
        ///   Rebuild = true  词池: 发现外部词/长度不足时从本书整体重建（补池只能用本书）；
        ///   Rebuild = false 进度/用户选择: 只过滤外部词，绝不补词（补词会伪造学习进度）。
        /// PreferLearned 决定补池时"本书已学"还是"本书未学"优先:
        ///   复习/测试类池子优先已学，学习类队列优先未学。
        /// </summary>
        private sealed class FieldRule
        {
            internal readonly string Name;
            internal readonly bool IsArray;
            internal readonly bool Rebuild;
            internal readonly bool PreferLearned;
            internal readonly int MinTarget;

            internal FieldRule(string name, bool isArray, bool rebuild, bool preferLearned,
                               int minTarget)
            {
                Name = name;
                IsArray = isArray;
                Rebuild = rebuild;
                PreferLearned = preferLearned;
                MinTarget = minTarget;
            }
        }

        private static readonly FieldRule[] Rules = new FieldRule[] {
            // S7 战斗词表。游戏原本用全局已学词典 + one..five 占位词补齐。
            new FieldRule("S7TestWordList_Para", false, true, true, BookPool.MinPlayable),
            // S9 已学词测试池（ResetTestListQuick 由全局词典构造）
            new FieldRule("allTestWordsS10_Para", false, true, true, BookPool.MinPlayable),
            // S8 学习与复习队列
            new FieldRule("S8TestWordList_Para", false, true, false, BookPool.MinPlayable),
            new FieldRule("S8needToLearnWordList_Para", false, true, false, BookPool.MinPlayable),
            new FieldRule("S8TestWordList_DailyStudy", false, true, false, 0),
            new FieldRule("S8TestWordList_DailyStudy_left", false, true, false, 0),
            new FieldRule("S8TestWordList_DailyReview", false, true, true, 0),
            new FieldRule("S8TestWordList_DailyReview_left", false, true, true, 0),
            new FieldRule("S8TestWordList_ExtraStudy", false, true, false, 0),
            new FieldRule("S8TestWordList_ExtraStudy_left", false, true, false, 0),
            new FieldRule("S8TestWordList_ExtraReview", false, true, true, 0),
            new FieldRule("S8TestWordList_ExtraReview_left", false, true, true, 0),
            new FieldRule("S8TestWordList_LearnedTest_left", false, true, true, 0),
            // 进度与用户选择: 只过滤
            // 选词层隔离（2026-09-22）: 自由复习/自选测试的选词页渲染
            // S9CurrentArray_Para，勾选结果写进 S9extraStudy_Para，而
            // SwitchCurrentArrayS9.WordHaveLearned 把 S9CurrentArray_Para 换成
            // **全局** HaveLearnedDictionary.Keys —— 英语旧词全部在里面，
            // 只过滤候选表剔不干净同形词，所以候选表可从本书重建。
            // 勾选结果是用户选择，只能过滤，不能补进用户没选的词。
            // S9CurrentArray_Para 仍不落盘（原有边界: 它是场景态数组，游戏不读盘）。
            new FieldRule("S9CurrentArray_Para", true, true, false, 0),
            new FieldRule("S9extraStudy_Para", true, false, false, 0),
            new FieldRule("S8HaveLearnedWordList_Para", false, false, false, 0),
            new FieldRule("S7_SelfChosenWord_List", false, false, false, 0)
        };

        /// <summary>
        /// 学习进度来源（宿主启动时注入 GameLearnedStats.FromGame）。
        /// 未注入 = 没有进度信息: 只影响补池顺序，不影响隔离。测试直接给桩。
        /// </summary>
        internal static Func<ILearnedStats> StatsProvider;

        /// <summary>诊断出口（宿主注入到日志）。测试环境不注入 = 静默。</summary>
        internal static Action<string> WarnSink;

        private LanguageManifest _manifest;
        private IList<string> _bookWords;
        private readonly Dictionary<string, List<string>> _listBaselines =
            new Dictionary<string, List<string>>(StringComparer.Ordinal);
        private readonly Dictionary<string, string[]> _arrayBaselines =
            new Dictionary<string, string[]>(StringComparer.Ordinal);
        private readonly HashSet<string> _ownedLists =
            new HashSet<string>(StringComparer.Ordinal);
        private readonly HashSet<string> _ownedArrays =
            new HashSet<string>(StringComparer.Ordinal);
        private bool _active;

        internal bool IsActive { get { return _active; } }
        internal string ProfileId { get { return _manifest == null ? null : _manifest.Profile.Id; } }

        internal void Enter(LanguageManifest manifest, IList<string> bookWords)
        {
            if (manifest == null || bookWords == null || bookWords.Count == 0)
            {
                Leave();
                return;
            }
            if (_active && _manifest != null && _manifest.Profile.Id == manifest.Profile.Id)
            {
                _bookWords = bookWords;
                return;
            }
            Leave();
            _manifest = manifest;
            _bookWords = new List<string>(bookWords);
            _active = true;
            // A previous process may have exited in this same profile. Restore
            // its baseline before taking ownership again, or the filtered queue
            // would become the next baseline and leak when leaving the book.
            RecoverStale(null);
        }


        internal void Leave()
        {
            if (!_active || _manifest == null)
            {
                _manifest = null;
                _bookWords = null;
                _active = false;
                return;
            }
            // 同一次还原里的多个字段写也合并成一次整档读写（切书离开时这笔最重：
            // 每个待还原字段各写一次 bak_/owned_/游戏字段）。
            using (GameAdapter.Es3BatchScope())
            {
                RestoreOwned(_manifest.Profile.Es3Prefix);
            }
            string[] s9Baseline;
            if (_arrayBaselines.TryGetValue("S9CurrentArray_Para", out s9Baseline))
            {
                GameAdapter.SetStaticField(GameAdapter.ParametersType, "S9CurrentArray_Para", s9Baseline);
            }
            _listBaselines.Clear();
            _arrayBaselines.Clear();
            _ownedLists.Clear();
            _ownedArrays.Clear();
            _manifest = null;
            _bookWords = null;
            _active = false;
        }

        // 当前 profile 变化后，清理上一次会话留下但不属于当前 pack 的接管记录。
        // 只处理 manifest 注册表里的前缀；未知键永远不猜、不碰。
        internal void RecoverStale(string activeProfileId)
        {
            BookRegistry registry = WcpHostPlugin.Instance == null ? null :
                WcpHostPlugin.Instance.Registry;
            RecoverStale(registry, activeProfileId);
        }

        // ── 「哪些 prefix 可能有残留标记」索引 ────────────────────────────────
        //
        // 第七轮（2026-09-18）新增。原实现是**无条件**为注册表里每一个语言包都做一次
        // `RestoreOwned`，而 `RestoreOwned` 一进门就要读两个键（prefix_owned_lists /
        // prefix_owned_arrays）来判断"有没有残留"。ES3 的读是**整文件解析**：本机
        // 默认存档 SaveFile.es3 = 6.0MB / 341 个键，所以每个语言包 2 次 = 9 个包 18 次
        // 整文件解析。实测（第六轮日志）：首次激活那一次 `身份:Evaluate` 就花了 **698.5ms**，
        // 量级与 18 × ~39ms 完全吻合，而结论每次都是"没有残留，直接返回"。
        //
        // 改法：加一个 mod 自己的索引键，记下"真的写过标记的 prefix"。读一次索引
        // （O(1) 次整文件解析）就能跳过其余全部语言包。
        //
        // 正确性（这是纯读优化，不放松任何判定）：
        //   能出现残留标记的 prefix 只有两类来源 ——
        //     ① 本进程 `CaptureList/CaptureArray` 写下的（记在 `_capturedPrefixes`）；
        //     ② 旧构建写下的（此时索引键在存档里**根本不存在** → 走 legacy 全扫）。
        //   只要索引键存在，任何"不在索引且不在 _capturedPrefixes"的 prefix 都必然
        //   没有标记，跳过它不改变任何判定。索引每轮都会被重新写回实际剩余集合，
        //   所以它不会永久漏掉谁。
        private const string OwnedIndexKey = "wcp_owned_prefixes";
        private readonly HashSet<string> _capturedPrefixes =
            new HashSet<string>(StringComparer.Ordinal);

        private static string[] LoadOwnedOrNull(string key)
        {
            return GameAdapter.Es3Load(key, typeof(string[]), null, null) as string[];
        }

        internal void RecoverStale(BookRegistry registry, string activeProfileId)
        {
            if (registry == null) return;
            // 稳态下这段一个键都不写（索引已就位、没有残留），批量作用域因此不会
            // 触发装载 —— 成本为 0。只有真的迁移/清理时才落到一次整档读写。
            using (GameAdapter.Es3BatchScope())
            {
                string[] raw = LoadOwnedOrNull(OwnedIndexKey);
                bool legacy = raw == null;   // 索引键不存在 = 旧构建写过标记 → 只能全扫一遍
                HashSet<string> index = new HashSet<string>(
                    raw ?? new string[0], StringComparer.Ordinal);
                bool dirty = legacy;         // 迁移：索引缺失时补一次，之后不再写
                for (int i = 0; i < registry.Manifests.Count; i++)
                {
                    LanguageManifest m = registry.Manifests[i];
                    if (m.Profile.Id == activeProfileId) continue;
                    string prefix = m.Profile.Es3Prefix;
                    if (string.IsNullOrEmpty(prefix)) continue;
                    if (!legacy && !index.Contains(prefix) && !_capturedPrefixes.Contains(prefix))
                        continue;
                    if (RestoreOwned(prefix))
                    {
                        if (index.Add(prefix)) dirty = true;
                    }
                    else if (index.Remove(prefix)) dirty = true;
                }
                // 本进程刚捕获过标记的 prefix 必须并进索引，否则下一轮会跳过它、
                // 把这次会话留下的残留标记漏在存档里。
                foreach (string captured in _capturedPrefixes)
                    if (index.Add(captured)) dirty = true;
                if (!dirty) return;
                GameAdapter.Es3Save(OwnedIndexKey, ToArray(index));
            }
        }

        internal void Enforce()
        {
            if (!_active || _manifest == null || _bookWords == null || _bookWords.Count == 0)
                return;

            // 一次 Enforce 里对 ES3 的所有写合并成「一次整文件读 + 一次整文件写」。
            // 首次落位时这一轮要写 ~45 个键（每个字段 bak_/owned_/游戏字段 各一次），
            // 逐键写是 45 次整档读写（离线实测 5084ms），批量后 110ms。作用域是惰性的，
            // 本轮不需要改任何字段时（稳态的绝大多数轮次）成本为 0。
            using (GameAdapter.Es3BatchScope())
            {
                // 第十一轮（2026-09-18）加探针：实机切书帧 `运行态:队列校正` 单次
                // 257.8ms，稳态每秒 ~34ms。批量的账（装载+提交）已经单独有标签，
                // 但扣除批量之后剩下那部分一直没归属。这里的三个候选是
                // BookPool.ToSet（8000+ 词的 HashSet 构建）、18 条规则的扫描/改写、
                // 以及 AlignTestQueue。拆开才知道下一轮该动哪一个。
                HashSet<string> allowed;
                using (PerfProbe.Begin("队列:授权集")) allowed = BookPool.ToSet(_bookWords);
                // 词书本身不够游戏下限（坏语言包）时仍然只做过滤、不补词:
                // 过滤是隔离要求，补词是内容要求。
                bool canRebuild = allowed.Count >= BookPool.MinPlayable;

                ILearnedStats stats = StatsProvider == null ? null : StatsProvider();
                PoolOrder order = ReadOrder();
                using (PerfProbe.Begin("队列:规则"))
                {
                    // 第十四轮（2026-09-18）：一次 Enforce 内 14 条 Rebuild 规则共享
                    // 同一份「分区+排序」计划（原实现每条规则各跑一遍 8451 词的分区
                    // 与反射比较器排序，实机切换帧单次 642~706ms）；FilterOnly 也改用
                    // 上面建好的授权集，不再每条规则重建一遍 HashSet。生命周期 =
                    // 一次 Enforce：不跨轮缓存，学习进度与随机洗牌照常逐轮刷新。
                    BookPool.Plan plan = new BookPool.Plan(_bookWords, stats, order);
                    for (int i = 0; i < Rules.Length; i++)
                    {
                        FieldRule rule = Rules[i];
                        try
                        {
                            if (rule.IsArray) EnforceArray(rule, allowed);
                            else EnforceList(rule, allowed, plan, canRebuild);
                        }
                        catch (Exception e)
                        {
                            if (WarnSink != null)
                                WarnSink("WcpHost: 队列隔离失败 " + rule.Name + ": " + e.Message);
                        }
                    }
                }
                using (PerfProbe.Begin("队列:对齐")) AlignTestQueue(allowed);
            }
        }

        /// <summary>
        /// 供补池入口（ChooseWordManager.AddWordsToSelfChosenList）调用:
        /// 用同一套规则重建指定词池。
        /// 返回 null = 不接管（未激活 / 字段不受管 / 本书词不足 / 结果与现状一致）。
        /// </summary>
        internal List<string> RebuildPool(string fieldName, IList<string> current, int requested)
        {
            if (!_active || _manifest == null || _bookWords == null || _bookWords.Count == 0)
                return null;
            FieldRule rule = FindRule(fieldName);
            if (rule == null || !rule.Rebuild) return null;
            HashSet<string> allowed = BookPool.ToSet(_bookWords);
            if (allowed.Count < BookPool.MinPlayable) return null;

            int target = requested;
            if (current != null && current.Count > target) target = current.Count;
            if (target < rule.MinTarget) target = rule.MinTarget;
            if (rule.Name == "S7TestWordList_Para") target = FightTarget(target);

            ILearnedStats stats = StatsProvider == null ? null : StatsProvider();
            List<string> rebuilt = BookPool.Rebuild(_bookWords, stats, ReadOrder(),
                rule.PreferLearned, target);
            if (rebuilt == null || rebuilt.Count == 0) return null;
            if (Same(current, rebuilt)) return null;
            using (GameAdapter.Es3BatchScope())
            {
                if (!CaptureList(fieldName, current)) return null;
            }
            return rebuilt;
        }

        private static FieldRule FindRule(string name)
        {
            for (int i = 0; i < Rules.Length; i++)
                if (!Rules[i].IsArray && Rules[i].Name == name) return Rules[i];
            return null;
        }

        /// <summary>
        /// 单字段隔离。词池字段（Rebuild）在两种情况整体重建:
        ///   1. 列表里出现不属于本书的词 —— 语言切换后的残留，必须换成本书词；
        ///   2. 列表长度低于游戏下限 —— 游戏会用全局词典或 one..five 占位词补，必须由本书补。
        /// 已经"干净且够长"的列表一律不重写: 保留玩家当前的复习顺序，避免每次轮询都动它。
        /// </summary>
        private void EnforceList(FieldRule rule, HashSet<string> allowed,
                                 BookPool.Plan plan, bool canRebuild)
        {
            object raw = GameAdapter.StaticField(GameAdapter.ParametersType, rule.Name);
            IList<string> current = GameAdapter.ToWordList(raw);
            if (current == null || current.Count == 0) return;   // 游戏本来就让它空着: 不凭空造内容

            List<string> next;
            if (rule.Rebuild)
            {
                int target = current.Count;
                if (target < rule.MinTarget) target = rule.MinTarget;
                if (rule.Name == "S7TestWordList_Para") target = FightTarget(target);
                bool foreign = ContainsForeign(current, allowed);
                if (!canRebuild || (!foreign && current.Count >= target))
                {
                    next = BookPool.FilterOnly(current, allowed);
                    if (next == null) return;                    // 已经干净: 不动
                }
                else
                {
                    next = plan.Rebuild(rule.PreferLearned, target);
                }
            }
            else
            {
                next = BookPool.FilterOnly(current, allowed);
            }
            if (next == null) return;
            if (Same(current, next)) return;
            if (!CaptureList(rule.Name, current)) return;
            object replacement = ListValueForField(raw, next);
            if (!GameAdapter.SetStaticField(GameAdapter.ParametersType, rule.Name, replacement)) return;
            GameAdapter.Es3Save(rule.Name, replacement);
        }

        private void EnforceArray(FieldRule rule, HashSet<string> allowed)
        {
            object raw = GameAdapter.StaticField(GameAdapter.ParametersType, rule.Name);
            string[] current = ToArray(raw);
            if (current == null || current.Length == 0) return;
            List<string> filtered;
            if (rule.Rebuild)
            {
                // 选词层隔离（2026-09-22）: 数组词池与列表词池同一语义。
                // 书里同形的英语旧词（HaveLearnedDictionary 全集）靠过滤剔不掉，
                // 必须换来源: 发现外部词时从本书词池整体重建，规模对齐原数组。
                // 已是本书词的数组不动 —— 保留玩家当前选词页的翻页位置与勾选。
                bool foreign = ContainsForeign(current, allowed);
                if (!foreign) return;
                int target = current.Length;
                if (target < rule.MinTarget) target = rule.MinTarget;
                filtered = BookPool.Rebuild(_bookWords, StatsProvider == null ? null : StatsProvider(),
                    ReadOrder(), rule.PreferLearned, target);
                if (filtered == null || filtered.Count == 0) return;
                if (filtered.Count > target) filtered.RemoveRange(target, filtered.Count - target);
            }
            else
            {
                filtered = BookPool.FilterOnly(current, allowed);
            }
            if (filtered == null) return;
            if (Same(current, filtered)) return;
            if (!CaptureArray(rule.Name, current)) return;
            string[] value = filtered.ToArray();
            if (!GameAdapter.SetStaticField(GameAdapter.ParametersType, rule.Name, value)) return;
            if (rule.Name != "S9CurrentArray_Para")
                GameAdapter.Es3Save(rule.Name, value);
        }

        // 题干队列必须和测试词池的当前进度对齐。只在游戏已经进入已学词测试
        // 或者两张表本来就有内容时修正，避免给普通词书流程凭空制造测试状态。
        private void AlignTestQueue(HashSet<string> allowed)
        {
            if (!IsLearnedTest()) return;
            object poolRaw = GameAdapter.StaticField(GameAdapter.ParametersType, "allTestWordsS10_Para");
            List<string> pool = GameAdapter.ToWordList(poolRaw) as List<string>;
            if (pool == null)
            {
                IList<string> any = GameAdapter.ToWordList(
                    poolRaw);
                if (any == null) return;
                pool = new List<string>(any);
            }
            if (pool.Count < 5) return;

            int progress = ReadInt("S8Progress_Para", 0);
            if (progress < 0 || progress >= pool.Count) progress = 0;
            List<string> expected = new List<string>();
            for (int i = progress; i < pool.Count; i++) expected.Add(pool[i]);

            object needRaw = GameAdapter.StaticField(GameAdapter.ParametersType, "S8needToLearnWordList_Para");
            IList<string> current = GameAdapter.ToWordList(needRaw);
            if (current == null || current.Count == 0 || current[0] != pool[progress] ||
                !ContainsOnly(current, allowed))
            {
                List<string> old = current == null ? new List<string>() : new List<string>(current);
                if (!CaptureList("S8needToLearnWordList_Para", old)) return;
                object replacement = ListValueForField(needRaw, expected);
                if (!GameAdapter.SetStaticField(GameAdapter.ParametersType, "S8needToLearnWordList_Para", replacement)) return;
                GameAdapter.Es3Save("S8needToLearnWordList_Para", replacement);
            }
        }

        private static bool ContainsForeign(IList<string> values, HashSet<string> allowed)
        {
            for (int i = 0; i < values.Count; i++)
            {
                string word = values[i];
                if (string.IsNullOrEmpty(word)) continue;
                if (!allowed.Contains(word.Trim())) return true;
            }
            return false;
        }

        private int FightTarget(int fallback)
        {
            object value = GameAdapter.StaticField(GameAdapter.ParametersType, "S7FightWordMax");
            int configured = value is int ? (int)value : 0;
            return configured > fallback ? configured : fallback;
        }

        private static object ListValueForField(object raw, IList<string> values)
        {
            if (raw is string[])
                return new List<string>(values).ToArray();
            return new List<string>(values);
        }

        private bool CaptureList(string fieldName, IList<string> current)
        {
            if (_ownedLists.Contains(fieldName)) return true;
            List<string> baseline = current == null ? new List<string>() : new List<string>(current);
            if (!GameAdapter.Es3Save(Key("bak_" + fieldName), baseline.ToArray())) return false;
            _ownedLists.Add(fieldName);
            _capturedPrefixes.Add(_manifest.Profile.Es3Prefix);
            if (!GameAdapter.Es3Save(Key("owned_lists"), ToArray(_ownedLists)))
            {
                _ownedLists.Remove(fieldName);
                return false;
            }
            _listBaselines[fieldName] = baseline;
            return true;
        }

        private bool CaptureArray(string fieldName, string[] current)
        {
            if (_ownedArrays.Contains(fieldName)) return true;
            string[] baseline = current == null ? new string[0] : (string[])current.Clone();
            if (fieldName == "S9CurrentArray_Para")
            {
                _ownedArrays.Add(fieldName);
                _arrayBaselines[fieldName] = baseline;
                return true;
            }
            if (!GameAdapter.Es3Save(Key("bak_" + fieldName), baseline)) return false;
            _ownedArrays.Add(fieldName);
            _capturedPrefixes.Add(_manifest.Profile.Es3Prefix);
            if (!GameAdapter.Es3Save(Key("owned_arrays"), ToArray(_ownedArrays)))
            {
                _ownedArrays.Remove(fieldName);
                return false;
            }
            _arrayBaselines[fieldName] = baseline;
            return true;
        }

        // 返回 true = 这个 prefix 在库里**仍然**有未完成的残留标记（下次还要再看）。
        private bool RestoreOwned(string prefix)
        {
            if (string.IsNullOrEmpty(prefix)) return false;
            HashSet<string> lists = new HashSet<string>(LoadOwned(prefix + "_owned_lists"), StringComparer.Ordinal);
            HashSet<string> arrays = new HashSet<string>(LoadOwned(prefix + "_owned_arrays"), StringComparer.Ordinal);
            bool local = _manifest != null && _manifest.Profile.Es3Prefix == prefix;
            if (local)
            {
                lists.UnionWith(_ownedLists);
                arrays.UnionWith(_ownedArrays);
            }
            // An inactive host must be completely read-only when it has no
            // ownership marker.  Writing empty marker arrays on every probe
            // races legacy language plugins while they switch books.
            if (lists.Count == 0 && arrays.Count == 0) return false;
            HashSet<string> pendingLists = new HashSet<string>(StringComparer.Ordinal);
            HashSet<string> pendingArrays = new HashSet<string>(StringComparer.Ordinal);
            bool restoredPool = false;
            foreach (string field in lists)
            {
                if (!IsKnownListField(field)) continue;
                List<string> baseline = null;
                if (local) _listBaselines.TryGetValue(field, out baseline);
                if (baseline == null)
                {
                    string[] saved = GameAdapter.Es3Load(prefix + "_bak_" + field,
                        typeof(string[]), null, null) as string[];
                    if (saved != null) baseline = new List<string>(saved);
                }
                if (baseline == null || !RestoreList(field, baseline)) pendingLists.Add(field);
                else if (field == "allTestWordsS10_Para") restoredPool = true;
            }
            foreach (string field in arrays)
            {
                if (!IsKnownArrayField(field)) continue;
                string[] baseline = null;
                if (local) _arrayBaselines.TryGetValue(field, out baseline);
                if (baseline == null && field != "S9CurrentArray_Para")
                    baseline = GameAdapter.Es3Load(prefix + "_bak_" + field,
                        typeof(string[]), null, null) as string[];
                if (field == "S9CurrentArray_Para")
                {
                    if (baseline != null) RestoreArray(field, baseline);
                    continue;
                }
                if (baseline == null || !RestoreArray(field, baseline)) pendingArrays.Add(field);
            }
            if (restoredPool) MarkNoTestIfUnsafe();
            GameAdapter.Es3Save(prefix + "_owned_lists", ToArray(pendingLists));
            GameAdapter.Es3Save(prefix + "_owned_arrays", ToArray(pendingArrays));
            return pendingLists.Count > 0 || pendingArrays.Count > 0;
        }

        private static bool IsKnownListField(string name)
        {
            for (int i = 0; i < Rules.Length; i++)
                if (!Rules[i].IsArray && Rules[i].Name == name) return true;
            return false;
        }

        private static bool IsKnownArrayField(string name)
        {
            for (int i = 0; i < Rules.Length; i++)
                if (Rules[i].IsArray && Rules[i].Name == name) return true;
            return false;
        }

        private bool RestoreList(string fieldName, List<string> value)
        {
            object current = GameAdapter.StaticField(GameAdapter.ParametersType, fieldName);
            object replacement;
            if (current is string[]) replacement = value.ToArray();
            else replacement = value;
            if (!GameAdapter.SetStaticField(GameAdapter.ParametersType, fieldName, replacement)) return false;
            return GameAdapter.Es3Save(fieldName, replacement);
        }

        private bool RestoreArray(string fieldName, string[] value)
        {
            if (!GameAdapter.SetStaticField(GameAdapter.ParametersType, fieldName,
                (string[])value.Clone())) return false;
            if (fieldName == "S9CurrentArray_Para")
                return true;
            return GameAdapter.Es3Save(fieldName, (string[])value.Clone());
        }

        private string Key(string suffix)
        {
            return _manifest == null ? suffix : _manifest.Profile.Es3Prefix + "_" + suffix;
        }

        private static string[] LoadOwned(string key)
        {
            string[] value = GameAdapter.Es3Load(key, typeof(string[]), null, null) as string[];
            return value ?? new string[0];
        }

        private bool IsLearnedTest()
        {
            object mode = GameAdapter.StaticField(GameAdapter.ParametersType, "S8ThisMode_Para");
            return string.Equals(mode as string, "已学词测试", StringComparison.Ordinal);
        }

        private void MarkNoTestIfUnsafe()
        {
            IList<string> pool = GameAdapter.ToWordList(
                GameAdapter.StaticField(GameAdapter.ParametersType, "allTestWordsS10_Para"));
            if (pool != null && pool.Count >= 5) return;
            GameAdapter.SetStaticField(GameAdapter.ParametersType, "S8Progress_Para", 0);
            GameAdapter.Es3Save("S8Progress_Para", 0);
            GameAdapter.SetStaticField(GameAdapter.ParametersType, "testingIf_Para", false);
            GameAdapter.Es3Save("testingIf_Para", false);
            GameAdapter.SetStaticField(GameAdapter.ParametersType, "testingIf_CompleteIf", true);
            GameAdapter.Es3Save("testingIf_CompleteIf", true);
        }

        private int ReadInt(string fieldName, int fallback)
        {
            object value = GameAdapter.StaticField(GameAdapter.ParametersType, fieldName);
            if (value is int) return (int)value;
            return fallback;
        }

        private PoolOrder ReadOrder()
        {
            PoolOrder order = new PoolOrder();
            object mode = GameAdapter.StaticField(GameAdapter.ParametersType, "testNegOrPos");
            string text = mode as string;
            if (!string.IsNullOrEmpty(text)) order.Mode = text;
            object priority = GameAdapter.StaticField(GameAdapter.ParametersType, "testPriorityOn");
            if (priority is bool) order.PriorityOn = (bool)priority;
            return order;
        }

        private static string[] ToArray(object raw)
        {
            if (raw == null || raw is string) return null;
            if (raw is string[]) return (string[])((string[])raw).Clone();
            IEnumerable seq = raw as IEnumerable;
            if (seq == null) return null;
            List<string> result = new List<string>();
            try
            {
                foreach (object item in seq) result.Add(item == null ? null : item.ToString());
            }
            catch (Exception) { return null; }
            return result.ToArray();
        }

        private static bool ContainsOnly(IList<string> values, HashSet<string> allowed)
        {
            for (int i = 0; i < values.Count; i++)
                if (string.IsNullOrEmpty(values[i]) || !allowed.Contains(values[i])) return false;
            return true;
        }

        private static bool Same(IList<string> a, IList<string> b)
        {
            if (a == null || b == null || a.Count != b.Count) return false;
            for (int i = 0; i < a.Count; i++)
                if (!string.Equals(a[i], b[i], StringComparison.Ordinal)) return false;
            return true;
        }

        private static string[] ToArray(HashSet<string> values)
        {
            string[] result = new string[values.Count];
            values.CopyTo(result);
            Array.Sort(result, StringComparer.Ordinal);
            return result;
        }
    }
}
