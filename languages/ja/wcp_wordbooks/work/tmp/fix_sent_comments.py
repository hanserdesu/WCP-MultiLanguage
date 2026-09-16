# -*- coding: utf-8 -*-
"""清掉 4 个 SentenceAudio*Mod.cs 头部注释里残留的 legacy 目录名（probe 判据是全文 -match）。"""
from pathlib import Path

ROOT = Path(r'D:/ATooManyLanguage')
FILES = [
    ('French',    'mod_sentence_audio_fr/SentenceAudioFrMod.cs', 'fr'),
    ('German',    'mod_sentence_audio_de/SentenceAudioDeMod.cs', 'de'),
    ('Russian',   'mod_sentence_audio_ru/SentenceAudioRuMod.cs', 'ru'),
    ('Contonese', 'mod_sentence_audio_yue/SentenceAudioYueMod.cs', 'yue'),
]

for repo, rel, lang in FILES:
    p = ROOT / repo / rel
    raw = p.read_bytes()
    bom = raw[:3] == b'\xef\xbb\xbf'
    text = (raw[3:] if bom else raw).decode('utf-8').replace('\r\n', '\n')
    old = '// 例句旁挂 ▶ 按钮, 点击播放 %s_sentence_audio/<md5(%s)>.mp3 (由' % (lang, lang)
    new = '// 例句旁挂 ▶ 按钮, 点击播放 packs/%s/audio/sentence/<md5(%s)>.mp3 (由' % (lang, lang)
    if old in text:
        text = text.replace(old, new)
        out = text.replace('\n', '\r\n').encode('utf-8')
        if bom:
            out = b'\xef\xbb\xbf' + out
        p.write_bytes(out)
        print('OK  %s' % rel)
    else:
        print('--  %s（无该行，跳过）' % rel)
