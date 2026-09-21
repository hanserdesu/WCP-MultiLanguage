// WCP round-7 identity/UI-scan cost benchmark (ASCII only on purpose).
//
// Question this answers BEFORE any code change:
//   "每秒一次的全量身份/UI 扫描"里，钱到底花在哪一步？
//   候选：(a) SlotOwnership 重解析 1.22MB store + 12 行指纹；
//         (b) GameAdapter.SlotWords 每次 ES3 全文档解析（2.1MB）；
//         (c) FingerprintOf 本身；
//         (d) 全场景 FindObjectsOfTypeAll（无法离线量，另计）。
//
// Method: use the project's OWN Json.cs parser + a byte-exact copy of
// BookRegistry.FingerprintOf, against the REAL save files dumped from the
// machine that produced the 26179ms/24.7s window. Same BCL generation
// (.NET Framework 4.x) as Unity Mono.
//
// Compile: run2.cmd  (csc.exe is sandbox-blocked when invoked directly)
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using WcpHost;

internal static class Bench2
{
    private const string StoreJson = @"C:\Users\hanserdesu\AppData\LocalLow\WCP\wcp\WcpCustomSlots.json";
    private const string BookFile = @"C:\Users\hanserdesu\AppData\LocalLow\WCP\wcp\MyBook.es3";

    private static readonly StringBuilder Report = new StringBuilder();

    private static void Say(string s)
    {
        Console.WriteLine(s);
        Report.AppendLine(s);
    }

