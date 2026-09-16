# -*- coding: utf-8 -*-
"""B 类改造：移除 de/fr/ru/yue 旧插件的 legacy 音频回退（迁移期已结束）。

改动内容：
  1. 4 个 SentenceAudio*Mod.cs：
     - 删掉 AudioDirName 常量与 _audioDir 字段（legacy 目录）；
     - Awake 里不再解析 legacy 目录；
     - Resolve/Preload 的 "pack 优先, legacy 回退" 改为只查 pack；
     - 日志去掉 legacy dir 字段。
  2. 4 个 *WordListMod.cs：
     - PrePlayWordAudio 的音频路径从 wcp/<lang>_word_audio 改为
       packs/<lang>/audio/word（与宿主 ResourceRouter 同一物理目录，
       词表文件本身不变）。

依据（2026-09-16 实测）：
  - fr/yue：旧目录与 pack 逐字节同集合（差集 0），回退无增量。
  - de/ru：pack 覆盖当前语料 98.5%/100%（de 363 句差异 = 语料更新前的旧
    发音，属于应淘汰的陈旧副本而非缺失）；词音频 de 缺 4 词（旧目录有，
    属历史残留——保留旧目录本身即可，不靠插件回退）。
  - 宿主 WcpHost 0.4.0 的 WordAudioPrefix 已按 pack 解析词音频并在 miss 时
    放行游戏（而游戏原生目录也被兼容层补齐），四语言词书在宿主接管时发音
    不依赖这些旧插件。
"""
import sys
from pathlib import Path

ROOT = Path(r'D:/ATooManyLanguage')

# (仓库, 相对路径, lang)
SENT = [
    ('French',   'mod_sentence_audio_fr/SentenceAudioFrMod.cs', 'fr'),
    ('German',   'mod_sentence_audio_de/SentenceAudioDeMod.cs', 'de'),
    ('Russian',  'mod_sentence_audio_ru/SentenceAudioRuMod.cs', 'ru'),
    ('Contonese','mod_sentence_audio_yue/SentenceAudioYueMod.cs', 'yue'),
]
WORD = [
    ('French',    'mod_fr_wordlist/FrWordListMod.cs',   'fr_word_audio'),
    ('German',    'mod_de_wordlist/DeWordListMod.cs',   'de_word_audio'),
    ('Russian',   'mod_ru_wordlist/RuWordListMod.cs',   'ru_word_audio'),
    ('Contonese', 'mod_yue_wordlist/YueWordListMod.cs', 'yue_word_audio'),
]


def load(p: Path):
    raw = p.read_bytes()
    bom = raw[:3] == b'\xef\xbb\xbf'
    body = raw[3:] if bom else raw
    crlf = b'\r\n' in body
    text = body.decode('utf-8').replace('\r\n', '\n')
    return text, bom, crlf


def save(p: Path, text: str, bom: bool, crlf: bool):
    out = text.replace('\n', '\r\n').encode('utf-8') if crlf else text.encode('utf-8')
    if bom:
        out = b'\xef\xbb\xbf' + out
    p.write_bytes(out)


fail = []

