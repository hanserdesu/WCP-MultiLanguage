// WCP Host Core — 语言包清单与身份注册表
//
// 与 mod_book_name/BookProfiles.cs 的关系:
//   · 指纹算法（SHA-256 over 排序后的全词形集合，'\n' 连接）**逐字节保持不变**，
//     见 FingerprintOf()。任何改动都会让已导入的词书全部失配。
//   · 区别在于注册表不再硬编码进 DLL，而是从 packs/*/manifest.json 读。
//     这就是"加一种语言不需要重编译其它语言的 DLL"的实现。
//
// 关键语义（2026-09-14 实测确认）:
//   一个语言包 = 一个 SlotProfile = 一条 BookProfile。
//   manifest.books 里可以列多个 xlsx 片段（法语/俄语各 3 个分册），
//   游戏导入后并成一个槽位，fingerprint 是对**并集**算的。
//   实测存档: 槽1=7922(ja) 槽2=8116(fr) 槽3=8451(ru) 槽4=空。
using System;
using System.Collections.Generic;
using System.IO;
using System.Security.Cryptography;
using System.Text;

namespace WcpHost
{
    internal sealed class BookProfile
    {
        internal readonly string Id;
        internal readonly string Language;
        internal readonly string DisplayName;
        internal readonly int WordCount;
        internal readonly string Fingerprint;
        internal readonly int ObservedSlot;
        internal readonly string Es3Prefix;

        internal BookProfile(string id, string language, string displayName, int wordCount,
                             string fingerprint, int observedSlot, string es3Prefix)
        {
            Id = id;
            Language = language;
            DisplayName = displayName;
            WordCount = wordCount;
            Fingerprint = fingerprint;
            ObservedSlot = observedSlot;
            Es3Prefix = es3Prefix;
        }
    }

    internal sealed class LanguageManifest
    {
        internal int Schema;
        internal BookProfile Profile;
        internal string PackRoot;                    // 本 pack 目录（绝对路径）
        internal string ManifestPath;
        internal List<string> Books = new List<string>();
        internal string MeaningDb;
        internal string SentenceTable;
        internal string Repair;
        internal string WordAudioDir;
        internal string SentenceAudioDir;
        internal List<string> RepairProbes = new List<string>();
        internal string StrategyAssembly;
        internal string StrategyType;

        // 「宿主真的能服务这门语言」的判据: 清单声明的资源必须实际存在。
        // 只看 manifest.json 会让"半装"的语言包把旧词表插件挤走 —— 那门语言随后
        // 既没有宿主的释义库, 也没有旧插件的兜底。接管的前提是接管方真的有资源。
        internal bool ResourcesReady(out string missing)
        {
            missing = null;
            string[] rel = new string[] { MeaningDb, SentenceTable, Repair };
            for (int i = 0; i < rel.Length; i++)
            {
                if (string.IsNullOrEmpty(rel[i])) continue;
                if (!File.Exists(LocalPath(rel[i]))) { missing = rel[i]; return false; }
            }
            for (int i = 0; i < Books.Count; i++)
            {
                if (!File.Exists(LocalPath(Books[i]))) { missing = Books[i]; return false; }
            }
            return true;
        }

        private string LocalPath(string rel)
        {
            return Path.Combine(PackRoot, rel.Replace('/', Path.DirectorySeparatorChar));
        }

        internal static LanguageManifest Load(string manifestPath)
        {
            string json = File.ReadAllText(manifestPath, Encoding.UTF8);
            Dictionary<string, object> root = Json.AsDict(Json.Parse(json));

            LanguageManifest m = new LanguageManifest();
            m.ManifestPath = manifestPath;
            m.PackRoot = Path.GetDirectoryName(Path.GetFullPath(manifestPath));
            m.Schema = Json.Int(root, "schema", 0);

            m.Profile = new BookProfile(
                Json.Str(root, "profile_id", null),
                Json.Str(root, "language", null),
                Json.Str(root, "display_name", null),
                Json.Int(root, "word_count", 0),
                Json.Str(root, "fingerprint_sha256", null),
                Json.Int(root, "observed_slot", 0),
                Json.Str(root, "es3_prefix", Json.Str(root, "language", "xx")));

            if (m.Profile.Id == null || m.Profile.Language == null || m.Profile.Fingerprint == null)
                throw new FormatException("manifest 缺 profile_id/language/fingerprint_sha256: " + manifestPath);

            Dictionary<string, object> res = Json.Sub(root, "resources");
            m.Books = Json.StrList(res, "books");
            m.MeaningDb = Json.Str(res, "meaning_db", null);
            m.SentenceTable = Json.Str(res, "sentence_table", null);
            m.Repair = Json.Str(res, "repair", null);
            m.WordAudioDir = Json.Str(res, "word_audio", null);
            m.SentenceAudioDir = Json.Str(res, "sentence_audio", null);

            m.RepairProbes = Json.StrList(root, "repair_probes");

            Dictionary<string, object> st = Json.Sub(root, "strategy");
            m.StrategyAssembly = Json.Str(st, "assembly", null);
            m.StrategyType = Json.Str(st, "type", null);

            Validate(m);
            return m;
        }

