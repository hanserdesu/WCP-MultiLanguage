# -*- coding: utf-8 -*-
"""批量并发生成粤语单词发音 MP3 -> packs/yue/audio/word 与 yue_word_audio 目录。
采用 edge-tts (zh-HK-HiuGaaiNeural)，支持断点续传、并发与自动重试。
用法: python tools/gen_word_audio.py [--limit N] [--retry-failed]
"""
import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path

import edge_tts

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
from audio_paths_yue import pack_word_audio_dir, word_audio_dir

MANIFEST = ROOT / 'output' / 'audio_manifest_yue.json'
VOICE = 'zh-HK-HiuGaaiNeural'
CONCURRENCY = 12
TIMEOUT = 30
INVALID_FN = re.compile(r'[\/:*?"<>|]')

_sem = None
_manifest_lock = None


def load_manifest():
    if MANIFEST.exists():
        try:
            return json.loads(MANIFEST.read_text(encoding='utf-8'))
        except Exception:
            pass
    return {'done': {}, 'failed': {}}


def save_manifest(m):
    tmp = MANIFEST.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(MANIFEST)


def get_words():
    books_file = ROOT / 'output' / 'cantonese_books.json'
    if not books_file.exists():
        return []
    data = json.loads(books_file.read_text(encoding='utf-8'))
    return [item['word'] for item in data.get('vocabulary', []) if not INVALID_FN.search(item['word'])]


async def synthesize_word(word: str, targets: list[Path]):
    async with _sem:
        for attempt in range(3):
            try:
                first_target = targets[0]
                communicate = edge_tts.Communicate(word, VOICE)
                await asyncio.wait_for(communicate.save(str(first_target)), timeout=TIMEOUT)

                if first_target.stat().st_size < 100:
                    first_target.unlink(missing_ok=True)
                    raise RuntimeError("音频文件过小")

                data = first_target.read_bytes()
                for t in targets[1:]:
                    t.write_bytes(data)
                return True, ""
            except Exception as e:
                if attempt == 2:
                    return False, str(e)
                await asyncio.sleep(1 + attempt * 0.5)


async def process_word(w: str, pack_dir: Path, app_dir: Path, manifest: dict, counter: list):
    targets = [pack_dir / f"{w}.mp3", app_dir / f"{w}.mp3"]
    ok, err = await synthesize_word(w, targets)
    async with _manifest_lock:
        counter[0] += 1
        idx = counter[0]
        total = counter[1]
        if ok:
            manifest['done'][w] = f"{w}.mp3"
            manifest['failed'].pop(w, None)
            counter[2] += 1
            if idx % 20 == 0 or idx == total:
                print(f"[{idx}/{total}] 单词音频就绪: {w}")
                save_manifest(manifest)
        else:
            manifest['failed'][w] = err
            counter[3] += 1
            print(f"[{idx}/{total}] 合成失败: {w} - {err}")


async def main_async(args):
    global _sem, _manifest_lock
    _sem = asyncio.Semaphore(CONCURRENCY)
    _manifest_lock = asyncio.Lock()

    pack_dir = pack_word_audio_dir()
    app_dir = word_audio_dir()

    words = get_words()
    manifest = load_manifest()

    to_run = []
    for w in words:
        p_target = pack_dir / f"{w}.mp3"
        if not args.retry_failed and w in manifest.get('done', {}):
            if p_target.exists() and p_target.stat().st_size > 100:
                continue
        to_run.append(w)

    if args.limit and args.limit > 0:
        to_run = to_run[:args.limit]

    print(f"总计单词数: {len(words)}，本次待合成发音: {len(to_run)}")
    if not to_run:
        print("所有单词发音已全部就绪！")
        return

    # counter: [current, total, success, fail]
    counter = [0, len(to_run), 0, 0]
    tasks = [process_word(w, pack_dir, app_dir, manifest, counter) for w in to_run]
    await asyncio.gather(*tasks)

    save_manifest(manifest)
    print(f"\n单词音频合成结束: 成功 {counter[2]}，失败 {counter[3]}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=0, help='限制本次合成数量')
    parser.add_argument('--retry-failed', action='store_true', help='重试失败项')
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == '__main__':
    main()
