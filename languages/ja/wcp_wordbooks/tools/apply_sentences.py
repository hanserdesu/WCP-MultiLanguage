# -*- coding: utf-8 -*-
"""把翻译+新生成例句回写游戏本地词库 sentence2, 生成 sentences_master.json。

输入:
  logs/sentence_worklist.tsv   (idx, rowid, word, ja, 旧翻译)
  data/translations/sent_zh_*.json + work/tr_out_*.json  (idx -> 中文)
  work/gen_out_*_*.json        (word -> [{ja,zh},...])
输出:
  UPDATE sentence2 (按 rowid): 例句：ja（中文）
  INSERT 新例句 (每词补到 >=3 条)
  data/translations/sentences_master.json {word: [[ja,zh],...]}  (patch_local_db 用)
"""
import json
import re
import sqlite3
import sys
from pathlib import Path

import wcp_paths

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'output'
WORK = ROOT / 'work'
TDIR = ROOT / 'data' / 'translations'
DB = wcp_paths.full_db()

# ---- 收集翻译 ----
zh_map = {}
for p in sorted(TDIR.glob('sent_zh_*.json')):
    zh_map.update(json.loads(p.read_text(encoding='utf-8')))
for p in sorted(WORK.glob('tr_out_*.json')):
    zh_map.update({str(k): v for k, v in
                   json.loads(p.read_text(encoding='utf-8')).items()})
print('已收翻译:', len(zh_map))

# ---- 收集生成例句 ----
gen = {}
for p in sorted(WORK.glob('gen_out_*.json')):
    try:
        gen.update(json.loads(p.read_text(encoding='utf-8')))
    except Exception as e:
        print('!! 解析失败(跳过):', p.name, e)
print('生成例句覆盖词数:', len(gen))

# ---- 读工作清单 ----
wl = []  # (idx, rowid, word, ja, old_tr)
for line in (ROOT / 'logs' / 'sentence_worklist.tsv').read_text(
        encoding='utf-8').splitlines():
    parts = line.split('\t')
    if len(parts) >= 5:
        wl.append((parts[0], int(parts[1]), parts[2], parts[3], parts[4]))

# ---- 组装 master ----
master = {}   # word -> [[ja, zh], ...]
missing_zh = []
for idx, rowid, word, ja, old_tr in wl:
    zh = zh_map.get(idx, '')
    if not zh or not re.search(r'[\u4e00-\u9fff]', zh):
        missing_zh.append(idx)
        zh = ''
    master.setdefault(word, []).append([ja, zh])
for word, items in gen.items():
    lst = master.setdefault(word, [])
    for it in items:
        if isinstance(it, dict) and it.get('ja') and it.get('zh'):
            lst.append([it['ja'], it['zh']])
short = {w: len(v) for w, v in master.items() if len(v) < 3}
print(f'master 词数 {len(master)}, 缺翻译 {len(missing_zh)}, <3条 {len(short)}')

# ---- 回写 DB ----
con = sqlite3.connect(str(DB), timeout=30)
con.execute('PRAGMA busy_timeout=30000')
cur = con.cursor()
cur.execute('BEGIN')
n_upd = n_ins = 0
for idx, _rowid, word, ja, old_tr in wl:
    items = master.get(word) or []
    zh = items[0][1] if items and items[0][0] == ja else zh_map.get(idx, '')
    if zh:
        # 不能用 worklist 里的 rowid: 那份清单是 patch_local_db 重建 sentence2
        # 之前抓的, 行号早已指向别的词 —— 曾因此把 10251 条例句写串行。
        # 改成「按词 + 原句」定位, 幂等且不会跨词覆盖。
        cur.execute("UPDATE sentence2 SET sentences=? "
                    "WHERE word=? AND sentences LIKE ?",
                    (f'例句：{ja}（{zh}）', word, f'例句：{ja}%'))
        n_upd += 1
for word, items in master.items():
    have = cur.execute('SELECT COUNT(*) FROM sentence2 WHERE word=?',
                       (word,)).fetchone()[0]
    for ja, zh in items[have:] if have else items:
        if have >= 3:
            break
        s = f'例句：{ja}（{zh}）' if zh else f'例句：{ja}'
        cur.execute('INSERT INTO sentence2 (word, sentences) VALUES (?,?)',
                    (word, s))
        have += 1
        n_ins += 1
con.commit()
# 校验
bad = 0
for word in list(master)[:500]:
    c = cur.execute('SELECT COUNT(*) FROM sentence2 WHERE word=?',
                    (word,)).fetchone()[0]
    if c < 3:
        bad += 1
probe = cur.execute('SELECT sentences FROM sentence2 WHERE word=?',
                    ('お産',)).fetchall()
con.close()
print(f'UPDATE {n_upd}, INSERT {n_ins}, 抽样500词中<3条 {bad}')
print('お産 例句:', probe)

master_out = TDIR / 'sentences_master.json'
master_out.write_text(json.dumps(master, ensure_ascii=False, indent=1),
                      encoding='utf-8')
print('master ->', master_out.name, len(master), '词')
if missing_zh:
    (ROOT / 'logs' / 'sentence_missing_zh.txt').write_text(
        '\n'.join(missing_zh), encoding='utf-8')
    print('缺翻译清单 -> logs/sentence_missing_zh.txt')
