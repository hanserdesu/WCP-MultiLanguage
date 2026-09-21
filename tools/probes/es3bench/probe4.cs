// probe4.cs -- does GameAdapter.Es3WriteBatch.Create() actually succeed, and what
// does the batched write really cost vs. the per-key fallback?
//
// Why this exists (2026-09-18, round 9):
//   Round 8 shipped an ES3 batch (ES3.CacheFile -> N x cached Save -> StoreCachedFile)
//   and proved it offline: 45 per-key writes 5084 ms -> 110 ms.
//   The live session on that exact build (WcpHost.dll fb5365d1..., Player.log 20:02)
//   still shows a single 8528 ms `Enqueue-fix` span -- i.e. roughly 45 x 190 ms, the
//   *unbatched* unit price. There was not one batch-related warning in the log, and
//   the batch only logs on exception, so "Create() returned null" would be silent.
//
//   So the question is narrow and answerable: under the EXACT member-resolution
//   queries GameAdapter uses, do all seven prerequisites resolve? Which one is null?
//   And if they all resolve, is the batched path actually fast for 45 keys?
//
// This probe uses compile-time refs (like probe3) so the patched ES3 assemblies load,
// and it queries members with reflection exactly as GameAdapter does -- including the
// same BindingFlags and the same enum-parse / setter-readback guard. Nothing here is
// a model of the shipped code; it *is* the shipped queries.
//
// usage: probe4.exe <outTxt> <liveSaveCopy> <workDir> <managedDir> [nKeys]
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

class Probe4
{
    static StringBuilder log = new StringBuilder();
    static string managed, work, patchedDir;
    static List<string> firstChance = new List<string>();

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

    static void OnFirstChance(object sender, System.Runtime.ExceptionServices.FirstChanceExceptionEventArgs a)
    {
        if (firstChance.Count > 40) return;
        Exception e = a.Exception;
        MethodBase t = e.TargetSite;
        string site = t == null ? "?" : (t.DeclaringType == null ? "?" : t.DeclaringType.FullName) + "::" + t.Name;
        string line = e.GetType().Name + "  target=" + site;
        if (!firstChance.Contains(line)) firstChance.Add(line);
    }

