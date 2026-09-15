# -*- coding: utf-8 -*-
import sqlite3, os, sys

BASE = r'E:\SteamLibrary\steamapps\common\WCP-WordGirlgriend\wcp_Data\StreamingAssets'
sys.stdout.reconfigure(encoding='utf-8')

for db in ['wcpFullEng.db', 'wcpOnlyWord.db', 'wcpFight.db', 'wcpScript.db']:
    p = os.path.join(BASE, db)
    try:
        con = sqlite3.connect(p)
        cur = con.cursor()
        tables = cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        print('===', db, '===')
        for (t,) in tables:
            n = cur.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
            cols = [c[1] for c in cur.execute(f'PRAGMA table_info("{t}")').fetchall()]
            print(f'  table {t}: {n} rows, cols={cols}')
        con.close()
    except Exception as e:
        print(db, 'ERR', e)
