// probe2.cs -- REAL-ES3 offline A/B on a copy of the live 6 MB save.
//
//   A = today's behaviour : N x ES3.Save<T>(key, value, path)      (whole-file read+merge+write per key)
//   B = the batch we want  : ES3.CacheFile -> N x ES3.Save(...,settings) -> ES3.StoreCachedFile
//
// Assertion: sha256(A) == sha256(B).
//
// ES3 itself cannot run outside Unity because ES3Settings.get_location() calls the
// native Application.get_platform() whenever _location == 0 (== Location.File), and
// Location.File is exactly the mode we need for real file IO. So we make a PRIVATE
// Cecil-rewritten copy of Assembly-CSharp-firstpass.dll in the scratch dir and
// replace those native Application.* calls with constants. The shipped/game copy is
// never touched -- only the probe's own scratch copy.
//
// usage: probe2.exe <outTxt> <srcEs3> <workDir> <managedDir> [nKeys]
// Pure ASCII.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using Mono.Cecil;
using Mono.Cecil.Cil;

class Probe2
{
    static StringBuilder log = new StringBuilder();
    static string managed, work, patchedDir;
    static Assembly fp;
    static Type tEs3, tEs3s, tEs3f, tLoc;
    static object locCache;

    static void Main(string[] args)
    {
        string outPath = args[0];
        string src = args[1];
        work = args[2];
        managed = args[3];
        int nKeys = args.Length > 4 ? int.Parse(args[4]) : 45;

        try
        {
            int patched = Patch();
            L("patched sites total = " + patched);
            AppDomain.CurrentDomain.AssemblyResolve += Resolve;
            Run(src, nKeys);
        }
        catch (Exception e)
        {
            L("FATAL " + e.GetType().Name + ": " + Msg(e));
            L(e.StackTrace ?? "");
        }
        File.WriteAllText(outPath, log.ToString(), new UTF8Encoding(false));
    }

    // ---------- 1. private Cecil patches (scratch copies only) ----------
    static int Patch()
    {
        patchedDir = Path.Combine(work, "patched");
        Directory.CreateDirectory(patchedDir);
        int n = PatchFirstpass();
        int m = PatchCoreModule();
        L("patch sites: firstpass=" + n + " UnityEngine.CoreModule=" + m);
        return n + m;
    }

    static AssemblyDefinition ReadAsm(string path)
    {
        DefaultAssemblyResolver res = new DefaultAssemblyResolver();
        res.AddSearchDirectory(managed);
        ReaderParameters rp = new ReaderParameters();
        rp.AssemblyResolver = res;
        rp.ReadingMode = ReadingMode.Immediate;
        return AssemblyDefinition.ReadAssembly(path, rp);
    }

    static int PatchFirstpass()
    {
        AssemblyDefinition ad = ReadAsm(Path.Combine(managed, "Assembly-CSharp-firstpass.dll"));
        int n = 0;
        foreach (TypeDefinition t in AllTypes(ad.MainModule))
            foreach (MethodDefinition m in t.Methods)
            {
                if (!m.HasBody) continue;
                ILProcessor il = m.Body.GetILProcessor();
                foreach (Instruction ins in new List<Instruction>(m.Body.Instructions))
                {
                    Instruction repl = ReplFor(ins);
                    if (repl == null) continue;
                    il.Replace(ins, repl);
                    n++;
                }
            }
        ad.Write(Path.Combine(patchedDir, "Assembly-CSharp-firstpass.dll"));
        return n;
    }

    // UnityEngine.Object's type initialiser calls a native FreeFunction
    // (GetOffsetOfInstanceIDInCPlusPlusObject); anything that so much as touches the
    // type outside Unity blows up with "ECall methods must be packaged into a system
    // module". ES3 touches it (typeof(UnityEngine.Object) checks), so neutralise it.
    static int PatchCoreModule()
    {
        AssemblyDefinition ad = ReadAsm(Path.Combine(managed, "UnityEngine.CoreModule.dll"));
        int n = 0;
        foreach (TypeDefinition t in AllTypes(ad.MainModule))
            foreach (MethodDefinition m in t.Methods)
            {
                if (!m.HasBody) continue;
                ILProcessor il = m.Body.GetILProcessor();
                foreach (Instruction ins in new List<Instruction>(m.Body.Instructions))
                {
                    MethodReference mr = ins.Operand as MethodReference;
                    if (mr == null) continue;
                    if (m.Name == ".cctor" && mr.Name == "GetOffsetOfInstanceIDInCPlusPlusObject")
                    {
                        il.Replace(ins, Instruction.Create(OpCodes.Ldc_I4_0));
                        n++;
                        continue;
                    }
                    Instruction repl = ReplFor(ins);
                    if (repl == null) continue;
                    il.Replace(ins, repl);
                    n++;
                }
            }
        ad.Write(Path.Combine(patchedDir, "UnityEngine.CoreModule.dll"));
        return n;
    }

