# -*- coding: utf-8 -*-
"""生成 WCP 游戏官方导入通道所需的配套文件:
  - 法语A1A2.xlsx / 法语B1.xlsx / 法语B2.xlsx (游戏内 Excel 导入建书)
  - wcp_french.db (SQLite 外接词库, pron 表: word/meaning + french_all 明细)

游戏内 Excel 导入契约 (逆向自 SaveSourceType, NPOI):
  - 读第一个 sheet, 从第 0 行开始逐行读 A/B 两列
  - A列=单词, B列=释义(游戏内显示文本)  -> 因此【不要加表头行】
  - C列以后被忽略, 可放 IPA/英文/例句等人工参考信息
"""
import json
import sqlite3
import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'output'
IMPORT = OUT / 'import'

SLOT_MAP = {
    '法语A1A2': ['a1', 'a2'],
    '法语B1': ['b1'],
    '法语B2': ['b2'],
}


def fmt_meaning(w):
    ipa = f"[{w['ipa']}] " if w.get('ipa') else ''
    return f"{ipa}{w['zh']}〈{w['pos']}〉"


def save_book(path, rows):
    wb = Workbook()
    ws = wb.active
    ws.title = '词汇表'
    for row in rows:
        ws.append(row)
    for col, width in zip('ABCDEF', (20, 46, 16, 30, 44, 8)):
        ws.column_dimensions[col].width = width
    for row in ws.iter_rows(min_row=1):
        for c in row:
            c.alignment = Alignment(vertical='center', wrap_text=True)
    wb.save(path)


def main():
    data = json.loads((OUT / 'french_books.json').read_text(
        encoding='utf-8'))
    levels = data['levels']
    IMPORT.mkdir(parents=True, exist_ok=True)

    all_rows = []
    for name, lvs in SLOT_MAP.items():
        rows = []
        for lv in lvs:
            for w in levels[lv]:
                meaning = fmt_meaning(w)
                # 游戏: A=单词, B=释义; C/D/E=IPA/释义原文/例句(仅人工参考)
                rows.append([w['word'], meaning, w.get('ipa', ''),
                             w['zh'], w.get('pos', ''), lv])
        all_rows.extend(rows)
        path = IMPORT / f'{name}.xlsx'
        save_book(path, rows)
        print(f'{path.name}: {len(rows)} 词')

    db_path = IMPORT / 'wcp_french.db'
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute('CREATE TABLE pron (word TEXT PRIMARY KEY, meaning TEXT)')
    seen = set()
    for w in all_rows:
        if w[0] in seen:
            continue
        seen.add(w[0])
        cur.execute('INSERT INTO pron VALUES (?, ?)',
                    (w[0], w[1]))
    cur.execute('''CREATE TABLE french_all (
        word TEXT, meaning TEXT, ipa TEXT, zh TEXT, pos TEXT, level TEXT)''')
    for w in all_rows:
        cur.execute('INSERT INTO french_all VALUES (?,?,?,?,?,?)', w)
    con.commit()
    con.close()
    print(f'{db_path.name}: pron {len(seen)} 词 (去重), french_all {len(all_rows)} 行')


if __name__ == '__main__':
    main()
