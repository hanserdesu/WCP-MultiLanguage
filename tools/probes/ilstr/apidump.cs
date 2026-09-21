// apidump.cs — dump the public API surface of named types from a managed assembly.
// usage: apidump.exe <asm.dll> <TypeName> [TypeName ...]
// Also prints whether the assembly references UnityEngine, and dumps ctor IL for
// types whose construction we must reason about.
using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using Mono.Cecil;
using Mono.Cecil.Cil;

class ApiDump
{
    static StringBuilder sb = new StringBuilder();

    static void Main(string[] args)
    {
        string asm = args[0];
        List<string> want = new List<string>();
        for (int i = 1; i < args.Length; i++) want.Add(args[i]);

        DefaultAssemblyResolver res = new DefaultAssemblyResolver();
        res.AddSearchDirectory(Path.GetDirectoryName(asm));
        res.AddSearchDirectory(@"E:\Steam\steamapps\common\WCP-WordGirlgriend\wcp_Data\Managed");
        res.AddSearchDirectory(@"E:\Steam\steamapps\common\WCP-WordGirlgriend\BepInEx\core");
        ReaderParameters rp = new ReaderParameters();
        rp.AssemblyResolver = res;
        rp.ReadingMode = ReadingMode.Immediate;

        AssemblyDefinition ad = AssemblyDefinition.ReadAssembly(asm, rp);
        sb.AppendLine("ASM " + ad.Name.Name);

        sb.AppendLine("--- referenced assemblies containing 'Unity' ---");
        foreach (AssemblyNameReference r in ad.MainModule.AssemblyReferences)
            if (r.Name.IndexOf("Unity", StringComparison.OrdinalIgnoreCase) >= 0)
                sb.AppendLine("  ref " + r.Name + " " + r.Version);

        foreach (string name in want)
        {
            TypeDefinition t = Find(ad.MainModule, name);
            sb.AppendLine();
            if (t == null)
            {
                sb.AppendLine("### NOT FOUND: " + name);
                continue;
            }
            sb.AppendLine("### " + t.FullName + "  base=" + (t.BaseType == null ? "-" : t.BaseType.FullName)
                + "  abstract=" + t.IsAbstract + " sealed=" + t.IsSealed);
            sb.AppendLine("  FIELDS:");
            foreach (FieldDefinition f in t.Fields)
                sb.AppendLine("    " + Vis(f) + (f.IsStatic ? "static " : "") + f.FieldType.FullName + " " + f.Name);
            sb.AppendLine("  PROPS:");
            foreach (PropertyDefinition p in t.Properties)
                sb.AppendLine("    " + p.PropertyType.FullName + " " + p.Name);
            sb.AppendLine("  CTORS:");
            foreach (MethodDefinition m in t.Methods)
            {
                if (!m.IsConstructor) continue;
                sb.AppendLine("    " + Vis(m) + ".ctor(" + Sig(m) + ")");
            }
            sb.AppendLine("  METHODS:");
            foreach (MethodDefinition m in t.Methods)
            {
                if (m.IsConstructor) continue;
                sb.AppendLine("    " + Vis(m) + (m.IsStatic ? "static " : "") +
                    (m.HasGenericParameters ? "GEN" + m.GenericParameters.Count + " " : "") +
                    m.ReturnType.FullName + " " + m.Name + "(" + Sig(m) + ")");
            }
        }
        Console.WriteLine(sb.ToString());
    }

    static string Vis(MethodDefinition m)
    {
        if (m.IsPublic) return "public";
        if (m.IsAssembly) return "internal";
        return "nonpublic";
    }
    static string Vis(FieldDefinition f)
    {
        if (f.IsPublic) return "public";
        if (f.IsAssembly) return "internal";
        return "nonpublic";
    }

    static string Sig(MethodDefinition m)
    {
        StringBuilder b = new StringBuilder();
        for (int i = 0; i < m.Parameters.Count; i++)
        {
            if (i > 0) b.Append(", ");
            ParameterDefinition p = m.Parameters[i];
            b.Append(p.ParameterType.FullName);
            if (p.IsOptional) b.Append(" = opt");
            b.Append(" ").Append(p.Name);
        }
        return b.ToString();
    }

    static TypeDefinition Find(ModuleDefinition mod, string name)
    {
        foreach (TypeDefinition t in AllTypes(mod))
            if (t.Name == name || t.FullName == name) return t;
        return null;
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
