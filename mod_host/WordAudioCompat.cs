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
//
// 2026-09-18 第六轮（切词库卡顿）：整个镜像体改为 MirrorPack()，由后台线程调用。
//   本文件**不得**引用任何 Unity API（Time / Application / Debug 都不行）——
//   它会被非主线程执行，Unity 的 API 只在主线程合法（守规矩的方式是路径全部
//   由主线程算好再传进来）。协程版的两条已踩过的坑一并记在这里：
//     - Time.realtimeSinceStartup 在一帧内是常量，"每帧时间预算"判据实际上永不
//       提前触发，最坏帧只能靠条数上限兜底；
//     - StartCoroutine 的生命周期跟 MonoBehaviour/场景绑定，切库时 StopCoroutine
//       会让镜像"有开始没完成"，且 stamp 写不上 → 每次切库全量重扫。
//   换成后台线程后这两条结构性消失：不占帧、不怕场景切换、必然跑完。
//
// 离线实测（probes/csbench，.NET Framework 4.0，本机 SSD）：
//   DirectoryInfo.EnumerateFiles() + FileInfo.Length  1.3~2.1us/项（大小随枚举免费带回）
//   new FileInfo(path).Length 单独取大小             88us/项（慢 40~60 倍，是旧长帧来源）
//   File.Copy 10KB                                    1.25~1.4ms/文件
//   FingerprintOf(8116 词)                            1.9~4.9ms
//   File.ReadAllBytes(MyBook.es3 2.1MB)               1~5ms
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Text;

namespace WcpHost
{
    internal static class WordAudioCompat
    {
        internal const string StampFileName = ".wcp-mirror.txt";
        // 后台线程已不占帧，这三个上限只作防御（万一被主线程路径复用）。
        internal const int MaxFilesPerFrame = 32;
        internal const float FrameBudgetSeconds = 0.006f;
        internal const int IndexBatchPerFrame = 4096;
        // 原子复制的中间后缀：先写它再改名，游戏不会读到半截 mp3。
        internal const string TempSuffix = ".wcptmp";

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

        // 完成标记（schema=2）：pack 身份 + 源目录修改时间（+ 文件数，仅诊断）。
        // 任一变化（换语言包 / pack 音频增删）都会让下一次激活重新镜像；未完成
        // （中途退出）则不写标记，下次自动续做。
        //
        // 为什么把「源文件数」换成「源目录 mtime」：原判据是 pack 身份 + 文件数，
        // 而文件数必须**枚举整个源目录**才数得出来 —— 为了判断「要不要跳过镜像」
        // 反而先把源目录列一遍，把要省的成本又花回去了。目录 mtime 是一次 stat
        // （O(1)），且源目录增删文件都会更新它，语义上严格强于「文件数」。
        // 文件数仍写进标记，但只用于诊断，不参与判据。
        internal static string SourceDirTicks(string sourceDir)
        {
            try
            {
                if (string.IsNullOrEmpty(sourceDir)) return "0";
                DirectoryInfo info = new DirectoryInfo(sourceDir);
                if (!info.Exists) return "0";
                return info.LastWriteTimeUtc.Ticks.ToString();
            }
            catch { return "0"; }
        }

        // 跳过判据用的前缀：pack 身份 + 源目录 mtime，全部 O(1) 可得，
        // **不需要枚举源目录**。以 ';' 结尾，便于与后面的 files= 段拼接/前缀匹配。
        internal static string StampPrefix(string packId, string sourceDir)
        {
            return "schema=2;pack=" + (packId == null ? "" : packId) +
                   ";src=" + SourceDirTicks(sourceDir) + ";";
        }

        internal static string ExpectedStamp(string packId, int fileCount)
        {
            return StampPrefix(packId, null) + "files=" + fileCount.ToString();
        }

