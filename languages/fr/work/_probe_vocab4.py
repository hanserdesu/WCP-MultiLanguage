import pathlib, sys, re
sys.stdout.reconfigure(encoding="utf-8")
VOCAB = pathlib.Path.home() / "AppData/LocalLow/WCP/vocabulary"
files = list(VOCAB.glob("*.mp3"))
# classify by filename: CJK/kana vs latin ascii
cjk = [p.stem for p in files if re.search(r"[\u3040-\u30FF\u3400-\u9FFF]", p.stem)]
latin = [p.stem for p in files if not re.search(r"[\u3040-\u30FF\u3400-\u9FFF]", p.stem)]
print("total:", len(files))
print("CJK/kana stems:", len(cjk))
print("latin (ascii) stems:", len(latin))
print("latin samples:", latin[:20])
