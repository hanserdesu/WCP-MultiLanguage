import json, sqlite3, pathlib, sys, hashlib, unicodedata
sys.path.insert(0, r"D:/French/tools")
import wcp_paths
ROOT = pathlib.Path(r"D:/French")
books = json.loads((ROOT / "output" / "french_books.json").read_text(encoding="utf-8"))
allw = [w["word"] for lv in ("a1", "a2", "b1", "b2") for w in books["levels"][lv]]
ws = set(allw)
print("FR word count:", len(allw), "unique:", len(ws))
def table_info(db):
    con = sqlite3.connect(str(db))
    cur = con.cursor()
    out = []
    for (t,) in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
        cols = [c[1] for c in cur.execute("PRAGMA table_info(" + t + ")").fetchall()]
        n = cur.execute("SELECT COUNT(*) FROM " + t).fetchone()[0]
        out.append((t, n, cols[:10]))
    con.close()
    return out
def count_existing(db, ws):
    con = sqlite3.connect(str(db))
    cur = con.cursor()
    wl = list(ws)
    n = 0
    for i in range(0, len(wl), 500):
        c = wl[i:i+500]
        ph = ",".join("?" * len(c))
        n += cur.execute("SELECT COUNT(*) FROM pron WHERE word IN (" + ph + ")", c).fetchone()[0]
    con.close()
    return n
def english_collisions(db, ws):
    con = sqlite3.connect(str(db))
    cur = con.cursor()
    out = []
    wl = list(ws)
    for i in range(0, len(wl), 500):
        c = wl[i:i+500]
        ph = ",".join("?" * len(c))
        for w, uk, us, m in cur.execute("SELECT word, ukPhonic, usPhonic, meaning FROM pron WHERE word IN (" + ph + ")", c).fetchall():
            out.append((w, uk or "", us or "", m or ""))
    con.close()
    return out
def fp(words):
    norm = sorted((unicodedata.normalize("NFC", w.strip()) for w in words), key=lambda x: [ord(c) for c in x])
    payload = "".join(w + chr(10) for w in norm)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
for db in (wcp_paths.full_db(), wcp_paths.only_db()):
    print("---", db.name)
    for t, n, cols in table_info(db):
        print("  table", t, "rows", n, "cols", cols)
    print("FR words already present in pron:", count_existing(db, ws))
    rows = english_collisions(db, ws)
    print("collision rows:", len(rows))
    for w, uk, us, m in rows[:15]:
        print("   ", repr(w), "| uk=", repr(uk[:36]), "| us=", repr(us[:36]), "| m=", repr(m[:60]))
print("expected fp 376af2ea:", fp(allw)[:16])
mybook = pathlib.Path.home() / "AppData/LocalLow/WCP/wcp/MyBook.es3"
doc = json.loads(mybook.read_text(encoding="utf-8-sig"))
for slot in (1, 2, 3, 4):
    lst = doc.get("SelfBookList" + str(slot), {}).get("value", [])
    print("slot" + str(slot) + ":", len(lst), "fp:", (fp(lst)[:16] if lst else "-"))
