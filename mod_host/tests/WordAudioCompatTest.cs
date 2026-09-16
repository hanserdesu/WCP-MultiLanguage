// 离线 harness：验证单词音频兼容层的纯逻辑（候选词形 / 完成标记 / 幂等判据）。
// 与 TakeoverScopeTest 同款：csc 直接编译源文件，不依赖 Unity。
// 验收：run_word_audio_compat_test.ps1 → Failures: 0
using System;
using System.IO;
using System.Text;
using WcpHost;

internal static class WordAudioCompatTest
{
    private static int _failures;

    private static int Main()
    {
        CandidateFormsBasics();
        CandidateFormsDedup();
        StampRoundTrip();
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
            Check(WordAudioCompat.AlreadyPresent(first, target), "同大小目标视为已就位");
            Check(WordAudioCompat.TryCopy(first, target), "重复复制幂等成功");

            // 大小不一致（内容被改坏）必须重新复制而不是跳过。
            File.WriteAllBytes(target, new byte[] { 9, 9, 9, 9 });
            Check(!WordAudioCompat.AlreadyPresent(first, target), "大小不一致时非已就位");
            Check(WordAudioCompat.TryCopy(first, target), "覆盖大小不符的目标");
            Check(new FileInfo(target).Length == 3, "覆盖后内容长度正确");

            // 越界/非法目标（目录不存在）→ 自动建目录，不抛异常。
            string nested = Path.Combine(dst, "sub", "dir", "x.mp3");
            Check(WordAudioCompat.TryCopy(first, nested), "自动创建目标子目录");
        }
        finally
        {
            try { Directory.Delete(root, true); } catch { }
        }
    }
}
