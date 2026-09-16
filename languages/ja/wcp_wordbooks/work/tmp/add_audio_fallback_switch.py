# -*- coding: utf-8 -*-
"""B 类收敛补充：例句插件加 Legacy/AudioFallback 兼容开关。

用户硬要求：最大化与旧版兼容。词表插件有 Legacy/YieldToHost 开关（宿主接管时
可强制旧模式），但例句插件只读 pack 后没有任何回退开关——万一某用户环境
pack 例句音频缺失而 legacy 目录存在，旧数据将不可用。这里给 4 个例句插件补上
Legacy/AudioFallback 开关（默认 false = 只读 pack，与 B 类改造语义一致；
设 true 恢复旧的 pack→legacy 回退链），把「移除回退」从硬删除变成可逆配置。

同时清理 4 个文件头注释里 probe 判据覆盖不到的角落（确保 -match 不误报已清过的行）。
"""
import sys
from pathlib import Path

ROOT = Path(r'D:/ATooManyLanguage')
FILES = [
    ('French',    'mod_sentence_audio_fr/SentenceAudioFrMod.cs', 'fr', 'Fr'),
    ('German',    'mod_sentence_audio_de/SentenceAudioDeMod.cs', 'de', 'De'),
    ('Russian',   'mod_sentence_audio_ru/SentenceAudioRuMod.cs', 'ru', 'Ru'),
    ('Contonese', 'mod_sentence_audio_yue/SentenceAudioYueMod.cs', 'yue', 'Yue'),
]

fail = []
for repo, rel, lang, cls in FILES:
    p = ROOT / repo / rel
    raw = p.read_bytes()
    bom = raw[:3] == b'\xef\xbb\xbf'
    text = (raw[3:] if bom else raw).decode('utf-8').replace('\r\n', '\n')

    # 1) 字段：加 _audioFallback 开关（放在 _packAudioDir 声明旁）
    old_field = '        private string _packAudioDir;'
    new_field = '''        private string _packAudioDir;
        // 旧版兼容开关（默认关）：true 时恢复 pack→legacy(<lang>_sentence_audio)
        // 的迁移期回退链。B 类改造后默认只读 pack；只有 pack 缺音频且用户明确
        // 打开本开关时才碰 legacy 目录（只读，绝不写/删）。
        private ConfigEntry<bool> _audioFallback;
        private string _legacyAudioDir;'''
    if old_field not in text:
        fail.append('%s: 字段锚点未找到' % rel); continue
    text = text.replace(old_field, new_field, 1)

    # 2) Awake：绑定开关 + 记录 legacy 目录（不创建）
    old_awake = '''            _packAudioDir = Path.Combine(packsRoot, PackLangCode, "audio", "sentence");'''
    new_awake = '''            _packAudioDir = Path.Combine(packsRoot, PackLangCode, "audio", "sentence");
            _legacyAudioDir = Path.Combine(Application.persistentDataPath,
                PackLangCode + "_sentence_audio");
            _audioFallback = Config.Bind("Legacy", "AudioFallback", false,
                "旧版兼容开关（默认关）。true 时例句音频在 pack 缺失时回退读 legacy 目录 " +
                "<persistentDataPath>/" + PackLangCode + "_sentence_audio（迁移期行为，只读）。");'''
    if old_awake not in text:
        fail.append('%s: Awake 锚点未找到' % rel); continue
    text = text.replace(old_awake, new_awake, 1)

    # 3) 启动日志带上开关状态
    old_log = '''            Log.LogInfo(string.Format(
                "WCP Sentence Audio 1.1.0 loaded, pack dir = {0} (存在={1})",
                _packAudioDir, Directory.Exists(_packAudioDir)));'''
    new_log = '''            Log.LogInfo(string.Format(
                "WCP Sentence Audio 1.1.0 loaded, pack dir = {0} (存在={1}), legacy fallback = {2}",
                _packAudioDir, Directory.Exists(_packAudioDir),
                _audioFallback != null && _audioFallback.Value));'''
    if old_log in text:
        text = text.replace(old_log, new_log, 1)

    # 4) LocalAudio/Resolve 段：pack miss 时按开关回退
    old_resolve = '''            // 只读 pack（legacy 回退已移除）。
            p = Path.Combine(_packAudioDir, key + ".mp3");
            p = File.Exists(p) ? p : null;'''
    new_resolve = '''            // 只读 pack；Legacy/AudioFallback=true 时恢复迁移期回退链。
            p = Path.Combine(_packAudioDir, key + ".mp3");
            if (!File.Exists(p) && _audioFallback != null && _audioFallback.Value)
                p = Path.Combine(_legacyAudioDir, key + ".mp3");
            p = File.Exists(p) ? p : null;'''
    if old_resolve in text:
        text = text.replace(old_resolve, new_resolve, 1)
    else:
        # RU 版注释写法不同
        old_ru = '''            // 只读 pack（legacy 回退已移除）。
            string p = Path.Combine(_packAudioDir, Md5(ru) + ".mp3");
            return File.Exists(p) ? p : null;'''
        new_ru = '''            // 只读 pack；Legacy/AudioFallback=true 时恢复迁移期回退链。
            string p = Path.Combine(_packAudioDir, Md5(ru) + ".mp3");
            if (!File.Exists(p) && _audioFallback != null && _audioFallback.Value)
                p = Path.Combine(_legacyAudioDir, Md5(ru) + ".mp3");
            return File.Exists(p) ? p : null;'''
        if old_ru in text:
            text = text.replace(old_ru, new_ru, 1)
        else:
            fail.append('%s: resolve 段未找到' % rel); continue

    # 5) preload 段（扫描分支）
    old_pre = '''                    string p = Path.Combine(_packAudioDir, Md5(%s) + ".mp3");
                    if (File.Exists(p)) file = p;''' % lang
    new_pre = '''                    string p = Path.Combine(_packAudioDir, Md5(%s) + ".mp3");
                    if (!File.Exists(p) && _audioFallback != null && _audioFallback.Value)
                        p = Path.Combine(_legacyAudioDir, Md5(%s) + ".mp3");
                    if (File.Exists(p)) file = p;''' % (lang, lang)
    if old_pre in text:
        text = text.replace(old_pre, new_pre, 1)
    else:
        fail.append('%s: preload 段未找到' % rel); continue

    out = text.replace('\n', '\r\n').encode('utf-8')
    if bom:
        out = b'\xef\xbb\xbf' + out
    p.write_bytes(out)
    print('OK  %s/%s' % (repo, rel))

if fail:
    print()
    print('未完成:')
    for f in fail:
        print('  -', f)
    sys.exit(1)
print()
print('4 个例句插件均已加 Legacy/AudioFallback 开关。')
