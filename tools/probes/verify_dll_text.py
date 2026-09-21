import sys, os
P = r'E:\Steam\steamapps\common\WCP-WordGirlgriend\BepInEx\plugins'
R = r'D:\ATooManyLanguage\MultiLanguage\languages'
cases = [
    ('DeWordListMod.dll',  '轮询 Enforce 一并停用', r'de\mod_de_wordlist\DeWordListMod.cs'),
    ('FrWordListMod.dll',  '轮询 Enforce 一并停用', r'fr\mod_fr_wordlist\FrWordListMod.cs'),
    ('JpWordListMod.dll',  '轮询 Enforce 一并停用', r'ja\mod_jp_wordlist\JpWordListMod.cs'),
    ('YueWordListMod.dll', '轮询 Enforce 一并停用', r'yue\mod_yue_wordlist\YueWordListMod.cs'),
]
print("%-24s %-8s %-8s" % ("dll", "in_src", "in_dll"))
for dll, needle, src in cases:
    sp = os.path.join(R, src)
    dp = os.path.join(P, dll)
    src_txt = open(sp, encoding='utf-8').read() if os.path.exists(sp) else ''
    in_src = needle in src_txt
    data = open(dp, 'rb').read()
    in_dll = needle.encode('utf-16-le') in data
    # 顺带看旧文案是否还在（用旧文案的尾巴区分）
    old = '旧词表插件不再打补丁 ('
    old_dll = old.encode('utf-16-le') in data
    print("%-24s %-8s %-8s  old_still=%s" % (dll, in_src, in_dll, old_dll))
