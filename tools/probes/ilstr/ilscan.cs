// ilscan.cs — 纯反射扫描 Assembly-CSharp.dll 的 IL，按字符串常量定位方法
// 用法: ilscan.exe <asm.dll> <mode> <needle|Type::Method> ...
//   mode=find   : 打印所有含 needle 字符串常量的方法 + 该方法内全部字符串常量
//   mode=dump   : 打印 Type::Method 的完整 IL（含 token 解析）
// 编译: 见 build.cmd（只用桌面 .NET Framework，不引用 Unity mscorlib）
using System;
using System.Collections;
using System.Collections.Generic;
using System.Reflection;
using System.Reflection.Emit;

class IlScan
{
    static Dictionary<short, OpCode> _ops;

    static void Main(string[] args)
    {
        string asmPath = args[0];
        string mode = args[1];
        Assembly asm = Assembly.LoadFrom(asmPath);
        Console.WriteLine("ASM " + asm.GetName().Name);

        if (mode == "find")
        {
            int hits = 0;
            foreach (Type t in SafeTypes(asm))
            {
                MethodBase[] ms = SafeMethods(t);
                for (int i = 0; i < ms.Length; i++)
                {
                    byte[] il = IlOf(ms[i]);
                    if (il == null) continue;
                    List<string> lits = Literals(ms[i], il);
                    bool match = false;
                    for (int j = 0; j < lits.Count && !match; j++)
                        for (int k = 2; k < args.Length; k++)
                            if (lits[j].IndexOf(args[k], StringComparison.Ordinal) >= 0) { match = true; break; }
                    if (!match) continue;
                    hits++;
                    Console.WriteLine();
                    Console.WriteLine("=== " + t.FullName + " :: " + Sig(ms[i]) + "   (il=" + il.Length + "B)");
                    for (int j = 0; j < lits.Count; j++) Console.WriteLine("    lit[" + j + "] = " + Lit(lits[j]));
                }
            }
            Console.WriteLine();
            Console.WriteLine("HITS " + hits);
            return;
        }

        if (mode == "callers")
        {
            // 列出调用了指定 Type::Method 的所有位置
            for (int k = 2; k < args.Length; k++)
            {
                string spec = args[k];
                string tn = spec.Substring(0, spec.LastIndexOf("::", StringComparison.Ordinal));
                string mn = spec.Substring(spec.LastIndexOf("::", StringComparison.Ordinal) + 2);
                Console.WriteLine();
                Console.WriteLine("=== CALLERS OF " + spec);
                int n = 0;
                foreach (Type t in SafeTypes(asm))
                {
                    MethodBase[] ms = SafeMethods(t);
                    for (int i = 0; i < ms.Length; i++)
                    {
                        byte[] il = IlOf(ms[i]);
                        if (il == null) continue;
                        List<string> calls = CallTargets(ms[i], il);
                        for (int j = 0; j < calls.Count; j++)
                        {
                            if (calls[j] != tn + "::" + mn) continue;
                            n++;
                            Console.WriteLine("    " + t.FullName + " :: " + Sig(ms[i]));
                            break;
                        }
                    }
                }
                Console.WriteLine("    count=" + n);
            }
            return;
        }

        if (mode == "dump")
        {
            for (int k = 2; k < args.Length; k++)
            {
                string spec = args[k];
                int sep = spec.LastIndexOf("::", StringComparison.Ordinal);
                string tn = spec.Substring(0, sep);
                string mn = spec.Substring(sep + 2);
                Type t = asm.GetType(tn, false);
                if (t == null) { Console.WriteLine("TYPE NOT FOUND " + tn); continue; }
                MethodBase found = null;
                MethodBase[] ms = SafeMethods(t);
                for (int i = 0; i < ms.Length; i++) if (ms[i].Name == mn) { found = ms[i]; break; }
                if (found == null) { Console.WriteLine("METHOD NOT FOUND " + spec); continue; }
                Console.WriteLine();
                Console.WriteLine("=== DUMP " + spec);
                byte[] il = IlOf(found);
                if (il == null) { Console.WriteLine("  (no body)"); continue; }
                Disasm(found, il);
            }
            return;
        }
        Console.WriteLine("unknown mode " + mode);
    }

