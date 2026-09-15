# -*- coding: utf-8 -*-
"""从 jmdict_eng.json 提取分主题专业词表 -> data/themed/<theme>.csv
   并汇总 output/themed_books.json (结构与 jlpt_books.json 一致)。

主题 -> JMDict 标签:
  it       field=comp            IT/计算机
  medical  field=med|pathol|anat 医学
  business field=bus|econ        商务/经济
  law      field=law             法律
  idiom    misc=id               惯用句
  onoma    misc=on-mim           拟声拟态
  yoji     misc=yoji             四字熟语

筛选原则: 词头干净(不含括号/非法文件名字符), 排除 vulg/obsc/derog,
优先 common 词形; 每主题上限 --cap 按优先级截断。
"""
import argparse
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
OUT = ROOT / 'output'

BAD_CHARS = re.compile(r'[\\/:*?"<>|()\[\]()（）\s]')

THEMES = {
    'it':       {'fields': {'comp'},                 'misc_any': set(), 'cap': 800},
    'medical':  {'fields': {'med', 'pathol', 'anat'},'misc_any': set(), 'cap': 800},
    'business': {'fields': {'bus', 'econ'},          'misc_any': set(), 'cap': 700},
    'law':      {'fields': {'law'},                  'misc_any': set(), 'cap': 600},
    'idiom':    {'fields': set(),                    'misc_any': {'id'},   'cap': 600},
    'onoma':    {'fields': set(),                    'misc_any': {'on-mim'},'cap': 500},
    'yoji':     {'fields': set(),                    'misc_any': {'yoji'}, 'cap': 500},
}
EXCLUDE_MISC = {'vulg', 'obsc', 'derog', 'sl'}

# 粗筛词头: 纯 ascii(如 "Wi-Fi" 除外规则后面统一过滤长度), 纯数字等
def headword_ok(w):
    if not w or len(w) < 1 or len(w) > 24:
        return False
    if BAD_CHARS.search(w):
        return False
    # 纯 ASCII 拉丁词头对日语学习意义小且 TTS 无法读
    if all(ord(c) < 128 for c in w):
        return False
    # 含小写拉丁字母混排(如 ラン泽词头一般已是片假名) — 允许长音符号
    return True


# uK=通常假名书写 rK=罕用 iK/oK/sK=不规范/旧式 -> 不能作为词头
BAD_KANJI_TAGS = {'uK', 'rK', 'iK', 'oK', 'sK'}


def pick_kanji(kanji_list):
    """返回 (词头, 是否常规汉字形)。只接受无 BAD_KANJI_TAGS 的汉字形。"""
    normal = [k for k in kanji_list if not (set(k.get('tags', [])) & BAD_KANJI_TAGS)]
    if not normal:
        return None
    common = [k for k in normal if k.get('common')]
    return (common or normal)[0]['text']


def pick_kana(kana_list, applies_word):
    """返回与 applies_word 匹配的读音; 找不到匹配返回 None。"""
    common = [k for k in kana_list if k.get('common')]
    pool = common or kana_list
    for k in pool:
        ap = k.get('appliesToKanji', [])
        if '*' in ap or applies_word in ap:
            return k['text']
    for k in kana_list:
        ap = k.get('appliesToKanji', [])
        if '*' in ap or applies_word in ap:
            return k['text']
    return None


