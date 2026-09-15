# -*- coding: utf-8 -*-
"""用 Google 翻译(gtx 免费端点)把剩余英文释义译为中文。

产出: data/translations/gtx_zh.json  (word -> 中文释义)
特性: 断点续传、限流重试、分批 --limit。
"""
import argparse
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'output'
TDIR = ROOT / 'data' / 'translations'
TFILE = TDIR / 'gtx_zh.json'

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'


def load_state():
    if TFILE.exists():
        return json.loads(TFILE.read_text(encoding='utf-8'))
    return {}


def save_state(st):
    TDIR.mkdir(parents=True, exist_ok=True)
    tmp = TFILE.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(st, ensure_ascii=False), encoding='utf-8')
    tmp.replace(TFILE)


def gtx(text, sl='en', tl='zh-CN'):
    q = urllib.parse.quote(text)
    url = (f'https://translate.googleapis.com/translate_a/single'
           f'?client=gtx&sl={sl}&tl={tl}&dt=t&q={q}')
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read().decode('utf-8'))
    parts = [seg[0] for seg in data[0] if seg and seg[0]]
    return ''.join(parts).strip()


def clean_zh(s):
    s = re.sub(r'\s+', ' ', s).strip()
    s = s.strip('"“”「」')
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=800)
    ap.add_argument('--sleep', type=float, default=0.25)
    args = ap.parse_args()

    lock = TDIR / 'translate.lock'
    if lock.exists() and time.time() - lock.stat().st_mtime < 1800:
        print('另一翻译任务运行中, 跳过')
        return
    TDIR.mkdir(parents=True, exist_ok=True)
    lock.write_text(str(time.time()), encoding='utf-8')
    try:
        _work(args)
    finally:
        try:
            lock.unlink()
        except OSError:
            pass


def _work(args):
    data = json.loads((OUT / 'jlpt_books.json').read_text(encoding='utf-8'))
    state = load_state()

    # word -> (meaning_en, 已有中文?)
    todo = []
    seen = set()
    for lv in ['n5', 'n4', 'n3', 'n2', 'n1']:
        for r in data['levels'][lv]:
            w = r['word']
            if w in seen:
                continue
            seen.add(w)
            en = r['meaning_en']
            if not en or r['meaning_zh']:
                continue
            todo.append((w, en))

    todo = [(w, en) for w, en in todo if state.get(w, {}).get('zh', '') == '']
    print(f'待翻译 {len(todo)} (已译 {len(state)})')
    batch = todo[:args.limit]

    ok = fail = 0
    for i, (w, en) in enumerate(batch):
        src = en if len(en) <= 400 else en[:400]
        try:
            zh = clean_zh(gtx(src))
            if zh:
                state[w] = {'zh': zh, 'en': en}
                ok += 1
            else:
                fail += 1
        except Exception as e:
            fail += 1
            state.setdefault(w, {'zh': '', 'en': en, 'err': 0})
            state[w]['err'] = state[w].get('err', 0) + 1
        if (i + 1) % 50 == 0:
            save_state(state)
            print(f'  {i+1}/{len(batch)} ok={ok} fail={fail}', flush=True)
        time.sleep(args.sleep)
    save_state(state)
    print(f'完成: ok={ok} fail={fail}, 总计 {len(state)}')


if __name__ == '__main__':
    main()