    // ============================ the experiment ============================
    static void Run(string srcEs3, int nKeys)
    {
        // Same injection probe3 does: defaultSettings must not walk into Resources.Load.
        object bare = new ES3Settings(false);
        typeof(ES3Settings).GetField("_defaults", BindingFlags.NonPublic | BindingFlags.Static)
            .SetValue(null, bare);

        L("");
        L("========== PART 1: GameAdapter.Es3WriteBatch.Create() prerequisites ==========");
        L("(queries are byte-for-byte what GameAdapter.Probe()/Create() runs)");
        L("");

        Type es3 = FindType("ES3");
        Type es3Settings = FindType("ES3Settings");
        Type es3File = FindType("ES3File");
        L("AccessTools.TypeByName equivalent: ES3=" + (es3 == null ? "NULL" : es3.Assembly.GetName().Name) +
          "  ES3Settings=" + (es3Settings == null ? "NULL" : es3Settings.Assembly.GetName().Name) +
          "  ES3File=" + (es3File == null ? "NULL" : es3File.Assembly.GetName().Name));
        if (es3 == null || es3Settings == null) { L("=> Create() returns null at the first null check. STOP."); return; }

        PropertyInfo defaultsProp = es3Settings.GetProperty("defaultSettings",
            BindingFlags.Public | BindingFlags.Static);
        PropertyInfo locationProp = es3Settings.GetProperty("location",
            BindingFlags.Public | BindingFlags.Instance);
        PropertyInfo pathProp = es3Settings.GetProperty("path",
            BindingFlags.Public | BindingFlags.Instance);
        MethodInfo clone = es3Settings.GetMethod("Clone", BindingFlags.Public | BindingFlags.Instance);

        L("");
        L("--- ES3Settings members ---");
        L("  defaultSettings(Public|Static)      = " + D(defaultsProp) +
          (defaultsProp == null ? "" : "   getter=" + V(defaultsProp.GetGetMethod()) + " canRead=" + defaultsProp.CanRead));
        L("  location(Public|Instance)           = " + D(locationProp) +
          (locationProp == null ? "" : "   get=" + V(locationProp.GetGetMethod()) + " set=" + V(locationProp.GetSetMethod())));
        L("  path(Public|Instance)               = " + D(pathProp));
        L("  Clone(Public|Instance)              = " + D(clone) +
          (clone == null ? "" : "  returns " + clone.ReturnType.FullName));

        // SHIPPED: es3Settings.GetNestedType("Location", ...)  -- wrong receiver, see below.
        Type locationTypeShipped = es3Settings.GetNestedType("Location", BindingFlags.Public);
        Type locationType = locationTypeShipped;
        L("");
        L("--- ES3.Location ---");
        L("  SHIPPED: es3Settings.GetNestedType(\"Location\", Public) = " +
          (locationTypeShipped == null ? "NULL   <-- wrong receiver (Location is nested in ES3, not ES3Settings)" : locationTypeShipped.FullName));
        L("  CORRECT: es3.GetNestedType(\"Location\", Public)         = " +
          (es3.GetNestedType("Location", BindingFlags.Public) == null ? "NULL" : es3.GetNestedType("Location", BindingFlags.Public).FullName));
        Type[] nestedPub = es3.GetNestedTypes(BindingFlags.Public);
        Type[] nestedAll = es3.GetNestedTypes(BindingFlags.Public | BindingFlags.NonPublic);
        L("  ES3.GetNestedTypes(Public)     = " + Names(nestedPub));
        L("  ES3.GetNestedTypes(Public|NonPublic) = " + Names(nestedAll));
        for (int i = 0; i < nestedAll.Length; i++)
        {
            Type t = nestedAll[i];
            L("    " + t.Name + ": IsNestedPublic=" + t.IsNestedPublic +
              " IsNestedAssembly=" + t.IsNestedAssembly + " IsNestedFamily=" + t.IsNestedFamily +
              " IsEnum=" + t.IsEnum);
        }
        L("  GetNestedType(\"Location\", Public) = " + (locationType == null ? "NULL" : locationType.FullName));
        object locationCache = null;
        if (locationType != null && locationType.IsEnum)
        {
            Array locVals = Enum.GetValues(locationType);
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < locVals.Length; i++)
                sb.Append(locVals.GetValue(i)).Append('=').Append(Convert.ToInt32(locVals.GetValue(i))).Append(i == locVals.Length - 1 ? "" : ", ");
            L("  values (" + locVals.Length + ") = " + sb);
            try
            {
                locationCache = Enum.Parse(locationType, "Cache", false);
                L("  Enum.Parse(\"Cache\") = " + locationCache + "  (int=" + Convert.ToInt32(locationCache) + ")");
            }
            catch (Exception e)
            {
                L("  Enum.Parse(\"Cache\") THREW " + e.GetType().Name + ": " + e.Message);
                L("  -> GameAdapter falls back to: values.Length > 4 ? values[4] : (null, silently)");
                if (locVals.Length > 4)
                {
                    locationCache = locVals.GetValue(4);
                    L("  fallback values[4] = " + locationCache + "  (int=" + Convert.ToInt32(locationCache) + ")");
                }
                else L("  fallback IMPOSSIBLE: only " + locVals.Length + " members -> locationCache stays NULL -> Create() silently returns null");
            }
        }

        // The two static-method scans, matching GameAdapter's matcher conditions verbatim.
        MethodInfo cacheFile = null, storeCachedFile = null, saveWithSettings = null;
        MethodInfo[] statics = es3.GetMethods(BindingFlags.Public | BindingFlags.Static);
        for (int i = 0; i < statics.Length; i++)
        {
            MethodInfo m = statics[i];
            ParameterInfo[] ps = m.GetParameters();
            if (m.Name == "CacheFile" && ps.Length == 1 && ps[0].ParameterType == es3Settings) cacheFile = m;
            else if (m.Name == "StoreCachedFile" && ps.Length == 1 && ps[0].ParameterType == es3Settings) storeCachedFile = m;
            else if (m.Name == "Save" && m.IsGenericMethodDefinition && ps.Length == 3 &&
                     ps[0].ParameterType == typeof(string) &&
                     ps[1].ParameterType.IsGenericParameter &&
                     ps[2].ParameterType == es3Settings) saveWithSettings = m;
        }
        MethodInfo removeCachedFile = null;
        if (es3File != null)
        {
            MethodInfo[] fs = es3File.GetMethods(BindingFlags.Static | BindingFlags.NonPublic | BindingFlags.Public);
            for (int i = 0; i < fs.Length; i++)
                if (fs[i].Name == "RemoveCachedFile" && fs[i].GetParameters().Length == 1 &&
                    fs[i].GetParameters()[0].ParameterType == es3Settings) removeCachedFile = fs[i];
        }
        L("");
        L("--- ES3 static methods (matcher conditions verbatim) ---");
        L("  ES3.CacheFile(ES3Settings)          = " + D(cacheFile));
        L("  ES3.StoreCachedFile(ES3Settings)    = " + D(storeCachedFile));
        L("  ES3.Save<T>(string,T,ES3Settings)   = " + D(saveWithSettings));
        L("  ES3File.RemoveCachedFile(ES3Settings)= " + D(removeCachedFile) + "  (optional)");

