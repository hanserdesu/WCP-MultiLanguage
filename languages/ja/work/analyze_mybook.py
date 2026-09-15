import json, io

path = 'C:/Users/hanserdesu/AppData/LocalLow/WCP/wcp/MyBook.es3'
raw = open(path, 'rb').read()
print('BOM/head bytes:', raw[:20])
text = raw.decode('utf-8-sig', errors='replace')
data = json.loads(text)
print('keys:', list(data.keys()))
for k, v in data.items():
    t = v.get('__type', '?')
    val = v.get('value')
    if isinstance(val, list):
        print(f'\n{k} ({t}): list of {len(val)} items. head: {val[:8]}')
    elif isinstance(val, dict):
        items = list(val.items())[:5]
        print(f'\n{k} ({t}): dict of {len(val)} entries. head: {items}')
    else:
        print(f'\n{k} ({t}): {str(val)[:200]}')
