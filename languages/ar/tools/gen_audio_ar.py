# -*- coding: utf-8 -*-
"""阿拉伯语单词与例句发音全量生成工具 (基于 edge-tts 神经网络高品质阿语语音)。

按日语/法语/葡语/西语统一契约落盘:
  - 单词音频: LocalLow/WCP/wcp/ar_word_audio/<word>.mp3 (文件名=词条原文)
  - 例句音频: LocalLow/WCP/wcp/ar_sentence_audio/<md5(sentence)>.mp3
    (md5 对剥除 HTML 标签后的例句原文计算, 与运行时 ExtractAr 剥离逻辑一致)
并发批量生成, manifest 断点续跑, 实时显示进度, 生成完整音频与 SHA-256 清单。
"""
import asyncio
import hashlib
import json
import os
import re
import sys
from pathlib import Path

import edge_tts
from audio_paths_ar import sentence_audio_dir, word_audio_dir
from audio_filename_ar import safe_filename

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'output'
AUDIO_DIR = word_audio_dir()
SENT_AUDIO_DIR = sentence_audio_dir()
MANIFEST = OUT / 'audio_manifest_ar.json'
TMP_TAG = f'.{os.getpid()}.tmp.mp3'
MIN_BYTES = 500
CONCURRENCY = 24
TIMEOUT = 30

DEFAULT_VOICE = "ar-SA-ZariyahNeural"
def extract_ar(raw):
    if not raw:
        return None
    s = re.sub(r'<[^>]+>', '', raw).strip()
    if len(s) < 2:
        return None
    return s

def md5(s):
    return hashlib.md5(s.encode('utf-8')).hexdigest()

def load_manifest():
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text(encoding='utf-8'))
    return {'done': {}, 'failed': {}}

def save_manifest(m):
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    tmp = MANIFEST.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(MANIFEST)

async def generate_item(sem, text, out_path, voice=DEFAULT_VOICE, retries=3):
    if out_path.exists() and out_path.stat().st_size > MIN_BYTES:
        return True
    async with sem:
        for attempt in range(retries):
            try:
                communicate = edge_tts.Communicate(text, voice)
                tmp = out_path.with_name(out_path.name + TMP_TAG)
                await asyncio.wait_for(communicate.save(str(tmp)), TIMEOUT)
                if tmp.stat().st_size < MIN_BYTES:
                    raise ValueError('too small')
                os.replace(str(tmp), str(out_path))
                return True
            except Exception as e:
                tmp = out_path.with_name(out_path.name + TMP_TAG)
                if tmp.exists():
                    try:
                        tmp.unlink()
                    except OSError:
                        pass
                if attempt == retries - 1:
                    print(f"TTS 失败: {text[:20]} -> {e}")
                    return False
                await asyncio.sleep(1)
        return False

async def process_batch(items, out_dir, desc, concurrency, name_fn):
    sem = asyncio.Semaphore(concurrency)
    manifest_map = {}
    entries = [(text, name_fn(text), out_dir / name_fn(text))
               for text in items]
    total = len(entries)
    done_count = 0
    t0 = asyncio.get_event_loop().time()

    batch_size = max(concurrency * 2, 50)
    for start in range(0, total, batch_size):
        batch = entries[start:start + batch_size]
        results = await asyncio.gather(
            *(generate_item(sem, text, fpath) for text, _, fpath in batch))
        for (text, fname, fpath), success in zip(batch, results):
            if success and fpath.exists():
                manifest_map[text] = {
                    "file": fname,
                    "sha256": hashlib.sha256(fpath.read_bytes()).hexdigest(),
                    "size": fpath.stat().st_size
                }
        done_count += len(batch)
        elapsed = asyncio.get_event_loop().time() - t0
        rate = done_count / max(elapsed, 0.1)
        remain = (total - done_count) / max(rate, 0.1)
        print(f"  [{desc}] 进度: {done_count}/{total} | rate: {rate:.1f}/s | eta: {remain:.0f}s", flush=True)
    return manifest_map

async def main():
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    SENT_AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    master_path = OUT / 'arabic_books.json'
    if not master_path.exists():
        print("未找到 arabic_books.json")
        return

    data = json.loads(master_path.read_text(encoding='utf-8'))
    books = data.get('books', {})

    unique_words = {}
    unique_sentences = {}
    for bname, entries in books.items():
        for it in entries:
            w = it['word']
            if w not in unique_words:
                unique_words[w] = it
            pairs = it.get('sentences') or []
            if not pairs:
                pairs = [[it.get('example_ar', ''), it.get('example_zh', '')]]
            for pair in pairs:
                s = (pair[0] or '').strip() if isinstance(pair, (list, tuple)) else ''
                if len(s) >= 2 and s not in unique_sentences:
                    unique_sentences[s] = it

    print("=" * 60)
    print(f"开始阿拉伯语全量音频合成与落盘...")
    print(f"  单词总数: {len(unique_words)} 个")
    print(f"  例句总数: {len(unique_sentences)} 句")
    print(f"  神经网络声音: {DEFAULT_VOICE}")
    print("=" * 60)

    print(">>> 正在生成全量单词发音...")
    word_manifest = await process_batch(
        unique_words, AUDIO_DIR, "单词音频", CONCURRENCY,
        lambda w: safe_filename(w))

    print(">>> 正在生成全量例句发音...")
    sent_manifest = await process_batch(
        unique_sentences, SENT_AUDIO_DIR, "例句音频", CONCURRENCY,
        lambda s: md5(extract_ar(s)) + '.mp3')

    manifest = {
        "voice": DEFAULT_VOICE,
        "word_count": len(word_manifest),
        "sentence_count": len(sent_manifest),
        "words": word_manifest,
        "sentences": sent_manifest
    }

    manifest_path = OUT / 'audio_manifest_ar.json'
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print("=" * 60)
    print(f"音频全量落盘完成！")
    print(f"  成功落盘单词音频: {len(word_manifest)} / {len(unique_words)}")
    print(f"  成功落盘例句音频: {len(sent_manifest)} / {len(unique_sentences)}")
    print(f"  音频校验清单已更新: {manifest_path.name}")
    print("=" * 60)

if __name__ == '__main__':
    asyncio.run(main())
