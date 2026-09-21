// probe6 -- 量化 HostPatches.InstallFeatures 的 1827ms 到底花在哪
//
// 背景（实机证据）：
//   Player.log:658  "语言策略已确认，行为 Harmony 接线已安装"
//   Player.log:664  长帧 18632ms — 补丁:Sync x1=1827.4ms
//   Player.log:702  "行为 Harmony 接线已移除"（退出时）—— install 全程只发生 1 次
// 所以 1827ms 是**一次性**的 Harmony 接线成本，不是抖动。HostPatches.InstallFeatures
// 内部结构：PatchSet 被调 20 次、PatchOne 被调 20 次，每个入口都先做一次
// AccessTools.TypeByName(名字)；25 个唯一名字被反复解析 40 次。
// Harmony 的 TypeByName 要遍历 AppDomain.CurrentDomain.GetAssemblies() 的 GetTypes()，
// 单价随已加载程序集数量增长。本探针就是要量出：
//   A) 在 Managed 目录全部程序集加载前后，TypeByName 的单价差别（证明它随程序集数增长）
//   B) 同名重复调用是否命中 Harmony 内部缓存
//   C) 40 次真实调用序列的总时长，与实机 1827ms 是否同量级
//   D) 按名字缓存 Type 之后的总时长（候选优化的收益）
//
// Usage: probe6.exe <outFile> <bepInExCoreDir> <managedDir> <repoWcpHostDll>
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Reflection;
using System.Text;
using HarmonyLib;

internal static class Probe6
{
    private static readonly List<string> Out = new List<string>();

    private static void W(string s)
    {
        Out.Add(s);
        Console.WriteLine(s);
    }

    // HostPatches 里出现的全部类型名，按 PatchSet/PatchOne 的调用顺序展开
    // （重复项保留，因为重复调用正是要量的东西）。
    private static readonly string[] PatchSetPrefixTypes = new string[] {
        "InitializeManagerS2", "WordListManagerS7", "S3ScoreShow",
        "LifeAndScoreManagerS15", "showWordS17", "RandomButtonInvoker",
        "MultipleChoiceGenerator", "MultipleChoiceGeneratorS9", "SetS8Data" };

    private static readonly string[] PatchSetPostfixTypes = new string[] {
        "ChooseWordManager", "InitializeManagerS2", "updateNewLearnWord",
        "WordListManagerS7", "SetS8Data", "ButtonEquivalence", "S7NumberAdd",
        "ColorInputFieldS17", "MultipleChoiceGenerator", "RandomButtonInvoker",
        "clickChangeImageSource" };

    private static readonly string[][] PatchOneCalls = new string[][] {
        new string[] { "SetS8Data", "SetAsLearnedTest" },
        new string[] { "MultipleChoiceGeneratorS9", "Start" },
        new string[] { "MultipleChoiceGeneratorS9", "GenerateOptions" },
        new string[] { "MultipleChoiceGenerator", "GenerateOptions" },
        new string[] { "MultipleChoiceGeneratorS9", "GenerateOptions" },
        new string[] { "SetInputFieldValueS8", "ShowTheWord" },
        new string[] { "DatabaseManagerS8", "OnSearchButtonClick" },
        new string[] { "S8checkWordMeaning", "OnSearchButtonClick" },
        new string[] { "ButtonTextTransfer", "OnSearchButtonClick" },
        new string[] { "showTheAnswerS8", "ShowAnswer" },
        new string[] { "showTheAnswerS8", "ShowAnswerForStudy" },
        new string[] { "showTheAnswerS8", "ShowAnswerNoAutoVoice" },
        new string[] { "VocabularyAudioPlayer", "PlayWordAudio" },
        new string[] { "SoundTheWordS8", "OnButton1Click" },
        new string[] { "PageController", "SetThis" },
        new string[] { "GoToAllS9", "ArrayToAll" },
        new string[] { "SwitchCurrentArrayS9", "SwitchThis" },
        new string[] { "ChooseWordManager", "AddWordsToSelfChosenList" },
        new string[] { "SetInputFieldValueS8", "changeKnownFuzzUnknownTimes" },
        new string[] { "WordListManagerS7", "Start" }
    };

