# -*- coding: utf-8 -*-
"""构建例句大规模生产任务:
  1. gen_words_XX.json  — 全部词条 (word/reading/meaning/level/need),
     need = 该词还差的例句数 (无现有例句=3, 有=2)
  2. tr_chunk_XX.tsv    — 待翻译现有例句 (idx/rowid/word/ja/en), 每块550句
输出: work/ 目录
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'output'
WORK = ROOT / 'work'
WORK.mkdir(exist_ok=True)

# ---- 1. 词块 ----
words = {}  # word -> {reading, meaning, level, has_example}


def put(w, reading, meaning, level, has_ex):
    w = (w or '').strip()
    if not w or not meaning:
        return
    cur = words.get(w)
    if cur is None:
        words[w] = {'reading': reading or '', 'meaning': meaning,
                    'level': level, 'has_example': has_ex}
    else:
        cur['has_example'] = cur['has_example'] or has_ex


jlpt = json.loads((OUT / 'jlpt_books.json').read_text(encoding='utf-8'))
for lv in ('n5', 'n4', 'n3', 'n2', 'n1'):
    for r in jlpt['levels'][lv]:
        put(r['word'], r.get('reading'), r.get('meaning'), lv.upper(),
            bool(r.get('example_ja')))
setb = json.loads((OUT / 'setb_books.json').read_text(encoding='utf-8'))
for lv, rows in setb['levels'].items():
    for r in rows:
        put(r['word'], r.get('reading'), r.get('meaning'), r.get('level', lv),
            bool(r.get('example_ja')))
topic = json.loads((OUT / 'topic_books.json').read_text(encoding='utf-8'))
for tag in ('it', 'biz'):
    for r in topic['books'][tag]:
        put(r['word'], r.get('reading'), r.get('meaning'), tag.upper(), False)
themed_p = OUT / 'themed_books.json'
if themed_p.exists():
    themed = json.loads(themed_p.read_text(encoding='utf-8'))
    for tag, rows in themed.get('themes', {}).items():
        for r in rows:
            put(r['word'], r.get('reading'), r.get('meaning'), tag,
                bool(r.get('example_ja')))
kanji = json.loads((OUT / 'kanji_books.json').read_text(encoding='utf-8'))
for r in kanji['books']['kanji']:
    put(r['word'], r.get('reading'), r.get('meaning'), '漢字', False)

word_list = list(words.items())
print('词条总数:', len(word_list),
      '无例句:', sum(1 for _, v in word_list if not v['has_example']))

CHUNK = 400
n_chunks = 0
for i in range(0, len(word_list), CHUNK):
    part = {}
    for w, v in word_list[i:i + CHUNK]:
        need = 3 if not v['has_example'] else 2
        part[w] = {'reading': v['reading'], 'meaning': v['meaning'],
                   'level': v['level'], 'need': need}
    (WORK / f'gen_words_{n_chunks:02d}.json').write_text(
        json.dumps(part, ensure_ascii=False, indent=1), encoding='utf-8')
    n_chunks += 1
print('词块数:', n_chunks)

# ---- 2. 翻译块 (idx >= 1180 的剩余部分) ----
src = ROOT / 'logs' / 'sentence_worklist.tsv'
lines = src.read_text(encoding='utf-8').splitlines()[1180:]
TCHUNK = 550
n_t = 0
for i in range(0, len(lines), TCHUNK):
    part = lines[i:i + TCHUNK]
    (WORK / f'tr_chunk_{n_t:02d}.tsv').write_text(
        '\n'.join(part), encoding='utf-8')
    n_t += 1
print('翻译块数:', n_t, '(每块', TCHUNK, '句)')
