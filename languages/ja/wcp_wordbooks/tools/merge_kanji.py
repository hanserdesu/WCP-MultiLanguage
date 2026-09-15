# -*- coding: utf-8 -*-
"""常用汉字书合并: kanji_books_raw.json + kanji_zh_*.json -> kanji_books.json,
并生成 output/import/常用汉字.xlsx + wcp_kanji.db。

显示释义格式: 音:ア 訓:つ.ぐ｜亚；次之   (音/训取 kanjidic2 前3个)
音频: 文件名 = <汉字>.mp3, 内容朗读 音读(片假名)+训读(平假名, 去点)
      -> 存入日语 pack 的 word 音频目录。
"""
import asyncio
import json
import os
import random
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'output'
IMPORT = OUT / 'import'
TDIR = ROOT / 'data' / 'translations'
VOCAB_DIR = (Path.home() / 'AppData' / 'LocalLow' / 'WCP' /
             'packs' / 'ja' / 'audio' / 'word')
KANJIBOOKS = OUT / 'kanji_books.json'
MANIFEST = OUT / 'audio_manifest_kanji.json'

VOICE = 'ja-JP-NanamiNeural'
INVALID_FN = re.compile(r'[\\/:*?"<>|]')


def build():
    raw = json.loads((OUT / 'kanji_books_raw.json').read_text(encoding='utf-8'))
    zh = {}
    for p in sorted(TDIR.glob('kanji_zh_*.json')):
        zh.update(json.loads(p.read_text(encoding='utf-8')))

    rows = []
    for r in raw['books']['kanji']:
        w = r['word']
        t = zh.get(w)
        if not t:
            continue
        zh_text = t if isinstance(t, str) else t.get('zh', '')
        on = r.get('onyomi') or []
        kun = r.get('kunyomi') or []
        rd = ''
        if on:
            rd = '音:' + '・'.join(on)
        if kun:
            rd += (' ' if rd else '') + '訓:' + '・'.join(kun)
        meaning = (rd + ('｜' if rd else '') + zh_text)
        rows.append({
            'word': w, 'reading': on[0] if on else (kun[0].replace('.', '')
                                                    if kun else ''),
            'meaning': meaning, 'meaning_zh': zh_text,
            'onyomi': on, 'kunyomi': kun,
            'grade': r.get('grade', 0), 'jlpt': r.get('jlpt', 0),
            'meaning_en': '; '.join(r.get('meaning_en', [])),
        })
    result = {'meta': {'count': len(rows)}, 'books': {'kanji': rows}}
    KANJIBOOKS.write_text(json.dumps(result, ensure_ascii=False, indent=1),
                          encoding='utf-8')
    print(f'kanji_books.json: {len(rows)} 字')

    # xlsx + db
    from openpyxl import Workbook
    from openpyxl.styles import Alignment
    import sqlite3
    IMPORT.mkdir(exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = '词汇表'
    for r in rows:
        ws.append([r['word'], r['meaning'], ''.join(r['onyomi']),
                   '・'.join(r['kunyomi']), r['meaning_en'],
                   f"G{r['grade']}" + (f" N{r['jlpt']}" if r['jlpt'] else '')])
    for col, width in zip('ABCDEF', (8, 46, 12, 20, 40, 10)):
        ws.column_dimensions[col].width = width
    for row in ws.iter_rows(min_row=1):
        for c in row:
            c.alignment = Alignment(vertical='center', wrap_text=True)
    xlsx = IMPORT / '常用汉字.xlsx'
    wb.save(xlsx)
    print(f'{xlsx.name}: {len(rows)} 字')

    db = IMPORT / 'wcp_kanji.db'
    if db.exists():
        db.unlink()
    con = sqlite3.connect(db)
    cur = con.cursor()
    cur.execute('CREATE TABLE pron (word TEXT PRIMARY KEY, meaning TEXT)')
    for r in rows:
        cur.execute('INSERT INTO pron VALUES (?,?)', (r['word'], r['meaning']))
    con.commit()
    con.close()
    print(f'{db.name}: pron {len(rows)} 字')


def audio_text(r):
    parts = []
    if r['onyomi']:
        parts.append(r['onyomi'][0])
    if r['kunyomi']:
        parts.append(r['kunyomi'][0].replace('.', '').replace('-', ''))
    return '、'.join(parts) if parts else r['word']


async def gen_audio():
    import edge_tts
    data = json.loads(KANJIBOOKS.read_text(encoding='utf-8'))
    rows = [r for r in data['books']['kanji'] if not INVALID_FN.search(r['word'])]
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8')) if MANIFEST.exists() \
        else {'done': {}, 'failed': {}}
    todo = []
    for r in rows:
        w = r['word']
        if w in manifest['done']:
            continue
        dest = VOCAB_DIR / f'{w}.mp3'
        if dest.exists() and dest.stat().st_size > 500:
            manifest['done'][w] = 'existed'
            continue
        todo.append(r)
    print(f'待生成 {len(todo)} 个音频')
    sem = asyncio.Semaphore(8)
    ok = fail = 0

    async def one(r):
        nonlocal ok, fail
        async with sem:
            await asyncio.sleep(random.uniform(0.05, 0.3))
            dest = VOCAB_DIR / f"{r['word']}.mp3"
            tmp = dest.with_name(f"{r['word']}.{os.getpid()}.tmp.mp3")
            try:
                c = edge_tts.Communicate(audio_text(r), VOICE)
                await asyncio.wait_for(c.save(str(tmp)), 25)
                if tmp.stat().st_size < 500:
                    raise ValueError('too small')
                os.replace(str(tmp), str(dest))
                manifest['done'][r['word']] = 'generated'
                ok += 1
            except Exception as e:
                try:
                    tmp.unlink(missing_ok=True)
                except OSError:
                    pass
                manifest['failed'][r['word']] = str(e)[:100]
                fail += 1

    t0 = time.time()
    for i, r in enumerate(todo):
        await one(r)
        if (i + 1) % 50 == 0 or i == len(todo) - 1:
            MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False),
                                encoding='utf-8')
            print(f'  {i+1}/{len(todo)} ok={ok} fail={fail} '
                  f'{(i+1)/max(time.time()-t0,1):.1f}/s', flush=True)
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False),
                        encoding='utf-8')
    print(f'音频完成 ok={ok} fail={fail} 总 {len(manifest["done"])}/{len(rows)}')


def main():
    build()
    if '--audio' in sys.argv:
        VOCAB_DIR.mkdir(parents=True, exist_ok=True)
        asyncio.run(gen_audio())


if __name__ == '__main__':
    main()
