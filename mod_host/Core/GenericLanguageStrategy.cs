// WCP Host — resource-only language strategy.
//
// This strategy deliberately contains no language code or language-specific
// path.  BindPack supplies the language and all resource paths from the
// manifest.  Packs whose display/audio/meaning contract is the standard WCP
// shape can therefore use strategy.assembly="$host" and add data only.
using System;
using System.Collections.Generic;
using System.IO;
using System.Text.RegularExpressions;
using Mono.Data.Sqlite;

namespace WcpHost
{
    public sealed class GenericLanguageStrategy : ILanguageStrategy, IPackBoundStrategy
    {
        private sealed class PronRecord
        {
            internal string UkPhonic;
            internal string UsPhonic;
            internal string Meaning;
        }

        private static readonly IList<string> EmptyProbes =
            new List<string>().AsReadOnly();
        private static readonly Regex Tags = new Regex("<[^>]+>", RegexOptions.Compiled);
        private readonly Dictionary<string, PronRecord> _pron =
            new Dictionary<string, PronRecord>(StringComparer.Ordinal);
        private StrategyContext _context;
        private bool _pronLoadAttempted;
        private string _pronLoadError;

        public string Language
        {
            get { return _context == null ? null : _context.Language; }
        }

        public IList<string> RepairProbes
        {
            get { return _context == null ? EmptyProbes : _context.RepairProbes; }
        }

        public string LastLoadError { get { return _pronLoadError; } }

        public void BindPack(StrategyContext context)
        {
            if (context == null) throw new ArgumentNullException("context");
            if (string.IsNullOrEmpty(context.Language))
                throw new InvalidOperationException("资源策略收到空语言码");
            _context = context;
            _pron.Clear();
            _pronLoadAttempted = false;
            _pronLoadError = null;
        }

        public string ExtractSentenceKey(string renderedText)
        {
            if (string.IsNullOrEmpty(renderedText)) return null;
            string text = Tags.Replace(renderedText, "");
            text = text.Replace("例句：", "").Replace("例句:", "").Trim();
            int newline = text.IndexOfAny(new char[] { '\r', '\n' });
            if (newline >= 0) text = text.Substring(0, newline).Trim();
            if (text.Length == 0) return null;
            return RemoveTranslationTail(text);
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
            if (string.IsNullOrEmpty(meaning)) return meaning;
            string entry = EnrichedEntry(canonicalWord, meaning);
            string rest = StripReading(entry);
            return string.IsNullOrEmpty(rest) ? meaning : rest;
        }

        public string AudioLookupForm(string displayedForm, string canonicalWord)
        {
            return string.IsNullOrEmpty(canonicalWord) ? displayedForm : canonicalWord;
        }

        public bool ProvideMeaning(string word, out string meaning, out string phonic)
        {
            meaning = null;
            phonic = null;
            if (string.IsNullOrEmpty(word)) return false;
            PronRecord row = FindPron(word);
            if (row == null) return false;
            meaning = Clean(row.Meaning);
            phonic = NormalizePhonic(!string.IsNullOrEmpty(row.UkPhonic)
                ? row.UkPhonic : row.UsPhonic);
            return !string.IsNullOrEmpty(meaning) || !string.IsNullOrEmpty(phonic);
        }

        private string EnrichedEntry(string word, string supplied)
        {
            string clean = Clean(supplied);
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
            if (string.IsNullOrEmpty(word)) return null;
            PronRecord row;
            if (_pron.TryGetValue(word, out row)) return row;
            string lower = word.ToLowerInvariant();
            return lower != word && _pron.TryGetValue(lower, out row) ? row : null;
        }

        private void EnsurePronLoaded()
        {
            if (_pronLoadAttempted) return;
            _pronLoadAttempted = true;
            if (_context == null || string.IsNullOrEmpty(_context.MeaningDbPath))
            {
                _pronLoadError = "策略未绑定有效的 MeaningDbPath";
                return;
            }
            if (!File.Exists(_context.MeaningDbPath))
            {
                _pronLoadError = "找不到 meaning.sqlite: " + _context.MeaningDbPath;
                return;
            }

            try
            {
                using (SqliteConnection connection = new SqliteConnection(
                    "Data Source=" + _context.MeaningDbPath + ";Version=3;Read Only=True;"))
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
            string meaning = Clean(row.Meaning);
            string reading = NormalizePhonic(!string.IsNullOrEmpty(row.UkPhonic)
                ? row.UkPhonic : row.UsPhonic);
            if (string.IsNullOrEmpty(reading)) return meaning;
            if (string.IsNullOrEmpty(meaning)) return "【" + reading + "】";
            return "【" + reading + "】" + meaning;
        }

        private static string Clean(string value)
        {
            return string.IsNullOrEmpty(value) ? value : value.Replace("\\n", "\n").Trim();
        }

        private static bool HasReadingMarker(string entry)
        {
            return !string.IsNullOrEmpty(entry) &&
                (entry.IndexOf('【') >= 0 || entry.IndexOf('[') >= 0);
        }

        private static string ReadingOf(string entry)
        {
            string inside;
            if (!TryMarker(entry, '【', '】', out inside) &&
                !TryMarker(entry, '[', ']', out inside)) return null;
            return NormalizePhonic(inside);
        }

        private static string StripReading(string entry)
        {
            if (string.IsNullOrEmpty(entry)) return entry;
            string inside;
            int start;
            int end;
            if (!TryMarker(entry, '【', '】', out inside, out start, out end) &&
                !TryMarker(entry, '[', ']', out inside, out start, out end))
                return entry.Trim();
            return (entry.Substring(0, start) + entry.Substring(end + 1)).Trim();
        }

        private static bool TryMarker(string entry, char left, char right, out string inside)
        {
            int start;
            int end;
            return TryMarker(entry, left, right, out inside, out start, out end);
        }

        private static bool TryMarker(string entry, char left, char right,
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

        private static string RemoveTranslationTail(string text)
        {
            int full = text.LastIndexOf('（');
            if (full >= 0 && text.EndsWith("）") && IsTranslationTail(text.Substring(full + 1, text.Length - full - 2)))
                return text.Substring(0, full).Trim();
            int normal = text.LastIndexOf('(');
            if (normal >= 0 && text.EndsWith(")") && IsTranslationTail(text.Substring(normal + 1, text.Length - normal - 2)))
                return text.Substring(0, normal).Trim();
            return text;
        }

        private static bool IsTranslationTail(string tail)
        {
            if (string.IsNullOrWhiteSpace(tail)) return false;
            for (int i = 0; i < tail.Length; i++)
            {
                char c = tail[i];
                if ((c >= '\u3400' && c <= '\u9fff') || (c >= '\u3040' && c <= '\u30ff'))
                    return true;
            }
            bool digit = false;
            bool letter = false;
            for (int i = 0; i < tail.Length; i++)
            {
                digit = digit || char.IsDigit(tail[i]);
                letter = letter || char.IsLetter(tail[i]);
            }
            return digit && letter;
        }
    }
}
