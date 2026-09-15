import json, pathlib, sqlite3, sys
sys.stdout.reconfigure(encoding="utf-8")
books = json.loads((pathlib.Path(r"D:/French/output/french_books.json")).read_text(encoding="utf-8"))
allw = [w["word"] for lv in ("a1","a2","b1","b2") for w in books["levels"][lv]]
ws = set(allw)
VOCAB = pathlib.Path.home() / "AppData/LocalLow/WCP/vocabulary"
files = {p.stem: p for p in VOCAB.glob("*.mp3")}
print("total vocab mp3:", len(files))
# overlap = french words that exist in the backup english db
b = sqlite3.connect(r"D:/French/backups/wcpFullEng.before_french_e32c01_20260913_101456.db")
eng = set(x[0] for x in b.execute("SELECT word FROM pron"))
b.close()
overlap = [w for w in ws if w in eng]
print("french-english same-form words:", len(overlap))
has_mp3 = [w for w in overlap if w in files]
missing_mp3 = [w for w in overlap if w not in files]
print("overlap with vocab mp3:", len(has_mp3))
print("overlap missing mp3:", len(missing_mp3), missing_mp3[:15])
print("samples:", has_mp3[:15])
# check fr_audio dir state
FR = pathlib.Path.home() / "AppData/LocalLow/WCP/fr_audio"
print("fr_audio exists:", FR.exists(), "count:", len(list(FR.glob("*.mp3"))) if FR.exists() else 0)
