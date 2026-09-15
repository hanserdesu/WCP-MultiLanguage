# -*- coding: utf-8 -*-
"""把 15812 词的读音灌进游戏本地库与外接词库 (重灌, 幂等)。

背景: 2026-09-12 验证发现两库 pron 已被还原为英文原库 (Steam 校验或手动
恢复), 09-06 会话B 的日语 pron 补丁丢失; sentence2 例句仍在。本脚本:
  1. wcpFullEng.db / wcpOnlyWord.db: pron 全量重灌
     (word, ukPhonic=[かな], usPhonic='', meaning=游戏显示释义)
     纯假名词读音=词本身, 保证每词必有读音
  2. wcpFullEng.db help 表: 含汉字词写入振假名标注 (furigana_map.json)
  3. output/import/wcp_all.db: pron 表补 ukPhonic 列并填读音
写前自动备份 (时间戳)。
"""
import json
import re
import shutil
import sqlite3
import sys
import time
from pathlib import Path

import wcp_paths

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / 'work'
OUT = ROOT / 'output'
SA = wcp_paths.streaming_assets()
FULL = wcp_paths.full_db()
ONLY = wcp_paths.only_db()
BACKUP_DIR = ROOT / 'backups'
FURIGANA = ROOT / 'data' / 'translations' / 'furigana_map.json'

PURE_KANA = re.compile(r'^[\u3040-\u30ffー・]+$')


def load_words():
    need = {}
    for n in range(40):
        p = WORK / f'gen_words_{n:02d}.json'
        if p.exists():
            need.update(json.loads(p.read_text(encoding='utf-8')).items())
    rows = {}
    for w, v in need.items():
        reading = (v.get('reading') or '').strip()
        if not reading and PURE_KANA.match(w):
            reading = w          # 假名词自身即读音
        rows[w] = (reading, v['meaning'])
    return rows


def backup(db: Path):
    BACKUP_DIR.mkdir(exist_ok=True)
    stamp = time.strftime('%Y%m%d_%H%M%S')
    dst = BACKUP_DIR / f'{db.stem}.before_readings_{stamp}{db.suffix}'
    shutil.copy2(db, dst)
    print('  已备份 ->', dst.name)


def patch_pron(db: Path, rows: dict):
    con = sqlite3.connect(str(db), timeout=30)
    con.execute('PRAGMA busy_timeout=30000')
    cur = con.cursor()
    cur.execute('BEGIN')
    wl = list(rows)
    for i in range(0, len(wl), 500):
        chunk = wl[i:i + 500]
        ph = ','.join('?' * len(chunk))
        cur.execute(f'DELETE FROM pron WHERE word IN ({ph})', chunk)
    n = 0
    for w, (reading, meaning) in rows.items():
        ph = f'[{reading}]' if reading else ''
        cur.execute('INSERT INTO pron (word, ukPhonic, usPhonic, meaning) '
                    'VALUES (?,?,?,?)', (w, ph, '', meaning))
        n += 1
    con.commit()
    # 校验
    miss = [w for w in wl if not cur.execute(
        'SELECT ukPhonic FROM pron WHERE word=?', (w,)).fetchone()[0]]
    con.close()
    print(f'  {db.name}: pron 重灌 {n} 词, 无读音残留 {len(miss)}', miss[:5])


def patch_help(db: Path, furigana: dict):
    con = sqlite3.connect(str(db), timeout=30)
    con.execute('PRAGMA busy_timeout=30000')
    cur = con.cursor()
    cur.execute('BEGIN')
    wl = list(furigana)
    for i in range(0, len(wl), 500):
        chunk = wl[i:i + 500]
        ph = ','.join('?' * len(chunk))
        cur.execute(f'DELETE FROM help WHERE word IN ({ph})', chunk)
    for w, ann in furigana.items():
        cur.execute('INSERT INTO help (word, help) VALUES (?,?)',
                    (w, f'振り仮名：{ann}'))
    con.commit()
    n = cur.execute('SELECT COUNT(*) FROM help WHERE help LIKE '
                    '"振り仮名：%"').fetchone()[0]
    con.close()
    print(f'  {db.name}: help 振假名 {n} 条')


def patch_wcp_all(db: Path, rows: dict):
    con = sqlite3.connect(str(db), timeout=30)
    con.execute('PRAGMA busy_timeout=30000')
    cur = con.cursor()
    cols = [r[1] for r in cur.execute('PRAGMA table_info(pron)')]
    if 'ukPhonic' not in cols:
        cur.execute('ALTER TABLE pron ADD COLUMN ukPhonic TEXT')
    cur.execute('BEGIN')
    n = 0
    for w, (reading, _) in rows.items():
        if cur.execute('SELECT 1 FROM pron WHERE word=?', (w,)).fetchone():
            cur.execute('UPDATE pron SET ukPhonic=? WHERE word=?',
                        (f'[{reading}]' if reading else '', w))
            n += 1
    con.commit()
    filled = cur.execute(
        'SELECT COUNT(*) FROM pron WHERE ukPhonic IS NOT NULL '
        'AND ukPhonic != ""').fetchone()[0]
    total = cur.execute('SELECT COUNT(*) FROM pron').fetchone()[0]
    con.close()
    print(f'  {db.name}: ukPhonic 更新 {n}, 填充 {filled}/{total}')


def main():
    rows = load_words()
    no_rd = [w for w, (r, _) in rows.items() if not r]
    print(f'词数 {len(rows)}, 仍无读音 {len(no_rd)}', no_rd[:10])
    furigana = json.loads(FURIGANA.read_text(encoding='utf-8'))
    for db in (FULL, ONLY):
        print(f'-> {db.name}')
        backup(db)
        patch_pron(db, rows)
    print('-> help 表')
    patch_help(FULL, furigana)
    print('-> 外接词库 wcp_all.db')
    patch_wcp_all(OUT / 'import' / 'wcp_all.db', rows)
    print('完成')


if __name__ == '__main__':
    main()
