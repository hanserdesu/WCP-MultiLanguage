import os, time, shutil, statistics, random
L = r'C:\Users\hanserdesu\AppData\LocalLow\WCP'
src = os.path.join(L,'packs','ja','audio','word')
tmp = os.path.join(os.environ.get('TEMP','.'), 'wcp_copy_bench')
if not os.path.isdir(src):
    print('src missing'); raise SystemExit
fs = os.listdir(src)
random.seed(1); sample = random.sample(fs, 300)
os.makedirs(tmp, exist_ok=True)
ts=[]
for i,f in enumerate(sample):
    s = os.path.join(src,f); d = os.path.join(tmp, f)
    t0=time.perf_counter()
    try: shutil.copy2(s,d)
    except Exception as e: continue
    ts.append((time.perf_counter()-t0)*1000)
ts.sort()
if ts:
    print("copy %d files: median=%.3fms p90=%.3fms max=%.3fms" % (len(ts), statistics.median(ts), ts[int(len(ts)*0.9)], ts[-1]))
    print("est for 22790 files: median=%.1fs  p90=%.1fs" % (statistics.median(ts)*22790/1000, ts[int(len(ts)*0.9)]*22790/1000))
# also measure stat-only cost (AlreadyPresent path)
ms=[]; 
for f in sample[:300]:
    s = os.path.join(src,f); d = os.path.join(tmp, f)
    t0=time.perf_counter()
    try:
        a=os.path.getsize(s); b=os.path.getsize(d)
    except: continue
    ms.append((time.perf_counter()-t0)*1000)
print("AlreadyPresent(2x stat) median=%.4fms -> 22790 files = %.0fms" % (statistics.median(ms), statistics.median(ms)*22790))
shutil.rmtree(tmp, ignore_errors=True)
