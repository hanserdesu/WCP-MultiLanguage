# -*- coding: utf-8 -*-
"""生成严格对齐复刻规范的 RuWordListMod.cs"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INTEGRATION_ROOT = ROOT.parent
FR_CS = INTEGRATION_ROOT / "French" / "mod_fr_wordlist" / "FrWordListMod.cs"
RU_CS = ROOT / "mod_ru_wordlist" / "RuWordListMod.cs"

def main():
    text = FR_CS.read_text(encoding='utf-8')

    # 1. 替换命名空间与类名
    text = text.replace("namespace FrWordList", "namespace RuWordList")
    text = text.replace("FrWordListPlugin", "RuWordListPlugin")
    text = text.replace("dev.hanserdesu.frwordlist", "dev.hanserdesu.ruwordlist")
    text = text.replace("WCP FR Word List", "WCP RU Word List")
    text = text.replace("FRWordList", "RUWordList")
    text = text.replace("FrWordList", "RuWordList")

    # 2. 替换 Profile 与语言匹配
    text = text.replace("BookProfiles.French", "BookProfiles.Russian")
    text = text.replace("FrenchBookSelected", "RussianBookSelected")
    text = text.replace("catbar-french-cefr-complete", "catbar-russian-cefr-complete")

    # 3. 替换前缀
    text = text.replace("FrWL_", "RuWL_")

    # 4. 替换 payload 与音频
    text = text.replace("fr_db_payload", "ru_db_payload")
    text = text.replace("fr_pron.tsv", "ru_pron.tsv")
    text = text.replace("fr_sentences.tsv", "ru_sentences.tsv")
    text = text.replace("fr_only_pron.tsv", "ru_only_pron.tsv")
    text = text.replace("fr_word_audio", "ru_word_audio")
    text = text.replace("PlayFrenchWord", "PlayRussianWord")
    text = text.replace("法语", "俄语")

    # 5. 俄语音频只允许落在 ru_word_audio；不得生成共享 vocabulary 回退。
    text = text.replace(
        'WarnOnce("word-audio:" + word, "俄语独立单词音频缺失: " + word);\n                return false;',
        'WarnOnce("word-audio:" + word, "俄语独立单词音频缺失: " + word);\n                return true;'
    )

    # 6. 在 Update() 中移除法国独有的 TickSharedDbSwitch() 调用
    text = text.replace(
        '            try { TickDbHeal(); }\n            catch (Exception e) { Warn("离线自愈异常: " + e.Message); }\n            try { TickSharedDbSwitch(); }\n            catch (Exception e) { Warn("共享库切换轮询异常: " + e.Message); }',
        '            try { TickDbHeal(); }\n            catch (Exception e) { Warn("离线自愈异常: " + e.Message); }'
    )

    # 7. 重构自愈部分（移除英法同形词切换逻辑，与日文 JpWordListMod.cs 保持一致的纯净自愈）
    heal_idx = text.find("// ---------------- 数据库自愈 (ru_db_payload) ----------------")
    if heal_idx < 0:
        raise ValueError("Cannot find heal section")

    prefix = text[:heal_idx]

    clean_heal = '''// ---------------- 数据库自愈 (ru_db_payload) ----------------
        // 官方更新会覆盖 StreamingAssets 下的 .db, 把俄语词条的释义(pron)和例句(sentence2)冲掉。
        // 启动后若发现探针词缺失, 就从 LocalLow 的补丁包(ru_db_payload)重灌一次; 写前先备份 DB。
        private const string DbPackDir = "ru_db_payload";
        private static readonly string[] DbProbes = new string[] { "стол", "человек", "хорошо", "говорить" };
        private static bool _dbHealTried;
        private static float _dbHealAt = -1f;

        private static void TickDbHeal()
        {
            if (_dbHealTried || _healDb == null || !_healDb.Value ||
                _allowLegacySharedDbWrites == null || !_allowLegacySharedDbWrites.Value) return;
            if (BookState() != 1) return;
            if (_dbHealAt < 0f) { _dbHealAt = Time.unscaledTime + 8f; return; }
            if (Time.unscaledTime < _dbHealAt) return;
            string pack = System.IO.Path.Combine(Application.persistentDataPath, DbPackDir);
            if (!System.IO.Directory.Exists(pack)) { _dbHealTried = true; return; }
            string full = System.IO.Path.Combine(Application.streamingAssetsPath, "wcpFullEng.db");
            if (!System.IO.File.Exists(full)) { _dbHealTried = true; return; }
            string only = System.IO.Path.Combine(Application.streamingAssetsPath, "wcpOnlyWord.db");
            _dbHealTried = true;
            try
            {
                System.Threading.Thread t = new System.Threading.Thread(
                    new System.Threading.ThreadStart(delegate { RunDbHeal(pack, full, only); }));
                t.IsBackground = true;
                t.Start();
            }
            catch (Exception e) { Warn("例句库自愈启动异常: " + e.Message); }
        }

        private static void RunDbHeal(string pack, string full, string only)
        {
            try
            {
                if (!NeedsDbHeal(full))
                {
                    InfoOnce("dbheal-skip", "例句库已是补丁状态, 不再重灌");
                    return;
                }
                string fullPron = System.IO.Path.Combine(pack, "ru_pron.tsv");
                string fullSent = System.IO.Path.Combine(pack, "ru_sentences.tsv");
                string onlyPron = System.IO.Path.Combine(pack, "ru_only_pron.tsv");
                if (!System.IO.File.Exists(fullPron) || !System.IO.File.Exists(fullSent) ||
                    !System.IO.File.Exists(onlyPron))
                {
                    throw new System.IO.FileNotFoundException("ru_db_payload 不完整");
                }
                string stamp = DateTime.Now.ToString("yyyyMMdd_HHmmss");
                string bakDir = System.IO.Path.Combine(pack, "backup");
                System.IO.Directory.CreateDirectory(bakDir);
                System.IO.File.Copy(full, System.IO.Path.Combine(bakDir, "wcpFullEng.db.bak_" + stamp), true);
                if (System.IO.File.Exists(only))
                {
                    System.IO.File.Copy(only, System.IO.Path.Combine(bakDir, "wcpOnlyWord.db.bak_" + stamp), true);
                }
                int n1 = ApplyDbPack(full, fullPron, fullSent);
                int n2 = 0;
                if (System.IO.File.Exists(only))
                {
                    n2 = ApplyDbPack(only, onlyPron, null);
                }
                if (n1 == 0 || NeedsDbHeal(full))
                    throw new InvalidOperationException("补丁回读校验失败");
                if (Log != null)
                {
                    Log.LogInfo("RUWordList: 例句库已自动重灌 FullEng.pron+sent=" + n1 +
                                ", OnlyWord.pron=" + n2 + " (官方更新后恢复)");
                }
            }
            catch (Exception e) { Warn("例句库自愈失败(下次启动再试): " + e.Message); }
        }

        private static bool NeedsDbHeal(string db)
        {
            using (SqliteConnection con = new SqliteConnection("URI=file:" + db))
            {
                con.Open();
                using (SqliteCommand cmd = con.CreateCommand())
                {
                    for (int i = 0; i < DbProbes.Length; i++)
                    {
                        cmd.CommandText = "SELECT COUNT(*) FROM pron WHERE word = @w";
                        cmd.Parameters.Clear();
                        cmd.Parameters.Add(new SqliteParameter("@w", DbProbes[i]));
                        object o = cmd.ExecuteScalar();
                        if (o == null || Convert.ToInt64(o) == 0) return true;
                    }
                }
                con.Close();
            }
            return false;
        }

        private static int ApplyDbPack(string db, string pronTsv, string sentTsv)
        {
            if (!System.IO.File.Exists(pronTsv)) return 0;
            string[][] pron = ReadTsv(pronTsv, 4);
            string[][] sent = (sentTsv != null && System.IO.File.Exists(sentTsv))
                ? ReadTsv(sentTsv, 2) : new string[0][];
            int n = 0;
            using (SqliteConnection con = new SqliteConnection("URI=file:" + db))
            {
                con.Open();
                using (SqliteCommand p = con.CreateCommand())
                {
                    p.CommandText = "PRAGMA busy_timeout=30000";
                    p.ExecuteNonQuery();
                }
                using (SqliteTransaction tx = con.BeginTransaction())
                {
                    DeleteRows(con, tx, "pron", pron);
                    if (sent.Length > 0) DeleteRows(con, tx, "sentence2", sent);
                    using (SqliteCommand ins = con.CreateCommand())
                    {
                        ins.Transaction = tx;
                        ins.CommandText =
                            "INSERT INTO pron (word, ukPhonic, usPhonic, meaning) VALUES (@w,@u,@s,@m)";
                        for (int i = 0; i < pron.Length; i++)
                        {
                            ins.Parameters.Clear();
                            ins.Parameters.Add(new SqliteParameter("@w", pron[i][0]));
                            ins.Parameters.Add(new SqliteParameter("@u", pron[i][1]));
                            ins.Parameters.Add(new SqliteParameter("@s", pron[i][2]));
                            ins.Parameters.Add(new SqliteParameter("@m", pron[i][3]));
                            n += ins.ExecuteNonQuery();
                        }
                    }
                    if (sent.Length > 0)
                    {
                        using (SqliteCommand ins2 = con.CreateCommand())
                        {
                            ins2.Transaction = tx;
                            ins2.CommandText = "INSERT INTO sentence2 (word, sentences) VALUES (@w,@s)";
                            for (int i = 0; i < sent.Length; i++)
                            {
                                ins2.Parameters.Clear();
                                ins2.Parameters.Add(new SqliteParameter("@w", sent[i][0]));
                                ins2.Parameters.Add(new SqliteParameter("@s", sent[i][1]));
                                ins2.ExecuteNonQuery();
                            }
                        }
                    }
                    tx.Commit();
                }
                con.Close();
            }
            return n;
        }

        private static void DeleteRows(SqliteConnection con, SqliteTransaction tx,
            string table, string[][] rows)
        {
            if (rows.Length == 0) return;
            List<string> wl = new List<string>();
            HashSet<string> seen = new HashSet<string>();
            for (int i = 0; i < rows.Length; i++)
            {
                string w = rows[i][0];
                if (w != null && w.Length > 0 && seen.Add(w)) wl.Add(w);
            }
            for (int i = 0; i < wl.Count; i += 400)
            {
                int end = Math.Min(i + 400, wl.Count);
                System.Text.StringBuilder sb = new System.Text.StringBuilder();
                sb.Append("DELETE FROM ").Append(table).Append(" WHERE word IN (");
                using (SqliteCommand cmd = con.CreateCommand())
                {
                    cmd.Transaction = tx;
                    for (int j = i; j < end; j++)
                    {
                        if (j > i) sb.Append(',');
                        string pn = "@p" + (j - i);
                        sb.Append(pn);
                        cmd.Parameters.Add(new SqliteParameter(pn, wl[j]));
                    }
                    sb.Append(')');
                    cmd.CommandText = sb.ToString();
                    cmd.ExecuteNonQuery();
                }
            }
        }

        private static string[][] ReadTsv(string path, int cols)
        {
            string[] lines = System.IO.File.ReadAllLines(path, System.Text.Encoding.UTF8);
            List<string[]> rows = new List<string[]>(lines.Length);
            for (int i = 0; i < lines.Length; i++)
            {
                if (lines[i].Length == 0) continue;
                string[] parts = lines[i].Split('\\t');
                string[] vals = new string[cols];
                for (int c = 0; c < cols; c++)
                    vals[c] = (c < parts.Length) ? Unescape(parts[c]) : "";
                rows.Add(vals);
            }
            return rows.ToArray();
        }

        private static string Unescape(string s)
        {
            if (s == null || s.IndexOf('\\\\') < 0) return s;
            System.Text.StringBuilder sb = new System.Text.StringBuilder(s.Length);
            for (int i = 0; i < s.Length; i++)
            {
                char c = s[i];
                if (c == '\\\\' && i + 1 < s.Length)
                {
                    char x = s[i + 1];
                    if (x == 'n') { sb.Append('\\n'); i++; continue; }
                    if (x == 't') { sb.Append('\\t'); i++; continue; }
                    if (x == '\\\\') { sb.Append('\\\\'); i++; continue; }
                }
                sb.Append(c);
            }
            return sb.ToString();
        }

        private static bool IsEnabled()
        {
            return Instance != null && _enabled != null && _enabled.Value;
        }

        private static void Warn(string s)
        {
            if (Log != null) Log.LogWarning("RUWordList: " + s);
        }

        private static void WarnOnce(string key, string s)
        {
            if (!Warned.Add(key)) return;
            Warn(s);
        }

        private static void InfoOnce(string key, string s)
        {
            if (!Warned.Add("info:" + key)) return;
            if (Log != null) Log.LogInfo("RUWordList: " + s);
        }
    }
}
'''
    full_text = prefix + clean_heal
    RU_CS.write_text(full_text, encoding='utf-8')
    print("Generated clean RuWordListMod.cs, bytes:", len(full_text))

if __name__ == '__main__':
    main()
