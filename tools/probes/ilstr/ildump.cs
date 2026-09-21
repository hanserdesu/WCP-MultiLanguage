// ildump.cs — dump the IL body of EVERY overload of the given Type::Method.
// usage: ildump.exe <asm.dll> "Type::Method" ["Type::Method" ...]
// Mono.Cecil based; desktop .NET Framework only. Pure ASCII on purpose.
using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using Mono.Cecil;
using Mono.Cecil.Cil;

class IlDump
{
    static StringBuilder sb = new StringBuilder();

    static void Main(string[] args)
    {
        string asm = args[0];
        List<string> wants = new List<string>();
        for (int i = 1; i < args.Length; i++) wants.Add(args[i]);

        DefaultAssemblyResolver res = new DefaultAssemblyResolver();
        res.AddSearchDirectory(Path.GetDirectoryName(asm));
        res.AddSearchDirectory(@"E:\Steam\steamapps\common\WCP-WordGirlgriend\wcp_Data\Managed");
        res.AddSearchDirectory(@"E:\Steam\steamapps\common\WCP-WordGirlgriend\BepInEx\core");
        ReaderParameters rp = new ReaderParameters();
        rp.AssemblyResolver = res;
        rp.ReadingMode = ReadingMode.Immediate;

        AssemblyDefinition ad = AssemblyDefinition.ReadAssembly(asm, rp);
        sb.AppendLine("ASM " + ad.Name.Name);

        foreach (string spec in wants)
        {
            int sep = spec.LastIndexOf("::", StringComparison.Ordinal);
            string tn = spec.Substring(0, sep);
            string mn = spec.Substring(sep + 2);
            TypeDefinition t = Find(ad.MainModule, tn);
            if (t == null) { sb.AppendLine("TYPE NOT FOUND " + tn); continue; }
            int n = 0;
            foreach (MethodDefinition m in t.Methods)
            {
                if (m.Name != mn) continue;
                n++;
                sb.AppendLine();
                sb.AppendLine("=== " + t.FullName + "::" + m.Name + "(" + Sig(m) + ")  generic=" + m.GenericParameters.Count);
                if (!m.HasBody) { sb.AppendLine("  (no body)"); continue; }
                Dump(m);
            }
            if (n == 0) sb.AppendLine("METHOD NOT FOUND " + spec);
        }
        Console.WriteLine(sb.ToString());
    }

    static void Dump(MethodDefinition m)
    {
        foreach (VariableDefinition v in m.Body.Variables)
            sb.AppendLine("  .local " + v.Index + " " + v.VariableType.FullName);
        foreach (Instruction ins in m.Body.Instructions)
        {
            string operand = "";
            if (ins.Operand == null) operand = "";
            else if (ins.Operand is string) operand = "\"" + ((string)ins.Operand).Replace("\r", "\\r").Replace("\n", "\\n") + "\"";
            else if (ins.Operand is FieldReference) operand = ((FieldReference)ins.Operand).FullName;
            else if (ins.Operand is MethodReference) operand = LogSig((MethodReference)ins.Operand);
            else if (ins.Operand is TypeReference) operand = ((TypeReference)ins.Operand).FullName;
            else if (ins.Operand is Instruction) operand = "IL_" + ((Instruction)ins.Operand).Offset.ToString("X4");
            else if (ins.Operand is Instruction[]) { StringBuilder b = new StringBuilder(); foreach (Instruction i2 in (Instruction[])ins.Operand) { if (b.Length > 0) b.Append(", "); b.Append("IL_" + i2.Offset.ToString("X4")); } operand = b.ToString(); }
            else operand = ins.Operand.ToString();
            string call = ins.OpCode.FlowControl == FlowControl.Call ? "" : "";
            sb.AppendLine("    IL_" + ins.Offset.ToString("X4") + ": " + ins.OpCode.Name + " " + operand + call);
        }
    }

    static string LogSig(MethodReference mr)
    {
        StringBuilder b = new StringBuilder();
        b.Append(mr.DeclaringType == null ? "?" : mr.DeclaringType.FullName).Append("::").Append(mr.Name);
        if (mr is GenericInstanceMethod)
        {
            GenericInstanceMethod g = (GenericInstanceMethod)mr;
            b.Append("<");
            for (int i = 0; i < g.GenericArguments.Count; i++) { if (i > 0) b.Append(","); b.Append(g.GenericArguments[i].Name); }
            b.Append(">");
        }
        b.Append("(");
        for (int i = 0; i < mr.Parameters.Count; i++) { if (i > 0) b.Append(", "); b.Append(mr.Parameters[i].ParameterType.Name); }
        b.Append(")");
        return b.ToString();
    }

    static string Sig(MethodDefinition m)
    {
        StringBuilder b = new StringBuilder();
        for (int i = 0; i < m.Parameters.Count; i++)
        {
            if (i > 0) b.Append(", ");
            b.Append(m.Parameters[i].ParameterType.Name).Append(" ").Append(m.Parameters[i].Name);
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
