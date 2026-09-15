# -*- coding: utf-8 -*-
"""批量生成俄语单词发音 MP3 -> 游戏 wcp/ru_word_audio 私有目录。

RuWordListMod 只从 `%USERPROFILE%\\AppData\\LocalLow\\WCP\\wcp\\ru_word_audio`
读取；不写入游戏原生共享 vocabulary，避免同形词污染其它语言。
断点续传(manifest) + 并发限流 + 失败重试。
用法: python tools/gen_word_audio.py [--limit N] [--retry-failed]
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

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
VOCAB_DIR = Path.home() / 'AppData' / 'LocalLow' / 'WCP' / 'wcp' / 'ru_word_audio'
MANIFEST = ROOT / 'output' / 'audio_manifest_ru.json'

VOICE = 'ru-RU-SvetlanaNeural'
CONCURRENCY = 12
TIMEOUT = 30
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
    data = json.loads((ROOT / 'output' / 'russian_books.json').read_text(
        encoding='utf-8'))
    order = {'a1': 0, 'a2': 1, 'b1': 2, 'b2': 3}
    seen, out = set(), []
    for lv in sorted(order):
        for r in data['levels'][lv]:
            w = r['word'].strip()
            if not w or w in seen:
                continue
            if INVALID_FN.search(w):
                continue
            seen.add(w)
            out.append(w)
    return out


TMP_TAG = f'.{os.getpid()}.tmp.mp3'


async def gen_one(text, dest):
    async with _sem:
        await asyncio.sleep(random.uniform(0.05, 0.3))
        tmp = dest.with_name(dest.name + TMP_TAG)
        try:
            c = edge_tts.Communicate(text, VOICE)
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
        if (i + 1) % 50 == 0 or i == len(todo) - 1:
            save_manifest(manifest)
            rate = (i + 1) / max(time.time() - start, 1)
            print(f'  {i+1}/{len(todo)} ok={ok} fail={fail} '
                  f'{rate:.1f}词/秒', flush=True)
    save_manifest(manifest)
    return ok, fail


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=100000)
    ap.add_argument('--retry-failed', action='store_true')
    args = ap.parse_args()

    lock = MANIFEST.parent / 'gen_word_audio_ru.lock'
    if lock.exists() and time.time() - lock.stat().st_mtime < 1800:
        print('另一单词音频任务运行中, 跳过')
        return
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
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


if __name__ == '__main__':
    main()
