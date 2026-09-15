# -*- coding: utf-8 -*-
"""合并精选批次 -> output/french_books.json {levels:{a1,a2,b1,b2}}。

词条: {word, ipa, pos, zh, level} (pos 为展示用标签, 已规范化)。
"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / 'work'
OUT = ROOT / 'output' / 'french_books.json'

POS_MAP = {
    'n.m': 'n.m.', 'n.f': 'n.f.', 'n': 'n.', 'v': 'v.', 'aux': 'v.',
    'adj': 'adj.', 'adv': 'adv.', 'pron': 'pron.', 'prép': 'prép.',
    'conj': 'conj.', 'det': 'det.', 'art': 'art.', 'interj': 'interj.',
    'onoma': 'interj.', 'num': 'num.',
}
LEVELS = ('a1', 'a2', 'b1', 'b2')


def main():
    levels = {lv: [] for lv in LEVELS}
    seen = set()
    n_drop = 0
    n = 0
    while (WORK / f'cur_{n:02d}.json').exists():
        src = json.loads((WORK / f'cur_{n:02d}.json').read_text(
            encoding='utf-8'))
        pos_of = {w['word']: w['pos'] for w in src}
        ipa_of = {w['word']: w['ipa'] for w in src}
        outf = WORK / f'cur_out_{n:02d}.json'
        if not outf.exists():
            print(f'缺少 cur_out_{n:02d}.json, 终止')
            sys.exit(1)
        d = json.loads(outf.read_text(encoding='utf-8'))
        n_drop += len(d.get('drop', []))
        for it in d['kept']:
            w = it['word']
            if w in seen:
                continue
            seen.add(w)
            pos = POS_MAP.get(pos_of.get(w, ''), 'n.')
            levels[it['level']].append({
                'word': w, 'ipa': ipa_of.get(w, ''), 'pos': pos,
                'zh': it['zh'].strip(), 'level': it['level'],
            })
        n += 1
    total = sum(len(v) for v in levels.values())
    for lv in LEVELS:
        levels[lv].sort(key=lambda x: x['word'])
    doc = {'meta': {'total': total, 'dropped': n_drop,
                    'source': 'Lexique383 (lexique.org) + LLM curation'},
           'levels': levels}
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1),
                   encoding='utf-8')
    print('级别分布:', {lv: len(levels[lv]) for lv in LEVELS},
          '合计', total, 'drop', n_drop)


if __name__ == '__main__':
    main()
