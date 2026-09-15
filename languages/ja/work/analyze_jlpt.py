import csv, collections, json

levels = {}
for n in [5,4,3,2,1]:
    path = f'D:/Japanese/work/data/jlpt_n{n}.csv'
    words = []
    with open(path, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            expr = row['expression'].strip()
            read = row['reading'].strip()
            if expr:
                words.append((expr, read))
    levels[n] = words
    print(f'N{n}: {len(words)} rows, {len(set(w for w,r in words))} unique expressions')

# check overlaps between consecutive levels by expression
sets = {n: set(w for w,r in levels[n]) for n in levels}
for a in [5,4,3,2,1]:
    for b in [5,4,3,2,1]:
        if a < b:
            print(f'N{a} ∩ N{b}: {len(sets[a] & sets[b])}')

# how many expressions missing a reading
for n in levels:
    missing = sum(1 for w,r in levels[n] if not r)
    katakana = sum(1 for w,r in levels[n] if w and all('ァ'<=c<='ヶ' for c in w))
    kana_only = sum(1 for w,r in levels[n] if w and all('ぁ'<=c<='ゖ' or 'ァ'<=c<='ヶ' or c in 'ー・〜' for c in w))
    print(f'N{n}: missing_reading={missing}, pure_katakana={katakana}, pure_kana={kana_only}')

# check multi-reading expressions
by_expr = collections.defaultdict(set)
for n in levels:
    for w,r in levels[n]:
        if r: by_expr[w].add(r)
multi = {w:rs for w,rs in by_expr.items() if len(rs)>1}
print(f'expressions with multiple readings: {len(multi)}; sample: {dict(list(multi.items())[:5])}')
