// WCP Japanese language pack — language-specific behavior only.
//
// This assembly deliberately has no Harmony patch points. The host owns the
// game hooks and injects StrategyContext after validating the manifest.
using System;
using System.Collections.Generic;
using System.IO;
using System.Text.RegularExpressions;
using Mono.Data.Sqlite;
using WcpHost;

namespace WcpPack.Ja
{
    public sealed class JapaneseStrategy : ILanguageStrategy, IPackBoundStrategy
    {
        private sealed class PronRecord
        {
            internal string UkPhonic;
            internal string UsPhonic;
            internal string Meaning;
        }

        private static readonly IList<string> Probes = Array.AsReadOnly(
            new string[] { "歯医者", "続ける", "工業" });

        private readonly Dictionary<string, PronRecord> _pron =
            new Dictionary<string, PronRecord>(StringComparer.Ordinal);
        private StrategyContext _context;
        private bool _pronLoadAttempted;
        private string _pronLoadError;

        public string Language { get { return "ja"; } }

        public IList<string> RepairProbes { get { return Probes; } }

        public string LastLoadError { get { return _pronLoadError; } }

        public void BindPack(StrategyContext context)
        {
            if (context == null) throw new ArgumentNullException("context");
            if (!string.Equals(context.Language, Language, StringComparison.Ordinal))
                throw new InvalidOperationException("日语策略收到其它语言 pack: " + context.Language);
            _context = context;
            _pron.Clear();
            _pronLoadAttempted = false;
            _pronLoadError = null;
        }

        public string ExtractSentenceKey(string renderedText)
        {
            if (string.IsNullOrEmpty(renderedText)) return null;
            string text = Regex.Replace(renderedText, "<[^>]+>", "");
            text = text.Replace("例句：", "").Replace("例句:", "").Trim();
            int newline = text.IndexOfAny(new char[] { '\r', '\n' });
            if (newline >= 0) text = text.Substring(0, newline).Trim();
            if (text.Length == 0) return null;

            text = RemoveTranslationTail(text);
            if (text.Length < 2 || !HasJapaneseScript(text)) return null;
            return text;
        }

        public string StemDisplay(string canonicalWord, string meaning)
        {
            if (string.IsNullOrEmpty(canonicalWord)) return canonicalWord;
            string entry = EnrichedEntry(canonicalWord, meaning);
            string reading = ReadingOf(entry);
            return string.IsNullOrEmpty(reading) ? canonicalWord : reading;
        }

        public string OptionDisplay(string canonicalWord, string meaning)
        {
            if (string.IsNullOrEmpty(canonicalWord) || string.IsNullOrEmpty(meaning))
                return meaning;

            string entry = EnrichedEntry(canonicalWord, meaning);
            string rest = StripReading(entry);
            if (string.IsNullOrEmpty(rest)) return meaning;
            if (rest.StartsWith(canonicalWord, StringComparison.Ordinal)) return rest;
            return canonicalWord + " " + rest;
        }

        public string AudioLookupForm(string displayedForm, string canonicalWord)
        {
            if (string.IsNullOrEmpty(displayedForm)) return canonicalWord;
            if (string.IsNullOrEmpty(canonicalWord)) return displayedForm;
            string shown = displayedForm.Trim();
            if (IsKanaOnly(shown))
            {
                string reading = ReadingOf(EnrichedEntry(canonicalWord, null));
                if (string.Equals(reading, shown, StringComparison.Ordinal))
                    return canonicalWord;
            }
            return displayedForm;
        }

        public bool ProvideMeaning(string word, out string meaning, out string phonic)
        {
            meaning = null;
            phonic = null;
            if (string.IsNullOrEmpty(word)) return false;
            PronRecord row = FindPron(word);
            if (row == null) return false;

            meaning = CleanEntry(row.Meaning);
            phonic = NormalizePhonic(!string.IsNullOrEmpty(row.UkPhonic)
                ? row.UkPhonic : row.UsPhonic);
            if (string.IsNullOrEmpty(phonic) && IsKanaOnly(word)) phonic = word;
            return !string.IsNullOrEmpty(meaning) || !string.IsNullOrEmpty(phonic);
        }

