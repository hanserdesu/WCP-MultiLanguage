# -*- coding: utf-8 -*-
"""合并全部词书为单一外接词库 wcp_all.db:
  来源: wcp_jlpt.db / wcp_themed.db / wcp_topic.db / wcp_setb.db / wcp_kanji.db
  表: pron(word, meaning) 去重全量 (同词取更丰富释义)
      all_detail(word, meaning, book) 明细, book 标注出处
"""
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IMPORT = ROOT / 'output' / 'import'
DEST = IMPORT / 'wcp_all.db'

SOURCES = [
    ('wcp_jlpt.db', 'jlpt'),
    ('wcp_themed.db', 'themed'),
    ('wcp_topic.db', 'topic'),
    ('wcp_kanji.db', 'kanji'),
    ('setb/wcp_setb.db', 'setb'),
]


def richness(m):
    """释义丰富度: 越多标注越丰富。"""
    if not m:
        return -1
    s = 0
    if '【' in m:
        s += 2
    if '〈' in m:
        s += 1
    return s + min(len(m) // 20, 3)


def main():
    best = {}   # word -> (meaning, book)
    detail = []
    for fname, book in SOURCES:
        p = IMPORT / fname
        if not p.exists():
            print(f'跳过(不存在): {fname}')
            continue
        con = sqlite3.connect(p)
        try:
            rows = con.execute('SELECT word, meaning FROM pron').fetchall()
        except sqlite3.OperationalError as e:
            print(f'{fname}: pron 表读取失败 {e}')
            con.close()
            continue
        for w, m in rows:
            w = (w or '').strip()
            m = (m or '').strip()
            if not w or not m:
                continue
            detail.append((w, m, book))
            cur = best.get(w)
            if cur is None or richness(m) > richness(cur[0]):
                best[w] = (m, book)
        con.close()
        print(f'{fname}: {len(rows)} 行')

    if DEST.exists():
        DEST.unlink()
    con = sqlite3.connect(DEST)
    cur = con.cursor()
    cur.execute('CREATE TABLE pron (word TEXT PRIMARY KEY, meaning TEXT)')
    for w, (m, _b) in best.items():
        cur.execute('INSERT INTO pron VALUES (?,?)', (w, m))
    cur.execute('CREATE TABLE all_detail (word TEXT, meaning TEXT, book TEXT)')
    seen = set()
    for w, m, b in detail:
        key = (w, m, b)
        if key in seen:
            continue
        seen.add(key)
        cur.execute('INSERT INTO all_detail VALUES (?,?,?)', (w, m, b))
    con.commit()
    con.close()
    print(f'wcp_all.db: pron {len(best)} 词 (去重), all_detail {len(seen)} 行')


if __name__ == '__main__':
    main()
