# -*- coding: utf-8 -*-
"""把被法语补丁覆盖的英法同形词从备份库还原为英文原版。

背景 (2026-09-13): patch_local_db_fr.py 把全部 8116 个法语词写进共享
wcpFullEng.db / wcpOnlyWord.db。法语是拉丁字母, 其中 1638 个词形与英语
原词完全同形 (accord/table/ring/...), 直接覆盖了英文释义+音标+例句,
违反「法语词书不影响其它词书」原则。

本脚本:
  1. 对比备份库(写法语前)与当前库, 找出被覆盖的同形词
  2. 把它们的 pron / sentence2 逐词还原为备份库里的英文原版
  3. 法语独有的 6478 词不动 (英语词书查不到它们, 不冲突)
  4. 写前自动备份当前库; 幂等 (已还原的词跳过)

用法: python tools/restore_english_overlap_fr.py
"""
import hashlib
import shutil
import sqlite3
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
import wcp_paths

ROOT = Path(__file__).resolve().parent.parent
BACKUP_DIR = ROOT / 'backups'


def find_backup():
    hits = sorted(BACKUP_DIR.glob('wcpFullEng.before_french_*_*.db'))
    if not hits:
        print('找不到法语前备份库:', BACKUP_DIR)
        sys.exit(1)
    return hits[0]


def snapshot(db: Path):
    tag = hashlib.sha1(str(db.resolve()).lower().encode('utf-8')).hexdigest()[:6]
    stamp = time.strftime('%Y%m%d_%H%M%S')
    dst = BACKUP_DIR / f'{db.stem}.before_restore_{tag}_{stamp}{db.suffix}'
    shutil.copy2(db, dst)
    print('已备份 ->', dst.name)
    return dst


def load(db, table):
    con = sqlite3.connect(str(db))
    cur = con.cursor()
    d = {}
    if table == 'pron':
        for w, uk, us, m in cur.execute(
                'SELECT word, ukPhonic, usPhonic, meaning FROM pron'):
            d[w] = (uk, us, m)
    else:
        for w, s in cur.execute('SELECT word, sentences FROM sentence2'):
            d.setdefault(w, []).append(s)
    con.close()
    return d


def main():
    before_full = find_backup()
    before_only = BACKUP_DIR / before_full.name.replace('wcpFullEng',
                                                       'wcpOnlyWord')
    if not before_only.exists():
        # 只库的备份可能独立命名, 找对应文件
        before_only = None
        for p in BACKUP_DIR.glob('wcpOnlyWord.before_french_*_*.db'):
            before_only = p
            break
    if before_only is None:
        print('找不到 wcpOnlyWord 法语前备份')
        sys.exit(1)

    full = wcp_paths.full_db()
    only = wcp_paths.only_db()

    b_pron = load(before_full, 'pron')
    n_pron = load(full, 'pron')
    overlap = [w for w in n_pron if w in b_pron and b_pron[w] != n_pron[w]]
    print(f'被覆盖的同形词: {len(overlap)}')

    b_sent = load(before_full, 'sentence2')
    n_sent = load(full, 'sentence2')
    sent_overlap = [w for w in n_sent if w in b_sent and b_sent[w] != n_sent[w]]
    print(f'例句被覆盖的同形词: {len(sent_overlap)}')

    if not overlap and not sent_overlap:
        print('没有需要还原的词, 完成')
        return

    for db, table, words in ((full, 'pron', overlap),
                             (full, 'sentence2', sent_overlap),
                             (only, 'pron', overlap)):
        snapshot(db)
        con = sqlite3.connect(str(db), timeout=60)
        con.execute('PRAGMA busy_timeout=60000')
        cur = con.cursor()
        cur.execute('BEGIN')
        if table == 'pron':
            for w in words:
                uk, us, m = b_pron[w]
                cur.execute('UPDATE pron SET ukPhonic=?, usPhonic=?, meaning=? '
                            'WHERE word=?', (uk, us, m, w))
        else:
            for w in words:
                cur.execute('DELETE FROM sentence2 WHERE word=?', (w,))
                for s in b_sent[w]:
                    cur.execute('INSERT INTO sentence2 (word, sentences) '
                                'VALUES (?,?)', (w, s))
        con.commit()
        con.close()
        print(f'{db.name} {table}: 还原 {len(words)} 词')

    # 校验: 同形词现在应等于备份库英文原版
    v_pron = load(full, 'pron')
    bad = [w for w in overlap if v_pron.get(w) != b_pron.get(w)]
    v_sent = load(full, 'sentence2')
    bad_s = [w for w in sent_overlap if v_sent.get(w) != b_sent.get(w)]
    print('校验: pron', 'PASS' if not bad else f'FAIL {len(bad)}',
          '| sentence2', 'PASS' if not bad_s else f'FAIL {len(bad_s)}')
    sys.exit(1 if (bad or bad_s) else 0)


if __name__ == '__main__':
    main()