    static Instruction ReplFor(Instruction ins)
    {
        MethodReference mr = ins.Operand as MethodReference;
        if (mr == null || mr.DeclaringType == null) return null;
        if (mr.DeclaringType.FullName != "UnityEngine.Application") return null;
        if (mr.Name == "get_platform") return Instruction.Create(OpCodes.Ldc_I4_2);   // WindowsPlayer
        if (mr.Name == "get_persistentDataPath") return Instruction.Create(OpCodes.Ldstr, work);
        if (mr.Name == "get_dataPath") return Instruction.Create(OpCodes.Ldstr, work);
        if (mr.Name == "get_streamingAssetsPath") return Instruction.Create(OpCodes.Ldstr, work);
        return null;
    }

    static Assembly Resolve(object sender, ResolveEventArgs a)
    {
        string name = new AssemblyName(a.Name).Name;
        // BCL / netstandard: hand back to the CLR. The game ships a netstandard 2.1
        // facade whose System.ReadOnlySpan`1 forward cannot load on desktop .NET
        // Framework 4.x; letting the runtime pick its own netstandard 2.0 avoids that.
        if (name == "mscorlib" || name == "netstandard" || name == "System" ||
            name == "System.Core" || name.StartsWith("System.", StringComparison.Ordinal) ||
            name.StartsWith("Microsoft.", StringComparison.Ordinal))
            return null;
        string p = Path.Combine(patchedDir, name + ".dll");
        if (!File.Exists(p)) p = Path.Combine(managed, name + ".dll");
        return File.Exists(p) ? Assembly.LoadFrom(p) : null;
    }

    static void L(string s) { log.AppendLine(s); }
    static string Msg(Exception e) { Exception c = e; while (c.InnerException != null) c = c.InnerException; return c.GetType().Name + ": " + c.Message; }

