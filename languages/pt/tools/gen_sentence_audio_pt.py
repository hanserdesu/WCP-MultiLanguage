# -*- coding: utf-8 -*-
"""Batch generate Portuguese sentence audio -> pt_sentence_audio/md5(es).mp3
Voice: pt-BR-FranciscaNeural. md5(es) mirrors Japanese/French convention.
"""
import argparse, asyncio, hashlib, json, os, random, re, sys, time
from pathlib import Path
import edge_tts
from audio_paths_pt import sentence_audio_dir

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
SENT_DIR = sentence_audio_dir()
MANIFEST = ROOT / 'output' / 'audio_manifest_pt_sent.json'
VOICE = 'pt-BR-FranciscaNeural'
CONCURRENCY = 20
TIMEOUT = 30
TMP_TAG = f'.{os.getpid()}.tmp.mp3'

def extract_pt(raw):
    if not raw: return None
    s = re.sub(r'<[^>]+>', '', raw).strip()
    if len(s) < 2: return None
    return s

def md5(s): return hashlib.md5(s.encode('utf-8')).hexdigest()

def load_manifest():
    if MANIFEST.exists(): return json.loads(MANIFEST.read_text(encoding='utf-8'))
    return {'done': {}, 'failed': {}}

def save_manifest(m):
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    tmp = MANIFEST.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(MANIFEST)

def load_sentence_list():
    master = ROOT / 'data' / 'translations' / 'sentences_master.json'
    if not master.exists(): return []
    data = json.loads(master.read_text(encoding='utf-8'))
    result = []
    seen = set()
    for w, sents in data.items():
        for pair in sents:
            if len(pair) != 2: continue
            es = extract_pt(pair[0])
            if not es or es in seen: continue
            seen.add(es)
            result.append((es, md5(es)))
    return result

async def gen_one(text, dest):
    async with gen_one.sem:
        await asyncio.sleep(random.uniform(0.05, 0.2))
        tmp = dest.with_name(dest.name + TMP_TAG)
        try:
            c = edge_tts.Communicate(text, VOICE)
            await asyncio.wait_for(c.save(str(tmp)), TIMEOUT)
            if tmp.stat().st_size < 500: raise ValueError('too small')
            os.replace(str(tmp), str(dest))
            return 'ok'
        except Exception as e:
            if tmp.exists():
                try: tmp.unlink()
                except OSError: pass
            return str(e)

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=0)
    parser.add_argument('--retry-failed', action='store_true')
    args = parser.parse_args()
    items = load_sentence_list()
    if not items: print('no sentences'); return
    manifest = load_manifest()
    done = manifest.get('done', {}); failed = manifest.get('failed', {})
    todo = []
    for es, key in items:
        dest = SENT_DIR / f'{key}.mp3'
        if dest.exists() and dest.stat().st_size >= 500:
            done[key] = True; continue
        if key in failed and not args.retry_failed: continue
        todo.append((es, key))
    if args.limit > 0: todo = todo[:args.limit]
    print(f'total: {len(items)}, done: {len(done)}, todo: {len(todo)} -> {SENT_DIR}')
    if not todo: print('all done'); return
    SENT_DIR.mkdir(parents=True, exist_ok=True)
    gen_one.sem = asyncio.Semaphore(CONCURRENCY)
    t0 = time.time(); success = 0; fail = 0
    BATCH = 30
    for i in range(0, len(todo), BATCH):
        batch = todo[i:i+BATCH]
        tasks = [(k, gen_one(es, SENT_DIR / f'{k}.mp3')) for es, k in batch]
        results = await asyncio.gather(*[t[1] for t in tasks])
        for (k, _), res in zip(tasks, results):
            if res == 'ok': done[k] = True; failed.pop(k, None); success += 1
            else: failed[k] = res; fail += 1
        save_manifest(manifest)
        done_total = success + fail
        rate = done_total / max(time.time() - t0, 0.1)
        remain = (len(todo) - done_total) / max(rate, 0.1)
        print(f'progress: {done_total}/{len(todo)} | ok: {success}, fail: {fail} | rate: {rate:.1f}/s, eta: {remain:.0f}s', flush=True)
    print(f'done: success {success}, fail {fail}')

if __name__ == '__main__':
    asyncio.run(main())
