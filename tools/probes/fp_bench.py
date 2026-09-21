import json, time, hashlib, unicodedata, statistics, os
P = r'C:\Users\hanserdesu\AppData\LocalLow\WCP\packs'
def fp(ws):
    n = sorted(unicodedata.normalize('NFC', w.strip()) for w in ws)
    payload = ''.join(x + '\n' for x in n)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()
print("lang  words   median_ms   min_ms   max_ms")
out=[]
for lang in ('ru','de','fr','ja','yue'):
    sm = os.path.join(P, lang, 'db', 'sentences.json')
    try:
        d = json.load(open(sm, encoding='utf-8'))
        words = list((d.get('sentences') or {}).keys())
    except Exception as e:
        print(lang, 'ERR', e); continue
    if not words:
        print(lang, 'EMPTY'); continue
    ts=[]
    for _ in range(9):
        t0=time.perf_counter(); fp(words); ts.append((time.perf_counter()-t0)*1000)
    med=statistics.median(ts); lo=min(ts); hi=max(ts)
    print("%-5s %-7d %-11.2f %-8.2f %-8.2f" % (lang, len(words), med, lo, hi))
    out.append(med)
if out:
    print()
    print("单次中位数均值 = %.2f ms" % (sum(out)/len(out)))
    print("5 插件 x 3.33Hz x 2次/次 = 33.3 次/秒 -> %.0f ms/秒 = %.0f%% 单核" % (33.3*(sum(out)/len(out)), 33.3*(sum(out)/len(out))/10))
