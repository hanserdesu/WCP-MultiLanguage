# -*- coding: utf-8 -*-
import json, pathlib, sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
# 从 DB 拿到 1638 个被覆盖的同形词
FULL = r"E:/Steam/steamapps/common/WCP-WordGirlgriend/wcp_Data/StreamingAssets/wcpFullEng.db"
BEFORE = r"D:/French/backups/wcpFullEng.before_french_e32c01_20260913_101456.db"
V = pathlib.Path.home() / "AppData/LocalLow/WCP/vocabulary"
def load(db, cols):
    con = sqlite3.connect(db); cur = con.cursor()
    d = {}
    for row in cur.execute("SELECT " + ",".join(cols) + " FROM pron"):
        d[row[0]] = row[1:]
    con.close(); return d
b = load(BEFORE, ["word","ukPhonic","usPhonic","meaning"])
n = load(FULL, ["word","ukPhonic","usPhonic","meaning"])
changed = [w for w in n if w in b and b[w] != n[w]]
added = [w for w in n if w not in b]
print("changed (english overwritten):", len(changed), "added (french-only):", len(added))
# 这些同形词里有多少个有本地 mp3 (会被法语覆盖)
chg_mp3 = [w for w in changed if (V / (w + ".mp3")).exists()]
print("of changed, has vocab mp3 (overwritten):", len(chg_mp3))
# 日语书 word list 是否与法语同形词冲突 (日语词全假名/汉字, 应无)
jp = set()
try:
    d = json.loads(open(r"C:/Users/hanserdesu/AppData/LocalLow/WCP/wcp/MyBook.es3", encoding='utf-8-sig').read())
    jp = set(d["SelfBookList1"]["value"])
except Exception as e:
    print("jp err", e)
overlap_jp_fr = jp & set(changed)
print("jp words overlapping french same-form words:", len(overlap_jp_fr))
print("sample:", sorted(overlap_jp_fr)[:15])