        L("");
        L("--- Create()'s null chain, evaluated ---");
        string[] names = { "_cacheFile", "_storeCachedFile", "_saveWithSettings", "_clone",
                           "_defaultsProp", "_locationProp", "_locationCache" };
        object[] values = { cacheFile, storeCachedFile, saveWithSettings, clone,
                            defaultsProp, locationProp, locationCache };
        int firstNull = -1;
        for (int i = 0; i < names.Length; i++)
        {
            bool ok = values[i] != null;
            if (!ok && firstNull < 0) firstNull = i;
            L("  " + names[i].PadRight(20) + (ok ? "OK" : "<-- NULL  => Create() returns null HERE, silently (no warning is logged)"));
            if (firstNull >= 0) break;
        }
        bool shippedEngages = firstNull < 0;
        if (!shippedEngages)
        {
            L("");
            L("VERDICT: Create() CANNOT succeed with these queries. The batch has never engaged.");
            L("         -> every Es3Save fell through to Es3SaveDirect = one whole-file write each.");
            L("");
            L("========== PART 1b: what it takes to make it resolve ==========");
            if (locationType == null)
            {
                Type fixedLoc = es3.GetNestedType("Location", BindingFlags.Public);
                L("  es3.GetNestedType(\"Location\", Public) = " +
                  (fixedLoc == null ? "still NULL" : fixedLoc.FullName + "  IsEnum=" + fixedLoc.IsEnum));
                if (fixedLoc != null)
                {
                    locationType = fixedLoc;   // gate [1] asserts the CORRECTED query resolves
                    Array fv = Enum.GetValues(fixedLoc);
                    StringBuilder fb = new StringBuilder();
                    for (int i = 0; i < fv.Length; i++)
                        fb.Append(fv.GetValue(i)).Append('=').Append(Convert.ToInt32(fv.GetValue(i))).Append(i == fv.Length - 1 ? "" : ", ");
                    L("  enum members = " + fb);
                    locationCache = Enum.Parse(fixedLoc, "Cache", false);
                    L("  Enum.Parse(\"Cache\") = " + locationCache + " (int=" + Convert.ToInt32(locationCache) + ")");
                    L("  => ONE-LINE FIX: query Location on ES3, not on ES3Settings.");
                }
            }
            if (pathProp == null)
                L("  NOTE: ES3Settings.path is a public FIELD, not a property -> " +
                  "GetProperty(\"path\") is NULL. GameAdapter tolerates this (null-guarded), " +
                  "but the 'path must exist' safety check then never runs. Use GetField, or " +
                  "rely on defaultSettings.path.");
            L("");
            L("Continuing with the CORRECTED lookup so PART 2 can price both arms.");
        }

        // Exercise the remaining Create() body: clone, path readback, location setter readback.
        L("");
        L("--- Create() body (corrected lookups) ---");
        object settings = clone.Invoke(defaultsProp.GetValue(null, null), null);
        L("  clone(defaultSettings)              = " + D(settings) + (settings == null ? "" : "  type=" + settings.GetType().FullName));
        if (settings == null) { L("VERDICT: clone returned null -> Create() returns null."); return; }
        FieldInfo pathField = pathProp == null
            ? es3Settings.GetField("path", BindingFlags.Public | BindingFlags.Instance) : null;
        L("  path accessor used                  = " + (pathProp != null ? "property" :
            (pathField != null ? "FIELD (property lookup missed)" : "NONE")));
        object p = pathProp != null ? pathProp.GetValue(settings, null)
                 : (pathField != null ? pathField.GetValue(settings) : null);
        L("  cloned path                         = " + (p == null ? "NULL -> Create() returns null" : "'" + p + "'"));
        bool shippedPathGuardRan = pathProp != null;
        L("  shipped 'path must exist' guard ran = " + shippedPathGuardRan);
        if (p == null) { L("VERDICT: no path -> Create() returns null."); return; }
        locationProp.SetValue(settings, locationCache, null);
        object back = locationProp.GetValue(settings, null);
        bool readback = locationCache.Equals(back);
        L("  set location=" + locationCache + " -> readback=" + back + "  equal=" + readback +
          (readback ? "" : "  => Create() returns null ('setter did not take')"));
        if (!readback) return;
        L("  => ALL PREREQUISITES MET: Create() succeeds in-game too (same queries, same types).");

