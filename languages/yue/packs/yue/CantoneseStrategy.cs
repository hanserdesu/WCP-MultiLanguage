// WCP Cantonese language pack strategy implementation.
// 符合 ARCHITECTURE-UNIFIED.md 统一架构契约。
using System;
using System.Collections.Generic;
using System.IO;
using System.Text.RegularExpressions;
using Mono.Data.Sqlite;
using WcpHost;

namespace WcpPack.Yue
{
    public sealed class CantoneseStrategy : ILanguageStrategy, IPackBoundStrategy
    {
        private sealed class PronRecord
        {
            internal string UkPhonic;
            internal string UsPhonic;
            internal string Meaning;
        }

        private static readonly IList<string> Probes = Array.AsReadOnly(
            new string[] { "食", "睇", "搞掂" });

        private readonly Dictionary<string, PronRecord> _pron =
            new Dictionary<string, PronRecord>(StringComparer.Ordinal);
        private readonly Dictionary<string, List<string>> _readings =
            new Dictionary<string, List<string>>(StringComparer.Ordinal);
        private StrategyContext _context;
        private bool _pronLoadAttempted;
        private string _pronLoadError;

        public string Language { get { return "yue"; } }

        public IList<string> RepairProbes { get { return Probes; } }

        public string LastLoadError { get { return _pronLoadError; } }

        public void BindPack(StrategyContext context)
        {
            if (context == null) throw new ArgumentNullException("context");
            if (!string.Equals(context.Language, Language, StringComparison.Ordinal))
                throw new InvalidOperationException("粤语策略收到其它语言 pack: " + context.Language);
            _context = context;
            _pron.Clear();
            _readings.Clear();
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
            if (text.Length < 1) return null;
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
            // 显示形可能是任意词条的粤语拼音（浏览页显示词与队列指针词不同）。
            // 指针词音频配显示词会静默放错音，故先走读音反查：
            // 拼音→词形，同音多形按 pack 音频存在性择优；反查不中才回指针词。
            List<string> candidates = ReadingCandidates(displayedForm.Trim());
            if (candidates != null)
            {
                string best = PickReadableForm(candidates);
                if (!string.IsNullOrEmpty(best)) return best;
            }
            // 反查不中: 按显示形原样查（宿主未命中会留日志），不静默配指针词的音。
            return displayedForm;
        }

        public bool ProvideMeaning(string word, out string meaning, out string phonic)
        {
            meaning = null;
            phonic = null;
            if (string.IsNullOrEmpty(word)) return false;
            EnsurePronLoaded();
            PronRecord rec;
            if (!_pron.TryGetValue(word, out rec) || rec == null) return false;

            meaning = rec.Meaning;
            phonic = !string.IsNullOrEmpty(rec.UkPhonic) ? rec.UkPhonic : rec.UsPhonic;
            return true;
        }

        private string EnrichedEntry(string word, string fallbackMeaning)
        {
            EnsurePronLoaded();
            PronRecord rec;
            if (_pron.TryGetValue(word, out rec) && !string.IsNullOrEmpty(rec.Meaning))
                return rec.Meaning;
            return fallbackMeaning ?? "";
        }

        private static string ReadingOf(string text)
        {
            if (string.IsNullOrEmpty(text)) return null;
            int open = text.IndexOf('[');
            if (open < 0) return null;
            int close = text.IndexOf(']', open + 1);
            if (close < 0) return null;
            return text.Substring(open + 1, close - open - 1).Trim();
        }

        private static string StripReading(string text)
        {
            if (string.IsNullOrEmpty(text)) return text;
            int open = text.IndexOf('[');
            if (open < 0) return text.Trim();
            int close = text.IndexOf(']', open + 1);
            if (close < 0) return text.Trim();
            return (text.Substring(0, open) + text.Substring(close + 1)).Trim();
        }

        private static string RemoveTranslationTail(string text)
        {
            int idx = text.LastIndexOf('（');
            if (idx >= 0 && text.EndsWith("）"))
                return text.Substring(0, idx).Trim();
            idx = text.LastIndexOf('(');
            if (idx >= 0 && text.EndsWith(")"))
                return text.Substring(0, idx).Trim();
            return text;
        }

