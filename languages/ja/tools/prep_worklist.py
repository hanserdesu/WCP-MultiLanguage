# -*- coding: utf-8 -*-
"""从下载的 JLPT CSV 生成按读音排序的工作清单。

- 每个词归入其最低级别（N5<N4<N3<N2<N1），保证跨级别不重复。
- 输出 data/worklist/n{n}.json: [{e: 表记, r: 读音, en: 英文释义}]
- 读音按五十音排序（片假名映射为平假名后排），同音词相邻，便于人工合并为一条词书条目。
"""
import csv, json, os, re, unicodedata

WORK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(WORK, 'data')
OUT = os.path.join(DATA, 'worklist')
os.makedirs(OUT, exist_ok=True)


def kata_to_hira(s):
    out = []
    for c in s:
        cp = ord(c)
        if 0x30A1 <= cp <= 0x30F6:
            out.append(chr(cp - 0x60))
        else:
            out.append(c)
    return ''.join(out)


def sort_key(r):
    r = kata_to_hira(r.strip())
    r = r.replace('ー', 'あ')  # 长音符号排前面近似处理
    r = r.replace('・', '').replace(' ', '').replace('　', '')
    return r


def clean(s):
    s = s.strip()
    s = s.replace('　', ' ')
    return s


def main():
    # 读取所有级别
    rows = {n: [] for n in [5, 4, 3, 2, 1]}
    for n in rows:
        path = os.path.join(DATA, f'jlpt_n{n}.csv')
        with open(path, encoding='utf-8') as f:
            for row in csv.DictReader(f):
                e = clean(row['expression'])
                r = clean(row['reading'])
                en = clean(row.get('meaning', '')).strip('"')
                tags = row.get('tags', '')
                if not e:
                    continue
                rows[n].append({'e': e, 'r': r, 'en': en, 'tags': tags})

    # 全局按表记去重（跨级别），归入最低级别
    seen = {}  # expr -> level
    for n in [5, 4, 3, 2, 1]:
        for row in rows[n]:
            if row['e'] in seen:
                continue
            seen[row['e']] = n

    # 分配
    assigned = {n: [] for n in [5, 4, 3, 2, 1]}
    for expr, n in seen.items():
        # 找到该 expr 在对应级别的行（取第一条）
        for row in rows[n]:
            if row['e'] == expr:
                assigned[n].append(row)
                break

    # 每级别排序并写出
    for n in [5, 4, 3, 2, 1]:
        items = assigned[n]
        items.sort(key=lambda row: (sort_key(row['r'] or row['e']), row['e']))
        out_path = os.path.join(OUT, f'n{n}.json')
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(items, f, ensure_ascii=False, indent=1)
        print(f'N{n}: {len(items)} words -> {out_path}')

    # 检查同级别内读音冲突（同读音不同表记）——这些需要合并条目
    for n in [5, 4, 3, 2, 1]:
        by_r = {}
        for row in assigned[n]:
            w = row['r'] or row['e']
            by_r.setdefault(w, []).append(row['e'])
        dups = {r: es for r, es in by_r.items() if len(es) > 1}
        print(f'N{n}: {len(dups)} readings with multiple expressions (merge candidates)')
        if n == 5:
            print('  sample:', dict(list(dups.items())[:8]))


if __name__ == '__main__':
    main()
