// WCP Host Core — 学习进度适配（MyParameters.HaveLearnedDictionary → ILearnedStats）
//
// 这个字典是**全局单例、跨语言共享**的: 它没有词书/语言维度，玩家在任何词书里
// 学过的词都混在一起。所以宿主只允许把它用在"本书 ∩ 已学"的排序优先级上，
// 绝不允许当作词池来源（见 BookPool 的注释）。
//
// 字段读不到（游戏更新改名）时一律按"未学 / 0"处理: 只影响补池顺序，
// 不影响隔离本身，也不会抛异常。
using System;
using System.Collections;
using System.Collections.Generic;
using System.Reflection;

namespace WcpHost
{
    internal sealed class GameLearnedStats : ILearnedStats
    {
        private const int SlotTestTimes = 0;
        private const int SlotLastStudy = 1;

        private static readonly FieldInfo[] _fields = new FieldInfo[2];
        private static readonly bool[] _probed = new bool[2];
        private static bool _warned;

        private readonly IDictionary _entries;
        private LearnedSnapshot _snap;           // 懒建：第一次查询时整表扫一遍

        // internal：RegistryTest（InternalsVisibleTo）直接喂假字典做快照门禁。
        internal GameLearnedStats(IDictionary entries)
        {
            _entries = entries;
        }

        /// <summary>读不到字典时返回 null（调用方按"没有进度信息"处理，只影响排序）。</summary>
        internal static GameLearnedStats FromGame()
        {
            try
            {
                object raw = GameAdapter.StaticField("MyParameters", "HaveLearnedDictionary");
                IDictionary entries = raw as IDictionary;
                return entries == null ? null : new GameLearnedStats(entries);
            }
            catch (Exception)
            {
                return null;
            }
        }

        // 第十六轮（2026-09-18）：查询快照化。
        // 实机（R15 日志 23:45）进入每日学习场景的 Rebuild 走全量分区+键抽取，
        // 队列:规则 单次 804.6ms —— 根源是旧 ReadInt 每词做
        // Contains + IDictionary 索引 + 反射 GetValue，8451 词 × 3 类查询 ≈
        // 两万五千次重调用。现在每个 GameLearnedStats 实例（= 每次 Enforce，
        // StatsProvider 是工厂）只在第一次查询时把字典整表扫一遍（每条目
        // 2 次反射），之后所有查询都是纯哈希查找 —— 语义不变（快照 = Enforce
        // 开始时的进度，Enforce 内本就不该看到中途变化）。
        public bool IsLearned(string word)
        {
            if (string.IsNullOrEmpty(word)) return false;
            EnsureSnapshot();
            return _snap.IsLearned(word);
        }

        public int TestTimes(string word)
        {
            if (string.IsNullOrEmpty(word)) return 0;
            EnsureSnapshot();
            return _snap.TestTimes(word);
        }

        public int LastStudyTime(string word)
        {
            if (string.IsNullOrEmpty(word)) return 0;
            EnsureSnapshot();
            return _snap.LastStudyTime(word);
        }

        private void EnsureSnapshot()
        {
            if (_snap != null) return;
            HashSet<string> learned = new HashSet<string>(StringComparer.Ordinal);
            Dictionary<string, int> times = new Dictionary<string, int>(StringComparer.Ordinal);
            Dictionary<string, int> last = new Dictionary<string, int>(StringComparer.Ordinal);
            int scanned = 0;
            try
            {
                foreach (DictionaryEntry de in _entries)
                {
                    string word = de.Key as string;
                    object entry = de.Value;
                    if (word == null || entry == null) continue;
                    learned.Add(word);
                    times[word] = ReadEntryInt(entry, SlotTestTimes, "testTimes");
                    last[word] = ReadEntryInt(entry, SlotLastStudy, "lastStudyTime");
                    scanned++;
                }
            }
            catch (Exception e)
            {
                // 快照扫了一半：保留已扫到的部分，但把原因记下来（测试可断言）。
                LastBuildError = e.GetType().Name + ": " + e.Message + " @scanned=" + scanned;
            }
            if (LastBuildError == null && scanned == 0 && learned.Count == 0 && _entries.Count > 0)
                LastBuildError = "枚举 0 条（entries=" + _entries.Count + "）";
            _snap = new LearnedSnapshot(learned, times, last);
            ScannedCount = scanned;
        }

        // 诊断（第十六轮）：非 null = 上次建快照中途出错；测试与实机日志可读。
        internal static string LastBuildError;
        internal static int ScannedCount = -1;

        private static int ReadEntryInt(object entry, int slot, string fieldName)
        {
            FieldInfo field = Resolve(slot, fieldName, entry.GetType());
            if (field == null) return 0;
            try
            {
                object value = field.GetValue(entry);
                return value is int ? (int)value : 0;
            }
            catch (Exception) { return 0; }
        }

        private sealed class LearnedSnapshot : ILearnedStats
        {
            private readonly HashSet<string> _learned;
            private readonly Dictionary<string, int> _times;
            private readonly Dictionary<string, int> _last;

            internal LearnedSnapshot(HashSet<string> learned,
                Dictionary<string, int> times, Dictionary<string, int> last)
            {
                _learned = learned;
                _times = times;
                _last = last;
            }

            public bool IsLearned(string word)
            {
                return word != null && _learned.Contains(word);
            }

            public int TestTimes(string word)
            {
                int value;
                return word != null && _times.TryGetValue(word, out value) ? value : 0;
            }

            public int LastStudyTime(string word)
            {
                int value;
                return word != null && _last.TryGetValue(word, out value) ? value : 0;
            }
        }

        private static FieldInfo Resolve(int slot, string fieldName, Type entryType)
        {
            if (_probed[slot]) return _fields[slot];
            _probed[slot] = true;
            try
            {
                FieldInfo field = entryType.GetField(fieldName,
                    BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
                if (field != null && field.FieldType == typeof(int))
                {
                    _fields[slot] = field;
                    return field;
                }
            }
            catch (Exception) { }
            if (!_warned)
            {
                _warned = true;
                if (WcpHostPlugin.Log != null)
                    WcpHostPlugin.Log.LogWarning("WcpHost: 学习进度字段不可用（" + fieldName +
                        "），词池补词顺序退化为本书顺序；隔离不受影响");
            }
            return null;
        }
    }
}
