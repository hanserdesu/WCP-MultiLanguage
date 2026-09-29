// WCP Host Core — 词池构造（纯逻辑，语言无关）
//
// 背景（2026-09-15 复查结论）: 游戏的战斗/复习/测试词池由 ChooseWordManager 从
// **全局单例** MyParameters.HaveLearnedDictionary 构造，再用
// AddWordsToSelfChosenList(ref list, num) 补池（补不满时塞 one..five 占位词）。
// 这个字典没有语言/词书维度: 玩家在英语书里学过的词，只要在法语书里拼写相同
// （实测法语书 1,638/8,116 = 20.2% 同形词），就会通过"本书过滤"留在池子里，
// 于是法语战斗看起来全是英语；俄语书留下的队列也会在切到日语后继续供词。
//
// 结论: 隔离不能靠事后过滤 —— 过滤只会留下"同形的那批"。必须**换来源**:
// 受管词书激活时，词池只从当前词书构造，全局已学词典不再供词。
//
// 本文件是纯逻辑: 不引用 Unity、游戏内部类型、文件系统，可独立编译与测试
// （tests\run_takeover_test.ps1 会把本文件与 TakeoverScope.cs 一起编译成 exe）。
using System;
using System.Collections.Generic;

namespace WcpHost
{
    /// <summary>
    /// 玩家学习进度的只读视图。宿主用反射从 MyParameters.HaveLearnedDictionary 取，
    /// 单元测试用手写桩。词池构造只关心"这本书里学没学过"和排序键。
    /// </summary>
    internal interface ILearnedStats
    {
        bool IsLearned(string word);
        int TestTimes(string word);
        int LastStudyTime(string word);
        int MasteryLevel(string word);
    }

    /// <summary>游戏的测试排序设置（复刻 ChooseWordManager.TestWordPos/Neg/Ran[Off] 语义）。</summary>
    internal sealed class PoolOrder
    {
        internal string Mode = "正序";
        internal bool PriorityOn;
        internal HashSet<int> AllowedLevels;
    }

    internal static class BookPool
    {
        /// <summary>游戏硬性下限: 战斗词表 >= 4，测试词池 >= 5。</summary>
        internal const int MinPlayable = 5;

        /// <summary>
        /// 只保留"属于本书"的词条（去重、保持原顺序），不补词。
        /// 用于学习进度/用户选择列表 —— 这些列表补词会伪造进度，所以只做过滤。
        /// 返回 null = 过滤不产生任何影响（调用方不需要写回）。
        /// </summary>
        internal static List<string> FilterOnly(IList<string> current, IList<string> book)
        {
            if (current == null) return null;
            if (book == null || book.Count == 0) return null;
            return FilterOnly(current, ToSet(book));
        }

        /// <summary>
        /// 同 FilterOnly(current, book)，但接受调用方已建好的本书集合。
        /// 第十四轮（2026-09-18）：Enforce 里 17 条规则原本各自重建一遍 8451 词的
        /// HashSet（稳态 25~33ms/s、切换帧的大头之一），而授权集 `allowed` 在
        /// Enforce 开头只建一次 —— 改为共享，语义不变（同一个集合）。
        /// </summary>
        internal static List<string> FilterOnly(IList<string> current, HashSet<string> bookSet)
        {
            if (current == null) return null;
            if (bookSet == null || bookSet.Count == 0) return null;
            List<string> keep = new List<string>();
            HashSet<string> seen = new HashSet<string>(StringComparer.Ordinal);
            for (int i = 0; i < current.Count; i++)
            {
                string word = Normalize(current[i]);
                if (word == null || !bookSet.Contains(word)) continue;
                if (seen.Add(word)) keep.Add(word);
            }
            return Same(current, keep) ? null : keep;
        }

