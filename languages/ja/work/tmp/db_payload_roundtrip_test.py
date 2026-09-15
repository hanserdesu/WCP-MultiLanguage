# -*- coding: utf-8 -*-
"""在临时副本中验证 jp_db_payload 可恢复被更新覆盖的词条，不写游戏数据库。"""
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

GAME = Path(os.environ.get(
    "WCP_GAME_DIR", r"E:\Steam\steamapps\common\WCP-WordGirlgriend"))
PACK = Path(os.environ.get(
    "WCP_LOCALLOW", os.path.expanduser("~") + r"\AppData\LocalLow\WCP\wcp")) / "jp_db_payload"


def unescape(value):
    out = []
    i = 0
    while i < len(value):
        if value[i] == "\\" and i + 1 < len(value):
            nxt = value[i + 1]
            if nxt == "n":
                out.append("\n")
                i += 2
                continue
            if nxt == "t":
                out.append("\t")
                i += 2
                continue
            if nxt == "\\":
                out.append("\\")
                i += 2
                continue
        out.append(value[i])
        i += 1
    return "".join(out)


def rows(name, width):
    result = []
    for line in (PACK / name).read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        assert len(parts) == width, (name, len(parts), line[:80])
        result.append(tuple(unescape(p) for p in parts))
    return result


def words(records):
    return sorted({r[0] for r in records})


def delete_rows(con, table, keys):
    for start in range(0, len(keys), 400):
        batch = keys[start:start + 400]
        con.execute("DELETE FROM %s WHERE word IN (%s)" %
                    (table, ",".join("?" for _ in batch)), batch)


def restore(full, only):
    pron = rows("jp_pron.tsv", 4)
    sent = rows("jp_sentences.tsv", 2)
    only_pron = rows("jp_only_pron.tsv", 4)
    con = sqlite3.connect(full)
    try:
        delete_rows(con, "pron", words(pron))
        delete_rows(con, "sentence2", words(sent))
        con.executemany(
            "INSERT INTO pron (word, ukPhonic, usPhonic, meaning) VALUES (?,?,?,?)",
            pron)
        con.executemany("INSERT INTO sentence2 (word, sentences) VALUES (?,?)", sent)
        con.commit()
    finally:
        con.close()
    con = sqlite3.connect(only)
    try:
        delete_rows(con, "pron", words(only_pron))
        con.executemany(
            "INSERT INTO pron (word, ukPhonic, usPhonic, meaning) VALUES (?,?,?,?)",
            only_pron)
        con.commit()
    finally:
        con.close()
    return pron, sent, only_pron


def count(con, table, records):
    keys = words(records)
    total = 0
    for start in range(0, len(keys), 400):
        batch = keys[start:start + 400]
        total += con.execute("SELECT COUNT(*) FROM %s WHERE word IN (%s)" %
                             (table, ",".join("?" for _ in batch)), batch).fetchone()[0]
    return total


with tempfile.TemporaryDirectory(prefix="jp-payload-") as temp:
    temp = Path(temp)
    source = GAME / "wcp_Data" / "StreamingAssets"
    full = temp / "wcpFullEng.db"
    only = temp / "wcpOnlyWord.db"
    shutil.copy2(source / full.name, full)
    shutil.copy2(source / only.name, only)
    pron, sent, only_pron = restore(full, only)
    con = sqlite3.connect(full)
    try:
        p = count(con, "pron", pron)
        s = count(con, "sentence2", sent)
        probes = [con.execute("SELECT COUNT(*) FROM pron WHERE word=?", (w,)).fetchone()[0]
                  for w in ("歯医者", "続ける", "工業")]
    finally:
        con.close()
    con = sqlite3.connect(only)
    try:
        o = count(con, "pron", only_pron)
    finally:
        con.close()
    assert p == len(pron), (p, len(pron))
    assert s == len(sent), (s, len(sent))
    assert o == len(only_pron), (o, len(only_pron))
    assert probes == [1, 1, 1], probes
    print("PASS: 临时库恢复 FullEng pron=%d sentence2=%d OnlyWord pron=%d probes=%s" %
          (p, s, o, probes))
