using System;

namespace WcpCustomSlots
{
    // This model is deliberately independent of Unity and of any language pack.
    // The game still has four native SelfBookList fields; the host exposes twenty
    // logical rows and materializes one selected row into a native free slot.
    [Serializable]
    public sealed class SlotRecord
    {
        public int number;
        public string id = "";
        public string name = "";
        public string language = "";
        public string owner = "external";
        public bool managed;
        public int nativeSlot;
        public string[] words = new string[0];
    }

    [Serializable]
    public sealed class SlotState
    {
        public int schema = 1;
        public int selected;
        public SlotRecord[] slots = new SlotRecord[0];
    }

    public static class SlotRules
    {
        public const int MaxSlots = 20;
        public const int NativeSlots = 4;
        public const int MinimumPlayableWords = 5;

        public static SlotState NewState()
        {
            SlotState state = new SlotState();
            state.slots = new SlotRecord[MaxSlots];
            for (int i = 0; i < MaxSlots; i++)
                state.slots[i] = Empty(i + 1);
            return state;
        }

        public static SlotRecord Empty(int number)
        {
            return new SlotRecord {
                number = number,
                id = "",
                name = "",
                language = "",
                owner = "external",
                managed = false,
                nativeSlot = 0,
                words = new string[0]
            };
        }

        public static bool HasPlayableWords(SlotRecord record)
        {
            return record != null && record.words != null &&
                   record.words.Length >= MinimumPlayableWords;
        }

        public static bool IsManaged(SlotRecord record)
        {
            return record != null && record.managed && HasPlayableWords(record);
        }

        public static void Normalize(SlotState state)
        {
            if (state == null) return;
            SlotRecord[] old = state.slots ?? new SlotRecord[0];
            SlotRecord[] normalized = new SlotRecord[MaxSlots];
            for (int i = 0; i < MaxSlots; i++)
            {
                SlotRecord item = i < old.Length ? old[i] : null;
                if (item == null) item = Empty(i + 1);
                item.number = i + 1;
                if (item.words == null) item.words = new string[0];
                if (item.owner == null) item.owner = item.managed ? "mod" : "external";
                normalized[i] = item;
            }
            state.schema = 1;
            if (state.selected < 0 || state.selected > MaxSlots) state.selected = 0;
            state.slots = normalized;
        }

        public static bool SameWords(string[] a, string[] b)
        {
            if (a == null || b == null || a.Length != b.Length) return false;
            for (int i = 0; i < a.Length; i++)
                if (!string.Equals(a[i], b[i], StringComparison.Ordinal)) return false;
            return true;
        }

        public static bool NativeSlotOwnedByManaged(SlotState state, int nativeSlot)
        {
            if (state == null || nativeSlot < 1 || nativeSlot > NativeSlots) return false;
            Normalize(state);
            for (int i = 0; i < state.slots.Length; i++)
            {
                SlotRecord record = state.slots[i];
                if (record.nativeSlot == nativeSlot && IsManaged(record)) return true;
            }
            return false;
        }
    }
}
