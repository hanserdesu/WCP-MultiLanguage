# -*- coding: utf-8 -*-
"""用 Jisho API 为缺读音的词条补假名读音 (断点续传)。

产出: data/readings_jisho.json  word -> reading
"""
import argparse
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'output'
RF = ROOT / 'data' / 'readings_jisho.json'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'

import re
KANA_RE = re.compile(r'^[\u3040-\u30ffー・]+$')


def load():
    if RF.exists():
        return json.loads(RF.read_text(encoding='utf-8'))
    return {}


def save(st):
    tmp = RF.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(st, ensure_ascii=False), encoding='utf-8')
    tmp.replace(RF)


def jisho(word):
    url = 'https://jisho.org/api/v1/search/words?keyword=' + urllib.parse.quote(word)
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read().decode('utf-8'))
    for d in (data.get('data') or [])[:3]:
        if d.get('word') == word and d.get('reading'):
            return d['reading']
    for d in (data.get('data') or [])[:3]:
        if d.get('reading'):
            return d['reading']
    return ''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=60)
    args = ap.parse_args()
    data = json.loads((OUT / 'jlpt_books.json').read_text(encoding='utf-8'))
    state = load()
    todo = []
    for lv in ['n5', 'n4', 'n3', 'n2', 'n1']:
        for r in data['levels'][lv]:
            w = r['word']
            if w in state:
                continue
            if '/' in w:
                state[w] = ''  # 变体词, Jisho 无法匹配, 标记跳过
                continue
            if not r['reading'] and not KANA_RE.match(w):
                todo.append(w)
    todo = todo[:args.limit]
    print(f'待查读音 {len(todo)} (已缓存 {len(state)})')
    ok = 0
    for i, w in enumerate(todo):
        try:
            rd = jisho(w)
            if rd and rd != w:
                state[w] = rd
                ok += 1
            else:
                state[w] = ''
        except Exception:
            state[w] = ''
            time.sleep(2)
        if (i + 1) % 20 == 0:
            save(state)
        time.sleep(0.35)
    save(state)
    print(f'获得读音 {ok} 个, 缓存 {len(state)}')


if __name__ == '__main__':
    main()