    // ---------- 2. the experiment ----------
    static void Run(string srcEs3, int nKeys)
    {
        fp = Assembly.LoadFrom(Path.Combine(patchedDir, "Assembly-CSharp-firstpass.dll"));
        tEs3 = fp.GetType("ES3", true);
        tEs3s = fp.GetType("ES3Settings", true);
        tEs3f = fp.GetType("ES3File", true);
        tLoc = fp.GetType("ES3+Location", true);
        locCache = Enum.ToObject(tLoc, 4);

        object bare = Activator.CreateInstance(tEs3s, new object[] { false });
        tEs3s.GetField("_defaults", BindingFlags.NonPublic | BindingFlags.Static).SetValue(null, bare);
        object d = tEs3s.GetProperty("defaultSettings", BindingFlags.Public | BindingFlags.Static).GetValue(null, null);
        L("defaultSettings injected = " + (d == null ? "null" : "ok")
          + "  format=" + GetF(d, "format") + " compression=" + GetF(d, "compressionType")
          + " encryption=" + GetF(d, "encryptionType") + " prettyPrint=" + GetF(d, "prettyPrint")
          + " encoding=" + GetF(d, "encoding"));

        string pathA = Path.Combine(work, "A.es3");
        string pathB = Path.Combine(work, "B.es3");
        File.Copy(srcEs3, pathA, true);
        File.Copy(srcEs3, pathB, true);
        long srcLen = new FileInfo(srcEs3).Length;
        L("source = " + srcEs3 + "  (" + srcLen + " B)");
        L("keys(src) = " + CountKeys(pathA) + "   nKeys to write = " + nKeys);

        List<string> keys = new List<string>();
        List<string> vals = new List<string>();
        for (int i = 0; i < nKeys; i++)
        {
            keys.Add("wcp_backup_S8TestWordList_" + i);
            vals.Add("value-" + i + "-" + new string('x', 40));
        }

        // ---------- A: plain per-key ES3.Save ----------
        Stopwatch sw = Stopwatch.StartNew();
        long firstA = -1;
        for (int i = 0; i < keys.Count; i++)
        {
            long t0 = sw.ElapsedMilliseconds;
            SaveString(keys[i], vals[i], pathA);
            if (i == 0) firstA = sw.ElapsedMilliseconds - t0;
        }
        sw.Stop();
        long msA = sw.ElapsedMilliseconds;

        // ---------- B: cached batch ----------
        object s = Activator.CreateInstance(tEs3s, new object[] { pathB, null });
        tEs3s.GetField("path").SetValue(s, pathB);
        tEs3s.GetProperty("location").SetValue(s, locCache, null);
        L("batch settings: path=" + GetF(s, "path") + " location=" + GetP(s, "location"));
        sw = Stopwatch.StartNew();
        InvokeOne(tEs3, "CacheFile", s);
        long msCache = sw.ElapsedMilliseconds;
        sw = Stopwatch.StartNew();
        for (int i = 0; i < keys.Count; i++) SaveStringSettings(keys[i], vals[i], s);
        long msSets = sw.ElapsedMilliseconds;
        sw = Stopwatch.StartNew();
        InvokeOne(tEs3, "StoreCachedFile", s);
        long msStore = sw.ElapsedMilliseconds;

        L("");
        L("=== TIMING (real 6 MB save, " + nKeys + " keys) ===");
        L("A  " + nKeys + " x ES3.Save<T>(key,val,path)      = " + msA + " ms total, first=" + firstA
          + " ms, avg=" + (msA / (double)nKeys).ToString("F1") + " ms/key");
        L("B  CacheFile                          = " + msCache + " ms");
        L("B  " + nKeys + " x cached Save                 = " + msSets + " ms");
        L("B  StoreCachedFile                    = " + msStore + " ms");
        L("B  total                              = " + (msCache + msSets + msStore) + " ms");
        if (msA > 0) L("speedup = " + ((double)msA / Math.Max(1, msCache + msSets + msStore)).ToString("F1") + "x");

        // ---------- equivalence ----------
        L("");
        L("=== EQUIVALENCE ===");
        string shaA = Sha(pathA), shaB = Sha(pathB);
        L("A  " + new FileInfo(pathA).Length + " B  sha256=" + shaA);
        L("B  " + new FileInfo(pathB).Length + " B  sha256=" + shaB);
        bool same = shaA == shaB;
        L("BYTE-IDENTICAL = " + same);

        if (!same)
        {
            L("");
            L("--- key sets ---");
            string[] ka = (string[])Invoke(tEs3, "GetKeys", new object[] { pathA });
            string[] kb = (string[])Invoke(tEs3, "GetKeys", new object[] { pathB });
            L("keys A=" + ka.Length + " B=" + kb.Length);
            HashSet<string> sa = new HashSet<string>(ka), sb = new HashSet<string>(kb);
            int onlyA = 0, onlyB = 0;
            foreach (string k in sa) if (!sb.Contains(k)) { if (onlyA < 8) L("  onlyA " + k); onlyA++; }
            foreach (string k in sb) if (!sa.Contains(k)) { if (onlyB < 8) L("  onlyB " + k); onlyB++; }
            L("onlyA=" + onlyA + " onlyB=" + onlyB);

            L("");
            L("--- per-key raw JSON block diff (first 8 differing) ---");
            string textA = File.ReadAllText(pathA), textB = File.ReadAllText(pathB);
            int shown = 0, diffs = 0;
            foreach (string k in Union(ka, kb))
            {
                string ba = Block(textA, k), bb = Block(textB, k);
                if (ba == bb) continue;
                diffs++;
                if (shown++ < 8)
                {
                    L("  key " + k);
                    L("    A: " + Clip(ba));
                    L("    B: " + Clip(bb));
                }
            }
            L("differing key blocks = " + diffs + " (of " + Union(ka, kb).Count + ")");
        }

        // ---------- round trip via the plain path ----------
        L("");
        L("=== ROUND TRIP: plain ES3.Load<string>(key, dflt, path) ===");
        int badA = 0, badB = 0;
        for (int i = 0; i < keys.Count; i++)
        {
            if (LoadString(keys[i], "?MISSING?", pathA) != vals[i]) badA++;
            if (LoadString(keys[i], "?MISSING?", pathB) != vals[i]) badB++;
        }
        L("failures A=" + badA + " B=" + badB + " of " + keys.Count);
        L("keys after: A=" + CountKeys(pathA) + " B=" + CountKeys(pathB));

        // ---------- a pre-existing key must be untouched ----------
        L("");
        L("=== PRE-EXISTING KEY PRESERVED (ja_owned_lists) ===");
        string[] pre = LoadStringArray("ja_owned_lists", pathA);
        string[] preB = LoadStringArray("ja_owned_lists", pathB);
        L("A len=" + (pre == null ? -1 : pre.Length) + "  B len=" + (preB == null ? -1 : preB.Length));
        L("equal = " + (Join(pre) == Join(preB)));
    }

    static string Join(string[] a) { return a == null ? "<null>" : string.Join("|", a); }
    static List<string> Union(string[] a, string[] b)
    {
        List<string> r = new List<string>();
        HashSet<string> s = new HashSet<string>();
        foreach (string x in a) if (s.Add(x)) r.Add(x);
        foreach (string x in b) if (s.Add(x)) r.Add(x);
        return r;
    }
    static string Clip(string s) { if (s == null) return "<null>"; s = s.Replace("\r", "\\r").Replace("\n", "\\n").Replace("\t", "\\t"); return s.Length > 220 ? s.Substring(0, 220) + "..." : s; }