# ── SentenceAudio*Mod.cs ────────────────────────────────────────────
for repo, rel, lang in SENT:
    p = ROOT / repo / rel
    text, bom, crlf = load(p)
    orig = text

    # 1) 删 AudioDirName 常量行（及其上一行注释里的 legacy 提法改写）
    old_const = '        private const string AudioDirName = "%s_sentence_audio";\n' % lang
    if old_const not in text:
        fail.append('%s: AudioDirName 未找到' % rel); continue
    text = text.replace(old_const, '')
    text = text.replace(
        '        // 资源命名空间化: pack 优先 (packs/<lang>/audio/sentence),\n'
        '        // legacy 目录 (<lang>_sentence_audio) 仅作迁移期回退。\n',
        '        // 资源命名空间化: 只读 pack (packs/<lang>/audio/sentence)。\n'
        '        // legacy 目录 (<lang>_sentence_audio) 回退已移除（迁移期结束，2026-09-16）。\n')

    # 2) 删 _audioDir 字段
    old_field = '        private string _audioDir;\n'
    if old_field in text:
        text = text.replace(old_field, '')

    # 3) Awake：不再解析 legacy
    old_awake = '''            _audioDir = Path.Combine(Application.persistentDataPath,
                AudioDirName);'''
    if old_awake in text:
        text = text.replace(old_awake, '')
    else:
        # 变体：单行
        import re
        text = re.sub(r'\n *private string _audioDir = Path\.Combine\(Application\.persistentDataPath,\s*\n?\s*AudioDirName\);', '', text)
    # 日志去 legacy
    text = text.replace(
        '''            Log.LogInfo(string.Format(
                "WCP Sentence Audio 1.1.0 loaded, pack dir = {0} (存在={1}), legacy dir = {2}",
                _packAudioDir, Directory.Exists(_packAudioDir), _audioDir));''',
        '''            Log.LogInfo(string.Format(
                "WCP Sentence Audio 1.1.0 loaded, pack dir = {0} (存在={1})",
                _packAudioDir, Directory.Exists(_packAudioDir)));''')

    # 4) Resolve/Preload：去掉 legacy 回退
    old_resolve = '''            // pack 优先, legacy 回退 (迁移期); 都没有才判缺失。
            p = Path.Combine(_packAudioDir, key + ".mp3");
            if (!File.Exists(p)) p = Path.Combine(_audioDir, key + ".mp3");
            p = File.Exists(p) ? p : null;'''
    new_resolve = '''            // 只读 pack（legacy 回退已移除）。
            p = Path.Combine(_packAudioDir, key + ".mp3");
            p = File.Exists(p) ? p : null;'''
    if old_resolve in text:
        text = text.replace(old_resolve, new_resolve)
    else:
        fail.append('%s: resolve 段未匹配' % rel); continue

    old_pre = '''                    string p = Path.Combine(_packAudioDir, Md5(fr) + ".mp3");
                    if (!File.Exists(p))
                        p = Path.Combine(_audioDir, Md5(fr) + ".mp3");
                    if (File.Exists(p)) file = p;'''
    new_pre = '''                    string p = Path.Combine(_packAudioDir, Md5(fr) + ".mp3");
                    if (File.Exists(p)) file = p;'''
    if old_pre in text:
        text = text.replace(old_pre, new_pre)
    else:
        fail.append('%s: preload 段未匹配' % rel); continue

    if text != orig:
        save(p, text, bom, crlf)
        print('OK  %s/%s' % (repo, rel))
    else:
        print('--  %s/%s（无变化）' % (repo, rel))

# ── *WordListMod.cs：词音频改读 pack ────────────────────────────────
for repo, rel, dirname in WORD:
    p = ROOT / repo / rel
    text, bom, crlf = load(p)
    lang = dirname.split('_')[0]
    old = '''            string file = System.IO.Path.Combine(Application.persistentDataPath,
                "%s", word + ".mp3");''' % dirname
    new = '''            // 只读 pack（legacy 目录 <persistentDataPath>/%s 回退已移除，
            // 与宿主 ResourceRouter 的 WordAudioDir 同一物理目录）。
            string file = System.IO.Path.Combine(Application.persistentDataPath,
                "..", "packs", "%s", "audio", "word", word + ".mp3");''' % (dirname, lang)
    if old in text:
        text = text.replace(old, new)
        save(p, text, bom, crlf)
        print('OK  %s/%s' % (repo, rel))
    else:
        fail.append('%s: word audio 路径段未匹配' % rel)

print()
if fail:
    print('未完成项:')
    for f in fail:
        print('  -', f)
    sys.exit(1)
print('全部 8 个文件改造完成。')
