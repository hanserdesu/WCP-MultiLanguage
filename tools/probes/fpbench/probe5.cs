// probe5 -- 身份指纹 FingerprintOf 的成本拆解与等价优化验证
//
// 背景：第九轮修掉 ES3 批量写之后，切书帧的大头变成 HOST 的 `身份:Evaluate`。
// 实测 line 694: 身份:Evaluate x1=2712.2ms（ru 切书帧），line 664: 239.4ms（ja 切书帧）。
// Evaluate 内部唯一量级够得着的是 _registry.Match(words) 与 _registry.Match(slotWords)，
// 两者最终都落到 BookRegistry.FingerprintOf —— 对 8451 个词做
// Trim + Unicode Normalize(FormC) + Ordinal 排序 + 拼接 + UTF8 + SHA256。
//
// 本探针回答四个问题，全部要求实测数字：
//   1) ru_pron.tsv 第一列的词表，算出的指纹是否等于 manifest 的 fingerprint_sha256？
//      （不相等 = 我拿到的不是权威词表，后面所有计时都不作数）
//   2) 真函数 FingerprintOf 在 8451 词上耗时多少？与实机 239ms/2712ms 是否同量级？
//   3) 分段拆解：normalize / sort / 拼接+ToString / UTF8 / SHA256 各占多少？
//   4) 两个候选优化是否输出逐字节相同的 hash，分别快多少：
//      优化A: word.IsNormalized(FormC) 为真时直接复用原串，跳过 Normalize 的分配
//      优化B: 先算总字节数，一次分配 byte[]，逐词 GetBytes 写入（消除 100KB StringBuilder
//             + payload.ToString() 那一份 LOH 字符串）
//
// Usage: probe5.exe <outFile> <tsv> <wcpDll> <expectedFingerprint> <searchDir> [rounds]
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;

internal static class Probe5
{
    private static readonly List<string> Out = new List<string>();

    private static void W(string s)
    {
        Out.Add(s);
        Console.WriteLine(s);
    }

    private static int Main(string[] args)
    {
        string outFile = args.Length > 0 ? args[0] : "probe5_out.txt";
        string tsv = args.Length > 1 ? args[1] : null;
        string wcpDll = args.Length > 2 ? args[2] : null;
        string expected = args.Length > 3 ? args[3] : null;
        string searchDir = args.Length > 4 ? args[4] : null;
        int rounds = args.Length > 5 ? int.Parse(args[5]) : 5;

        try { Run(outFile, tsv, wcpDll, expected, searchDir, rounds); }
        catch (Exception e) { W("FATAL " + e.GetType().Name + ": " + e.Message); W(e.StackTrace); }

        try { File.WriteAllLines(outFile, Out.ToArray(), new UTF8Encoding(false)); } catch { }
        return 0;
    }

