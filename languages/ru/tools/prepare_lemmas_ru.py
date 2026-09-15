# -*- coding: utf-8 -*-
"""data/raw/ru_50k.txt -> data/lemmas_ranked.json

词源: hermitdave/FrequencyWords (OpenSubtitles 2018) 俄语前 50,000 词形频率。
词元还原: pymorphy3 (OpenCorpora 词典)。

流程 (对应法语项目 prepare_lemmas.py 的 Lexique lemme 聚合):
  - 每个词形取 pymorphy3 最优解析 -> normal_form 作为词元, 词形频率累加到词元
  - 过滤: 专名(所有解析均带 Name/Surn/Patr/Geox/Orgn/Trad)/无解析词/
    拉丁或数字混入/单字母(仅保留 俄语中真实成词的单字母: в с к у о я а и ж б э)
  - 词性: 取该词元下频率最高词形的解析 (NOUN 带性别 -> n.m./n.f./n.n.)
  - stress 字段留空, 由 enrich_stress.py 从 kaikki (Wiktionary) 补重音标注形式

输出: [{word, stress, pos, freq, rank}] 按频率降序
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
import pymorphy3

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'data' / 'raw' / 'ru_50k.txt'
DST = ROOT / 'data' / 'lemmas_ranked.json'
TOP_N = 9000

PROPER = {'Name', 'Surn', 'Patr', 'Geox', 'Orgn', 'Trad'}
SINGLE_OK = set('вскуояижбэ')

POS_LABEL = {
    'NOUN': 'n.', 'VERB': 'v.', 'INFN': 'v.', 'GRND': 'v.', 'PRTS': 'v.',
    'PRTF': 'v.', 'ADJF': 'adj.', 'ADJS': 'adj.', 'COMP': 'adj.',
    'NUMR': 'num.', 'NPRO': 'pron.', 'ADVBO': 'adv.', 'ADVB': 'adv.',
    'PRED': 'пред.', 'PREP': 'prep.', 'CONJ': 'conj.', 'PRCL': 'part.',
    'INTJ': 'interj.',
}

CYR_RE = re.compile(r'^[а-яё-]+$')


def main():
    morph = pymorphy3.MorphAnalyzer()
    lemmas = {}   # lemma -> {'freq': int, 'best': (count, parse)}
    n_lines = n_skip = 0
    for line in SRC.read_text(encoding='utf-8').splitlines():
        n_lines += 1
        parts = line.rsplit(' ', 1)
        if len(parts) != 2:
            continue
        form, cnt_s = parts[0].strip().lower(), parts[1]
        try:
            cnt = int(cnt_s)
        except ValueError:
            continue
        if not form or not CYR_RE.match(form):
            n_skip += 1
            continue
        if len(form) == 1 and form not in SINGLE_OK:
            n_skip += 1
            continue
        parses = morph.parse(form)
        good = [p for p in parses if p.tag.POS and p.is_known]
        if not good:
            n_skip += 1
            continue
        # 专名: 所有可行解析都带专名词性 -> 剔除
        if all(PROPER & set(p.tag.grammemes) for p in good):
            n_skip += 1
            continue
        best = good[0]   # pymorphy 已按打分排序
        lemma = best.normal_form
        gender = str(best.tag.gender) if best.tag.gender else None
        cur = lemmas.get(lemma)
        if cur is None:
            lemmas[lemma] = {'freq': cnt, 'cnt': cnt, 'pos': best.tag.POS,
                             'gender': gender}
        else:
            cur['freq'] += cnt
            if cnt > cur['cnt']:
                cur['cnt'] = cnt
                cur['pos'] = best.tag.POS
                cur['gender'] = gender
    out = []
    for lemma, v in lemmas.items():
        pos = POS_LABEL.get(v['pos'], (v['pos'] or '').lower())
        if pos == 'n.' and v['gender'] in ('masc', 'femn', 'neut'):
            pos = {'masc': 'n.m.', 'femn': 'n.f.', 'neut': 'n.n.'}[v['gender']]
        out.append({'word': lemma, 'stress': '', 'pos': pos,
                    'freq': v['freq']})
    out.sort(key=lambda x: -x['freq'])
    for i, w in enumerate(out):
        w['rank'] = i + 1
    out = out[:TOP_N]
    DST.write_text(json.dumps(out, ensure_ascii=False, indent=0),
                   encoding='utf-8')
    from collections import Counter
    pos_dist = Counter(w['pos'] for w in out)
    print(f'输入词形 {n_lines}, 过滤 {n_skip}, 词元 {len(lemmas)}, '
          f'输出 TOP {TOP_N}')
    print('词性分布:', dict(pos_dist.most_common()))
    for w in out[:15]:
        print(' ', w['word'], w['pos'], w['freq'])
    print('  ...')
    for w in out[-5:]:
        print(' ', w['word'], w['pos'], w['freq'])


if __name__ == '__main__':
    main()