    private static void Main()
    {
        Say("== WCP round-7 identity/UI-scan benchmark ==");
        Say("clr=" + Environment.Version + " 64bit=" + (IntPtr.Size == 8));

        // ---------------------------------------------------------------
        // PART A — SlotOwnership.RefreshCache on a cache miss
        //   exactly what runs when the 20-slot store mtime changes
        // ---------------------------------------------------------------
        byte[] storeBytes = File.ReadAllBytes(StoreJson);
        Say("A0 store bytes = " + storeBytes.Length);

        double read = Median(3, delegate
        {
            string s = File.ReadAllText(StoreJson, Encoding.UTF8);
            return s.Length;
        });
        Say(string.Format("A1 File.ReadAllText(store 1.22MB) = {0:F1} ms", read));

        string storeText = File.ReadAllText(StoreJson, Encoding.UTF8);
        double parse = Median(3, delegate
        {
            object o = Json.Parse(storeText);
            return o == null ? 0 : 1;
        });
        Say(string.Format("A2 Json.Parse(store 908K chars)  = {0:F1} ms", parse));

        // pull the real words of every registered row (same filter SlotOwnership uses)
        object parsed = Json.Parse(storeText);
        Dictionary<string, object> root = (Dictionary<string, object>)parsed;
        List<object> rows = (List<object>)root["slots"];
        List<List<string>> served = new List<List<string>>();
        int managedRows = 0;
        for (int i = 0; i < rows.Count; i++)
        {
            Dictionary<string, object> row = rows[i] as Dictionary<string, object>;
            bool managed = Json.Bool(row, "managed", false);
            int nativeSlot = Json.Int(row, "nativeSlot", 0);
            if (!managed && nativeSlot <= 0) continue;
            List<string> words = Json.StrList(row, "words");
            if (words == null || words.Count < 5) continue;
            served.Add(words);
            managedRows++;
        }
        Say("A3 store rows with words = " + managedRows +
            "  (word counts: " + Counts(served) + ")");

        double fpRows = Median(3, delegate
        {
            long sink = 0;
            for (int i = 0; i < served.Count; i++)
                sink += FingerprintOf(served[i]).Length;
            return (int)sink;
        });
        Say(string.Format("A4 {0} x FingerprintOf(store rows) = {1:F1} ms  ({2:F2} ms/row)",
            served.Count, fpRows, fpRows / served.Count));
        Say(string.Format("A5 == RefreshCache total (miss)  = {0:F1} ms", read + parse + fpRows));

        // ---------------------------------------------------------------
        // PART B — one GameAdapter.SlotWords(slot): ES3 must parse the WHOLE
        //   MyBook.es3 document to reach one key. Lower bound = read + parse.
        // ---------------------------------------------------------------
        byte[] bookBytes = File.ReadAllBytes(BookFile);
        Say("B0 MyBook.es3 bytes = " + bookBytes.Length + " (ES3 = whole-file JSON)");

        double bread = Median(3, delegate
        {
            byte[] b = File.ReadAllBytes(BookFile);
            return b.Length;
        });
        Say(string.Format("B1 File.ReadAllBytes(MyBook.es3 2.1MB) = {0:F1} ms", bread));

        string bookText = File.ReadAllText(BookFile, Encoding.UTF8);
        Say("B2 book text chars = " + bookText.Length);

        double bparse = Median(3, delegate
        {
            object o = Json.Parse(bookText);
            return o == null ? 0 : 1;
        });
        Say(string.Format("B3 Json.Parse(MyBook.es3 {0}K chars)  = {1:F1} ms", bookText.Length / 1000, bparse));
        Say(string.Format("B4 == one SlotWords(slot) lower bound = {0:F1} ms  (read+parse; ES3 adds reflection + boxing)",
            bread + bparse));
        Say(string.Format("B5   => 32 calls (4 slots x 8 rows, all cache misses) = {0:F0} ms",
            32 * (bread + bparse)));

        // real word lists out of MyBook.es3, to price FingerprintOf at true size
        object book = Json.Parse(bookText);
        Dictionary<string, object> bk = (Dictionary<string, object>)book;
        List<string> sizes = new List<string>();
        List<List<string>> lists = new List<List<string>>();
        for (int i = 1; i <= 8; i++)
        {
            object slotObj;
            if (!bk.TryGetValue("SelfBookList" + i, out slotObj)) continue;
            Dictionary<string, object> holder = slotObj as Dictionary<string, object>;
            if (holder == null) continue;
            List<object> vals = holder["value"] as List<object>;
            if (vals == null) continue;
            List<string> wl = new List<string>(vals.Count);
            for (int k = 0; k < vals.Count; k++) wl.Add(vals[k] as string);
            lists.Add(wl);
            sizes.Add("SelfBookList" + i + "=" + wl.Count);
        }
        Say("B6 real slot lists: " + Join(sizes));

        // ---------------------------------------------------------------
        // PART C — FingerprintOf at real sizes
        // ---------------------------------------------------------------
        for (int i = 0; i < lists.Count; i++)
        {
            List<string> wl = lists[i];
            double ms = Median(3, delegate { return FingerprintOf(wl).Length; });
            Say(string.Format("C{0} FingerprintOf({1} words) = {2:F2} ms", i + 1, wl.Count, ms));
        }

        // ---------------------------------------------------------------
        // PART D — the SlotByDisplayName storm, as the code actually reads today.
        //   per row: for slot=1..NativeSlotCount -> ManifestForSlot(slot)
        //   ManifestForSlot = SlotWords(slot) [cache thrash => full ES3] + 2 x Match
        //   Match(N words) = 1 x FingerprintOf once word-count prefilter passes
        // ---------------------------------------------------------------
        int nativeSlots = lists.Count;
        int uiRows = 5;   // native chooser rows on the book-select page (log: 4 custom + native)
        double perRow = 0;
        for (int s = 0; s < nativeSlots; s++)
            perRow += (bread + bparse) + 2 * FpMs(lists[s]);
        Say(string.Format("D1 per row (loop {0} slots) = {1:F0} ms", nativeSlots, perRow));
        Say(string.Format("D2 x {0} rows = {1:F0} ms per scan", uiRows, perRow * uiRows));
        Say(string.Format("D3 scans per 10s window (cache wiped every 10s) = {0:F1} s of main thread",
            perRow * uiRows / 1000.0));

        string outPath = Path.Combine(Path.GetDirectoryName(
            System.Reflection.Assembly.GetExecutingAssembly().Location), "bench2_report.txt");
        File.WriteAllText(outPath, Report.ToString(), new UTF8Encoding(false));
        Say("report -> " + outPath);
    }

    private static double FpMs(List<string> w)
    {
        // median of 3, cheap enough at this size
        return Median(3, delegate { return FingerprintOf(w).Length; });
    }

    private static string Counts(List<List<string>> rows)
    {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < rows.Count; i++)
        {
            if (i > 0) sb.Append(',');
            sb.Append(rows[i].Count);
        }
        return sb.ToString();
    }

    private static string Join(List<string> items)
    {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < items.Count; i++)
        {
            if (i > 0) sb.Append(' ');
            sb.Append(items[i]);
        }
        return sb.ToString();
    }

    private static double Median(int runs, Func<int> body)
    {
        body(); // warm
        double[] ts = new double[runs];
        for (int i = 0; i < runs; i++)
        {
            long t0 = Stopwatch.GetTimestamp();
            body();
            ts[i] = (Stopwatch.GetTimestamp() - t0) * 1000.0 / Stopwatch.Frequency;
        }
        Array.Sort(ts);
        return ts[runs / 2];
    }

    // byte-exact copy of WcpHost.BookRegistry.FingerprintOf
    internal static string FingerprintOf(IList<string> words)
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
}
