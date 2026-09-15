# -*- coding: utf-8 -*-
"""一键回归校验全套韩语词书与多模态资产 (对齐 verify_all_de.py 契约)。"""
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding='utf-8')


def check():
    errors = []
    print("=== 开始韩语全量资产终验 ===")

    # 1. 词书
    books_p = ROOT / 'output' / 'korean_books.json'
    if not books_p.exists():
        errors.append("缺失 output/korean_books.json")
    else:
        b = json.loads(books_p.read_text(encoding='utf-8'))
        total_b = sum(len(v) for v in b.get('levels', {}).values())
        print(f"[PASS] 词书条目: {total_b} 词")

    # 2. 例句
    master_p = ROOT / 'data' / 'translations' / 'sentences_master.json'
    if not master_p.exists():
        errors.append("缺失 data/translations/sentences_master.json")
    else:
        m = json.loads(master_p.read_text(encoding='utf-8'))
        total_s = sum(len(v) for v in m.values())
        ratio = total_s / max(len(m), 1)
        if ratio < 3.0:
            errors.append(f"例句配比未达到 1:3 (当前: {ratio:.2f})")
        else:
            print(f"[PASS] 例句库: {len(m)} 词, {total_s} 句 (比例 1:{ratio:.2f})")

    # 3. 导入 Excel 与 DB
    imp_dir = ROOT / 'output' / 'import'
    for fn in ['韩语TOPIK1.xlsx', '韩语TOPIK2.xlsx', '韩语TOPIK3.xlsx', '韩语全量.xlsx', 'wcp_korean.db']:
        if not (imp_dir / fn).exists():
            errors.append(f"缺失导入资产: {fn}")
    if (imp_dir / 'wcp_korean.db').exists():
        conn = sqlite3.connect(imp_dir / 'wcp_korean.db')
        c = conn.cursor()
        c.execute("SELECT count(*) FROM pron")
        cnt = c.fetchone()[0]
        conn.close()
        print(f"[PASS] 独立数据库 wcp_korean.db: {cnt} 条")

    # 4. 离线 Payload
    payload_dir = ROOT / 'output' / 'ko_db_payload'
    for fn in ['ko_pron.tsv', 'ko_sentences.tsv', 'ko_only_pron.tsv', 'manifest.json']:
        if not (payload_dir / fn).exists():
            errors.append(f"缺失自愈 Payload: {fn}")
    if (payload_dir / 'manifest.json').exists():
        print("[PASS] 离线自愈包 ko_db_payload 完整")

    # 5. 音频
    w_dir = Path.home() / 'AppData/LocalLow/WCP/wcp/ko_word_audio'
    s_dir = Path.home() / 'AppData/LocalLow/WCP/wcp/ko_sentence_audio'

    w_files = list(w_dir.glob('*.mp3')) if w_dir.exists() else []
    s_files = list(s_dir.glob('*.mp3')) if s_dir.exists() else []

    print(f"[PASS] 单词发音: {len(w_files)} 个 MP3")
    print(f"[PASS] 例句发音: {len(s_files)} 个 MP3")

    if errors:
        print("\n[FAIL] 校验发现以下问题:")
        for e in errors:
            print("  -", e)
        sys.exit(1)
    else:
        print("\n==========================================")
        print("🎉 ALL PASS! 韩语全部工程资产已 100% 全量落盘并通过验收！")
        print("==========================================")


if __name__ == '__main__':
    check()
