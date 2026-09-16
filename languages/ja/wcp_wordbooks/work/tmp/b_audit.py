# -*- coding: utf-8 -*-
"""B 类改造质量收敛审查（只读，不改任何东西）。

五个维度：
  A. 游戏本体集成风险：DLL 是否引用 Assembly-CSharp / Harmony 钩子是否仍按需
  B. 与旧版兼容：旧数据文件是否还有读路径 / 目录是否被创建
  C. 源码一致性：4 语言工程 vs ML languages/ 副本是否一致
  D. 行为矩阵：宿主接管/未接管 × 词音频/例句音频 每格谁负责
  E. 残留清单：源码/文档里是否还有指向旧目录的活引用
"""
import re
from pathlib import Path

ROOT = Path(r'D:/ATooManyLanguage')
GAME = Path(r'E:/steam/steamapps/common/WCP-WordGirlgriend')
PLUGINS = GAME / 'BepInEx/plugins'
LANGS = ['fr', 'de', 'ru', 'yue']

print('=' * 72)
print('A. 游戏本体集成风险（DLL 程序集引用）')
print('=' * 72)
import ctypes
from pathlib import Path as P

def refs_of(dll: Path):
    """用 Mono.Cecil（游戏自带）读程序集引用，拿不到就用字节粗查。"""
    cecil = GAME / 'BepInEx/core/Mono.Cecil.dll'
    if cecil.is_file():
        import clr  # 不一定有 pythonnet；失败则走字节粗查
    return None

# 直接用字节粗查（程序集引用表里程序集名以 UTF-8 出现在元数据中）
files = [
    PLUGINS / 'SentenceAudioFrMod.dll', PLUGINS / 'SentenceAudioDeMod.dll',
    PLUGINS / 'SentenceAudioRuMod.dll', PLUGINS / 'SentenceAudioYueMod.dll',
    PLUGINS / 'FrWordListMod.dll', PLUGINS / 'DeWordListMod.dll',
    PLUGINS / 'RuWordListMod.dll', PLUGINS / 'YueWordListMod.dll',
]
for dll in files:
    if not dll.is_file():
        print('!! 缺少部署件:', dll.name)
        continue
    data = dll.read_bytes().decode('latin-1', errors='ignore')
    refs_acs = 'Assembly-CSharp' in data
    # Unity 模块引用正常（UnityEngine.*），Assembly-CSharp 引用 = 编译期绑定游戏类型
    print('%-28s 引用 Assembly-CSharp: %s' % (dll.name, refs_acs))

print()
print('=' * 72)
print('B. 与旧版兼容（改动后旧数据/旧行为是否仍可用）')
print('=' * 72)
# B1: 例句插件是否会写/删 legacy 目录（只读移除，不应出现删除逻辑）
sent_files = {
    'fr': ROOT / 'French/mod_sentence_audio_fr/SentenceAudioFrMod.cs',
    'de': ROOT / 'German/mod_sentence_audio_de/SentenceAudioDeMod.cs',
    'ru': ROOT / 'Russian/mod_sentence_audio_ru/SentenceAudioRuMod.cs',
    'yue': ROOT / 'Contonese/mod_sentence_audio_yue/SentenceAudioYueMod.cs',
}
for lang, p in sent_files.items():
    t = p.read_text(encoding='utf-8')
    writes = re.findall(r'(Delete|Move|Directory\.Delete|File\.Delete)[^\n]*%s_sentence_audio' % lang, t)
    print('%s: 例句插件对 legacy 目录有写/删操作: %s' % (lang, writes if writes else '无（只不再读）'))

# B2: 词表插件改后路径是否真实存在于用户机（pack 目录）
home = Path.home()
for lang in LANGS:
    pd = home / 'AppData/LocalLow/WCP/packs' / lang / 'audio/word'
    print('%s: packs 词音频目录存在=%s 文件数=%d' % (lang, pd.is_dir(), len(list(pd.glob('*.mp3'))) if pd.is_dir() else 0))

# B3: 宿主 0.4.0 兼容层仍在（词音频 miss 时游戏原生目录有兜底）
host_dll = PLUGINS / 'WcpHost.dll'
host_data = host_dll.read_bytes().decode('latin-1', errors='ignore')
print('宿主 0.4.0 兼容层在部署件中: mirror=%s candidates=%s' % (
    'MirrorWordAudio' in host_data or 'wcp-mirror' in host_data,
    'CandidateForms' in host_data))

print()
print('=' * 72)
print('C. 源码一致性（语言工程 vs ML languages/ 副本）')
print('=' * 72)
pairs = [
    ('French/mod_sentence_audio_fr/SentenceAudioFrMod.cs', 'languages/fr/mod_sentence_audio_fr/SentenceAudioFrMod.cs'),
    ('German/mod_sentence_audio_de/SentenceAudioDeMod.cs', 'languages/de/mod_sentence_audio_de/SentenceAudioDeMod.cs'),
    ('Russian/mod_sentence_audio_ru/SentenceAudioRuMod.cs', 'languages/ru/mod_sentence_audio_ru/SentenceAudioRuMod.cs'),
    ('Contonese/mod_sentence_audio_yue/SentenceAudioYueMod.cs', 'languages/yue/mod_sentence_audio_yue/SentenceAudioYueMod.cs'),
    ('French/mod_fr_wordlist/FrWordListMod.cs', 'languages/fr/mod_fr_wordlist/FrWordListMod.cs'),
    ('German/mod_de_wordlist/DeWordListMod.cs', 'languages/de/mod_de_wordlist/DeWordListMod.cs'),
    ('Russian/mod_ru_wordlist/RuWordListMod.cs', 'languages/ru/mod_ru_wordlist/RuWordListMod.cs'),
    ('Contonese/mod_yue_wordlist/YueWordListMod.cs', 'languages/yue/mod_yue_wordlist/YueWordListMod.cs'),
]
bad = 0
for a, b in pairs:
    pa, pb = ROOT / a, ROOT / 'MultiLanguage' / b
    same = pa.read_bytes() == pb.read_bytes()
    if not same:
        bad += 1
    print('%-58s %s' % (a, '一致' if same else '!! 不一致'))
print('不一致数:', bad)

print()
print('=' * 72)
print('D. 行为矩阵（每格谁负责发音）')
print('=' * 72)
print('''场景                        | 词音频                     | 例句音频
宿主接管 + pack 命中        | WcpHost(0.4.0)             | 宿主 SentenceAudioService / 旧插件(pack)
宿主接管 + pack miss        | 放行→游戏原生目录(已镜像)  | 旧插件: 只查 pack → 静默无按钮/无音
宿主未接管(读档中/未激活)   | 游戏原生目录(兼容层已补)   | 旧插件(仍打补丁, 只查 pack)
非受管词书(英语等)          | 游戏原生                   | 旧插件不接(语言谓词不匹配)''')

print()
print('=' * 72)
print('E. 残留引用清单（源码中指向旧目录的活代码）')
print('=' * 72)
pats = [r'\w+_sentence_audio', r'\w+_word_audio']
code_files = list(ROOT.glob('*/mod_*/*.cs'))
hits = defaultdict = {}
count = 0
for f in code_files:
    try:
        t = f.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        continue
    for m in set(re.findall(pats[0], t)) | set(re.findall(pats[1], t)):
        # 排除纯注释行
        for i, line in enumerate(t.splitlines(), 1):
            if m in line and not line.strip().startswith('//'):
                count += 1
                print('%s:%d  %s' % (f.relative_to(ROOT), i, line.strip()[:90]))
if count == 0:
    print('（无活代码残留）')
