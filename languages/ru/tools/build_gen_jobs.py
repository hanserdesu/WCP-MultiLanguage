# -*- coding: utf-8 -*-
"""output/russian_books.json -> work/gen_words_NN.json (每块 100 词, 供例句代理)。"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
CHUNK = 100


def main():
    data = json.loads((ROOT / 'output' / 'russian_books.json').read_text(
        encoding='utf-8'))
    work = ROOT / 'work'
    rows = []
    for lv in ('a1', 'a2', 'b1', 'b2'):
        rows.extend(data['levels'][lv])
    n = 0
    for i in range(0, len(rows), CHUNK):
        part = rows[i:i + CHUNK]
        slim = [{'word': w['word'], 'pos': w['pos'], 'zh': w['zh'],
                 'level': w['level']} for w in part]
        p = work / f'gen_words_{n:02d}.json'
        p.write_text(json.dumps(slim, ensure_ascii=False, indent=0),
                     encoding='utf-8')
        n += 1
    print(f'共 {len(rows)} 词 -> {n} 个例句批次')


if __name__ == '__main__':
    main()
