# -*- coding: utf-8 -*-
"""精细化洗练德语 B1/B2 词表：
1. 规范大小写：名词首字母大写，动词、形容词、副词首字母小写。
2. 过滤人名（如 Iwan, Bob）、复数词（如 Mäuse -> 对应已收录或清理）、第三人称假名词（Reagiert）。
3. 生成纯净 IPA 音标（借助 tools/g2p_de.py）。
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
import g2p_de

NAMES_BLACK = {
    'iwan', 'elena', 'sarah', 'katja', 'maria', 'anna', 'lisa', 'julia',
    'peter', 'michael', 'thomas', 'andreas', 'stefan', 'martin', 'alexander',
    'robert', 'daniel', 'christian', 'david', 'frank', 'jens', 'marcus',
    'jürgen', 'klaus', 'hans', 'wolfgang', 'dieter', 'uwe', 'werner',
    'holst', 'avery', 'roberts', 'hugh', 'ludwig', 'fiona', 'archie', 'elisabeth',
    'henri', 'brad', 'francis', 'felix', 'beth', 'paula', 'lou', 'davis', 'jacob'
}

def clean_zh(zh):
    zh = zh.replace('\n', '；').replace('\n', '；').replace('\r', '')
    terms = []
    for t in re.split(r'[,，;；]', zh):
        t = t.strip()
        t = re.sub(r'^[a-z]+\.\s*', '', t)
        t = re.sub(r'\(.*?\)|\[.*?\]', '', t).strip()
        if t and len(t) <= 12 and t not in terms:
            terms.append(t)
    return '；'.join(terms[:3]) if terms else zh[:15]

def main():
    raw_data = json.loads((ROOT / 'work' / 'b1_b2_curated.json').read_text('utf-8'))
    books = json.loads((ROOT / 'output' / 'german_books.json').read_text('utf-8'))
    known_lower = {w['word'].strip().lower() for lvl in books['levels'].values() for w in lvl}

    seen_final = set(known_lower)

    def process_list(items, target_len, level):
        res = []
        for it in items:
            w = it['word'].strip()
            pos = it['pos']
            w_low = w.lower()

            if w_low in seen_final or w_low in NAMES_BLACK:
                continue
            if len(w) < 3 or len(w) > 22:
                continue

            # 动词必须以 en/eln/ern 结尾且小写
            if pos == 'v.':
                if not (w_low.endswith('en') or w_low.endswith('eln') or w_low.endswith('ern')):
                    continue
                w = w_low
            elif pos in ('adj.', 'adv.'):
                w = w_low
                # 排除动词过去分词当普通词
                if w.startswith('ge') and w.endswith('t') and len(w) > 5:
                    # 除非是常见形容词
                    pass
            elif 'n' in pos: # 名词首字母必须大写
                if w[0].islower():
                    w = w[0].upper() + w[1:]
                # 排除动词变位误判为名词
                if w.endswith('t') and w.lower().endswith(('iert', 'acht', 'eckt')):
                    continue
                if w.endswith(('test', 'tet', 'st')):
                    continue

            zh = clean_zh(it['zh'])
            if not zh or len(zh) < 1:
                continue

            # 生成 IPA
            ipa = g2p_de.to_ipa(w)

            seen_final.add(w.lower())
            res.append({
                'word': w,
                'pos': pos,
                'zh': zh,
                'ipa': ipa,
                'level': level,
                'rank': it['rank']
            })
            if len(res) >= target_len:
                break
        return res

    b1_final = process_list(raw_data['b1'], 2400, 'b1')
    b2_final = process_list(raw_data['b2'], 2300, 'b2')

    print(f'已精炼 B1: {len(b1_final)} 词, B2: {len(b2_final)} 词')
    out = {'b1': b1_final, 'b2': b2_final}
    (ROOT / 'work' / 'b1_b2_refined.json').write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')

if __name__ == '__main__':
    main()
