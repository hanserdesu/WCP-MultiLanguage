# -*- coding: utf-8 -*-
"""【关键实现】把全部法语词条灌进游戏本地词库。

 逆向结论 (复用日语项目 2026-09-06 确认):
   - 每日学习界面 DatabaseManagerS8 查 StreamingAssets/wcpFullEng.db 的
     pron(释义/音标) + sentence2(例句); 词典查询 S17 同源
  - 故需把法语词直接写入 wcpFullEng.db; wcpOnlyWord.db(其他查词界面)同步

写入内容:
  pron:      (word, ukPhonic='[IPA]', usPhonic='', meaning=游戏显示释义)
  sentence2: (word, '例句：法语。（中文翻译）')

幂等: 先 DELETE 同批 word 再 INSERT。写前自动备份。
"""
import hashlib
import json
import sqlite3
import shutil
import sys
import time
from pathlib import Path

import wcp_paths
from es3_safe import require_game_closed

sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parent.parent
FULL = wcp_paths.full_db()
ONLY = wcp_paths.only_db()
BACKUP_DIR = ROOT / 'backups'


def collect():
    books = json.loads((ROOT / 'output' / 'french_books.json').read_text(
        encoding='utf-8'))
    master_p = ROOT / 'data' / 'translations' / 'sentences_master.json'
    master = json.loads(master_p.read_text(encoding='utf-8')) \
        if master_p.exists() else {}
    words = {}
    for lv in ('a1', 'a2', 'b1', 'b2'):
        for w in books['levels'][lv]:
            ipa = f"[{w['ipa']}]" if w.get('ipa') else ''
            words[w['word']] = {
                'phonic': ipa,
                'meaning': f"{w['zh']}〈{w['pos']}〉",
                'sentences': master.get(w['word'], []),
            }
    return words


def load_overlap(words):
    """英法同形词清单 — 这些词的英文 pron/sentence2 不允许被覆盖。

    优先读 work/english_overlap_words.json (提交在仓库里);
    缺失时从英文基线库与法语词表求交集现算。
    """
    p = ROOT / 'work' / 'english_overlap_words.json'
    if p.exists():
        return set(json.loads(p.read_text(encoding='utf-8')))
    base = ROOT / 'work' / 'english_baseline' / 'wcpFullEng.db'
    if not base.exists():
        raise RuntimeError('缺少英文同形词清单与基线，拒绝修改共享词库')
    con = sqlite3.connect(str(base))
    en = {r[0] for r in con.execute('SELECT word FROM pron').fetchall()}
    con.close()
    return en & set(words)


def backup(db: Path):
    BACKUP_DIR.mkdir(exist_ok=True)
    tag = hashlib.sha1(str(db.resolve()).lower().encode('utf-8')
                       ).hexdigest()[:6]
    if any(BACKUP_DIR.glob(f'{db.stem}.before_french_{tag}_*')):
        return None
    stamp = time.strftime('%Y%m%d_%H%M%S')
    dst = BACKUP_DIR / f'{db.stem}.before_french_{tag}_{stamp}{db.suffix}'
    shutil.copy2(db, dst)
    print('已备份 ->', dst.name)
    return dst


def content_matches(con, words, with_sentence):
    from collections import Counter
    wl = list(words)
    for start in range(0, len(wl), 500):
        chunk = wl[start:start + 500]
        placeholders = ','.join('?' for _ in chunk)
        actual = Counter(con.execute(
            f'SELECT word, ukPhonic, usPhonic, meaning FROM pron WHERE word IN ({placeholders})',
            chunk))
        expected = Counter((w, words[w]['phonic'], '', words[w]['meaning']) for w in chunk)
        if actual != expected:
            return False
        if with_sentence:
            actual = Counter(con.execute(
                f'SELECT word, sentences FROM sentence2 WHERE word IN ({placeholders})', chunk))
            expected = Counter((w, f'例句：{fr}（{zh}）')
                               for w in chunk for fr, zh in words[w]['sentences'])
            if actual != expected:
                return False
    return True


def patch(db: Path, words: dict, with_sentence: bool, force=False):
    if not words:
        return
    if not db.is_file():
        raise FileNotFoundError(db)
    if not force:
        with sqlite3.connect(db.as_uri() + '?mode=ro', uri=True) as con:
            if content_matches(con, words, with_sentence):
                print(f'{db.name}: 全量内容一致，跳过')
                return
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
                for fr, zh in words[w]['sentences']:
                    sents.append((w, f'例句：{fr}（{zh}）'))
            cur.executemany('INSERT INTO sentence2 (word, sentences) '
                            'VALUES (?,?)', sents)
            n_sent += len(sents)
    con.commit()
    con.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    con.close()
    print(f'{db.name}: pron +{n_pron}, sentence2 +{n_sent}; '
          f'共处理 {len(wl)} 词')


def main():
    require_game_closed()
    force = '--force' in sys.argv
    words = collect()
    overlap = load_overlap(words)
    skipped = sorted(set(words) & overlap)
    for w in skipped:
        del words[w]
    if skipped:
        print(f'跳过英法同形词 {len(skipped)} 个 (英文释义/例句保持原版, '
              '运行时由 FrWordListMod 按词书切换)')
    ex = sum(len(v['sentences']) for v in words.values())
    print(f'游戏目录 {wcp_paths.game_dir()}')
    print(f'汇总词条 {len(words)} (含例句 {ex})')
    patch(FULL, words, with_sentence=True, force=force)
    patch(ONLY, words, with_sentence=False, force=force)


if __name__ == '__main__':
    main()