    // ---------- IL 解析 ----------

    static byte[] IlOf(MethodBase m)
    {
        try
        {
            MethodBody b = m.GetMethodBody();
            if (b == null) return null;
            return b.GetILAsByteArray();
        }
        catch { return null; }
    }

    static void Disasm(MethodBase m, byte[] il)
    {
        Module mod = m.Module;
        int i = 0;
        while (i < il.Length)
        {
            int start = i;
            short code = il[i++];
            if (code == 0xFE) { code = (short)(0xFE00 | il[i++]); }
            OpCode op = _ops[code];
            object operand = null;
            int tok = 0;
            int n = 0;
            switch (op.OperandType)
            {
                case OperandType.InlineNone: break;
                case OperandType.ShortInlineI:
                case OperandType.ShortInlineVar: n = 1; break;
                case OperandType.ShortInlineBrTarget:
                    n = 1; operand = i + 1 + (sbyte)il[i]; break;
                case OperandType.InlineVar: n = 2; break;
                case OperandType.InlineI:
                case OperandType.InlineBrTarget: n = 4; break;
                case OperandType.InlineI8:
                case OperandType.InlineR: n = 8; break;
                case OperandType.InlineSig:
                case OperandType.InlineString:
                case OperandType.InlineTok:
                case OperandType.InlineType:
                case OperandType.InlineMethod:
                case OperandType.InlineField:
                case OperandType.InlineSwitch: n = 4; break;
                default: n = 4; break;
            }
            if (op.OperandType == OperandType.InlineString || op.OperandType == OperandType.InlineMethod ||
                op.OperandType == OperandType.InlineField || op.OperandType == OperandType.InlineType ||
                op.OperandType == OperandType.InlineTok)
                tok = BitConverter.ToInt32(il, i);
            if (n > 0) { if (op.OperandType == OperandType.InlineSwitch) { /* skip, rare */ } }
            i += n;
            if (op.OperandType != OperandType.InlineNone && operand == null)
            {
                switch (op.OperandType)
                {
                    case OperandType.ShortInlineI: operand = (sbyte)il[start + 1]; break;
                    case OperandType.ShortInlineVar: operand = il[start + 1]; break;
                    case OperandType.InlineVar: operand = BitConverter.ToInt16(il, start + 1); break;
                    case OperandType.InlineI: operand = BitConverter.ToInt32(il, start + 1); break;
                    case OperandType.InlineI8: operand = BitConverter.ToInt64(il, start + 1); break;
                    case OperandType.InlineR: operand = BitConverter.ToDouble(il, start + 1); break;
                    case OperandType.InlineString:
                        try { operand = "\"" + mod.ResolveString(tok) + "\""; }
                        catch { operand = "tok(0x" + tok.ToString("X8") + ")"; }
                        break;
                    case OperandType.InlineMethod:
                        try { operand = MemberOf(mod.ResolveMethod(tok)); } catch { operand = "mref(0x" + tok.ToString("X8") + ")"; }
                        break;
                    case OperandType.InlineField:
                        try { operand = MemberOf(mod.ResolveField(tok)); } catch { operand = "fref(0x" + tok.ToString("X8") + ")"; }
                        break;
                    case OperandType.InlineType:
                        try { operand = mod.ResolveType(tok).FullName; } catch { operand = "tref(0x" + tok.ToString("X8") + ")"; }
                        break;
                    case OperandType.InlineTok:
                        try { operand = MemberOf(mod.ResolveMember(tok)); } catch { operand = "tref2(0x" + tok.ToString("X8") + ")"; }
                        break;
                    default: operand = "?"; break;
                }
            }
            Console.WriteLine("    IL_" + start.ToString("X4") + ": " + op.Name + (operand == null ? "" : " " + operand));
        }
    }

    static string MemberOf(MemberInfo mi)
    {
        if (mi == null) return "null";
        MethodBase mb = mi as MethodBase;
        if (mb != null) return (mb.DeclaringType == null ? "?" : mb.DeclaringType.Name) + "::" + mb.Name;
        FieldInfo fi = mi as FieldInfo;
        if (fi != null) return (fi.DeclaringType == null ? "?" : fi.DeclaringType.Name) + "::" + fi.Name;
        return mi.Name;
    }

