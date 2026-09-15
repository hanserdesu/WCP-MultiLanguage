# -*- coding: utf-8 -*-
"""导出下一个 LLM 精翻待办批次 -> data/translations/themed_batch_pending.json
待办 = 主题词书中 zh_source 不是 llm/extra 的词, 按 (主题, common, 词长) 排序。
用法: py make_themed_batch.py [--theme yoji] [--size 150]
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'output'
PEND = ROOT / 'data' / 'translations' / 'themed_batch_pending.json'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--theme', default=None)
    ap.add_argument('--size', type=int, default=150)
    args = ap.parse_args()

    books = json.loads((OUT / 'themed_books.json').read_text(encoding='utf-8'))
    todo = []
    for t, rows in books['themes'].items():
        if args.theme and t != args.theme:
            continue
        for r in rows:
            if r.get('zh_source') == 'llm':
                continue
            todo.append({
                'theme': t, 'word': r['word'], 'reading': r['reading'],
                'meaning_en': r['meaning_en'], 'pos_en': r.get('pos_en', ''),
                'meaning_zh_now': r.get('meaning_zh', ''),
            })
    todo.sort(key=lambda x: (x['theme'], not (x['reading'] and True),
                             len(x['word'])))
    batch = todo[:args.size]
    PEND.parent.mkdir(parents=True, exist_ok=True)
    PEND.write_text(json.dumps(batch, ensure_ascii=False, indent=1),
                    encoding='utf-8')
    remain = {}
    for x in todo:
        remain[x['theme']] = remain.get(x['theme'], 0) + 1
    print(f'本批 {len(batch)} 词 -> {PEND.name}')
    print('剩余(按主题):', json.dumps(remain, ensure_ascii=False))
    if batch:
        print('首批词例:', ' '.join(x['word'] for x in batch[:12]))


if __name__ == '__main__':
    main()
