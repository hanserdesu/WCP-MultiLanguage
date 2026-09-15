import json, sqlite3, pathlib, sys
import wcp_paths
ROOT = pathlib.Path(r"D:/French")
books = json.loads((ROOT / "output" / "french_books.json").read_text(encoding="utf-8"))
allw = [w["word"] for lv in ("a1", "a2", "b1", "b2") for w in books["levels"][lv]]
ws = set(allw)
VOCAB = pathlib.Path.home() / "AppData/LocalLow/WCP/vocabulary"
files = {p.stem: p for p in VOCAB.glob("*.mp3")} if VOCAB.exists() else {}
print("vocab dir exists:", VOCAB.exists(), "total mp3:", len(files))
hit = [w for w in ws if w in files]
print("FR words with local vocab mp3:", len(hit))

# Which of those are English words in the ORIGINAL english db (before french patch)?
BEFORE_FULL = pathlib.Path(r"D:/French/backups/wcpFullEng.before_french_e32c01_20260913_101456.db")
con = sqlite3.connect(str(BEFORE_FULL))
cur = con.cursor()
eng_words = set(r[0] for r in cur.execute("SELECT word FROM pron"))
con.close()
same = [w for w in hit if w in eng_words]
print("FR words with mp3 that EXISTED in english db before:", len(same))
for w in sorted(same)[:30]:
    print("   ", w)

# sentence2 conflict details: words that had english sentences before, now french
FULL = wcp_paths.full_db()
def load(db, table):
    con = sqlite3.connect(str(db)); cur = con.cursor()
    d = {}
    for w, s in cur.execute("SELECT word, sentences FROM " + table):
        d.setdefault(w, []).append(s)
    con.close(); return d
b_s = load(BEFORE_FULL, "sentence2")
n_s = load(FULL, "sentence2")
both = []
for w in n_s:
    if w in b_s:
        old_all = " ".join(b_s[w])
        new_all = " ".join(n_s[w])
        if old_all != new_all:
            both.append(w)
print("sentence2 words whose content changed:", len(both))
for w in sorted(both)[:20]:
    print("   ", repr(w), "| OLD:", repr(b_s[w][0][:70]), "| NEW:", repr(n_s[w][0][:70]))
