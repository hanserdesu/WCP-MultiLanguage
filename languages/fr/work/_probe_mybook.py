import pathlib, re, sys
sys.stdout.reconfigure(encoding="utf-8")
p = pathlib.Path.home() / "AppData/LocalLow/WCP/wcp/MyBook.es3"
data = p.read_bytes()
try:
    txt = data.decode("utf-8", errors="replace")
except Exception as e:
    print("decode fail", e); txt = None
print("MyBook.es3 size:", len(data))
# 找法语词条样本 (accord / table / ring)
for w in ["accord", "table", "ring", "baguette"]:
    i = txt.find(w)
    print(w, "found at", i)
    if i >= 0:
        print("  ctx:", repr(txt[max(0,i-120):i+220]))
