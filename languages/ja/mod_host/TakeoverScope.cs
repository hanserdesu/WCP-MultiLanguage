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
            new FieldRule("S8HaveLearnedWordList_Para", false, false, false, 0),
            new FieldRule("S7_SelfChosenWord_List", false, false, false, 0),
            new FieldRule("S9CurrentArray_Para", true, false, false, 0),
            new FieldRule("S9extraStudy_Para", true, false, false, 0)
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
            RestoreOwned(_manifest.Profile.Es3Prefix);
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

        internal void RecoverStale(BookRegistry registry, string activeProfileId)
        {
            if (registry == null) return;
            for (int i = 0; i < registry.Manifests.Count; i++)
            {
                LanguageManifest m = registry.Manifests[i];
                if (m.Profile.Id == activeProfileId) continue;
                RestoreOwned(m.Profile.Es3Prefix);
            }
        }

        internal void Enforce()
        {
            if (!_active || _manifest == null || _bookWords == null || _bookWords.Count == 0)
                return;

            HashSet<string> allowed = BookPool.ToSet(_bookWords);
            // 词书本身不够游戏下限（坏语言包）时仍然只做过滤、不补词:
            // 过滤是隔离要求，补词是内容要求。
            bool canRebuild = allowed.Count >= BookPool.MinPlayable;

            ILearnedStats stats = StatsProvider == null ? null : StatsProvider();
            PoolOrder order = ReadOrder();
            for (int i = 0; i < Rules.Length; i++)
            {
                FieldRule rule = Rules[i];
                try
                {
                    if (rule.IsArray) EnforceArray(rule, allowed);
                    else EnforceList(rule, allowed, stats, order, canRebuild);
                }
                catch (Exception e)
                {
                    if (WarnSink != null)
                        WarnSink("WcpHost: 队列隔离失败 " + rule.Name + ": " + e.Message);
                }
            }
            AlignTestQueue(allowed);
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
            if (!CaptureList(fieldName, current)) return null;
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
        private void EnforceList(FieldRule rule, HashSet<string> allowed, ILearnedStats stats,
                                 PoolOrder order, bool canRebuild)
        {
            object raw = GameAdapter.StaticField("MyParameters", rule.Name);
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
                    next = BookPool.FilterOnly(current, _bookWords);
                    if (next == null) return;                    // 已经干净: 不动
                }
                else
                {
                    next = BookPool.Rebuild(_bookWords, stats, order, rule.PreferLearned, target);
                }
            }
            else
            {
                next = BookPool.FilterOnly(current, _bookWords);
            }
            if (next == null) return;
            if (Same(current, next)) return;
            if (!CaptureList(rule.Name, current)) return;
            object replacement = ListValueForField(raw, next);
            if (!GameAdapter.SetStaticField("MyParameters", rule.Name, replacement)) return;
            GameAdapter.Es3Save(rule.Name, replacement);
        }

        private void EnforceArray(FieldRule rule, HashSet<string> allowed)
        {
            object raw = GameAdapter.StaticField("MyParameters", rule.Name);
            string[] current = ToArray(raw);
            if (current == null || current.Length == 0) return;
            List<string> filtered = BookPool.FilterOnly(current, _bookWords);
            if (filtered == null) return;
            if (Same(current, filtered)) return;
            if (!CaptureArray(rule.Name, current)) return;
            string[] value = filtered.ToArray();
            if (!GameAdapter.SetStaticField("MyParameters", rule.Name, value)) return;
            GameAdapter.Es3Save(rule.Name, value);
        }

        // 题干队列必须和测试词池的当前进度对齐。只在游戏已经进入已学词测试
        // 或者两张表本来就有内容时修正，避免给普通词书流程凭空制造测试状态。
        private void AlignTestQueue(HashSet<string> allowed)
        {
            if (!IsLearnedTest()) return;
            object poolRaw = GameAdapter.StaticField("MyParameters", "allTestWordsS10_Para");
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

            object needRaw = GameAdapter.StaticField("MyParameters", "S8needToLearnWordList_Para");
            IList<string> current = GameAdapter.ToWordList(needRaw);
            if (current == null || current.Count == 0 || current[0] != pool[progress] ||
                !ContainsOnly(current, allowed))
            {
                List<string> old = current == null ? new List<string>() : new List<string>(current);
                if (!CaptureList("S8needToLearnWordList_Para", old)) return;
                object replacement = ListValueForField(needRaw, expected);
                if (!GameAdapter.SetStaticField("MyParameters", "S8needToLearnWordList_Para", replacement)) return;
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
            object value = GameAdapter.StaticField("MyParameters", "S7FightWordMax");
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
            if (!GameAdapter.Es3Save(Key("bak_" + fieldName), baseline)) return false;
            _ownedArrays.Add(fieldName);
            if (!GameAdapter.Es3Save(Key("owned_arrays"), ToArray(_ownedArrays)))
            {
                _ownedArrays.Remove(fieldName);
                return false;
            }
            _arrayBaselines[fieldName] = baseline;
            return true;
        }

        private void RestoreOwned(string prefix)
        {
            if (string.IsNullOrEmpty(prefix)) return;
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
            if (lists.Count == 0 && arrays.Count == 0) return;
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
                if (baseline == null) baseline = GameAdapter.Es3Load(prefix + "_bak_" + field,
                    typeof(string[]), null, null) as string[];
                if (baseline == null || !RestoreArray(field, baseline)) pendingArrays.Add(field);
            }
            if (restoredPool) MarkNoTestIfUnsafe();
            GameAdapter.Es3Save(prefix + "_owned_lists", ToArray(pendingLists));
            GameAdapter.Es3Save(prefix + "_owned_arrays", ToArray(pendingArrays));
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
            object current = GameAdapter.StaticField("MyParameters", fieldName);
            object replacement;
            if (current is string[]) replacement = value.ToArray();
            else replacement = value;
            if (!GameAdapter.SetStaticField("MyParameters", fieldName, replacement)) return false;
            return GameAdapter.Es3Save(fieldName, replacement);
        }

        private bool RestoreArray(string fieldName, string[] value)
        {
            if (!GameAdapter.SetStaticField("MyParameters", fieldName,
                (string[])value.Clone())) return false;
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
            object mode = GameAdapter.StaticField("MyParameters", "S8ThisMode_Para");
            return string.Equals(mode as string, "已学词测试", StringComparison.Ordinal);
        }

        private void MarkNoTestIfUnsafe()
        {
            IList<string> pool = GameAdapter.ToWordList(
                GameAdapter.StaticField("MyParameters", "allTestWordsS10_Para"));
            if (pool != null && pool.Count >= 5) return;
            GameAdapter.SetStaticField("MyParameters", "S8Progress_Para", 0);
            GameAdapter.Es3Save("S8Progress_Para", 0);
            GameAdapter.SetStaticField("MyParameters", "testingIf_Para", false);
            GameAdapter.Es3Save("testingIf_Para", false);
            GameAdapter.SetStaticField("MyParameters", "testingIf_CompleteIf", true);
            GameAdapter.Es3Save("testingIf_CompleteIf", true);
        }

        private int ReadInt(string fieldName, int fallback)
        {
            object value = GameAdapter.StaticField("MyParameters", fieldName);
            if (value is int) return (int)value;
            return fallback;
        }

        private PoolOrder ReadOrder()
        {
            PoolOrder order = new PoolOrder();
            object mode = GameAdapter.StaticField("MyParameters", "testNegOrPos");
            string text = mode as string;
            if (!string.IsNullOrEmpty(text)) order.Mode = text;
            object priority = GameAdapter.StaticField("MyParameters", "testPriorityOn");
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
