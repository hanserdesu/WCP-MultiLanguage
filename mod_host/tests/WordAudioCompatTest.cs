// 离线 harness：验证单词音频兼容层的纯逻辑（候选词形 / 完成标记 / 幂等判据）。
// 与 TakeoverScopeTest 同款：csc 直接编译源文件，不依赖 Unity。
// 验收：run_word_audio_compat_test.ps1 → Failures: 0
using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using WcpHost;

internal static class WordAudioCompatTest
{
    private static int _failures;

    private static int Main()
    {
        CandidateFormsBasics();
        ManagedRequestBoundary();
        CandidateFormsDedup();
        StampRoundTrip();
        StampPrefixSkipsWithoutEnumeration();
        MultiPackStampCoexists();
        StampDropsOtherPacks();
        MirrorPackEndToEnd();
        MirrorFileOps();
        Console.WriteLine("Failures: " + _failures);
        return _failures == 0 ? 0 : 1;
    }

    private static void Check(bool condition, string label)
    {
        if (condition) Console.WriteLine("PASS " + label);
        else { _failures++; Console.WriteLine("FAIL " + label); }
    }

    private static bool Contains(string[] forms, string value)
    {
        for (int i = 0; i < forms.Length; i++)
            if (string.Equals(forms[i], value, StringComparison.Ordinal)) return true;
        return false;
    }

    private static void ManagedRequestBoundary()
    {
        HashSet<string> words = new HashSet<string>(StringComparer.Ordinal) { "bonjour", "歯医者" };
        Check(WordAudioCompat.IsManagedRequest(words, "bonjour", null, null),
            "当前词书词形由 pack 接管");
        Check(WordAudioCompat.IsManagedRequest(words, "はいしゃ", "歯医者", "はいしゃ"),
            "当前词的日语读音可由 pack 接管");
        Check(!WordAudioCompat.IsManagedRequest(words, "unrelated", "歯医者", "はいしゃ"),
            "无关文本不能借当前词指针接管发音");
        Check(!WordAudioCompat.IsManagedRequest(words, "はいしゃ", "foreign", "はいしゃ"),
            "书外词指针不能借合法读音接管发音");
        Check(!WordAudioCompat.IsManagedRequest(words, "a whole sentence", null, null),
            "句子留给原生流程");
        Check(!WordAudioCompat.IsManagedRequest(null, "bonjour", null, null),
            "未激活词书不接管发音");
    }

    private static void CandidateFormsBasics()
    {
        string[] full = WordAudioCompat.CandidateForms("ＡＢＣ");
        Check(full.Length > 0 && Contains(full, "ＡＢＣ"), "全角原样保留");
        Check(Contains(full, "abc"), "全角+大小写归一到 abc");

        string[] dotted = WordAudioCompat.CandidateForms("Mr.");
        Check(Contains(dotted, "Mr."), "带点原样保留");
        Check(Contains(dotted, "Mr"), "去尾部句点");
        Check(Contains(dotted, "mr"), "去点+小写");

        string[] plain = WordAudioCompat.CandidateForms("Mr");
        Check(Contains(plain, "Mr."), "无点词补齐句点候选");

        string[] spaced = WordAudioCompat.CandidateForms("take off");
        Check(Contains(spaced, "take_off"), "空格转下划线");
        Check(Contains(spaced, "takeoff"), "去空格合并");

        Check(WordAudioCompat.CandidateForms("").Length == 0, "空输入返回空数组");
        Check(WordAudioCompat.CandidateForms(null).Length == 0, "null 输入返回空数组");
    }

    private static void CandidateFormsDedup()
    {
        string[] forms = WordAudioCompat.CandidateForms("abc");
        // "abc" 与其 NFKC+小写结果相同，候选集内不得有重复项。
        for (int i = 0; i < forms.Length; i++)
            for (int j = i + 1; j < forms.Length; j++)
                if (string.Equals(forms[i], forms[j], StringComparison.Ordinal))
                {
                    Check(false, "候选集存在重复项: " + forms[i]);
                    return;
                }
        Check(true, "候选集无重复项（" + forms.Length + " 项）");
    }

