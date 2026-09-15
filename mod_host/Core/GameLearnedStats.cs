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

        private GameLearnedStats(IDictionary entries)
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

        public bool IsLearned(string word)
        {
            if (string.IsNullOrEmpty(word)) return false;
            try { return _entries.Contains(word); }
            catch (Exception) { return false; }
        }

        public int TestTimes(string word)
        {
            return ReadInt(word, SlotTestTimes, "testTimes");
        }

        public int LastStudyTime(string word)
        {
            return ReadInt(word, SlotLastStudy, "lastStudyTime");
        }

        private int ReadInt(string word, int slot, string fieldName)
        {
            if (string.IsNullOrEmpty(word)) return 0;
            object entry;
            try
            {
                if (!_entries.Contains(word)) return 0;
                entry = _entries[word];
            }
            catch (Exception) { return 0; }
            if (entry == null) return 0;

            FieldInfo field = Resolve(slot, fieldName, entry.GetType());
            if (field == null) return 0;
            try
            {
                object value = field.GetValue(entry);
                return value is int ? (int)value : 0;
            }
            catch (Exception) { return 0; }
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
