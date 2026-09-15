# -*- coding: utf-8 -*-
"""生成专业词书的游戏导入文件 (游戏导入契约: 无表头, A列=单词, B列=释义;
C列起游戏忽略, 放读音/英文/例句仅供人工参考):
  - output/import/主题_<名称>.xlsx  (每主题一个, 游戏内 Excel 导入)
  - output/import/wcp_themed.db    (SQLite 外接词库: pron 全量 + 每主题明细表)
表命名: t_it / t_medical / ... + themes(目录表) + pron(去重全量)
"""
import json
import sqlite3
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'output'
IMPORT = OUT / 'import'

# 游戏只读 A/B 列; C/D/E 人工参考
HEADERS = None

FILE_LABEL = {
    'it': '专业_IT·计算机', 'medical': '专业_医学',
    'business': '专业_商务日语', 'law': '专业_法律',
    'idiom': '惯用句·比喻表达', 'onoma': '拟声拟态',
    'yoji': '四字熟语', 'kotowaza': '谚语·格言', 'keigo': '敬语',
    'talk': '日常会话',
}


def main():
    books = json.loads((OUT / 'themed_books.json').read_text(encoding='utf-8'))
    themes = books['themes']
    labels = books['meta'].get('theme_labels', {})
    IMPORT.mkdir(parents=True, exist_ok=True)

    for t, rows in themes.items():
        wb = Workbook()
        ws = wb.active
        ws.title = '词汇表'
        for r in rows:
            ws.append([r['word'], r['meaning'],
                       r['reading'], r['meaning_en'], r['example_ja']])
        for col, w in zip('ABCDE', (22, 46, 16, 40, 44)):
            ws.column_dimensions[col].width = w
        for row in ws.iter_rows():
            for c in row:
                c.alignment = Alignment(vertical='center', wrap_text=True)
        name = FILE_LABEL.get(t, t)
        path = IMPORT / f'{name}.xlsx'
        wb.save(path)
        print(f'{path.name}: {len(rows)} 词 (无表头 A词/B义)')

    # SQLite 外接词库
    db_path = IMPORT / 'wcp_themed.db'
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute('CREATE TABLE pron (word TEXT PRIMARY KEY, meaning TEXT)')
    seen = set()
    for t, rows in themes.items():
        for r in rows:
            if r['word'] in seen or not r['meaning']:
                continue
            seen.add(r['word'])
            cur.execute('INSERT INTO pron VALUES (?, ?)', (r['word'], r['meaning']))
    cur.execute('CREATE TABLE themes (tname TEXT PRIMARY KEY, label TEXT, count INTEGER)')
    for t, rows in themes.items():
        cur.execute('INSERT INTO themes VALUES (?,?,?)',
                    (t, labels.get(t, t), len(rows)))
    for t, rows in themes.items():
        cur.execute(f'''CREATE TABLE t_{t} (
            word TEXT, reading TEXT, meaning TEXT,
            meaning_en TEXT, example_ja TEXT)''')
        for r in rows:
            cur.execute(f'INSERT INTO t_{t} VALUES (?,?,?,?,?)',
                        (r['word'], r['reading'], r['meaning'],
                         r['meaning_en'], r['example_ja']))
    con.commit()
    con.close()
    print(f'{db_path.name}: pron {len(seen)} 词 (去重), '
          f'{len(themes)} 张主题表, themes 目录表')


if __name__ == '__main__':
    main()