        // ── 标记文件：一行一个 pack ──────────────────────────────────────
        //
        // 目标目录是**所有语言共用**的（游戏只认这一个 vocabulary 目录），而旧实现
        // 只存一行"最后完成的那个 pack"。后果是：切到法语写一行 fr，再切到俄语就
        // 因为不匹配而全量重扫一遍（目标 69918 项 + 源 8451 项），切回法语又重扫
        // ——每次切库都白扫 7.8 万项。这是"切词库特别卡"的直接来源之一。
        // 现在按 pack 分行累积，切回已镜像过的语言是 O(1) 跳过。
        internal static bool StampMatches(string stampPath, string expected)
        {
            try
            {
                if (string.IsNullOrEmpty(expected)) return false;
                if (!File.Exists(stampPath)) return false;
                string[] lines = File.ReadAllLines(stampPath, Encoding.UTF8);
                for (int i = 0; i < lines.Length; i++)
                {
                    string line = lines[i] == null ? null : lines[i].Trim();
                    if (string.IsNullOrEmpty(line)) continue;
                    if (line.StartsWith(expected, StringComparison.Ordinal)) return true;
                }
                return false;
            }
            catch { return false; }
        }

        // 从标记串里抽出 pack 身份；抽不到返回 null（调用方退化为"只追加"）。
        internal static string StampPackId(string stamp)
        {
            if (string.IsNullOrEmpty(stamp)) return null;
            int at = stamp.IndexOf(";pack=", StringComparison.Ordinal);
            if (at < 0) return null;
            int start = at + 6;
            int end = stamp.IndexOf(';', start);
            if (end < 0) end = stamp.Length;
            return stamp.Substring(start, end - start);
        }

        private static bool IsLegacyStampLine(string line)
        {
            // schema=1 的单行标记（无 src 时间戳，无法校验新鲜度）→ 写入时清掉，
            // 由下一次镜像重新建立可信记录。
            return line.StartsWith("schema=1;", StringComparison.Ordinal);
        }

        internal static void WriteStamp(string stampPath, string stamp)
        {
            try
            {
                string dir = Path.GetDirectoryName(stampPath);
                if (!string.IsNullOrEmpty(dir) && !Directory.Exists(dir))
                    Directory.CreateDirectory(dir);

                string packId = StampPackId(stamp);
                List<string> keep = new List<string>();
                if (File.Exists(stampPath))
                {
                    string[] old = File.ReadAllLines(stampPath, Encoding.UTF8);
                    for (int i = 0; i < old.Length; i++)
                    {
                        string line = old[i] == null ? null : old[i].Trim();
                        if (string.IsNullOrEmpty(line)) continue;
                        if (IsLegacyStampLine(line)) continue;
                        if (packId != null)
                        {
                            string oldPack = StampPackId(line);
                            if (string.Equals(oldPack, packId, StringComparison.Ordinal)) continue;
                        }
                        keep.Add(line);
                    }
                }
                keep.Add(stamp);

                // 临时文件 + 改名：标记文件是"下次跳过"的唯一依据，写坏了会退化成
                // 每次全量重扫，不能出现半截内容。
                string temp = stampPath + TempSuffix;
                File.WriteAllText(temp, string.Join("\n", keep.ToArray()) + "\n",
                                  new UTF8Encoding(false));
                if (File.Exists(stampPath)) File.Delete(stampPath);
                File.Move(temp, stampPath);
            }
            catch { }
        }

