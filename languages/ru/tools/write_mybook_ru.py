# -*- coding: utf-8 -*-
"""将俄语词书写入游戏 MyBook.es3 (Easy Save 3 JSON)。

槽位 3 = 俄语合并单册 (a1→a2→b1→b2 顺序), 槽位 4 清空;
槽位 1 (日语书 7,922 词) 与 槽位 2 (法语书 8,116 词) 原样保留。

游戏: WCP-WordGirlfriend (wcp.exe, Unity)
文件: %USERPROFILE%\\AppData\\LocalLow\\WCP\\wcp\\MyBook.es3

用法:
  py write_mybook_ru.py            # 实际写入(自动备份原文件)
  py write_mybook_ru.py --dry-run  # 只预览不写入
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

# (槽位, 级别列表, 标签) —— 合并单册, 槽位 1/2 (日/法) 不在写入范围
SLOTS = [
    (3, ['a1', 'a2', 'b1', 'b2'], '俄语词库(猫条版) 合并单册'),
    (4, [], '空槽位'),
]


def fmt_meaning(w):
    stress = f"[{w['stress']}]" if w.get('stress') else ''
    return f"{stress}{w['zh']}〈{w['pos']}〉"


def build_slot(words):
    word_list, word_dict = [], {}
    for w in words:
        word = w['word'].strip()
        meaning = fmt_meaning(w)
        if not word or not meaning:
            continue
        word_list.append(word)
        word_dict[word] = meaning
    return word_list, word_dict


def main():
    if game_running():
        print('wcp.exe 正在运行，请先关闭游戏后再写入 MyBook.es3')
        sys.exit(1)
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--file', default=str(MYBOOK))
    args = ap.parse_args()

    target = Path(args.file)
    data = json.loads((OUT / 'russian_books.json').read_text(
        encoding='utf-8'))
    levels = data['levels']

    doc = {}
    summary = []
    for slot, lvls, label in SLOTS:
        words = []
        for lv in lvls:
            words.extend(levels[lv])
        wlist, wdict = build_slot(words)
        doc[f'SelfBookList{slot}'] = {'__type': ARR_TYPE, 'value': wlist}
        doc[f'wordDictionary{slot}'] = {'__type': DICT_TYPE, 'value': wdict}
        summary.append((slot, label, len(wlist)))

    # 保留文件中我们不了解的键 + 不在本次写入范围的槽位 (槽位1日语/槽位2法语)
    existing = {}
    if target.exists():
        try:
            existing = json.loads(target.read_text(encoding='utf-8-sig'))
        except Exception as e:
            print(f'WARN: 原文件无法解析({e})，将只写入标准键', file=sys.stderr)
    for k, v in existing.items():
        base = ''.join(c for c in k if not c.isdigit())
        if base in ('SelfBookList', 'wordDictionary'):
            slot_no = ''.join(c for c in k if c.isdigit())
            if any(f'{base}{slot_no}' in doc for _, _, _ in SLOTS):
                continue  # 本次要写的槽位, 用新数据覆盖
        if k not in doc:
            doc[k] = v

    text = json.dumps(doc, ensure_ascii=False, indent=1)

    if args.dry_run:
        for slot, label, n in summary:
            print(f'槽位{slot} {label}: {n}词')
        print('--- 预览(前400字) ---')
        print(text[:400])
        return

    if not target.parent.exists():
        print(f'错误: 游戏数据目录不存在 {target.parent}')
        sys.exit(1)

    if target.exists():
        BACKUP_DIR.mkdir(exist_ok=True)
        bak = BACKUP_DIR / f'MyBook.es3.{time.strftime("%Y%m%d_%H%M%S")}.bak'
        shutil.copy2(target, bak)
        print(f'已备份原文件 -> {bak}')

    target.write_text(text, encoding='utf-8')
    print('写入完成:', target)
    for slot, label, n in summary:
        print(f'  槽位{slot} {label}: {n}词')

    check = json.loads(target.read_text(encoding='utf-8'))
    for slot, _, _label in SLOTS:
        lst = check[f'SelfBookList{slot}']['value']
        dct = check[f'wordDictionary{slot}']['value']
        assert isinstance(lst, list) and isinstance(dct, dict)
        for w in lst:
            assert w in dct, f'释义缺失: {w}'
    jp = check.get('SelfBookList1', {}).get('value', [])
    fr = check.get('SelfBookList2', {}).get('value', [])
    print(f'回读校验通过; 槽位1(日语书) {len(jp)} 词, 槽位2(法语书) {len(fr)} 词保留')


if __name__ == '__main__':
    main()
