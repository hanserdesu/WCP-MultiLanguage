import sqlite3, sys
sys.stdout.reconfigure(encoding="utf-8")
b = sqlite3.connect(r"D:/French/backups/wcpFullEng.before_french_e32c01_20260913_101456.db")
n = sqlite3.connect(r"E:/Steam/steamapps/common/WCP-WordGirlgriend/wcp_Data/StreamingAssets/wcpFullEng.db")
for w in ["accord", "table", "ring", "baguette"]:
    print("== word", w)
    print("  BACKUP pron:", b.execute("SELECT ukPhonic,usPhonic,meaning FROM pron WHERE word=?", (w,)).fetchone())
    print("  NOW    pron:", n.execute("SELECT ukPhonic,usPhonic,meaning FROM pron WHERE word=?", (w,)).fetchone())
    print("  BACKUP sent:", [s[0] for s in b.execute("SELECT sentences FROM sentence2 WHERE word=?", (w,))][:3])
    print("  NOW    sent:", [s[0] for s in n.execute("SELECT sentences FROM sentence2 WHERE word=?", (w,))][:3])
b.close(); n.close()
