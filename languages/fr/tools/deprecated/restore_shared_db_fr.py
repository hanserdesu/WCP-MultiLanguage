# -*- coding: utf-8 -*-
"""从法语写入前备份精确还原共享游戏词典中的所有法语词形。

``wcpFullEng.db`` / ``wcpOnlyWord.db`` 是全词书共享数据，不能再存法语书
内容。本脚本只处理法语书的 8,116 个词：备份中原有的记录逐行恢复，备份中
没有的记录删除；绝不复制整库，也不改动其它词形。写入前会建立可恢复快照。
"""
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
import wcp_paths

ROOT = Path(__file__).resolve().parent.parent
BACKUPS = ROOT / 'backups'


def game_running() -> bool:
    result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq wcp.exe'],
                            capture_output=True, text=True, errors='replace')
    return 'wcp.exe' in result.stdout.lower()


def french_words() -> list[str]:
    books = json.loads((ROOT / 'output' / 'french_books.json').read_text(
        encoding='utf-8'))
    return [item['word'] for level in ('a1', 'a2', 'b1', 'b2')
            for item in books['levels'][level]]


def source_backup(stem: str) -> Path:
    hits = sorted(BACKUPS.glob(f'{stem}.before_french_*_*.db'))
    if not hits:
        raise FileNotFoundError(f'找不到 {stem} 的法语写入前备份')
    return hits[0]


def snapshot(db: Path) -> Path:
    tag = hashlib.sha1(str(db.resolve()).lower().encode('utf-8')).hexdigest()[:6]
    target = BACKUPS / f'{db.stem}.before_full_fr_restore_{tag}_{time.strftime("%Y%m%d_%H%M%S")}{db.suffix}'
    shutil.copy2(db, target)
    return target


def columns(con: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in con.execute(f'PRAGMA table_info({table})')]


def rows_by_word(con: sqlite3.Connection, table: str, words: list[str]) -> dict[str, list[tuple]]:
    """批量读取，避免对大词典进行 8,116 次全表扫描。"""
    found: dict[str, list[tuple]] = {}
    for start in range(0, len(words), 500):
        chunk = words[start:start + 500]
        marks = ','.join('?' for _ in chunk)
        for row in con.execute(
                f'SELECT rowid, * FROM {table} WHERE word IN ({marks}) ORDER BY word, rowid',
                chunk):
            found.setdefault(row[1], []).append(row[1:])
    return found


def restore_table(current: Path, baseline: Path, table: str, words: list[str]) -> int:
    with sqlite3.connect(baseline) as before, sqlite3.connect(current, timeout=60) as now:
        cols = columns(now, table)
        if cols != columns(before, table) or 'word' not in cols:
            raise RuntimeError(f'{current.name}:{table} 的表结构与备份不一致')
        now.execute('PRAGMA busy_timeout=60000')
        before_rows = rows_by_word(before, table, words)
        current_rows = rows_by_word(now, table, words)
        changed_words = [word for word in words
                         if before_rows.get(word, []) != current_rows.get(word, [])]
        if not changed_words:
            return 0
        now.execute('BEGIN IMMEDIATE')
        placeholders = ','.join('?' for _ in cols)
        # sentence2 的 word 列没有索引。按 500 个词批量删除而不是逐词删除，
        # 否则会对整张表执行数千次扫描。
        for start in range(0, len(changed_words), 500):
            chunk = changed_words[start:start + 500]
            marks = ','.join('?' for _ in chunk)
            now.execute(f'DELETE FROM {table} WHERE word IN ({marks})', chunk)
        restored = [row for word in changed_words for row in before_rows.get(word, [])]
        if restored:
            now.executemany(
                f'INSERT INTO {table} ({",".join(cols)}) VALUES ({placeholders})', restored)
        now.commit()
    return len(changed_words)


def verify_table(current: Path, baseline: Path, table: str, words: list[str]) -> list[str]:
    with sqlite3.connect(baseline) as before, sqlite3.connect(current) as now:
        old = rows_by_word(before, table, words)
        new = rows_by_word(now, table, words)
        return [word for word in words if old.get(word, []) != new.get(word, [])]


def main() -> None:
    if game_running():
        raise SystemExit('wcp.exe 正在运行；为避免游戏覆盖或锁定数据库，未作修改。')
    words = french_words()
    full, only = wcp_paths.full_db(), wcp_paths.only_db()
    jobs = ((full, source_backup('wcpFullEng'), ('pron', 'sentence2')),
            (only, source_backup('wcpOnlyWord'), ('pron',)))
    for current, baseline, tables in jobs:
        if not current.exists():
            raise FileNotFoundError(f'游戏数据库不存在: {current}')
        print(f'备份 {current.name} -> {snapshot(current).name}')
        for table in tables:
            changed = restore_table(current, baseline, table, words)
            bad = verify_table(current, baseline, table, words)
            if bad:
                raise RuntimeError(f'{current.name}:{table} 回读失败 {len(bad)} 词，例如 {bad[:3]}')
            print(f'{current.name}:{table} 已还原 {changed} 个法语词形；回读 PASS')


if __name__ == '__main__':
    main()