    private static int Main(string[] args)
    {
        string outFile = args.Length > 0 ? args[0] : "probe6_out.txt";
        string core = args.Length > 1 ? args[1] : null;
        string managed = args.Length > 2 ? args[2] : null;
        string wcpDll = args.Length > 3 ? args[3] : null;

        // 依赖解析必须在**任何 HarmonyLib 引用被 JIT 之前**装好：Run 的方法体里用到
        // AccessTools/Harmony，JIT 编译 Run 时就要解析 0Harmony，而它不在 exe 同目录。
        // 第一版把注册写在 Run 内部 -> JIT 先进 Run 才注册 -> 鸡生蛋 -> FileNotFound。
        List<string> probeDirs = new List<string>();
        if (!string.IsNullOrEmpty(core)) probeDirs.Add(core);
        if (!string.IsNullOrEmpty(managed)) probeDirs.Add(managed);
        probeDirs.Add(AppDomain.CurrentDomain.BaseDirectory);

        AppDomain.CurrentDomain.AssemblyResolve += delegate(object s, ResolveEventArgs e)
        {
            try
            {
                string simple = new AssemblyName(e.Name).Name;
                for (int i = 0; i < probeDirs.Count; i++)
                {
                    string p = Path.Combine(probeDirs[i], simple + ".dll");
                    if (File.Exists(p)) return Assembly.LoadFrom(p);
                }
            }
            catch { }
            return null;
        };

        // 显式预加载 0Harmony，让 Run 的 JIT 直接命中。
        for (int i = 0; i < probeDirs.Count; i++)
        {
            string h = Path.Combine(probeDirs[i], "0Harmony.dll");
            if (File.Exists(h))
            {
                try { Assembly.LoadFrom(h); } catch { }
                break;
            }
        }

        try { Run(probeDirs, managed, wcpDll); }
        catch (Exception e) { W("FATAL " + e.GetType().Name + ": " + e.Message); W(e.StackTrace); }

        try { File.WriteAllLines(outFile, Out.ToArray(), new UTF8Encoding(false)); } catch { }
        return 0;
    }

