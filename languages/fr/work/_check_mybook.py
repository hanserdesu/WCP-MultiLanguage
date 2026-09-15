# -*- coding: utf-8 -*-
import json, sys
sys.stdout.reconfigure(encoding='utf-8')
p = r"C:/Users/hanserdesu/AppData/LocalLow/WCP/wcp/MyBook.es3"
d = json.loads(open(p, encoding='utf-8-sig').read())
print("keys sample:", list(d.keys())[:60])
for k in d:
    if "wordDictionary" in k or "SelfBookList" in k or "ChosenBook" in k or k.startswith("book"):
        v = d[k]
        if isinstance(v, dict) and "value" in v:
            vv = v["value"]
            if isinstance(vv, list):
                print(k, "list len", len(vv), "sample", vv[:3])
            else:
                print(k, repr(vv)[:80])
        else:
            print(k, "TYPE", type(v).__name__, repr(v)[:80])