        // 某个 pack 真的写进了目标目录后，**其它 pack 的"已完成"记录就不再可信** ——
        // 目标目录是所有语言共用的，这个 pack 可能覆盖了别人需要的同名文件。
        // 保留没被影响的记录会让我们跳过本该重做的镜像 → 目标里留着别人的音频。
        // 保守但正确：只要复制过文件，就把其它 pack 的行全部清掉；下次切到那些语言
        // 会重跑一次，而重跑靠「大小 + mtime」判据只会补真正需要的文件（几十毫秒级 IO，
        // 且全在后台线程）。
        internal static void DropOtherPacks(string stampPath, string keepPackId)
        {
            try
            {
                if (!File.Exists(stampPath)) return;
                string[] old = File.ReadAllLines(stampPath, Encoding.UTF8);
                List<string> keep = new List<string>();
                bool changed = false;
                for (int i = 0; i < old.Length; i++)
                {
                    string line = old[i] == null ? null : old[i].Trim();
                    if (string.IsNullOrEmpty(line)) { changed = true; continue; }
                    if (IsLegacyStampLine(line)) { changed = true; continue; }
                    string pack = StampPackId(line);
                    if (pack != null && !string.Equals(pack, keepPackId, StringComparison.Ordinal))
                    {
                        changed = true;
                        continue;
                    }
                    keep.Add(line);
                }
                if (!changed) return;
                string temp = stampPath + TempSuffix;
                File.WriteAllText(temp, keep.Count == 0
                    ? string.Empty
                    : string.Join("\n", keep.ToArray()) + "\n",
                    new UTF8Encoding(false));
                if (File.Exists(stampPath)) File.Delete(stampPath);
                File.Move(temp, stampPath);
            }
            catch { }
        }

        // ── 文件操作（全部吞异常；调用方按返回值计数）────────────────────

        // 一次性列出源目录（只保留给离线 harness 断言；宿主路径用 MirrorPack 的
        // 「枚举带回名字与大小」，避免为取大小再逐文件 stat）。
        internal static string[] ListSourceFiles(string sourceDir)
        {
            try
            {
                if (!Directory.Exists(sourceDir)) return null;
                return Directory.GetFiles(sourceDir, "*.mp3");
            }
            catch { return null; }
        }

        // 目标已存在且**大小与 mtime 都一致** → 视为已就位。
        // 判据为什么不是"只看大小"：见上面 IsPresentIn 的注释（跨语言同名文件
        // 大小相同而内容不同的比例实测 6.82%）。
        internal static bool AlreadyPresent(string sourceFile, string targetFile)
        {
            try
            {
                FileStamp target = StampOf(targetFile);
                if (target.Size < 0) return false;
                FileStamp source = StampOf(sourceFile);
                if (source.Size < 0) return false;
                return target.Size == source.Size && target.Ticks == source.Ticks;
            }
            catch { return false; }
        }

        // ── 批量比对 ────────────────────────────────────────────────────
        //
        // 索引化花了两轮才做对，把错在哪记下来免得再踩：
        //   第一轮：AlreadyPresent 每个文件建 2 个 FileInfo（源 + 目标）= 2 次
        //     stat；ja 包 22794 个 = 454ms 纯 stat，再按「每帧 32 个」摊薄要 712
        //     帧，而一次会话常常只有 600 多帧 —— 外循环永远走不到头、stamp 永远
        //     写不上（2026-09-18 14:05 会话实测：只有「开始」没有「完成」）。
        //   第二轮：只把**目标侧**索引化，源侧仍留在 AlreadyPresentIn 里做
        //     new FileInfo(sourceFile).Length —— **那是 1 次 stat/文件，没省掉**。
        //   第三轮：两侧都改由「一次目录枚举」带回名字与大小，比对退化为纯内存。
        //
        // 判据从「只看大小」升级为「大小 + mtime」（2026-09-18 第六轮）。这不是
        // 加成本，而是**修一个正确性缺陷**：
        //   目标目录是所有语言共用的一个目录，不同语言包存在**同名但内容不同**的
        //   音频。实测 11 个语言对、10679 个同名样本：其中 6952 个大小恰好相同，
        //   而这 6952 个里 **474 个内容其实不同**（错判率 6.82%）—— 只看大小会把
        //   它们判成"已就位"，于是切语言后保留上一语言的音频 → 播放错误发音。
        //   换成「大小 + mtime」后，同一批样本的错判率是 **0.00%（0/6952）**。
        // 成本为零的依据（离线实测 probes/csbench）：
        //   EnumerateFiles() 同时带回 Length 与 LastWriteTimeUtc（都来自
        //   WIN32_FIND_DATA）—— 69918 项读 Length 62~101ms、读 mtime 78~102ms，
        //   同量级；而用新建 FileInfo 取任一属性要 4.6~5.8 秒（66~84us/项）。
        // 复制后把源 mtime 写到目标（File.SetLastWriteTimeUtc，129us/文件）来让这个
        // 判据在"我们复制的文件"上成立。
        //
        // 名字比较用 OrdinalIgnoreCase：Windows 文件系统本身不区分大小写，
        // 用 Ordinal 会漏判。
        internal struct FileStamp
        {
            internal long Size;
            internal long Ticks;
        }

