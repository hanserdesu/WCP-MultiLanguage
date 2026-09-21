// ilstr.cs — 扫描 Assembly-CSharp.dll，定位含指定字符串常量的方法
// 用法: ilstr.exe <asm.dll> <needle1> [needle2 ...]
// 输出: 每个命中方法的 类型::方法 + 该方法内所有 ldstr 常量（按 IL 顺序）
using System;
using System.Collections.Generic;
using System.IO;
using Mono.Cecil;
using Mono.Cecil.Cil;

class IlStr
{
    static void Main(string[] args)
    {
        string asm = args[0];
        List<string> needles = new List<string>();
        for (int i = 1; i < args.Length; i++) needles.Add(args[i]);

        DefaultAssemblyResolver res = new DefaultAssemblyResolver();
        res.AddSearchDirectory(Path.GetDirectoryName(asm));
        res.AddSearchDirectory(@"E:\Steam\steamapps\common\WCP-WordGirlgriend\BepInEx\core");
        ReaderParameters rp = new ReaderParameters();
        rp.AssemblyResolver = res;
        rp.ReadingMode = ReadingMode.Immediate;

        AssemblyDefinition ad = AssemblyDefinition.ReadAssembly(asm, rp);
        Console.WriteLine("ASM " + ad.Name.Name + "  types=" + ad.MainModule.Types.Count);

        int hits = 0;
        foreach (TypeDefinition t in AllTypes(ad.MainModule))
        {
            foreach (MethodDefinition m in t.Methods)
            {
                if (!m.HasBody) continue;
                List<string> lits = new List<string>();
                bool match = false;
                foreach (Instruction ins in m.Body.Instructions)
                {
                    if (ins.OpCode.Code != Code.Ldstr) continue;
                    string s = ins.Operand as string;
                    if (s == null) continue;
                    lits.Add(Trim(s));
                    for (int i = 0; i < needles.Count; i++)
                        if (s.IndexOf(needles[i], StringComparison.Ordinal) >= 0) match = true;
                }
                if (!match) continue;
                hits++;
                Console.WriteLine();
                Console.WriteLine("=== " + t.FullName + " :: " + m.Name + "  (il=" + m.Body.Instructions.Count + ")");
                for (int i = 0; i < lits.Count; i++)
                    Console.WriteLine("    lit[" + i + "] = " + lits[i]);
            }
        }
        Console.WriteLine();
        Console.WriteLine("HITS " + hits);
    }

    static string Trim(string s)
    {
        s = s.Replace("\r", "\\r").Replace("\n", "\\n").Replace("\t", "\\t");
        if (s.Length > 160) s = s.Substring(0, 160) + "...";
        return s;
    }

    static IEnumerable<TypeDefinition> AllTypes(ModuleDefinition mod)
    {
        Stack<TypeDefinition> stack = new Stack<TypeDefinition>();
        foreach (TypeDefinition t in mod.Types) stack.Push(t);
        while (stack.Count > 0)
        {
            TypeDefinition t = stack.Pop();
            yield return t;
            foreach (TypeDefinition n in t.NestedTypes) stack.Push(n);
        }
    }
}
