# -*- coding: utf-8 -*-
"""批量生成韩语例句发音 MP3 -> ko_sentence_audio/<md5(ko)>.mp3

数据源: data/translations/sentences_master.json {word: [[ko_sent, zh_trans], ...]}
文件名: md5(ko_sent.encode('utf-8')).hexdigest() + '.mp3'
与 BepInEx 插件 SentenceAudioKoMod 的取音逻辑严格一致。
断点续传 + 异步并发 + 3次重试。
用法: python tools/gen_sentence_audio.py [--limit N]
"""
import argparse
import asyncio
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import edge_tts
from audio_paths_ko import sentence_audio_dir

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
MASTER = ROOT / 'data' / 'translations' / 'sentences_master.json'
OUT_DIR = sentence_audio_dir()

VOICE = 'ko-KR-SunHiNeural'
CONCURRENCY = 12


def fname(text: str) -> str:
    return hashlib.md5(text.encode('utf-8')).hexdigest() + '.mp3'


async def worker(sem, text, ok, fail, proxy=None):
    async with sem:
        path = OUT_DIR / fname(text)
        for attempt in range(3):
            try:
                tts = edge_tts.Communicate(text, VOICE, proxy=proxy)
                await tts.save(str(path))
                if path.stat().st_size > 500:
                    ok.add(text)
                    return
            except Exception:
                await asyncio.sleep(1.0 * (attempt + 1))
        fail.add(text)


async def main():
    parser = argparse.ArgumentParser(description='Generate Korean sentence audio')
    parser.add_argument('--limit', type=int, default=0, help='Limit number of sentences')
    parser.add_argument('--proxy', default='', help='aiohttp proxy for edge-tts, e.g. http://127.0.0.1:7897')
    args = parser.parse_args()

    if not MASTER.exists():
        print(f'未找到例句数据源: {MASTER}')
        return

    master = json.loads(MASTER.read_text(encoding='utf-8'))
    seen = set()
    todo = []
    for items in master.values():
        for item in items:
            if isinstance(item, list) and len(item) >= 1:
                ko = item[0].strip()
                if not ko or ko in seen:
                    continue
                seen.add(ko)
                p = OUT_DIR / fname(ko)
                if not (p.exists() and p.stat().st_size > 500):
                    todo.append(ko)

    if args.limit > 0:
        todo = todo[:args.limit]

    print(f'唯一例句总数: {len(seen)}, 待生成: {len(todo)} -> {OUT_DIR}')
    if not todo:
        print('全部例句音频已生成完毕！')
        return

    ok, fail = set(), set()
    sem = asyncio.Semaphore(CONCURRENCY)
    proxy = args.proxy or None
    t0 = time.time()
    done = 0
    BATCH = 30

    for i in range(0, len(todo), BATCH):
        batch = todo[i:i + BATCH]
        tasks = [worker(sem, ko, ok, fail, proxy) for ko in batch]
        await asyncio.gather(*tasks)
        done += len(batch)
        rate = done / max(time.time() - t0, 0.1)
        remain = (len(todo) - done) / max(rate, 0.1)
        print(f'进度: {done}/{len(todo)} | 成功: {len(ok)}, 失败: {len(fail)} | 速度: {rate:.1f}句/s, 预估剩余: {remain:.0f}s', flush=True)

    print(f'例句音频生成完成: 成功 {len(ok)}, 失败 {len(fail)}')


if __name__ == '__main__':
    asyncio.run(main())
