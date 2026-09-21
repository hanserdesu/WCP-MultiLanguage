import os
L = r'C:\Users\hanserdesu\AppData\LocalLow\WCP'
src = os.path.join(L,'packs','ja','audio','word')
tgt = os.path.join(L,'vocabulary')
sf = os.listdir(src)
print("ja/audio/word 文件数 = %d" % len(sf))
# 目标目录索引（只取名字 -> 大小）
tgt_size = {}
for n in os.listdir(tgt):
    try: tgt_size[n] = os.path.getsize(os.path.join(tgt,n))
    except: pass
print("vocabulary 文件数 = %d" % len(tgt_size))
present=0; missing=0; sizemismatch=0
sample = sf  # 全量比对（纯内存 + 一次 stat 源）
import time
t0=time.perf_counter()
for n in sample:
    if n not in tgt_size: missing+=1; continue
    try:
        if os.path.getsize(os.path.join(src,n)) == tgt_size[n]: present+=1
        else: sizemismatch+=1
    except: missing+=1
t1=time.perf_counter()
print("已存在(大小一致)=%d  缺失=%d  大小不符=%d   比对耗时=%.0fms" % (present, missing, sizemismatch, (t1-t0)*1000))
print()
# ru 对照
rsrc = os.path.join(L,'packs','ru','audio','word')
if os.path.isdir(rsrc):
    rf = os.listdir(rsrc); p=0; m=0
    for n in rf:
        if n in tgt_size:
            try:
                if os.path.getsize(os.path.join(rsrc,n))==tgt_size[n]: p+=1
                else: m+=1
            except: m+=1
        else: m+=1
    print("ru/audio/word 文件数=%d  已存在=%d  缺失=%d" % (len(rf), p, m))
