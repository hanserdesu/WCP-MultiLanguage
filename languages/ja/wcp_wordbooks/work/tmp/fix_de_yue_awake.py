# -*- coding: utf-8 -*-
"""DE/YUE 的 Awake 补丁：add_audio_fallback_switch.py 的 Awake 锚点因 DE/YUE
此前已被上一轮改造改动过（_audioDir 删除方式不同），实际没插进去。补上。"""
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

    if '_legacyAudioDir' in text:
        print('--  %s（已有，跳过）' % rel)
        continue
    old = '''            _packAudioDir = Path.Combine(packsRoot, PackLangCode, "audio", "sentence");

            Log.LogInfo('''
    new = '''            _packAudioDir = Path.Combine(packsRoot, PackLangCode, "audio", "sentence");
            _legacyAudioDir = Path.Combine(Application.persistentDataPath,
                PackLangCode + "_sentence_audio");
            _audioFallback = Config.Bind("Legacy", "AudioFallback", false,
                "旧版兼容开关（默认关）。true 时例句音频在 pack 缺失时回退读 legacy 目录 " +
                "<persistentDataPath>/" + PackLangCode + "_sentence_audio（迁移期行为，只读）。");

            Log.LogInfo('''
    assert old in text, '%s: Awake 锚点未找到' % rel
    text = text.replace(old, new, 1)
    # 日志加开关状态
    text = text.replace(
        '''                "WCP Sentence Audio 1.1.0 loaded, pack dir = {0} (存在={1})",
                _packAudioDir, Directory.Exists(_packAudioDir)));''',
        '''                "WCP Sentence Audio 1.1.0 loaded, pack dir = {0} (存在={1}), legacy fallback = {2}",
                _packAudioDir, Directory.Exists(_packAudioDir),
                _audioFallback != null && _audioFallback.Value));''')
    out = text.replace('\n', '\r\n').encode('utf-8')
    if bom:
        out = b'\xef\xbb\xbf' + out
    p.write_bytes(out)
    print('OK  %s' % rel)