    private static void Run(List<string> probeDirs, string managed, string wcpDll)
    {
        W("PROBE6 -- where does the 1827 ms 'PatchSync' go?");
        W("");

        // ── 0) 展开真实调用序列 ──
        List<string> sequence = new List<string>();
        for (int i = 0; i < PatchSetPrefixTypes.Length; i++) sequence.Add(PatchSetPrefixTypes[i]);
        for (int i = 0; i < PatchSetPostfixTypes.Length; i++) sequence.Add(PatchSetPostfixTypes[i]);
        HashSet<string> unique = new HashSet<string>(StringComparer.Ordinal);
        for (int i = 0; i < sequence.Count; i++) unique.Add(sequence[i]);
        for (int i = 0; i < PatchOneCalls.Length; i++)
        {
            sequence.Add(PatchOneCalls[i][0]);
            unique.Add(PatchOneCalls[i][0]);
        }
        W("--- call inventory (from HostPatches.cs) ---");
        W("  PatchSet calls       = " + (PatchSetPrefixTypes.Length + PatchSetPostfixTypes.Length)
          + "  (each does one TypeByName)");
        W("  PatchOne calls       = " + PatchOneCalls.Length + "  (each does one TypeByName)");
        W("  total TypeByName     = " + sequence.Count);
        W("  unique type names    = " + unique.Count);
        W("  redundant lookups    = " + (sequence.Count - unique.Count));
        W("");

        // ── 1) 基线：Managed 未加载时 ──
        W("--- before loading game assemblies ---");
        W("  assemblies in AppDomain = " + AppDomain.CurrentDomain.GetAssemblies().Length);
        double baseFirst = TimeOne("InitializeManagerS2");
        double baseRepeat = TimeOne("InitializeManagerS2");
        W("  TypeByName(\"InitializeManagerS2\") first = " + F(baseFirst) + " ms, repeat = "
          + F(baseRepeat) + " ms   (null here -- game asm not loaded yet)");
        W("");

        // ── 2) 加载 Managed 全部程序集，模拟实机 ──
        W("--- loading every dll from the game's Managed dir ---");
        int ok = 0, fail = 0;
        List<string> failed = new List<string>();
        if (managed != null && Directory.Exists(managed))
        {
            string[] dlls = Directory.GetFiles(managed, "*.dll");
            Array.Sort(dlls, StringComparer.Ordinal);
            for (int i = 0; i < dlls.Length; i++)
            {
                try { Assembly.LoadFrom(dlls[i]); ok++; }
                catch (Exception e) { fail++; if (failed.Count < 8) failed.Add(Path.GetFileName(dlls[i]) + " (" + e.GetType().Name + ")"); }
            }
            W("  files = " + dlls.Length + "  loaded = " + ok + "  failed = " + fail);
            for (int i = 0; i < failed.Count; i++) W("    fail: " + failed[i]);
        }
        else W("  managed dir missing: " + managed);
        W("  assemblies in AppDomain = " + AppDomain.CurrentDomain.GetAssemblies().Length);
        W("");

        // ── 3) 加载后的单价 ──
        W("--- after game assemblies are loaded ---");
        double loadedFirst = TimeOne("InitializeManagerS2");
        double loadedRepeat = TimeOne("InitializeManagerS2");
        W("  TypeByName(\"InitializeManagerS2\") first = " + F(loadedFirst) + " ms, repeat = "
          + F(loadedRepeat) + " ms");
        W("  growth vs baseline = " + F(loadedFirst / Math.Max(0.001, baseFirst)) + "x");
        W("");

        // ── 4) 逐个名字量单价（每个名字只量第一次） ──
        W("--- per-name cost, first touch (this is what InstallFeatures actually pays) ---");
        string[] uniq = new string[unique.Count];
        unique.CopyTo(uniq);
        Array.Sort(uniq, StringComparer.Ordinal);
        double totalFirstTouch = 0;
        int resolved = 0;
        Stopwatch swAll = Stopwatch.StartNew();
        for (int i = 0; i < uniq.Length; i++)
        {
            Stopwatch s = Stopwatch.StartNew();
            Type t = AccessTools.TypeByName(uniq[i]);
            s.Stop();
            double ms = s.Elapsed.TotalMilliseconds;
            totalFirstTouch += ms;
            if (t != null) resolved++;
            W("  " + Pad(uniq[i], 26) + F(ms).PadLeft(9) + " ms   " + (t == null ? "NULL" : "OK"));
        }
        swAll.Stop();
        W("  ---- resolved " + resolved + " / " + uniq.Length + " names");
        W("  sum of individual first touches = " + F(totalFirstTouch) + " ms");
        W("  wall clock for the whole loop    = " + F(swAll.Elapsed.TotalMilliseconds) + " ms");
        W("");

        // ── 5) 真实序列（40 次含重复） ──
        W("--- replaying the real 40-call sequence ---");
        double seqWall = TimeBest(3, delegate()
        {
            for (int i = 0; i < sequence.Count; i++) AccessTools.TypeByName(sequence[i]);
        });
        W("  wall clock = " + F(seqWall) + " ms   (vs real-machine 1827 ms for the whole Sync)");
        // 用字典缓存后
        Dictionary<string, Type> cache = new Dictionary<string, Type>(StringComparer.Ordinal);
        double cachedWall = TimeBest(3, delegate()
        {
            for (int i = 0; i < sequence.Count; i++)
            {
                Type t;
                if (!cache.TryGetValue(sequence[i], out t))
                {
                    t = AccessTools.TypeByName(sequence[i]);
                    cache[sequence[i]] = t;
                }
            }
        });
        W("  with a name->Type cache = " + F(cachedWall) + " ms   saved = "
          + F(seqWall - cachedWall) + " ms (" + F((seqWall - cachedWall) / Math.Max(0.001, seqWall) * 100.0) + "%)");
        W("");

        // ── 6) 冷启动 vs 预热：第一次和最暖的一次 ──
        W("--- cold vs warm (does Harmony cache internally?) ---");
        double cold = TimeOne("DatabaseManagerS8");   // 刚才没单独量过或量过
        double warm = TimeOne("DatabaseManagerS8");
        W("  DatabaseManagerS8 cold=" + F(cold) + " ms warm=" + F(warm) + " ms  -> "
          + (cold > warm * 5 ? "COLD-ONLY cost (idempotent warm path)" : "no big gap"));
        W("");

        // ── 7) 真实 InstallFeatures 里 Harmony.Patch 的净成本 ──
        W("--- can we attribute the rest to Harmony.Patch itself? ---");
        if (wcpDll == null || !File.Exists(wcpDll)) { W("  wcp dll missing: " + wcpDll); }
        else
        {
            try
            {
                Assembly wcp = Assembly.LoadFrom(wcpDll);
                Type hp = wcp.GetType("WcpHost.HostPatches");
                MethodInfo install = hp == null ? null :
                    hp.GetMethod("InstallFeatures", BindingFlags.NonPublic | BindingFlags.Static);
                W("  HostPatches.InstallFeatures = " + (install == null ? "NULL" : install.ToString()));
                if (install != null)
                {
                    // 装一个全新的 Harmony 实例，量真实的 InstallFeatures 全程。
                    Harmony h = new Harmony("probe6.timing");
                    Stopwatch s = Stopwatch.StartNew();
                    try { install.Invoke(null, new object[] { h }); }
                    catch (Exception e)
                    {
                        Exception inner = e is TargetInvocationException ? e.InnerException : e;
                        W("  InstallFeatures threw " + (inner == null ? e.Message : inner.GetType().Name + ": " + inner.Message));
                    }
                    s.Stop();
                    double total = s.Elapsed.TotalMilliseconds;
                    W("  real InstallFeatures wall clock = " + F(total) + " ms");
                    W("  (this is the number to compare with the real machine's 1827 ms)");

                    // 数出真正被 patch 的目标方法数 —— 这才是 Harmony.Patch 的调用次数。
                    List<MethodBase> patched = new List<MethodBase>();
                    try
                    {
                        foreach (MethodBase mb in h.GetPatchedMethods()) patched.Add(mb);
                    }
                    catch (Exception e) { W("  GetPatchedMethods failed: " + e.Message); }
                    W("  patched target methods        = " + patched.Count);
                    if (patched.Count > 0)
                        W("  average cost per patched method= " + F(total / patched.Count)
                          + " ms   (this is the real unit price of harmony.Patch)");

                    // 按声明类型分组，看哪个类型贡献最多 patch 点（决定分帧批大小）
                    Dictionary<string, int> byType = new Dictionary<string, int>(StringComparer.Ordinal);
                    for (int i = 0; i < patched.Count; i++)
                    {
                        string tn = patched[i].DeclaringType == null ? "?" : patched[i].DeclaringType.Name;
                        int c;
                        byType.TryGetValue(tn, out c);
                        byType[tn] = c + 1;
                    }
                    List<KeyValuePair<string, int>> kv = new List<KeyValuePair<string, int>>(byType);
                    kv.Sort(delegate(KeyValuePair<string, int> a, KeyValuePair<string, int> b)
                    {
                        return b.Value.CompareTo(a.Value);
                    });
                    W("  --- patch points per declaring type (top 15) ---");
                    for (int i = 0; i < kv.Count && i < 15; i++)
                        W("    " + Pad(kv[i].Key, 28) + kv[i].Value);
                    W("  distinct declaring types       = " + kv.Count);

                    // 分帧可行性：如果按 ms 预算切批，需要几帧？
                    double budget = 4.0;
                    W("  --- amortization math ---");
                    W("    at a " + F(budget) + " ms/frame budget, installing "
                      + patched.Count + " patches takes "
                      + Math.Ceiling(total / budget) + " frames ("
                      + F(Math.Ceiling(total / budget) / 60.0 * 1000.0) + " ms wall at 60fps)");

                    try { h.UnpatchSelf(); } catch { }
                }
            }
            catch (Exception e) { W("  load/reflect failed: " + e.GetType().Name + ": " + e.Message); }
        }
        W("");

        W("PROBE6 DONE -- no pass/fail gate: this is a measurement, not an assertion.");
    }

    private static double TimeOne(string name)
    {
        Stopwatch s = Stopwatch.StartNew();
        AccessTools.TypeByName(name);
        s.Stop();
        return s.Elapsed.TotalMilliseconds;
    }

    private delegate void Action0();

    private static double TimeBest(int rounds, Action0 a)
    {
        double best = double.MaxValue;
        for (int r = 0; r < rounds; r++)
        {
            Stopwatch s = Stopwatch.StartNew();
            a();
            s.Stop();
            if (s.Elapsed.TotalMilliseconds < best) best = s.Elapsed.TotalMilliseconds;
        }
        return best;
    }

    private static string Pad(string s, int n)
    {
        return s.Length >= n ? s : s + new string(' ', n - s.Length);
    }

    private static string F(double d) { return d.ToString("F2", CultureInfo.InvariantCulture); }
}