        private string EnrichedEntry(string word, string supplied)
        {
            string clean = CleanEntry(supplied);
            if (!string.IsNullOrEmpty(clean) && HasReadingMarker(clean)) return clean;
            PronRecord row = FindPron(word);
            if (row != null)
            {
                string entry = ComposeEntry(row);
                if (!string.IsNullOrEmpty(entry)) return entry;
            }
            return clean;
        }

        private PronRecord FindPron(string word)
        {
            EnsurePronLoaded();
            if (_pron.Count == 0 || string.IsNullOrEmpty(word)) return null;
            PronRecord row;
            if (_pron.TryGetValue(word, out row)) return row;
            string lower = word.ToLowerInvariant();
            if (lower != word && _pron.TryGetValue(lower, out row)) return row;
            return null;
        }

        private void EnsurePronLoaded()
        {
            if (_pronLoadAttempted) return;
            _pronLoadAttempted = true;
            if (_context == null || string.IsNullOrEmpty(_context.MeaningDbPath) ||
                !File.Exists(_context.MeaningDbPath)) return;

            try
            {
                using (SqliteConnection connection = new SqliteConnection(
                    "URI=file:" + _context.MeaningDbPath))
                {
                    connection.Open();
                    using (SqliteCommand command = connection.CreateCommand())
                    {
                        command.CommandText =
                            "SELECT word, ukPhonic, usPhonic, meaning FROM pron";
                        using (SqliteDataReader reader = command.ExecuteReader())
                        {
                            while (reader.Read())
                            {
                                string word = ReadText(reader, 0);
                                if (string.IsNullOrEmpty(word)) continue;
                                _pron[word] = new PronRecord {
                                    UkPhonic = ReadText(reader, 1),
                                    UsPhonic = ReadText(reader, 2),
                                    Meaning = ReadText(reader, 3)
                                };
                            }
                        }
                    }
                }
            }
            catch (Exception e)
            {
                // A missing/corrupt pack is a strategy miss, never a reason to
                // fall back to the shared game database or another language.
                _pron.Clear();
                _pronLoadError = e.GetType().FullName + ": " + e.Message;
            }
        }

        private static string ReadText(SqliteDataReader reader, int ordinal)
        {
            return reader.IsDBNull(ordinal) ? null : reader.GetValue(ordinal).ToString();
        }

        private static string ComposeEntry(PronRecord row)
        {
            if (row == null) return null;
            string meaning = CleanEntry(row.Meaning);
            string reading = NormalizePhonic(!string.IsNullOrEmpty(row.UkPhonic)
                ? row.UkPhonic : row.UsPhonic);
            if (string.IsNullOrEmpty(reading)) return meaning;
            if (string.IsNullOrEmpty(meaning)) return "【" + reading + "】";
            return "【" + reading + "】" + meaning;
        }

        private static string CleanEntry(string value)
        {
            if (string.IsNullOrEmpty(value)) return value;
            return value.Replace("\\n", "\n").Trim();
        }

        private static bool HasReadingMarker(string entry)
        {
            if (string.IsNullOrEmpty(entry)) return false;
            return entry.IndexOf('【') >= 0 || entry.IndexOf('[') >= 0;
        }

        private static string ReadingOf(string entry)
        {
            string inside;
            if (!TryReadMarker(entry, '【', '】', out inside) &&
                !TryReadMarker(entry, '[', ']', out inside)) return null;
            inside = inside.Trim();
            return IsKanaOnly(inside) ? inside : null;
        }

        private static string StripReading(string entry)
        {
            string inside;
            int start;
            int end;
            if (!TryReadMarker(entry, '【', '】', out inside, out start, out end) &&
                !TryReadMarker(entry, '[', ']', out inside, out start, out end)) return null;
            string rest = (entry.Substring(0, start) + entry.Substring(end + 1)).Trim();
            return rest.Length == 0 ? null : rest;
        }

        private static bool TryReadMarker(string entry, char left, char right,
                                          out string inside)
        {
            int start;
            int end;
            return TryReadMarker(entry, left, right, out inside, out start, out end);
        }

