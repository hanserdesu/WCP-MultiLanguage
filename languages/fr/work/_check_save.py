# -*- coding: utf-8 -*-
import json, sys
sys.stdout.reconfigure(encoding='utf-8')
p = r"C:/Users/hanserdesu/AppData/LocalLow/WCP/wcp/SaveFile.es3"
d = json.loads(open(p, encoding='utf-8-sig').read())
for k in ["SelfBookName1","SelfBookName2","SelfBookName3","SelfBookName4","ChosenBook_Para"]:
    print(k, "=", repr((d.get(k) or {}).get("value")))
