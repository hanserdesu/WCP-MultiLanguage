import os
P = r'E:\Steam\steamapps\common\WCP-WordGirlgriend\BepInEx\plugins'
cases = [
    ('SentenceAudioDeMod.dll',  'OwnWordCount', 'mod_sentence_audio_de'),
    ('SentenceAudioFrMod.dll',  'OwnWordCount', 'mod_sentence_audio_fr'),
    ('SentenceAudioMod.dll',    'OwnWordCount', 'mod_sentence_audio'),
    ('SentenceAudioRuMod.dll',  'OwnWordCount', 'mod_sentence_audio_ru'),
    ('SentenceAudioYueMod.dll', 'OwnWordCount', 'mod_sentence_audio_yue'),
]
print("%-26s %-14s %-10s %s" % ("dll", "OwnWordCount", "old_disk", "size"))
for dll, needle, d in cases:
    data = open(os.path.join(P, dll), 'rb').read()
    has = needle.encode('utf-8') in data or needle.encode('utf-16-le') in data
    # 旧结构特征: ManagedBookSelected 里 bool ok 的 IL 无法看, 改看源码侧是否还有旧模式
    print("%-26s %-14s %-10s %d" % (dll, has, '-', len(data)))
