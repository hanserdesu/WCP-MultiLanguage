// WCP Host Core — pack 例句表（宿主自服务）
//
// 为什么需要这一层:
//   游戏的两条例句通路都只认 wcpFullEng.db 的 sentence2 表:
//     DatabaseManagerS8.OnSearchButtonClick  → SELECT sentences FROM sentence2 WHERE word=@w
//     SentenceReplyManager.StartThis         → 解析渲染文本里的 「例句N：…释义：」
//   语言资源隔离落地后，各语言插件默认不再写共享库（AllowSharedDatabaseWrites=false），
//   库里只剩英语 → 任何受管词书的例句都查不到，表现为「【例句】区空白 + 日志 没有例句」。
//   释义由策略 ProvideMeaning（meaning.sqlite）兜住，例句原本由写库兜住 —— 这一层就是
//   把例句也搬进宿主，从此不再依赖游戏 DB。
//
// 数据来源 = manifest.resources.sentence_table → packs/<lang>/db/sentences.json
//   { "schema": 1, "sentences": { "<词>": ["例句：原文（译文）", ...] } }
//   串的格式与旧插件写入 sentence2 的值逐字节一致，宿主直接复用游戏自己的三段 Replace 变换。
//
// 职责边界: 只读 + 只缓存 + 只服务当前激活语言包。未激活/文件缺失/解析失败一律返回 false，
// 宿主保持游戏原状（fail-closed），绝不回退到别的语言或写游戏库。
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;

namespace WcpHost
{
    internal sealed class SentenceTable
    {
        private readonly string _path;
        private Dictionary<string, List<string>> _rows;
        private bool _attempted;
        private string _error;
        private double _loadMs;

        internal SentenceTable(string path)
        {
            _path = path;
        }

        internal string Path { get { return _path; } }
        internal string LastError { get { return _error; } }
        internal double LoadMs { get { return _loadMs; } }

        internal int RowCount
        {
            get { EnsureLoaded(); return _rows == null ? 0 : _rows.Count; }
        }

        /// <summary>按词取例句（DB 磁盘格式，未做游戏侧 Replace）。取不到返回 false。</summary>
        internal bool TryGet(string word, out List<string> sentences)
        {
            sentences = null;
            if (string.IsNullOrEmpty(word)) return false;
            EnsureLoaded();
            if (_rows == null) return false;

            List<string> hit;
            if (_rows.TryGetValue(word, out hit)) { sentences = hit; return true; }
            // 与 ProvideMeaning 同规则: 精确优先，再退一次小写。
            string lower = word.ToLowerInvariant();
            if (lower != word && _rows.TryGetValue(lower, out hit)) { sentences = hit; return true; }
            return false;
        }

        // 例句表存在两代形状，宿主都必须吃下:
        //   ① DB 磁盘行（旧插件写库用的格式）: "例句：<原文>（<译文>）"
        //   ② 结构化对象（粤语 pack 的写出形状）: { "sentence": …, "translate": … }
        // ② 组合成 ① 是**逐字节还原**，不是发明: yue 的 db/repair.tsv 里存的正是
        //   "例句：佢哋兩個做嘢態度都係一擔擔。（keoi5 …）" 这种带拼音括注的串。
        // 认不出的形状返回 null 被丢弃 —— 宁可该词没有例句，也不把对象 ToString 灌进界面。
        private static string EntryToDbRow(object entry)
        {
            string asText = entry as string;
            if (!string.IsNullOrEmpty(asText)) return asText;

            Dictionary<string, object> row = entry as Dictionary<string, object>;
            if (row == null) return null;
            string sentence = Json.Str(row, "sentence", null);
            if (string.IsNullOrEmpty(sentence)) return null;
            if (sentence.StartsWith("例句：", StringComparison.Ordinal)) return sentence;

            string translation = Json.Str(row, "translate", null);
            if (string.IsNullOrEmpty(translation)) translation = Json.Str(row, "translation", null);
            if (string.IsNullOrEmpty(translation)) return sentence;
            return "例句：" + sentence + "（" + translation + "）";
        }

        private void EnsureLoaded()
        {            if (_attempted) return;
            _attempted = true;

            if (string.IsNullOrEmpty(_path))
            {
                _error = "manifest 未声明 sentence_table";
                return;
            }
            if (!File.Exists(_path))
            {
                _error = "找不到例句表: " + _path;
                return;
            }

            try
            {
                DateTime t0 = DateTime.UtcNow;
                string text = File.ReadAllText(_path, Encoding.UTF8);
                Dictionary<string, object> root = Json.AsDict(Json.Parse(text));
                Dictionary<string, object> rows = Json.Sub(root, "sentences");
                if (rows == null)
                {
                    _error = "例句表缺少 sentences 段: " + _path;
                    return;
                }

                Dictionary<string, List<string>> table =
                    new Dictionary<string, List<string>>(rows.Count, StringComparer.Ordinal);
                foreach (KeyValuePair<string, object> kv in rows)
                {
                    if (string.IsNullOrEmpty(kv.Key) || kv.Value == null) continue;
                    List<object> arr = kv.Value as List<object>;
                    if (arr == null || arr.Count == 0) continue;
                    List<string> items = new List<string>(arr.Count);
                    for (int i = 0; i < arr.Count; i++)
                    {
                        string s = EntryToDbRow(arr[i]);
                        if (!string.IsNullOrEmpty(s)) items.Add(s);
                    }
                    if (items.Count > 0) table[kv.Key] = items;
                }
                _rows = table;
                _loadMs = (DateTime.UtcNow - t0).TotalMilliseconds;
            }
            catch (Exception e)
            {
                _rows = null;
                _error = e.GetType().Name + ": " + e.Message;
            }
        }
    }
}
