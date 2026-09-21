import os, hashlib, random, itertools
L = r'C:\Users\hanserdesu\AppData\LocalLow\WCP'
pk = os.path.join(L,'packs'); TGT = os.path.join(L,'vocabulary')
langs = {}
for d in sorted(os.listdir(pk)):
    w = os.path.join(pk, d, 'audio', 'word')
    if os.path.isdir(w): langs[d] = w
def sz(p):
    try: return os.path.getsize(p)
    except: return -1
def md5(p):
    try: return hashlib.md5(open(p,'rb').read()).hexdigest()
    except: return 'ERR'
random.seed(3)
print("=== 同名但内容不同的文件对：大小是否碰撞？===")
print("%-13s %-8s %-10s %-10s %s" % ("pair","sample","size_same","size_diff","结论"))
tot_collide = 0; tot = 0
for a, b in itertools.combinations(sorted(langs), 2):
    na = set(os.listdir(langs[a])); nb = set(os.listdir(langs[b]))
    inter = sorted(na & nb)
    if not inter: continue
    samp = random.sample(inter, min(40, len(inter)))
    ss=0; sd=0
    for n in samp:
        pa = os.path.join(langs[a],n); pb = os.path.join(langs[b],n)
        if md5(pa) == md5(pb): continue   # 内容相同的不算
        tot += 1
        if sz(pa) == sz(pb): ss+=1; tot_collide+=1
        else: sd+=1
    if ss+sd:
        print("%-13s %-8d %-10d %-10d %s" % ("%s∩%s"%(a,b), ss+sd, ss, sd, "!! 大小碰撞" if ss else "ok"))
print()
print("内容不同的样本 %d 个，其中大小恰好相同的 %d 个（%.1f%%）" % (tot, tot_collide, 100*tot_collide/max(tot,1)))
print()
print("=== 决定性验证：vocabulary 里存的是哪一版？ ===")
# 找 de∩fr 的同名文件，看 vocabulary 版本等于谁
de = langs['de']; fr = langs['fr']
inter = sorted(set(os.listdir(de)) & set(os.listdir(fr)))
random.seed(5); samp = random.sample(inter, min(12, len(inter)))
print("%-26s %-12s %-12s %-12s %s" % ("file","de_md5","fr_md5","vocab_md5","vocab 属于"))
match_de=match_fr=neither=0
for n in samp:
    d_ = md5(os.path.join(de,n)); f_ = md5(os.path.join(fr,n))
    t_ = md5(os.path.join(TGT,n)) if os.path.exists(os.path.join(TGT,n)) else 'MISSING'
    who = "de" if t_==d_ else ("fr" if t_==f_ else "neither")
    if who=="de": match_de+=1
    elif who=="fr": match_fr+=1
    else: neither+=1
    print("%-26s %-12s %-12s %-12s %s" % (n[:26], d_[:8], f_[:8], (t_[:8] if t_!='MISSING' else t_), who))
print()
print("vocab 属于: de=%d fr=%d neither=%d" % (match_de, match_fr, neither))
