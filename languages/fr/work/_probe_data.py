import json, pathlib, sys
sys.stdout.reconfigure(encoding="utf-8")
books = json.load(open(r"D:/French/output/french_books.json", encoding="utf-8"))
print("books type:", type(books).__name__, "len:", len(books))
if isinstance(books, list):
    for it in books[:3]: print(" item:", json.dumps(it, ensure_ascii=False)[:300])
else:
    for k, v in list(books.items())[:3]: print(" ", repr(k), "->", json.dumps(v, ensure_ascii=False)[:300])
sent = json.load(open(r"D:/French/data/translations/sentences_master.json", encoding="utf-8"))
print("sent type:", type(sent).__name__, "len:", len(sent))
for k, v in list(sent.items())[:2]:
    print(" sent", repr(k), "->", json.dumps(v, ensure_ascii=False)[:300])
