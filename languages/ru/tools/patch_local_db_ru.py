# -*- coding: utf-8 -*-
"""把俄语词条灌进游戏本地词库 (幂等, 只动俄语词)。

逆向结论 (复用日语项目 2026-09-06 确认):
  - 每日学习界面 DatabaseManagerS8 查 StreamingAssets/wcpFullEng.db 的
    pron(释义/音标) + sentence2(例句); 词典查询 S17 同源
  - 故需把俄语词写入 wcpFullEng.db; wcpOnlyWord.db(其他查词界面)同步

写入内容:
  pron:      (word, ukPhonic='[重音形]', usPhonic='', meaning='中文〈词性〉')
  sentence2: (word, '例句：俄语。（中文）')  — 例句取
             data/translations/sentences_master.json, 每词 3 条

幂等: 先 DELETE 本批俄语词旧行再 INSERT; 写前自动备份。
与日语/法语补丁互不干扰 (本脚本只写俄语词)。
"""
import hashlib
import json
import sqlite3
import shutil
import sys
import time
from pathlib import Path

import wcp_paths

sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parent.parent
FULL = wcp_paths.full_db()
ONLY = wcp_paths.only_db()
BACKUP_DIR = ROOT / 'backups'


def collect():
    books = json.loads((ROOT / 'output' / 'russian_books.json').read_text(
        encoding='utf-8'))
    master_p = ROOT / 'data' / 'translations' / 'sentences_master.json'
    master = json.loads(master_p.read_text(encoding='utf-8')) \
        if master_p.exists() else {}
    words = {}
    for lv in ('a1', 'a2', 'b1', 'b2'):
        for w in books['levels'][lv]:
            stress = f"[{w['stress']}]" if w.get('stress') else ''
            words[w['word']] = {
                'phonic': stress,
                'meaning': f"{w['zh']}〈{w['pos']}〉",
                'sentences': master.get(w['word'], []),
            }
    return words


def backup(db: Path):
    BACKUP_DIR.mkdir(exist_ok=True)
    tag = hashlib.sha1(str(db.resolve()).lower().encode('utf-8')
                       ).hexdigest()[:6]
    if any(BACKUP_DIR.glob(f'{db.stem}.before_russian_{tag}_*')):
        return None
    stamp = time.strftime('%Y%m%d_%H%M%S')
    dst = BACKUP_DIR / f'{db.stem}.before_russian_{tag}_{stamp}{db.suffix}'
    shutil.copy2(db, dst)
    print('已备份 ->', dst.name)
    return dst


def patch(db: Path, words: dict, with_sentence: bool, force=False):
    probes = ['быть', 'который', 'привидение']
    if db.exists() and not force:
        try:
            con = sqlite3.connect(str(db), timeout=10)
            cur = con.cursor()
            hit = 0
            for p in probes:
                if p in words:
                    cur.execute('SELECT meaning FROM pron WHERE word=?', (p,))
                    row = cur.fetchone()
                    if row and row[0] == words[p]['meaning']:
                        hit += 1
            con.close()
            if hit == len([p for p in probes if p in words]):
                print(f'{db.name}: 俄语补丁已存在(探针 {hit} 命中), 跳过 '
                      '(--force 可强制)')
                return
        except sqlite3.Error:
            pass
    backup(db)
    con = sqlite3.connect(str(db), timeout=60)
    con.execute('PRAGMA busy_timeout=60000')
    con.execute('PRAGMA journal_mode=WAL')
    cur = con.cursor()
    wl = list(words)
    cur.execute('BEGIN')
    for i in range(0, len(wl), 500):
        chunk = wl[i:i + 500]
        ph = ','.join('?' * len(chunk))
        cur.execute(f'DELETE FROM pron WHERE word IN ({ph})', chunk)
        if with_sentence:
            cur.execute(f'DELETE FROM sentence2 WHERE word IN ({ph})', chunk)
    n_pron = n_sent = 0
    for i in range(0, len(wl), 500):
        chunk = wl[i:i + 500]
        ph = ','.join('?' * len(chunk))
        cur.executemany('INSERT INTO pron (word, ukPhonic, usPhonic, meaning) '
                        'VALUES (?,?,?,?)',
                        [(w, words[w]['phonic'], '', words[w]['meaning'])
                         for w in chunk])
        n_pron += len(chunk)
        if with_sentence:
            sents = []
            for w in chunk:
                for ru, zh in words[w]['sentences']:
                    sents.append((w, f'例句：{ru}（{zh}）'))
            cur.executemany('INSERT INTO sentence2 (word, sentences) '
                            'VALUES (?,?)', sents)
            n_sent += len(sents)
    con.commit()
    con.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    con.close()
    sample = wl[len(wl) // 2]
    print(f'{db.name}: pron +{n_pron}, sentence2 +{n_sent}; '
          f'共处理 {len(wl)} 词')


def main():
    force = '--force' in sys.argv
    words = collect()
    n_s = sum(1 for v in words.values() if v['sentences'])
    print(f'游戏目录 {wcp_paths.game_dir()}')
    print(f'俄语词条 {len(words)} (含例句 {n_s})')
    patch(FULL, words, with_sentence=True, force=force)
    patch(ONLY, words, with_sentence=False, force=force)


if __name__ == '__main__':
    main()
