# -*- coding: utf-8 -*-
"""导出我们插入的例句行 (rowid, word, ja, 当前翻译) 供 LLM 翻译。
只导出 ( ) 内为英文或为空的行; 已是中文的跳过。
输出: logs/sentence_worklist.tsv (idx, rowid, word, ja) + 当前翻译参考
"""
import re
import sqlite3
import sys
from pathlib import Path

import wcp_paths

sys.stdout.reconfigure(encoding='utf-8')
DB = wcp_paths.full_db()
OUT = Path(r'D:\ATooManyLanguage\Japanese\wcp_wordbooks\logs\sentence_worklist.tsv')

CJK_RE = re.compile(r'[\u4e00-\u9fff]')
# 排除: 日文汉字句必然含 CJK; 英文翻译行不含 CJK(假名除外)
KANA_RE = re.compile(r'[\u3040-\u30ff]')

con = sqlite3.connect(str(DB))
cur = con.cursor()
cur.execute("SELECT rowid, word, sentences FROM sentence2 "
            "WHERE sentences LIKE '例句：%'")
rows = cur.fetchall()
con.close()

JP_WORD = re.compile(r'[\u3040-\u30ff\u4e00-\u9fff々〆ヶ]')

out = []
for rowid, word, sent in rows:
    if not JP_WORD.search(word or ''):
        continue  # 原库英文行, 不动
    m = re.match(r'^例句：(.*)（(.*)）\s*$', sent, re.S)
    if not m:
        ja = sent[len('例句：'):]
        tr = ''
    else:
        ja, tr = m.group(1), m.group(2)
    tr = tr.strip()
    ja = ja.strip()
    # 需要翻译: 翻译为空 或 不含中文(英文残留)
    need = (not tr) or (not CJK_RE.search(tr))
    if need:
        out.append((rowid, word, ja.replace('\n', ' '), tr))

with open(OUT, 'w', encoding='utf-8') as f:
    for i, (rowid, word, ja, tr) in enumerate(out):
        f.write(f'{i}\t{rowid}\t{word}\t{ja}\t{tr}\n')
print(f'待翻译例句: {len(out)} / 总例句行 {len(rows)} -> {OUT.name}')
