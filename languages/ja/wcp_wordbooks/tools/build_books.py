# -*- coding: utf-8 -*-
"""构建 WCP-WordGirlfriend 日语词书数据集。

数据源:
  - OpenJLPT (CC-BY-SA-4.0)  https://github.com/evanclan/OpenJLPT  主数据
  - Kaishi 1.5k zh-CN 汉化版  https://github.com/maimemo/kaishi-zh-cn  中文释义
  - Bluskyo/JLPT_Vocabulary    读音交叉验证

输出:
  output/jlpt_books.json   各级别词书结构化数据
"""
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
OUT = ROOT / 'output'

LEVELS = ['n5', 'n4', 'n3', 'n2', 'n1']


def clean(s):
    if s is None:
        return ''
    s = s.replace('\r', ' ').replace('\n', ' ').strip()
    s = re.sub(r'\s+', ' ', s)
    return s


def load_openjlpt():
    books = {}
    for lv in LEVELS:
        path = DATA / f'openjlpt_vocab_{lv}.csv'
        rows = []
        with open(path, encoding='utf-8-sig', newline='') as f:
            for row in csv.DictReader(f):
                word = clean(row.get('word'))
                if not word:
                    continue
                rows.append({
                    'word': word,
                    'reading': clean(row.get('reading')),
                    'meaning_en': clean(row.get('meanings')),
                    'example_ja': clean(row.get('example_ja')),
                    'example_en': clean(row.get('example_en')),
                    'level': lv.upper(),
                })
        books[lv] = rows
    return books


def load_bluskyo():
    path = DATA / 'bluskyo_all.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    # {word: [{reading, level}]}  level 1=N1 ... 5=N5
    out = {}
    for word, variants in data.items():
        out[word] = [(v.get('reading', ''), v.get('level')) for v in variants]
    return out


KANJI_RE = re.compile(r'[\u4e00-\u9fff々〆ヶ]')
KANJI_ONLY_NUM = re.compile(r'[\u4e00-\u9fff々〆]')


def has_kanji(word):
    return bool(KANJI_RE.search(word))


KANA_RE = re.compile(r'^[\u3040-\u30ffー・]+$')


def is_kana_only(word):
    return bool(KANA_RE.match(word))


def strip_html(s):
    return re.sub(r'<[^>]*>', '', s or '').strip()


def load_kaishi():
    """返回 word -> 中文释义 的映射（含假名形式）。"""
    path = DATA / 'kaishi15k_zh.tsv'
    mapping = {}
    with open(path, encoding='utf-8-sig', newline='') as f:
        reader = csv.reader(f, delimiter='\t')
        for row in reader:
            if not row or row[0].startswith('#'):
                continue
            if len(row) < 4:
                continue
            word = clean(row[1])
            reading = clean(row[2])
            meaning = clean(row[3])
            furigana = clean(row[4]) if len(row) > 4 else ''
            pos = clean(row[14]) if len(row) > 14 else ''
            if not word or not meaning:
                continue
            meaning = re.sub(r'<br\s*/?>', ' ', meaning)
            meaning = strip_html(meaning)
            pos = strip_html(pos)
            base = {'meaning': meaning, 'reading': reading, 'pos': pos}
            mapping.setdefault(word, base)
            # 假名条目（kanji词的假名读法）也纳入
            if reading and reading != word:
                mapping.setdefault(reading, base)
            m = re.match(r'^(.*?)\[([^\]]+)\]$', furigana)
            if m:
                kanji_form = clean(m.group(1))
                kana_form = clean(m.group(2))
                if kanji_form:
                    mapping.setdefault(kanji_form, base)
                if kana_form:
                    mapping.setdefault(kana_form, base)
    return mapping


def strip_reading_brackets(s):
    return re.sub(r'\[|\]', '', s)


def fmt_meaning_zh(word, reading, zh, pos):
    """游戏内显示的释义文本。"""
    if not zh:
        return ''
    core = zh
    if pos:
        pos = pos.replace('，', ',').strip(', ')
        if pos and pos not in ('', '-'):
            core = f'{core}〈{pos}〉'
    if (reading and has_kanji(word) and reading != word
            and not is_kana_only(word)):
        return f'【{reading}】{core}'
    return core


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    books = load_openjlpt()
    bluskyo = load_bluskyo()
    kaishi = load_kaishi()

    report = {'kaishi_hits': 0, 'kaishi_total': 0, 'reading_fixed': 0,
              'bluskyo_extra': Counter()}

    for lv in LEVELS:
        rows = books[lv]
        seen = set()
        dedup = []
        for r in rows:
            w = r['word']
            if w in seen:
                continue
            seen.add(w)
            dedup.append(r)
        rows = dedup

        for r in rows:
            w, rd = r['word'], r['reading']
            # 读音补全/校正 (Bluskyo)，仅限含汉字词，避免片假名截断读音
            if (not rd or rd == w) and has_kanji(w) and w in bluskyo:
                variants = bluskyo[w]
                for brd, blv in variants:
                    if brd and brd != w:
                        r['reading'] = brd
                        report['reading_fixed'] += 1
                        break
            # Kaishi 中文释义
            report['kaishi_total'] += 1
            hit = kaishi.get(w)
            if hit is None and rd:
                hit = kaishi.get(rd)
            if hit and hit['meaning']:
                r['meaning_zh'] = hit['meaning']
                r['pos_zh'] = hit['pos']
                if not r['reading']:
                    r['reading'] = hit['reading']
                report['kaishi_hits'] += 1
            else:
                r['meaning_zh'] = ''

        # 生成游戏内释义文本
        for r in rows:
            r['meaning'] = fmt_meaning_zh(r['word'], r['reading'],
                                          r['meaning_zh'], r.get('pos_zh', ''))
            if not r['meaning'] and r['meaning_en']:
                # 未翻译时回退英文
                r['meaning'] = r['meaning_en']

        books[lv] = rows

    # 汇总
    result = {
        'meta': {
            'generated': 'WCP 日语词书管线',
            'sources': [
                'OpenJLPT (CC-BY-SA-4.0) https://github.com/evanclan/OpenJLPT',
                'Kaishi 1.5k zh-CN https://github.com/maimemo/kaishi-zh-cn',
                'Bluskyo/JLPT_Vocabulary https://github.com/Bluskyo/JLPT_Vocabulary',
            ],
            'stats': {
                lv: {'count': len(books[lv]),
                     'zh_covered': sum(1 for r in books[lv] if r['meaning_zh']),
                     'with_reading': sum(1 for r in books[lv] if r['reading'])}
                for lv in LEVELS
            },
            'report': {'kaishi_hits': report['kaishi_hits'],
                       'kaishi_total': report['kaishi_total'],
                       'reading_fixed': report['reading_fixed']},
        },
        'levels': books,
    }
    out_path = OUT / 'jlpt_books.json'
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=1),
                        encoding='utf-8')
    print(json.dumps(result['meta']['stats'], ensure_ascii=False, indent=1))
    print('report:', json.dumps(result['meta']['report'], ensure_ascii=False))
    print('written:', out_path)


if __name__ == '__main__':
    main()
