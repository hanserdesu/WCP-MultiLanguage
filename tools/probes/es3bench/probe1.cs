// probe1.cs -- real-ES3 offline A/B:
//   path A: today's behaviour (N x ES3.Save to the default "File" location)
//   path B: ES3's sanctioned batch (CacheFile -> N x cached Save -> StoreCachedFile)
// Assertion: the two files must be BYTE-IDENTICAL. If they are not, the batch is
// not equivalent and must not ship.
// Pure ASCII. Results are written to argv[1].
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;

class Probe1
{
    static StringBuilder log = new StringBuilder();
    static string managed = @"E:\Steam\steamapps\common\WCP-WordGirlgriend\wcp_Data\Managed";
    static Assembly fp;
    static Type tEs3, tEs3s, tEs3f, tLoc;
    static object locCache;

    static void Main(string[] args)
    {
        string outPath = args[0];
        string srcEs3 = args[1];
        string work = args[2];
        AppDomain.CurrentDomain.AssemblyResolve += Resolve;
        try { Run(srcEs3, work); }
        catch (Exception e) { L("FATAL " + e.GetType().Name + ": " + Msg(e)); L(e.StackTrace ?? ""); }
        File.WriteAllText(outPath, log.ToString(), new UTF8Encoding(false));
    }

    static Assembly Resolve(object sender, ResolveEventArgs a)
    {
        string name = new AssemblyName(a.Name).Name;
        string p = Path.Combine(managed, name + ".dll");
        return File.Exists(p) ? Assembly.LoadFrom(p) : null;
    }
    static void L(string s) { log.AppendLine(s); }
    static string Msg(Exception e) { Exception c = e; while (c.InnerException != null) c = c.InnerException; return c.GetType().Name + ": " + c.Message; }

