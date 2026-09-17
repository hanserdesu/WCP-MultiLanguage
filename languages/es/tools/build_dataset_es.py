# -*- coding: utf-8 -*-
"""Spanish TEM-8 / CEFR C1-C2 wordlist build pipeline."""
import json, re, sys, time, urllib.parse, urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'; RAW = DATA / 'raw'; OUT = ROOT / 'output'
TRANSLATIONS = DATA / 'translations'
OUT.mkdir(parents=True, exist_ok=True); TRANSLATIONS.mkdir(parents=True, exist_ok=True)
TOTAL_TARGET = 8600
TIER_BOUNDS = (2000, 4500, 7500)

def load_freq_words():
    words = []
    with (RAW / 'es_50k.txt').open(encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 2:
                words.append(parts[0].strip().lower())
    return words

def load_oxford3000():
    ox = set(); p = RAW / 'oxford3000.txt'
    if p.exists():
        with p.open(encoding='utf-8') as f:
            for line in f:
                w = line.strip().lower()
                if w: ox.add(w)
    return ox

def clean_gloss(gloss):
    if not gloss: return ''
    s = gloss.strip()
    s = re.sub(r'\([^)]*\)', '', s)
    s = re.split(r'[,;]', s)[0].strip()
    s = re.sub(r'^to\s+', '', s, flags=re.I)
    return s

def pick_pos(poss):
    priority = ['noun', 'verb', 'adj', 'adv', 'pron', 'det', 'prep', 'num', 'conj', 'intj']
    for p in priority:
        if p in poss: return p
    return next(iter(poss))

POS_TO_ZH = {'noun': '名', 'verb': '动', 'adj': '形', 'adv': '副', 'pron': '代', 'prep': '介', 'det': '限定', 'num': '数', 'conj': '连', 'intj': '叹'}

# Manual corrections for top high-frequency function words.
# word -> (pos, Chinese, IPA). Applied AFTER kaikki and BEFORE Google Translate.
ES_MANUAL = {
    'de': ('prep', '从；的', 'de'),
    'que': ('conj', '关系代词/连接词', 'ke'),
    'no': ('adv', '不，不是', 'no'),
    'la': ('det', '定冠词[阴性单数]', 'la'),
    'el': ('det', '定冠词[阳性单数]', 'el'),
    'un': ('det', '一个[阳性]', 'un'),
    'una': ('det', '一个[阴性]', 'una'),
    'por': ('prep', '通过；因为；为', 'por'),
    'para': ('prep', '为了；给', 'para'),
    'me': ('pron', '我[宾格]', 'me'),
    'te': ('pron', '你[宾格]', 'te'),
    'se': ('pron', '自己', 'se'),
    'lo': ('pron', '它；这件事', 'lo'),
    'le': ('pron', '他/她/您[与格]', 'le'),
    'les': ('pron', '他们/您们[与格]', 'les'),
    'si': ('conj', '如果；是否', 'si'),
    'mi': ('det', '我的', 'mi'),
    'tu': ('det', '你的', 'tu'),
    'su': ('det', '他/她/它的', 'su'),
    'yo': ('pron', '我', 'ʒo'),
    'este': ('det', '这个', 'este'),
    'esta': ('det', '这个[阴性]', 'esta'),
    'eso': ('pron', '那个', 'eso'),
    'esto': ('pron', '这', 'esto'),
    'hay': ('verb', '有[存在]', 'aj'),
    'gracias': ('intj', '谢谢', 'grasjas'),
    'hola': ('intj', '你好', 'ola'),
    'pero': ('conj', '但是', 'pero'),
    'como': ('adv', '怎样；作为', 'komo'),
    'ya': ('adv', '已经；现在', 'ja'),
    'bien': ('adv', '好；很', 'bjen'),
    'cuando': ('adv', '什么时候', 'kwando'),
    'ahora': ('adv', '现在', 'aora'),
    'muy': ('adv', '非常', 'muj'),
    'todo': ('det', '所有；全部', 'todo'),
    'nada': ('pron', '什么也没有', 'nada'),
    'algo': ('pron', '某事；某物', 'algo'),
}


CACHE_FILE = DATA / 'zh_cache.json'

def load_cache():
    if CACHE_FILE.exists():
        try: return json.loads(CACHE_FILE.read_text(encoding='utf-8'))
        except Exception: return {}
    return {}

def save_cache(cache):
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False), encoding='utf-8')

