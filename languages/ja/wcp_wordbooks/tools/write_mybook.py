# -*- coding: utf-8 -*-
"""将词书写入游戏的 MyBook.es3 (Easy Save 3 JSON)。

游戏: WCP-WordGirlfriend (wcp.exe, Unity)
文件: %USERPROFILE%\\AppData\\LocalLow\\WCP\\wcp\\MyBook.es3
格式: {"SelfBookList1": {"__type":"System.String[],mscorlib","value":[...]},
       "wordDictionary1": {"__type":"System.Collections.Generic.Dictionary`2[...],mscorlib","value":{...}}}

4 个槽位映射:
  1 = JLPT N5+N4 初级词汇
  2 = JLPT N3
  3 = JLPT N2
  4 = JLPT N1

用法:
  py write_mybook.py            # 实际写入(自动备份原文件)
  py write_mybook.py --dry-run  # 只预览不写入
"""
import argparse
import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'output'

MYBOOK = Path.home() / 'AppData' / 'LocalLow' / 'WCP' / 'wcp' / 'MyBook.es3'
BACKUP_DIR = MYBOOK.parent / 'MyBook_backups'

ARR_TYPE = 'System.String[],mscorlib'
DICT_TYPE = ('System.Collections.Generic.Dictionary`2[[System.String, mscorlib, '
             'Version=4.0.0.0, Culture=neutral, PublicKeyToken=b77a5c561934e089],'
             '[System.String, mscorlib, Version=4.0.0.0, Culture=neutral, '
             'PublicKeyToken=b77a5c561934e089]],mscorlib')

SLOTS = [
    (1, ['n5', 'n4'], 'JLPT N5+N4 初级'),
    (2, ['n3'], 'JLPT N3'),
    (3, ['n2'], 'JLPT N2'),
    (4, ['n1'], 'JLPT N1'),
]


def load_books():
    data = json.loads((OUT / 'jlpt_books.json').read_text(encoding='utf-8'))
    return data['levels']


def make_entry(value):
    return {'__type': value[0], 'value': value[1]}


def build_slot(words):
    """words: [{'word','reading','meaning','meaning_en'}...]"""
    word_list, word_dict = [], {}
    for w in words:
        word = w['word'].strip()
        meaning = (w.get('meaning') or w.get('meaning_en') or '').strip()
        if not word:
            continue
        word_list.append(word)
        word_dict[word] = meaning
    return word_list, word_dict


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--file', default=str(MYBOOK))
    args = ap.parse_args()

    target = Path(args.file)
    books = load_books()
    doc = {}
    summary = []
    for slot, levels, label in SLOTS:
        words = []
        for lv in levels:
            words.extend(books[lv])
        wlist, wdict = build_slot(words)
        doc[f'SelfBookList{slot}'] = make_entry((ARR_TYPE, wlist))
        doc[f'wordDictionary{slot}'] = make_entry((DICT_TYPE, wdict))
        summary.append((slot, label, len(wlist),
                        sum(1 for m in wdict.values() if m)))

    # 保留文件中我们不了解的其他键（如游戏新增内容）
    existing = {}
    if target.exists():
        try:
            existing = json.loads(target.read_text(encoding='utf-8-sig'))
        except Exception as e:
            print(f'WARN: 原文件无法解析({e})，将只写入标准键', file=sys.stderr)
    for k, v in existing.items():
        base = ''.join(c for c in k if not c.isdigit())
        if base not in ('SelfBookList', 'wordDictionary') and k not in doc:
            doc[k] = v

    text = json.dumps(doc, ensure_ascii=False, indent=1)

    if args.dry_run:
        for slot, label, n, nmean in summary:
            print(f'槽位{slot} {label}: {n}词, {nmean}条释义')
        print('--- 预览(前600字) ---')
        print(text[:600])
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
    for slot, label, n, nmean in summary:
        print(f'  槽位{slot} {label}: {n}词, {nmean}条释义')

    # 校验回读
    check = json.loads(target.read_text(encoding='utf-8'))
    assert str(len(doc)) and check.keys() == doc.keys()
    total = 0
    for slot, _, _label, in SLOTS:
        lst = check[f'SelfBookList{slot}']['value']
        dct = check[f'wordDictionary{slot}']['value']
        assert isinstance(lst, list) and isinstance(dct, dict)
        for w in lst:
            assert w in dct, f'释义缺失: {w}'
        total += len(lst)
    print(f'回读校验通过, 共 {total} 个词条')


if __name__ == '__main__':
    main()
