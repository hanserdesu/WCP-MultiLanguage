import os, hashlib, random, itertools
L = r'C:\Users\hanserdesu\AppData\LocalLow\WCP'
pk = os.path.join(L,'packs'); TGT = os.path.join(L,'vocabulary')
langs = {}
for d in sorted(os.listdir(pk)):
    w = os.path.join(pk, d, 'audio', 'word')
    if os.path.isdir(w): langs[d] = w
def md5(p):
    try: return hashlib.md5(open(p,'rb').read()).hexdigest()
    except: return 'ERR'
random.seed(11)
print("=== 跨语言同名文件内容一致性（每对抽 40 个）===")
tot_same = tot_diff = 0
for a, b in itertools.combinations(sorted(langs), 2):
    na = set(os.listdir(langs[a])); nb = set(os.listdir(langs[b]))
    inter = sorted(na & nb)
    if not inter: continue
    samp = random.sample(inter, min(40, len(inter)))
    same = diff = 0
    for n in samp:
        if md5(os.path.join(langs[a],n)) == md5(os.path.join(langs[b],n)): same += 1
        else: diff += 1
    tot_same += same; tot_diff += diff
    flag = "OK" if diff == 0 else "!!! MISMATCH"
    print("  %-5s ∩ %-5s inter=%-6d sample=%-4d SAME=%-4d DIFF=%-3d %s" % (a,b,len(inter),len(samp),same,diff,flag))
print()
print("总计 SAME=%d DIFF=%d" % (tot_same, tot_diff))
# vocabulary 中同名文件是否等于源文件
print()
print("=== vocabulary 中文件 vs 源文件（抽 ja 200 个）===")
ja = sorted(os.listdir(langs['ja']))
samp = random.sample(ja, 200)
miss=0; sizeok=0; sizemiss=0; hashmis=0
for n in samp:
    t = os.path.join(TGT,n)
    if not os.path.exists(t): miss+=1; continue
    if os.path.getsize(t) == os.path.getsize(os.path.join(langs['ja'],n)):
        sizeok+=1
        if md5(t) != md5(os.path.join(langs['ja'],n)): hashmis+=1
    else: sizemiss+=1
print("  missing=%d size_ok=%d size_mismatch=%d (size_ok 中 md5 不符=%d)" % (miss,sizeok,sizemiss,hashmis))
