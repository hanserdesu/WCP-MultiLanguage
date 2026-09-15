// WCP Host Core — 极简 JSON 解析器（C#5，无外部依赖）
//
// 为什么自己写: 游戏只带 netstandard.dll + Unity，没有 Newtonsoft。
// 宿主需要读 packs/*/manifest.json，而 manifest 是固定的小 schema，
// 手写递归下降解析器比引入依赖更稳（BepInEx 插件加载期禁止未解析的程序集）。
//
// 只支持 manifest 需要的子集: object / array / string / number / bool / null。
using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text;

namespace WcpHost
{
    internal static class Json
    {
        internal static object Parse(string text)
        {
            if (text == null) throw new FormatException("JSON: 输入为 null");
            int i = 0;
            object v = Value(text, ref i);
            Ws(text, ref i);
            if (i != text.Length) throw new FormatException("JSON: 尾部多余内容 @" + i);
            return v;
        }

        internal static Dictionary<string, object> AsDict(object o)
        {
            Dictionary<string, object> d = o as Dictionary<string, object>;
            if (d == null) throw new FormatException("JSON: 期望 object");
            return d;
        }

        internal static List<object> AsList(object o)
        {
            List<object> l = o as List<object>;
            if (l == null) throw new FormatException("JSON: 期望 array");
            return l;
        }

        internal static string Str(Dictionary<string, object> d, string key, string fallback)
        {
            object v;
            if (d == null || !d.TryGetValue(key, out v) || v == null) return fallback;
            return Convert.ToString(v, CultureInfo.InvariantCulture);
        }

        internal static int Int(Dictionary<string, object> d, string key, int fallback)
        {
            object v;
            if (d == null || !d.TryGetValue(key, out v) || v == null) return fallback;
            if (v is double) return (int)(double)v;
            string s = v as string;
            if (s != null)
            {
                int n;
                if (int.TryParse(s, NumberStyles.Integer, CultureInfo.InvariantCulture, out n)) return n;
            }
            return fallback;
        }

        internal static List<string> StrList(Dictionary<string, object> d, string key)
        {
            List<string> result = new List<string>();
            object v;
            if (d == null || !d.TryGetValue(key, out v) || v == null) return result;
            List<object> l = v as List<object>;
            if (l == null) return result;
            for (int i = 0; i < l.Count; i++)
                if (l[i] != null) result.Add(Convert.ToString(l[i], CultureInfo.InvariantCulture));
            return result;
        }

        internal static Dictionary<string, object> Sub(Dictionary<string, object> d, string key)
        {
            object v;
            if (d == null || !d.TryGetValue(key, out v) || v == null) return null;
            return v as Dictionary<string, object>;
        }

        private static void Ws(string s, ref int i)
        {
            while (i < s.Length)
            {
                char c = s[i];
                if (c == ' ' || c == '\t' || c == '\n' || c == '\r') { i++; continue; }
                break;
            }
        }

        private static object Value(string s, ref int i)
        {
            Ws(s, ref i);
            if (i >= s.Length) throw new FormatException("JSON: 意外结束");
            char c = s[i];
            if (c == '{') return Obj(s, ref i);
            if (c == '[') return Arr(s, ref i);
            if (c == '"') return Str8(s, ref i);
            if (c == 't') { Lit(s, ref i, "true"); return true; }
            if (c == 'f') { Lit(s, ref i, "false"); return false; }
            if (c == 'n') { Lit(s, ref i, "null"); return null; }
            return Num(s, ref i);
        }

        private static void Lit(string s, ref int i, string lit)
        {
            if (i + lit.Length > s.Length || string.CompareOrdinal(s, i, lit, 0, lit.Length) != 0)
                throw new FormatException("JSON: 非法字面量 @" + i);
            i += lit.Length;
        }

        private static Dictionary<string, object> Obj(string s, ref int i)
        {
            Dictionary<string, object> d = new Dictionary<string, object>();
            i++;
            Ws(s, ref i);
            if (i < s.Length && s[i] == '}') { i++; return d; }
            while (true)
            {
                Ws(s, ref i);
                if (i >= s.Length || s[i] != '"') throw new FormatException("JSON: 期望键 @" + i);
                string k = Str8(s, ref i);
                Ws(s, ref i);
                if (i >= s.Length || s[i] != ':') throw new FormatException("JSON: 期望 ':' @" + i);
                i++;
                d[k] = Value(s, ref i);
                Ws(s, ref i);
                if (i < s.Length && s[i] == ',') { i++; continue; }
                if (i < s.Length && s[i] == '}') { i++; return d; }
                throw new FormatException("JSON: 期望 ',' 或 '}' @" + i);
            }
        }

        private static List<object> Arr(string s, ref int i)
        {
            List<object> l = new List<object>();
            i++;
            Ws(s, ref i);
            if (i < s.Length && s[i] == ']') { i++; return l; }
            while (true)
            {
                l.Add(Value(s, ref i));
                Ws(s, ref i);
                if (i < s.Length && s[i] == ',') { i++; continue; }
                if (i < s.Length && s[i] == ']') { i++; return l; }
                throw new FormatException("JSON: 期望 ',' 或 ']' @" + i);
            }
        }

        private static string Str8(string s, ref int i)
        {
            StringBuilder sb = new StringBuilder();
            i++;
            while (i < s.Length)
            {
                char c = s[i++];
                if (c == '"') return sb.ToString();
                if (c != '\\') { sb.Append(c); continue; }
                if (i >= s.Length) break;
                char e = s[i++];
                switch (e)
                {
                    case '"': sb.Append('"'); break;
                    case '\\': sb.Append('\\'); break;
                    case '/': sb.Append('/'); break;
                    case 'b': sb.Append('\b'); break;
                    case 'f': sb.Append('\f'); break;
                    case 'n': sb.Append('\n'); break;
                    case 'r': sb.Append('\r'); break;
                    case 't': sb.Append('\t'); break;
                    case 'u':
                        if (i + 4 > s.Length) throw new FormatException("JSON: \\u 截断");
                        sb.Append((char)Convert.ToInt32(s.Substring(i, 4), 16));
                        i += 4;
                        break;
                    default: throw new FormatException("JSON: 非法转义 \\" + e);
                }
            }
            throw new FormatException("JSON: 字符串未闭合");
        }

        private static object Num(string s, ref int i)
        {
            int start = i;
            while (i < s.Length)
            {
                char c = s[i];
                if (c == '-' || c == '+' || c == '.' || c == 'e' || c == 'E' || (c >= '0' && c <= '9')) { i++; continue; }
                break;
            }
            double d;
            if (!double.TryParse(s.Substring(start, i - start), NumberStyles.Float,
                                 CultureInfo.InvariantCulture, out d))
                throw new FormatException("JSON: 非法数字 @" + start);
            return d;
        }
    }
}
