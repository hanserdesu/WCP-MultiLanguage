#!/bin/bash
# 一体化工作流: 校验 -> 孤儿键审计 -> 合并 -> 导出下一批
cd /d/Japanese/wcp_wordbooks
py tools/validate_themed.py 2>&1 | tail -3
py - <<'PYEOF'
import json
from pathlib import Path
books = json.loads(Path(r'D:\ATooManyLanguage\Japanese\wcp_wordbooks\output\themed_books.json').read_text(encoding='utf-8'))
all_words = set()
for t, rows in books['themes'].items():
    for r in rows:
        all_words.add(r['word'])
for p in Path(r'D:\ATooManyLanguage\Japanese\wcp_wordbooks\data\themed').glob('extra_*.json'):
    for e in json.loads(p.read_text(encoding='utf-8'))['entries']:
        all_words.add(e['word'])
bad = []
for p in sorted(Path(r'D:\ATooManyLanguage\Japanese\wcp_wordbooks\data\translations').glob('zh_llm_themed_*.json')):
    for k in json.loads(p.read_text(encoding='utf-8')):
        if k not in all_words:
            bad.append((p.name, k))
print('孤儿键:', bad if bad else '无')
PYEOF
py tools/merge_themed.py > logs/merge_latest.log 2>&1
tail -10 logs/merge_latest.log
