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
    }

    /// <summary>游戏的测试排序设置（复刻 ChooseWordManager.TestWordPos/Neg/Ran[Off] 语义）。</summary>
    internal sealed class PoolOrder
    {
        internal string Mode = "正序";
        internal bool PriorityOn;
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
            HashSet<string> bookSet = ToSet(book);
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

        /// <summary>
        /// 复刻 ChooseWordManager 的排序:
        ///   随机     = 纯随机;
        ///   未测词优先 = testTimes 升序，其次 lastStudyTime（正序升 / 倒序降）;
        ///   未测词优先关: 正序 = lastStudyTime 升序，倒序 = testTimes 降序。
        /// 全局词典缺字段时按 0 处理（等价于"没测过"），不会抛。
        /// </summary>
        internal static void SortBySetting(List<string> words, ILearnedStats stats, PoolOrder order)
        {
            if (words == null || words.Count < 2) return;
            if (stats == null) return;
            string mode = (order == null || string.IsNullOrEmpty(order.Mode)) ? "正序" : order.Mode;
            if (mode == "随机")
            {
                Random rng = new Random();
                for (int i = words.Count - 1; i > 0; i--)
                {
                    int j = rng.Next(i + 1);
                    string swap = words[i];
                    words[i] = words[j];
                    words[j] = swap;
                }
                return;
            }
            bool desc = mode == "倒序";
            if (order != null && order.PriorityOn)
            {
                words.Sort(delegate(string a, string b)
                {
                    int byTimes = stats.TestTimes(a).CompareTo(stats.TestTimes(b));
                    if (byTimes != 0) return byTimes;
                    int sa = stats.LastStudyTime(a);
                    int sb = stats.LastStudyTime(b);
                    return desc ? sb.CompareTo(sa) : sa.CompareTo(sb);
                });
            }
            else if (desc)
            {
                words.Sort(delegate(string a, string b)
                {
                    return stats.TestTimes(b).CompareTo(stats.TestTimes(a));
                });
            }
            else
            {
                words.Sort(delegate(string a, string b)
                {
                    return stats.LastStudyTime(a).CompareTo(stats.LastStudyTime(b));
                });
            }
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
    }
}
