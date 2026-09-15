using System;
using System.Collections.Generic;
using System.Text;

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

        // ── 持久化：自建 JSON 读写，不依赖 Unity 的 JsonUtility ──
        //
        // 实测（1.2.0 诊断日志）：JsonUtility.ToJson 会把 SlotRecord[] slots 整段丢掉 ——
        // `rows=20 -> 0 (LOSS! slots 未落盘)`，落盘永远是 38 字节的
        // {"schema":1,"selected":0}，20 行数据从未真正保存过。
        // 因此把序列化搬进这个不依赖 Unity 的纯模型：既绕开该限制，又能离线单测。

        private static readonly string[] EmptyWords = new string[0];

        // 固定字段顺序写出；words 数组按原样写出（原生镜像行需要完整词表快照）。
        public static string Serialize(SlotState state)
        {
            if (state == null) return "{}";
            Normalize(state);
            StringBuilder sb = new StringBuilder(1 << 16);
            sb.Append("{\"schema\":").Append(state.schema)
              .Append(",\"selected\":").Append(state.selected)
              .Append(",\"slots\":[");
            for (int i = 0; i < state.slots.Length; i++)
            {
                SlotRecord row = state.slots[i];
                if (i > 0) sb.Append(',');
                sb.Append("{\"number\":").Append(row.number)
                  .Append(",\"id\":");
                AppendString(sb, row.id)
                  .Append(",\"name\":");
                AppendString(sb, row.name)
                  .Append(",\"language\":");
                AppendString(sb, row.language)
                  .Append(",\"owner\":");
                AppendString(sb, row.owner)
                  .Append(",\"managed\":").Append(row.managed ? "true" : "false")
                  .Append(",\"nativeSlot\":").Append(row.nativeSlot)
                  .Append(",\"words\":[");
                string[] words = row.words ?? EmptyWords;
                for (int w = 0; w < words.Length; w++)
                {
                    if (w > 0) sb.Append(',');
                    AppendString(sb, words[w]);
                }
                sb.Append("]}");
            }
            sb.Append("]}");
            return sb.ToString();
        }

        private static StringBuilder AppendString(StringBuilder sb, string value)
        {
            if (value == null) return sb.Append("\"\"");
            sb.Append('"');
            for (int i = 0; i < value.Length; i++)
            {
                char c = value[i];
                switch (c)
                {
                    case '"': sb.Append("\\\""); break;
                    case '\\': sb.Append("\\\\"); break;
                    case '\n': sb.Append("\\n"); break;
                    case '\r': sb.Append("\\r"); break;
                    case '\t': sb.Append("\\t"); break;
                    case '\b': sb.Append("\\b"); break;
                    case '\f': sb.Append("\\f"); break;
                    default:
                        if (c < ' ') sb.Append("\\u").Append(((int)c).ToString("x4"));
                        else sb.Append(c);
                        break;
                }
            }
            return sb.Append('"');
        }

        // 解析失败返回 null（调用方据此走新建分支，绝不静默丢数据）。
        public static SlotState Deserialize(string json)
        {
            if (json == null) return null;
            JsonScanner scanner = new JsonScanner(json);
            try
            {
                SlotState state = new SlotState();
                state.slots = new SlotRecord[0];
                scanner.SkipWhitespace();
                if (!scanner.TryReadObjectStart()) return null;
                bool any = false;
                while (true)
                {
                    scanner.SkipWhitespace();
                    if (scanner.TryReadObjectEnd()) break;
                    if (any && !scanner.TryReadComma()) return null;
                    any = true;
                    string key = scanner.ReadString();
                    if (key == null || !scanner.TryReadColon()) return null;
                    scanner.SkipWhitespace();
                    if (key == "schema") state.schema = scanner.ReadInt();
                    else if (key == "selected") state.selected = scanner.ReadInt();
                    else if (key == "slots") state.slots = ReadSlots(scanner);
                    else scanner.SkipValue();
                }
                Normalize(state);
                return state;
            }
            catch (Exception)
            {
                return null;
            }
        }

        private static SlotRecord[] ReadSlots(JsonScanner scanner)
        {
            if (!scanner.TryReadArrayStart()) throw new FormatException("slots 不是数组");
            List<SlotRecord> rows = new List<SlotRecord>();
            bool any = false;
            while (true)
            {
                scanner.SkipWhitespace();
                if (scanner.TryReadArrayEnd()) break;
                if (any && !scanner.TryReadComma()) throw new FormatException("slots 缺少逗号");
                any = true;
                scanner.SkipWhitespace();
                if (!scanner.TryReadObjectStart()) throw new FormatException("slot 行不是对象");
                SlotRecord row = new SlotRecord();
                bool first = true;
                while (true)
                {
                    scanner.SkipWhitespace();
                    if (scanner.TryReadObjectEnd()) break;
                    if (!first && !scanner.TryReadComma()) throw new FormatException("行内缺少逗号");
                    first = false;
                    string key = scanner.ReadString();
                    if (key == null || !scanner.TryReadColon()) throw new FormatException("行内键无效");
                    scanner.SkipWhitespace();
                    if (key == "number") row.number = scanner.ReadInt();
                    else if (key == "id") row.id = scanner.ReadStringOrEmpty();
                    else if (key == "name") row.name = scanner.ReadStringOrEmpty();
                    else if (key == "language") row.language = scanner.ReadStringOrEmpty();
                    else if (key == "owner") row.owner = scanner.ReadStringOrEmpty();
                    else if (key == "managed") row.managed = scanner.ReadBool();
                    else if (key == "nativeSlot") row.nativeSlot = scanner.ReadInt();
                    else if (key == "words") row.words = ReadWords(scanner);
                    else scanner.SkipValue();
                }
                rows.Add(row);
            }
            return rows.ToArray();
        }

        private static string[] ReadWords(JsonScanner scanner)
        {
            if (!scanner.TryReadArrayStart()) throw new FormatException("words 不是数组");
            List<string> words = new List<string>();
            bool any = false;
            while (true)
            {
                scanner.SkipWhitespace();
                if (scanner.TryReadArrayEnd()) break;
                if (any && !scanner.TryReadComma()) throw new FormatException("words 缺少逗号");
                any = true;
                scanner.SkipWhitespace();
                words.Add(scanner.ReadStringOrEmpty());
            }
            return words.ToArray();
        }

        // 极简 JSON 扫描器：只覆盖本文件写出的形状 + 宽松跳过未知值。
        private sealed class JsonScanner
        {
            private readonly string _s;
            private int _i;

            public JsonScanner(string s) { _s = s; _i = 0; }

            public void SkipWhitespace()
            {
                while (_i < _s.Length && char.IsWhiteSpace(_s[_i])) _i++;
            }

            private bool Take(char c)
            {
                SkipWhitespace();
                if (_i < _s.Length && _s[_i] == c) { _i++; return true; }
                return false;
            }

            public bool TryReadObjectStart() { return Take('{'); }
            public bool TryReadObjectEnd() { return Take('}'); }
            public bool TryReadArrayStart() { return Take('['); }
            public bool TryReadArrayEnd() { return Take(']'); }
            public bool TryReadComma() { return Take(','); }
            public bool TryReadColon() { return Take(':'); }

            public string ReadStringOrEmpty()
            {
                string v = ReadString();
                return v ?? "";
            }

            public string ReadString()
            {
                SkipWhitespace();
                if (!Take('"')) return null;
                StringBuilder sb = new StringBuilder();
                while (_i < _s.Length)
                {
                    char c = _s[_i++];
                    if (c == '"') return sb.ToString();
                    if (c != '\\') { sb.Append(c); continue; }
                    if (_i >= _s.Length) break;
                    char esc = _s[_i++];
                    switch (esc)
                    {
                        case '"': sb.Append('"'); break;
                        case '\\': sb.Append('\\'); break;
                        case '/': sb.Append('/'); break;
                        case 'n': sb.Append('\n'); break;
                        case 'r': sb.Append('\r'); break;
                        case 't': sb.Append('\t'); break;
                        case 'b': sb.Append('\b'); break;
                        case 'f': sb.Append('\f'); break;
                        case 'u':
                            if (_i + 4 > _s.Length) throw new FormatException("\\u 截断");
                            sb.Append((char)Convert.ToInt32(_s.Substring(_i, 4), 16));
                            _i += 4;
                            break;
                        default: throw new FormatException("未知转义 " + esc);
                    }
                }
                throw new FormatException("字符串未闭合");
            }

            public int ReadInt()
            {
                SkipWhitespace();
                int start = _i;
                if (_i < _s.Length && (_s[_i] == '-' || _s[_i] == '+')) _i++;
                while (_i < _s.Length && _s[_i] >= '0' && _s[_i] <= '9') _i++;
                if (_i == start) throw new FormatException("不是整数");
                return int.Parse(_s.Substring(start, _i - start));
            }

            public bool ReadBool()
            {
                SkipWhitespace();
                if (_i + 4 <= _s.Length && _s.Substring(_i, 4) == "true") { _i += 4; return true; }
                if (_i + 5 <= _s.Length && _s.Substring(_i, 5) == "false") { _i += 5; return false; }
                throw new FormatException("不是布尔");
            }

            // 跳过任意完整值（未知字段用，保证向后兼容）。
            public void SkipValue()
            {
                SkipWhitespace();
                if (_i >= _s.Length) return;
                char c = _s[_i];
                if (c == '{' || c == '[')
                {
                    char open = c, close = c == '{' ? '}' : ']';
                    int depth = 0;
                    while (_i < _s.Length)
                    {
                        char cur = _s[_i];
                        if (cur == '"') { ReadString(); continue; }
                        if (cur == open) depth++;
                        else if (cur == close)
                        {
                            depth--;
                            _i++;
                            if (depth == 0) return;
                            continue;
                        }
                        _i++;
                    }
                    return;
                }
                if (c == '"') { ReadString(); return; }
                while (_i < _s.Length && _s[_i] != ',' && _s[_i] != '}' && _s[_i] != ']') _i++;
            }
        }
    }
}