        internal static bool IsPresentIn(Dictionary<string, FileStamp> index,
                                        string name, FileStamp source)
        {
            if (index == null || string.IsNullOrEmpty(name)) return false;
            FileStamp have;
            if (!index.TryGetValue(name, out have)) return false;
            return have.Size == source.Size && have.Ticks == source.Ticks;
        }

        // 目录枚举 → 名字:（大小 + mtime）。两者都随枚举免费带回，不做 per-file stat。
        internal static Dictionary<string, FileStamp> IndexDir(string dir, string pattern)
        {
            Dictionary<string, FileStamp> index =
                new Dictionary<string, FileStamp>(StringComparer.OrdinalIgnoreCase);
            try
            {
                DirectoryInfo info = new DirectoryInfo(dir);
                if (!info.Exists) return index;
                IEnumerable<FileInfo> seq =
                    pattern == null ? info.EnumerateFiles() : info.EnumerateFiles(pattern);
                foreach (FileInfo fi in seq)
                {
                    try
                    {
                        FileStamp stamp;
                        stamp.Size = fi.Length;
                        stamp.Ticks = fi.LastWriteTimeUtc.Ticks;
                        index[fi.Name] = stamp;
                    }
                    catch { }
                }
            }
            catch { }
            return index;
        }

        internal static FileStamp StampOf(string file)
        {
            FileStamp stamp;
            stamp.Size = -1;
            stamp.Ticks = -1;
            try
            {
                FileInfo info = new FileInfo(file);
                if (!info.Exists) return stamp;
                stamp.Size = info.Length;
                stamp.Ticks = info.LastWriteTimeUtc.Ticks;
            }
            catch { }
            return stamp;
        }

        // Win32 保留设备名（大小写不敏感，带不带扩展名都保留）：这些名字在
        // Win32 层指向设备而不是文件，复制必然失败，但游戏自己也读不到它们。
        // 单独归类为"忽略"，不计入 failed —— 否则只要源目录里有一个 aux.mp3，
        // failed 就永远非 0，stamp 永远写不上，每次都重扫全表。
        internal static bool IsReservedDeviceName(string fileName)
        {
            if (string.IsNullOrEmpty(fileName)) return false;
            string stem = Path.GetFileNameWithoutExtension(fileName);
            if (string.IsNullOrEmpty(stem)) return false;
            switch (stem.ToUpperInvariant())
            {
                case "CON": case "PRN": case "AUX": case "NUL":
                    return true;
            }
            if (stem.Length == 4)
            {
                char c0 = char.ToUpperInvariant(stem[0]);
                char c1 = char.ToUpperInvariant(stem[1]);
                char c2 = char.ToUpperInvariant(stem[2]);
                char c3 = stem[3];
                if (c0 == 'C' && c1 == 'O' && c2 == 'M' && c3 >= '1' && c3 <= '9')
                    return true;
                if (c0 == 'L' && c1 == 'P' && c2 == 'T' && c3 >= '1' && c3 <= '9')
                    return true;
            }
            return false;
        }

        internal static bool IsTempName(string fileName)
        {
            return !string.IsNullOrEmpty(fileName) &&
                   fileName.EndsWith(TempSuffix, StringComparison.OrdinalIgnoreCase);
        }