    private static void Run(string outFile, string tsv, string wcpDll, string expected,
                            string searchDir, int rounds)
    {
        W("PROBE5 -- FingerprintOf cost breakdown + equivalence of two optimizations");
        W("");

        // ── 0) 解析依赖，让 LoadFrom(WcpHost.dll) 能解析 Harmony / netstandard ──
        if (!string.IsNullOrEmpty(searchDir))
        {
            // searchDir 可以是分号分隔的多个目录（BepInEx\core;wcp_Data\Managed）
            string[] dirs = searchDir.Split(';');
            AppDomain.CurrentDomain.AssemblyResolve += delegate(object s, ResolveEventArgs e)
            {
                try
                {
                    string simple = new AssemblyName(e.Name).Name;
                    for (int i = 0; i < dirs.Length; i++)
                    {
                        string d = dirs[i].Trim();
                        if (d.Length == 0) continue;
                        string p = Path.Combine(d, simple + ".dll");
                        if (File.Exists(p)) return Assembly.LoadFrom(p);
                    }
                }
                catch { }
                return null;
            };
        }

        // ── 1) 读词表 ──
        W("--- word source ---");
        if (tsv == null || !File.Exists(tsv)) { W("FATAL tsv missing: " + tsv); return; }
        string[] lines = File.ReadAllLines(tsv, new UTF8Encoding(false));
        List<string> words = new List<string>();
        int dup = 0;
        HashSet<string> seen = new HashSet<string>(StringComparer.Ordinal);
        for (int i = 0; i < lines.Length; i++)
        {
            string line = lines[i];
            if (line.Length == 0) continue;
            int t = line.IndexOf('\t');
            string w = t < 0 ? line : line.Substring(0, t);
            if (w.Length == 0) continue;
            if (!seen.Add(w)) dup++;
            words.Add(w);
        }
        W("  tsv            = " + tsv);
        W("  lines          = " + lines.Length);
        W("  words (raw)    = " + words.Count);
        W("  duplicate words= " + dup + "   (unique=" + seen.Count + ")");
        W("");

        // ── 2) 反射调用仓库里真的 FingerprintOf ──
        W("--- reflection into shipped WcpHost.dll ---");
        MethodInfo real = null;
        if (wcpDll != null && File.Exists(wcpDll))
        {
            W("  dll = " + wcpDll);
            W("  sha256 = " + Sha256File(wcpDll));
            try
            {
                Assembly asm = Assembly.LoadFrom(wcpDll);
                Type t = asm.GetType("WcpHost.BookRegistry");
                if (t == null) W("  BookRegistry type NOT FOUND");
                else
                {
                    real = t.GetMethod("FingerprintOf",
                        BindingFlags.NonPublic | BindingFlags.Static);
                    W("  BookRegistry.FingerprintOf = " + (real == null ? "NULL" : real.ToString()));
                }
            }
            catch (Exception e) { W("  LoadFrom/GetType THREW " + e.GetType().Name + ": " + e.Message); }
        }
        else W("  dll missing: " + wcpDll);
        W("");

        // ── 3) 真函数指纹 vs manifest ──
        W("--- truth check: does this word list hash to the manifest fingerprint? ---");
        string hashReal = null;
        if (real != null)
        {
            try
            {
                object r = real.Invoke(null, new object[] { words });
                hashReal = r as string;
            }
            catch (Exception e) { W("  Invoke THREW " + e.GetType().Name + ": " + Msg(e)); }
        }
        if (hashReal == null) { W("  could not call real FingerprintOf -> abort measurement"); return; }
        W("  FingerprintOf(words) = " + hashReal);
        W("  manifest expects     = " + expected);
        bool truth = expected != null && expected == hashReal;
        W("  VERDICT: " + (truth ? "MATCH -- word list is the authoritative one"
                                  : "MISMATCH -- this word list is NOT what the manifest was built from"));
        W("");

        // 样本副本（复制版需要独立 List，避免被测函数改变其内部状态）
        List<string> sample = new List<string>(words);

        // ── 4) 真函数计时 ──
        W("--- timing: real FingerprintOf ---");
        double msReal = TimeBest(rounds, delegate() { real.Invoke(null, new object[] { sample }); });
        W("  best of " + rounds + " = " + F(msReal) + " ms   (" + words.Count + " words, avg "
          + F(msReal / words.Count * 1000.0) + " us/word)");
        W("");

        // ── 5) 分段拆解（复制版，先证明与真函数等价） ──
        W("--- stage breakdown (copy of the algorithm; must hash to the same value) ---");
        StageMs stg;
        string hashCopy = CopyCurrent(sample, out stg);
        W("  copy hash = " + hashCopy);
        W("  copy == real : " + (hashCopy == hashReal));
        if (hashCopy != hashReal) { W("  COPY DIVERGED -> breakdown invalid"); return; }
        W("  normalize  = " + F(stg.Normalize) + " ms");
        W("  sort       = " + F(stg.Sort) + " ms");
        W("  append+str = " + F(stg.Append) + " ms   (StringBuilder " + (stg.PayloadChars * 2 / 1024) + " KB -> ToString)");
        W("  utf8       = " + F(stg.Utf8) + " ms   (" + (stg.Utf8Bytes / 1024) + " KB)");
        W("  sha256     = " + F(stg.Sha) + " ms");
        W("  sum        = " + F(stg.Total) + " ms");
        W("");

        // ── 6) 两个优化 ──
        W("--- optimization A: IsNormalized short-circuit (output must be identical) ---");
        double msA = TimeBest(rounds, delegate() { OptA(sample); });
        string hashA = OptA(sample);
        W("  hash = " + hashA);
        W("  identical to real : " + (hashA == hashReal));
        W("  best of " + rounds + " = " + F(msA) + " ms   speedup vs real = "
          + F(msReal / Math.Max(0.001, msA)) + "x");
        W("");

        W("--- optimization B: single byte[] + per-word GetBytes (no 100KB string) ---");
        double msB = TimeBest(rounds, delegate() { OptB(sample); });
        string hashB = OptB(sample);
        W("  hash = " + hashB);
        W("  identical to real : " + (hashB == hashReal));
        W("  best of " + rounds + " = " + F(msB) + " ms   speedup vs real = "
          + F(msReal / Math.Max(0.001, msB)) + "x");
        W("");

        W("--- optimization A+B ---");
        double msAB = TimeBest(rounds, delegate() { OptAB(sample); });
        string hashAB = OptAB(sample);
        W("  hash = " + hashAB);
        W("  identical to real : " + (hashAB == hashReal));
        W("  best of " + rounds + " = " + F(msAB) + " ms   speedup vs real = "
          + F(msReal / Math.Max(0.001, msAB)) + "x");
        W("");

        // ── 7) normalize 短路到底省多少：先看有多少词真的需要规范化 ──
        W("--- how many words actually need Normalize(FormC)? ---");
        int need = 0, already = 0;
        for (int i = 0; i < sample.Count; i++)
        {
            string w = sample[i];
            if (w.Trim().IsNormalized(NormalizationForm.FormC)) already++;
            else need++;
        }
        W("  already FormC = " + already + " / " + sample.Count);
        W("  need Normalize= " + need + " / " + sample.Count);
        W("");

        // ── 8) 结论 ──
        bool gateOk = truth && hashA == hashReal && hashB == hashReal && hashAB == hashReal;
        W("PROBE5 GATE: " + (gateOk ? "PASS" : "FAIL"));
        W("  (truth=" + truth + " A=" + (hashA == hashReal) + " B=" + (hashB == hashReal)
          + " AB=" + (hashAB == hashReal) + ")");
    }

