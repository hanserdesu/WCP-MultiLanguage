using System;
using System.Collections.Generic;

namespace WcpHost
{
    // The game can resume an S7 queue while ChosenBook_List still contains its
    // startup list. Only the saved, fingerprinted book in the selected native
    // slot may restore that list; an arbitrary quiz word never selects a pack.
    internal static class BattleBookRecovery
    {
        internal static List<string> Resolve(BookRegistry registry, string memoryName,
            string diskName, IList<string> memoryWords, IList<string> savedWords,
            IList<string> slotWords, IList<string> fightWords)
        {
            if (registry == null || string.IsNullOrEmpty(memoryName) ||
                !string.Equals(memoryName, diskName, StringComparison.Ordinal) ||
                memoryWords == null || savedWords == null || slotWords == null ||
                fightWords == null || fightWords.Count < 4 ||
                registry.Match(memoryWords) != null) return null;

            BookProfile saved = registry.Match(savedWords);
            BookProfile slot = registry.Match(slotWords);
            if (saved == null || slot == null || saved.Id != slot.Id) return null;

            HashSet<string> memorySet = BookPool.ToSet(memoryWords);
            bool foreign = false;
            for (int i = 0; i < fightWords.Count; i++)
                if (!memorySet.Contains(fightWords[i])) { foreign = true; break; }
            return foreign ? new List<string>(savedWords) : null;
        }
    }
}
