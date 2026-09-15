import sqlite3
for name in ['wcpOnlyWord','wcpFullEng','wcpFight','wcpScript']:
    path = f'E:/SteamLibrary/steamapps/common/WCP-WordGirlgriend/wcp_Data/StreamingAssets/{name}.db'
    con = sqlite3.connect(path)
    cur = con.cursor()
    tables = cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    print(f'=== {name} ===')
    for (t,) in tables:
        cols = cur.execute(f'PRAGMA table_info("{t}")').fetchall()
        cnt = cur.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        sample = cur.execute(f'SELECT * FROM "{t}" LIMIT 2').fetchall()
        print(f'  {t} ({cnt} rows): cols={[c[1] for c in cols]}')
        for s in sample:
            print(f'    sample: {str(s)[:300]}')
    con.close()