        /// <summary>
        /// Emergency battle queue when the normal host rebuild fails. Keep the current
        /// book's entries in their existing order, then top up from that same book.
        /// An unavailable book produces an empty queue; never yield to the game's
        /// language-blind global dictionary or its English placeholders.
        /// </summary>
        internal static List<string> FailClosedFightPool(IList<string> current,
                                                           IList<string> book, int requested)
        {
            List<string> safe = new List<string>();
            if (book == null || book.Count == 0) return safe;

            List<string> filtered = FilterOnly(current, book);
            if (filtered != null) safe = filtered;
            else if (current != null)
                for (int i = 0; i < current.Count; i++) safe.Add(current[i]);

            int target = requested < MinPlayable ? MinPlayable : requested;
            if (safe.Count > target) target = safe.Count;
            HashSet<string> seen = ToSet(safe);
            for (int i = 0; i < book.Count && safe.Count < target; i++)
            {
                string word = Normalize(book[i]);
                if (word != null && seen.Add(word)) safe.Add(word);
            }
            return safe;
        }

        /// <summary>
        /// 从当前词书重建词池（唯一允许的补池来源）:
        ///   1. 本书已学词（本书 ∩ HaveLearnedDictionary），按玩家的排序设置排列；
        ///   2. 本书其余词，保持词书自身的学习顺序。
        /// 目标长度 = 游戏原本的规模（至少 target），凑不够就用整本书，
        /// **绝不**回退到全局词典、其它语言或 one..five 占位词。
        /// 返回 null = 没有可用的本书词表（调用方 fail-closed，保持原值不动）。
        /// </summary>
        internal static List<string> Rebuild(IList<string> book, ILearnedStats stats,
                                             PoolOrder order, bool preferLearned, int target)
        {
            if (book == null || book.Count == 0) return null;
            if (target < MinPlayable) target = MinPlayable;

            List<string> learned = new List<string>();
            List<string> unlearned = new List<string>();
            HashSet<string> seen = new HashSet<string>(StringComparer.Ordinal);
            for (int i = 0; i < book.Count; i++)
            {
                string word = Normalize(book[i]);
                if (word == null || !seen.Add(word)) continue;
                if (stats != null && stats.IsLearned(word)) learned.Add(word);
                else unlearned.Add(word);
            }
            if (learned.Count > 1) SortBySetting(learned, stats, order);

            List<string> result = new List<string>();
            if (preferLearned)
            {
                Append(result, learned, target);
                Append(result, unlearned, target);
            }
            else
            {
                Append(result, unlearned, target);
                Append(result, learned, target);
            }
            return result;
        }

        // 快速测试（已学测试）：只从当前词书且玩家已学习的词中抽样，
        // 并按掌握度过滤（level0If..level5If 映射为 1,2,3,4,5,0）。
        // 若当前词书匹配的已学词为 0，返回空列表，原生触发"题数不足"提示，
        // 绝不向已学测试注入未学词或他语同形词。
        internal static List<string> QuickTest(IList<string> book, ILearnedStats stats, PoolOrder order,
                                               int requested, Random random)
        {
            if (book == null || book.Count == 0 || stats == null || requested <= 0)
                return new List<string>();

            HashSet<string> seen = new HashSet<string>(StringComparer.Ordinal);
            List<string> candidates = new List<string>();
            HashSet<int> allowed = (order != null) ? order.AllowedLevels : null;

            for (int i = 0; i < book.Count; i++)
            {
                string word = Normalize(book[i]);
                if (word == null || !seen.Add(word)) continue;
                if (!stats.IsLearned(word)) continue;
                if (allowed != null && !allowed.Contains(stats.MasteryLevel(word))) continue;
                candidates.Add(word);
            }

            if (candidates.Count == 0) return candidates;

            if (order != null && order.Mode == "随机" && !order.PriorityOn)
            {
                if (random == null) random = new Random();
                for (int i = candidates.Count - 1; i > 0; i--)
                {
                    int j = random.Next(i + 1);
                    string swap = candidates[i];
                    candidates[i] = candidates[j];
                    candidates[j] = swap;
                }
            }
            else
            {
                SortBySetting(candidates, stats, order, random);
            }

            int need = Math.Min(requested, candidates.Count);
            if (candidates.Count == need) return candidates;
            List<string> result = new List<string>(need);
            for (int i = 0; i < need; i++) result.Add(candidates[i]);
            return result;
        }

