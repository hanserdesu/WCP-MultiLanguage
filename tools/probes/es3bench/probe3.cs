// probe3.cs -- REAL-ES3 offline A/B on a copy of the live 6 MB save, using
// COMPILE-TIME references instead of reflection enumeration.
//
// Reflection enumeration (Type.GetMethods) forces the runtime to resolve every
// method signature of the ES3 family, which drags in BCL/unity types that cannot
// load outside Unity. Compiling against Assembly-CSharp-firstpass.dll emits exact
// MemberRefs, so only the members we actually call get resolved.
//
// The ES3 assemblies still cannot run outside Unity as-is:
//   * ES3Settings.get_location() calls the native Application.get_platform()
//     whenever _location == Location.File -- and File is the mode we need.
//   * UnityEngine.Object..cctor calls the native
//     GetOffsetOfInstanceIDInCPlusPlusObject().
// So the probe writes private Cecil-rewritten copies of Assembly-CSharp-firstpass
// and UnityEngine.CoreModule into the scratch dir and loads those. The shipped /
// installed copies are never touched.
//
//   A = today's behaviour : N x ES3.Save<string>(key, value, path)
//   B = the batch we want  : ES3.CacheFile(s) -> N x ES3.Save<string>(key,value,s) -> ES3.StoreCachedFile(s)
//
// usage: probe3.exe <outTxt> <srcEs3> <workDir> <managedDir> [nKeys]
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

class Probe3
{
    static StringBuilder log = new StringBuilder();
    static string managed, work, patchedDir;

    static void Main(string[] args)
    {
        string outPath = args[0];
        string src = args[1];
        work = args[2];
        managed = args[3];
        int nKeys = args.Length > 4 ? int.Parse(args[4]) : 45;

        try
        {
            AppDomain.CurrentDomain.AssemblyResolve += Resolve;
            AppDomain.CurrentDomain.FirstChanceException += OnFirstChance;
            int n1 = PatchAssembly("Assembly-CSharp-firstpass.dll", false);
            int n2 = PatchAssembly("UnityEngine.CoreModule.dll", true);
            L("patched sites: firstpass=" + n1 + " UnityEngine.CoreModule=" + n2);
            Run(src, nKeys);
        }
        catch (Exception e)
        {
            L("FATAL " + e.GetType().Name + ": " + Msg(e));
            Exception c = e; while (c != null) { L("   cause: " + c.GetType().Name + ": " + c.Message); c = c.InnerException; }
            L(e.StackTrace ?? "");
        }
        if (firstChance.Count > 0)
        {
            L("");
            L("=== FIRST-CHANCE EXCEPTIONS (unique, in order) ===");
            for (int i = 0; i < firstChance.Count; i++) L("  " + firstChance[i]);
        }
        File.WriteAllText(outPath, log.ToString(), new UTF8Encoding(false));
    }

    static void L(string s) { log.AppendLine(s); }
    static string Msg(Exception e) { Exception c = e; while (c.InnerException != null) c = c.InnerException; return c.GetType().Name + ": " + c.Message; }

    // Names the exact method that raised an exception -- without this, an ECall
    // failure only shows the nearest managed frame, not the offending member.
    static List<string> firstChance = new List<string>();
    static void OnFirstChance(object sender, System.Runtime.ExceptionServices.FirstChanceExceptionEventArgs a)
    {
        if (firstChance.Count > 40) return;
        Exception e = a.Exception;
        MethodBase t = e.TargetSite;
        string site = t == null ? "?" : (t.DeclaringType == null ? "?" : t.DeclaringType.FullName) + "::" + t.Name;
        string line = e.GetType().Name + "  target=" + site;
        if (!firstChance.Contains(line)) firstChance.Add(line);
    }