    static void Run(string srcEs3, string work)
    {
        fp = Assembly.LoadFrom(Path.Combine(managed, "Assembly-CSharp-firstpass.dll"));
        tEs3 = fp.GetType("ES3", true);
        tEs3s = fp.GetType("ES3Settings", true);
        tEs3f = fp.GetType("ES3File", true);
        tLoc = fp.GetType("ES3+Location", true);
        locCache = Enum.ToObject(tLoc, 4);
        L("Location.Cache = " + locCache + " (" + Convert.ToInt32(locCache) + ")");

        // Inject ES3Settings._defaults so defaultSettings never touches UnityEngine.Object.
        object bare = Activator.CreateInstance(tEs3s, new object[] { false });
        FieldInfo priv = tEs3s.GetField("_defaults", BindingFlags.NonPublic | BindingFlags.Static);
        priv.SetValue(null, bare);
        object d = tEs3s.GetProperty("defaultSettings", BindingFlags.Public | BindingFlags.Static)
                        .GetValue(null, null);
        L("defaultSettings after inject = " + (d == null ? "null" : "ok"));
        L("  defaults.path=" + GetF(d, "path") + " location=" + GetP(d, "location")
          + " compression=" + GetF(d, "compressionType") + " encryption=" + GetF(d, "encryptionType")
          + " format=" + GetF(d, "format"));

        Directory.CreateDirectory(work);
        string pathA = Path.Combine(work, "A.es3");
        string pathB = Path.Combine(work, "B.es3");
        File.Copy(srcEs3, pathA, true);
        File.Copy(srcEs3, pathB, true);
        L("src=" + srcEs3 + " (" + new FileInfo(srcEs3).Length + " B)");

        // Same payload for both paths: 45 keys, fresh ones so we exercise adds.
        List<string> keys = new List<string>();
        List<string> vals = new List<string>();
        for (int i = 0; i < 45; i++)
        {
            keys.Add("wcp_probe_" + i);
            vals.Add("value-" + i + "-" + new string('x', 40));
        }

        int keysBeforeA = CountKeys(pathA);
        L("keys(A) before = " + keysBeforeA);

        // ---- path A: one whole-file read+write per key (today's Es3Save) ----
        Stopwatch sw = Stopwatch.StartNew();
        for (int i = 0; i < keys.Count; i++)
            SaveString(keys[i], vals[i], pathA);
        sw.Stop();
        long msA = sw.ElapsedMilliseconds;

        // ---- path B: cached file, single flush ----
        sw = Stopwatch.StartNew();
        object s = ((object)Activator.CreateInstance(tEs3s,
            new object[] { pathB, null }));
        tEs3s.GetField("path").SetValue(s, pathB);
        tEs3s.GetProperty("location").SetValue(s, locCache, null);
        L("batch settings: path=" + GetF(s, "path") + " location=" + GetP(s, "location")
          + " compression=" + GetF(s, "compressionType") + " encryption=" + GetF(s, "encryptionType"));
        InvokeStatic(tEs3, "CacheFile", new object[] { s });
        long msCache = sw.ElapsedMilliseconds;
        // guard: does the cached view see the same keys as the plain disk read?
        L("keys(disk A) = " + CountKeys(pathA) + "  keys(disk B, pre) = " + CountKeys(pathB));

        sw = Stopwatch.StartNew();
        for (int i = 0; i < keys.Count; i++)
            SaveStringCached(keys[i], vals[i], s);
        long msSets = sw.ElapsedMilliseconds;

        sw = Stopwatch.StartNew();
        InvokeStatic(tEs3, "StoreCachedFile", new object[] { s });
        long msStore = sw.ElapsedMilliseconds;

        L("");
        L("=== TIMING ===");
        L("A  sequential 45 x ES3.Save        = " + msA + " ms   (" + (msA / 45.0).ToString("F1") + " ms/key)");
        L("B  CacheFile                      = " + msCache + " ms");
        L("B  45 x cached Save               = " + msSets + " ms");
        L("B  StoreCachedFile                = " + msStore + " ms");
        L("B  total                          = " + (msCache + msSets + msStore) + " ms");

        L("");
        L("=== EQUIVALENCE ===");
        long lenA = new FileInfo(pathA).Length, lenB = new FileInfo(pathB).Length;
        string shaA = Sha(pathA), shaB = Sha(pathB);
        L("A size=" + lenA + "  sha256=" + shaA);
        L("B size=" + lenB + "  sha256=" + shaB);
        L("BYTE-IDENTICAL = " + (shaA == shaB));

        if (shaA != shaB)
        {
            L("");
            L("--- divergence probe: key sets ---");
            string[] ka = (string[])InvokeStatic(tEs3, "GetKeys", new object[] { pathA });
            string[] kb = (string[])InvokeStatic(tEs3, "GetKeys", new object[] { pathB });
            L("keys A=" + ka.Length + " B=" + kb.Length);
            HashSet<string> sa = new HashSet<string>(ka), sb2 = new HashSet<string>(kb);
            int onlyA = 0, onlyB = 0;
            foreach (string k in sa) if (!sb2.Contains(k)) { if (onlyA < 10) L("  only in A: " + k); onlyA++; }
            foreach (string k in sb2) if (!sa.Contains(k)) { if (onlyB < 10) L("  only in B: " + k); onlyB++; }
            L("onlyA=" + onlyA + " onlyB=" + onlyB);
        }

        // round-trip: can each file still be read back with the PLAIN path?
        L("");
        L("=== ROUND TRIP (plain ES3.Load<string>(key, path)) ===");
        int badA = 0, badB = 0;
        for (int i = 0; i < keys.Count; i++)
        {
            string ra = LoadString(keys[i], "?MISSING?", pathA);
            string rb = LoadString(keys[i], "?MISSING?", pathB);
            if (ra != vals[i]) { if (badA < 3) L("  A mismatch " + keys[i] + " -> " + ra); badA++; }
            if (rb != vals[i]) { if (badB < 3) L("  B mismatch " + keys[i] + " -> " + rb); badB++; }
        }
        L("round-trip failures: A=" + badA + " B=" + badB + "  (of " + keys.Count + ")");
        L("keys(A) final = " + CountKeys(pathA) + "  keys(B) final = " + CountKeys(pathB));
    }