    static List<string> Literals(MethodBase m, byte[] il)
    {
        List<string> outp = new List<string>();
        int i = 0;
        while (i < il.Length)
        {
            short code = il[i++];
            if (code == 0xFE) { code = (short)(0xFE00 | il[i++]); }
            OpCode op;
            if (!_ops.TryGetValue(code, out op)) break;
            int n = OperandSize(op);
            if (op.OperandType == OperandType.InlineString && i + 4 <= il.Length)
            {
                int tok = BitConverter.ToInt32(il, i);
                try { outp.Add(m.Module.ResolveString(tok)); }
                catch { }
            }
            i += n;
        }
        return outp;
    }

    static List<string> CallTargets(MethodBase m, byte[] il)
    {
        List<string> outp = new List<string>();
        int i = 0;
        while (i < il.Length)
        {
            short code = il[i++];
            if (code == 0xFE) { code = (short)(0xFE00 | il[i++]); }
            OpCode op;
            if (!_ops.TryGetValue(code, out op)) break;
            int n = OperandSize(op);
            if ((op.OperandType == OperandType.InlineMethod || op.OperandType == OperandType.InlineTok) && i + 4 <= il.Length)
            {
                int tok = BitConverter.ToInt32(il, i);
                try
                {
                    MethodBase mb = m.Module.ResolveMethod(tok);
                    if (mb != null && mb.DeclaringType != null) outp.Add(mb.DeclaringType.FullName + "::" + mb.Name);
                }
                catch { }
            }
            i += n;
        }
        return outp;
    }

    static int OperandSize(OpCode op)
    {
        switch (op.OperandType)
        {
            case OperandType.InlineNone: return 0;
            case OperandType.ShortInlineI:
            case OperandType.ShortInlineVar:
            case OperandType.ShortInlineBrTarget: return 1;
            case OperandType.InlineVar: return 2;
            case OperandType.InlineI:
            case OperandType.InlineBrTarget:
            case OperandType.InlineSig:
            case OperandType.InlineString:
            case OperandType.InlineTok:
            case OperandType.InlineType:
            case OperandType.InlineMethod:
            case OperandType.InlineField:
            case OperandType.InlineSwitch: return 4;
            case OperandType.InlineI8:
            case OperandType.InlineR: return 8;
            default: return 4;
        }
    }

    static string Lit(string s)
    {
        s = s.Replace("\r", "\\r").Replace("\n", "\\n").Replace("\t", "\\t");
        if (s.Length > 200) s = s.Substring(0, 200) + "...";
        return s;
    }

    static string Sig(MethodBase m)
    {
        return m.Name + "(" + m.GetParameters().Length + "p)";
    }

    static Type[] SafeTypes(Assembly asm)
    {
        try { return asm.GetTypes(); }
        catch (ReflectionTypeLoadException e)
        {
            List<Type> list = new List<Type>();
            for (int i = 0; i < e.Types.Length; i++) if (e.Types[i] != null) list.Add(e.Types[i]);
            return list.ToArray();
        }
    }

    static MethodBase[] SafeMethods(Type t)
    {
        List<MethodBase> list = new List<MethodBase>();
        try
        {
            MethodInfo[] ms = t.GetMethods(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance | BindingFlags.Static | BindingFlags.DeclaredOnly);
            for (int i = 0; i < ms.Length; i++) list.Add(ms[i]);
            ConstructorInfo[] cs = t.GetConstructors(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance | BindingFlags.Static);
            for (int i = 0; i < cs.Length; i++) list.Add(cs[i]);
        }
        catch { }
        return list.ToArray();
    }

    static IlScan()
    {
        _ops = new Dictionary<short, OpCode>();
        FieldInfo[] fs = typeof(OpCodes).GetFields(BindingFlags.Public | BindingFlags.Static);
        for (int i = 0; i < fs.Length; i++)
        {
            OpCode op = (OpCode)fs[i].GetValue(null);
            short v = (short)op.Value;
            if (!_ops.ContainsKey(v)) _ops.Add(v, op);
        }
    }
}