        /// <summary>
        /// 复刻 ChooseWordManager 的排序:
        ///   随机     = 纯随机;
        ///   未测词优先 = testTimes 升序，其次 lastStudyTime（正序升 / 倒序降）;
        ///   未测词优先关: 正序 = lastStudyTime 升序，倒序 = testTimes 降序。
        /// 全局词典缺字段时按 0 处理（等价于"没测过"），不会抛。
        /// </summary>
        internal static void SortBySetting(List<string> words, ILearnedStats stats, PoolOrder order)
        {
            SortBySetting(words, stats, order, null);
        }

        internal static void SortBySetting(List<string> words, ILearnedStats stats, PoolOrder order, Random random)
        {
            if (words == null || words.Count < 2) return;
            if (stats == null) return;
            string mode = (order == null || string.IsNullOrEmpty(order.Mode)) ? "正序" : order.Mode;
            bool priority = order != null && order.PriorityOn;
            if (mode == "随机")
            {
                Random rng = random ?? new Random();
                if (!priority)
                {
                    for (int i = words.Count - 1; i > 0; i--)
                    {
                        int j = rng.Next(i + 1);
                        string swap = words[i];
                        words[i] = words[j];
                        words[j] = swap;
                    }
                    return;
                }
            }
            bool desc = mode == "倒序";
            int n = words.Count;
            string[] ws = words.ToArray();
            int[] primary = new int[n];
            int[] secondary = new int[n];
            Random ranRng = (mode == "随机" && priority) ? (random ?? new Random()) : null;
            for (int i = 0; i < n; i++)
            {
                string w = ws[i];
                if (priority)
                {
                    primary[i] = stats.TestTimes(w);
                    secondary[i] = (ranRng != null) ? ranRng.Next() : stats.LastStudyTime(w);
                }
                else if (desc) primary[i] = stats.TestTimes(w);
                else primary[i] = stats.LastStudyTime(w);
            }
            int[] idx = new int[n];
            for (int i = 0; i < n; i++) idx[i] = i;
            Array.Sort(idx, delegate(int a, int b)
            {
                int c;
                if (priority)
                {
                    c = primary[a].CompareTo(primary[b]);       // testTimes 恒升序（同旧比较器）
                    if (c != 0) return c;
                    c = secondary[a].CompareTo(secondary[b]);
                    return desc ? -c : c;                       // lastStudyTime 按 desc 翻转
                }
                c = desc ? primary[b].CompareTo(primary[a])     // testTimes 降序
                         : primary[a].CompareTo(primary[b]);    // lastStudyTime 升序
                if (c != 0) return c;
                // 同键稳定化：原 List.Sort 不稳定（同键次序由内省排序的机械细节
                // 决定），这里显式取词序 —— 对「键唯一」的输入两者输出完全一致，
                // 对平级输入这是一个确定化（门禁有平级多集等价断言守着）。
                return string.CompareOrdinal(ws[a], ws[b]);
            });
            for (int i = 0; i < n; i++) words[i] = ws[idx[i]];
        }

        /// <summary>本书词表 → 去重集合（游戏字段里可能有 null / 空串）。</summary>
        internal static HashSet<string> ToSet(IList<string> book)
        {
            HashSet<string> set = new HashSet<string>(StringComparer.Ordinal);
            if (book == null) return set;
            for (int i = 0; i < book.Count; i++)
            {
                string word = Normalize(book[i]);
                if (word != null) set.Add(word);
            }
            return set;
        }

        private static void Append(List<string> dest, List<string> source, int target)
        {
            for (int i = 0; i < source.Count && dest.Count < target; i++)
            {
                string word = source[i];
                if (word != null) dest.Add(word);
            }
        }