        internal string Resolve(string relative)
        {
            if (string.IsNullOrEmpty(relative)) return null;
            // Pack manifests are data, not an escape hatch to arbitrary host paths.
            // A malformed or malicious path must make that resource unavailable.
            if (Path.IsPathRooted(relative)) return null;
            string normalized = relative.Replace('/', Path.DirectorySeparatorChar)
                                        .Replace('\\', Path.DirectorySeparatorChar);
            string path = Path.GetFullPath(Path.Combine(PackRoot, normalized));
            string root = PackRoot.TrimEnd(Path.DirectorySeparatorChar,
                                           Path.AltDirectorySeparatorChar) +
                          Path.DirectorySeparatorChar;
            if (!path.StartsWith(root, StringComparison.OrdinalIgnoreCase) &&
                !string.Equals(path, PackRoot, StringComparison.OrdinalIgnoreCase))
                return null;
            return path;
        }

        internal bool Matches(IList<string> words)
        {
            if (words == null || words.Count == 0) return false;
            if (words.Count != Profile.WordCount) return false;
            return BookRegistry.FingerprintOf(words) == Profile.Fingerprint;
        }

        private static void Validate(LanguageManifest m)
        {
            if (m.Schema != 1) throw new FormatException("不支持的 manifest schema: " + m.Schema);
            if (m.Profile == null || string.IsNullOrEmpty(m.Profile.Id) ||
                string.IsNullOrEmpty(m.Profile.Language) ||
                string.IsNullOrEmpty(m.Profile.DisplayName))
                throw new FormatException("manifest 身份字段不完整");
            if (m.Profile.WordCount <= 0)
                throw new FormatException("word_count 必须为正数: " + m.Profile.Id);
            if (m.Profile.ObservedSlot < 0 || m.Profile.ObservedSlot > 4)
                throw new FormatException("observed_slot 必须在 0..4（0=未分配槽位）: " + m.Profile.Id);
            if (m.Profile.Fingerprint == null || m.Profile.Fingerprint.Length != 64)
                throw new FormatException("fingerprint_sha256 长度不是 64: " + m.Profile.Id);
            for (int i = 0; i < m.Profile.Fingerprint.Length; i++)
            {
                char c = m.Profile.Fingerprint[i];
                bool hex = (c >= '0' && c <= '9') ||
                           (c >= 'a' && c <= 'f');
                if (!hex) throw new FormatException("fingerprint_sha256 不是小写十六进制: " + m.Profile.Id);
            }
            if (string.IsNullOrEmpty(m.Profile.Es3Prefix))
                throw new FormatException("es3_prefix 不能为空: " + m.Profile.Id);
            if (m.Books == null || m.Books.Count == 0)
                throw new FormatException("resources.books 为空: " + m.Profile.Id);
            RequireInside(m, m.MeaningDb, "meaning_db");
            RequireInside(m, m.SentenceTable, "sentence_table");
            RequireInside(m, m.Repair, "repair");
            RequireInside(m, m.WordAudioDir, "word_audio");
            RequireInside(m, m.SentenceAudioDir, "sentence_audio");
            for (int i = 0; i < m.Books.Count; i++)
                RequireInside(m, m.Books[i], "books[" + i + "]");
            if (string.IsNullOrEmpty(m.StrategyAssembly) || string.IsNullOrEmpty(m.StrategyType))
                throw new FormatException("strategy 未声明完整: " + m.Profile.Id);
            // $host selects the language-neutral strategy shipped by WcpHost.
            // It is the resource-only extension point: a new pack can provide
            // manifest/data/audio without copying a language DLL.
            if (!string.Equals(m.StrategyAssembly, "$host", StringComparison.Ordinal))
                RequireInside(m, m.StrategyAssembly, "strategy.assembly");
        }

        private static void RequireInside(LanguageManifest m, string relative, string field)
        {
            if (string.IsNullOrEmpty(relative) || m.Resolve(relative) == null)
                throw new FormatException(field + " 必须是 pack 内相对路径: " + m.Profile.Id);
        }
    }

    internal sealed class BookRegistry
    {
        private readonly List<LanguageManifest> _manifests = new List<LanguageManifest>();
        private readonly List<string> _errors = new List<string>();
        private readonly List<string> _warnings = new List<string>();