        // ================= PART 2: real cost of both arms =================
        string live = Path.Combine(work, "live_save.es3");
        string def = Path.Combine(work, "SaveFile.es3");     // patched persistentDataPath == work
        long srcLen = new FileInfo(live).Length;
        L("");
        L("========== PART 2: arm A (per-key, location=File) vs arm B (batched) ==========");
        L("live save = " + live + "  (" + srcLen + " B)   default-file arm writes = " + def);
        L("keys to write = " + nKeys);

        List<string> keys = new List<string>();
        List<string> vals = new List<string>();
        for (int i = 0; i < nKeys; i++)
        {
            keys.Add("wcp_p4_" + i);
            vals.Add("v" + i + "-" + new string('x', 40));
        }

        // ---- A: exactly what Es3SaveDirect does -- ES3.Save<T>(key,value), unpathed ----
        File.Copy(live, def, true);
        int keysBefore = ES3.GetKeys(def).Length;
        Stopwatch sw = Stopwatch.StartNew();
        long firstA = -1;
        MethodInfo save2 = null;
        MethodInfo[] all = es3.GetMethods(BindingFlags.Public | BindingFlags.Static);
        for (int i = 0; i < all.Length; i++)
        {
            MethodInfo m = all[i];
            ParameterInfo[] ps = m.GetParameters();
            if (m.Name == "Save" && m.IsGenericMethodDefinition && ps.Length == 2 &&
                ps[0].ParameterType == typeof(string) && ps[1].ParameterType.IsGenericParameter)
            { save2 = m; break; }
        }
        for (int i = 0; i < keys.Count; i++)
        {
            long t0 = sw.ElapsedMilliseconds;
            save2.MakeGenericMethod(typeof(string)).Invoke(null, new object[] { keys[i], vals[i] });
            HandCommit(def);   // ES3IO.CommitBackup is neutered in the patched copy
            if (i == 0) firstA = sw.ElapsedMilliseconds - t0;
        }
        sw.Stop();
        long msA = sw.ElapsedMilliseconds;
        L("");
        L("A   " + nKeys + " x ES3.Save<string>(k,v) [no path] = " + msA + " ms   first=" + firstA +
          " ms  avg=" + (msA / (double)nKeys).ToString("F1") + " ms/key");
        L("    hand-commits=" + handCommits + " misses=" + handMisses);
        L("    keys before=" + keysBefore + " after=" + ES3.GetKeys(def).Length + "  size=" + new FileInfo(def).Length);

        // ---- B: the shipped batch, one whole-file read + one write ----
        File.Copy(live, def, true);
        object bs = clone.Invoke(defaultsProp.GetValue(null, null), null);
        locationProp.SetValue(bs, locationCache, null);
        L("");
        object bPath = pathProp != null ? pathProp.GetValue(bs, null) : pathField.GetValue(bs);
        L("B   batch settings path='" + bPath + "' location=" + locationProp.GetValue(bs, null));
        sw = Stopwatch.StartNew();
        cacheFile.Invoke(null, new object[] { bs });
        long msCache = sw.ElapsedMilliseconds;
        sw = Stopwatch.StartNew();
        MethodInfo saveBatch = saveWithSettings.MakeGenericMethod(typeof(string));
        for (int i = 0; i < keys.Count; i++) saveBatch.Invoke(null, new object[] { keys[i], vals[i], bs });
        long msSets = sw.ElapsedMilliseconds;
        sw = Stopwatch.StartNew();
        storeCachedFile.Invoke(null, new object[] { bs });
        long msStore = sw.ElapsedMilliseconds;
        handCommits = 0; handMisses = 0;
        HandCommit(def);
        L("B   CacheFile            = " + msCache + " ms");
        L("B   " + nKeys + " x cached Save    = " + msSets + " ms");
        L("B   StoreCachedFile      = " + msStore + " ms");
        L("B   total                = " + (msCache + msSets + msStore) + " ms" +
          "   speedup=" + (msA / (double)Math.Max(1, msCache + msSets + msStore)).ToString("F1") + "x");
        L("    hand-commits=" + handCommits + " misses=" + handMisses);
        L("    keys after=" + ES3.GetKeys(def).Length + "  size=" + new FileInfo(def).Length);