    // ---------- patches (scratch copies only) ----------
    //
    // Sites we neutralise, all of them native-bound outside Unity:
    //   Application.get_platform / get_persistentDataPath / get_dataPath / get_streamingAssetsPath
    //   UnityEngine.Object..cctor -> GetOffsetOfInstanceIDInCPlusPlusObject()
    //   ES3Settings.get_defaultSettingsScriptableObject() -> Resources.Load (native)
    //   UnityEngine.Debug.Log* (native sink)
    // The ES3 reader calls ES3Debug.Log for benign JSON quirks; outside Unity that
    // diagnostic path walks into Resources.Load and kills the run.
    static int PatchAssembly(string file, bool isCoreModule)
    {
        patchedDir = Path.Combine(work, "patched");
        Directory.CreateDirectory(patchedDir);
        string src = Path.Combine(managed, file);
        DefaultAssemblyResolver res = new DefaultAssemblyResolver();
        res.AddSearchDirectory(managed);
        ReaderParameters rp = new ReaderParameters();
        rp.AssemblyResolver = res;
        rp.ReadingMode = ReadingMode.Immediate;
        AssemblyDefinition ad = AssemblyDefinition.ReadAssembly(src, rp);

        int n = 0;
        foreach (TypeDefinition t in AllTypes(ad.MainModule))
        {
            bool killWholeType = isCoreModule && t.FullName == "UnityEngine.Debug";
            foreach (MethodDefinition m in t.Methods)
            {
                if (!m.HasBody) continue;

                // whole-type neutering: return default immediately
                if (killWholeType || (!isCoreModule &&
                                      (t.FullName == "ES3Internal.ES3Debug" ||
                                       (t.FullName == "ES3Internal.ES3IO" &&
                                        m.Name == "CommitBackup") ||
                                       (t.FullName == "ES3Settings" &&
                                        m.Name == "get_defaultSettingsScriptableObject"))))
                {
                    ReturnDefault(m);
                    n++;
                    continue;
                }

                ILProcessor il = m.Body.GetILProcessor();
                foreach (Instruction ins in new List<Instruction>(m.Body.Instructions))
                {
                    MethodReference mr = ins.Operand as MethodReference;
                    if (mr == null || mr.DeclaringType == null) continue;
                    if (isCoreModule && m.Name == ".cctor" &&
                        mr.Name == "GetOffsetOfInstanceIDInCPlusPlusObject")
                    {
                        il.Replace(ins, Instruction.Create(OpCodes.Ldc_I4_0));
                        n++;
                        continue;
                    }
                    if (mr.DeclaringType.FullName != "UnityEngine.Application") continue;
                    Instruction repl = null;
                    if (mr.Name == "get_platform") repl = Instruction.Create(OpCodes.Ldc_I4_2);
                    else if (mr.Name == "get_persistentDataPath") repl = Instruction.Create(OpCodes.Ldstr, work);
                    else if (mr.Name == "get_dataPath") repl = Instruction.Create(OpCodes.Ldstr, work);
                    else if (mr.Name == "get_streamingAssetsPath") repl = Instruction.Create(OpCodes.Ldstr, work);
                    if (repl == null) continue;
                    il.Replace(ins, repl);
                    n++;
                }
            }
        }
        ad.Write(Path.Combine(patchedDir, file));
        return n;
    }

    // Rewrite a method body to "return default(T);"
    static void ReturnDefault(MethodDefinition m)
    {
        m.Body = new Mono.Cecil.Cil.MethodBody(m);
        ILProcessor il = m.Body.GetILProcessor();
        TypeReference rt = m.ReturnType;
        if (rt.FullName != "System.Void")
        {
            if (rt.IsValueType)
            {
                VariableDefinition v = new VariableDefinition(rt);
                m.Body.Variables.Add(v);
                il.Append(Instruction.Create(OpCodes.Ldloca, v));
                il.Append(Instruction.Create(OpCodes.Initobj, rt));
                il.Append(Instruction.Create(OpCodes.Ldloc, v));
            }
            else il.Append(Instruction.Create(OpCodes.Ldnull));
        }
        il.Append(Instruction.Create(OpCodes.Ret));
    }