        // 先写临时名、再改名覆盖。File.Copy(overwrite) 会让目标文件在拷贝期间
        // 处于"长度已变、内容未全"的状态，而游戏可能正好在这一刻读它 → 播到半截
        // 音频。实测多出的 delete+rename 约 0.2ms/文件，换掉这个竞态很划算。
        //
        // 复制后把**源文件的 mtime 写到目标**：这是「大小 + mtime」判据能在我们自己
        // 复制的文件上成立的前提（否则每次都要重拷一遍）。实测
        // File.SetLastWriteTimeUtc 129us/文件。
        internal static bool TryCopy(string sourceFile, string targetFile)
        {
            string temp = targetFile + TempSuffix;
            try
            {
                string dir = Path.GetDirectoryName(targetFile);
                if (!string.IsNullOrEmpty(dir) && !Directory.Exists(dir))
                    Directory.CreateDirectory(dir);
                DateTime sourceTime = File.GetLastWriteTimeUtc(sourceFile);
                File.Copy(sourceFile, temp, true);
                if (File.Exists(targetFile)) File.Delete(targetFile);
                File.Move(temp, targetFile);
                try { File.SetLastWriteTimeUtc(targetFile, sourceTime); } catch { }
                return File.Exists(targetFile);
            }
            catch
            {
                try { if (File.Exists(temp)) File.Delete(temp); } catch { }
                return false;
            }
        }

        // ── 镜像主体（后台线程调用；无任何 Unity API）────────────────────

        internal sealed class MirrorStats
        {
            internal int Source;
            internal int Target;
            internal int Copied;
            internal int Skipped;
            internal int Failed;
            internal int Ignored;
            internal int StaleTemp;
            internal double SourceMs;
            internal double TargetMs;
            internal double CompareMs;
            internal double CopyMs;
        }

        // 一次完整的镜像。返回 null 表示源目录空/不可读（调用方不打标记，下次重试）。
        // 调用方负责记日志与写标记；这里只做 IO 与计数。
        internal static MirrorStats MirrorPack(string sourceDir, string targetDir)
        {
            Stopwatch clock = Stopwatch.StartNew();
            MirrorStats stats = new MirrorStats();

            Dictionary<string, FileStamp> sourceIndex = IndexDir(sourceDir, "*.mp3");
            stats.Source = sourceIndex.Count;
            stats.SourceMs = clock.Elapsed.TotalMilliseconds;
            if (stats.Source == 0) return null;

            clock.Restart();
            Dictionary<string, FileStamp> targetIndex = IndexDir(targetDir, null);
            stats.TargetMs = clock.Elapsed.TotalMilliseconds;
            List<string> stale = null;
            foreach (KeyValuePair<string, FileStamp> pair in targetIndex)
                if (IsTempName(pair.Key))
                {
                    if (stale == null) stale = new List<string>();
                    stale.Add(pair.Key);
                }
            for (int i = 0; stale != null && i < stale.Count; i++)
            {
                // 上次会话被杀在 copy 中途留下的 .wcptmp：清掉，免得越积越多。
                try { File.Delete(Path.Combine(targetDir, stale[i])); } catch { }
                targetIndex.Remove(stale[i]);
                stats.StaleTemp++;
            }
            stats.Target = targetIndex.Count;

            clock.Restart();
            List<string> todo = new List<string>();
            foreach (KeyValuePair<string, FileStamp> pair in sourceIndex)
            {
                // 保留设备名（aux.mp3 之类）在 Win32 层不可寻址，复制必然失败，
                // 但游戏自己也读不到 —— 单独归类，否则 failed 恒非 0、stamp 永不写。
                if (IsReservedDeviceName(pair.Key)) { stats.Ignored++; continue; }
                if (IsPresentIn(targetIndex, pair.Key, pair.Value)) stats.Skipped++;
                else todo.Add(pair.Key);
            }
            stats.CompareMs = clock.Elapsed.TotalMilliseconds;

            clock.Restart();
            for (int i = 0; i < todo.Count; i++)
            {
                string target = Path.Combine(targetDir, todo[i]);
                if (TryCopy(Path.Combine(sourceDir, todo[i]), target)) stats.Copied++;
                else stats.Failed++;
            }
            stats.CopyMs = clock.Elapsed.TotalMilliseconds;
            return stats;
        }
    }
}
