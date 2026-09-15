# -*- coding: utf-8 -*-
"""检查 topic_zh_*.json 的键是否有源词表拼写不匹配(错别字)。"""
import json
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'output'
TDIR = ROOT / 'data' / 'translations'
sys.stdout.reconfigure(encoding='utf-8')

data = json.loads((OUT / 'topic_books.json').read_text(encoding='utf-8'))
src = {}
for tag, rows in data['books'].items():
    for r in rows:
        src[r['word']] = tag


def norm(w):
    return ''.join(
        unicodedata.normalize('NFKC', ch) if ('Ａ' <= ch <= 'Ｚ') or ('ａ' <= ch <= 'ｚ') or ('０' <= ch <= '９')
        else ch
        for ch in w)


srcn = {norm(k): v for k, v in src.items()}
bad = []
for p in sorted(TDIR.glob('topic_zh_*.json')):
    for k in json.loads(p.read_text(encoding='utf-8')):
        if norm(k) not in srcn:
            bad.append((p.name, k))
print('mismatched keys:', len(bad))
for name, k in bad:
    print(' ', name, k)