    // ---------- helpers ----------
    static object GetF(object o, string f) { return tEs3s.GetField(f).GetValue(o); }
    static object GetP(object o, string p) { return tEs3s.GetProperty(p).GetValue(o, null); }

    static object InvokeStatic(Type t, string name, object[] a)
    {
        MethodInfo m = null;
        foreach (MethodInfo c in t.GetMethods(BindingFlags.Public | BindingFlags.Static))
        {
            if (c.Name != name) continue;
            ParameterInfo[] ps = c.GetParameters();
            if (ps.Length != a.Length) continue;
            bool ok = true;
            for (int i = 0; i < ps.Length; i++)
                if (a[i] != null && !ps[i].ParameterType.IsInstanceOfType(a[i]) &&
                    ps[i].ParameterType != typeof(string)) { ok = false; break; }
            if (!ok) continue;
            m = c; break;
        }
        if (m == null) throw new MissingMethodException(t.Name + "::" + name + "/" + a.Length);
        // unwrap Nullable-free optional params: pass exactly a.Length args
        return m.Invoke(null, a);
    }

    static void SaveString(string key, string val, string path)
    {
        MethodInfo m = null;
        foreach (MethodInfo c in tEs3.GetMethods(BindingFlags.Public | BindingFlags.Static))
            if (c.Name == "Save" && c.IsGenericMethodDefinition)
            {
                ParameterInfo[] ps = c.GetParameters();
                if (ps.Length == 3 && ps[0].ParameterType == typeof(string)
                    && ps[1].ParameterType.IsGenericParameter
                    && ps[2].ParameterType == typeof(string)) { m = c; break; }
            }
        if (m == null) throw new MissingMethodException("ES3.Save<T>(string,T,string)");
        m.MakeGenericMethod(typeof(string)).Invoke(null, new object[] { key, val, path });
    }

    static void SaveStringCached(string key, string val, object settings)
    {
        MethodInfo m = null;
        foreach (MethodInfo c in tEs3.GetMethods(BindingFlags.Public | BindingFlags.Static))
            if (c.Name == "Save" && c.IsGenericMethodDefinition)
            {
                ParameterInfo[] ps = c.GetParameters();
                if (ps.Length == 3 && ps[0].ParameterType == typeof(string)
                    && ps[1].ParameterType.IsGenericParameter
                    && ps[2].ParameterType == tEs3s) { m = c; break; }
            }
        if (m == null) throw new MissingMethodException("ES3.Save<T>(string,T,ES3Settings)");
        m.MakeGenericMethod(typeof(string)).Invoke(null, new object[] { key, val, settings });
    }

    static string LoadString(string key, string dflt, string path)
    {
        MethodInfo m = null;
        foreach (MethodInfo c in tEs3.GetMethods(BindingFlags.Public | BindingFlags.Static))
            if (c.Name == "Load" && c.IsGenericMethodDefinition)
            {
                ParameterInfo[] ps = c.GetParameters();
                if (ps.Length == 3 && ps[0].ParameterType == typeof(string)
                    && ps[2].ParameterType == typeof(string)) { m = c; break; }
            }
        if (m == null) throw new MissingMethodException("ES3.Load<T>(string,string,T)");
        return (string)m.MakeGenericMethod(typeof(string)).Invoke(null, new object[] { key, dflt, path });
    }

    static int CountKeys(string path)
    {
        try { return ((string[])InvokeStatic(tEs3, "GetKeys", new object[] { path })).Length; }
        catch (Exception e) { L("CountKeys FAILED " + Msg(e)); return -1; }
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
}
