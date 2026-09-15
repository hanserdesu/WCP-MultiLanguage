# -*- coding: utf-8 -*-
"""导出全部可疑释义供 LLM 复核: 产出 logs/review_suspicious.txt 与
data/translations/review_suspicious.json (含 word/zh/en 上下文)"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'output'

data = json.loads((OUT / 'jlpt_books.json').read_text(encoding='utf-8'))
seen, items = set(), []
for lv in ['n5', 'n4', 'n3', 'n2', 'n1']:
    for r in data['levels'][lv]:
        w = r['word']
        if w in seen:
            continue
        seen.add(w)
        items.append(r)


def cats(r):
    zh, en = r.get('meaning_zh') or '', r.get('meaning_en') or ''
    out = []
    if not zh:
        out.append('missing')
    if re.search(r'[A-Za-z]{3,}', zh) and 'pH' not in zh:
        out.append('latin')
    if zh.strip().lower() == en.strip().lower():
        out.append('same')
    # 假名: 排除括号内引用 (……) 与全角括号内容
    zh_outside = re.sub(r'（[^）]*）|\([^)]*\)', '', zh)
    if re.search(r'[\u3040-\u30ff]', zh_outside):
        out.append('kana')
    return out


rows = []
for r in items:
    c = cats(r)
    if c:
        rows.append({'word': r['word'], 'reading': r.get('reading', ''),
                     'zh': r.get('meaning_zh', ''), 'en': r.get('meaning_en', ''),
                     'flags': c})

by_cat = {}
for r in rows:
    for f in r['flags']:
        by_cat.setdefault(f, []).append(r['word'])
print('category counts:', {k: len(v) for k, v in by_cat.items()})

txt_lines = []
for r in rows:
    txt_lines.append(f"{r['word']}({r['reading']})\t[{','.join(r['flags'])}]\t{r['zh']}\t<<EN>> {r['en']}")
(ROOT / 'logs' / 'review_suspicious.txt').write_text('\n'.join(txt_lines), encoding='utf-8')
(ROOT / 'data' / 'translations' / 'review_suspicious.json').write_text(
    json.dumps(rows, ensure_ascii=False, indent=1), encoding='utf-8')
print(f'total {len(rows)} -> logs/review_suspicious.txt')
