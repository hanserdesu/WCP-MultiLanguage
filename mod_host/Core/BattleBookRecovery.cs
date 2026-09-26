using System;
using System.Collections.Generic;

namespace WcpHost
{
    // The game can enter a mini-game while ChosenBook_List still contains its
    // startup list. Only the saved, fingerprinted book in the selected native
    // slot may restore that list; queue contents never select a pack.
    internal static class BattleBookRecovery
    {
        internal static List<string> Resolve(BookRegistry registry, string memoryName,
            string diskName, IList<string> memoryWords, IList<string> savedWords,
            IList<string> slotWords)
        {
            if (registry == null || string.IsNullOrEmpty(memoryName) ||
                !string.Equals(memoryName, diskName, StringComparison.Ordinal) ||
                memoryWords == null || savedWords == null || slotWords == null ||
                registry.Match(memoryWords) != null) return null;

            BookProfile saved = registry.Match(savedWords);
            BookProfile slot = registry.Match(slotWords);
            if (saved == null || slot == null || saved.Id != slot.Id) return null;

            return new List<string>(savedWords);
        }
    }
}
