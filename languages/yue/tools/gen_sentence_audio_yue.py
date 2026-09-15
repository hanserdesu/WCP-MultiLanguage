# -*- coding: utf-8 -*-
"""批量并发生成粤语例句发音 MP3 -> packs/yue/audio/sentence 与 yue_sentence_audio 目录。
采用 md5(例句原文) 命名规则，支持断点续传、并发与自动重试。
用法: python tools/gen_sentence_audio_yue.py [--limit N] [--retry-failed]
"""
import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
from pathlib import Path

import edge_tts

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
from audio_paths_yue import pack_sentence_audio_dir, sentence_audio_dir

MANIFEST = ROOT / 'output' / 'sentence_audio_manifest_yue.json'
VOICE = 'zh-HK-HiuGaaiNeural'
CONCURRENCY = 12
TIMEOUT = 30

_sem = None
_manifest_lock = None


def md5_str(s: str) -> str:
    return hashlib.md5(s.strip().encode('utf-8')).hexdigest()


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


def get_sentences():
    master_file = ROOT / 'output' / 'sentences_master.json'
    if not master_file.exists():
        return []
    data = json.loads(master_file.read_text(encoding='utf-8'))
    items = []
    seen = set()
    for word, s_list in data.get('sentences', {}).items():
        for s in s_list:
            raw_sent = s.get('sentence', '').strip()
            # 剥离拼音注音（保留汉字例句正文）
            clean_sent = re.sub(r'（[^）]*）|\([^\)]*\)', '', raw_sent).strip()
            if not clean_sent:
                continue
            key = md5_str(clean_sent)
            if key not in seen:
                seen.add(key)
                items.append({
                    "key": key,
                    "clean_text": clean_sent,
                    "raw_text": raw_sent,
                    "word": word
                })
    return items


async def synthesize_sentence(clean_text: str, targets: list[Path]):
    async with _sem:
        for attempt in range(3):
            try:
                first_target = targets[0]
                communicate = edge_tts.Communicate(clean_text, VOICE)
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


async def process_sentence(s: dict, pack_dir: Path, app_dir: Path, manifest: dict, counter: list):
    k = s["key"]
    targets = [pack_dir / f"{k}.mp3", app_dir / f"{k}.mp3"]
    ok, err = await synthesize_sentence(s["clean_text"], targets)
    async with _manifest_lock:
        counter[0] += 1
        idx = counter[0]
        total = counter[1]
        if ok:
            manifest['done'][k] = s["clean_text"]
            manifest['failed'].pop(k, None)
            counter[2] += 1
            if idx % 25 == 0 or idx == total:
                print(f"[{idx}/{total}] 例句音频就绪: {s['clean_text'][:15]}...")
                save_manifest(manifest)
        else:
            manifest['failed'][k] = err
            counter[3] += 1
            print(f"[{idx}/{total}] 例句合成失败: {s['clean_text'][:15]}... - {err}")


async def main_async(args):
    global _sem, _manifest_lock
    _sem = asyncio.Semaphore(CONCURRENCY)
    _manifest_lock = asyncio.Lock()

    pack_dir = pack_sentence_audio_dir()
    app_dir = sentence_audio_dir()

    sentences = get_sentences()
    manifest = load_manifest()

    to_run = []
    for s in sentences:
        k = s["key"]
        p_target = pack_dir / f"{k}.mp3"
        if not args.retry_failed and k in manifest.get('done', {}):
            if p_target.exists() and p_target.stat().st_size > 100:
                continue
        to_run.append(s)

    if args.limit and args.limit > 0:
        to_run = to_run[:args.limit]

    print(f"总计独立例句数: {len(sentences)}，本次待合成例句: {len(to_run)}")
    if not to_run:
        print("所有例句音频已全部就绪！")
        return

    counter = [0, len(to_run), 0, 0]
    tasks = [process_sentence(s, pack_dir, app_dir, manifest, counter) for s in to_run]
    await asyncio.gather(*tasks)

    save_manifest(manifest)
    print(f"\n例句音频合成结束: 成功 {counter[2]}，失败 {counter[3]}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=0, help='限制本次合成数量')
    parser.add_argument('--retry-failed', action='store_true', help='重试失败项')
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == '__main__':
    main()
