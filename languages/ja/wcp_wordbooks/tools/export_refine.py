# -*- coding: utf-8 -*-
"""导出 LLM 精翻工作清单: 全部唯一词条 (词/读音/英文/现中文/级别/来源), 按级别+词排序。
输出 refwork/all_words.json + 分块 refwork/chunk_NN.json (每块300) 供 agent 顺序精翻。
"""
import json
from pathlib import Path

ROOT = Path(r'D:/ATooManyLanguage/Japanese/wcp_wordbooks')
data = json.loads((ROOT / 'output/jlpt_books.json').read_text(encoding='utf-8'))

items = []
seen = set()
for lv in ['n5', 'n4', 'n3', 'n2', 'n1']:
    rows = sorted(data['levels'][lv], key=lambda r: r['word'])
    for r in rows:
        w = r['word']
        if w in seen:
            continue
        seen.add(w)
        items.append({
            'w': w, 'r': r['reading'], 'en': r['meaning_en'][:120],
            'zh': r.get('meaning_zh', ''), 'src': r.get('zh_source', ''),
            'pos': r.get('pos_zh', ''), 'lv': lv,
        })

ref = ROOT / 'refwork'
ref.mkdir(exist_ok=True)
(ref / 'all_words.json').write_text(
    json.dumps(items, ensure_ascii=False, indent=1), encoding='utf-8')

CHUNK = 300
n_chunks = 0
for i in range(0, len(items), CHUNK):
    part = items[i:i + CHUNK]
    (ref / f'chunk_{n_chunks:02d}.json').write_text(
        json.dumps(part, ensure_ascii=False, indent=1), encoding='utf-8')
    n_chunks += 1
print(f'共 {len(items)} 词, {n_chunks} 个工作块 -> {ref}')