        private void IndexReadings(string word, PronRecord rec)
        {
            if (string.IsNullOrEmpty(word) || rec == null) return;
            string viaUk = BracketReading(rec.UkPhonic);
            string viaUs = BracketReading(rec.UsPhonic);
            string viaMarker = ReadingOf(rec.Meaning);
            if (string.Equals(viaUs, viaUk, StringComparison.Ordinal)) viaUs = null;
            if (string.Equals(viaMarker, viaUk, StringComparison.Ordinal) ||
                string.Equals(viaMarker, viaUs, StringComparison.Ordinal)) viaMarker = null;
            AddReading(word, viaUk);
            AddReading(word, viaUs);
            AddReading(word, viaMarker);
        }

        private void AddReading(string word, string reading)
        {
            if (string.IsNullOrEmpty(reading)) return;
            if (string.Equals(reading, word, StringComparison.Ordinal)) return;
            List<string> bucket;
            if (!_readings.TryGetValue(reading, out bucket))
            {
                bucket = new List<string>();
                _readings[reading] = bucket;
            }
            if (!bucket.Contains(word)) bucket.Add(word);
        }

        private List<string> ReadingCandidates(string reading)
        {
            EnsurePronLoaded();
            if (_readings.Count == 0 || string.IsNullOrEmpty(reading)) return null;
            List<string> bucket;
            return _readings.TryGetValue(reading, out bucket) ? bucket : null;
        }

        private string PickReadableForm(List<string> candidates)
        {
            if (candidates == null || candidates.Count == 0) return null;
            if (candidates.Count == 1) return candidates[0];
            for (int i = 0; i < candidates.Count; i++)
                if (HasPackAudio(candidates[i])) return candidates[i];
            return candidates[0];
        }

        private bool HasPackAudio(string form)
        {
            if (string.IsNullOrEmpty(form) || _context == null ||
                string.IsNullOrEmpty(_context.WordAudioDir)) return false;
            try
            {
                return File.Exists(Path.Combine(_context.WordAudioDir, form + ".mp3")) ||
                       File.Exists(Path.Combine(_context.WordAudioDir, form + ".wav"));
            }
            catch (Exception)
            {
                return false;
            }
        }

        private static string BracketReading(string value)
        {
            if (string.IsNullOrEmpty(value)) return null;
            string v = value.Trim();
            if (v.Length >= 2 && v[0] == '[' && v[v.Length - 1] == ']')
                v = v.Substring(1, v.Length - 2).Trim();
            return v.Length == 0 ? null : v;
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

            string dbPath = _context.MeaningDbPath;
            if (!File.Exists(dbPath))
            {
                _pronLoadError = "找不到 meaning.sqlite: " + dbPath;
                return;
            }

            try
            {
                string cs = "Data Source=" + dbPath + ";Version=3;Read Only=True;";
                using (SqliteConnection conn = new SqliteConnection(cs))
                {
                    conn.Open();
                    using (SqliteCommand cmd = conn.CreateCommand())
                    {
                        cmd.CommandText = "SELECT word, ukPhonic, usPhonic, meaning FROM pron";
                        using (SqliteDataReader r = cmd.ExecuteReader())
                        {
                            while (r.Read())
                            {
                                string w = r.IsDBNull(0) ? null : r.GetString(0);
                                if (string.IsNullOrEmpty(w)) continue;
                                PronRecord rec = new PronRecord();
                                rec.UkPhonic = r.IsDBNull(1) ? "" : r.GetString(1);
                                rec.UsPhonic = r.IsDBNull(2) ? "" : r.GetString(2);
                                rec.Meaning = r.IsDBNull(3) ? "" : r.GetString(3);
                                _pron[w] = rec;
                                IndexReadings(w, rec);
                            }
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                _pron.Clear();
                _readings.Clear();
                _pronLoadError = "加载 SQLite 失败: " + ex.Message;
            }
        }
    }
}
