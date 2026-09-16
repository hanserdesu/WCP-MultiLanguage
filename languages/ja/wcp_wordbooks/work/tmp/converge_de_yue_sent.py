# -*- coding: utf-8 -*-
"""DE/YUE sentence 插件补齐 AudioFallback（它们上一轮只删了声明、漏了引用点）。"""
from pathlib import Path

ROOT = Path(r'D:/ATooManyLanguage')
FILES = [
    ('German',    'mod_sentence_audio_de/SentenceAudioDeMod.cs', 'de', '德语'),
    ('Contonese', 'mod_sentence_audio_yue/SentenceAudioYueMod.cs', 'yue', '粤语'),
]

for repo, rel, lang, cn in FILES:
    p = ROOT / repo / rel
    raw = p.read_bytes()
    bom = raw[:3] == b'\xef\xbb\xbf'
    text = (raw[3:] if bom else raw).decode('utf-8').replace('\r\n', '\n')

    # 1) 常量区补字段声明（找 PackLangCode 常量行，在其后补 _legacyAudioDir/_audioFallback）
    anchor = '        private const string PackLangCode = "%s";' % lang
    assert anchor in text, '%s: PackLangCode 未找到' % rel
    decl = (anchor + '\n'
            '        // legacy 目录与开关：AudioFallback=true 时恢复迁移期回退（数据保留，只读）。\n'
            '        private string _legacyAudioDir;\n'
            '        private ConfigEntry<bool> _audioFallback;')
    text = text.replace(anchor, decl)

    # 2) Awake：pack 目录解析后补 legacy 解析 + 配置 + 日志
    old_awake = ('            _packAudioDir = Path.Combine(packsRoot, PackLangCode, "audio", "sentence");\n'
                 '\n'
                 '            Log.LogInfo(string.Format(\n'
                 '                "WCP Sentence Audio 1.1.0 loaded, pack dir = {0} (存在={1})",\n'
                 '                _packAudioDir, Directory.Exists(_packAudioDir)));')
    new_awake = ('            _packAudioDir = Path.Combine(packsRoot, PackLangCode, "audio", "sentence");\n'
                 '            _legacyAudioDir = Path.Combine(Application.persistentDataPath,\n'
                 '                PackLangCode + "_sentence_audio");\n'
                 '            _audioFallback = Config.Bind("Legacy", "AudioFallback", false,\n'
                 '                "旧版兼容开关（默认关）。true 时例句音频在 pack 缺失时回退读 legacy 目录 "\n'
                 '                + "<persistentDataPath>/" + PackLangCode + "_sentence_audio（迁移期行为，只读）。");\n'
                 '            Log.LogInfo(string.Format(\n'
                 '                "WCP Sentence Audio 1.1.0 loaded, pack dir = {0} (存在={1}), legacy fallback = {2}",\n'
                 '                _packAudioDir, Directory.Exists(_packAudioDir),\n'
                 '                _audioFallback != null && _audioFallback.Value));')
    assert old_awake in text, '%s: Awake 段未匹配' % rel
    text = text.replace(old_awake, new_awake)

    out = text.replace('\n', '\r\n').encode('utf-8')
    if bom:
        out = b'\xef\xbb\xbf' + out
    p.write_bytes(out)
    print('OK  %s/%s' % (repo, rel))
print('DE/YUE 收敛完成。')
