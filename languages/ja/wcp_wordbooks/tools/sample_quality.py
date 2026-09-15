# -*- coding: utf-8 -*-
import json, random, sys
from pathlib import Path
ROOT = Path(r'D:/ATooManyLanguage/Japanese/wcp_wordbooks')
data = json.loads((ROOT/'output/jlpt_books.json').read_text(encoding='utf-8'))
random.seed(42)
n = int(sys.argv[1]) if len(sys.argv) > 1 else 30
lv = sys.argv[2] if len(sys.argv) > 2 else None
levels = [lv] if lv else ['n5','n4','n3','n2','n1']
items = []
for l in levels:
    for r in data['levels'][l]:
        items.append((l, r))
random.shuffle(items)
src_count = {}
for l, r in items:
    src = r.get('zh_source', 'kaishi' if r.get('meaning_zh') else 'en')
    src_count[src] = src_count.get(src, 0) + 1
print('zh_source distribution:', json.dumps(src_count, ensure_ascii=False))
for l, r in items[:n]:
    print(f"[{l}] {r['word']} ({r['reading']}) => {r['meaning'][:60]}  | en: {r['meaning_en'][:40]}")