def sense_gloss(sense):
    for g in sense.get('gloss', []):
        if g.get('lang') == 'eng' and g.get('text'):
            return g['text'].strip()
    return ''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cap', type=int, default=None, help='覆盖全局每主题上限')
    args = ap.parse_args()

    print('loading jmdict_eng.json ...', flush=True)
    d = json.loads((DATA / 'jmdict_eng.json').read_text(encoding='utf-8'))
    words = d['words']
    print(f'entries: {len(words)}', flush=True)

    # 全局已占用词头 (JLPT 书): 转义/拟声主题排除, 避免与基础义冲突
    jlpt_words = set()
    jb = OUT / 'jlpt_books.json'
    if jb.exists():
        jd = json.loads(jb.read_text(encoding='utf-8'))
        for lv in jd['levels'].values():
            for r in lv:
                jlpt_words.add(r['word'])
    NO_OVERLAP = {'idiom', 'onoma', 'yoji'}

    stats = {}
    per_theme = {t: [] for t in THEMES}
    seen_in_theme = {t: set() for t in THEMES}

    for ent in words:
        kanjis = ent.get('kanji', [])
        kanas = ent.get('kana', [])
        if not kanas:
            continue
        head = pick_kanji(kanjis)
        if head is None:
            # 无常规汉字形 -> 用假名词头 (common 优先)
            common_k = [k for k in kanas if k.get('common')]
            head = (common_k or kanas)[0]['text']
            reading = head
        else:
            reading = pick_kana(kanas, head)
            if reading is None:
                # 汉字形无对应读音(数据异常) -> 退回假名词头
                common_k = [k for k in kanas if k.get('common')]
                head = (common_k or kanas)[0]['text']
                reading = head
        if not headword_ok(head) or not headword_ok(reading):
            continue
        alt_kana = None
        if head == reading and len(kanas) > 1 and kanas[1]['text'] != reading:
            alt_kana = pick_kana(kanas[1:], head)

        for sense in ent.get('sense', []):
            fields = set(sense.get('field', []))
            misc = set(sense.get('misc', []))
            if misc & EXCLUDE_MISC:
                continue
            gloss = sense_gloss(sense)
            if not gloss:
                continue
            pos = ','.join(sense.get('partOfSpeech', []))
            for t, cfg in THEMES.items():
                if cfg['fields'] & fields or cfg['misc_any'] & misc:
                    if head in seen_in_theme[t]:
                        continue
                    if t in NO_OVERLAP and head in jlpt_words:
                        continue
                    if t == 'idiom' and len(head) < 2:
                        continue
                    if t == 'onoma' and not any(
                            '\u3040' <= c <= '\u30ff' for c in head):
                        continue  # 拟声拟态必须含假名(排除中文式叠词)
                    seen_in_theme[t].add(head)
                    common = (head and any(k.get('common') for k in kanjis)) or \
                             any(k.get('common') for k in kanas)
                    per_theme[t].append({
                        'word': head, 'reading': reading if reading != head else (alt_kana or ''),
                        'meaning_en': gloss, 'pos': pos, 'common': common,
                        'fields': sorted(fields), 'misc': sorted(misc),
                    })
                    break  # 一个 sense 只归一个主题

    OUT.mkdir(parents=True, exist_ok=True)
    tdir = DATA / 'themed'
    tdir.mkdir(parents=True, exist_ok=True)

    books = {'meta': {'source': 'JMDict/EDRDG (CC-BY-SA 4.0) via jmdict-simplified 3.6.2',
                      'themes': {}}, 'themes': {}}
    for t, cfg in THEMES.items():
        rows = per_theme[t]
        # 优先级: common 优先, 其次词长短的(核心词), 再按原顺序
        rows.sort(key=lambda r: (not r['common'], len(r['word'])))
        cap = args.cap or cfg['cap']
        rows = rows[:cap]
        books['themes'][t] = rows
        books['meta']['themes'][t] = {'count': len(rows),
                                      'common': sum(1 for r in rows if r['common'])}
        with open(tdir / f'{t}.csv', 'w', encoding='utf-8-sig', newline='') as f:
            wtr = csv.DictWriter(f, fieldnames=['word', 'reading', 'meaning_en', 'pos', 'common'])
            wtr.writeheader()
            for r in rows:
                wtr.writerow({k: r[k] for k in ['word', 'reading', 'meaning_en', 'pos', 'common']})
        stats[t] = len(rows)
        print(f"{t}: {len(rows)} (common {books['meta']['themes'][t]['common']})")

    (OUT / 'themed_books.json').write_text(json.dumps(books, ensure_ascii=False), encoding='utf-8')
    print('saved output/themed_books.json')


if __name__ == '__main__':
    main()
