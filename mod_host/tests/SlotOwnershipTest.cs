// Offline harness for the P1-4 service boundary (SlotOwnership).
// References the same compiled WcpHost.dll the game runs — no game types needed:
// SlotOwnership only depends on BCL file IO + the in-DLL Json/Fingerprint helpers.
using System;
using System.IO;
using System.Text;
using WcpHost;

internal static class SlotOwnershipTest
{
    private static int failures;

    private static void Check(bool value, string label)
    {
        Console.WriteLine((value ? "PASS " : "FAIL ") + label);
        if (!value) failures++;
    }

    private static string TempDir()
    {
        string dir = Path.Combine(Path.GetTempPath(), "wcphost_slotown_" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(dir);
        return dir;
    }

    // A store row written exactly the way CustomSlotModel.Serialize writes it.
    private static string Row(int number, string id, string owner, bool managed, int nativeSlot, string[] words)
    {
        StringBuilder sb = new StringBuilder();
        sb.Append("{\"number\":").Append(number).Append(",\"id\":\"").Append(id)
          .Append("\",\"name\":\"n\",\"language\":\"xx\",\"owner\":\"").Append(owner)
          .Append("\",\"managed\":").Append(managed ? "true" : "false")
          .Append(",\"nativeSlot\":").Append(nativeSlot).Append(",\"words\":[");
        for (int i = 0; i < words.Length; i++)
        {
            if (i > 0) sb.Append(',');
            sb.Append('"').Append(words[i]).Append('"');
        }
        sb.Append("]}");
        return sb.ToString();
    }

    private static string Store(int selected, params string[] rows)
    {
        StringBuilder sb = new StringBuilder();
        sb.Append("{\"schema\":1,\"selected\":").Append(selected).Append(",\"slots\":[");
        for (int i = 0; i < rows.Length; i++)
        {
            if (i > 0) sb.Append(',');
            sb.Append(rows[i]);
        }
        sb.Append("]}");
        return sb.ToString();
    }

    private static int _storeStamp;
    private static void WriteStore(string path, string json)
    {
        File.WriteAllText(path, json, new UTF8Encoding(false));
        // Make sure the mtime-based cache cannot mask the rewrite even on
        // coarse-resolution filesystems or back-to-back calls.
        // 第十四轮改为单调递增戳：原 `failures*1000 + 毫秒` 在一次全过的运行里
        // failures 恒为 0，两次相邻写入可能落进同一毫秒 → mtime 相同 → 第 11 条
        // （重写后重解析）会被 mtime 缓存掩盖而假通过。
        File.SetLastWriteTimeUtc(path, DateTime.UtcNow.AddSeconds(++_storeStamp));
    }

    private static string[] Six = { "b1", "b2", "b3", "b4", "b5", "b6" };
    private static string[] Other = { "o1", "o2", "o3", "o4", "o5", "o6" };

    private static int Main()
    {
        try { Console.OutputEncoding = Encoding.UTF8; }
        catch (Exception) { }

        string served = BookRegistry.FingerprintOf(Six);
        string other = BookRegistry.FingerprintOf(Other);

        // 1. No store at all → compatibility fallback (old fingerprint-only behavior).
        string dir = TempDir();
        string path = Path.Combine(dir, "WcpCustomSlots.json");
        SlotOwnership so = new SlotOwnership(path);
        string reason;
        Check(so.IsServed(served, out reason), "store 缺失 → 兼容回退放行");
        Check(reason == null, "store 缺失时不产生拒因");

        // 2. Managed seeded row → served.
        WriteStore(path, Store(0, Row(5, "catbar-xx", "mod", true, 0, Six)));
        so = new SlotOwnership(path);
        Check(so.IsServed(served, out reason), "托管播种行 → 在服务范围");

        // 3. Native mirror row → served (existing-user compatibility).
        WriteStore(path, Store(0, Row(1, "", "external", false, 2, Six)));
        so = new SlotOwnership(path);
        Check(so.IsServed(served, out reason), "原生镜像行 → 在服务范围");

        // 4. Store exists but nothing registered for this fingerprint → fail-closed.
        WriteStore(path, Store(0, Row(5, "catbar-xx", "mod", true, 0, Other)));
        so = new SlotOwnership(path);
        Check(!so.IsServed(served, out reason), "未登记指纹 → 拒绝服务");
        Check(reason != null && reason.Contains("20 槽"), "拒因说明槽位归属");

        // 5. Every row cleared / too short → nothing registered at all → treated as
        //    "not seeded yet" and served (an all-empty table cannot express
        //    revocation; fail-closed here blacked out fully installed books).
        WriteStore(path, Store(0, Row(5, "", "external", false, 0, new string[0])));
        so = new SlotOwnership(path);
        Check(so.IsServed(served, out reason), "唯一一行被清空 → 视为未播种，放行");
        Check(reason == null, "未播种放行时不产生拒因");

        // 6. Too-short row is ignored (below playable minimum) → same as not seeded.
        WriteStore(path, Store(0, Row(5, "catbar-xx", "mod", true, 0, new[] { "b1", "b2" })));
        so = new SlotOwnership(path);
        Check(so.IsServed(served, out reason), "词数不足的行不计入登记（等价未播种）");

        // 6b. Real fresh-install shape: 20 placeholder rows, no registration → served.
        string[] placeholders = new string[20];
        for (int i = 0; i < placeholders.Length; i++)
            placeholders[i] = Row(i + 1, "", "external", false, 0, new string[0]);
        WriteStore(path, Store(0, placeholders));
        so = new SlotOwnership(path);
        Check(so.IsServed(served, out reason), "20 条占位行（新装未播种）→ 放行");

        // 6c. Revocation still holds while other rows stay registered: clearing the
        //     target's row leaks nothing because the table is non-empty.
        WriteStore(path, Store(0,
            Row(1, "", "external", false, 0, new string[0]),
            Row(2, "", "external", false, 2, Other)));
        so = new SlotOwnership(path);
        Check(!so.IsServed(served, out reason), "非空表中的清空行 → 仍拒绝服务");

        // 7. Mixed table: served fingerprint present among other rows.
        WriteStore(path, Store(0,
            Row(1, "", "external", false, 1, Other),
            Row(5, "catbar-xx", "mod", true, 0, Six)));
        so = new SlotOwnership(path);
        Check(so.IsServed(served, out reason), "混合表中的托管行命中");
        Check(!so.IsServed(other, out reason) == false, "混合表中的镜像行命中");

        // 8. Corrupt store → fail-closed, then self-heals after CustomSlotsMod rewrites it.
        WriteStore(path, "{not json");
        so = new SlotOwnership(path);
        Check(!so.IsServed(served, out reason), "损坏存档 → fail-closed");
        Check(reason != null && reason.Contains("损坏"), "损坏拒因明确");
        WriteStore(path, Store(0, Row(5, "catbar-xx", "mod", true, 0, Six)));
        Check(so.IsServed(served, out reason), "存档被重写后自动恢复（自愈路径）");

        // 9. Empty slots array → nothing registered → compatibility fallback.
        WriteStore(path, Store(0));
        so = new SlotOwnership(path);
        Check(so.IsServed(served, out reason), "空表（未播种）→ 兼容回退放行");

        // 10. mtime cache: unchanged store reuses result (no re-read) — same answer both ways.
        WriteStore(path, Store(0, Row(5, "catbar-xx", "mod", true, 0, Six)));
        so = new SlotOwnership(path);
        bool first = so.IsServed(served, out reason);
        bool second = so.IsServed(served, out reason);
        Check(first && second, "mtime 未变时缓存结论稳定");

        // 11. 第十四轮：行指纹记忆化 —— CustomSlotsMod 每次保存都重写整个 store
        //     （mtime 必变），但内容原样。重解析必须命中 memo（跳过
        //     Normalize+排序+SHA256 的全量指纹），结论不变。
        WriteStore(path, Store(0, Row(5, "catbar-xx", "mod", true, 0, Six)));
        so = new SlotOwnership(path);
        int hitsBefore = so.MemoHits;
        bool r1 = so.IsServed(served, out reason);          // 首次：未命中 → 计算并缓存
        WriteStore(path, Store(0, Row(5, "catbar-xx", "mod", true, 0, Six)));   // mtime 变、内容不变
        bool r2 = so.IsServed(served, out reason);          // 重解析：应命中
        Check(r1 && r2, "store 重写内容不变 → 服务结论不变");
        Check(so.MemoHits == hitsBefore + 1, "重解析命中行指纹 memo（全量指纹只算一次）");

        // 12. 行内容真的变化 → 该行 memo 未命中、重算指纹，服务边界正确翻转。
        WriteStore(path, Store(0, Row(5, "catbar-xx", "mod", true, 0, Other)));
        bool r3 = so.IsServed(other, out reason);
        bool r4 = so.IsServed(served, out reason);
        Check(r3 && !r4, "行内容变化 → memo 未命中，重算指纹并正确翻转服务边界");
        Check(so.MemoHits == hitsBefore + 1, "内容变化的那一行不计入 memo 命中");

        Console.WriteLine(failures == 0 ? "ALL PASS" : ("FAILURES: " + failures));
        return failures == 0 ? 0 : 1;
    }
}
