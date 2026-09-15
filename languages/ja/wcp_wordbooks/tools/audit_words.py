# -*- coding: utf-8 -*-
"""审计词表字段质量: 脏词字段统计 + elzup词表与现有词书的差集(扩充候选)。"""
import csv, json, re
from pathlib import Path

ROOT = Path(r'D:/ATooManyLanguage/Japanese/wcp_wordbooks')
data = json.loads((ROOT/'output/jlpt_books.json').read_text(encoding='utf-8'))

all_words = {}
for lv, rows in data['levels'].items():
    for r in rows:
        all_words.setdefault(r['word'], lv)

# 1) 脏词字段模式
junk = []
for w in all_words:
    if re.search(r'[（(]', w) or '/' in w or '～' in w or '~' in w or '？' in w or '！' in w:
        junk.append(w)
print(f'含括号/斜杠/波浪线等符号的词: {len(junk)}')
for w in sorted(junk)[:40]:
    print('  ', w, '|', all_words[w])

# 2) elzup 差集
elz = {}
for n in [5,4,3,2,1]:
    with open(f'D:/ATooManyLanguage/Japanese/data/jlpt_n{n}.csv', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            e = row['expression'].strip()
            if e and e not in elz:
                elz[e] = {'lv': f'n{n}', 'r': row['reading'].strip(), 'en': row['meaning']}
new_words = {w: v for w, v in elz.items() if w not in all_words}
print(f'\nelzup 总词数 {len(elz)}, 现有词书 {len(all_words)}, 差集(新候选) {len(new_words)}')
from collections import Counter
cnt = Counter(v['lv'] for v in new_words.values())
print('按级别:', dict(cnt))
# 也查反向: 现有词书里有但 elzup 没有的(即 OpenJLPT 独有)
only_ours = [w for w in all_words if w not in elz]
print('现有词书独有(OpenJLPT独有):', len(only_ours))
# 保存差集候选
out = ROOT/'data'/'expansion_elzup_candidates.json'
out.write_text(json.dumps(new_words, ensure_ascii=False, indent=1), encoding='utf-8')
print('saved:', out)
