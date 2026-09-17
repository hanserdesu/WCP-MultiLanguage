using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Text;

// 存档修复辅助（移植 ja Install-WCP-Japanese.ps1 的 WcpEs3Helper 判据/恢复逻辑，
// 与语言无关：修的是 ES3 JSON 序列化元数据，不是任何词书内容）。
// 只支持 C# 5（PS 5.1 Add-Type 限制）。
public static class WcpHubEs3Repair
{
    public static Dictionary<string, object> ParseJson(string json)
    {
        int idx = 0;
        return ParseObject(json, ref idx);
    }

    private static void SkipWhite(string s, ref int i)
    {
        while (i < s.Length && (s[i] == ' ' || s[i] == '\t' || s[i] == '\r' || s[i] == '\n')) i++;
    }

    private static object ParseValue(string s, ref int i)
    {
        SkipWhite(s, ref i);
        if (i >= s.Length) return null;
        char c = s[i];
        if (c == '{') return ParseObject(s, ref i);
        if (c == '[') return ParseArray(s, ref i);
        if (c == '"') return ParseString(s, ref i);
        if (c == 't') { i += 4; return true; }
        if (c == 'f') { i += 5; return false; }
        if (c == 'n') { i += 4; return null; }
        return ParseNumber(s, ref i);
    }

    public static Dictionary<string, object> ParseObject(string s, ref int i)
    {
        var dict = new Dictionary<string, object>(StringComparer.Ordinal);
        if (i >= s.Length || s[i] != '{') return dict;
        i++;
        while (i < s.Length)
        {
            SkipWhite(s, ref i);
            if (i >= s.Length || s[i] == '}') { if (i < s.Length) i++; break; }
            string key = ParseString(s, ref i);
            SkipWhite(s, ref i);
            if (i < s.Length && s[i] == ':') i++;
            object val = ParseValue(s, ref i);
            dict[key] = val;
            SkipWhite(s, ref i);
            if (i < s.Length && s[i] == ',') i++;
            else if (i < s.Length && s[i] == '}') { i++; break; }
        }
        return dict;
    }

    public static List<object> ParseArray(string s, ref int i)
    {
        var list = new List<object>();
        if (i >= s.Length || s[i] != '[') return list;
        i++;
        while (i < s.Length)
        {
            SkipWhite(s, ref i);
            if (i >= s.Length || s[i] == ']') { if (i < s.Length) i++; break; }
            object val = ParseValue(s, ref i);
            list.Add(val);
            SkipWhite(s, ref i);
            if (i < s.Length && s[i] == ',') i++;
            else if (i < s.Length && s[i] == ']') { i++; break; }
        }
        return list;
    }

    public static string ParseString(string s, ref int i)
    {
        SkipWhite(s, ref i);
        if (i >= s.Length || s[i] != '"') return "";
        i++;
        int start = i;
        StringBuilder sb = null;
        while (i < s.Length)
        {
            char c = s[i++];
            if (c == '"')
            {
                if (sb == null) return s.Substring(start, i - 1 - start);
                return sb.ToString();
            }
            if (c == '\\')
            {
                if (sb == null)
                {
                    sb = new StringBuilder(64);
                    sb.Append(s, start, i - 1 - start);
                }
                if (i >= s.Length) break;
                char esc = s[i++];
                if (esc == '"') sb.Append('"');
                else if (esc == '\\') sb.Append('\\');
                else if (esc == '/') sb.Append('/');
                else if (esc == 'b') sb.Append('\b');
                else if (esc == 'f') sb.Append('\f');
                else if (esc == 'n') sb.Append('\n');
                else if (esc == 'r') sb.Append('\r');
                else if (esc == 't') sb.Append('\t');
                else if (esc == 'u' && i + 4 <= s.Length)
                {
                    string hex = s.Substring(i, 4);
                    i += 4;
                    sb.Append((char)Convert.ToInt32(hex, 16));
                }
            }
            else if (sb != null)
            {
                sb.Append(c);
            }
        }
        return sb != null ? sb.ToString() : "";
    }

    private static object ParseNumber(string s, ref int i)
    {
        int start = i;
        if (i < s.Length && s[i] == '-') i++;
        while (i < s.Length && (char.IsDigit(s[i]) || s[i] == '.' || s[i] == 'e' || s[i] == 'E' || s[i] == '+' || s[i] == '-')) i++;
        string num = s.Substring(start, i - start);
        long l;
        if (long.TryParse(num, out l)) return l;
        double d;
        if (double.TryParse(num, System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out d)) return d;
        return num;
    }