    static Assembly Resolve(object sender, ResolveEventArgs a)
    {
        string name = new AssemblyName(a.Name).Name;
        if (name == "mscorlib" || name == "System" || name == "System.Core" ||
            name.StartsWith("System.", StringComparison.Ordinal) ||
            name.StartsWith("Microsoft.", StringComparison.Ordinal))
            return null;
        string p = Path.Combine(patchedDir, name + ".dll");
        if (!File.Exists(p)) p = Path.Combine(managed, name + ".dll");
        return File.Exists(p) ? Assembly.LoadFrom(p) : null;
    }

    // ---------- the experiment ----------
    static void Run(string srcEs3, int nKeys)
    {
        // Inject ES3Settings._defaults so defaultSettings never reaches Resources.Load
        // (native). The values match what the real save file shows: JSON, no
        // compression, no encryption, pretty printed, UTF-8.
        object bare = new ES3Settings(false);
        typeof(ES3Settings).GetField("_defaults", BindingFlags.NonPublic | BindingFlags.Static)
            .SetValue(null, bare);
        ES3Settings d = ES3Settings.defaultSettings;
        L("defaultSettings injected: format=" + d.format + " compression=" + d.compressionType +
          " encryption=" + d.encryptionType + " prettyPrint=" + d.prettyPrint + " encoding=" + d.encoding);

        string pathA = Path.Combine(work, "A.es3");
        string pathB = Path.Combine(work, "B.es3");
        File.Copy(srcEs3, pathA, true);
        File.Copy(srcEs3, pathB, true);
        L("source = " + srcEs3 + "  (" + new FileInfo(srcEs3).Length + " B)");
        L("keys(src) = " + ES3.GetKeys(pathA).Length + "   nKeys to write = " + nKeys);

        List<string> keys = new List<string>();
        List<string> vals = new List<string>();
        for (int i = 0; i < nKeys; i++)
        {
            keys.Add("wcp_backup_S8TestWordList_" + i);
            vals.Add("value-" + i + "-" + new string('x', 40));
        }

        // ---- A: plain per-key ES3.Save ----
        Stopwatch sw = Stopwatch.StartNew();
        long firstA = -1;
        for (int i = 0; i < keys.Count; i++)
        {
            long t0 = sw.ElapsedMilliseconds;
            ES3.Save<string>(keys[i], vals[i], pathA);
            HandCommit(pathA);
            if (i == 0) firstA = sw.ElapsedMilliseconds - t0;
        }
        sw.Stop();
        long msA = sw.ElapsedMilliseconds;
        L("after first A save, scratch dir holds: " + Listing());

        // ---- B: cached batch ----
        ES3Settings s = new ES3Settings(pathB, (ES3Settings)null);
        s.location = ES3.Location.Cache;
        L("batch settings: path=" + s.path + " location=" + s.location);
        sw = Stopwatch.StartNew();
        ES3.CacheFile(s);
        long msCache = sw.ElapsedMilliseconds;
        sw = Stopwatch.StartNew();
        for (int i = 0; i < keys.Count; i++) ES3.Save<string>(keys[i], vals[i], s);
        long msSets = sw.ElapsedMilliseconds;
        sw = Stopwatch.StartNew();
        ES3.StoreCachedFile(s);
        long msStore = sw.ElapsedMilliseconds;
        HandCommit(pathB);

        L("");
        L("=== TIMING (real 6 MB save, " + nKeys + " keys) ===");
        L("A  " + nKeys + " x ES3.Save<string>(k,v,path)   = " + msA + " ms total, first=" + firstA +
          " ms, avg=" + (msA / (double)nKeys).ToString("F1") + " ms/key");
        L("   hand-commits=" + handCommits + " misses=" + handMisses);
        L("B  CacheFile                        = " + msCache + " ms");
        L("B  " + nKeys + " x cached Save               = " + msSets + " ms");
        L("B  StoreCachedFile                  = " + msStore + " ms");
        L("B  total                            = " + (msCache + msSets + msStore) + " ms");
        if (msA > 0) L("speedup = " + ((double)msA / Math.Max(1, msCache + msSets + msStore)).ToString("F1") + "x");

        // ---- equivalence ----
        L("");
        L("=== EQUIVALENCE ===");
        long lenA = new FileInfo(pathA).Length, lenB = new FileInfo(pathB).Length;
        string shaA = Sha(pathA), shaB = Sha(pathB);
        L("A  " + lenA + " B  sha256=" + shaA);
        L("B  " + lenB + " B  sha256=" + shaB);
        bool same = shaA == shaB;
        L("BYTE-IDENTICAL = " + same);

        if (!same)
        {
            string[] ka = ES3.GetKeys(pathA), kb = ES3.GetKeys(pathB);
            L("keys A=" + ka.Length + " B=" + kb.Length);
            HashSet<string> sa = new HashSet<string>(ka), sb = new HashSet<string>(kb);
            int onlyA = 0, onlyB = 0;
            foreach (string k in sa) if (!sb.Contains(k)) { if (onlyA < 8) L("  onlyA " + k); onlyA++; }
            foreach (string k in sb) if (!sa.Contains(k)) { if (onlyB < 8) L("  onlyB " + k); onlyB++; }
            L("onlyA=" + onlyA + " onlyB=" + onlyB);
            L("key ORDER identical = " + (string.Join("|", ka) == string.Join("|", kb)));

            // Who disturbs the file's existing key order? B keeps the original order and
            // appends; A (ES3's own Merge path) promotes the just-written key to the top.
            string[] ks = ES3.GetKeys(srcEs3);
            L("B preserves source key order as a prefix = " + IsPrefix(ks, kb));
            L("A preserves source key order as a prefix = " + IsPrefix(ks, ka));

            // where do the bytes actually diverge?
            byte[] ra = File.ReadAllBytes(pathA), rb = File.ReadAllBytes(pathB);
            int first = -1;
            for (int i = 0; i < ra.Length && i < rb.Length; i++) if (ra[i] != rb[i]) { first = i; break; }
            L("first differing byte offset = " + first + " of " + ra.Length);
            if (first >= 0) L("  A: " + Snippet(ra, first) + "     B: " + Snippet(rb, first));

            string textA = File.ReadAllText(pathA), textB = File.ReadAllText(pathB);
            string[] la = textA.Split('\n'), lb = textB.Split('\n');
            L("lines A=" + la.Length + " B=" + lb.Length);
            int shown = 0, diffs = 0;
            for (int i = 0; i < la.Length && i < lb.Length; i++)
            {
                if (la[i] == lb[i]) continue;
                diffs++;
                if (shown++ < 6) { L("  line " + (i + 1)); L("    A: " + Clip(la[i])); L("    B: " + Clip(lb[i])); }
            }
            L("differing lines = " + diffs);

            // The bytes differ only because ES3 re-orders top-level keys (its Merge
            // path writes the just-saved key first; the cached path appends). Key order
            // is not part of the storage contract -- the game reads by key, and its own
            // ES3.Save calls re-order the file anyway. So compare content per key:
            SortedDictionary<string, string> ba2 = BlocksByKey(textA);
            SortedDictionary<string, string> bb2 = BlocksByKey(textB);
            int badKeys = 0;
            List<string> badNames = new List<string>();
            foreach (KeyValuePair<string, string> kv in ba2)
            {
                string other;
                if (!bb2.TryGetValue(kv.Key, out other)) { badKeys++; badNames.Add("<missing>" + kv.Key); continue; }
                if (other != kv.Value) { badKeys++; badNames.Add(kv.Key); }
            }
            foreach (KeyValuePair<string, string> kv in bb2)
                if (!ba2.ContainsKey(kv.Key)) { badKeys++; badNames.Add("<extra>" + kv.Key); }
            L("per-key blocks: A=" + ba2.Count + " B=" + bb2.Count + " mismatching=" + badKeys);
            for (int i = 0; i < badNames.Count && i < 8; i++)
            {
                string nm = badNames[i];
                string x, y;
                ba2.TryGetValue(nm, out x); bb2.TryGetValue(nm, out y);
                L("    bad: " + nm + "  lenA=" + (x == null ? -1 : x.Length) + " lenB=" + (y == null ? -1 : y.Length));
                if (x != null && y != null)
                {
                    int dz = 0; while (dz < x.Length && dz < y.Length && x[dz] == y[dz]) dz++;
                    L("      first char diff at " + dz);
                    L("      A: " + Clip(x.Substring(Math.Max(0, dz - 30))));
                    L("      B: " + Clip(y.Substring(Math.Max(0, dz - 30))));
                }
            }
            L("CONTENT EQUIVALENT (same size, same key set, every per-key block identical) = " +
              (badKeys == 0 && lenA == lenB));

            // second run of the A path must produce the same bytes as the first run:
            // if it does not, key order is provably unstable under ES3's own Save path.
            string pathA2 = Path.Combine(work, "A2.es3");
            File.Copy(srcEs3, pathA2, true);
            for (int i = 0; i < nKeys; i++) { ES3.Save<string>(keys[i], vals[i], pathA2); HandCommit(pathA2); }
            L("order is stable across two identical A runs = " + (Sha(pathA) == Sha(pathA2)) +
              "   (A2 blocks match A = " + (BlocksByKey(File.ReadAllText(pathA2)).Count == ba2.Count) + ")");
        }

        // ---- round trip through the plain path ----
        L("");
        L("=== ROUND TRIP: ES3.Load<string>(k, dflt, path) ===");
        int badA = 0, badB = 0;
        for (int i = 0; i < keys.Count; i++)
        {
            if (ES3.Load<string>(keys[i], pathA, "?MISSING?") != vals[i]) badA++;
            if (ES3.Load<string>(keys[i], pathB, "?MISSING?") != vals[i]) badB++;
        }
        L("failures A=" + badA + " B=" + badB + " of " + keys.Count);

        // ---- a pre-existing mod key must survive ----
        L("");
        L("=== PRE-EXISTING KEY PRESERVED (ja_owned_lists) ===");
        string[] preA = ES3.Load<string[]>("ja_owned_lists", pathA, (string[])null);
        string[] preB = ES3.Load<string[]>("ja_owned_lists", pathB, (string[])null);
        L("A len=" + (preA == null ? -1 : preA.Length) + "  B len=" + (preB == null ? -1 : preB.Length) +
          "  equal=" + (Join(preA) == Join(preB)));
    }

