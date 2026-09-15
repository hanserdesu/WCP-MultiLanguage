# -*- coding: utf-8 -*-
# 共享库俄语残留清理 (2026-09-14):
# 俄语与英语零重叠, 离开俄语书的英语基线 = 整体删除俄语行。
# 插件侧 SwitchSharedDb(want=2) 已内置同样逻辑; 本脚本用于一次性修复
# 当前已被污染的库, 可重复执行 (幂等)。
import sqlite3
import sys
import time

GAME = r"E:\Steam\steamapps\common\WCP-WordGirlgriend"
SA = GAME + r"\wcp_Data\StreamingAssets"
PACK = r"D:\ATooManyLanguage\Russian\output\ru_db_payload"
BACKUP = PACK + r"\backup"


def load_words(path, col=0):
    words = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            w = line.split("\t")[col]
            if w and w not in words:
                words.append(w)
    return words


def clean_db(db, pron_words, sent_words, backup_name):
    con = sqlite3.connect(db)
    try:
        cur = con.cursor()
        tables = [r[0] for r in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        if "sentence2" not in tables:
            sent_words = []
        before_p = cur.execute(
            "SELECT COUNT(*) FROM pron WHERE word IN (%s)"
            % ",".join("?" * len(pron_words)), pron_words).fetchone()[0]
        before_s = 0
        if sent_words:
            before_s = cur.execute(
                "SELECT COUNT(*) FROM sentence2 WHERE word IN (%s)"
                % ",".join("?" * len(sent_words)), sent_words).fetchone()[0]
        if before_p == 0 and before_s == 0:
            print(db, "-> already clean")
            return (0, 0)
        cur.execute("BEGIN IMMEDIATE")
        cur.execute("DELETE FROM pron WHERE word IN (%s)"
                    % ",".join("?" * len(pron_words)), pron_words)
        if sent_words:
            cur.execute("DELETE FROM sentence2 WHERE word IN (%s)"
                        % ",".join("?" * len(sent_words)), sent_words)
        con.commit()
        after_p = cur.execute(
            "SELECT COUNT(*) FROM pron WHERE word IN (%s)"
            % ",".join("?" * len(pron_words)), pron_words).fetchone()[0]
        after_s = 0
        if sent_words:
            after_s = cur.execute(
                "SELECT COUNT(*) FROM sentence2 WHERE word IN (%s)"
                % ",".join("?" * len(sent_words)), sent_words).fetchone()[0]
        if after_p or after_s:
            print(db, "-> VERIFY FAILED", after_p, after_s)
            sys.exit(1)
        print(db, "-> removed pron=%d sentence2=%d" % (before_p, before_s))
        return (before_p, before_s)
    finally:
        con.close()


def main():
    pron_full = load_words(PACK + r"\ru_pron.tsv")
    sent_full = load_words(PACK + r"\ru_sentences.tsv")
    pron_only = load_words(PACK + r"\ru_only_pron.tsv")
    stamp = time.strftime("%Y%m%d_%H%M%S")
    targets = [
        (SA + r"\wcpFullEng.db", pron_full, sent_full),
        (SA + r"\wcpOnlyWord.db", pron_only, []),
    ]
    import os
    os.makedirs(BACKUP, exist_ok=True)
    for db, pw, sw in targets:
        if not os.path.exists(db):
            print("missing", db)
            continue
        con = sqlite3.connect(db)
        has_ru = con.execute(
            "SELECT COUNT(*) FROM pron WHERE word IN (%s)"
            % ",".join("?" * len(pw)), pw).fetchone()[0]
        con.close()
        if has_ru:
            bak = BACKUP + "\\" + os.path.basename(db) + ".bak_" + stamp
            with open(db, "rb") as src, open(bak, "wb") as dst:
                dst.write(src.read())
            print("backup:", bak)
        clean_db(db, pw, sw, stamp)
    print("DONE")


if __name__ == "__main__":
    main()
