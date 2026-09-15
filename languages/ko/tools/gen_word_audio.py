# -*- coding: utf-8 -*-
"""批量生成韩语单词发音 MP3 -> ko_word_audio/<word>.mp3

采用 edge-tts (ko-KR-SunHiNeural 女声首选标准首尔音)。
断点续传 (manifest) + 异步并发 (Semaphore 12) + 自动重试。
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
from audio_paths_ko import word_audio_dir

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
VOCAB_DIR = word_audio_dir()
MANIFEST = ROOT / 'output' / 'audio_manifest_ko.json'

VOICE = 'ko-KR-SunHiNeural'
CONCURRENCY = 12
TIMEOUT = 30
INVALID_FN = re.compile(r'[\/:*?"<>|]')

_sem = None


def load_manifest():
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text(encoding='utf-8'))
    return {'done': {}, 'failed': {}}


def save_manifest(m):
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    tmp = MANIFEST.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(MANIFEST)


def load_word_list():
    """从 korean_books.json 或 sentences_master.json 获取单词列表。"""
    books_file = ROOT / 'output' / 'korean_books.json'
    master_file = ROOT / 'data' / 'translations' / 'sentences_master.json'
    words = []
    seen = set()

    if books_file.exists():
        data = json.loads(books_file.read_text(encoding='utf-8'))
        for lv in ('topik1', 'topik2', 'topik3', 'topik4', 'topik5', 'topik6'):
            if lv in data.get('levels', {}):
                for r in data['levels'][lv]:
                    w = r.get('word', '').strip()
                    if w and w not in seen and not INVALID_FN.search(w):
                        seen.add(w)
                        words.append(w)

    if master_file.exists():
        data = json.loads(master_file.read_text(encoding='utf-8'))
        for w in data.keys():
            w = w.strip()
            if w and w not in seen and not INVALID_FN.search(w):
                seen.add(w)
                words.append(w)

    return words


TMP_TAG = f'.{os.getpid()}.tmp.mp3'


async def gen_one(text, dest):
    async with _sem:
        await asyncio.sleep(random.uniform(0.05, 0.2))
        tmp = dest.with_name(dest.name + TMP_TAG)
        try:
            c = edge_tts.Communicate(text, VOICE)
            await asyncio.wait_for(c.save(str(tmp)), TIMEOUT)
            if tmp.stat().st_size < 500:
                raise ValueError('audio file too small')
            os.replace(str(tmp), str(dest))
            return 'ok'
        except Exception as e:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass
            return str(e)


async def main():
    global _sem
    parser = argparse.ArgumentParser(description='Generate Korean word audio')
    parser.add_argument('--limit', type=int, default=0, help='Limit number of words')
    parser.add_argument('--retry-failed', action='store_true', help='Retry previously failed')
    args = parser.parse_args()

    words = load_word_list()
    if not words:
        print('暂无待生成的韩语单词列表 (korean_books.json 或 sentences_master.json 为空)')
        return

    manifest = load_manifest()
    done = manifest.get('done', {})
    failed = manifest.get('failed', {})

    todo = []
    for w in words:
        dest = VOCAB_DIR / f'{w}.mp3'
        if dest.exists() and dest.stat().st_size >= 500:
            done[w] = True
            continue
        if w in failed and not args.retry_failed:
            continue
        todo.append(w)

    if args.limit > 0:
        todo = todo[:args.limit]

    print(f'总词数: {len(words)}, 已就绪: {len(done)}, 待生成: {len(todo)} -> {VOCAB_DIR}')
    if not todo:
        print('全部单词音频已完成！')
        return

    _sem = asyncio.Semaphore(CONCURRENCY)
    t0 = time.time()
    success_count = 0
    fail_count = 0

    BATCH = 30
    for i in range(0, len(todo), BATCH):
        batch = todo[i:i + BATCH]
        tasks = []
        for w in batch:
            dest = VOCAB_DIR / f'{w}.mp3'
            tasks.append((w, gen_one(w, dest)))

        results = await asyncio.gather(*[t[1] for t in tasks])
        for (w, _), res in zip(tasks, results):
            if res == 'ok':
                done[w] = True
                failed.pop(w, None)
                success_count += 1
            else:
                failed[w] = res
                fail_count += 1

        save_manifest(manifest)
        done_total = success_count + fail_count
        rate = done_total / max(time.time() - t0, 0.1)
        remain = (len(todo) - done_total) / max(rate, 0.1)
        print(f'进度: {done_total}/{len(todo)} | 成功: {success_count}, 失败: {fail_count} | 速度: {rate:.1f}词/s, 预估剩余: {remain:.0f}s', flush=True)

    print(f'单词音频生成完毕: 成功 {success_count}, 失败 {fail_count}')


if __name__ == '__main__':
    asyncio.run(main())
