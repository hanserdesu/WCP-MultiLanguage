// WCP mirror/identity offline cost benchmark (ASCII only on purpose).
// Compile: run.cmd  (csc 4.0.30319, .NET Framework 4.x -> same BCL family as Unity Mono)
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Security.Cryptography;
using System.Text;

internal static class Bench
{
    private const string SourceFr = @"C:\Users\hanserdesu\AppData\LocalLow\WCP\packs\fr\audio\word";
    private const string SourceJa = @"C:\Users\hanserdesu\AppData\LocalLow\WCP\packs\ja\audio\word";
    private const string Target = @"C:\Users\hanserdesu\AppData\LocalLow\WCP\vocabulary";
    private const string BookFile = @"C:\Users\hanserdesu\AppData\LocalLow\WCP\wcp\MyBook.es3";
    private static readonly StringBuilder Report = new StringBuilder();

    private static void Say(string s)
    {
        Console.WriteLine(s);
        Report.AppendLine(s);
    }

    private static void Main()
    {
        Say("== WCP mirror/identity offline benchmark ==");
        Say("clr=" + Environment.Version + " 64bit=" + (IntPtr.Size == 8));

        Warmup();

        // A. How expensive is one pass over a directory when we only need name+size?
        BenchEnumerate("A1 src fr  EnumerateFiles(*.mp3)+Length", SourceFr, "*.mp3", 0, 3);
        BenchEnumerate("A2 src ja  EnumerateFiles(*.mp3)+Length", SourceJa, "*.mp3", 0, 3);
        BenchEnumerate("A3 target  EnumerateFiles()+Length", Target, null, 0, 3);
        // Same iteration but reading Length via a fresh FileInfo => forces a stat if
        // the enumerator does NOT carry the size. Difference vs A1/A3 is the tell.
        BenchEnumerate("A4 target  EnumerateFiles()+new FileInfo().Length", Target, null, 1, 1);
        // 关键前提：「已就位」判据要用 (大小 + mtime)。两者都能从枚举免费带回吗？
        // A5 读 LastWriteTimeUtc；若与 A3 同量级 = 免费（来自 WIN32_FIND_DATA）；
        // A6 用新 FileInfo 取 mtime 走 stat，作为慢的对照。
        BenchEnumerate("A5 target  EnumerateFiles()+LastWriteTimeUtc", Target, null, 2, 3);
        BenchEnumerate("A6 target  EnumerateFiles()+new FileInfo().LastWriteTimeUtc", Target, null, 3, 1);
        BenchRoundTripTime(200);
        // B. Index build: Dictionary<string,long>(OrdinalIgnoreCase) over those entries.
        BenchIndex("B1 src fr  index build", SourceFr, "*.mp3", 3);
        BenchIndex("B2 target  index build", Target, null, 3);
        BenchIndex("B3 src ja  index build", SourceJa, "*.mp3", 3);

        // C. Copy cost (single file + batch) - use a temp dir.
        BenchCopy(200);

        // D. FingerprintOf() replica: this is what runs every second in Host.Evaluate.
        string[] words = LoadWords(SourceFr);
        Say("D0 word count = " + words.Length);
        BenchFingerprint("D1 FingerprintOf (8116 words)", words, 3);

        // E. Raw read of MyBook.es3 - lower bound for one ES3.Load<string[]> of a slot.
        BenchReadFile("E1 read MyBook.es3 (2.1MB)", BookFile, 3);

        // F. JSON-ish store write: 900KB text write.
        BenchWriteFile("F1 write 900KB text", Path.Combine(Path.GetTempPath(), "wcp_bench.json"), 900 * 1024, 3);

        string outPath = Path.Combine(Path.GetDirectoryName(System.Reflection.Assembly.GetExecutingAssembly().Location),
                                      "bench_report.txt");
        File.WriteAllText(outPath, Report.ToString(), new UTF8Encoding(false));
        Say("report -> " + outPath);
    }

    private static void Warmup()
    {
        try
        {
            long sink = 0;
            DirectoryInfo di = new DirectoryInfo(SourceFr);
            foreach (FileInfo fi in di.EnumerateFiles("*.mp3")) sink += fi.Length;
            string[] a = Directory.GetFiles(SourceFr, "*.mp3");
            sink += a.Length;
            if (sink == long.MinValue) Console.WriteLine("impossible");
        }
        catch (Exception e) { Say("warmup failed: " + e.Message); }
    }

