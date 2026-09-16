# -*- coding: utf-8 -*-
"""B 类收敛：给 4 个 *WordListMod.cs 补回可配置的词音频回退（与既有 Legacy/* 开关同风格）。

现状（收敛前）：我上一轮把 PrePlayWordAudio 改成硬编码 packs/<lang>/audio/word，
丢掉了回退能力——与项目「旧版兼容优先」原则不符。

收敛后：默认读 pack；Legacy/WordAudioFallback=true 时回退旧目录
<persistentDataPath>/<lang>_word_audio（数据还在，只读）。风格对齐
Legacy/YieldToHost、Legacy/AllowSharedDatabaseWrites 既有开关。

同时 SentenceAudio*Mod.cs 的 Legacy/AudioFallback 开关已经存在（fr/ru/yue/de
四种模板均带），保持不动。
"""
import sys
from pathlib import Path

ROOT = Path(r'D:/ATooManyLanguage')
FILES = [
    ('French',    'mod_fr_wordlist/FrWordListMod.cs',   'fr', '法语'),
    ('German',    'mod_de_wordlist/DeWordListMod.cs',   'de', '德语'),
    ('Russian',   'mod_ru_wordlist/RuWordListMod.cs',   'ru', '俄语'),
    ('Contonese', 'mod_yue_wordlist/YueWordListMod.cs', 'yue', '粤语'),
]

fail = []
for repo, rel, lang, cn in FILES:
    p = ROOT / repo / rel
    raw = p.read_bytes()
    bom = raw[:3] == b'\xef\xbb\xbf'
    text = (raw[3:] if bom else raw).decode('utf-8').replace('\r\n', '\n')
    orig = text

    # 1) 硬路径 → pack 变量 + 回退变量
    old = '''            // 只读 pack（legacy 目录 <persistentDataPath>/%s_word_audio 回退已移除，
            // 与宿主 ResourceRouter 的 WordAudioDir 同一物理目录）。
            string file = System.IO.Path.Combine(Application.persistentDataPath,
                "..", "packs", "%s", "audio", "word", word + ".mp3");
            Instance.StopWordAudio();
            if (!System.IO.File.Exists(file))
            {
                WarnOnce("word-audio:" + word, "%s独立单词音频缺失: " + word);
                return false;
            }''' % (lang, lang, cn)
    new = '''            // pack 优先（与宿主 ResourceRouter 的 WordAudioDir 同一物理目录）；
            // Legacy/WordAudioFallback=true 时回退旧目录（数据保留，只读）。
            string file = System.IO.Path.Combine(Application.persistentDataPath,
                "..", "packs", "%s", "audio", "word", word + ".mp3");
            Instance.StopWordAudio();
            if (!System.IO.File.Exists(file) && _wordAudioFallback != null && _wordAudioFallback.Value)
                file = System.IO.Path.Combine(Application.persistentDataPath,
                    "%s_word_audio", word + ".mp3");
            if (!System.IO.File.Exists(file))
            {
                WarnOnce("word-audio:" + word, "%s独立单词音频缺失: " + word);
                return false;
            }''' % (lang, lang, cn)
    if old not in text:
        fail.append('%s: 音频路径段未匹配' % rel)
        continue
    text = text.replace(old, new)

    # 2) Awake 里补配置项（紧跟 _yieldToHost 之后）
    anchor = '_yieldToHost = Config.Bind("Legacy", "YieldToHost", true,'
    idx = text.find(anchor)
    if idx < 0:
        fail.append('%s: YieldToHost 锚点未找到' % rel)
        continue
    # 找该语句结束（第一个分号结尾的行）
    line_end = text.find('\n', text.find(');', idx))
    insert = ('\n            _wordAudioFallback = Config.Bind("Legacy", "WordAudioFallback", false,\n'
              '                "旧版兼容开关（默认关）。true 时单词音频在 pack 缺失时回退读 legacy 目录 "\n'
              '                + "<persistentDataPath>/%s_word_audio（迁移期行为，只读）。");' % lang)
    text = text[:line_end] + insert + text[line_end:]

    # 3) 字段声明（找 _yieldToHost 字段行）
    import re
    m = re.search(r'\n(\s+)private .* _yieldToHost;', text)
    if not m:
        fail.append('%s: _yieldToHost 字段未找到' % rel)
        continue
    indent = m.group(1)
    field = '\n%sprivate ConfigEntry<bool> _wordAudioFallback;' % indent
    text = text[:m.start()] + field + text[m.start():]

    if text != orig:
        out = text.replace('\n', '\r\n').encode('utf-8')
        if bom:
            out = b'\xef\xbb\xbf' + out
        p.write_bytes(out)
        print('OK  %s/%s' % (repo, rel))
    else:
        print('--  %s/%s（无变化）' % (repo, rel))

if fail:
    print('\n未完成:')
    for f in fail:
        print('  -', f)
    sys.exit(1)
print('\n4 个词表插件收敛完成。')
