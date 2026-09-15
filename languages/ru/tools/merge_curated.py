# -*- coding: utf-8 -*-
"""合并精选批次 -> output/russian_books.json {levels:{a1,a2,b1,b2}}。

词条: {word, stress, pos, zh, level} (pos 为展示用标签)。
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / 'work'
OUT = ROOT / 'output' / 'russian_books.json'

LEVELS = ('a1', 'a2', 'b1', 'b2')


def main():
    lemmas = {w['word']: w for w in json.loads(
        (ROOT / 'data' / 'lemmas_ranked.json').read_text(encoding='utf-8'))}
    levels = {lv: [] for lv in LEVELS}
    seen = set()
    n_drop = 0
    n = 0
    while (WORK / f'cur_{n:02d}.json').exists():
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
            src = lemmas.get(w, {})
            levels[it['level']].append({
                'word': w, 'stress': src.get('stress', ''),
                'pos': src.get('pos', 'n.'),
                'zh': it['zh'].strip(), 'level': it['level'],
            })
        n += 1
    total = sum(len(v) for v in levels.values())
    for lv in LEVELS:
        levels[lv].sort(key=lambda x: lemmas.get(x['word'], {}).get(
            'rank', 99999))
    doc = {'meta': {'total': total, 'dropped': n_drop,
                    'source': 'OpenSubtitles freq (hermitdave) + pymorphy3 '
                              '+ Wiktionary stress + LLM curation'},
           'levels': levels}
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1),
                   encoding='utf-8')
    print('级别分布:', {lv: len(levels[lv]) for lv in LEVELS},
          '合计', total, 'drop', n_drop)


if __name__ == '__main__':
    main()
