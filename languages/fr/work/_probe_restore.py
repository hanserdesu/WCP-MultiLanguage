import sqlite3, sys, pathlib
sys.stdout.reconfigure(encoding="utf-8")
b = sqlite3.connect(r"D:/French/backups/wcpFullEng.before_french_e32c01_20260913_101456.db")
n = sqlite3.connect(r"E:/Steam/steamapps/common/WCP-WordGirlgriend/wcp_Data/StreamingAssets/wcpFullEng.db")
for w in ["accord", "table", "ring"]:
    bb = b.execute("SELECT ukPhonic,usPhonic,meaning FROM pron WHERE word=?", (w,)).fetchone()
    nn = n.execute("SELECT ukPhonic,usPhonic,meaning FROM pron WHERE word=?", (w,)).fetchone()
    print(w, "BACKUP:", bb, "| NOW:", nn, "| MATCH:", bb==nn)
    bs = [s[0] for s in b.execute("SELECT sentences FROM sentence2 WHERE word=?", (w,))]
    ns = [s[0] for s in n.execute("SELECT sentences FROM sentence2 WHERE word=?", (w,))]
    print("   sent MATCH:", bs==ns, "| BACKUP n=", len(bs), "NOW n=", len(ns))
b.close(); n.close()