def translate_batch(words, retries=5):
    cache = load_cache()
    results = []
    idx_map = {}
    to_fetch = []
    for i, w in enumerate(words):
        if w in cache and cache[w]:
            results.append(cache[w])
        else:
            idx_map[len(results)] = w
            results.append(None)
            to_fetch.append(w)
    print(f'cache hit: {len(words) - len(to_fetch)}, to fetch: {len(to_fetch)}')
    if to_fetch:
        time.sleep(30)
    for j in range(0, len(to_fetch), 50):
        chunk = to_fetch[j:j + 50]
        q = chr(10).join(chunk)
        ok = False
        for attempt in range(retries):
            try:
                url = ('https://translate.googleapis.com/translate_a/single'
                       '?client=gtx&sl=es&tl=zh-CN&dt=t&q=' + urllib.parse.quote(q))
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                resp = urllib.request.urlopen(req, timeout=15)
                data = json.loads(resp.read().decode('utf-8'))
                text = ''.join(seg[0] for seg in data[0] if seg[0])
                lines2 = text.split(chr(10))
                if len(lines2) == len(chunk):
                    for k, w in enumerate(chunk):
                        cache[w] = lines2[k]
                        for ix, v in idx_map.items():
                            if v == w: results[ix] = lines2[k]
                    ok = True
                    save_cache(cache)
                    print(f'  batch {j}: {len(chunk)} translated')
                    break
            except Exception as e:
                wait = 30 * (attempt + 1)
                print(f'  batch {j} attempt {attempt+1} err: {str(e)[:60]}; wait {wait}s')
                time.sleep(wait)
        if not ok: print(f'  batch {j} all retries failed')
        time.sleep(2.5)
    return [r if r else '' for r in results]
def main():
    print('=== Spanish TEM-8 build pipeline v1.0 ===')
    lemma_p = DATA / 'lemma_es.json'
    if not lemma_p.exists(): print(f'missing {lemma_p}'); sys.exit(1)
    d = json.loads(lemma_p.read_text(encoding='utf-8'))
    lemmas = d['lemmas']; form_map = d['form_map']
    print(f'lemmas: {len(lemmas)}, form_map: {len(form_map)}')
    freq = load_freq_words(); oxford = load_oxford3000()
    print(f'freq: {len(freq)}, oxford3000: {len(oxford)}')
    seen = set(); candidates = []
    for w in freq:
        if w in seen: continue
        src = w if w in lemmas else form_map.get(w, '')
        if not src or src not in lemmas or src in seen: continue
        seen.add(src)
        candidates.append((src, lemmas[src]))
        if len(candidates) >= TOTAL_TARGET: break
    print(f'candidates: {len(candidates)}')
    manual_entries = []
    gt_entries = []
    for w, poss in candidates:
        pos = pick_pos(poss)
        gls, ipa = poss[pos]
        g = clean_gloss(gls[0]) if gls else ''
        if w in ES_MANUAL:
            pos_m, zh_m, ipa_m = ES_MANUAL[w]
            manual_entries.append({'word': w, 'pos': pos_m, 'ipa': ipa_m, 'gloss': '', 'glosses': [], 'zh': zh_m})
        else:
            gt_entries.append({'word': w, 'pos': pos, 'ipa': ipa, 'gloss': g, 'glosses': gls[:3]})
    to_translate = [e['word'] for e in gt_entries]
    print(f'manual: {len(manual_entries)}, to translate: {len(to_translate)}')
    print('translating...')
    t0 = time.time()
    zh_list = translate_batch(to_translate)
    print(f'translated: {len(zh_list)} in {time.time() - t0:.1f}s')
    for e, zh in zip(gt_entries, zh_list):
        e['zh'] = zh.strip()
    entries = manual_entries + gt_entries
    # Restore original frequency order using the original candidates order
    order = {w: i for i, (w, _) in enumerate(candidates)}
    entries.sort(key=lambda e: order.get(e['word'], 10**9))
    out = {}
    for i, e in enumerate(entries):
        if i < TIER_BOUNDS[0]: level = 'tem4_a1a2'
        elif i < TIER_BOUNDS[1]: level = 'tem4_b1'
        elif i < TIER_BOUNDS[2]: level = 'tem8_b2'
        else: level = 'tem8_c1'
        e['level'] = level; e['rank'] = i + 1
        pos_zh = POS_TO_ZH.get(e['pos'], '?')
        ipa = e.get('ipa', '').strip('/')
        zh_v = e.get('zh', '') or e.get('word', '')
        e['meaning'] = f'[{ipa}] {zh_v}<{pos_zh}>' if ipa else f'{zh_v}<{pos_zh}>'
        out.setdefault(level, []).append(e)
    for lv in ['tem4_a1a2', 'tem4_b1', 'tem8_b2', 'tem8_c1']: print(f'  {lv}: {len(out.get(lv, []))}')
    total = sum(len(v) for v in out.values())
    print(f'  total: {total}')
    payload = {'levels': out, 'meta': {'total': total, 'generated_by': 'build_dataset_es.py'}}
    books_p = OUT / 'spanish_books.json'
    books_p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'saved: {books_p}')

if __name__ == '__main__':
    main()
