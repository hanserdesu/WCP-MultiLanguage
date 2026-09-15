import io, json, os, sys, random
sys.stdout.reconfigure(encoding='utf-8')
PD = r'C:/Users/hanserdesu/AppData/LocalLow/WCP/wcp'
def unwrap(node):
    if isinstance(node, dict):
        if '__type' in node and 'value' in node:
            return unwrap(node['value'])
        return {k: unwrap(v) for k, v in node.items()}
    if isinstance(node, list):
        return [unwrap(x) for x in node]
    return node
with io.open(os.path.join(PD, 'MyBook.es3'), 'r', encoding='utf-8') as f:
    mb = {k: unwrap(v) for k, v in json.load(f).items()}
d = mb.get('wordDictionary1') or {}
print('entries', len(d))
for w in ['歯医者', 'うち', '工業', '世話する', '黄色', '割れる', '続ける', '全部', '豚肉', '止む', '今週']:
    print(repr(w), '=>', repr(d.get(w)))
random.seed(7)
for w in random.sample(list(d.keys()), 20):
    print(repr(w), '=>', repr(d[w]))
br = [w for w in d if '【' not in (d[w] or '')]
print('no bracket count', len(br))
for w in br[:15]:
    print('  ', repr(w), '=>', repr(d[w]))
