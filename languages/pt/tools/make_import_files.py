# -*- coding: utf-8 -*-
"""Generate WCP Excel import files + SQLite for Portuguese.
Excel: no header, A=word, B=meaning (game contract).
DB: pron + portuguese_all tables.
"""
import json, sqlite3, sys
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Alignment

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'output'
IMPORT = OUT / 'import'
IMPORT.mkdir(parents=True, exist_ok=True)

SLOT_MAP = {
    '葡萄牙语专四基础': ['pt_a1a2'],
    '葡萄牙语专四进阶': ['pt_b1'],
    '葡萄牙语专八高阶': ['pt_b2'],
    '葡萄牙语专八精通': ['pt_c1'],
    '葡萄牙语考级词库(猫条版)': ['pt_a1a2', 'pt_b1', 'pt_b2', 'pt_c1'],
}

def save_book(path, rows):
    wb = Workbook(); ws = wb.active; ws.title = '词汇表'
    for row in rows: ws.append(row)
    for col, width in zip('ABCDEF', (20, 46, 16, 30, 44, 8)):
        ws.column_dimensions[col].width = width
    for row in ws.iter_rows(min_row=1):
        for c in row: c.alignment = Alignment(vertical='center', wrap_text=True)
    wb.save(path)

def main():
    data = json.loads((OUT / 'portuguese_books.json').read_text(encoding='utf-8'))
    levels = data['levels']
    all_rows = []
    for name, lvs in SLOT_MAP.items():
        rows = []
        for lv in lvs:
            for w in levels.get(lv, []):
                rows.append([w['word'], w.get('meaning', ''), w.get('ipa', ''), w.get('zh', ''), w.get('pos', ''), lv])
        if name == '葡萄牙语考级词库(猫条版)': all_rows = rows
        path = IMPORT / f'{name}.xlsx'
        save_book(path, rows)
        print(f'{path.name}: {len(rows)}')
    db = IMPORT / 'wcp_portuguese.db'
    if db.exists(): db.unlink()
    conn = sqlite3.connect(db); cur = conn.cursor()
    cur.execute('CREATE TABLE IF NOT EXISTS pron (word TEXT PRIMARY KEY, ukPhonic TEXT, usPhonic TEXT, meaning TEXT)')
    cur.execute('CREATE TABLE IF NOT EXISTS portuguese_all (word TEXT PRIMARY KEY, ipa TEXT, meaning TEXT, level TEXT, category TEXT, pos TEXT)')
    for r in all_rows:
        w, meaning, ipa, zh, pos, lv = r
        cur.execute('INSERT OR REPLACE INTO pron VALUES (?, ?, ?, ?)', (w, ipa, ipa, meaning))
        cur.execute('INSERT OR REPLACE INTO portuguese_all VALUES (?, ?, ?, ?, ?, ?)', (w, ipa, meaning, lv, '', pos))
    conn.commit(); conn.close()
    print(f'{db.name}: {len(all_rows)} words')

if __name__ == '__main__':
    main()
