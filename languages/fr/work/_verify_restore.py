import sqlite3, sys
sys.stdout.reconfigure(encoding="utf-8")
B = [r"D:/French/backups/wcpFullEng.before_french_e32c01_20260913_101456.db", r"D:/French/backups/wcpOnlyWord.before_french_657afe_20260913_101457.db"]
N = [r"E:/Steam/steamapps/common/WCP-WordGirlgriend/wcp_Data/StreamingAssets/wcpFullEng.db", r"E:/Steam/steamapps/common/WCP-WordGirlgriend/wcp_Data/StreamingAssets/wcpOnlyWord.db"]
for bf, nf in zip(B, N):
    b = sqlite3.connect(bf); n = sqlite3.connect(nf)
    bd = {w: (u,s,m) for w,u,s,m in b.execute("SELECT word,ukPhonic,usPhonic,meaning FROM pron")}
    nd = {w: (u,s,m) for w,u,s,m in n.execute("SELECT word,ukPhonic,usPhonic,meaning FROM pron")}
    diff = [w for w in bd if w in nd and bd[w] != nd[w]]
    miss = [w for w in bd if w not in nd]
    extra = [w for w in nd if w not in bd]
    print(nf.split(chr(92))[-1], "| pron diffs:", len(diff), "| backup-missing:", len(miss), "| extra:", len(extra))
    # sentence2 check for full
    if "FullEng" in nf:
        bs = {}
        for w,s in b.execute("SELECT word,sentences FROM sentence2"): bs.setdefault(w,[]).append(s)
        ns = {}
        for w,s in n.execute("SELECT word,sentences FROM sentence2"): ns.setdefault(w,[]).append(s)
        sdiff = [w for w in bs if w in ns and bs[w] != ns[w]]
        smiss = [w for w in bs if w not in ns]
        print("   sentence2 diffs:", len(sdiff), "| backup-missing:", len(smiss))
    b.close(); n.close()
