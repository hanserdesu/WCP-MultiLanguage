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

        // ── 兼容层：原生槽位数量运行时可回填（P1-17）────────────────────────
        // 游戏作者将来把 SelfBookList1..4 扩到 5/6/... 时，宿主启动探测后回填，
        // 规则函数一律用 CurrentNativeSlots；NativeSlots 保留为历史下限
        // （探测失败/旧存档的保底值），旧测试与旧调用不受影响。
        public const int MinNativeSlots = 4;
        public const int MaxNativeSlotsProbe = 64;
        private static int _nativeSlotCount = NativeSlots;
        public static int CurrentNativeSlots { get { return _nativeSlotCount; } }

        public static void SetNativeSlotCount(int count)
        {
            if (count < MinNativeSlots) count = MinNativeSlots;
            if (count > MaxNativeSlotsProbe) count = MaxNativeSlotsProbe;
            _nativeSlotCount = count;
        }

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
            if (state == null || nativeSlot < 1 || nativeSlot > CurrentNativeSlots) return false;
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

        // ── 地址翻译层（2026-09-18 收敛）────────────────────────────────────
        //
        // 症状（实机两轮）：20 槽里选中「俄语词库」，存档确实写对了
        // （ChosenBook_Para=自定义词书二 / ChosenBook_List=俄语词表），但左侧
        // 「选择词汇书」与保存确认弹窗仍显示「日语词库(猫条版)」。
        //
        // 根因：三层各用同一个「槽位号」当标识，语义却不一致——
        //   ① 逻辑槽号：玩家在本 mod 的 20 行里的行号（index+1）；
        //   ② 物理页框：游戏原生 SelfBookList1..4 的下标；
        //   ③ 显示名：BookNameMod 按「槽号 → MyBook.es3 的 SelfBookListN」查表
        //      得到的语言名（其 SlotProfile 对槽号做 5s 缓存）。
        // 物化只改了物理页框的**内容**，槽号本身没变；BookNameMod 仍按槽号查它
        // 那张「槽号 → 语言名」的表 → 显示层永远滞后一层。这就是「物理线程与
        // 逻辑线程之间缺少映射表」的经典错位。
        //
        // 修法（对齐操作系统地址翻译）：显示名不再由槽号反查，而是由**页框内容
        // 指纹**（词表首词序列 + 词数）直接判定；展示给玩家的每一处文本都用这张
        // 映射表翻译，物理槽号从此只是「页框号」，不再当身份用。
        public static string ContentFingerprint(string[] words)
        {
            if (words == null || words.Length == 0) return "";
            // 只需稳定、可比较：词数 + 前 3 词 + 后 2 词；不做哈希以避免依赖。
            StringBuilder sb = new StringBuilder(64);
            sb.Append(words.Length).Append('|');
            int head = words.Length < 3 ? words.Length : 3;
            for (int i = 0; i < head; i++) sb.Append(words[i]).Append('\u0001');
            sb.Append('|');
            int tailStart = words.Length > 2 ? words.Length - 2 : 0;
            for (int i = tailStart; i < words.Length; i++) sb.Append(words[i]).Append('\u0001');
            return sb.ToString();
        }

        // 页框内容是否与给定快照一致（用于「这行显示什么名」的翻译判断，
        // 不看槽号，只看内容 —— 槽号会被复用、会被别处改写）。
        // 必须逐词比对：只比词数会把「词数相同的另一本书」误认成本行，
        // 进而把别人的词书当成自己物化成功（离线用例已锁住这一条）。
        public static bool ContentMatches(string[] live, SlotRecord record)
        {
            if (record == null || !HasPlayableWords(record)) return false;
            if (live == null || live.Length == 0) return false;
            return SameWords(live, record.words);
        }

        // 反查：某块页框内容属于哪个逻辑行（0 = 无主）。物理槽号不复用作身份，
        // 因此任何「这块页框现在是谁」的判断都必须走这里，而不是比较 nativeSlot。
        public static int OwnerOfContent(SlotState state, string[] liveWords)
        {
            if (state == null || liveWords == null || liveWords.Length == 0) return 0;
            Normalize(state);
            for (int i = 0; i < state.slots.Length; i++)
            {
                SlotRecord row = state.slots[i];
                if (IsManaged(row) && ContentMatches(liveWords, row)) return i + 1;
                if (IsNativeMirror(row) && ContentMatches(liveWords, row)) return i + 1;
            }
            return 0;
        }

        // 页框释放：把「某逻辑行占着这块页框」的登记撤掉（不动物化内容）。
        // 供选中换行时使用 —— 旧实现只清别的行的 nativeSlot，漏掉了
        // 「同一行先前占过的另一块页框」，会造成两块页框同时宣称归属。
        public static void ReleaseFramesExcept(SlotState state, int keepRowIndex, int keepNativeSlot)
        {
            if (state == null) return;
            Normalize(state);
            for (int i = 0; i < state.slots.Length; i++)
            {
                if (i == keepRowIndex) continue;
                SlotRecord row = state.slots[i];
                if (IsManaged(row) && row.nativeSlot == keepNativeSlot) row.nativeSlot = 0;
            }
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
                if (book == null || book.Slot < 1 || book.Slot > CurrentNativeSlots) continue;
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
            if (IsManaged(record) && record.nativeSlot >= 1 && record.nativeSlot <= CurrentNativeSlots)
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