        private static bool Same(IList<string> a, IList<string> b)
        {
            if (a == null || b == null || a.Count != b.Count) return false;
            for (int i = 0; i < a.Count; i++)
                if (!string.Equals(a[i], b[i], StringComparison.Ordinal)) return false;
            return true;
        }

        private static string Normalize(string value)
        {
            if (string.IsNullOrEmpty(value)) return null;
            string trimmed = value.Trim();
            return trimmed.Length == 0 ? null : trimmed;
        }

        /// <summary>
        /// 单次 Enforce 内共享的词池计划（第十四轮，2026-09-18）。
        /// 背景：Enforce 的 12 条 Rebuild 规则原本**各自**跑一遍「8451 词去重分区 +
        /// 反射比较器排序」，实机切换帧 队列:规则 单次 642~706ms（两轮日志复现）。
        /// Plan 把分区/排序收敛到一次，各规则只按 target 取前缀 —— 结果与逐规则
        /// BookPool.Rebuild 完全一致（有等价性门禁守着）。随机模式在单次 Enforce 内
        /// 本就共享同一洗牌（SortBySetting 每次调用 new Random()，同秒内种子相同）；
        /// 生命周期 = 一次 Enforce，不跨轮缓存 —— 学习进度与随机洗牌照常逐轮刷新。
        /// </summary>
        internal sealed class Plan
        {
            private readonly IList<string> _book;
            private readonly ILearnedStats _stats;
            private readonly PoolOrder _order;
            private List<string> _learnedFirst;    // 已学(排序) ++ 未学(书序)
            private List<string> _unlearnedFirst;  // 未学(书序) ++ 已学(排序)
            private List<string> _learnedOnly;     // 仅已学(排序)

            internal Plan(IList<string> book, ILearnedStats stats, PoolOrder order)
            {
                _book = book;
                _stats = stats;
                _order = order;
            }

            /// <summary>与 BookPool.Rebuild(book, stats, order, preferLearned, target) 同结果。</summary>
            internal List<string> Rebuild(bool preferLearned, int target)
            {
                if (_book == null || _book.Count == 0) return null;
                if (target < MinPlayable) target = MinPlayable;
                EnsureOrdered();
                List<string> source = preferLearned ? _learnedFirst : _unlearnedFirst;
                List<string> result = new List<string>(Math.Min(target, source.Count));
                for (int i = 0; i < source.Count && result.Count < target; i++)
                    result.Add(source[i]);
                return result;
            }

            /// <summary>仅从本书已学词抽样，绝不补充未学词（不足则只保留实际已学数，0 即为空）。用于复习/测试队列。</summary>
            internal List<string> RebuildLearnedOnly(int target)
            {
                if (_book == null || _book.Count == 0) return null;
                EnsureOrdered();
                if (_learnedOnly == null || _learnedOnly.Count == 0) return new List<string>();
                int count = Math.Min(target, _learnedOnly.Count);
                List<string> result = new List<string>(count);
                for (int i = 0; i < count; i++)
                    result.Add(_learnedOnly[i]);
                return result;
            }

            private void EnsureOrdered()
            {
                if (_learnedFirst != null) return;
                List<string> learned = new List<string>();
                List<string> unlearned = new List<string>();
                HashSet<string> seen = new HashSet<string>(StringComparer.Ordinal);
                for (int i = 0; i < _book.Count; i++)
                {
                    string word = Normalize(_book[i]);
                    if (word == null || !seen.Add(word)) continue;
                    if (_stats != null && _stats.IsLearned(word)) learned.Add(word);
                    else unlearned.Add(word);
                }
                if (learned.Count > 1) SortBySetting(learned, _stats, _order);
                _learnedFirst = new List<string>(learned.Count + unlearned.Count);
                _learnedFirst.AddRange(learned);
                _learnedFirst.AddRange(unlearned);
                _unlearnedFirst = new List<string>(learned.Count + unlearned.Count);
                _unlearnedFirst.AddRange(unlearned);
                _unlearnedFirst.AddRange(learned);
                _learnedOnly = new List<string>(learned);
            }
        }
    }
}
