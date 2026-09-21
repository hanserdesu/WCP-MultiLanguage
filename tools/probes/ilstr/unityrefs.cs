// unityrefs.cs -- which UnityEngine types does the ES3 family actually reference?
// usage: unityrefs.exe <asm.dll> <TypeNamePrefix> [Prefix ...]
// Pure ASCII.
using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using Mono.Cecil;
using Mono.Cecil.Cil;

class UnityRefs
{
    static SortedDictionary<string, SortedSet<string>> byAsm =
        new SortedDictionary<string, SortedSet<string>>(StringComparer.Ordinal);

    static void Main(string[] args)
    {
        string asm = args[0];
        List<string> prefixes = new List<string>();
        for (int i = 1; i < args.Length; i++) prefixes.Add(args[i]);

        DefaultAssemblyResolver res = new DefaultAssemblyResolver();
        res.AddSearchDirectory(Path.GetDirectoryName(asm));
        res.AddSearchDirectory(@"E:\Steam\steamapps\common\WCP-WordGirlgriend\wcp_Data\Managed");
        res.AddSearchDirectory(@"E:\Steam\steamapps\common\WCP-WordGirlgriend\BepInEx\core");
        ReaderParameters rp = new ReaderParameters();
        rp.AssemblyResolver = res;
        rp.ReadingMode = ReadingMode.Immediate;

        AssemblyDefinition ad = AssemblyDefinition.ReadAssembly(asm, rp);
        int types = 0;
        foreach (TypeDefinition t in AllTypes(ad.MainModule))
        {
            bool hit = false;
            for (int i = 0; i < prefixes.Count; i++)
                if (t.FullName.StartsWith(prefixes[i], StringComparison.Ordinal)) { hit = true; break; }
            if (!hit) continue;
            types++;
            if (t.BaseType != null) Add(t.BaseType);
            foreach (FieldDefinition f in t.Fields) Add(f.FieldType);
            foreach (PropertyDefinition p in t.Properties) Add(p.PropertyType);
            foreach (MethodDefinition m in t.Methods)
            {
                Add(m.ReturnType);
                for (int i = 0; i < m.Parameters.Count; i++) Add(m.Parameters[i].ParameterType);
                if (!m.HasBody) continue;
                foreach (VariableDefinition v in m.Body.Variables) Add(v.VariableType);
                foreach (Instruction ins in m.Body.Instructions)
                {
                    if (ins.Operand is TypeReference) Add((TypeReference)ins.Operand);
                    MethodReference mr = ins.Operand as MethodReference;
                    if (mr != null)
                    {
                        Add(mr.DeclaringType);
                        Add(mr.ReturnType);
                        for (int i = 0; i < mr.Parameters.Count; i++) Add(mr.Parameters[i].ParameterType);
                    }
                    FieldReference fr = ins.Operand as FieldReference;
                    if (fr != null) { Add(fr.DeclaringType); Add(fr.FieldType); }
                }
            }
        }
        Console.WriteLine("scanning " + types + " types with prefixes [" + string.Join(",", prefixes) + "]");
        Console.WriteLine();
        foreach (KeyValuePair<string, SortedSet<string>> kv in byAsm)
        {
            Console.WriteLine("=== ASM " + kv.Key);
            foreach (string s in kv.Value) Console.WriteLine("    " + s);
        }
    }

    static void Add(TypeReference tr)
    {
        if (tr == null) return;
        string ns = tr.Namespace;
        if (string.IsNullOrEmpty(ns)) return;
        if (ns.StartsWith("UnityEngine", StringComparison.Ordinal) ||
            ns.StartsWith("Unity.", StringComparison.Ordinal))
        {
            string asm = tr.Scope == null ? "?" : tr.Scope.Name;
            SortedSet<string> set;
            if (!byAsm.TryGetValue(asm, out set)) { set = new SortedSet<string>(StringComparer.Ordinal); byAsm[asm] = set; }
            set.Add(tr.Namespace + "." + tr.Name);
        }
        GenericInstanceType git = tr as GenericInstanceType;
        if (git != null)
            foreach (TypeReference a in git.GenericArguments) Add(a);
        ArrayType at = tr as ArrayType;
        if (at != null) Add(at.ElementType);
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
