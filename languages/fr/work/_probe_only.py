import sqlite3, sys
sys.stdout.reconfigure(encoding="utf-8")
b = sqlite3.connect(r"D:/French/backups/wcpOnlyWord.before_french_657afe_20260913_101457.db")
n = sqlite3.connect(r"E:/Steam/steamapps/common/WCP-WordGirlgriend/wcp_Data/StreamingAssets/wcpOnlyWord.db")
for w in ["accord", "table", "ring", "baguette"]:
    bb = b.execute("SELECT ukPhonic,usPhonic,meaning FROM pron WHERE word=?", (w,)).fetchone()
    nn = n.execute("SELECT ukPhonic,usPhonic,meaning FROM pron WHERE word=?", (w,)).fetchone()
    print(w, "MATCH:", bb==nn)
    if bb != nn:
        print("  BACKUP:", bb)
        print("  NOW:   ", nn)
b.close(); n.close()
