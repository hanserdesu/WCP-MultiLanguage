# -*- coding: utf-8 -*-
"""Dump stored meanings for sample words from the game DBs (read-only)."""
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")

SA = r"E:/Steam/steamapps/common/WCP-WordGirlgriend/wcp_Data/StreamingAssets"
WORDS = ["acheter", "table", "accord", "nation", "ring", "vote", "one", "three"]

for name in ["wcpOnlyWord.db", "wcpFullEng.db"]:
    print("=" * 60)
    print("DB:", name)
    con = sqlite3.connect("file:%s/%s?mode=ro" % (SA, name), uri=True)
    cur = con.cursor()
    for w in WORDS:
        row = cur.execute(
            "SELECT ukPhonic, usPhonic, meaning FROM pron WHERE word=?", (w,)).fetchone()
        if row is None:
            print("  %-8s <absent>" % w)
            continue
        meaning = (row[2] or "").replace("\\n", " / ")
        if len(meaning) > 90:
            meaning = meaning[:90] + "..."
        print("  %-8s uk=%s us=%s | %s" % (w, row[0], row[1], meaning))
    con.close()
