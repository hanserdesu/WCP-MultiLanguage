import os, time, statistics
L = r'C:\Users\hanserdesu\AppData\LocalLow\WCP'
targets = [
    ('ja/audio/word',     os.path.join(L,'packs','ja','audio','word')),
    ('ja/audio/sentence', os.path.join(L,'packs','ja','audio','sentence')),
    ('ru/audio/word',     os.path.join(L,'packs','ru','audio','word')),
    ('ru/audio/sentence', os.path.join(L,'packs','ru','audio','sentence')),
    ('vocabulary(目标)',  os.path.join(L,'vocabulary')),
]
print("%-20s %-8s %-14s %-14s" % ("dir","files","listdir_med","stat300_med"))
for name, p in targets:
    if not os.path.isdir(p):
        print("%-20s %s" % (name, "MISSING")); continue
    ld=[]; st=[]
    for _ in range(5):
        t0=time.perf_counter(); fs=os.listdir(p); t1=time.perf_counter()
        ld.append((t1-t0)*1000)
    sample = fs[:300]
    for _ in range(5):
        t0=time.perf_counter()
        for f in sample:
            try: os.path.getsize(os.path.join(p,f))
            except: pass
        t1=time.perf_counter()
        st.append((t1-t0)*1000)
    print("%-20s %-8d %-14.2f %-14.2f" % (name, len(fs), statistics.median(ld), statistics.median(st)))
