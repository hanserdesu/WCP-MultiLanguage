# -*- coding: utf-8 -*-
"""还原被法语补丁覆盖的英法同形词 (一次性数据修复, 2026-09-13)。

背景 (2026-09-13 已在 D:/ATooManyLanguage/French 执行一次):
  法语 8116 词中有 1638 个与英语原库同形 (table/zoom/vote/...)。
  patch_local_db_fr.py 直接 DELETE+INSERT, 把这些词的英文释义/例句
  覆盖成了法语。日语词库用假名, 与英语零重叠, 没有此问题。

本脚本把 1638 个同形词的 pron/sentence2 恢复为英文原版
(数据源: work/english_baseline/ 下法语灌库前的原始库)。
法语独有词 (6478 个) 不动 — 它们不在英文库里, 无冲突。

配套策略 (book-scoped switching, 已实现):
  * patch_local_db_fr.py / export_fr_db_payload.py 同步改为跳过同形词;
  * 运行时 FrWordListMod 按当前词书在同形词上双向切换英/法内容,
    离线自愈 payload 同时携带两套基线。

严格模式:
  当前库里同形词内容若既不等于英文基线也不等于法语补丁 (说明有
  未知来源的第三方改动), 本脚本立即中止, 不做任何写入。

用法: python tools/restore_english_overlap_fr.py [--dry-run]
"""
import json
import shutil
import sqlite3
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
import wcp_paths

ROOT = Path(__file__).resolve().parent.parent
OVERLAP_JSON = ROOT / 'work' / 'english_overlap_words.json'
BASE_DIR = ROOT / 'work' / 'english_baseline'
BACKUP_DIR = ROOT / 'backups'


def load_overlap():
    if OVERLAP_JSON.exists():
        return set(json.loads(OVERLAP_JSON.read_text(encoding='utf-8')))
    # 兜底: 用英文基线 pron 与法语词表求交集
    books = json.loads((ROOT / 'output' / 'french_books.json').read_text(
        encoding='utf-8'))
    fr = set()
    for lv in ('a1', 'a2', 'b1', 'b2'):
        fr |= {w['word'] for w in books['levels'][lv]}
    con = sqlite3.connect(str(BASE_DIR / 'wcpFullEng.db'))
    ov = {r[0] for r in con.execute('SELECT word FROM pron').fetchall()} & fr
    con.close()
    return ov


def load_en_pron(db: Path):
    con = sqlite3.connect(str(db))
    d = {r[0]: (r[1], r[2], r[3]) for r in con.execute(
        'SELECT word, ukPhonic, usPhonic, meaning FROM pron')}
    con.close()
    return d


def load_en_sentences(db: Path):
    con = sqlite3.connect(str(db))
    d = {}
    for w, s in con.execute('SELECT word, sentences FROM sentence2'):
        d.setdefault(w, []).append(s)
    con.close()
    return d


def load_cur_pron(db: Path, words):
    con = sqlite3.connect(str(db))
    ph = ','.join('?' * len(words))
    d = {r[0]: (r[1], r[2], r[3]) for r in con.execute(
        f'SELECT word, ukPhonic, usPhonic, meaning FROM pron '
        f'WHERE word IN ({ph})', list(words))}
    con.close()
    return d


def load_cur_sentences(db: Path, words):
    con = sqlite3.connect(str(db))
    ph = ','.join('?' * len(words))
    d = {}
    for w, s in con.execute(
            f'SELECT word, sentences FROM sentence2 WHERE word IN ({ph})',
            list(words)):
        d.setdefault(w, []).append(s)
    con.close()
    return d


def backup(db: Path):
    BACKUP_DIR.mkdir(exist_ok=True)
    stamp = time.strftime('%Y%m%d_%H%M%S')
    dst = BACKUP_DIR / f'{db.stem}.before_overlap_restore_{stamp}{db.suffix}'
    shutil.copy2(db, dst)
    print('已备份 ->', dst.name)
    return dst


def classify(cur, en_val, fr_meaning):
    """返回 'en' | 'fr' | 'unknown'。sentences 为空视为 en 已还原。"""
    m = cur[2] if cur else None
    if cur is None:
        return 'unknown'
    if cur == en_val:
        return 'en'
    if fr_meaning is not None and m == fr_meaning:
        return 'fr'
    return 'unknown'


