# -*- coding: utf-8 -*-
"""从 JMdict(jmdict-simplified 3.6.2, 键名 words) 提取专业领域词条。

领域: IT = comp(computing); BIZ = bus(business) + finc(finance)
输出: output/topic_books.json {meta, books:{it:[...], biz:[...]}}
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
OUT = ROOT / 'output'

MAX_PER_BOOK = 900
MAX_WORD_LEN = 16

ROMAN_RE = re.compile(r'^[A-Za-z0-9\s\-~\.\'’Ａ-Ｚａ-ｚ]+$')
KANA_HAN_RE = re.compile(r'^[\u3040-\u30ffー・]+$')

# JMdict POS 实体码 -> 中文词性
POS_MAP = {
    'v1': '动2', 'v1-s': '动2', 'v2a-s': '动2', 'v4r': '动1',
    'v5aru': '动1', 'v5b': '动1', 'v5g': '动1', 'v5k': '动1',
    'v5k-s': '动1', 'v5m': '动1', 'v5n': '动1', 'v5r': '动1',
    'v5r-i': '动1', 'v5s': '动1', 'v5t': '动1', 'v5u': '动1',
    'v5u-s': '动1', 'v5uru': '动1', 'v5z': '动1', 'v4k': '动1',
    'v4s': '动1', 'v4t': '动1', 'v4n': '动1', 'v4h': '动1',
    'v4b': '动1', 'v4m': '动1', 'v4g': '动1', 'v4z': '动1',
    'vz': '动2', 'vk': '动3', 'vn': '动3', 'vr': '动1',
    'vs': '动3', 'vs-i': '动3', 'vs-s': '动3', 'vu': '动1',
    'v-unspec': '动',
    'adj-i': 'イ形', 'adj-ix': 'イ形', 'adj-yoi': 'イ形', 'adj-ii': 'イ形',
    'adj-na': 'ナ形', 'adj-no': 'ナ形', 'adj-t': 'ナ形', 'adj-nari': 'ナ形',
    'adj-f': '形', 'adj': '形',
    'n': '名', 'n-adv': '名', 'n-t': '名', 'n-suf': '接尾', 'n-pref': '接头',
    'pn': '代', 'adv': '副', 'adv-to': '副',
    'aux-adj': '助动', 'aux-v': '助动', 'aux': '助动',
    'conj': '接', 'ctr': '量', 'exp': '惯', 'int': '感',
    'prt': '助', 'pref': '接头', 'suf': '接尾',
}

MISC_SKIP = {'slang', 'vulgar', 'derog', 'obs', 'obsolete', 'joke', 'dated'}


def map_pos(pos_list):
    for p in pos_list or []:
        if p in POS_MAP:
            return POS_MAP[p]
    return ''


def normalize(w):
    return (w.replace('＝', '=').replace('　', ' ')
             .replace('・', '').strip())


def entry_candidates(e):
    """[(word, reading)] 候选, 汉字形优先, 跳过 rK/oK/iK(稀用/旧字/异体)。"""
    cands = []
    kana = e.get('kana', [])
    for kj in e.get('kanji', []):
        w = kj.get('text', '')
        tags = kj.get('tags') or []
        if not w or set(tags) & {'rK', 'oK', 'iK'}:
            continue
        rd = ''
        for k in kana:
            apk = k.get('appliesToKanji') or ['*']
            if '*' in apk or w in apk:
                rd = k.get('text', '')
                break
        cands.append((w, rd))
    return cands


def kana_headword(e):
    """纯假名/片假名词头(无常用汉字形时用)。"""
    if e.get('kanji'):
        return None
    for k in e.get('kana', []):
        if k.get('common') and k.get('text'):
            return k['text']
    return None


def pick_sense(e, wanted):
    for s in e.get('sense', []):
        flds = set(s.get('field') or [])
        if not (flds & wanted):
            continue
        if set(s.get('misc') or []) & MISC_SKIP:
            continue
        gl = [g.get('text', '') for g in s.get('gloss', []) if g.get('text')]
        if gl:
            return gl, s.get('partOfSpeech') or []
    return None, None


def common_fields(e):
    flds = set()
    for s in e.get('sense', []):
        flds |= set(s.get('field') or [])
    return flds


CJK_RE = re.compile(r'[\u3040-\u30ff\u4e00-\u9fff々〆ヶ]')


def word_ok(w):
    """词条合法性: 至少含一个假名/汉字, 不含 = 等无法生成音频文件名的符号。"""
    if not CJK_RE.search(w):
        return False
    if re.search(r'[=+＃#]', w):
        return False
    return True


def collect(words, wanted, skip, need_common=True):
    picked = {}
    seen_pair = set()
    for e in words:
        common = (any(k.get('common') for k in e.get('kanji', []))
                  or any(k.get('common') for k in e.get('kana', [])))
        if need_common and not common:
            continue
        flds = common_fields(e)
        if not (flds & wanted):
            continue
        glosses, pos = pick_sense(e, wanted)
        if not glosses:
            continue
        zh_pos = map_pos(pos)
        cands = entry_candidates(e)
        kw = kana_headword(e)
        if not cands and kw:
            cands = [(kw, '')]
        for w, rd in cands:
            w = normalize(w)
            if not w or len(w) > MAX_WORD_LEN or w in skip or not word_ok(w):
                continue
            pair = (rd or w, glosses[0])
            if pair in seen_pair:
                continue  # 同读音同义的不同字形(新旧字体)只保留一个
            old = picked.get(w)
            if old:
                seen_pair.add(pair)
                continue
            seen_pair.add(pair)
            picked[w] = {
                'word': w, 'reading': rd,
                'meaning_en': '; '.join(glosses[:4]),
                'pos': zh_pos, 'common': common,
            }
    rows = sorted(picked.values(),
                  key=lambda r: (r['common'], r['pos'] != '', -len(r['word'])),
                  reverse=True)
    return rows


def main():
    print('loading jmdict_eng.json ...', flush=True)
    doc = json.loads((DATA / 'jmdict_eng.json').read_text(encoding='utf-8'))
    words = doc['words']
    print(f'entries: {len(words)}', flush=True)

    jlpt = json.loads((OUT / 'jlpt_books.json').read_text(encoding='utf-8'))
    skip = set()
    for lv, rows in jlpt['levels'].items():
        for r in rows:
            skip.add(r['word'])
            if r.get('reading'):
                skip.add(r['reading'])
    print(f'jlpt skip: {len(skip)}', flush=True)

    it = collect(words, {'comp'}, skip)
    it_nc = collect(words, {'comp'}, skip, need_common=False)
    biz = collect(words, {'bus', 'finc', 'econ', 'trade'}, skip)
    biz_nc = collect(words, {'bus', 'finc', 'econ', 'trade'}, skip,
                     need_common=False)
    print(f'common-only: it={len(it)} biz={len(biz)}', flush=True)
    # common 词全收; 非 common 词补足到目标量(排后)
    it = (it + [r for r in it_nc if r not in it])[:MAX_PER_BOOK]
    biz = (biz + [r for r in biz_nc if r not in biz])[:MAX_PER_BOOK]
    print(f'final: it={len(it)} biz={len(biz)}', flush=True)

    result = {
        'meta': {
            'source': 'JMdict 3.6.2 (EDRDG, CC-BY-SA-4.0), jmdict-simplified json',
            'fields': {'it': ['comp'], 'biz': ['bus', 'finc']},
            'counts': {'it': len(it), 'biz': len(biz)},
        },
        'books': {'it': it, 'biz': biz},
    }
    (OUT / 'topic_books.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=1), encoding='utf-8')
    for tag in ('it', 'biz'):
        for r in result['books'][tag][:12]:
            print(f' {tag.upper()}:', r['word'], '|', r['reading'],
                  '|', r['meaning_en'][:55], '|', r['pos'])
    print('written output/topic_books.json')


if __name__ == '__main__':
    main()