    // ── 真算法逐段计时 ──────────────────────────────────────────────
    private sealed class StageMs
    {
        internal double Normalize, Sort, Append, Utf8, Sha, Total;
        internal long PayloadChars, Utf8Bytes;
    }

    private static string CopyCurrent(IList<string> words, out StageMs stg)
    {
        stg = new StageMs();
        Stopwatch sw = Stopwatch.StartNew();

        List<string> normalized = new List<string>(words.Count);
        for (int i = 0; i < words.Count; i++)
        {
            string word = words[i];
            if (word == null) return null;
            normalized.Add(word.Trim().Normalize(NormalizationForm.FormC));
        }
        stg.Normalize = sw.Elapsed.TotalMilliseconds; sw.Restart();

        normalized.Sort(StringComparer.Ordinal);
        stg.Sort = sw.Elapsed.TotalMilliseconds; sw.Restart();

        StringBuilder payload = new StringBuilder();
        for (int i = 0; i < normalized.Count; i++)
            payload.Append(normalized[i]).Append('\n');
        string joined = payload.ToString();
        stg.PayloadChars = joined.Length;
        stg.Append = sw.Elapsed.TotalMilliseconds; sw.Restart();

        byte[] bytes = Encoding.UTF8.GetBytes(joined);
        stg.Utf8Bytes = bytes.Length;
        stg.Utf8 = sw.Elapsed.TotalMilliseconds; sw.Restart();

        using (SHA256 sha = SHA256.Create())
        {
            byte[] digest = sha.ComputeHash(bytes);
            StringBuilder hex = new StringBuilder(digest.Length * 2);
            for (int i = 0; i < digest.Length; i++) hex.Append(digest[i].ToString("x2"));
            string result = hex.ToString();
            stg.Sha = sw.Elapsed.TotalMilliseconds; sw.Stop();
            stg.Total = stg.Normalize + stg.Sort + stg.Append + stg.Utf8 + stg.Sha;
            return result;
        }
    }