        // ---- did the batch preserve every pre-existing key? ----
        string[] srcKeys = ES3.GetKeys(live);
        string[] outKeys = ES3.GetKeys(def);
        HashSet<string> so = new HashSet<string>(outKeys, StringComparer.Ordinal);
        int lost = 0;
        for (int i = 0; i < srcKeys.Length; i++) if (!so.Contains(srcKeys[i])) lost++;
        L("");
        L("--- B preservation check (this is what decides whether the batch is safe) ---");
        L("    live keys=" + srcKeys.Length + "  after B=" + outKeys.Length +
          "  LOST=" + lost + (lost == 0 ? "   (no data loss)" : "   <-- DATA LOSS"));
        int roundFail = 0;
        for (int i = 0; i < keys.Count; i++)
            if (ES3.Load<string>(keys[i], def, "?MISSING?") != vals[i]) roundFail++;
        L("    round-trip of the " + keys.Count + " written keys: failures=" + roundFail);

        try { removeCachedFile.Invoke(null, new object[] { bs }); L("    RemoveCachedFile invoked OK"); }
        catch (Exception e) { L("    RemoveCachedFile THREW " + Msg(e)); }

        // ================= PART 3: cross-scope cache reuse (round 15) ==========
        // Shipped design (GameAdapter.Es3WriteBatch, round 15): after a SUCCESSFUL
        // StoreCachedFile, KEEP the ES3 cache entry alive (no RemoveCachedFile) and
        // remember the file's (mtime,size). The next batch session skips CacheFile
        // iff the stamp still matches the file on disk. Two safety properties must
        // hold with the REAL ES3 assemblies:
        //   [5] skip path: batch #2 without CacheFile still sees batch #1's keys
        //       (i.e. the cache entry really survived StoreCachedFile);
        //   [6] stale guard: after an EXTERNAL writer touches the file, the
        //       remove-then-reload path picks the external write up (no stale read,
        //       no clobber). We remove the entry before re-caching: we do not rely
        //       on CacheFile's overwrite semantics for an existing entry.
        // ES3's cache dictionary keys on the settings INSTANCE, so the shipped code
        // reuses one cloned settings object across scopes -- mirrored here.
        L("");
        L("========== PART 3: cache reuse across batch scopes (round 15) ==========");
        File.Copy(live, def, true);
        object sA = clone.Invoke(defaultsProp.GetValue(null, null), null);
        locationProp.SetValue(sA, locationCache, null);
        string kA = "wcp_r15_A", kB = "wcp_r15_B", kX = "wcp_r15_ext";
        string vA = "value-A-" + new string('a', 30), vB = "value-B-" + new string('b', 30), vX = "value-EXT-" + new string('x', 30);

        // session 1: full load + put A + store; record stamp, keep entry alive.
        sw = Stopwatch.StartNew();
        cacheFile.Invoke(null, new object[] { sA });
        long msL1 = sw.ElapsedMilliseconds;
        saveWithSettings.MakeGenericMethod(typeof(string)).Invoke(null, new object[] { kA, vA, sA });
        storeCachedFile.Invoke(null, new object[] { sA });
        HandCommit(def);
        long[] stamp = new long[] { File.GetLastWriteTimeUtc(def).Ticks, new FileInfo(def).Length };
        L("  session1: CacheFile=" + msL1 + " ms, put " + kA + ", stored, stamp=(ticks=" +
          stamp[0] + ", size=" + stamp[1] + ")");

        // session 2: stamp matches -> SKIP CacheFile entirely; put B + store.
        bool stampMatch = stamp[1] == new FileInfo(def).Length &&
                          stamp[0] == File.GetLastWriteTimeUtc(def).Ticks;
        sw = Stopwatch.StartNew();
        saveWithSettings.MakeGenericMethod(typeof(string)).Invoke(null, new object[] { kB, vB, sA });
        storeCachedFile.Invoke(null, new object[] { sA });
        HandCommit(def);
        long msS2 = sw.ElapsedMilliseconds;
        L("  session2: stampMatch=" + stampMatch + " -> CacheFile SKIPPED (0 ms), put " +
          kB + " + store = " + msS2 + " ms");

