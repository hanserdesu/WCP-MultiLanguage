# -*- coding: utf-8 -*-
"""语法路线书占位词音频 -> 日语 pack 的 word/sentence 音频目录

单词音频: 朗读 读音(或语法名) + 第一条例句, 文件名 = 占位词全文 (游戏查 <单词>.mp3)。
例句音频: 与 gen_sentence_audio.py 同目录同命名 (md5(ja)), SentenceAudioMod 直接命中。

用法: python tools/gen_grammar_audio.py [--limit N]
"""
import argparse
import asyncio
import hashlib
import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'tools'))
import edge_tts

from build_grammar_book import load_curriculum, build_route, load_content

VOCAB_DIR = (Path.home() / 'AppData' / 'LocalLow' / 'WCP' /
             'packs' / 'ja' / 'audio' / 'word')
SENT_DIR = (Path.home() / 'AppData' / 'LocalLow' / 'WCP' /
            'packs' / 'ja' / 'audio' / 'sentence')
VOICE = 'ja-JP-NanamiNeural'
CONCURRENCY = 8


def md5name(s):
    return hashlib.md5(s.encode('utf-8')).hexdigest() + '.mp3'


def jobs():
    cur = load_curriculum(None)
    content = load_content()
    route, _ = build_route(cur, content, True)
    out = []
    for e in route:
        if e['kind'] not in ('grammar', 'stage') or not e['rows']:
            continue
        say = f"{e['reading']}。{e['rows'][0][0]}" if e['reading'] else e['rows'][0][0]
        out.append(('word', e['word'], say))
        for ja, _zh in e['rows']:
            out.append(('sent', md5name(ja), ja))
    return out


async def worker(sem, path, text, ok, fail):
    async with sem:
        for attempt in range(3):
            try:
                await edge_tts.Communicate(text, VOICE).save(str(path))
                if path.stat().st_size > 1000:
                    ok.add(str(path))
                    return
            except Exception:
                await asyncio.sleep(1.5 * (attempt + 1))
        fail.add(str(path))


async def main(limit):
    VOCAB_DIR.mkdir(parents=True, exist_ok=True)
    SENT_DIR.mkdir(parents=True, exist_ok=True)
    todo = []
    for kind, target, text in jobs():
        p = (VOCAB_DIR / (target + '.mp3')) if kind == 'word' else (SENT_DIR / target)
        if not (p.exists() and p.stat().st_size > 1000):
            todo.append((p, text))
    if limit:
        todo = todo[:limit]
    print(f'待生成 {len(todo)} (单词音频+例句音频)')
    ok, fail = set(), set()
    sem = asyncio.Semaphore(CONCURRENCY)
    t0 = time.time()
    for i in range(0, len(todo), 30):
        await asyncio.gather(*[worker(sem, p, t, ok, fail) for p, t in todo[i:i + 30]])
        done = min(i + 30, len(todo))
        print(f'进度 {done}/{len(todo)} fail={len(fail)} '
              f'{done / max(time.time() - t0, 1):.1f}/s', flush=True)
    print(f'完成 ok={len(ok)} fail={len(fail)} 用时 {(time.time() - t0) / 60:.1f}min')
    if fail:
        (Path.home() / 'AppData' / 'LocalLow' / 'WCP' / 'wcp' / 'grammar_audio_failed.txt') \
            .write_text('\n'.join(sorted(fail)), encoding='utf-8')
        print('失败清单 -> grammar_audio_failed.txt')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0)
    args = ap.parse_args()
    asyncio.run(main(args.limit))