    // ── 优化A：IsNormalized 短路 ─────────────────────────────────────
    private static string OptA(IList<string> words)
    {
        List<string> normalized = new List<string>(words.Count);
        for (int i = 0; i < words.Count; i++)
        {
            string word = words[i];
            if (word == null) return null;
            string trimmed = word.Trim();
            // IsNormalized 为真时 Normalize 返回内容相同的串 —— 直接复用可省一次分配。
            // 这是纯分配优化，不改变字节序。
            normalized.Add(trimmed.IsNormalized(NormalizationForm.FormC)
                ? trimmed
                : trimmed.Normalize(NormalizationForm.FormC));
        }
        normalized.Sort(StringComparer.Ordinal);
        StringBuilder payload = new StringBuilder();
        for (int i = 0; i < normalized.Count; i++)
            payload.Append(normalized[i]).Append('\n');
        byte[] bytes = Encoding.UTF8.GetBytes(payload.ToString());
        return Hex(SHA256.Create().ComputeHash(bytes));
    }

    // ── 优化B：一次 byte[]，逐词 GetBytes，消除 100KB 中间字符串 ──
    private static string OptB(IList<string> words)
    {
        List<string> normalized = new List<string>(words.Count);
        for (int i = 0; i < words.Count; i++)
        {
            string word = words[i];
            if (word == null) return null;
            normalized.Add(word.Trim().Normalize(NormalizationForm.FormC));
        }
        normalized.Sort(StringComparer.Ordinal);
        return HashJoined(normalized);
    }

    // ── 优化A+B ────────────────────────────────────────────────────
    private static string OptAB(IList<string> words)
    {
        List<string> normalized = new List<string>(words.Count);
        for (int i = 0; i < words.Count; i++)
        {
            string word = words[i];
            if (word == null) return null;
            string trimmed = word.Trim();
            normalized.Add(trimmed.IsNormalized(NormalizationForm.FormC)
                ? trimmed
                : trimmed.Normalize(NormalizationForm.FormC));
        }
        normalized.Sort(StringComparer.Ordinal);
        return HashJoined(normalized);
    }

    // 与真算法等价的哈希：拼接顺序和分隔符完全相同，只是不再先造一个大字符串。
    private static string HashJoined(List<string> normalized)
    {
        Encoding enc = Encoding.UTF8;
        int total = 0;
        for (int i = 0; i < normalized.Count; i++)
            total += enc.GetByteCount(normalized[i]) + 1;   // + '\n'
        byte[] buf = new byte[total];
        int off = 0;
        for (int i = 0; i < normalized.Count; i++)
        {
            string s = normalized[i];
            off += enc.GetBytes(s, 0, s.Length, buf, off);
            buf[off++] = (byte)'\n';
        }
        using (SHA256 sha = SHA256.Create())
            return Hex(sha.ComputeHash(buf));
    }

    private static string Hex(byte[] digest)
    {
        StringBuilder hex = new StringBuilder(digest.Length * 2);
        for (int i = 0; i < digest.Length; i++) hex.Append(digest[i].ToString("x2"));
        return hex.ToString();
    }

    // ── 小工具 ─────────────────────────────────────────────────────
    private delegate void Action0();

    private static double TimeBest(int rounds, Action0 a)
    {
        double best = double.MaxValue;
        for (int r = 0; r < rounds; r++)
        {
            Stopwatch sw = Stopwatch.StartNew();
            a();
            sw.Stop();
            if (sw.Elapsed.TotalMilliseconds < best) best = sw.Elapsed.TotalMilliseconds;
        }
        return best;
    }

    private static string Sha256File(string path)
    {
        try
        {
            using (FileStream fs = File.OpenRead(path))
            using (SHA256 sha = SHA256.Create())
                return Hex(sha.ComputeHash(fs));
        }
        catch (Exception e) { return "ERR " + e.Message; }
    }

    private static string Msg(Exception e)
    {
        Exception inner = e is TargetInvocationException ? e.InnerException : e;
        return inner == null ? e.Message : inner.GetType().Name + ": " + inner.Message;
    }

    private static string F(double d) { return d.ToString("F2", CultureInfo.InvariantCulture); }
}
