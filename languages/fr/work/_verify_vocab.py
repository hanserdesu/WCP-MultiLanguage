import json, pathlib, sqlite3, sys
sys.stdout.reconfigure(encoding="utf-8")
books = json.loads((pathlib.Path(r"D:/French/output/french_books.json")).read_text(encoding="utf-8"))
allw = [w["word"] for lv in ("a1","a2","b1","b2") for w in books["levels"][lv]]
ws = set(allw)
VOCAB = pathlib.Path.home() / "AppData/LocalLow/WCP/vocabulary"
FR = pathlib.Path.home() / "AppData/LocalLow/WCP/fr_audio"
files = {p.stem: p for p in VOCAB.glob("*.mp3")}
frfiles = {p.stem: p for p in FR.glob("*.mp3")}
b = sqlite3.connect(r"D:/French/backups/wcpFullEng.before_french_e32c01_20260913_101456.db")
eng = set(x[0] for x in b.execute("SELECT word FROM pron"))
b.close()
overlap = set(w for w in ws if w in eng)
# 1. no overlap words should remain in vocabulary
leftover = overlap & set(files)
print("overlap words STILL in vocabulary:", len(leftover), sorted(leftover)[:10])
# 2. all overlap words should be in fr_audio
print("overlap words in fr_audio:", len(overlap & set(frfiles)))
# 3. pure french words still in vocabulary (they belong there)
pure_fr = ws - overlap
print("pure french words still in vocabulary:", len(pure_fr & set(files)))
# 4. no english duplicate concern: check english words that now have NO mp3 in vocab
eng_with_mp3 = set(files) & eng
print("english words still with vocab mp3:", len(eng_with_mp3))
