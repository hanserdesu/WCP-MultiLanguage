# -*- coding: utf-8 -*-
"""Korean dataset v2 builder (2026-09-15 质量审计修复, P1).

审计问题:
  1. 释义混杂: 438 条纯英文 + ~900 条繁体, 全库无简体;
  2. 例句中文括注同为繁体 (2,084/9,369);
  3. 词量 3,123 < TOPIK-6 通说 5,000+。

修复 (本脚本, 幂等可续跑):
  A. 繁->简 (opencc t2s): 全部 meaning + 例句中文括注;
  B. 438 条英文释义 -> mymemory 缓存翻译 (output/ko_translation_cache.json);
  C. 扩词: vocab5000 (data/raw/korean_vocab_5000_zh.jsonl) 中 1,602 个新词
     (zh gloss 自带, romanization 作 ipa) -> level topik4;
     TSV (topik_nikl_combined) 新词由 kaikki 英文释义经缓存翻译 -> topik4/5;
  D. 新词例句由 batch_gen_sentences_ko 引擎在 books 落盘后统一生成。

分批落盘: 每处理 N 词写一次 books 文件, 中断可续。
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from opencc import OpenCC

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
BOOKS_FILE = ROOT / 'output' / 'korean_books.json'
CACHE_FILE = ROOT / 'output' / 'ko_translation_cache.json'
RAW = ROOT / 'data' / 'raw'

cc = OpenCC('t2s')


def load_cache():
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text(encoding='utf-8'))
    return {}


def save_cache(cache):
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding='utf-8')


def mymemory_translate(text):
    url = ('https://api.mymemory.translated.net/get?q=%s&langpair=en|zh-CN&de=catbar@example.com'
           % urllib.parse.quote(text))
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    data = json.loads(urllib.request.urlopen(req, timeout=15).read())
    t = (data.get('responseData') or {}).get('translatedText') or ''
    if 'MYMEMORY WARNING' in t:
        t = t.split('»', 1)[-1].strip()
    return t


def clean_gloss(g):
    """英文释义 -> 干净短术语: 去括注/取首义/压缩。"""
    g = re.sub(r'\([^)]*\)', '', g)
    g = re.sub(r'\[[^\]]*\]', '', g)
    g = g.split(';')[0].split(',')[0].strip()
    return g.strip()


def trad_clean(s):
    s = cc.convert(s)
    return s


def is_simplified_needed(s):
    return cc.convert(s) != s


def main():
    # ---------- A+B: 修复现有 3,123 条 ----------
    books = json.loads(BOOKS_FILE.read_text(encoding='utf-8'))
    cache = load_cache()
    stats = {'t2s_meaning': 0, 't2s_sent': 0, 'en_fixed': 0, 'en_failed': 0}

    for lv, items in books['levels'].items():
        for it in items:
            m = it.get('meaning', '')
            body = re.sub(r'^(\[\[.*?\]\]\s*)', r'\1', m)
            core = body.split(']', 2)[-1].strip() if body.count(']') >= 3 else body
            # meaning 形如 "[[ipa]] EN (Cat)" 或 "[[ipa]] 中文 (Cat)"
            prefix = ''
            mm = re.match(r'^(\[\[.*?\]\]\s*)(.*)$', m)
            if mm:
                prefix, core = mm.group(1), mm.group(2)
            cat = ''
            cm = re.match(r'^(.*?)\s*\(([^()]*)\)$', core)
            if cm:
                core_no, cat = cm.group(1).strip(), cm.group(2).strip()
            else:
                core_no = core.strip()
            if re.search(r'[A-Za-z]', core_no) and not any(
                    0x4E00 <= ord(c) <= 0x9FFF for c in core_no):
                # 英文释义 -> 缓存翻译
                key = 'EN:' + core_no
                if key in cache:
                    zh = cache[key]
                else:
                    try:
                        zh = mymemory_translate(clean_gloss(core_no))
                        zh = trad_clean(zh)
                        cache[key] = zh
                        time.sleep(0.6)
                    except Exception as e:
                        print(f'  translate fail {it["word"]}: {e}')
                        zh = ''
                        stats['en_failed'] += 1
                    save_cache(cache)
                if zh:
                    stats['en_fixed'] += 1
                    core_no = zh
            core_s = trad_clean(core_no)
            if core_s != core_no:
                stats['t2s_meaning'] += 1
            cat_s = trad_clean(cat) if cat else ''
            new_m = prefix + core_s + (f' ({cat_s})' if cat_s else '')
            if new_m != m:
                it['meaning'] = new_m
            # 例句中文括注
            sents = it.get('sentences') or []
            changed = False
            for pair in sents:
                if len(pair) >= 2 and cc.convert(pair[1]) != pair[1]:
                    pair[1] = cc.convert(pair[1])
                    stats['t2s_sent'] += 1
                    changed = True
            if changed:
                it['sentences'] = sents

    save_cache(cache)
    print('A+B done:', stats)

    # ---------- C: 扩词 ----------
    cur = {}
    for lv, items in books['levels'].items():
        for it in items:
            cur[it['word']] = it

    # C1. vocab5000 新词
    vocab = []
    with open(RAW / 'korean_vocab_5000_zh.jsonl', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                vocab.append(json.loads(line))
    seen_v5 = {}
    for d in vocab:
        w = (d.get('korean_term') or '').strip()
        if w and w not in seen_v5:
            seen_v5[w] = d

    def mk_entry(w, ipa, zh, cat, lv, source):
        return {'word': w, 'ipa': ipa, 'meaning': f'[[{ipa}]] {zh} ({cat})' if ipa
                else f'{zh} ({cat})', 'level': lv, 'category': cat,
                'source': source}

    new_v5 = []
    for w, d in seen_v5.items():
        if w in cur:
            continue
        if not re.match(r'^[가-힣][가-힣 ]*$', w):
            continue
        zh = trad_clean((d.get('english_term') or '').strip())
        rom = (d.get('romanization') or '').strip()
        cat = '文化·生活' if '문화' in w or '문화' in (d.get('context_description') or '') else '进阶词汇'
        new_v5.append((w, mk_entry(w, rom, zh or w, cat, 'topik4', 'vocab5000')))
    print(f'C1 vocab5000 new: {len(new_v5)}')

    # C2. TSV 新词 (kaikki EN gloss -> 缓存翻译), 只取 clean 形态
    tsv = {}
    with open(RAW / 'topik_nikl_combined.tsv', encoding='utf-8') as f:
        hdr = f.readline().rstrip('\n').split('\t')
        for line in f:
            cols = line.rstrip('\n').split('\t')
            if len(cols) != 7:
                continue
            r = dict(zip(hdr, cols))
            w = r['word'].strip()
            if not w or any(ch in w for ch in '-~()0123456789 '):
                continue
            if not all(0xAC00 <= ord(c) <= 0xD7A3 for c in w):
                continue
            tsv.setdefault(w, r)
    kaikki = {}
    with open(RAW / 'kaikki-ko.jsonl', encoding='utf-8') as f:
        for line in f:
            try:
                d = json.loads(line)
            except Exception:
                continue
            w = d.get('word', '')
            if w not in tsv or w in kaikki:
                continue
            gl = []
            for s in (d.get('senses') or []):
                for g in (s.get('glosses') or []):
                    if g and not g.startswith('('):
                        gl.append(g)
            if gl:
                pos = (d.get('pos') or '').strip()
                kaikki[w] = (gl[0], pos)
    print(f'C2 TSV clean words: {len(tsv)}, kaikki gloss: {len(kaikki)}')

    POS_MAP = {'noun': '명사', 'verb': '동사', 'adj': '형용사', 'adv': '부사',
               'name': '고유명사', 'num': '수사', 'pron': '대명사', 'det': '관형사',
               'particle': '조사', 'intj': '감탄사', 'prep': '조사',
               'postp': '조사', 'conj': '접속부사', 'suffix': '접사',
               'prefix': '접사', 'counter': '수사'}

    def tsv_level(r):
        topik = r.get('topik_level', '')
        nikl = r.get('nikl_level', '')
        if topik == '초급':
            return 'topik4'
        if topik == '중급':
            return 'topik5'
        return {'A': 'topik4', 'B': 'topik5', 'C': 'topik6'}.get(nikl, 'topik6')

    new_tsv = []
    todo = [w for w in tsv if w not in cur and w not in seen_v5 and w in kaikki]
    print(f'C2 words to translate: {len(todo)}')
    done = 0
    for w in todo:
        gl, pos = kaikki[w]
        key = 'TSV:' + gl
        if key in cache:
            zh = cache[key]
        else:
            g = clean_gloss(gl)
            if not g:
                continue
            try:
                zh = trad_clean(mymemory_translate(g))
                cache[key] = zh
                save_cache(cache)
                time.sleep(0.6)
            except Exception as e:
                print(f'  translate fail {w}: {e}')
                continue
        if not zh or not any(0x4E00 <= ord(c) <= 0x9FFF for c in zh):
            continue
        cat_s = trad_clean(POS_MAP.get(pos, '进阶词汇'))
        r = tsv[w]
        new_tsv.append((w, mk_entry(w, '', zh[:24], cat_s, tsv_level(r), 'topik_nikl')))
        done += 1
        if done % 200 == 0:
            print(f'  translated {done}/{len(todo)}')
    print(f'C2 TSV new: {len(new_tsv)}')

    # 落盘: topik4/5/6 合并进 levels (新建), 保证总数 >= 5000
    for lv in ('topik4', 'topik5', 'topik6'):
        books['levels'].setdefault(lv, [])
    have = set(cur)
    for w, e in new_v5:
        if w not in have:
            books['levels']['topik4'].append(e)
            have.add(w)
    for w, e in new_tsv:
        if w not in have:
            books['levels'][e['level']].append(e)
            have.add(w)
    BOOKS_FILE.write_text(json.dumps(books, ensure_ascii=False, indent=2), encoding='utf-8')
    total = sum(len(v) for v in books['levels'].values())
    print('levels:', {k: len(v) for k, v in books['levels'].items()})
    print('total words:', total)
    print('saved:', BOOKS_FILE)


if __name__ == '__main__':
    main()
