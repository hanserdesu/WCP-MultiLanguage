// Shared identity registry for the portable WCP word-book plugins.
//
// 生成物 — 不要手改。
//   事实来源: D:/ATooManyLanguage/Japanese/packs/<lang>/manifest.json
//   重新生成: python tools/gen_bookprofiles.py --write
//   漂移检查: python tools/gen_bookprofiles.py --check
//
// 以前这份注册表在 4 个项目里各有一份手抄副本（法语/俄语项目内部还各 3 份），
// 加一种语言就得同步改 N 处 —— 2026-09-14 实测漂移: 日语与法语项目的副本
// 只登记 ja+fr，缺 ru。改成从清单生成后，「加一种语言」只需要新增一个
// packs/<lang>/manifest.json，不必重编译任何现有语言的 DLL。
//
// FingerprintOf 必须与 mod_host/Core/Manifest.cs 逐字节一致。

using System;
using System.Collections.Generic;
using System.Security.Cryptography;
using System.Text;

namespace WcpBookProfiles
{
    internal sealed class BookProfile
    {
        internal readonly string Id;
        internal readonly string Language;
        internal readonly string DisplayName;
        internal readonly int WordCount;
        internal readonly string Fingerprint;

        internal BookProfile(string id, string language, string displayName,
                             int wordCount, string fingerprint)
        {
            Id = id;
            Language = language;
            DisplayName = displayName;
            WordCount = wordCount;
            Fingerprint = fingerprint;
        }
    }

    internal static class BookProfiles
    {
        internal const string Japanese = "ja";
        internal const string French = "fr";
        internal const string Russian = "ru";
        internal const string German = "de";
        internal const string Cantonese = "yue";

        // Fingerprints are SHA256 over the sorted full word-form set, so a book
        // matches in any custom slot. Registering every managed book here lets a
        // plugin positively identify — and therefore never touch — the others'.
        internal static readonly BookProfile[] All = new BookProfile[]
        {
            new BookProfile("catbar-jlpt-complete", Japanese, "日语词库(猫条版)", 7922,
                "6d7a51c0c5d30dd63d8a6e3412bce1cf2419554fb8487cf5c8a205e43ac41663"),
            new BookProfile("catbar-french-cefr-complete", French, "法语词库(猫条版)", 8116,
                "376af2eae0292052cefb4cb0d673f48a5ca480a38e25a6bf5353998caea17e9d"),
            new BookProfile("catbar-russian-cefr-complete", Russian, "俄语词库(猫条版)", 8451,
                "dfecb0ab75e9b3ef75aedd47c677d68594b060bfbb84cc6bd94efd7888f4b74e"),
            new BookProfile("catbar-german-complete", German, "德语词库(猫条版)", 8062,
                "66bded175dee70d9fd18ac3e08e793b79b35e9fd750904367a16c6012dd1f70a"),
            new BookProfile("catbar-cantonese-complete", Cantonese, "粤语词库(猫条版)", 384,
                "0748ca590e7caf6c2d11e5062ee381e2a3e1ac84f943c561a4fed94568f0cb9e"),
        };

        internal static BookProfile Match(IList<string> words)
        {
            if (words == null || words.Count == 0) return null;
            string hash = null;
            for (int i = 0; i < All.Length; i++)
            {
                BookProfile p = All[i];
                if (words.Count != p.WordCount) continue;
                if (hash == null) hash = FingerprintOf(words);
                if (hash == p.Fingerprint) return p;
            }
            return null;
        }

        internal static bool IsManagedDisplayName(string text)
        {
            if (string.IsNullOrEmpty(text)) return false;
            for (int i = 0; i < All.Length; i++)
                if (text.StartsWith(All[i].DisplayName, StringComparison.Ordinal)) return true;
            return false;
        }

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