        private static bool TryReadMarker(string entry, char left, char right,
                                          out string inside, out int start, out int end)
        {
            inside = null;
            start = -1;
            end = -1;
            if (string.IsNullOrEmpty(entry)) return false;
            start = entry.IndexOf(left);
            if (start < 0) return false;
            end = entry.IndexOf(right, start + 1);
            if (end <= start) return false;
            inside = entry.Substring(start + 1, end - start - 1);
            return true;
        }

        private static string NormalizePhonic(string value)
        {
            if (string.IsNullOrEmpty(value)) return null;
            string result = value.Trim();
            if (result.Length >= 2 &&
                ((result[0] == '[' && result[result.Length - 1] == ']') ||
                 (result[0] == '【' && result[result.Length - 1] == '】')))
                result = result.Substring(1, result.Length - 2).Trim();
            return result.Length == 0 ? null : result;
        }

        private static bool IsKanaOnly(string value)
        {
            if (string.IsNullOrEmpty(value)) return false;
            for (int i = 0; i < value.Length; i++)
            {
                char c = value[i];
                bool ok = (c >= 0x3040 && c <= 0x30FF) ||
                          c == 0x30FB || c == 0x30FC || c == 0x3099 ||
                          c == 0x309A || c == 0x309B || c == 0x309C ||
                          (c >= 0xFF66 && c <= 0xFF9F) || c == ' ' ||
                          c == '.' || c == 0x3000 || c == '-';
                if (!ok) return false;
            }
            return true;
        }

        private static string RemoveTranslationTail(string value)
        {
            if (string.IsNullOrEmpty(value) || value[value.Length - 1] != '）')
                return value;

            List<int> candidates = new List<int>();
            for (int i = 1; i < value.Length - 1; i++)
            {
                if (value[i] != '（' || !BalancedTail(value, i)) continue;
                string prefix = value.Substring(0, i).Trim();
                string suffix = value.Substring(i + 1, value.Length - i - 2);
                if (!HasJapaneseScript(prefix) || HasKana(suffix)) continue;
                candidates.Add(i);
                if (EndsSentence(prefix)) return prefix;
            }
            if (candidates.Count > 0)
                return value.Substring(0, candidates[0]).Trim();
            return value;
        }

        private static bool BalancedTail(string value, int start)
        {
            int depth = 0;
            for (int i = start; i < value.Length; i++)
            {
                if (value[i] == '（') depth++;
                else if (value[i] == '）')
                {
                    depth--;
                    if (depth < 0) return false;
                }
            }
            return depth == 0;
        }

        private static bool EndsSentence(string value)
        {
            if (string.IsNullOrEmpty(value)) return false;
            int i = value.Length - 1;
            while (i >= 0 && (value[i] == '」' || value[i] == '』' ||
                              value[i] == '）' || value[i] == ' ')) i--;
            return i >= 0 && (value[i] == '。' || value[i] == '！' ||
                              value[i] == '？' || value[i] == '!' ||
                              value[i] == '?');
        }

        private static bool HasJapaneseScript(string value)
        {
            if (string.IsNullOrEmpty(value)) return false;
            for (int i = 0; i < value.Length; i++)
            {
                char c = value[i];
                if ((c >= 0x3040 && c <= 0x30FF) ||
                    (c >= 0x3400 && c <= 0x4DBF) ||
                    (c >= 0x4E00 && c <= 0x9FFF) ||
                    (c >= 0xF900 && c <= 0xFAFF) ||
                    (c >= 0xFF66 && c <= 0xFF9D) ||
                    c == 0x3005 || c == 0x3006 || c == 0x3007) return true;
            }
            return false;
        }

        private static bool HasKana(string value)
        {
            if (string.IsNullOrEmpty(value)) return false;
            for (int i = 0; i < value.Length; i++)
            {
                char c = value[i];
                if ((c >= 0x3040 && c <= 0x30FF) ||
                    (c >= 0xFF66 && c <= 0xFF9F)) return true;
            }
            return false;
        }
    }
}
