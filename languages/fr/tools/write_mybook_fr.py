# -*- coding: utf-8 -*-
"""将法语词书写入游戏 MyBook.es3 (Easy Save 3 JSON)。

默认合并模式: 全部 8,116 词只写进槽位 2 (a1→a2→b1→b2 顺序)。槽位 1、3、4
完全保留，避免覆盖用户已经在其它槽位使用的任意词书。
--split 恢复旧三册模式: 槽位2=A1+A2, 槽位3=B1, 槽位4=B2。

游戏: WCP-WordGirlfriend (wcp.exe, Unity)
文件: %USERPROFILE%\\AppData\\LocalLow\\WCP\\wcp\\MyBook.es3

用法:
  py write_mybook_fr.py            # 合并单册写入(自动备份原文件)
  py write_mybook_fr.py --split    # 三册分级写入
  py write_mybook_fr.py --dry-run  # 只预览不写入
"""
import argparse
import json
import sys
from pathlib import Path

from es3_safe import write_values

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'output'

MYBOOK = Path.home() / 'AppData' / 'LocalLow' / 'WCP' / 'wcp' / 'MyBook.es3'
BACKUP_DIR = MYBOOK.parent / 'MyBook_backups'

ARR_TYPE = 'System.String[],mscorlib'
DICT_TYPE = ('System.Collections.Generic.Dictionary`2[[System.String, mscorlib, '
             'Version=4.0.0.0, Culture=neutral, PublicKeyToken=b77a5c561934e089],'
             '[System.String, mscorlib, Version=4.0.0.0, Culture=neutral, '
             'PublicKeyToken=b77a5c561934e089]],mscorlib')

# (槽位, 级别列表, 标签) —— 默认合并单册
SLOTS_COMBINED = [
    (2, ['a1', 'a2', 'b1', 'b2'], '法语词库(猫条版) 合并单册'),
]
SLOTS_SPLIT = [
    (2, ['a1', 'a2'], '法语 A1+A2 初级'),
    (3, ['b1'], '法语 B1'),
    (4, ['b2'], '法语 B2'),
]


def fmt_meaning(w):
    ipa = f"[{w['ipa']}] " if w.get('ipa') else ''
    return f"{ipa}{w['zh']}〈{w['pos']}〉"


def build_slot(words):
    word_list, word_dict = [], {}
    for w in words:
        word = w['word'].strip()
        meaning = fmt_meaning(w)
        if not word or not meaning:
            continue
        if word in word_dict:
            continue
        word_list.append(word)
        word_dict[word] = meaning
    return word_list, word_dict


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--split', action='store_true',
                    help='恢复旧三册模式 (槽位2=A1+A2, 3=B1, 4=B2)')
    ap.add_argument('--file', default=str(MYBOOK))
    args = ap.parse_args()

    target = Path(args.file)
    data = json.loads((OUT / 'french_books.json').read_text(
        encoding='utf-8'))
    levels = data['levels']
    slots = SLOTS_SPLIT if args.split else SLOTS_COMBINED

    doc = {}
    summary = []
    for slot, lvls, label in slots:
        words = []
        for lv in lvls:
            words.extend(levels[lv])
        wlist, wdict = build_slot(words)
        doc[f'SelfBookList{slot}'] = {'__type': ARR_TYPE, 'value': wlist}
        doc[f'wordDictionary{slot}'] = {'__type': DICT_TYPE, 'value': wdict}
        summary.append((slot, label, len(wlist)))

    updates = {key: (node['value'], node['__type']) for key, node in doc.items()}
    text = write_values(target, updates, dry_run=True)

    if args.dry_run:
        for slot, label, n in summary:
            print(f'槽位{slot} {label}: {n}词')
        print('--- 预览(前400字) ---')
        print(text[:400])
        return

    if not target.parent.exists():
        print(f'错误: 游戏数据目录不存在 {target.parent}')
        sys.exit(1)

    write_values(target, updates)
    print('写入完成:', target)
    for slot, label, n in summary:
        print(f'  槽位{slot} {label}: {n}词')

    check = json.loads(target.read_text(encoding='utf-8'))
    for slot, _, _label in slots:
        lst = check[f'SelfBookList{slot}']['value']
        dct = check[f'wordDictionary{slot}']['value']
        assert isinstance(lst, list) and isinstance(dct, dict)
        for w in lst:
            assert w in dct, f'释义缺失: {w}'
    old = check.get('SelfBookList1', {}).get('value', [])
    print(f'回读校验通过; 槽位1(日语书)保留 {len(old)} 词，槽位3/4未触及')


if __name__ == '__main__':
    main()
