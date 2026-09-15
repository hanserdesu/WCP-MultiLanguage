# -*- coding: utf-8 -*-
"""批量生成日语单词发音 MP3 -> 日语 pack 的 word 音频目录。

宿主按 `<单词文本>.mp3` / `.wav` 在
%USERPROFILE%\\AppData\\LocalLow\\WCP\\packs\\ja\\audio\\word 查找本地音频。
找不到才会回退内置 AI(英语向)TTS。日语词务必生成本地音频。

特性: 断点续传(manifest), 并发限流, 失败重试, 分批(--limit)。
用法:
  py gen_audio.py --limit 400          # 本轮最多生成 400 个
  py gen_audio.py --retry-failed      # 重试上次失败的
"""
import argparse
import asyncio
import json
import os
import random
import re
import sys
import time
from pathlib import Path

import edge_tts

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'output'
VOCAB_DIR = (Path.home() / 'AppData' / 'LocalLow' / 'WCP' /
             'packs' / 'ja' / 'audio' / 'word')
MANIFEST = OUT / 'audio_manifest.json'

VOICE = 'ja-JP-NanamiNeural'
CONCURRENCY = 8
TIMEOUT = 25

INVALID_FN = re.compile(r'[\\/:*?"<>|]')

_sem = None


def load_manifest():
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text(encoding='utf-8'))
    return {'done': {}, 'failed': {}}


def save_manifest(m):
    tmp = MANIFEST.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(m, ensure_ascii=False), encoding='utf-8')
    tmp.replace(MANIFEST)


def word_list():
    data = json.loads((OUT / 'jlpt_books.json').read_text(encoding='utf-8'))
    order = {'n5': 0, 'n4': 1, 'n3': 2, 'n2': 3, 'n1': 4}
    seen, out = set(), []
    for lv in sorted(order):
        for r in data['levels'][lv]:
            w = r['word'].strip()
            if not w or w in seen:
                continue
            if INVALID_FN.search(w):
                continue  # 无法作为文件名(如 いい/よい), 游戏会回退AI
            seen.add(w)
            out.append(w)
    # 主题词书 ( JLPT 之后追加, 共用同一 manifest )
    themed = OUT / 'themed_books.json'
    if themed.exists():
        tb = json.loads(themed.read_text(encoding='utf-8'))
        for rows in tb['themes'].values():
            for r in rows:
                w = r['word'].strip()
                if not w or w in seen or INVALID_FN.search(w):
                    continue
                if '～' in w or '~' in w:
                    continue  # 句型类条目 TTS 读不了
                seen.add(w)
                out.append(w)
    return out


TMP_TAG = f'.{os.getpid()}.tmp.mp3'


async def gen_one(word, dest):
    async with _sem:
        await asyncio.sleep(random.uniform(0.05, 0.35))
        tmp = dest.with_name(dest.stem + TMP_TAG)
        try:
            c = edge_tts.Communicate(word, VOICE)
            await asyncio.wait_for(c.save(str(tmp)), TIMEOUT)
            if tmp.stat().st_size < 1000:
                raise ValueError('audio too small')
            os.replace(str(tmp), str(dest))
            return 'ok'
        except Exception as e:
            try:
                if tmp.exists():
                    tmp.unlink(missing_ok=True)
            except OSError:
                pass
            return f'err:{type(e).__name__}:{e}'[:120]


async def run(words, manifest, max_n):
    global _sem
    _sem = asyncio.Semaphore(CONCURRENCY)
    VOCAB_DIR.mkdir(parents=True, exist_ok=True)
    todo = []
    for w in words:
        if w in manifest['done']:
            continue
        dest = VOCAB_DIR / f'{w}.mp3'
        if dest.exists() and dest.stat().st_size > 1000:
            manifest['done'][w] = 'existed'
            continue
        todo.append(w)
        if len(todo) >= max_n:
            break
    print(f'待生成 {len(todo)} 个', flush=True)
    ok = fail = 0
    start = time.time()
    for i, w in enumerate(todo):
        dest = VOCAB_DIR / f'{w}.mp3'
        res = await gen_one(w, dest)
        if res == 'ok':
            manifest['done'][w] = 'generated'
            ok += 1
        else:
            manifest['failed'][w] = res
            fail += 1
        if (i + 1) % 25 == 0 or i == len(todo) - 1:
            save_manifest(manifest)
            rate = (i + 1) / max(time.time() - start, 1)
            print(f'  {i+1}/{len(todo)} ok={ok} fail={fail} '
                  f'{rate:.1f}词/秒', flush=True)
    save_manifest(manifest)
    return ok, fail


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=500)
    ap.add_argument('--retry-failed', action='store_true')
    args = ap.parse_args()

    lock = MANIFEST.parent / 'gen_audio.lock'
    if lock.exists() and time.time() - lock.stat().st_mtime < 1800:
        print('另一音频任务运行中, 跳过')
        return
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(str(time.time()), encoding='utf-8')
    try:
        manifest = load_manifest()
        if args.retry_failed:
            failed = list(manifest['failed'])
            manifest['failed'] = {}
            for w in failed:
                manifest['done'].pop(w, None)
        words = word_list()
        print(f'词表总数 {len(words)}, 已完成 {len(manifest["done"])}')

        ok, fail = asyncio.run(run(words, manifest, args.limit))
        print(f'本轮完成: ok={ok} fail={fail}, '
              f'总进度 {len(manifest["done"])}/{len(words)}')
    finally:
        try:
            lock.unlink()
        except OSError:
            pass
    sys.exit(0)


if __name__ == '__main__':
    main()