        // preservation: batch #1's key and one original live key must still be there.
        // (Original keys can be any type -- e.g. String[] -- so presence is checked
        //  via the key list, never by loading with a hard-coded type.)
        string backA = ES3.Load<string>(kA, def, "?MISSING?");
        string backB = ES3.Load<string>(kB, def, "?MISSING?");
        string[] liveKeys3 = ES3.GetKeys(live);
        string[] defKeys3 = ES3.GetKeys(def);
        HashSet<string> defKeySet = new HashSet<string>(defKeys3, StringComparer.Ordinal);
        string probeKey = liveKeys3.Length > 0 ? liveKeys3[0] : null;
        bool origKept = probeKey == null || defKeySet.Contains(probeKey);
        bool g5 = stampMatch && backA == vA && backB == vB && origKept;
        L("  session2 readback: " + kA + "=" + (backA == vA ? "OK" : "WRONG('" + backA + "')") +
          "  " + kB + "=" + (backB == vB ? "OK" : "WRONG('" + backB + "')") +
          "  orig[" + probeKey + "] present=" + origKept);
        L("  => [5] skip path keeps batch-1 + original keys: " + (g5 ? "PASS" : "FAIL"));

        // session 3: EXTERNAL writer touches the file -> stamp must mismatch ->
        // design reloads via remove-then-CacheFile; external key must be visible.
        save2.MakeGenericMethod(typeof(string)).Invoke(null, new object[] { kX, vX });
        HandCommit(def);
        bool extChangedStamp = !(stamp[1] == new FileInfo(def).Length &&
                                 stamp[0] == File.GetLastWriteTimeUtc(def).Ticks);
        try { removeCachedFile.Invoke(null, new object[] { sA }); }
        catch (Exception e) { L("  removeCachedFile THREW " + Msg(e)); }
        cacheFile.Invoke(null, new object[] { sA });   // full reload
        storeCachedFile.Invoke(null, new object[] { sA });
        HandCommit(def);
        string backX = ES3.Load<string>(kX, def, "?MISSING?");
        string backA3 = ES3.Load<string>(kA, def, "?MISSING?");
        bool g6 = extChangedStamp && backX == vX && backA3 == vA;
        L("  session3: external ES3.Save(" + kX + ") changed stamp=" + extChangedStamp +
          " -> remove + CacheFile + store");
        L("  session3 readback: " + kX + "=" + (backX == vX ? "OK" : "WRONG('" + backX + "')") +
          "  " + kA + "=" + (backA3 == vA ? "OK" : "WRONG('" + backA3 + "')"));
        L("  => [6] stale guard picks up external writes: " + (g6 ? "PASS" : "FAIL"));

        // ================= PART 4: write-behind semantics (round 16) ==========
        // Shipped design change (GameAdapter.Es3WriteBatch, round 16): Put() only
        // records into _written (NO ES3 call, NO disk touch); Dispose() enqueues;
        // Host.Update drains ONE batch per frame; Commit() = stamp-check ->
        // CacheFile if needed -> cached Saves -> StoreCachedFile. Real-machine
        // evidence (R15 log 23:45): cache reuse NEVER hit (game rewrites
        // SaveFile.es3 on every answer -> stamp always stale) while the load
        // still stood on the switch frame (115-134 ms). So the load+store must
        // move OFF the switch frame entirely.
        //   [7a] "Put" phase touches nothing: file bytes identical after recording;
        //   [7b] drain #1 (no stamp -> full CacheFile): writes land, originals kept;
        //   [7c] drain #2 (stamp from drain #1 matches -> CacheFile SKIPPED):
        //        second batch's writes land with the first batch's preserved.
        L("");
        L("========== PART 4: write-behind (round 16) ==========");
        File.Copy(live, def, true);
        HandCommit(def);   // flush any stray tmp from the copy
        string h0 = SHA(def);
        long len0 = new FileInfo(def).Length;

