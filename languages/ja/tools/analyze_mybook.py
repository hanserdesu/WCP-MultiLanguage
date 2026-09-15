import json, sys
sys.stdout.reconfigure(encoding='utf-8')

P = r'C:\Users\hanserdesu\AppData\LocalLow\WCP\wcp\MyBook.es3'
data = json.load(open(P, encoding='utf-8-sig'))

for k, v in data.items():
    t = v.get('__type', '?')
    val = v.get('value')
    if isinstance(val, list):
        print(f"{k}: type={t}, len={len(val)}, head={val[:5]}")
    elif isinstance(val, dict):
        items = list(val.items())[:5]
        print(f"{k}: type={t}, len={len(val)}, head={items}")
    else:
        print(f"{k}: type={t}, value={val!r}")
