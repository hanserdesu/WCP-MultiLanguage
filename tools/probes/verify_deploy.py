import os, hashlib
P = r'E:\Steam\steamapps\common\WCP-WordGirlgriend\BepInEx\plugins'
R = r'D:\ATooManyLanguage\MultiLanguage'
repo = {
 'DeWordListMod.dll':  r'languages\de\mod_de_wordlist\DeWordListMod.dll',
 'FrWordListMod.dll':  r'languages\fr\mod_fr_wordlist\FrWordListMod.dll',
 'JpWordListMod.dll':  r'languages\ja\mod_jp_wordlist\JpWordListMod.dll',
 'YueWordListMod.dll': r'languages\yue\mod_yue_wordlist\YueWordListMod.dll',
 'SentenceAudioDeMod.dll':  r'languages\de\mod_sentence_audio_de\SentenceAudioDeMod.dll',
 'SentenceAudioFrMod.dll':  r'languages\fr\mod_sentence_audio_fr\SentenceAudioFrMod.dll',
 'SentenceAudioMod.dll':    r'languages\ja\mod_sentence_audio\SentenceAudioMod.dll',
 'SentenceAudioRuMod.dll':  r'languages\ru\mod_sentence_audio_ru\SentenceAudioRuMod.dll',
 'SentenceAudioYueMod.dll': r'languages\yue\mod_sentence_audio_yue\SentenceAudioYueMod.dll',
}
def h(p):
    return hashlib.sha256(open(p,'rb').read()).hexdigest()[:16] if os.path.exists(p) else 'MISSING'
print("%-26s %-18s %-18s %s" % ("dll","repo","game","status"))
for name, rel in repo.items():
    a = h(os.path.join(R, rel)); b = h(os.path.join(P, name))
    print("%-26s %-18s %-18s %s" % (name, a, b, 'MATCH' if a==b else 'DIFF'))
print()
gp = os.path.join(P, 'WcpHost.dll')
print("WcpHost.dll  game=%s size=%d" % (h(gp), os.path.getsize(gp)))
d = open(gp,'rb').read()
for k in ['性能哨兵','卡顿帧']:
    print("  contains %s: %s" % (k, k.encode('utf-16-le') in d))
print("  contains IsAlive(symbol):", b'IsAlive' in d)