        internal IList<LanguageManifest> Manifests { get { return _manifests; } }
        internal IList<string> Errors { get { return _errors; } }
        // 告警不丢包：注册表里"能装多少语言"不该受游戏 4 个原生槽限制。
        internal IList<string> Warnings { get { return _warnings; } }

        // 扫描 <packsRoot>/<lang>/manifest.json。单个 pack 坏掉不影响其它 pack 加载
        // —— 这是宿主对语言包唯一的容错要求：一种语言的数据坏了，别的语言照常用。
        internal static BookRegistry Load(string packsRoot)
        {
            BookRegistry r = new BookRegistry();
            if (string.IsNullOrEmpty(packsRoot) || !Directory.Exists(packsRoot))
            {
                r._errors.Add("packs 根目录不存在: " + packsRoot);
                return r;
            }
            string[] dirs = Directory.GetDirectories(packsRoot);
            Array.Sort(dirs, StringComparer.Ordinal);
            for (int i = 0; i < dirs.Length; i++)
            {
                string mp = Path.Combine(dirs[i], "manifest.json");
                if (!File.Exists(mp)) continue;
                try
                {
                    LanguageManifest m = LanguageManifest.Load(mp);
                    // word_count is only a fast Match prefilter, not an identity key:
                    // two different books may legitimately contain the same number of words.
                    for (int j = 0; j < r._manifests.Count; j++)
                    {
                        BookProfile old = r._manifests[j].Profile;
                        if (old.Id == m.Profile.Id)
                            throw new FormatException("profile_id 重复: " + m.Profile.Id);
                        if (old.Language == m.Profile.Language)
                            throw new FormatException("language 重复: " + m.Profile.Language);
                        if (old.Fingerprint == m.Profile.Fingerprint)
                            throw new FormatException("fingerprint 重复: " + m.Profile.Fingerprint);
                        if (m.Profile.ObservedSlot > 0 &&
                            old.ObservedSlot == m.Profile.ObservedSlot)
                            // observed_slot 只记录"在哪台机器的哪个原生槽里见过", 不是身份键。
                            // 游戏只有 4 个原生槽, 装到第 5 种语言必然撞槽 —— 撞槽只登记告警,
                            // 谁也不丢(身份判定始终只看指纹, 实际槽位由运行时决定)。
                            r._warnings.Add("observed_slot 撞槽 " + m.Profile.ObservedSlot +
                                            ": " + old.Language + " / " + m.Profile.Language +
                                            "（不丢包, 槽位按指纹运行时判定）");
                        if (old.Es3Prefix == m.Profile.Es3Prefix)
                            throw new FormatException("es3_prefix 重复: " + m.Profile.Es3Prefix);
                    }
                    r._manifests.Add(m);
                }
                catch (Exception e)
                {
                    r._errors.Add(Path.GetFileName(dirs[i]) + ": " + e.Message);
                }
            }
            return r;
        }

        // 与 BookProfiles.Match 语义一致（先比词数再算哈希，避免无谓的重哈希）
        internal BookProfile Match(IList<string> words)
        {
            if (words == null || words.Count == 0) return null;
            string hash = null;
            for (int i = 0; i < _manifests.Count; i++)
            {
                BookProfile p = _manifests[i].Profile;
                if (words.Count != p.WordCount) continue;
                if (hash == null) hash = FingerprintOf(words);
                if (hash == p.Fingerprint) return p;
            }
            return null;
        }

        internal LanguageManifest ByProfileId(string id)
        {
            for (int i = 0; i < _manifests.Count; i++)
                if (_manifests[i].Profile.Id == id) return _manifests[i];
            return null;
        }

        internal LanguageManifest ByLanguage(string lang)
        {
            for (int i = 0; i < _manifests.Count; i++)
                if (_manifests[i].Profile.Language == lang) return _manifests[i];
            return null;
        }

        // 槽位预算：游戏硬上限是同时导入的自定义槽数，而不是 pack
        // 注册表目录数。observed_slot=0 的 pack 是可随时导入到任一空槽的
        // 候选包；实际槽位仍由 Host.Evaluate 读取的词表指纹决定。
        internal bool SlotBudgetOk(out string detail)
        {
            HashSet<int> used = new HashSet<int>();
            for (int i = 0; i < _manifests.Count; i++)
            {
                int s = _manifests[i].Profile.ObservedSlot;
                if (s > 0) used.Add(s);
            }
            detail = _manifests.Count + " 个语言包 / 4 槽，注册表预分配 " +
                     used.Count + " 槽（0=候选包）";
            return used.Count <= 4;
        }

        // ── 指纹算法：必须与 mod_book_name/BookProfiles.cs 逐字节一致 ──
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
}