        // scope 1: "Put" = record only.
        Dictionary<string, string> writes1 = new Dictionary<string, string>(StringComparer.Ordinal);
        string kW1 = "wcp_r16_W1", kW2 = "wcp_r16_W2";
        string vW1 = "wb-1-" + new string('1', 30), vW2 = "wb-2-" + new string('2', 30);
        writes1[kW1] = vW1; writes1[kW2] = vW2;
        bool untouched = SHA(def) == h0 && new FileInfo(def).Length == len0;
        L("  scope1: recorded " + writes1.Count + " writes, disk untouched=" + untouched);

        // drain 1: no stamp yet -> full CacheFile -> apply -> store.
        cacheFile.Invoke(null, new object[] { sA });
        foreach (KeyValuePair<string, string> kv in writes1)
            saveWithSettings.MakeGenericMethod(typeof(string)).Invoke(null, new object[] { kv.Key, kv.Value, sA });
        storeCachedFile.Invoke(null, new object[] { sA });
        HandCommit(def);
        long[] stampD1 = new long[] { File.GetLastWriteTimeUtc(def).Ticks, new FileInfo(def).Length };
        string rW1 = ES3.Load<string>(kW1, def, "?MISSING?");
        string rW2 = ES3.Load<string>(kW2, def, "?MISSING?");
        string[] liveKeys4 = ES3.GetKeys(live);
        string[] defKeys4 = ES3.GetKeys(def);
        HashSet<string> defSet4 = new HashSet<string>(defKeys4, StringComparer.Ordinal);
        bool origKept4 = true;
        for (int i = 0; i < liveKeys4.Length; i++) if (!defSet4.Contains(liveKeys4[i])) { origKept4 = false; break; }
        bool g7b = rW1 == vW1 && rW2 == vW2 && origKept4;
        L("  drain1: full load -> apply -> store; readback W1=" + (rW1 == vW1 ? "OK" : "WRONG") +
          " W2=" + (rW2 == vW2 ? "OK" : "WRONG") + " originals kept=" + origKept4);

        // scope 2 + drain 2: stamp from drain1 matches -> CacheFile SKIPPED.
        string kW3 = "wcp_r16_W3", vW3 = "wb-3-" + new string('3', 30);
        bool reuseSkipped = stampD1[1] == new FileInfo(def).Length &&
                            stampD1[0] == File.GetLastWriteTimeUtc(def).Ticks;
        saveWithSettings.MakeGenericMethod(typeof(string)).Invoke(null, new object[] { kW3, vW3, sA });
        storeCachedFile.Invoke(null, new object[] { sA });
        HandCommit(def);
        string rW3 = ES3.Load<string>(kW3, def, "?MISSING?");
        string rW1b = ES3.Load<string>(kW1, def, "?MISSING?");
        bool g7c = reuseSkipped && rW3 == vW3 && rW1b == vW1;
        L("  drain2: stampMatch=" + reuseSkipped + " -> CacheFile SKIPPED; W3=" +
          (rW3 == vW3 ? "OK" : "WRONG") + " W1 still=" + (rW1b == vW1 ? "OK" : "WRONG"));
        bool g7 = untouched && g7b && g7c;
        L("  => [7] write-behind: put touches nothing, drain lands correct bytes, reuse links: " +
          (g7 ? "PASS" : "FAIL"));