    static string Join(string[] a) { return a == null ? "<null>" : string.Join("|", a); }

    static bool IsPrefix(string[] prefix, string[] full)
    {
        if (prefix == null || full == null || prefix.Length > full.Length) return false;
        for (int i = 0; i < prefix.Length; i++) if (prefix[i] != full[i]) return false;
        return true;
    }

    static string Snippet(byte[] b, int at)    {
        int from = Math.Max(0, at - 40), to = Math.Min(b.Length, at + 40);
        StringBuilder s = new StringBuilder();
        for (int i = from; i < to; i++) s.Append(b[i] >= 32 && b[i] < 127 ? ((char)b[i]).ToString() : "\\" + b[i]);
        return s.ToString();
    }

    // Split an ES3 JSON save into its top-level key blocks, keyed by name. String
    // literals are tracked so braces inside word lists do not confuse the depth count.
    static SortedDictionary<string, string> BlocksByKey(string text)
    {
        SortedDictionary<string, string> map = new SortedDictionary<string, string>(StringComparer.Ordinal);
        string[] lines = text.Split('\n');
        int i = 0;
        while (i < lines.Length)
        {
            string ln = lines[i].TrimEnd('\r');
            if (ln.Length > 3 && ln[0] == '\t' && ln[1] == '"')
            {
                int q = ln.IndexOf('"', 2);
                if (q > 2)
                {
                    string key = ln.Substring(2, q - 2);
                    StringBuilder sb = new StringBuilder();
                    int depth = 0;
                    bool inStr = false;
                    while (i < lines.Length)
                    {
                        string cur = lines[i].TrimEnd('\r');
                        sb.Append(cur).Append('\n');
                        for (int c = 0; c < cur.Length; c++)
                        {
                            char ch = cur[c];
                            if (inStr) { if (ch == '\\') c++; else if (ch == '"') inStr = false; continue; }
                            if (ch == '"') inStr = true;
                            else if (ch == '{') depth++;
                            else if (ch == '}') depth--;
                        }
                        i++;
                        if (depth == 0) break;
                    }
                    // The block separator (a trailing comma on every key but the last)
                    // is not content: strip it so the comparison is about content only.
                    string body = sb.ToString().TrimEnd('\n', '\r');
                    if (body.Length > 0 && body[body.Length - 1] == ',') body = body.Substring(0, body.Length - 1);
                    map[key] = body;
                    continue;
                }
            }
            i++;
        }
        return map;
    }

