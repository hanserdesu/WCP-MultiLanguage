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

        // ── P1-1/P1-2：原生书导入、改名、移除、逐出规则（全部纯模型，可离线单测）──

        // 从游戏落盘读出的一本原生词书快照（调用方负责 ES3 读取；本模型不依赖 Unity）。
        public sealed class NativeBook
        {
            public int Slot;
            public string Name;
            public string[] Words;
        }

        // 原生镜像行：owner=external 且 id 以 native- 开头，内容跟随游戏落盘数据。
        public static bool IsNativeMirror(SlotRecord record)
        {
            return record != null && !record.managed && record.id != null &&
                   record.id.StartsWith("native-", StringComparison.Ordinal);
        }

        // P1-1：每次加载都把原生 4 槽的词书导入/刷新为外部镜像行（旧版只在“新建存档”
        // 分支导入一次，导致 store 文件一旦存在原生书就永远进不了 20 行）。
        // 规则：托管行物化占用的原生槽不导入（内容归托管行）；已有镜像按 id 原位更新；
        // 新镜像优先落在槽位号对应的行，否则落到第一个空行；20 行全满时不挤掉任何词书。
        // 返回发生变化的行数。
        public static int ImportNativeBooks(SlotState state, NativeBook[] books)
        {
            if (state == null || books == null) return 0;
            Normalize(state);
            int changed = 0;
            foreach (NativeBook book in books)
            {
                if (book == null || book.Slot < 1 || book.Slot > NativeSlots) continue;
                if (!HasPlayableWords(new SlotRecord { words = book.Words })) continue;
                if (NativeSlotOwnedByManaged(state, book.Slot)) continue;
                SlotRecord existing = FindNativeMirror(state, book.Slot);
                if (existing != null)
                {
                    string name = book.Name ?? "";
                    if (SameWords(existing.words, book.Words) &&
                        string.Equals(existing.name, name, StringComparison.Ordinal)) continue;
                    existing.name = name;
                    existing.words = (string[])book.Words.Clone();
                    changed++;
                    continue;
                }
                int target = FindImportTarget(state, book.Slot);
                if (target < 0) continue;
                SlotRecord row = state.slots[target];
                row.id = "native-" + book.Slot;
                row.name = book.Name ?? "";
                row.language = "";
                row.owner = "external";
                row.managed = false;
                row.nativeSlot = book.Slot;
                row.words = (string[])book.Words.Clone();
                changed++;
            }
            return changed;
        }

        private static SlotRecord FindNativeMirror(SlotState state, int nativeSlot)
        {
            string id = "native-" + nativeSlot;
            for (int i = 0; i < state.slots.Length; i++)
            {
                SlotRecord row = state.slots[i];
                if (IsNativeMirror(row) && string.Equals(row.id, id, StringComparison.Ordinal)) return row;
            }
            return null;
        }

        private static int FindImportTarget(SlotState state, int nativeSlot)
        {
            int preferred = nativeSlot - 1;
            if (IsFreeRow(state.slots[preferred])) return preferred;
            for (int i = 0; i < state.slots.Length; i++)
                if (IsFreeRow(state.slots[i])) return i;
            return -1;
        }

        private static bool IsFreeRow(SlotRecord row)
        {
            return !IsManaged(row) && !HasPlayableWords(row);
        }

        // P1-2：改名只动本 mod 的显示名，绝不写 SelfBookNameN（写它会切断
        // SelfBookMeaningDictionary 的精确书名匹配路径）。
        // 原生镜像行的名称跟随游戏数据，拒绝在本 mod 里改名（否则下次导入又被顶回去）。
        public static bool TryRenameSlot(SlotState state, int index, string name)
        {
            if (state == null || index < 0 || index >= MaxSlots || name == null) return false;
            string trimmed = name.Trim();
            if (trimmed.Length == 0) return false;
            Normalize(state);
            SlotRecord record = state.slots[index];
            if (IsNativeMirror(record)) return false;
            record.name = trimmed;
            return true;
        }

        // P1-2：移除一行。mod 行清空并解除映射；原生镜像行拒绝——它是游戏数据的镜像，
        // 移除后下次加载又会被导入，语义自相矛盾（原生书请在游戏原生界面删除）。
        // releaseNativeSlot > 0 表示该行是托管行且物化在某个原生槽里，调用方应把该
        // 原生槽的落盘内容清空（内容归本 mod，可以安全清）。
        public static bool TryClearSlot(SlotState state, int index, out int releaseNativeSlot)
        {
            releaseNativeSlot = 0;
            if (state == null || index < 0 || index >= MaxSlots) return false;
            Normalize(state);
            SlotRecord record = state.slots[index];
            if (IsNativeMirror(record)) return false;
            if (IsManaged(record) && record.nativeSlot >= 1 && record.nativeSlot <= NativeSlots)
                releaseNativeSlot = record.nativeSlot;
            state.slots[index] = Empty(record.number);
            if (state.selected == index + 1) state.selected = 0;
            return true;
        }

        // P1-1 逐出规则：物理槽里的词表若已被任意一行持有（镜像行快照 / 托管行自带词表），
        // 内容就是可恢复的 → 该物理槽可以被其它行接管；否则 fail-closed 拒绝覆盖。
        // 语义从“非 mod 原生书从不被覆盖”放宽为“任何原生内容都不丢失”：4 本原生书装满时
        // 托管书第一次物化不再死锁，被逐出的原生书点回原行即可恢复。
        public static bool NativeContentTracked(SlotState state, string[] liveWords)
        {
            if (state == null || liveWords == null || liveWords.Length < MinimumPlayableWords) return false;
            Normalize(state);
            for (int i = 0; i < state.slots.Length; i++)
                if (SameWords(state.slots[i].words, liveWords)) return true;
            return false;
        }
    }
}