def main():
    dry = '--dry-run' in sys.argv
    overlap = load_overlap()
    print(f'同形词: {len(overlap)}')
    en_pron_full = load_en_pron(BASE_DIR / 'wcpFullEng.db')
    en_pron_only = load_en_pron(BASE_DIR / 'wcpOnlyWord.db')
    en_sent = load_en_sentences(BASE_DIR / 'wcpFullEng.db')

    full = wcp_paths.full_db()
    only = wcp_paths.only_db()

    # 法语补丁 meaning 判定依据: french_books.json 的 meaning 格式
    books = json.loads((ROOT / 'output' / 'french_books.json').read_text(
        encoding='utf-8'))
    fr_meaning = {}
    for lv in ('a1', 'a2', 'b1', 'b2'):
        for w in books['levels'][lv]:
            if w['word'] in overlap:
                fr_meaning[w['word']] = f"{w['zh']}〈{w['pos']}〉"

    cur_full = load_cur_pron(full, overlap)
    cur_only = load_cur_pron(only, overlap)
    cur_sent = load_cur_sentences(full, overlap)

    to_fix_full, to_fix_only, unknown = [], [], []
    for w in overlap:
        en_f = en_pron_full.get(w)
        en_o = en_pron_only.get(w)
        fm = fr_meaning.get(w)
        s_full = classify(cur_full.get(w), en_f, fm)
        s_only = classify(cur_only.get(w), en_o, fm)
        if s_full == 'unknown' or s_only == 'unknown':
            unknown.append(w)
            continue
        if s_full == 'fr':
            to_fix_full.append(w)
        if s_only == 'fr':
            to_fix_only.append(w)

    sent_diff = []
    for w in overlap:
        if w not in en_sent:
            continue
        if sorted(cur_sent.get(w, [])) != sorted(en_sent[w]):
            sent_diff.append(w)

    print(f'FullEng 需还原 pron: {len(to_fix_full)}, '
          f'OnlyWord 需还原 pron: {len(to_fix_only)}, '
          f'FullEng 需还原 sentence2: {len(sent_diff)}, '
          f'未知状态: {len(unknown)}')
    if unknown:
        print('未知状态样例:', unknown[:10])
        print('严格模式下中止 (第三方改动, 请人工确认)')
        sys.exit(2)
    if not to_fix_full and not to_fix_only and not sent_diff:
        print('同形词已全部为英文原版, 无需修复')
        return
    if dry:
        print('(dry-run) 不写入')
        return

    backup(full)
    backup(only)

    con = sqlite3.connect(str(full), timeout=60)
    con.execute('PRAGMA busy_timeout=60000')
    cur = con.cursor()
    cur.execute('BEGIN')
    for w in to_fix_full:
        uk, us, m = en_pron_full[w]
        cur.execute('UPDATE pron SET ukPhonic=?, usPhonic=?, meaning=? '
                    'WHERE word=?', (uk, us, m, w))
    for w in sent_diff:
        cur.execute('DELETE FROM sentence2 WHERE word=?', (w,))
        for s in en_sent[w]:
            cur.execute('INSERT INTO sentence2 (word, sentences) VALUES (?,?)',
                        (w, s))
    con.commit()
    con.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    con.close()

    con = sqlite3.connect(str(only), timeout=60)
    con.execute('PRAGMA busy_timeout=60000')
    cur = con.cursor()
    cur.execute('BEGIN')
    for w in to_fix_only:
        uk, us, m = en_pron_only[w]
        cur.execute('UPDATE pron SET ukPhonic=?, usPhonic=?, meaning=? '
                    'WHERE word=?', (uk, us, m, w))
    con.commit()
    con.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    con.close()

    # 回读校验
    v_full = load_cur_pron(full, overlap)
    v_only = load_cur_pron(only, overlap)
    v_sent = load_cur_sentences(full, overlap)
    bad_p = [w for w in overlap if v_full.get(w) != en_pron_full.get(w)]
    bad_o = [w for w in overlap if v_only.get(w) != en_pron_only.get(w)]
    bad_s = [w for w in en_sent
             if sorted(v_sent.get(w, [])) != sorted(en_sent[w])]
    ok = not (bad_p or bad_o or bad_s)
    print('校验 FullEng pron:', 'PASS' if not bad_p else f'FAIL {len(bad_p)}')
    print('校验 OnlyWord pron:', 'PASS' if not bad_o else f'FAIL {len(bad_o)}')
    print('校验 FullEng sentence2:', 'PASS' if not bad_s else f'FAIL {len(bad_s)}')
    print('总体:', 'ALL PASS' if ok else '存在失败项')
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
