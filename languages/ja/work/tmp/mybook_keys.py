import io, json, sys
sys.stdout.reconfigure(encoding='utf-8')
d = json.load(io.open(r'C:/Users/hanserdesu/AppData/LocalLow/WCP/wcp/MyBook.es3', encoding='utf-8'))
print('MyBook.es3 top-level keys:')
for k in sorted(d):
    v = d[k]
    n = len(v) if hasattr(v, '__len__') else v
    print('  ', k, type(v).__name__, n if not isinstance(v, dict) else 'dict(%d)' % len(v))
