// WCP Host — 单词音频"游戏原生目录"兼容层
//
// 背景（2026-09-16 实证）：游戏的 VocabularyAudioPlayer 只认
//   <LocalLow>\WCP\vocabulary\<题干>.mp3
// 这是游戏引擎自带的路径（不是插件的约定）。v1.1.0 起安装器只把单词音频写进
// packs/<lang>/audio/word，于是宿主未接管（读档中 / 未激活 / 旧插件兜底）或
// 词形查不到时，游戏会静默回退到自己的英语 AI 语音。开发机上通常有历史安装
// 留下的目录副本，缺陷只在用户侧暴露——所以这里把 pack 音频补进游戏原生目录。
//
// 三条硬约束：
//   1. 只补缺（目标已存在且大小一致就跳过）—— 幂等、可中断、可重入；
//   2. 任何 IO 异常只记录日志并停下，绝不抛进游戏加载路径；
//   3. 纯逻辑全部是无 Unity 依赖的静态方法，离线 harness 可直接断言。
using System;
using System.Collections.Generic;
using System.IO;
using System.Text;

namespace WcpHost
{
    internal static class WordAudioCompat
    {
        internal const string StampFileName = ".wcp-mirror.txt";
        // 每帧最多处理的文件数 / 每帧时间预算（秒），两者取先到者。
        internal const int MaxFilesPerFrame = 32;
        internal const float FrameBudgetSeconds = 0.006f;

        // ── 词形候选 ────────────────────────────────────────────────────
        //
        // 同一个词在不同来源之间的写法会有差异（游戏原生目录用全角、词表用
        // 半角、题干保留句点、空格与下划线混用……）。按序返回去重后的候选，
        // 调用方第一个命中磁盘的即为可用项。纯函数，便于离线断言。
        internal static string[] CandidateForms(string key)
        {
            if (string.IsNullOrEmpty(key)) return new string[0];
            List<string> forms = new List<string>();
            AddForm(forms, key);
            AddForm(forms, Fold(key));
            AddForm(forms, StripTrailingDot(key));
            AddForm(forms, key.Replace(' ', '_'));
            AddForm(forms, Fold(StripTrailingDot(key)));
            AddForm(forms, Fold(key.Replace(' ', '_')));
            AddForm(forms, Fold(key.Replace(" ", "").Replace("　", "")));
            if (key.IndexOf('.') < 0) AddForm(forms, key + ".");
            return forms.ToArray();
        }

        private static void AddForm(List<string> forms, string value)
        {
            if (string.IsNullOrEmpty(value)) return;
            for (int i = 0; i < forms.Count; i++)
                if (string.Equals(forms[i], value, StringComparison.Ordinal)) return;
            forms.Add(value);
        }

        // 全角/半角与大小写归一（"ＡＢＣ" ↔ "ABC"）。Normalize 在异常输入上
        // 可能抛（非法 UTF-16 代理对），回退为原值。
        private static string Fold(string value)
        {
            if (string.IsNullOrEmpty(value)) return value;
            string folded;
            try { folded = value.Normalize(NormalizationForm.FormKC); }
            catch { folded = value; }
            return folded.ToLowerInvariant();
        }

        private static string StripTrailingDot(string value)
        {
            return value.Length > 1 && value[value.Length - 1] == '.'
                ? value.Substring(0, value.Length - 1) : value;
        }

        // ── 镜像状态 ────────────────────────────────────────────────────

        internal static string StampPath(string targetDir)
        {
            return Path.Combine(targetDir, StampFileName);
        }

        // 完成标记：pack 身份 + 源文件数。任一变化（换语言包 / 音频更新）都会
        // 让下一次激活重新镜像；未完成（中途退出）则不写标记，下次自动续做。
        internal static string ExpectedStamp(string packId, int fileCount)
        {
            return "schema=1;" + (packId == null ? "" : packId) + ";files=" +
                   fileCount.ToString();
        }

        internal static bool StampMatches(string stampPath, string expected)
        {
            try
            {
                if (!File.Exists(stampPath)) return false;
                return string.Equals(File.ReadAllText(stampPath, Encoding.UTF8).Trim(),
                                     expected, StringComparison.Ordinal);
            }
            catch { return false; }
        }

        internal static void WriteStamp(string stampPath, string stamp)
        {
            try
            {
                string dir = Path.GetDirectoryName(stampPath);
                if (!string.IsNullOrEmpty(dir) && !Directory.Exists(dir))
                    Directory.CreateDirectory(dir);
                File.WriteAllText(stampPath, stamp, new UTF8Encoding(false));
            }
            catch { }
        }

        // ── 文件操作（全部吞异常；调用方按返回值计数）────────────────────

        internal static string[] ListSourceFiles(string sourceDir)
        {
            try
            {
                if (!Directory.Exists(sourceDir)) return null;
                return Directory.GetFiles(sourceDir, "*.mp3");
            }
            catch { return null; }
        }

        // 目标已存在且大小一致 → 视为已就位（幂等判据）。
        internal static bool AlreadyPresent(string sourceFile, string targetFile)
        {
            try
            {
                FileInfo target = new FileInfo(targetFile);
                if (!target.Exists) return false;
                return target.Length == new FileInfo(sourceFile).Length;
            }
            catch { return false; }
        }

        internal static bool TryCopy(string sourceFile, string targetFile)
        {
            try
            {
                string dir = Path.GetDirectoryName(targetFile);
                if (!string.IsNullOrEmpty(dir) && !Directory.Exists(dir))
                    Directory.CreateDirectory(dir);
                File.Copy(sourceFile, targetFile, true);
                // 保留设备名（aux.mp3/nul.mp3）在 Win32 层不可寻址，复制会失败；
                // 这类文件游戏自己也读不到，失败计数即可，不影响其它文件。
                return File.Exists(targetFile);
            }
            catch { return false; }
        }
    }
}
