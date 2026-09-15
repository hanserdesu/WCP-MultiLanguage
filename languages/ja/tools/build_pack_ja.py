"""Materialize the Japanese pack data from the verified DB payload.

The source payload is the read-only export produced by
``wcp_wordbooks/tools/export_jp_db_payload.py``.  The pack gets:

* ``db/meaning.sqlite`` — one isolated ``pron`` table;
* ``db/sentences.json`` — ``{"schema": 1, "sentences": {word: [rows]}}``;
* ``db/repair.tsv`` — a tagged, deterministic repair stream containing both
  pron and sentence rows;
* the canonical Japanese workbook under ``books/``.

No game database is opened or modified by this script.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / "wcp_wordbooks" / "output" / "jp_db_payload"
BOOK = ROOT / "wcp_wordbooks" / "output" / "import" / "日语词库(猫条版).xlsx"
PACK = ROOT / "packs" / "ja"


def unescape(value: str) -> str:
    out = []
    i = 0
    while i < len(value):
        if value[i] != "\\" or i + 1 >= len(value):
            out.append(value[i])
            i += 1
            continue
        code = value[i + 1]
        out.append({"t": "\t", "n": "\n", "r": "\r", "\\": "\\"}.get(code, code))
        i += 2
    return "".join(out)


def read_tsv(path: Path, width: int):
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            line = line.rstrip("\r\n")
            if not line:
                continue
            fields = line.split("\t")
            if len(fields) != width:
                raise ValueError(f"{path.name}:{number}: expected {width} fields, got {len(fields)}")
            rows.append(tuple(unescape(field) for field in fields))
    return rows


def escape(value: str) -> str:
    return (value or "").replace("\\", "\\\\").replace("\t", "\\t").replace("\r", "").replace("\n", "\\n")


def write_tsv(path: Path, rows) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write("\t".join(escape(value) for value in row) + "\n")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build(force: bool) -> None:
    pron_source = PAYLOAD / "jp_pron.tsv"
    sentence_source = PAYLOAD / "jp_sentences.tsv"
    for source in (pron_source, sentence_source, BOOK):
        if not source.is_file():
            raise FileNotFoundError(str(source))

    db_dir = PACK / "db"
    book_dir = PACK / "books"
    audio_word = PACK / "audio" / "word"
    audio_sentence = PACK / "audio" / "sentence"
    for directory in (db_dir, book_dir, audio_word, audio_sentence):
        directory.mkdir(parents=True, exist_ok=True)

    target_db = db_dir / "meaning.sqlite"
    target_json = db_dir / "sentences.json"
    target_repair = db_dir / "repair.tsv"
    targets = (target_db, target_json, target_repair, book_dir / BOOK.name)
    if not force:
        existing = [str(path) for path in targets if path.exists()]
        if existing:
            raise FileExistsError("refusing to overwrite existing pack files: " + ", ".join(existing))

    pron = read_tsv(pron_source, 4)
    sentences = read_tsv(sentence_source, 2)
    source_manifest = json.loads((PAYLOAD / "manifest.json").read_text(encoding="utf-8"))
    expected = source_manifest.get("files", {})
    for source in (pron_source, sentence_source):
        expected_hash = expected.get(source.name)
        if expected_hash and sha256_file(source) != expected_hash:
            raise ValueError(f"payload hash mismatch: {source}")
    if len(pron) != source_manifest.get("full_pron"):
        raise ValueError("jp_pron.tsv row count does not match payload manifest")
    if len(sentences) != source_manifest.get("full_sentences"):
        raise ValueError("jp_sentences.tsv row count does not match payload manifest")
    words = [row[0] for row in pron]
    if len(words) != len(set(words)):
        raise ValueError("jp_pron.tsv contains duplicate words")

    temp_db = target_db.with_suffix(".tmp.sqlite")
    if temp_db.exists():
        temp_db.unlink()
    connection = sqlite3.connect(str(temp_db))
    try:
        connection.execute(
            "CREATE TABLE pron (word TEXT PRIMARY KEY, ukPhonic TEXT, usPhonic TEXT, meaning TEXT)"
        )
        connection.executemany("INSERT INTO pron VALUES (?, ?, ?, ?)", pron)
        connection.execute("CREATE INDEX ix_pron_word ON pron(word)")
        connection.commit()
    finally:
        connection.close()
    if target_db.exists():
        target_db.unlink()
    os.replace(str(temp_db), str(target_db))

    sentence_map = {}
    for word, sentence in sentences:
        sentence_map.setdefault(word, []).append(sentence)
    with target_json.open("w", encoding="utf-8") as handle:
        json.dump({"schema": 1, "sentences": sentence_map}, handle,
                  ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")

    repair_rows = [("#", "schema=1", "kind", "word", "ukPhonic", "usPhonic", "value")]
    repair_rows.extend(("row", "pron", word, uk, us, meaning, "")
                       for word, uk, us, meaning in pron)
    repair_rows.extend(("row", "sentence", word, "", "", "", sentence)
                       for word, sentence in sentences)
    write_tsv(target_repair, repair_rows)
    shutil.copy2(str(BOOK), str(book_dir / BOOK.name))

    print("pack:", PACK)
    print("pron:", len(pron), "sentences:", len(sentences),
          "sentence_words:", len(sentence_map))
    print("meaning.sqlite:", target_db.stat().st_size)
    print("sentences.json:", target_json.stat().st_size)
    print("repair.tsv:", target_repair.stat().st_size)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="overwrite only the four generated pack files")
    build(parser.parse_args().force)
