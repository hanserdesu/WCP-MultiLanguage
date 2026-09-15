# -*- coding: utf-8 -*-
"""合并精选批次 -> output/german_books.json {levels:{a1,a2,b1,b2}}。

- dedup 列表 = 该词形的 lemma 已在别处保留 (不计入 drop)。
- 按 lemma 去重, 首见 (词频最高) 优先; 词书单词 = lemma。
- IPA 用 epitran deu-Latn 规则转换, 失败则留空。
词条: {word, ipa, pos, zh, level, rank}
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / 'work'
OUT = ROOT / 'output' / 'german_books.json'
LEVELS = ('a1', 'a2', 'b1', 'b2')


def make_ipa():
    try:
        import epitran
        epi = epitran.Epitran('deu-Latn')
    except Exception as e:
        print('WARN: epitran 不可用:', e)
        return None

    def to_ipa(word):
        try:
            ipa = epi.transliterate(word)
        except Exception:
            return ''
        if not ipa or not all(
                c.isalpha() or c in 'ɑøœɛəɪʊɔɐʃʒçŋɾː̯̆' for c in ipa):
            return ''
        return ipa
    return to_ipa


def main():
    to_ipa = make_ipa()
    by_lemma = {}
    n_dedup = 0
    n = 0
    while (WORK / f'cand_{n:02d}.json').exists():
        src = json.loads((WORK / f'cand_{n:02d}.json').read_text(
            encoding='utf-8'))
        outf = WORK / f'cur_out_{n:02d}.json'
        d = json.loads(outf.read_text(encoding='utf-8'))
        for it in d['kept']:
            lemma = (it.get('lemma') or it['word']).strip()
            if lemma not in by_lemma:
                by_lemma[lemma] = {
                    'word': lemma, 'zh': it['zh'].strip(),
                    'level': it['level'], 'pos': it['pos'],
                    'rank': next(w['rank'] for w in src if w['word'] == it['word']),
                }
        n_dedup += len(d.get('dedup', []))
        n += 1
    levels = {lv: [] for lv in LEVELS}
    for w in by_lemma.values():
        levels[w['level']].append(w)
    for lv in LEVELS:
        levels[lv].sort(key=lambda x: x['rank'])
        for w in levels[lv]:
            w['ipa'] = to_ipa(w['word']) if to_ipa else ''
    total = sum(len(v) for v in levels.values())
    no_ipa = sum(1 for v in levels.values() for w in v if not w['ipa'])
    doc = {'meta': {'total': total, 'dedup_forms': n_dedup,
                    'no_ipa': no_ipa,
                    'source': 'OpenSubtitles de_50k + main-agent curation'},
           'levels': {lv: [{k: w[k] for k in
                            ('word', 'ipa', 'pos', 'zh', 'level', 'rank')}
                           for w in levels[lv]] for lv in LEVELS}}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1),
                   encoding='utf-8')
    print('级别分布:', {lv: len(levels[lv]) for lv in LEVELS},
          '合计', total, '| dedup 词形', n_dedup, '| 无IPA', no_ipa)


if __name__ == '__main__':
    main()
