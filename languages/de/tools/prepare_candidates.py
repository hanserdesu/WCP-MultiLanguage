# -*- coding: utf-8 -*-
"""data/raw/de_50k.txt (OpenSubtitles 2018 德语词频, 词形) -> work/cand_NN.json
每块 200 词, 供主会话直接精选 (WORK_RULES.md: 不派子代理)。
预过滤: 数字/URL/单字母/明显非词形标记。"""
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'data' / 'raw' / 'de_50k.txt'
CHUNK = 200
TOP_N = 7000

BAD = re.compile(r'[\d<&=*_\[\]|~^`@#$%+\\/]')


def main():
    out = []
    rank = 0
    for line in SRC.read_text(encoding='utf-8').splitlines():
        parts = line.strip().rsplit(' ', 1)
        if len(parts) != 2:
            continue
        w = parts[0].strip()
        if not w or BAD.search(w):
            continue
        if len(w) < 1:
            continue
        if len(w) == 1 and w not in ('a',):
            continue
        rank += 1
        if rank > TOP_N:
            break
        out.append({'word': w, 'rank': rank})

    work = ROOT / 'work'
    work.mkdir(exist_ok=True)
    n = 0
    for i in range(0, len(out), CHUNK):
        p = work / f'cand_{n:02d}.json'
        p.write_text(json.dumps(out[i:i + CHUNK], ensure_ascii=False, indent=0),
                     encoding='utf-8')
        n += 1
    print(f'候选 {len(out)} 词形 -> {n} 块 (cand_NN.json)')


if __name__ == '__main__':
    main()
