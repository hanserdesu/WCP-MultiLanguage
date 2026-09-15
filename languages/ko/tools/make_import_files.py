# -*- coding: utf-8 -*-
"""生成 WCP 游戏官方导入通道所需的配套文件:
  - 韩语TOPIK1.xlsx / 韩语TOPIK2.xlsx / 韩语TOPIK3.xlsx / 韩语全量.xlsx (游戏内 Excel 导入建书)
  - wcp_korean.db (SQLite 外接词库, pron 表: word/meaning + korean_all 明细)

游戏内 Excel 导入契约:
  - 读第一个 sheet, 从第 0 行开始逐行读 A/B 两列
  - A列=单词, B列=释义(游戏内显示文本) -> 【不要加表头行】
  - C列以后被忽略, 可放 IPA/中文/词性/级别供参考
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
    '韩语TOPIK1': ['topik1'],
    '韩语TOPIK2': ['topik2'],
    '韩语TOPIK3': ['topik3'],
    '韩语全量': ['topik1', 'topik2', 'topik3'],
}


def fmt_meaning(w):
    ipa = f"[{w['ipa']}] " if w.get('ipa') else ''
    meaning = w.get('meaning', '')
    if ']' in meaning:
        meaning = meaning.split(']')[-1].strip()
    return f"{ipa}{meaning}"


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
    data = json.loads((OUT / 'korean_books.json').read_text(encoding='utf-8'))
    levels = data['levels']
    IMPORT.mkdir(parents=True, exist_ok=True)

    all_rows = []
    for name, lvs in SLOT_MAP.items():
        rows = []
        for lv in lvs:
            for w in levels.get(lv, []):
                meaning = fmt_meaning(w)
                rows.append([w['word'], meaning, w.get('ipa', ''),
                             w.get('meaning', ''), w.get('category', ''), lv])
        if name == '韩语全量':
            all_rows = rows
        path = IMPORT / f'{name}.xlsx'
        save_book(path, rows)
        print(f'{path.name}: {len(rows)} 词')

    db_path = IMPORT / 'wcp_korean.db'
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS pron (
        word TEXT PRIMARY KEY,
        ukPhonic TEXT,
        usPhonic TEXT,
        meaning TEXT
    )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS korean_all (
        word TEXT PRIMARY KEY,
        ipa TEXT,
        meaning TEXT,
        level TEXT,
        category TEXT
    )''')

    for r in all_rows:
        w, meaning, ipa, raw_m, cat, lv = r
        cur.execute('INSERT OR REPLACE INTO pron VALUES (?, ?, ?, ?)',
                    (w, ipa, ipa, meaning))
        cur.execute('INSERT OR REPLACE INTO korean_all VALUES (?, ?, ?, ?, ?)',
                    (w, ipa, meaning, lv, cat))

    conn.commit()
    conn.close()
    print(f'{db_path.name}: 写入 {len(all_rows)} 词条')


if __name__ == '__main__':
    main()
