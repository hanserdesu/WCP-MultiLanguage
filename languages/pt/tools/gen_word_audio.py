# -*- coding: utf-8 -*-
"""Batch generate Portuguese word audio MP3 -> pt_word_audio/<word>.mp3
edge-tts pt-BR-FranciscaNeural. Manifest-based resume + async concurrency.
Usage: python tools/gen_word_audio.py [--limit N] [--retry-failed]
"""
import argparse, asyncio, json, os, random, re, sys, time
from pathlib import Path
import edge_tts
from audio_paths_pt import word_audio_dir

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
VOCAB_DIR = word_audio_dir()
MANIFEST = ROOT / 'output' / 'audio_manifest_pt.json'
VOICE = 'pt-BR-FranciscaNeural'
CONCURRENCY = 12
TIMEOUT = 30
INVALID_FN = re.compile(r'[\/:*?"<>|]')
TMP_TAG = f'.{os.getpid()}.tmp.mp3'

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
    books_file = ROOT / 'output' / 'portuguese_books.json'
    words = []; seen = set()
    if books_file.exists():
        data = json.loads(books_file.read_text(encoding='utf-8'))
        for lv in ('pt_a1a2', 'pt_b1', 'pt_b2', 'pt_c1'):
            if lv in data.get('levels', {}):
                for r in data['levels'][lv]:
                    w = r.get('word', '').strip()
                    if w and w not in seen and not INVALID_FN.search(w):
                        seen.add(w); words.append(w)
    return words

async def gen_one(text, dest):
    sem = gen_one.sem
    async with sem:
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
                try: tmp.unlink()
                except OSError: pass
            return str(e)

async def main():
    parser = argparse.ArgumentParser(description='Generate Portuguese word audio')
    parser.add_argument('--limit', type=int, default=0)
    parser.add_argument('--retry-failed', action='store_true')
    args = parser.parse_args()
    words = load_word_list()
    if not words:
        print('no word list')
        return
    manifest = load_manifest()
    done = manifest.get('done', {}); failed = manifest.get('failed', {})
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
    print(f'total: {len(words)}, done: {len(done)}, todo: {len(todo)} -> {VOCAB_DIR}')
    if not todo:
        print('all done')
        return
    VOCAB_DIR.mkdir(parents=True, exist_ok=True)
    sem = asyncio.Semaphore(CONCURRENCY)
    gen_one.sem = sem
    t0 = time.time()
    success = 0; fail = 0
    BATCH = 30
    for i in range(0, len(todo), BATCH):
        batch = todo[i:i + BATCH]
        tasks = [(w, gen_one(w, VOCAB_DIR / f'{w}.mp3')) for w in batch]
        results = await asyncio.gather(*[t[1] for t in tasks])
        for (w, _), res in zip(tasks, results):
            if res == 'ok':
                done[w] = True; failed.pop(w, None); success += 1
            else:
                failed[w] = res; fail += 1
        save_manifest(manifest)
        done_total = success + fail
        rate = done_total / max(time.time() - t0, 0.1)
        remain = (len(todo) - done_total) / max(rate, 0.1)
        print(f'progress: {done_total}/{len(todo)} | ok: {success}, fail: {fail} | rate: {rate:.1f}/s, eta: {remain:.0f}s', flush=True)
    print(f'done: success {success}, fail {fail}')

if __name__ == '__main__':
    asyncio.run(main())