    // ES3Internal.ES3IO.CommitBackup is neutered (it is the one place the run aborts
    // outside Unity, for a reason that does not reproduce in-game). The probe does the
    // same work itself, with ES3's own File-location semantics, so both arms of the A/B
    // commit their bytes the same way:
    //     tmp = <path>.tmp ; tmpBak = <path>.tmp.bak
    //     if <path> exists { delete tmpBak; copy <path> -> tmpBak; delete <path>; move tmp -> <path> }
    //     else             { move tmp -> <path> }
    //     delete tmpBak
    static int handCommits, handMisses;
    static void HandCommit(string full)
    {
        string tmp = full + ".tmp";
        string tmpBak = full + ".tmp.bak";
        if (!File.Exists(tmp)) { handMisses++; return; }
        if (File.Exists(full))
        {
            if (File.Exists(tmpBak)) File.Delete(tmpBak);
            File.Copy(full, tmpBak);
            File.Delete(full);
            File.Move(tmp, full);
        }
        else File.Move(tmp, full);
        if (File.Exists(tmpBak)) File.Delete(tmpBak);
        handCommits++;
    }

    static string Listing()
    {
        StringBuilder b = new StringBuilder();
        foreach (string f in Directory.GetFiles(work))
            b.Append(Path.GetFileName(f)).Append("(").Append(new FileInfo(f).Length).Append(") ");
        return b.ToString();
    }
    static List<string> Union(string[] a, string[] b)
    {
        List<string> r = new List<string>(); HashSet<string> s = new HashSet<string>();
        foreach (string x in a) if (s.Add(x)) r.Add(x);
        foreach (string x in b) if (s.Add(x)) r.Add(x);
        return r;
    }
    static string Clip(string s) { if (s == null) return "<null>"; s = s.Replace("\r", "\\r").Replace("\n", "\\n").Replace("\t", "\\t"); return s.Length > 200 ? s.Substring(0, 200) + "..." : s; }

    static string Block(string text, string key)
    {
        string needle = "\"" + key + "\"";
        int at = text.IndexOf(needle, StringComparison.Ordinal);
        if (at < 0) return null;
        int i = at + needle.Length;
        while (i < text.Length && text[i] != '{' && text[i] != ',') i++;
        if (i >= text.Length || text[i] == ',') return text.Substring(at, i - at);
        int depth = 0, start = i; bool inStr = false;
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
