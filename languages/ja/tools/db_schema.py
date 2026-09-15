import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')

DB = r'E:\SteamLibrary\steamapps\common\WCP-WordGirlgriend\wcp_Data\StreamingAssets\wcpOnlyWord.db'
con = sqlite3.connect(DB)
cur = con.cursor()
cur.execute("SELECT name, sql FROM sqlite_master WHERE type='table'")
for name, sql in cur.fetchall():
    print("==>", name)
    print(sql)
    try:
        cur2 = con.cursor()
        cur2.execute(f"SELECT COUNT(*) FROM {name}")
        print("rows:", cur2.fetchone()[0])
        cur2.execute(f"SELECT * FROM {name} LIMIT 3")
        for row in cur2.fetchall():
            print("  ", row)
    except Exception as e:
        print("  err:", e)