    // brace-matched block for "\t\"key\" : { ... }"
    static string Block(string text, string key)
    {
        string needle = "\"" + key + "\"";
        int at = text.IndexOf(needle, StringComparison.Ordinal);
        if (at < 0) return null;
        int i = at + needle.Length;
        while (i < text.Length && text[i] != '{' && text[i] != ',') i++;
        if (i >= text.Length || text[i] == ',') return text.Substring(at, i - at);
        int depth = 0, start = i;
        bool inStr = false;
        for (; i < text.Length; i++)
        {
            char c = text[i];
            if (inStr) { if (c == '\\') i++; else if (c == '"') inStr = false; continue; }
            if (c == '"') { inStr = true; continue; }
            if (c == '{') depth++;
            else if (c == '}') { depth--; if (depth == 0) return text.Substring(start, i - start + 1); }
        }
        return text.Substring(start);
    }

    // ---------- reflection glue ----------
    static object GetF(object o, string f) { return tEs3s.GetField(f).GetValue(o); }
    static object GetP(object o, string p) { return tEs3s.GetProperty(p).GetValue(o, null); }

    static MethodInfo FindStatic(Type t, string name, int argc, params Type[] shape)
    {
        foreach (MethodInfo m in t.GetMethods(BindingFlags.Public | BindingFlags.Static))
        {
            if (m.Name != name) continue;
            if (!m.IsGenericMethodDefinition) continue;
            ParameterInfo[] ps = m.GetParameters();
            if (ps.Length != argc) continue;
            bool ok = true;
            for (int i = 0; i < ps.Length; i++)
                if (shape[i] != null && ps[i].ParameterType != shape[i]) { ok = false; break; }
            if (ok) return m;
        }
        return null;
    }

    static object Invoke(Type t, string name, object[] a)
    {
        MethodInfo m = null;
        foreach (MethodInfo c in t.GetMethods(BindingFlags.Public | BindingFlags.Static))
            if (c.Name == name && c.GetParameters().Length == a.Length &&
                (a.Length == 0 || a[0] == null || c.GetParameters()[0].ParameterType.IsInstanceOfType(a[0])))
            { m = c; break; }
        if (m == null) throw new MissingMethodException(t.Name + "::" + name + "/" + a.Length);
        return m.Invoke(null, a);
    }

    static void InvokeOne(Type t, string name, object arg)
    {
        Invoke(t, name, new object[] { arg });
    }

    static void SaveString(string key, string val, string path)
    {
        MethodInfo m = FindStatic(tEs3, "Save", 3, typeof(string), null, typeof(string));
        if (m == null) throw new MissingMethodException("ES3.Save<T>(string,T,string)");
        m.MakeGenericMethod(typeof(string)).Invoke(null, new object[] { key, val, path });
    }

    static void SaveStringSettings(string key, string val, object settings)
    {
        MethodInfo m = FindStatic(tEs3, "Save", 3, typeof(string), null, tEs3s);
        if (m == null) throw new MissingMethodException("ES3.Save<T>(string,T,ES3Settings)");
        m.MakeGenericMethod(typeof(string)).Invoke(null, new object[] { key, val, settings });
    }

    static string LoadString(string key, string dflt, string path)
    {
        MethodInfo m = FindStatic(tEs3, "Load", 3, typeof(string), typeof(string), null);
        if (m == null) throw new MissingMethodException("ES3.Load<T>(string,string,T)");
        return (string)m.MakeGenericMethod(typeof(string)).Invoke(null, new object[] { key, dflt, path });
    }

    static string[] LoadStringArray(string key, string path)
    {
        MethodInfo m = FindStatic(tEs3, "Load", 3, typeof(string), typeof(string), null);
        if (m == null) throw new MissingMethodException("ES3.Load<T>(string,string,T)");
        return (string[])m.MakeGenericMethod(typeof(string[])).Invoke(null, new object[] { key, null, path });
    }

    static int CountKeys(string path)
    {
        try { return ((string[])Invoke(tEs3, "GetKeys", new object[] { path })).Length; }
        catch (Exception e)
        {
            L("CountKeys FAILED " + Msg(e));
            Exception c = e;
            while (c != null) { L("   cause: " + c.GetType().Name + ": " + c.Message); c = c.InnerException; }
            L(Trace(e));
            return -1;
        }
    }

    static string Trace(Exception e) { return e.StackTrace ?? ""; }

    static string Sha(string path)
    {
        using (SHA256 s = SHA256.Create())
        using (FileStream f = File.OpenRead(path))
        {
            byte[] h = s.ComputeHash(f);
            StringBuilder b = new StringBuilder();
            foreach (byte x in h) b.Append(x.ToString("x2"));
            return b.ToString();
        }
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
