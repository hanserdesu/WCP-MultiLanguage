# -*- coding: utf-8 -*-
"""kaikki-ru.jsonl (Wiktionary wiktextract) -> 给 lemmas_ranked.json 补重音标注。

- 重音符: combining acute U+0301 (дру́г)。词含 ё 时 ё 天然带重音, 直接用词本身。
- 匹配: kaikki entry.word == lemma (字母骨架去重音、ё→е); 多条 entry 时取
  有重音形式者; 形式优先级 canonical > nominative+singular / infinitive > 任意。
- 同时抓 sounds[].ipa 存参考字段 (不显示)。

词表 ~9000 词, 只重音命中才是硬需求; 未命中词 stress='' (显示时不带 [])。
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'data' / 'raw' / 'kaikki-ru.jsonl'
LEM = ROOT / 'data' / 'lemmas_ranked.json'

ACUTE = '\u0301'


def skel(s: str) -> str:
    return s.replace(ACUTE, '').replace('\u0300', '').replace('ё', 'е').lower()


def pick_accented(entry, word):
    w_sk = skel(word)
    best = None
    best_score = -1
    for f in entry.get('forms', []):
        form = f.get('form', '')
        if ACUTE not in form:
            continue
        if skel(form) != w_sk:
            continue
        tags = set(f.get('tags', []))
        if 'canonical' in tags:
            score = 3
        elif 'infinitive' in tags or ('nominative' in tags and 'singular' in tags):
            score = 2
        else:
            score = 1
        if score > best_score:
            best, best_score = form, score
            if score == 3:
                break
    return best


def main():
    lemmas = json.loads(LEM.read_text(encoding='utf-8'))
    want = {w['word'] for w in lemmas}
    remaining = set(want)
    stress_map = {}   # lemma -> accented form
    ipa_map = {}
    n_entries = 0
    with SRC.open(encoding='utf-8') as fh:
        for line in fh:
            if ACUTE not in line and 'ё' not in line:
                continue
            if not remaining:
                break
            try:
                e = json.loads(line)
            except Exception:
                continue
            w = e.get('word') or ''
            if w not in remaining:
                continue
            n_entries += 1
            acc = None
            if ACUTE in line:
                acc = pick_accented(e, w)
            if acc:
                stress_map.setdefault(w, acc)
            else:
                stress_map.setdefault(w, '')
            if not e.get('sounds'):
                continue
            for s in e['sounds']:
                ipa = s.get('ipa')
                if ipa:
                    ipa_map.setdefault(w, ipa if isinstance(ipa, str)
                                       else ipa[0])
                    break
            if stress_map.get(w):
                remaining.discard(w)

    n_hit = 0
    for w in lemmas:
        word = w['word']
        if 'ё' in word and not stress_map.get(word):
            stress_map[word] = word   # ё 天然带重音
        s = stress_map.get(word, '')
        w['stress'] = s
        w['ipa'] = ipa_map.get(word, '')
        if s:
            n_hit += 1
    LEM.write_text(json.dumps(lemmas, ensure_ascii=False, indent=0),
                   encoding='utf-8')
    print(f'kaikki 词目匹配 {len(stress_map)}/{len(want)}, 重音命中 {n_hit}')
    miss = [w['word'] for w in lemmas[:500] if not w['stress']]
    print('前500词缺重音:', len(miss), miss[:10])


if __name__ == '__main__':
    main()