    // mode: 0=Length(枚举带回) 1=Length(new FileInfo, 走 stat) 2=mtime(枚举带回) 3=mtime(new FileInfo)
    private static void BenchEnumerate(string label, string dir, string pattern, int mode, int iters)
    {
        for (int it = 0; it < iters; it++)
        {
            Stopwatch sw = Stopwatch.StartNew();
            long n = 0, sum = 0;
            DirectoryInfo di = new DirectoryInfo(dir);
            IEnumerable<FileInfo> seq = pattern == null ? di.EnumerateFiles() : di.EnumerateFiles(pattern);
            foreach (FileInfo fi in seq)
            {
                switch (mode)
                {
                    case 0: sum += fi.Length; break;
                    case 1: sum += new FileInfo(fi.FullName).Length; break;
                    case 2: sum += fi.LastWriteTimeUtc.Ticks; break;
                    default: sum += new FileInfo(fi.FullName).LastWriteTimeUtc.Ticks; break;
                }
                n++;
            }
            sw.Stop();
            Say(label + " : " + sw.Elapsed.TotalMilliseconds.ToString("F1") + " ms  n=" + n +
                "  us/item=" + (n == 0 ? "0" : (sw.Elapsed.TotalMilliseconds * 1000.0 / n).ToString("F2")) +
                "  sink=" + sum);
        }
    }

    // TryCopy 计划在复制后把源文件的 mtime 写到目标上（让"大小+mtime"判据成立），
    // 这里量一次 SetLastWriteTimeUtc 的单价。
    private static void BenchRoundTripTime(int files)
    {
        string dir = Path.Combine(Path.GetTempPath(), "wcp_bench_mtime");
        try
        {
            if (Directory.Exists(dir)) Directory.Delete(dir, true);
            Directory.CreateDirectory(dir);
            for (int i = 0; i < files; i++)
                File.WriteAllText(Path.Combine(dir, "f" + i + ".txt"), "x");
            Stopwatch sw = Stopwatch.StartNew();
            for (int i = 0; i < files; i++)
            {
                string p = Path.Combine(dir, "f" + i + ".txt");
                DateTime src = new FileInfo(p).LastWriteTimeUtc;
                File.SetLastWriteTimeUtc(p, src.AddSeconds(-1));
            }
            sw.Stop();
            Say("A7 File.SetLastWriteTimeUtc x" + files + " : " +
                sw.Elapsed.TotalMilliseconds.ToString("F1") + " ms  us/file=" +
                (sw.Elapsed.TotalMilliseconds * 1000.0 / files).ToString("F1"));
        }
        catch (Exception e) { Say("mtime bench failed: " + e.Message); }
    }

    private static void BenchIndex(string label, string dir, string pattern, int iters)
    {
        for (int it = 0; it < iters; it++)
        {
            Stopwatch sw = Stopwatch.StartNew();
            Dictionary<string, long> index = new Dictionary<string, long>(StringComparer.OrdinalIgnoreCase);
            DirectoryInfo di = new DirectoryInfo(dir);
            IEnumerable<FileInfo> seq = pattern == null ? di.EnumerateFiles() : di.EnumerateFiles(pattern);
            foreach (FileInfo fi in seq) index[fi.Name] = fi.Length;
            sw.Stop();
            Say(label + " : " + sw.Elapsed.TotalMilliseconds.ToString("F1") + " ms  n=" + index.Count +
                "  us/item=" + (index.Count == 0 ? "0" : (sw.Elapsed.TotalMilliseconds * 1000.0 / index.Count).ToString("F2")));
        }
    }

    private static void BenchCopy(int files)
    {
        string src = Path.Combine(Path.GetTempPath(), "wcp_bench_src");
        string dst = Path.Combine(Path.GetTempPath(), "wcp_bench_dst");
        try
        {
            if (Directory.Exists(src)) Directory.Delete(src, true);
            if (Directory.Exists(dst)) Directory.Delete(dst, true);
            Directory.CreateDirectory(src);
            Directory.CreateDirectory(dst);
            byte[] blob = new byte[10 * 1024];
            (new Random(1234)).NextBytes(blob);
            for (int i = 0; i < files; i++)
                File.WriteAllBytes(Path.Combine(src, "w" + i + ".mp3"), blob);

            Stopwatch sw = Stopwatch.StartNew();
            for (int i = 0; i < files; i++)
            {
                string s = Path.Combine(src, "w" + i + ".mp3");
                string d = Path.Combine(dst, "w" + i + ".mp3");
                File.Copy(s, d, true);
            }
            sw.Stop();
            Say("C1 File.Copy x" + files + " (10KB) : " + sw.Elapsed.TotalMilliseconds.ToString("F1") +
                " ms  us/file=" + (sw.Elapsed.TotalMilliseconds * 1000.0 / files).ToString("F1"));

            // Overwrite existing (mirror's steady path).
            sw = Stopwatch.StartNew();
            for (int i = 0; i < files; i++)
            {
                string s = Path.Combine(src, "w" + i + ".mp3");
                string d = Path.Combine(dst, "w" + i + ".mp3");
                File.Copy(s, d, true);
            }
            sw.Stop();
            Say("C2 File.Copy x" + files + " overwrite : " + sw.Elapsed.TotalMilliseconds.ToString("F1") +
                " ms  us/file=" + (sw.Elapsed.TotalMilliseconds * 1000.0 / files).ToString("F1"));
        }
        catch (Exception e) { Say("copy bench failed: " + e.Message); }
    }

