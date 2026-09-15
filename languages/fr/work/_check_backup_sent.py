# -*- coding: utf-8 -*-
import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
BEFORE = r"D:/French/backups/wcpFullEng.before_french_e32c01_20260913_101456.db"
con = sqlite3.connect(BEFORE); cur = con.cursor()
# 备份库里 1638 个同形词都有英文例句吗?
changed = ["accord","addition","aide","allo","alphabet","amour","an","attention","avant","baguette","ballon","beau","ring","table","sweet","sun","team","vain","tick","rap","ton","vice","terrain","taper","consultation","permission"]
for w in changed:
    cur.execute("SELECT word, ukPhonic, meaning FROM pron WHERE word=?", (w,))
    pron = cur.fetchone()
    cur.execute("SELECT COUNT(*) FROM sentence2 WHERE word=?", (w,))
    ns = cur.fetchone()[0]
    print(f"{w}: pron={bool(pron)} ({pron[1] if pron else '-'}) sent={ns}")
cur.execute("SELECT COUNT(*) FROM pron"); print("backup pron total:", cur.fetchone()[0])
cur.execute("SELECT COUNT(*) FROM sentence2"); print("backup sentence2 total:", cur.fetchone()[0])
con.close()