    public static void Serialize(object obj, StringBuilder sb, int indent)
    {
        if (obj == null) { sb.Append("null"); return; }
        if (obj is string)
        {
            sb.Append('"');
            foreach (char c in (string)obj)
            {
                if (c == '"') sb.Append("\\\"");
                else if (c == '\\') sb.Append("\\\\");
                else if (c == '\b') sb.Append("\\b");
                else if (c == '\f') sb.Append("\\f");
                else if (c == '\n') sb.Append("\\n");
                else if (c == '\r') sb.Append("\\r");
                else if (c == '\t') sb.Append("\\t");
                else if (c < 32) sb.AppendFormat("\\u{0:x4}", (int)c);
                else sb.Append(c);
            }
            sb.Append('"');
            return;
        }
        if (obj is bool) { sb.Append((bool)obj ? "true" : "false"); return; }
        if (obj is IDictionary)
        {
            var dict = (IDictionary)obj;
            if (dict.Count == 0) { sb.Append("{}"); return; }
            sb.Append("{\r\n");
            int count = 0;
            string pad = new string('\t', indent + 1);
            foreach (DictionaryEntry kv in dict)
            {
                if (count++ > 0) sb.Append(",\r\n");
                sb.Append(pad);
                Serialize(kv.Key.ToString(), sb, indent + 1);
                sb.Append(" : ");
                Serialize(kv.Value, sb, indent + 1);
            }
            sb.Append("\r\n" + new string('\t', indent) + "}");
            return;
        }
        if (obj is IEnumerable && !(obj is string))
        {
            var list = (IEnumerable)obj;
            sb.Append("[");
            int count = 0;
            foreach (var item in list)
            {
                if (count++ > 0) sb.Append(", ");
                Serialize(item, sb, indent);
            }
            sb.Append("]");
            return;
        }
        if (obj is double || obj is float)
        {
            sb.Append(Convert.ToString(obj, System.Globalization.CultureInfo.InvariantCulture));
            return;
        }
        sb.Append(obj.ToString());
    }

    // 受损判据（与 ja 一致）：
    //   a) 根本不是合法 JSON dict（解析异常）；
    //   b) 顶层子对象的 __type 元数据丢失超过 5 条（旧版序列化器损坏）；
    //   c) 存档条目极少且开局剧情未推进（Initial_PlotDone.value <= 1，开局被重置）。
    // 不满足则返回 false（健康，绝不碰文件）。
    public static bool IsSaveCorrupted(string savePath)
    {
        if (!File.Exists(savePath)) return false;
        try
        {
            string text = File.ReadAllText(savePath, Encoding.UTF8);
            var doc = ParseJson(text);
            if (doc.Count == 0) return true;
            int typeMissing = 0;
            foreach (var kv in doc)
            {
                var child = kv.Value as Dictionary<string, object>;
                if (child != null && !child.ContainsKey("__type")) typeMissing++;
            }
            if (typeMissing > 5) return true;
            if (doc.Count < 120 && doc.ContainsKey("Initial_PlotDone"))
            {
                var child = doc["Initial_PlotDone"] as Dictionary<string, object>;
                if (child != null && child.ContainsKey("value"))
                {
                    object val = child["value"];
                    long plotVal = (val is long) ? (long)val : 0;
                    if (plotVal <= 1) return true;
                }
            }
            return false;
        }
        catch { return true; }
    }

    // 在候选里找"内容足够完整且健康"的最近备份：
    // 条目 >= 150、含 Initial_PlotDone（带 __type 和 value）、剧情推进 >= 3。
    public static string FindBestSaveBackup(string dataDir, string backupRoot)
    {
        var candidates = new List<string>();
        if (!string.IsNullOrEmpty(backupRoot) && Directory.Exists(backupRoot))
        {
            foreach (string sub in Directory.GetDirectories(backupRoot))
            {
                string f = Path.Combine(sub, "SaveFile.es3");
                if (File.Exists(f)) candidates.Add(f);
            }
        }
        foreach (string f in Directory.GetFiles(dataDir, "SaveFile_Copy*.es3"))
            candidates.Add(f);
        foreach (string f in Directory.GetFiles(dataDir, "SaveFile.es3.bak_*"))
            candidates.Add(f);

        candidates.Sort((a, b) => File.GetLastWriteTime(b).CompareTo(File.GetLastWriteTime(a)));

        foreach (string c in candidates)
        {
            try
            {
                string text = File.ReadAllText(c, Encoding.UTF8);
                var doc = ParseJson(text);
                if (doc.Count < 150) continue;
                if (!doc.ContainsKey("Initial_PlotDone")) continue;
                var child = doc["Initial_PlotDone"] as Dictionary<string, object>;
                if (child == null || !child.ContainsKey("__type") || !child.ContainsKey("value")) continue;
                long plotVal = (child["value"] is long) ? (long)child["value"] : 0;
                if (plotVal >= 3) return c;
            }
            catch { }
        }
        return null;
    }

