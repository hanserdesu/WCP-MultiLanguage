# -*- coding: utf-8 -*-
"""Generate WCP Excel import files + SQLite for Spanish.
Excel: no header, A=word, B=meaning (game contract).
DB: pron + spanish_all tables.
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
    '西班牙语专四基础': ['tem4_a1a2'],
    '西班牙语专四进阶': ['tem4_b1'],
    '西班牙语专八高阶': ['tem8_b2'],
    '西班牙语专八精通': ['tem8_c1'],
    '西班牙语考级词库(猫条版)': ['tem4_a1a2', 'tem4_b1', 'tem8_b2', 'tem8_c1'],
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
    data = json.loads((OUT / 'spanish_books.json').read_text(encoding='utf-8'))
    levels = data['levels']
    all_rows = []
    for name, lvs in SLOT_MAP.items():
        rows = []
        for lv in lvs:
            for w in levels.get(lv, []):
                rows.append([w['word'], w.get('meaning', ''), w.get('ipa', ''), w.get('zh', ''), w.get('pos', ''), lv])
        if name == '西班牙语考级词库(猫条版)': all_rows = rows
        path = IMPORT / f'{name}.xlsx'
        save_book(path, rows)
        print(f'{path.name}: {len(rows)}')
    db = IMPORT / 'wcp_spanish.db'
    if db.exists(): db.unlink()
    conn = sqlite3.connect(db); cur = conn.cursor()
    cur.execute('CREATE TABLE IF NOT EXISTS pron (word TEXT PRIMARY KEY, ukPhonic TEXT, usPhonic TEXT, meaning TEXT)')
    cur.execute('CREATE TABLE IF NOT EXISTS spanish_all (word TEXT PRIMARY KEY, ipa TEXT, meaning TEXT, level TEXT, category TEXT, pos TEXT)')
    for r in all_rows:
        w, meaning, ipa, zh, pos, lv = r
        cur.execute('INSERT OR REPLACE INTO pron VALUES (?, ?, ?, ?)', (w, ipa, ipa, meaning))
        cur.execute('INSERT OR REPLACE INTO spanish_all VALUES (?, ?, ?, ?, ?, ?)', (w, ipa, meaning, lv, '', pos))
    conn.commit(); conn.close()
    print(f'{db.name}: {len(all_rows)} words')

if __name__ == '__main__':
    main()
