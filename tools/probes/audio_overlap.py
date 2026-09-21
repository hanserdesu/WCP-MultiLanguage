import os
L = r'C:\Users\hanserdesu\AppData\LocalLow\WCP'
pk = os.path.join(L,'packs')
langs = {}
for d in sorted(os.listdir(pk)):
    w = os.path.join(pk, d, 'audio', 'word')
    if os.path.isdir(w):
        langs[d] = set(f.lower() for f in os.listdir(w))
print("=== 各语言 word 音频文件数 ===")
for k,v in langs.items():
    print("  %-6s %d" % (k, len(v)))
print()
tgt = os.path.join(L,'vocabulary')
tf = set(f.lower() for f in os.listdir(tgt))
print("vocabulary 总数(含全部扩展名) = %d" % len(tf))
print()
print("=== 两两重叠（交集大小 / 占较小集合比例）===")
keys = list(langs.keys())
for i in range(len(keys)):
    for j in range(i+1, len(keys)):
        a, b = keys[i], keys[j]
        inter = langs[a] & langs[b]
        if inter:
            print("  %-6s ∩ %-6s = %-7d (%.1f%% of %d, %.1f%% of %d)" % (
                a, b, len(inter), 100*len(inter)/len(langs[a]), len(langs[a]),
                100*len(inter)/len(langs[b]), len(langs[b])))
print()
# 有多少 japanese 文件在 vocabulary 中已存在（大小一致）
import time
idx = {}
t0=time.perf_counter()
for n in os.listdir(tgt):
    p = os.path.join(tgt,n)
    try: idx[n.lower()] = os.path.getsize(p)
    except: pass
t1=time.perf_counter()
print("建立 vocabulary 索引: %d 项 / %.0f ms" % (len(idx), (t1-t0)*1000))