    private static void StampRoundTrip()
    {
        string dir = Path.Combine(Path.GetTempPath(),
            "wcp-stamp-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(dir);
        try
        {
            string stampPath = WordAudioCompat.StampPath(dir);
            Check(stampPath == Path.Combine(dir, ".wcp-mirror.txt"), "标记文件路径约定");
            Check(!WordAudioCompat.StampMatches(stampPath, "x"), "缺失标记视为不匹配");

            string stamp = WordAudioCompat.ExpectedStamp("catbar-jlpt-complete", 15812);
            Check(stamp.IndexOf("catbar-jlpt-complete") >= 0, "标记含 pack id");
            Check(stamp.IndexOf("files=15812") >= 0, "标记含文件数");

            WordAudioCompat.WriteStamp(stampPath, stamp);
            Check(WordAudioCompat.StampMatches(stampPath, stamp), "写入后往返匹配");
            Check(!WordAudioCompat.StampMatches(stampPath,
                WordAudioCompat.ExpectedStamp("catbar-jlpt-complete", 15813)),
                "文件数变化视为不匹配");
            Check(!WordAudioCompat.StampMatches(stampPath,
                WordAudioCompat.ExpectedStamp("other-pack", 15812)),
                "pack 变化视为不匹配");
        }
        finally
        {
            try { Directory.Delete(dir, true); } catch { }
        }
    }

    // 性能收敛 2026-09-18 第三轮：跳过判据必须能只靠「pack 身份 + 源目录 mtime」
    // 判定，**不枚举源目录**。这组断言同时守住一条容易出错的假设：目录 mtime 在
    // 增删文件后确实会变（否则判据会漏检 pack 更新）。
    private static void StampPrefixSkipsWithoutEnumeration()
    {
        string root = Path.Combine(Path.GetTempPath(),
            "wcp-stamp2-" + Guid.NewGuid().ToString("N"));
        string src = Path.Combine(root, "packs", "ru", "audio", "word");
        Directory.CreateDirectory(src);
        try
        {
            File.WriteAllBytes(Path.Combine(src, "a.mp3"), new byte[] { 1 });
            string stampPath = WordAudioCompat.StampPath(root);

            string prefix = WordAudioCompat.StampPrefix("catbar-russian-cefr-complete", src);
            Check(prefix.StartsWith("schema=2;", StringComparison.Ordinal),
                "跳过前缀用新 schema");
            Check(prefix.IndexOf("src=") > 0, "跳过前缀含源目录标记");
            Check(!WordAudioCompat.StampMatches(stampPath, prefix), "无标记时不跳过");

            // 收尾写的是「前缀 + files=N」——判据只用到前缀部分，files 仅作诊断。
            WordAudioCompat.WriteStamp(stampPath, prefix + "files=1");
            Check(WordAudioCompat.StampMatches(stampPath, prefix),
                "同 pack + 同源目录 → 跳过（全程未枚举源目录）");

            Check(!WordAudioCompat.StampMatches(stampPath,
                WordAudioCompat.StampPrefix("other-pack", src)),
                "换 pack 后不再跳过");

            // 源目录增文件必须让 mtime 变化 → 不再跳过。sleep 跨过时间戳粒度。
            System.Threading.Thread.Sleep(1100);
            File.WriteAllBytes(Path.Combine(src, "b.mp3"), new byte[] { 2 });
            Check(!WordAudioCompat.StampMatches(stampPath,
                WordAudioCompat.StampPrefix("catbar-russian-cefr-complete", src)),
                "源目录增文件后不再跳过（目录 mtime 判据有效）");
        }
        finally
        {
            try { Directory.Delete(root, true); } catch { }
        }
    }

    // 性能收敛 2026-09-18 第六轮：目标目录是所有语言**共用**的一个 vocabulary，
    // 而旧标记只存"最后完成的那个 pack"——切到法语写一行、再切俄语就不匹配而
    // 全量重扫（目标 69918 项 + 源 8451 项），切回法语又重扫。这组断言守住
    // "多个 pack 的记录必须共存"和"legacy 单行记录写入时被淘汰"。
    private static void MultiPackStampCoexists()
    {
        string root = Path.Combine(Path.GetTempPath(),
            "wcp-stamp3-" + Guid.NewGuid().ToString("N"));
        string fr = Path.Combine(root, "packs", "fr", "audio", "word");
        string ru = Path.Combine(root, "packs", "ru", "audio", "word");
        Directory.CreateDirectory(fr);
        Directory.CreateDirectory(ru);
        try
        {
            File.WriteAllBytes(Path.Combine(fr, "a.mp3"), new byte[] { 1 });
            File.WriteAllBytes(Path.Combine(ru, "b.mp3"), new byte[] { 2 });
            string stampPath = WordAudioCompat.StampPath(root);
            string frPrefix = WordAudioCompat.StampPrefix("catbar-french-cefr-complete", fr);
            string ruPrefix = WordAudioCompat.StampPrefix("catbar-russian-cefr-complete", ru);

            // 先播下一条 legacy 单行记录（真实机器上就是这么一条 schema=1）。
            File.WriteAllText(stampPath, "schema=1;catbar-french-cefr-complete;files=8116\n",
                              new UTF8Encoding(false));
            Check(!WordAudioCompat.StampMatches(stampPath, frPrefix),
                "legacy(schema=1) 记录不作数（无 src 时间戳，无法校验新鲜度）");

            WordAudioCompat.WriteStamp(stampPath, frPrefix + "files=1");
            Check(WordAudioCompat.StampMatches(stampPath, frPrefix), "写入 fr 后 fr 跳过");
            string text = File.ReadAllText(stampPath, Encoding.UTF8);
            Check(text.IndexOf("schema=1;") < 0, "写入时淘汰 legacy 行");

            // 关键：写入俄语不能把法语那条挤掉（共用一个目标目录）。
            WordAudioCompat.WriteStamp(stampPath, ruPrefix + "files=1");
            Check(WordAudioCompat.StampMatches(stampPath, ruPrefix), "写入 ru 后 ru 跳过");
            Check(WordAudioCompat.StampMatches(stampPath, frPrefix),
                "写入 ru 后 fr 仍跳过（多 pack 记录共存）");

            // 同一 pack 重写 = 更新那一行，不是追加。
            WordAudioCompat.WriteStamp(stampPath, frPrefix + "files=2");
            int lines = 0;
            string[] all = File.ReadAllLines(stampPath, Encoding.UTF8);
            for (int i = 0; i < all.Length; i++)
                if (!string.IsNullOrEmpty(all[i])) lines++;
            Check(lines == 2, "同 pack 重写是更新而非追加（行数=" + lines + "）");

            // 源目录 mtime 变了 → 该 pack 的判据失效，另一 pack 不受影响。
            System.Threading.Thread.Sleep(1100);
            File.WriteAllBytes(Path.Combine(fr, "c.mp3"), new byte[] { 3 });
            Check(!WordAudioCompat.StampMatches(stampPath,
                WordAudioCompat.StampPrefix("catbar-french-cefr-complete", fr)),
                "fr 源目录变化后不再跳过");
            Check(WordAudioCompat.StampMatches(stampPath, ruPrefix),
                "fr 失效不影响 ru 的跳过判据");
        }
        finally
        {
            try { Directory.Delete(root, true); } catch { }
        }
    }

    // 目标目录共用 → 某个 pack 真写进文件后，别人的"已完成"记录不可信。
    private static void StampDropsOtherPacks()
    {
        string dir = Path.Combine(Path.GetTempPath(),
            "wcp-stamp4-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(dir);
        try
        {
            string stampPath = WordAudioCompat.StampPath(dir);
            string fr = WordAudioCompat.StampPrefix("catbar-french-cefr-complete", dir);
            string ru = WordAudioCompat.StampPrefix("catbar-russian-cefr-complete", dir);
            WordAudioCompat.WriteStamp(stampPath, fr + "files=1");
            WordAudioCompat.WriteStamp(stampPath, ru + "files=2");
            Check(WordAudioCompat.StampMatches(stampPath, fr) &&
                  WordAudioCompat.StampMatches(stampPath, ru), "两条记录先共存");

            WordAudioCompat.DropOtherPacks(stampPath, "catbar-french-cefr-complete");
            Check(WordAudioCompat.StampMatches(stampPath, fr), "保留发生写入的那个 pack");
            Check(!WordAudioCompat.StampMatches(stampPath, ru),
                "清掉其它 pack（它需要的同名文件可能已被覆盖）");

            // 清空后写入仍然可用（不能留下空文件导致判据崩溃）。
            WordAudioCompat.DropOtherPacks(stampPath, "nobody");
            Check(!WordAudioCompat.StampMatches(stampPath, fr), "全部清掉");
            WordAudioCompat.WriteStamp(stampPath, fr + "files=3");
            Check(WordAudioCompat.StampMatches(stampPath, fr), "清空后仍可重新写入");
        }
        finally
        {
            try { Directory.Delete(dir, true); } catch { }
        }
    }

    // 第六轮：镜像主体从"主线程协程"搬到"后台线程调用的纯 IO 函数"，
    // 这组断言就是那个函数（MirrorPack）的端到端验收：它会真的建目录、复制、
    // 清理半截临时文件，并重复跑一次验证幂等。
    private static void MirrorPackEndToEnd()
    {
        string root = Path.Combine(Path.GetTempPath(),
            "wcp-mirrorpack-" + Guid.NewGuid().ToString("N"));
        string src = Path.Combine(root, "packs", "fr", "audio", "word");
        string dst = Path.Combine(root, "vocabulary");
        Directory.CreateDirectory(src);
        Directory.CreateDirectory(dst);
        try
        {
            File.WriteAllBytes(Path.Combine(src, "a.mp3"), new byte[] { 1, 2, 3 });
            File.WriteAllBytes(Path.Combine(src, "b.mp3"), new byte[] { 4, 5, 6, 7, 8 });
            File.WriteAllBytes(Path.Combine(src, "notes.txt"), new byte[] { 9 });
            // 目标里已有 a.mp3（同大小 + 同 mtime）→ 应判"已存在"；另留一个上次
            // 会话被杀在半路的临时文件 → 应被清理。
            string srcA = Path.Combine(src, "a.mp3");
            string dstA = Path.Combine(dst, "a.mp3");
            File.WriteAllBytes(dstA, new byte[] { 1, 2, 3 });
            File.SetLastWriteTimeUtc(dstA, File.GetLastWriteTimeUtc(srcA));
            File.WriteAllBytes(Path.Combine(dst, "c.mp3" + WordAudioCompat.TempSuffix),
                               new byte[] { 0 });

            WordAudioCompat.MirrorStats s1 = WordAudioCompat.MirrorPack(src, dst);
            Check(s1 != null, "非空源目录返回统计");
            Check(s1.Source == 2, "源只数 mp3（2 个，含 txt 不计）");
            Check(s1.Skipped == 1, "同大小目标判为已存在（1 个）");
            Check(s1.Copied == 1, "缺的那个被复制（1 个）");
            Check(s1.Failed == 0, "无失败");
            Check(s1.Ignored == 0, "无保留设备名");
            Check(s1.StaleTemp == 1, "清理半截临时文件（1 个）");
            Check(File.Exists(Path.Combine(dst, "b.mp3")), "复制后目标存在");
            Check(!File.Exists(Path.Combine(dst, "c.mp3" + WordAudioCompat.TempSuffix)),
                "临时文件已清掉");
            Check(!File.Exists(Path.Combine(dst, "notes.txt")), "非 mp3 不复制");

            WordAudioCompat.MirrorStats s2 = WordAudioCompat.MirrorPack(src, dst);
            Check(s2.Copied == 0 && s2.Skipped == 2, "重跑幂等（0 复制 / 2 已存在）");

            // 目标内容被改坏（大小不符）→ 必须重新复制，而不是跳过。
            File.WriteAllBytes(Path.Combine(dst, "b.mp3"), new byte[] { 9, 9 });
            WordAudioCompat.MirrorStats s3 = WordAudioCompat.MirrorPack(src, dst);
            Check(s3.Copied == 1, "大小不符时重新复制");
            Check(new FileInfo(Path.Combine(dst, "b.mp3")).Length == 5, "覆盖后长度正确");

            // ★ 跨语言同名缺陷守卫：大小**完全相同**、mtime 不同 → 必须重拷。
            // 只看大小的旧判据会在这一步跳过，于是目标里留着上一语言的音频
            // （实测 11 个语言对 10679 个同名样本里，这类错判有 474 个）。
            System.Threading.Thread.Sleep(1100);
            File.WriteAllBytes(Path.Combine(dst, "b.mp3"), new byte[] { 4, 5, 6, 7, 8 });
            Check(new FileInfo(Path.Combine(dst, "b.mp3")).Length == 5, "构造：大小与源相同");
            WordAudioCompat.MirrorStats s3b = WordAudioCompat.MirrorPack(src, dst);
            Check(s3b.Copied == 1 && s3b.Skipped == 1,
                "大小相同但 mtime 不同 → 重拷（同名不同内容的口子封住）");
            Check(File.GetLastWriteTimeUtc(Path.Combine(dst, "b.mp3")) ==
                  File.GetLastWriteTimeUtc(Path.Combine(src, "b.mp3")),
                "复制后目标 mtime = 源 mtime（判据才能在下次成立）");
            WordAudioCompat.MirrorStats s3c = WordAudioCompat.MirrorPack(src, dst);
            Check(s3c.Copied == 0 && s3c.Skipped == 2, "重拷一次后即稳定（mtime 判据不反复重做）");

            // 目标目录不存在 → 自动建（TryCopy 内建目录），不是失败。
            string fresh = Path.Combine(root, "vocabulary2");
            WordAudioCompat.MirrorStats s4 = WordAudioCompat.MirrorPack(src, fresh);
            Check(s4 != null && s4.Copied == 2 && s4.Failed == 0, "目标目录不存在时自动建并复制");
            Check(WordAudioCompat.MirrorPack(Path.Combine(root, "nope"), dst) == null,
                "源目录不存在返回 null（调用方据此不写标记）");

            // 保留设备名是纯函数判据（Windows 上无法真的建出 aux.mp3 来测）。
            Check(WordAudioCompat.IsReservedDeviceName("aux.mp3"), "aux.mp3 是保留设备名");
            Check(WordAudioCompat.IsReservedDeviceName("COM1.MP3"), "COM1 是保留设备名（不分大小写）");
            Check(!WordAudioCompat.IsReservedDeviceName("abandon.mp3"), "普通词不是保留设备名");
            Check(WordAudioCompat.IsTempName("x.mp3.wcptmp"), "临时名识别");
            Check(!WordAudioCompat.IsTempName("x.mp3"), "普通名不是临时名");
        }
        finally
        {
            try { Directory.Delete(root, true); } catch { }
        }
    }

    private static void MirrorFileOps()
    {
        string root = Path.Combine(Path.GetTempPath(),
            "wcp-mirror-" + Guid.NewGuid().ToString("N"));
        string src = Path.Combine(root, "packs", "ja", "audio", "word");
        string dst = Path.Combine(root, "vocabulary");
        Directory.CreateDirectory(src);
        try
        {
            File.WriteAllBytes(Path.Combine(src, "歯医者.mp3"), new byte[] { 1, 2, 3 });
            File.WriteAllBytes(Path.Combine(src, "続ける.mp3"), new byte[] { 4, 5 });
            File.WriteAllBytes(Path.Combine(src, "readme.txt"), new byte[] { 9 });

            string[] files = WordAudioCompat.ListSourceFiles(src);
            Check(files != null && files.Length == 2, "只枚举 mp3（2 个）");
            Check(WordAudioCompat.ListSourceFiles(Path.Combine(root, "nope")) == null,
                "源目录不存在返回 null");

            string first = Path.Combine(src, "歯医者.mp3");
            string target = Path.Combine(dst, "歯医者.mp3");
            Check(!WordAudioCompat.AlreadyPresent(first, target), "目标缺失时非已就位");
            Check(WordAudioCompat.TryCopy(first, target), "首次复制成功");
            Check(File.Exists(target), "复制后目标存在");
            Check(WordAudioCompat.AlreadyPresent(first, target),
                "同大小 + 同 mtime → 已就位（TryCopy 把源 mtime 带到了目标）");
            Check(WordAudioCompat.TryCopy(first, target), "重复复制幂等成功");

            // 大小不一致（内容被改坏）必须重新复制而不是跳过。
            File.WriteAllBytes(target, new byte[] { 9, 9, 9, 9 });
            Check(!WordAudioCompat.AlreadyPresent(first, target), "大小不一致时非已就位");

            // 大小一致但 mtime 不同 → 非已就位（跨语言同名的真实形态）。
            System.Threading.Thread.Sleep(1100);
            File.WriteAllBytes(target, new byte[] { 1, 2, 3 });
            Check(new FileInfo(target).Length == new FileInfo(first).Length, "构造：大小一致");
            Check(!WordAudioCompat.AlreadyPresent(first, target), "大小一致但 mtime 不同 → 非已就位");

            Check(WordAudioCompat.TryCopy(first, target), "覆盖 mtime 不符的目标");
            Check(new FileInfo(target).Length == 3, "覆盖后内容长度正确");
            Check(WordAudioCompat.AlreadyPresent(first, target), "覆盖后回到已就位");

            // 越界/非法目标（目录不存在）→ 自动建目录，不抛异常。
            string nested = Path.Combine(dst, "sub", "dir", "x.mp3");
            Check(WordAudioCompat.TryCopy(first, nested), "自动创建目标子目录");

            // 批量比对判据（纯内存，0 次文件系统调用）。它替换了旧的
            // AlreadyPresentIn —— 后者对每个源文件仍做一次 new FileInfo(...).Length，
            // ja 包 22794 个文件就是 22794 次系统调用（长帧来源）。
            Dictionary<string, WordAudioCompat.FileStamp> index =
                new Dictionary<string, WordAudioCompat.FileStamp>(StringComparer.OrdinalIgnoreCase);
            WordAudioCompat.FileStamp five;
            five.Size = 5;
            five.Ticks = 1000;
            index["A.MP3"] = five;

            WordAudioCompat.FileStamp probe;
            probe.Size = 5;
            probe.Ticks = 1000;
            Check(WordAudioCompat.IsPresentIn(index, "a.mp3", probe),
                "索引命中且大小+mtime 一致 → 已就位（忽略大小写）");

            probe.Size = 4;
            probe.Ticks = 1000;
            Check(!WordAudioCompat.IsPresentIn(index, "a.mp3", probe), "大小不符 → 非已就位");

            probe.Size = 5;
            probe.Ticks = 2000;
            Check(!WordAudioCompat.IsPresentIn(index, "a.mp3", probe),
                "大小相同但 mtime 不符 → 非已就位（缺陷守卫）");

            probe.Size = 5;
            probe.Ticks = 1000;
            Check(!WordAudioCompat.IsPresentIn(index, "missing.mp3", probe),
                "索引未命中 → 非已就位");
            Check(!WordAudioCompat.IsPresentIn(null, "a.mp3", probe),
                "null 索引 → 非已就位");
        }
        finally
        {
            try { Directory.Delete(root, true); } catch { }
        }
    }
}
