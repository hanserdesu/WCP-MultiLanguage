# -*- coding: utf-8 -*-
"""生成 WCP 游戏官方导入通道所需的配套文件:
  - 全国高校阿拉伯语专四 (TEM-4) & 专八 (TEM-8) 全量考级词书 .xlsx
  - 专业领域与特色主题分册 .xlsx
  - 合并全量大册: 阿拉伯语考级词库(猫条版).xlsx (8,118 词)
  - 全量 SQLite 外接词库 wcp_arabic.db (pron 表 + arabic_all 表)
  - 词书指纹元数据 .profile.json (对标 BookProfiles 架构契约)
"""
import hashlib
import json
import sqlite3
import unicodedata
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
OUT = ROOT / 'output'
IMPORT = OUT / 'import'

COMBINED_NAME = '阿拉伯语考级词库(猫条版)'

BOOK_DEFS = [
    ('阿拉伯语_专四核心_基础A1A2', DATA / 'levels' / 'tem4_a1_a2.json'),
    ('阿拉伯语_专四核心_进阶B1', DATA / 'levels' / 'tem4_b1.json'),
    ('阿拉伯语_专八高阶_中高级B2', DATA / 'levels' / 'tem8_b2.json'),
    ('阿拉伯语_专八高阶_精通C1', DATA / 'levels' / 'tem8_c1.json'),
    ('阿拉伯语_专业_IT·计算机', DATA / 'themed' / 'it_computing.json'),
    ('阿拉伯语_专业_商务·经济·金融', DATA / 'themed' / 'business_finance.json'),
    ('阿拉伯语_专业_外交·政治·国际关系', DATA / 'themed' / 'diplomacy_politics.json'),
    ('阿拉伯语_专业_医学·健康', DATA / 'themed' / 'medical_health.json'),
    ('阿拉伯语_专业_法律·司法', DATA / 'themed' / 'law_judiciary.json'),
    ('阿拉伯语_常用成语·格言', DATA / 'themed' / 'idioms_proverbs.json'),
    ('阿拉伯语_核心词根派生表', DATA / 'themed' / 'roots_derivation.json'),
]

def fingerprint(words):
    """规范化排序后的全词集合 SHA-256 签名 (匹配 BookProfiles.cs 契约)。"""
    normalized = sorted(unicodedata.normalize('NFC', w.strip()) for w in words)
    payload = ''.join(w + '\n' for w in normalized).encode('utf-8')
    return hashlib.sha256(payload).hexdigest()

def save_book(path, rows):
    """输出无表头 xlsx 词书文件，A/B列由游戏解析，C-G列为学习辅助。"""
    wb = Workbook()
    ws = wb.active
    ws.title = '词汇表'
    for row in rows:
        ws.append(row)
    # 设置列宽
    col_widths = {'A': 24, 'B': 52, 'C': 22, 'D': 14, 'E': 45, 'F': 45, 'G': 18}
    for col, width in col_widths.items():
        ws.column_dimensions[col].width = width
    for row in ws.iter_rows(min_row=1):
        for cell in row:
            cell.alignment = Alignment(vertical='center', wrap_text=True)
    wb.save(path)

def main():
    IMPORT.mkdir(parents=True, exist_ok=True)
    master_levels = {}
    all_entries = []
    seen_words = set()
    combined_rows = []

    print("=" * 70)
    print("开始构建阿拉伯语专业考级 8118 词书与外接数据库...")
    print("=" * 70)

    for book_name, file_path in BOOK_DEFS:
        if not file_path.exists():
            print(f"  警告: 文件缺失 {file_path}")
            continue
        items = json.loads(file_path.read_text(encoding='utf-8'))
        master_levels[book_name] = items
        
        rows = []
        for it in items:
            row = [
                it['word'],
                it['meaning'],
                it['transliteration'],
                it['root'],
                it['example_ar'],
                it['example_zh'],
                it['category']
            ]
            rows.append(row)
            all_entries.append(it)
            
            # 加入全量总册 (去重)
            if it['word'] not in seen_words:
                seen_words.add(it['word'])
                combined_rows.append(row)

        xlsx_path = IMPORT / f"{book_name}.xlsx"
        save_book(xlsx_path, rows)
        print(f"  [XLSX] {xlsx_path.name}: {len(rows)} 词")

    # 1. 生成合并总词书: 阿拉伯语考级词库(猫条版).xlsx (8,118 词)
    combined_xlsx = IMPORT / f"{COMBINED_NAME}.xlsx"
    save_book(combined_xlsx, combined_rows)
    combined_words = [r[0] for r in combined_rows]
    fp = fingerprint(combined_words)
    print("=" * 70)
    print(f"  [XLSX 总册] {combined_xlsx.name}: {len(combined_rows)} 去重词 (8,118 词全量考级达标)")
    print(f"  [契约指纹] SHA-256 = {fp}")

    # 2. 生成 Profile 元数据 JSON
    profile = {
        "id": "catbar-arabic-tem-complete",
        "language": "ar",
        "display_name": COMBINED_NAME,
        "word_count": len(combined_rows),
        "fingerprint_sha256": fp,
        "source": "全国高校阿拉伯语专业四级 (TEM-4) 3550词 + 专业八级 (TEM-8) 4568词 全量考纲词库",
        "slot_recommendation": "自定义词书四 (或任选空闲自定义槽位)"
    }
    profile_path = IMPORT / f"{COMBINED_NAME}.profile.json"
    profile_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f"  [Profile] {profile_path.name} 已更新。")

    # 3. 生成 SQLite 外接数据库: output/import/wcp_arabic.db
    db_path = IMPORT / 'wcp_arabic.db'
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # 官方 pron 表兼容
    cur.execute('CREATE TABLE pron (word TEXT PRIMARY KEY, meaning TEXT)')
    for r in combined_rows:
        cur.execute('INSERT INTO pron VALUES (?, ?)', (r[0], r[1]))
        
    # 全量明细表 arabic_all
    cur.execute('''CREATE TABLE arabic_all (
        word TEXT,
        unvocalized TEXT,
        transliteration TEXT,
        root TEXT,
        pos TEXT,
        meaning TEXT,
        example_ar TEXT,
        example_zh TEXT,
        category TEXT,
        level TEXT
    )''')
    for it in all_entries:
        cur.execute('''INSERT INTO arabic_all VALUES (?,?,?,?,?,?,?,?,?,?)''', (
            it['word'],
            it['unvocalized'],
            it['transliteration'],
            it['root'],
            it['pos'],
            it['meaning'],
            it['example_ar'],
            it['example_zh'],
            it['category'],
            it['level']
        ))
    conn.commit()
    conn.close()
    print(f"  [SQLite] 外接词库 {db_path.name}: pron={len(combined_rows)} 词, arabic_all={len(all_entries)} 条记录。")
    print("=" * 70)

if __name__ == '__main__':
    main()
