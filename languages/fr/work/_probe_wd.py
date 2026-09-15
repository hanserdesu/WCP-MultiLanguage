import pathlib, re, sys
sys.stdout.reconfigure(encoding="utf-8")
p = pathlib.Path.home() / "AppData/LocalLow/WCP/wcp/MyBook.es3"
txt = p.read_text(encoding="utf-8", errors="replace")
# locate wordDictionary2 block
for key in ["wordDictionary2", "wordDictionary1", "wordDictionary3"]:
    i = txt.find(key)
    print(key, "at", i)
    if i >= 0:
        print("  ctx:", repr(txt[max(0,i-80):i+400]))
