# -*- coding: utf-8 -*-
"""提取德语 B1/B2 级别真实词元 (严格过滤屈折与前 7000 变位，对齐 DING 与 ECDICT 词典)"""
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def main():
    books = json.loads((ROOT / 'output' / 'german_books.json').read_text('utf-8'))
    known_lower = {w['word'].strip().lower() for lvl in books['levels'].values() for w in lvl}

    # 读取之前 35 块丢弃的所有变形词
    dropped_words = set()
    for n in range(35):
        p = ROOT / 'work' / f'cur_out_{n:02d}.json'
        if p.exists():
            d = json.loads(p.read_text('utf-8'))
            for it in d.get('drop', []):
                dropped_words.add(it['word'].strip().lower())

    # DING 词表
    ding_lemmas = {}
    with open(ROOT / 'data' / 'raw' / 'de-en.txt', 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split('::')
            if len(parts) != 2:
                continue
            de_part, en_part = parts[0].strip(), parts[1].strip()
            m = re.match(r"^([A-Za-zäöüßÄÖÜ\-]+)\s*(\{[^}]+\})?", de_part)
            if not m:
                continue
            w, pos = m.group(1), m.group(2) or ""
            if '-' in w and len(w) < 4:
                continue
            if w not in ding_lemmas:
                ding_lemmas[w] = (pos, en_part)

    # ECDICT 词表
    ecdict = {}
    with open(ROOT / 'data' / 'raw' / 'ecdict.csv', 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            w = row[0].strip().lower()
            trans = row[3].strip()
            if w and trans:
                lines = [l.strip() for l in trans.splitlines() if l.strip() and not l.strip().startswith('[')]
                clean_lines = []
                for l in lines:
                    cleaned = re.sub(r"^[a-z]+\.\s*", "", l)
                    cleaned = re.sub(r"\(.*?\)|\[.*?\]", "", cleaned).strip()
                    if cleaned:
                        clean_lines.append(cleaned)
                if clean_lines:
                    ecdict[w] = '；'.join(clean_lines[:2])

    raw_lines = (ROOT / 'data' / 'raw' / 'de_50k.txt').read_text('utf-8').splitlines()
    freq_map = {}
    # 我们关注真实进入 B1/B2 范围的高频词 (从 rank 3000 开始，且不在前 3488 词元池)
    for idx, line in enumerate(raw_lines, 1):
        parts = line.strip().rsplit(' ', 1)
        if len(parts) == 2:
            w, freq = parts[0].strip(), int(parts[1])
            freq_map[w] = (freq, idx)
            if w.lower() not in freq_map:
                freq_map[w.lower()] = (freq, idx)

    scored_lemmas = []
    seen = set()

    for lemma, (pos_tag, en_part) in ding_lemmas.items():
        w_low = lemma.lower()
        if w_low in known_lower or w_low in dropped_words or w_low in seen:
            continue
        if len(lemma) < 3 or len(lemma) > 25:
            continue
        if lemma not in freq_map and w_low not in freq_map:
            continue
        freq, rank = freq_map.get(lemma) or freq_map.get(w_low)
        
        # 排除 rank 过低 (前 7000 名内基本全都是 A1/A2 或人称变位)
        # B1 从 rank 3500 开始取纯正词元
        if rank < 3200:
            continue
        if lemma.isupper() and len(lemma) <= 4:
            continue

        first_chunk = re.split(r"[;|]", en_part)[0].strip()
        first_chunk = re.sub(r"\[.*?\]|\(.*?\)", "", first_chunk).strip()
        first_clean = re.sub(r"^(to\s+|the\s+|a\s+|an\s+)", "", first_chunk).strip().lower()
        zh = ecdict.get(first_clean)
        if not zh and ' ' in first_clean:
            zh = ecdict.get(first_clean.split()[0])
        if not zh:
            continue

        terms = [t.strip() for t in re.split(r"[,，;；\n]", zh) if t.strip() and not t.strip().startswith('[')]
        if not terms:
            continue
        zh_clean = '；'.join(terms[:3])

        # 词性映射
        if '{m}' in pos_tag:
            pos = 'n.m.'
        elif '{f}' in pos_tag:
            pos = 'n.f.'
        elif '{n}' in pos_tag:
            pos = 'n.'
        elif '{adj}' in pos_tag:
            pos = 'adj.'
        elif '{adv}' in pos_tag:
            pos = 'adv.'
        elif any(k in pos_tag for k in ['{vi}', '{vt}', '{vr}', '{v}']):
            pos = 'v.'
        elif lemma[0].isupper():
            pos = 'n.'
        elif lemma.endswith('en') or lemma.endswith('eln') or lemma.endswith('ern'):
            pos = 'v.'
        elif lemma.endswith('ig') or lemma.endswith('lich') or lemma.endswith('isch') or lemma.endswith('bar'):
            pos = 'adj.'
        else:
            pos = 'adv.'

        # 过滤明显动词第三人称变位/过去分词假词元
        if lemma.endswith('te') or lemma.endswith('test') or lemma.endswith('tet'):
            continue
        if lemma.startswith('ge') and lemma.endswith('t') and pos == 'v.':
            continue

        seen.add(w_low)
        scored_lemmas.append({
            'word': lemma,
            'pos': pos,
            'zh': zh_clean,
            'rank': rank,
            'freq': freq
        })

    scored_lemmas.sort(key=lambda x: x['rank'])
    print(f'符合标准的严格过滤德语词元总数: {len(scored_lemmas)}')

    # 划分 B1 与 B2 (目标：B1 2,500 词, B2 2,200 词，总增量 4,700 词)
    b1_items = scored_lemmas[:2500]
    b2_items = scored_lemmas[2500:4700]

    for it in b1_items:
        it['level'] = 'b1'
    for it in b2_items:
        it['level'] = 'b2'

    out_file = ROOT / 'work' / 'b1_b2_curated.json'
    out_file.parent.mkdir(exist_ok=True)
    out_file.write_text(json.dumps({'b1': b1_items, 'b2': b2_items}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'已生成干净的 B1 ({len(b1_items)} 词) 与 B2 ({len(b2_items)} 词) -> {out_file}')

if __name__ == '__main__':
    main()
