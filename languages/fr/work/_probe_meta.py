import pathlib, sys
sys.stdout.reconfigure(encoding="utf-8")
p = pathlib.Path.home() / "AppData/LocalLow/WCP/wcp/MyBook.es3"
txt = p.read_text(encoding="utf-8", errors="replace")
for key in ["SelfBookMeaningConnectIf", "ChosenBook_Para", "bookName", "SelfBookMeaningDictionary"]:
    i = txt.find(key)
    print(key, "at", i)
    if i >= 0:
        print("  ctx:", repr(txt[max(0,i-60):i+160]))