    private static string[] LoadWords(string dir)
    {
        List<string> list = new List<string>();
        try
        {
            foreach (string f in Directory.GetFiles(dir, "*.mp3"))
                list.Add(Path.GetFileNameWithoutExtension(f));
        }
        catch (Exception e) { Say("LoadWords failed: " + e.Message); }
        return list.ToArray();
    }

    // Verbatim replica of BookRegistry.FingerprintOf (Core/Manifest.cs).
    private static string FingerprintOf(IList<string> words)
    {
        if (words == null) return null;
        List<string> normalized = new List<string>(words.Count);
        for (int i = 0; i < words.Count; i++)
        {
            string word = words[i];
            if (word == null) return null;
            normalized.Add(word.Trim().Normalize(NormalizationForm.FormC));
        }
        normalized.Sort(StringComparer.Ordinal);
        StringBuilder payload = new StringBuilder();
        for (int i = 0; i < normalized.Count; i++)
            payload.Append(normalized[i]).Append('\n');
        byte[] bytes = Encoding.UTF8.GetBytes(payload.ToString());
        using (SHA256 sha = SHA256.Create())
        {
            byte[] digest = sha.ComputeHash(bytes);
            StringBuilder hex = new StringBuilder(digest.Length * 2);
            for (int i = 0; i < digest.Length; i++) hex.Append(digest[i].ToString("x2"));
            return hex.ToString();
        }
    }

    private static void BenchFingerprint(string label, IList<string> words, int iters)
    {
        // Split into stages so we know which one to attack.
        for (int it = 0; it < iters; it++)
        {
            Stopwatch sw = Stopwatch.StartNew();
            List<string> normalized = new List<string>(words.Count);
            for (int i = 0; i < words.Count; i++)
                normalized.Add(words[i].Trim().Normalize(NormalizationForm.FormC));
            sw.Stop();
            double norm = sw.Elapsed.TotalMilliseconds;

            sw = Stopwatch.StartNew();
            normalized.Sort(StringComparer.Ordinal);
            sw.Stop();
            double sort = sw.Elapsed.TotalMilliseconds;

            sw = Stopwatch.StartNew();
            StringBuilder payload = new StringBuilder();
            for (int i = 0; i < normalized.Count; i++) payload.Append(normalized[i]).Append('\n');
            string s = payload.ToString();
            byte[] bytes = Encoding.UTF8.GetBytes(s);
            using (SHA256 sha = SHA256.Create()) sha.ComputeHash(bytes);
            sw.Stop();
            double hash = sw.Elapsed.TotalMilliseconds;

            sw = Stopwatch.StartNew();
            string fp = FingerprintOf(words);
            sw.Stop();

            Say(label + " : total=" + sw.Elapsed.TotalMilliseconds.ToString("F1") +
                " ms (Normalize=" + norm.ToString("F1") + " Sort=" + sort.ToString("F1") +
                " payload+sha=" + hash.ToString("F1") + ") fp=" + (fp == null ? "null" : fp.Substring(0, 12)));
        }
    }

    private static void BenchReadFile(string label, string path, int iters)
    {
        for (int it = 0; it < iters; it++)
        {
            Stopwatch sw = Stopwatch.StartNew();
            byte[] data = File.ReadAllBytes(path);
            sw.Stop();
            Say(label + " : " + sw.Elapsed.TotalMilliseconds.ToString("F1") + " ms  bytes=" + data.Length);
        }
    }

    private static void BenchWriteFile(string label, string path, int bytes, int iters)
    {
        char[] blob = new char[bytes];
        for (int i = 0; i < blob.Length; i++) blob[i] = (char)('a' + (i % 26));
        string s = new string(blob);
        for (int it = 0; it < iters; it++)
        {
            Stopwatch sw = Stopwatch.StartNew();
            File.WriteAllText(path, s, new UTF8Encoding(false));
            sw.Stop();
            Say(label + " : " + sw.Elapsed.TotalMilliseconds.ToString("F1") + " ms");
        }
        try { File.Delete(path); } catch { }
    }
}
