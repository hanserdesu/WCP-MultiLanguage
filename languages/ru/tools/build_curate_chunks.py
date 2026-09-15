# -*- coding: utf-8 -*-
"""data/lemmas_ranked.json -> work/cur_NN.json (每块 300 词, 供 LLM 精选)。"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
CHUNK = 300


def main():
    data = json.loads((ROOT / 'data' / 'lemmas_ranked.json').read_text(
        encoding='utf-8'))
    work = ROOT / 'work'
    work.mkdir(exist_ok=True)
    n = 0
    for i in range(0, len(data), CHUNK):
        rows = data[i:i + CHUNK]
        slim = [{'word': w['word'], 'stress': w['stress'], 'pos': w['pos'],
                 'rank': w['rank']} for w in rows]
        p = work / f'cur_{n:02d}.json'
        p.write_text(json.dumps(slim, ensure_ascii=False, indent=0),
                     encoding='utf-8')
        print(p.name, len(slim))
        n += 1
    print(f'共 {n} 块')


if __name__ == '__main__':
    main()
