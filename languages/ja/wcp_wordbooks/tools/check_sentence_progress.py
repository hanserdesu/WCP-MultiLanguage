# -*- coding: utf-8 -*-
"""校验例句翻译进度: 找出 worklist 中尚未有中文翻译的 idx 及其块号。"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent

zh = {}
for p in sorted((ROOT / 'data' / 'translations').glob('sent_zh_*.json')):
    zh.update(json.loads(p.read_text(encoding='utf-8')))
for p in sorted((ROOT / 'work').glob('tr_out_*.json')):
    zh.update({str(k): v for k, v in
               json.loads(p.read_text(encoding='utf-8')).items()})

missing = []
total = 0
for line in (ROOT / 'logs' / 'sentence_worklist.tsv').read_text(
        encoding='utf-8').splitlines():
    parts = line.split('\t')
    if len(parts) < 5:
        continue
    total += 1
    idx = parts[0]
    v = zh.get(idx, '')
    if not v:
        missing.append(idx)

print(f'工作清单 {total} 句, 已有翻译 {total - len(missing)}, 缺 {len(missing)}')
if missing:
    idxs = [int(m) for m in missing]
    # 按块号归类 (块N = idx 1180+550N .. +549)
    from collections import Counter
    cnt = Counter((i - 1180) // 550 for i in idxs)
    print('缺口感:', dict(sorted(cnt.items())))
    print('缺失 idx 范围:', idxs[0], '-', idxs[-1])
    (ROOT / 'logs' / 'sentence_missing_idx.txt').write_text(
        '\n'.join(missing), encoding='utf-8')