    // SaveFile.es3 修复：先备份现场（.corrupt_before_repair.bak）再用最佳备份覆盖。
    // 找不到合格备份就不动文件（宁可保持受损也不雪上加霜）。
    public static bool TryRepairSaveFile(string savePath, string dataDir, string backupRoot, out string restoredFrom)
    {
        restoredFrom = null;
        if (!IsSaveCorrupted(savePath)) return false;
        string best = FindBestSaveBackup(dataDir, backupRoot);
        if (string.IsNullOrEmpty(best)) return false;
        try { File.Copy(savePath, savePath + ".corrupt_before_repair.bak", true); } catch { }
        File.Copy(best, savePath, true);
        restoredFrom = best;
        return true;
    }

    // MyBook.es3 修复：元数据丢失时先找健康备份覆盖；找不到再就地补 __type
    //（SelfBookList1..4 = string[]，wordDictionary1..4 = Dictionary<string,string>——
    // 这两个键的类型契约由游戏引擎固定，与语言无关）。
    public static bool TryRepairMyBook(string myBookPath, string dataDir, string backupRoot, out string restoredFrom)
    {
        restoredFrom = null;
        if (!File.Exists(myBookPath)) return false;
        try
        {
            string text = File.ReadAllText(myBookPath, Encoding.UTF8);
            var doc = ParseJson(text);
            bool needRepair = false;
            foreach (var kv in doc)
            {
                var child = kv.Value as Dictionary<string, object>;
                if (child != null && !child.ContainsKey("__type")) { needRepair = true; break; }
            }
            if (!needRepair) return false;
            if (!string.IsNullOrEmpty(backupRoot) && Directory.Exists(backupRoot))
            {
                var subs = new List<string>(Directory.GetDirectories(backupRoot));
                subs.Sort((a, b) => Directory.GetLastWriteTime(b).CompareTo(Directory.GetLastWriteTime(a)));
                foreach (string sub in subs)
                {
                    string f = Path.Combine(sub, "MyBook.es3");
                    if (File.Exists(f))
                    {
                        var bDoc = ParseJson(File.ReadAllText(f, Encoding.UTF8));
                        bool bGood = true;
                        foreach (var kv in bDoc)
                        {
                            var child = kv.Value as Dictionary<string, object>;
                            if (child != null && !child.ContainsKey("__type")) { bGood = false; break; }
                        }
                        if (bGood && bDoc.Count > 0)
                        {
                            try { File.Copy(myBookPath, myBookPath + ".corrupt_before_repair.bak", true); } catch { }
                            File.Copy(f, myBookPath, true);
                            restoredFrom = f;
                            return true;
                        }
                    }
                }
            }
            string arrType = "System.String[],mscorlib";
            string dictType = "System.Collections.Generic.Dictionary`2[[System.String, mscorlib, Version=4.0.0.0, Culture=neutral, PublicKeyToken=b77a5c561934e089],[System.String, mscorlib, Version=4.0.0.0, Culture=neutral, PublicKeyToken=b77a5c561934e089]],mscorlib";
            for (int i = 1; i <= 4; i++)
            {
                string lk = "SelfBookList" + i;
                string dk = "wordDictionary" + i;
                if (doc.ContainsKey(lk))
                {
                    var child = doc[lk] as Dictionary<string, object>;
                    if (child != null && !child.ContainsKey("__type")) child["__type"] = arrType;
                }
                if (doc.ContainsKey(dk))
                {
                    var child = doc[dk] as Dictionary<string, object>;
                    if (child != null && !child.ContainsKey("__type")) child["__type"] = dictType;
                }
            }
            var sb = new StringBuilder();
            Serialize(doc, sb, 0);
            try { File.Copy(myBookPath, myBookPath + ".corrupt_before_repair.bak", true); } catch { }
            File.WriteAllText(myBookPath, sb.ToString(), new UTF8Encoding(false));
            restoredFrom = "in-place repaired";
            return true;
        }
        catch { return false; }
    }
}
