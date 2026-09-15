# -*- coding: utf-8 -*-
"""Set B-1 主题词书导入文件。

游戏导入契约 (会话B逆向 SaveSourceType):
  - xlsx: 第一个 sheet 从第0行起读, A列=单词, B列=释义; **不能有表头行**
    (C列读音/D列中文原释义仅供人工参考, 游戏忽略)
  - .db: 须放 persistentDataPath, pron(word, meaning) 表

输出:
  - output/import/setb/*.xlsx  (无表头, A词/B义)
  - output/import/setb/wcp_setb.db  (pron 全量表 + setb_all 明细表)
"""
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'output'
IMPORT = OUT / 'import' / 'setb'

NAMES = {
    'idioms': '惯用句谚语',
    'giongo': '拟声拟态',
    'yoji': '四字熟语',
    'advanced': '高级词汇',
    'business': '商务敬语',
}


def main():
    from openpyxl import Workbook
    from openpyxl.styles import Alignment

    data = json.loads((OUT / 'setb_books.json').read_text(encoding='utf-8'))
    IMPORT.mkdir(parents=True, exist_ok=True)

    all_rows = []
    for key, rows in data['levels'].items():
        wb = Workbook()
        ws = wb.active
        ws.title = '词汇表'
        for r in rows:
            # A=单词, B=游戏内显示释义; C-F 人工参考(游戏忽略)
            row = [r['word'], r['meaning'], r['reading'], r['meaning_zh'],
                   r.get('example_ja', ''), r.get('example_zh', '')]
            ws.append(row)
            all_rows.append(row)
        for col, w in zip('ABCDEF', (22, 46, 14, 40, 46, 40)):
            ws.column_dimensions[col].width = w
        for row in ws.iter_rows(min_row=1):
            for c in row:
                c.alignment = Alignment(vertical='center', wrap_text=True)
        path = IMPORT / f'{NAMES[key]}.xlsx'
        wb.save(path)
        print(f'{path.name}: {len(rows)} 词 (无表头)')

    db = IMPORT / 'wcp_setb.db'
    if db.exists():
        db.unlink()
    con = sqlite3.connect(db)
    cur = con.cursor()
    cur.execute('CREATE TABLE pron (word TEXT PRIMARY KEY, meaning TEXT)')
    seen = set()
    for word, meaning, *_ in all_rows:
        if word in seen or not meaning:
            continue
        seen.add(word)
        cur.execute('INSERT INTO pron VALUES (?,?)', (word, meaning))
    cur.execute('''CREATE TABLE setb_all (
        word TEXT, meaning TEXT, reading TEXT, meaning_zh TEXT,
        topic TEXT)''')
    for key, rows in data['levels'].items():
        for r in rows:
            cur.execute('INSERT INTO setb_all VALUES (?,?,?,?,?)',
                        (r['word'], r['meaning'], r['reading'],
                         r['meaning_zh'], NAMES[key]))
    con.commit()
    con.close()
    print(f'{db.name}: pron {len(seen)} 词 (去重), setb_all {len(all_rows)} 行')


if __name__ == '__main__':
    main()
