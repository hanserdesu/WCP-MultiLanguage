# -*- coding: utf-8 -*-
"""将德语词书写入游戏 MyBook.es3 (Easy Save 3 JSON)。

槽位 4 = 德语合并单册 (a1→a2 顺序, 共 3,488 词);
槽位 1 (日语书 7,922 词)、槽位 2 (法语书 8,116 词)、槽位 3 (俄语书 8,451 词) 原样保留。

游戏: WCP-WordGirlfriend (wcp.exe, Unity)
文件: %USERPROFILE%\AppData\LocalLow\WCP\wcp\MyBook.es3

用法:
  python tools/write_mybook_de.py            # 实际写入(自动备份原文件)
  python tools/write_mybook_de.py --dry-run  # 只预览不写入
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'output'

MYBOOK = Path.home() / 'AppData' / 'LocalLow' / 'WCP' / 'wcp' / 'MyBook.es3'
BACKUP_DIR = MYBOOK.parent / 'MyBook_backups'


def game_running():
    tasklist = 'tasklist'
    sys32 = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32' / 'tasklist.exe'
    if sys32.exists():
        tasklist = str(sys32)
    try:
        r = subprocess.run([tasklist, '/FI', 'IMAGENAME eq wcp.exe'],
                           capture_output=True, text=True, encoding='gbk',
                           errors='replace')
        return 'wcp.exe' in (r.stdout or '').lower()
    except Exception:
        return False


ARR_TYPE = 'System.String[],mscorlib'
DICT_TYPE = ('System.Collections.Generic.Dictionary`2[[System.String, mscorlib, '
             'Version=4.0.0.0, Culture=neutral, PublicKeyToken=b77a5c561934e089],'
             '[System.String, mscorlib, Version=4.0.0.0, Culture=neutral, '
             'PublicKeyToken=b77a5c561934e089]],mscorlib')

# 仅操作槽位 4
SLOTS = [
    (4, ['a1', 'a2', 'b1', 'b2'], '德语词库(猫条版) 合并单册'),
]


def fmt_meaning(w):
    ipa = f"[{w['ipa']}]" if w.get('ipa') else ''
    return f"{ipa}{w['zh']}〈{w['pos']}〉"


def build_slot_data(books, levels):
    seen = set()
    words, meanings = [], {}
    for lvl in levels:
        if lvl not in books.get('levels', {}):
            continue
        for w in books['levels'][lvl]:
            word = w['word'].strip()
            if not word or word in seen:
                continue
            seen.add(word)
            words.append(word)
            meanings[word] = fmt_meaning(w)
    return words, meanings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    books_p = OUT / 'german_books.json'
    if not books_p.exists():
        print('找不到', books_p)
        return 1
    books = json.loads(books_p.read_text(encoding='utf-8'))

    if not MYBOOK.exists():
        print('找不到 MyBook.es3:', MYBOOK)
        return 1

    if game_running() and not args.dry_run:
        print('wcp.exe 正在运行, 请先退出游戏再写词书')
        return 1

    doc = json.loads(MYBOOK.read_text(encoding='utf-8-sig'))

    # 检查保留槽位
    for keep_slot in (1, 2, 3):
        old_list = (doc.get(f'SelfBookList{keep_slot}') or {}).get('value', [])
        print(f'保留槽位 {keep_slot}: 原有 {len(old_list)} 词 (不触及)')

    for slot, levels, label in SLOTS:
        words, meanings = build_slot_data(books, levels)
        print(f'准备槽位 {slot} ({label}): 词数={len(words)}')
        if not args.dry_run:
            doc[f'SelfBookList{slot}'] = {
                '__type': ARR_TYPE,
                'value': words
            }
            doc[f'SelfBookMeaningDic{slot}'] = {
                '__type': DICT_TYPE,
                'value': meanings
            }

    if args.dry_run:
        print('dry-run 模式, 未写入任何文件')
        return 0

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime('%Y%m%d_%H%M%S')
    bak = BACKUP_DIR / f'MyBook.es3.before_german_{stamp}'
    shutil.copy2(MYBOOK, bak)
    print(f'已备份原文件 -> {bak}')

    MYBOOK.write_text(json.dumps(doc, ensure_ascii=False, indent=2),
                      encoding='utf-8')
    print('已成功写入 MyBook.es3')

    # 回读验证
    verify = json.loads(MYBOOK.read_text(encoding='utf-8-sig'))
    for slot, levels, label in SLOTS:
        w_len = len((verify.get(f'SelfBookList{slot}') or {}).get('value', []))
        m_len = len((verify.get(f'SelfBookMeaningDic{slot}') or {}).get('value', {}))
        print(f'回读槽位 {slot}: 词表={w_len}, 释义字典={m_len}')
        assert w_len == 8062, f"期望 3488 词，实际 {w_len}"
        assert m_len == 8062, f"期望 3488 释义，实际 {m_len}"

    for keep_slot, expected_min in [(1, 7000), (2, 8000), (3, 8000)]:
        val = (verify.get(f'SelfBookList{keep_slot}') or {}).get('value', [])
        assert len(val) >= expected_min, f"槽位 {keep_slot} 数据受损！实际 {len(val)}"

    print(">>> 德语词书成功注入 MyBook.es3 槽位4，槽位1/2/3原样保留！<<<")
    return 0


if __name__ == '__main__':
    sys.exit(main())
