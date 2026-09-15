# -*- coding: utf-8 -*-
import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
p = r"E:/Steam/steamapps/common/WCP-WordGirlgriend/wcp_Data/StreamingAssets/wcpFight.db"
con = sqlite3.connect(p)
cur = con.cursor()
for (n, sql) in cur.execute("SELECT name, sql FROM sqlite_master WHERE type='table'"):
    print("TABLE", n, "|", (sql or "")[:120])
try:
    for w in ["accord", "ring", "acheter"]:
        cur.execute("SELECT COUNT(*) FROM pron WHERE word=?", (w,))
        print("pron", w, cur.fetchone())
except Exception as e:
    print("pron err", e)
con.close()
