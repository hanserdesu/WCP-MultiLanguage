import os, hashlib, random
L = r'C:\Users\hanserdesu\AppData\LocalLow\WCP'
pk = os.path.join(L,'packs')
FR = os.path.join(pk,'fr','audio','word')
JA = os.path.join(pk,'ja','audio','word')
RU = os.path.join(pk,'ru','audio','word')
TGT = os.path.join(L,'vocabulary')
def names(p): return set(os.listdir(p))
fr, ja, ru = names(FR), names(JA), names(RU)
inter_fj = sorted(fr & ja)
print("fr∩ja = %d ; fr∩ru = %d ; ja∩ru = %d" % (len(inter_fj), len(fr&ru), len(ja&ru)))
random.seed(7)
samp = random.sample(inter_fj, min(15, len(inter_fj)))
def md5(p):
    try: return hashlib.md5(open(p,'rb').read()).hexdigest()
    except Exception as e: return 'ERR:'+str(e)
print()
print("%-24s %-10s %-10s %-10s %s" % ("file", "fr_md5", "ja_md5", "vocab_md5", "fr==ja?"))
same=0; diff=0
for n in samp:
    a = md5(os.path.join(FR,n)); b = md5(os.path.join(JA,n))
    v = md5(os.path.join(TGT,n)) if os.path.exists(os.path.join(TGT,n)) else 'MISSING'
    eq = (a==b)
    same += 1 if eq else 0; diff += 0 if eq else 1
    print("%-24s %-10s %-10s %-10s %s" % (n[:24], a[:8], b[:8], v[:8], "SAME" if eq else "DIFF"))
print()
print("样本: SAME=%d DIFF=%d" % (same, diff))
