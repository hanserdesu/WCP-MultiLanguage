# -*- coding: utf-8 -*-
"""DE/YUE 补漏：这两份是 FR 模板派生，preload 段的变量名还是 Md5(fr)（模板残留）。
按实际文本打补丁（锚点用 Md5(fr) 行），顺带确认这是派生模板的既有行为、不改动。
"""
from pathlib import Path

ROOT = Path(r'D:/ATooManyLanguage')
FILES = [
    ('German',    'mod_sentence_audio_de/SentenceAudioDeMod.cs'),
    ('Contonese', 'mod_sentence_audio_yue/SentenceAudioYueMod.cs'),
]

for repo, rel in FILES:
    p = ROOT / repo / rel
    raw = p.read_bytes()
    bom = raw[:3] == b'\xef\xbb\xbf'
    text = (raw[3:] if bom else raw).decode('utf-8').replace('\r\n', '\n')

    old = '''                    string p = Path.Combine(_packAudioDir, Md5(fr) + ".mp3");
                    if (File.Exists(p)) file = p;'''
    new = '''                    string p = Path.Combine(_packAudioDir, Md5(fr) + ".mp3");
                    if (!File.Exists(p) && _audioFallback != null && _audioFallback.Value)
                        p = Path.Combine(_legacyAudioDir, Md5(fr) + ".mp3");
                    if (File.Exists(p)) file = p;'''
    assert old in text, '%s: preload 锚点未找到' % rel
    text = text.replace(old, new, 1)
    out = text.replace('\n', '\r\n').encode('utf-8')
    if bom:
        out = b'\xef\xbb\xbf' + out
    p.write_bytes(out)
    print('OK  %s/%s' % (repo, rel))
print('完成。')