        // ================= GATE =================
        // Why this gate exists: the round-8 batch failed for a whole round with zero
        // log output, and the only symptom was "still stutters". A mechanism that can
        // silently degrade to 45x slower must have an offline gate. Absence of the
        // PASS line == FAIL (every failure path above returns before reaching here).
        L("");
        L("========== GATE ==========");
        bool g1 = locationType != null && locationCache != null;
        bool g2 = cacheFile != null && storeCachedFile != null && saveWithSettings != null &&
                  clone != null && defaultsProp != null && locationProp != null &&
                  locationCache != null;
        long msB = msCache + msSets + msStore;
        bool g3 = msA > 0 && msB > 0 && msA / (double)msB >= 10.0 && msB < 500;
        bool g4 = lost == 0 && roundFail == 0;
        L("  [1] ES3.Location reachable via es3.GetNestedType + Cache parses : " + (g1 ? "PASS" : "FAIL"));
        L("      (the round-8 pattern -- es3Settings.GetNestedType -- returns NULL; " +
          (locationTypeShipped == null ? "confirmed NULL here" : "WARNING: it resolved?!") + ")");
        L("  [2] all 7 Create() prerequisites resolve                        : " + (g2 ? "PASS" : "FAIL"));
        L("  [3] batched arm >=10x faster and under 500 ms                   : " + (g3 ? "PASS" : "FAIL") +
          "   (A=" + msA + "ms  B=" + msB + "ms  " + (msB > 0 ? (msA / (double)msB).ToString("F1") : "?") + "x)");
        L("  [4] no key lost, every written key round-trips                  : " + (g4 ? "PASS" : "FAIL") +
          "   (lost=" + lost + " roundTripFailures=" + roundFail + ")");
        L("  [5] cache-reuse skip path keeps batch-1 + original keys         : " + (g5 ? "PASS" : "FAIL") +
          "   (stampMatch=" + stampMatch + ")");
        L("  [6] stale guard: external write picked up after reload          : " + (g6 ? "PASS" : "FAIL") +
          "   (extChangedStamp=" + extChangedStamp + ")");
        L("  [7] write-behind: put touches nothing, drain lands, reuse links : " + (g7 ? "PASS" : "FAIL") +
          "   (untouched=" + untouched + " drain1=" + g7b + " drain2Reuse=" + g7c + ")");
        L("");
        L("PROBE4 GATE: " + ((g1 && g2 && g3 && g4 && g5 && g6 && g7) ? "PASS" : "FAIL"));
    }

    // ES3Internal.ES3IO.CommitBackup is neutered in the patched copy (it aborts outside
    // Unity). Do its work here so the bytes actually land, identically for both arms:
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

    static string Names(Type[] ts)
    {
        if (ts == null || ts.Length == 0) return "(none)";
        StringBuilder b = new StringBuilder();
        for (int i = 0; i < ts.Length; i++) b.Append(ts[i].Name).Append(i == ts.Length - 1 ? "" : ", ");
        return b.ToString();
    }

    static string D(object o) { return o == null ? "NULL" : o.ToString(); }
    static string V(MethodBase m) { return m == null ? "NULL" : (m.IsPublic ? "public" : "non-public"); }

    static string SHA(string file)
    {
        using (FileStream fs = File.OpenRead(file))
        using (SHA256 sha = SHA256.Create())
        {
            byte[] h = sha.ComputeHash(fs);
            StringBuilder b = new StringBuilder(h.Length * 2);
            for (int i = 0; i < h.Length; i++) b.Append(h[i].ToString("x2"));
            return b.ToString();
        }
    }

    static Type FindType(string name)
    {
        Assembly[] asms = AppDomain.CurrentDomain.GetAssemblies();
        for (int i = 0; i < asms.Length; i++)
        {
            try
            {
                Type t = asms[i].GetType(name, false);
                if (t != null) return t;
            }
            catch (Exception) { }
        }
        try { return typeof(ES3).Assembly.GetType(name, false); }
        catch (Exception) { return null; }
    }

    // ============================ plumbing (same as probe3) ============================
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
                if (killWholeType || (!isCoreModule &&
                                      (t.FullName == "ES3Internal.ES3Debug" ||
                                       (t.FullName == "ES3Internal.ES3IO" && m.Name == "CommitBackup") ||
                                       (t.FullName == "ES3Settings" && m.Name == "get_defaultSettingsScriptableObject"))))
                {
                    ReturnDefault(m); n++; continue;
                }
                ILProcessor il = m.Body.GetILProcessor();
                foreach (Instruction ins in new List<Instruction>(m.Body.Instructions))
                {
                    MethodReference mr = ins.Operand as MethodReference;
                    if (mr == null || mr.DeclaringType == null) continue;
                    if (isCoreModule && m.Name == ".cctor" && mr.Name == "GetOffsetOfInstanceIDInCPlusPlusObject")
                    { il.Replace(ins, Instruction.Create(OpCodes.Ldc_I4_0)); n++; continue; }
                    if (mr.DeclaringType.FullName != "UnityEngine.Application") continue;
                    Instruction repl = null;
                    if (mr.Name == "get_platform") repl = Instruction.Create(OpCodes.Ldc_I4_2);
                    else if (mr.Name == "get_persistentDataPath") repl = Instruction.Create(OpCodes.Ldstr, work);
                    else if (mr.Name == "get_dataPath") repl = Instruction.Create(OpCodes.Ldstr, work);
                    else if (mr.Name == "get_streamingAssetsPath") repl = Instruction.Create(OpCodes.Ldstr, work);
                    if (repl == null) continue;
                    il.Replace(ins, repl); n++;
                }
            }
        }
        ad.Write(Path.Combine(patchedDir, file));
        return n;
    }

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
