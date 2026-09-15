# -*- coding: utf-8 -*-
"""批量生成例句日语语音 -> 日语 pack/audio/sentence/<md5>.mp3

数据源: data/translations/sentences_master.json {word: [[ja, zh], ...]}
文件名: md5(ja.encode('utf-8')).hexdigest()  — 与 BepInEx 插件
        SentenceAudioMod 的取音逻辑严格一致 (小写hex)。
特性: 断点续传 (manifest), 并发限流, 失败重试, 定期落盘。
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

sys.stdout.reconfigure(encoding='utf-8')
import edge_tts

ROOT = Path(__file__).resolve().parent.parent
MASTER = ROOT / 'data' / 'translations' / 'sentences_master.json'
OUT_DIR = Path(os.path.expandvars(
    r'%USERPROFILE%\AppData\LocalLow\WCP\packs\ja\audio\sentence'))
MANIFEST = OUT_DIR / 'manifest.json'
VOICE = 'ja-JP-NanamiNeural'
CONCURRENCY = 12


def fname(ja: str) -> str:
    return hashlib.md5(ja.encode('utf-8')).hexdigest() + '.mp3'


async def worker(sem, ja, ok, fail):
    async with sem:
        path = OUT_DIR / fname(ja)
        for attempt in range(3):
            try:
                tts = edge_tts.Communicate(ja, VOICE)
                await tts.save(str(path))
                if path.stat().st_size > 1000:
                    ok.add(ja)
                    return
            except Exception:
                await asyncio.sleep(1.5 * (attempt + 1))
        fail.add(ja)


async def main(limit):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    master = json.loads(MASTER.read_text(encoding='utf-8'))
    seen, todo = set(), []
    for items in master.values():
        for ja, _zh in items:
            if ja in seen:
                continue
            seen.add(ja)
            p = OUT_DIR / fname(ja)
            if not (p.exists() and p.stat().st_size > 1000):
                todo.append(ja)
    if limit:
        todo = todo[:limit]
    print(f'唯一例句 {len(seen)}, 待生成 {len(todo)} -> {OUT_DIR}')

    ok, fail = set(), set()
    sem = asyncio.Semaphore(CONCURRENCY)
    t0 = time.time()
    done = 0
    BATCH = 40

    async def batched():
        nonlocal done
        tasks = [worker(sem, ja, ok, fail) for ja in todo]
        for i in range(0, len(tasks), BATCH):
            await asyncio.gather(*tasks[i:i + BATCH])
            done += len(tasks[i:i + BATCH])
            if done % (BATCH * 5) < BATCH:
                rate = done / max(time.time() - t0, 1)
                remain = (len(todo) - done) / max(rate, 0.1)
                print(f'进度 {done}/{len(todo)} ok={len(ok)} fail={len(fail)} '
                      f'{rate:.1f}/s 剩余~{remain/60:.0f}min', flush=True)
    await batched()
    print(f'完成 ok={len(ok)} fail={len(fail)} 用时 {(time.time()-t0)/60:.0f}min')
    if fail:
        fl = OUT_DIR / 'failed.txt'
        fl.write_text('\n'.join(sorted(fail)), encoding='utf-8')
        print('失败清单 ->', fl)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0)
    args = ap.parse_args()
    asyncio.run(main(args.limit))
