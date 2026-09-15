# -*- coding: utf-8 -*-
"""合并 Set B 主题词书翻译 -> 重建 output/topic_books.json。

翻译文件: data/translations/topic_zh_*.json
  {word: {"zh": "...", "pos": "...", "reading": "(可选读音修正)"}}
规则:
  - 只保留翻译文件中出现的词 (翻译文件即保留清单)
  - 不在翻译文件中的词被过滤掉 (由 LLM 精翻时筛选)
  - 显示释义格式: 汉字词 -> 【读音】中文〈词性〉; 假名词 -> 中文〈词性〉
  - --write-import 同时生成 output/import/ 的 xlsx + wcp_topic.db
"""
import json
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'output'
IMPORT = OUT / 'import'
TDIR = ROOT / 'data' / 'translations'

sys.path.insert(0, str(ROOT / 'tools'))
from build_books import fmt_meaning_zh  # noqa: E402

TAGS = {'it': 'IT用语', 'biz': '商务日语'}


def norm(w):
    """全角字母数字 -> 半角 (Ｃ言語->C言語), 其余保持。"""
    return ''.join(
        unicodedata.normalize('NFKC', ch) if ('Ａ' <= ch <= 'Ｚ') or ('ａ' <= ch <= 'ｚ') or ('０' <= ch <= '９')
        else ch
        for ch in w)


def main():
    write_import = '--write-import' in sys.argv
    data = json.loads((OUT / 'topic_books.json').read_text(encoding='utf-8'))

    zh_all = {}
    for p in sorted(TDIR.glob('topic_zh_*.json')):
        raw = json.loads(p.read_text(encoding='utf-8'))
        zh_all.update({norm(k): v for k, v in raw.items()})

    books = {}
    for tag, rows in data['books'].items():
        kept = []
        seen = set()
        for r in rows:
            w = norm(r['word'])
            if w in seen or w not in zh_all:
                continue
            seen.add(w)
            t = zh_all[w]
            reading = t.get('reading', '') or r.get('reading', '')
            zh = t.get('zh', '')
            pos = t.get('pos', '') or r.get('pos', '')
            kept.append({
                'word': w,
                'reading': reading,
                'meaning_zh': zh,
                'meaning_en': r.get('meaning_en', ''),
                'pos_zh': pos,
                'example_ja': '',
                'example_en': '',
                'level': TAGS[tag],
                'zh_source': 'llm',
            })
        for r in kept:
            r['meaning'] = fmt_meaning_zh(r['word'], r['reading'],
                                          r['meaning_zh'], r['pos_zh'])
        books[tag] = kept

    result = {
        'meta': {
            'source': data['meta']['source'],
            'counts': {t: len(v) for t, v in books.items()},
            'untranslated': {t: sum(1 for r in data['books'][t]
                                    if r['word'] not in zh_all)
                             for t in books},
        },
        'books': books,
    }
    (OUT / 'topic_books.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(result['meta']['counts'], ensure_ascii=False),
          'untranslated:', json.dumps(result['meta']['untranslated'],
                                      ensure_ascii=False))

    if write_import:
        _write_import(books)


def _write_import(books):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment
    import sqlite3

    IMPORT.mkdir(parents=True, exist_ok=True)
    all_rows = []
    for tag, rows in books.items():
        name = TAGS[tag]
        wb = Workbook()
        ws = wb.active
        ws.title = '词汇表'
        for r in rows:
            row = [r['word'], r['meaning'], r['reading'], r['meaning_en']]
            ws.append(row)
            all_rows.append(row)
        for col, w in zip('ABCD', (18, 46, 14, 40)):
            ws.column_dimensions[col].width = w
        for row in ws.iter_rows(min_row=1):
            for c in row:
                c.alignment = Alignment(vertical='center', wrap_text=True)
        path = IMPORT / f'{name}.xlsx'
        wb.save(path)
        print(f'{path.name}: {len(rows)} 词')

    db_path = IMPORT / 'wcp_topic.db'
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute('CREATE TABLE pron (word TEXT PRIMARY KEY, meaning TEXT)')
    seen = set()
    for word, meaning, *_ in all_rows:
        if word in seen or not meaning:
            continue
        seen.add(word)
        cur.execute('INSERT INTO pron VALUES (?, ?)', (word, meaning))
    cur.execute('''CREATE TABLE topic_all (
        word TEXT, meaning TEXT, reading TEXT, meaning_en TEXT, topic TEXT)''')
    for tag, rows in books.items():
        for r in rows:
            cur.execute('INSERT INTO topic_all VALUES (?,?,?,?,?)',
                        (r['word'], r['meaning'], r['reading'],
                         r['meaning_en'], TAGS[tag]))
    con.commit()
    con.close()
    print(f'{db_path.name}: pron {len(seen)} 词 (去重)')


if __name__ == '__main__':
    main()
