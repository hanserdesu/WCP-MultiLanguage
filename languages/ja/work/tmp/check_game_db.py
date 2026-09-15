import os, sqlite3
db = r'E:\Steam\steamapps\common\WCP-WordGirlgriend\wcp_Data\StreamingAssets\wcpFullEng.db'
print('db exists:', os.path.exists(db))
if os.path.exists(db):
    con = sqlite3.connect(db)
    tables = [r[0] for r in con.execute("select name from sqlite_master where type='table'")]
    print('tables:', tables)
    if 'pron' in tables:
        print('pron total:', con.execute('select count(*) from pron').fetchone()[0])
    if 'sentence2' in tables:
        print('sentence2 total:', con.execute('select count(*) from sentence2').fetchone()[0])
    con.close()
