#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通用语言包物化器 —— 由 ``packs/<lang>/pack.build.json`` 驱动, 不含任何语言分支。

为什么放在这里
────────────
和同目录的 ``gen_bookprofiles.py`` 一样, 这是**跨项目**工具: 每种语言的 pack 数据
留在自己的项目里 (``French/packs/fr``、``Russian/packs/ru``…), 构建代码只有一份。
加一种语言 = 新增 ``<项目>/packs/<lang>/pack.build.json`` + 已有的 TSV 载荷与词书,
不需要改本文件, 更不需要为其它语言重编译 DLL —— 这正是宿主的
``strategy.assembly = "$host"`` 所依赖的"只提供资源"扩展点。

产物 (全部落在 ``packs/<lang>/`` 内, 宿主按 manifest 读取)
────────────────────────────────────────────────────────
  manifest.json         由 spec 生成 —— 清单不可能和数据漂移
  db/meaning.sqlite     pron(word PK, ukPhonic, usPhonic, meaning)
  db/sentences.json     {"schema": 1, "sentences": {word: [row, ...]}}
  db/repair.tsv         带标签的确定性自愈流 (pron + sentence 行)
  books/*.xlsx          词书分册 (身份指纹的来源)

三重身份校验 (任一不通过即拒绝生成)
──────────────────────────────────
  1. 载荷 TSV 的 sha256 必须与 payload manifest 声明的一致;
  2. 词书各分册 A 列的**并集去重**必须等于 spec 的 word_count/fingerprint_sha256;
  3. pron 的词集合必须与词书并集**完全相同** —— 释义缺词会让游戏回退到共享库
     (英语/其它语言), 多词则是夹带, 两者都是串词来源, 一律拒绝。

用法
────
  python tools/build_pack.py --spec ../French/packs/fr/pack.build.json --check
  python tools/build_pack.py --spec ../French/packs/fr/pack.build.json --write
  python tools/build_pack.py --check-all ..            # CI: 扫所有 <项目>/packs/*/
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import unicodedata
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

SPEC_NAME = "pack.build.json"
LANG_RE = re.compile(r"^[a-z][a-z0-9_]{1,15}$")
PROJECT_DIRS = ("Japanese", "French", "Russian", "German", "Contonese",
                "Spanish", "Portuguese", "Arabic", "korean")


# ── 与 pack 内部格式逐字节绑定的读写工具 ────────────────────────────────

def unescape(value: str) -> str:
    """载荷 TSV 里 \\t / \\n / \\\\ 是转义写法, 入库要还原成真实字符。"""
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


def escape(value: str) -> str:
    return (value or "").replace("\\", "\\\\").replace("\t", "\\t") \
                               .replace("\r", "").replace("\n", "\\n")


def read_tsv(path: Path, width: int):
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            line = line.rstrip("\r\n")
            if not line:
                continue
            fields = line.split("\t")
            if len(fields) != width:
                raise ValueError(f"{path.name}:{number}: 期望 {width} 列, 实际 {len(fields)} 列")
            rows.append(tuple(unescape(field) for field in fields))
    return rows


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


def normalize_word(value) -> str | None:
    if value is None:
        return None
    text = unicodedata.normalize("NFC", str(value)).strip()
    return text or None


def fingerprint_of(words) -> str:
    """与宿主 BookRegistry.FingerprintOf / gen_bookprofiles 逐字节一致。"""
    payload = "".join(word + "\n" for word in sorted(words))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ── spec ──────────────────────────────────────────────────────────────

REQUIRED_FIELDS = (
    "schema", "language", "profile_id", "display_name", "word_count",
    "fingerprint_sha256", "observed_slot", "es3_prefix", "strategy",
    "payload_dir", "pron", "sentences", "books",
)


def load_spec(spec_path: Path) -> dict:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    missing = [name for name in REQUIRED_FIELDS if name not in spec]
    if missing:
        raise SystemExit(f"{spec_path} 缺字段: {missing}")
    if spec["schema"] != 1:
        raise SystemExit(f"不支持的 spec schema: {spec['schema']}")
    language = str(spec["language"])
    if not LANG_RE.match(language):
        raise SystemExit(f"language 不是合法语言码: {language!r}")
    pack_dir = spec_path.parent
    if pack_dir.name != language:
        raise SystemExit(
            f"pack 目录名 {pack_dir.name!r} 与 language {language!r} 不一致")
    if pack_dir.parent.name != "packs":
        raise SystemExit(f"spec 必须位于 <项目>/packs/<language>/ 下: {spec_path}")
    slot = int(spec["observed_slot"])
    if slot < 0 or slot > 4:
        raise SystemExit(f"observed_slot 必须在 0..4 (0=未分配原生槽): {slot}")
    spec_fp = str(spec["fingerprint_sha256"])
    if len(spec_fp) != 64 or any(c not in "0123456789abcdef" for c in spec_fp):
        raise SystemExit(f"fingerprint_sha256 必须是小写十六进制 64 位: {spec_fp!r}")
    strategy = spec["strategy"]
    if not isinstance(strategy, dict) or not strategy.get("assembly") \
            or not strategy.get("type"):
        raise SystemExit("strategy 必须声明 assembly 与 type")
    if not spec["books"]:
        raise SystemExit("books 不能为空 —— 词书是身份指纹的唯一来源")
    return spec


def repo_root_of(spec_path: Path) -> Path:
    return spec_path.parent.parent.parent.resolve()


# ── 身份校验 ──────────────────────────────────────────────────────────

def book_words(book_path: Path, column: int) -> set:
    try:
        import openpyxl
    except ImportError as exc:  # pragma: no cover - 环境问题, 不是数据问题
        raise SystemExit(f"需要 openpyxl 才能读取词书: {exc}")
    if not book_path.is_file():
        raise SystemExit(f"词书不存在: {book_path}")
    sheet = openpyxl.load_workbook(str(book_path), read_only=True).active
    words = set()
    for row in sheet.iter_rows(values_only=True):
        if row is None or len(row) <= column:
            continue
        word = normalize_word(row[column])
        if word:
            words.add(word)
    return words


def check_payload_manifest(payload_dir: Path, spec: dict) -> dict:
    manifest_path = payload_dir / "manifest.json"
    if not manifest_path.is_file():
        raise SystemExit(f"载荷缺 manifest.json: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    declared = manifest.get("files") or {}
    for name in (spec["pron"], spec["sentences"]):
        want = declared.get(name)
        if not want:
            continue
        actual = sha256_file(payload_dir / name)
        if actual != want:
            raise SystemExit(f"载荷哈希不一致 {name}: manifest={want} 实际={actual}")
    return manifest


def declared_count(manifest: dict, names) -> int | None:
    for name in names:
        value = manifest.get(name)
        if isinstance(value, int):
            return value
    return None


# ── 物化 ──────────────────────────────────────────────────────────────

def materialize(spec_path: Path, out_dir: Path) -> dict:
    """把 spec 描述的语言包完整生成到 out_dir, 返回统计信息。"""
    spec = load_spec(spec_path)
    repo = repo_root_of(spec_path)
    payload_dir = (repo / spec["payload_dir"]).resolve()
    language = str(spec["language"])
    pron_columns = int(spec.get("pron_columns", 4))
    sentence_columns = int(spec.get("sentence_columns", 2))
    book_column = int(spec.get("book_word_column", 0))

    payload_manifest = check_payload_manifest(payload_dir, spec)
    pron = read_tsv(payload_dir / spec["pron"], pron_columns)
    sentences = read_tsv(payload_dir / spec["sentences"], sentence_columns)

    want_pron_rows = declared_count(payload_manifest, ("full_pron", "word_count", "only_pron"))
    if want_pron_rows is not None and len(pron) != want_pron_rows:
        raise SystemExit(f"{spec['pron']} 行数 {len(pron)} 与载荷声明 {want_pron_rows} 不一致")
    want_sentence_rows = declared_count(payload_manifest, ("full_sentences", "sentence_count"))
    if want_sentence_rows is not None and len(sentences) != want_sentence_rows:
        raise SystemExit(
            f"{spec['sentences']} 行数 {len(sentences)} 与载荷声明 {want_sentence_rows} 不一致")

    pron_words = [row[0] for row in pron]
    duplicates = len(pron_words) - len(set(pron_words))
    if duplicates:
        raise SystemExit(f"{spec['pron']} 有 {duplicates} 个重复词条")

    books = []
    book_union = set()
    seen_names = set()
    for entry in spec["books"]:
        source = (repo / entry).resolve()
        name = source.name
        if name in seen_names:
            raise SystemExit(f"词书分册重名, 无法在同一 pack 内共存: {name}")
        seen_names.add(name)
        words = book_words(source, book_column)
        if not words:
            raise SystemExit(f"词书 A 列为空: {source}")
        books.append((source, name, len(words)))
        book_union |= words

    if len(book_union) != int(spec["word_count"]):
        raise SystemExit(
            f"词书并集 {len(book_union)} 与 spec.word_count {spec['word_count']} 不一致")
    actual_fp = fingerprint_of(book_union)
    if actual_fp != spec["fingerprint_sha256"]:
        raise SystemExit(
            f"词书指纹不一致: spec={spec['fingerprint_sha256']} 实际={actual_fp}")

    pron_only = set(pron_words) - book_union
    book_only = book_union - set(pron_words)
    if pron_only or book_only:
        sample_pron = sorted(pron_only)[:5]
        sample_book = sorted(book_only)[:5]
        raise SystemExit(
            f"释义与词书不匹配 (释义多 {len(pron_only)} 例 {sample_pron}; "
            f"词书多 {len(book_only)} 例 {sample_book}) —— 缺词会让游戏回退共享库")

    db_dir = out_dir / "db"
    book_dir = out_dir / "books"
    db_dir.mkdir(parents=True, exist_ok=True)
    book_dir.mkdir(parents=True, exist_ok=True)

    temp_db = db_dir / "meaning.tmp.sqlite"
    if temp_db.exists():
        temp_db.unlink()
    connection = sqlite3.connect(str(temp_db))
    try:
        connection.execute(
            "CREATE TABLE pron (word TEXT PRIMARY KEY, ukPhonic TEXT, usPhonic TEXT, meaning TEXT)")
        connection.executemany("INSERT INTO pron VALUES (?, ?, ?, ?)", pron)
        connection.execute("CREATE INDEX ix_pron_word ON pron(word)")
        connection.commit()
    finally:
        connection.close()
    os.replace(str(temp_db), str(db_dir / "meaning.sqlite"))

    sentence_map: dict[str, list] = {}
    for word, sentence in sentences:
        sentence_map.setdefault(word, []).append(sentence)
    with (db_dir / "sentences.json").open("w", encoding="utf-8", newline="\n") as handle:
        json.dump({"schema": 1, "sentences": sentence_map}, handle,
                  ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")

    repair_rows = [("#", "schema=1", "kind", "word", "ukPhonic", "usPhonic", "value")]
    repair_rows.extend(("row", "pron", row[0], row[1], row[2], row[3], "") for row in pron)
    repair_rows.extend(("row", "sentence", word, "", "", "", sentence)
                       for word, sentence in sentences)
    write_tsv(db_dir / "repair.tsv", repair_rows)

    for source, name, _ in books:
        shutil.copy2(str(source), str(book_dir / name))

    missing_sentences = sorted(book_union - set(sentence_map))
    manifest = {
        "schema": 1,
        "profile_id": spec["profile_id"],
        "language": language,
        "display_name": spec["display_name"],
        "word_count": int(spec["word_count"]),
        "fingerprint_sha256": spec["fingerprint_sha256"],
        "observed_slot": int(spec["observed_slot"]),
        "es3_prefix": spec["es3_prefix"],
        "book_layout": spec.get("book_layout", "fragmented"),
        "strategy": {
            "assembly": spec["strategy"]["assembly"],
            "type": spec["strategy"]["type"],
        },
        "resources": {
            "books": ["books/" + name for _, name, _ in books],
            "meaning_db": "db/meaning.sqlite",
            "sentence_table": "db/sentences.json",
            "repair": "db/repair.tsv",
            "word_audio": "audio/word/",
            "sentence_audio": "audio/sentence/",
        },
        "repair_probes": list(spec.get("repair_probes", [])),
        "source": {
            "payload_dir": spec["payload_dir"],
            "pron": spec["pron"],
            "sentences": spec["sentences"],
            "payload_files": payload_manifest.get("files", {}),
        },
        "book_sha256": {name: sha256_file(source) for source, name, _ in books},
        "counts": {
            "pron": len(pron),
            "sentence_rows": len(sentences),
            "sentence_words": len(sentence_map),
            "words_without_sentences": len(missing_sentences),
        },
        "notes": list(spec.get("notes", [])),
    }
    with (out_dir / "manifest.json").open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    return {
        "spec": spec,
        "pack_dir": spec_path.parent,
        "out_dir": out_dir,
        "pron": len(pron),
        "sentence_rows": len(sentences),
        "sentence_words": len(sentence_map),
        "words_without_sentences": len(missing_sentences),
        "book_rows": {name: count for _, name, count in books},
        "files": ["manifest.json", "db/meaning.sqlite", "db/sentences.json",
                  "db/repair.tsv"] + ["books/" + name for _, name, _ in books],
    }


def compare(pack_dir: Path, built_dir: Path, files) -> list:
    diffs = []
    for rel in files:
        want = built_dir / rel
        have = pack_dir / rel
        if not have.is_file():
            diffs.append((rel, "缺失", None, sha256_file(want) if want.is_file() else None))
            continue
        if sha256_file(have) != sha256_file(want):
            diffs.append((rel, "内容不一致", sha256_file(have), sha256_file(want)))
    return diffs


def apply_pack(pack_dir: Path, built_dir: Path, files, force: bool) -> None:
    existing = [rel for rel in files if (pack_dir / rel).exists()]
    if existing and not force:
        raise SystemExit(
            "拒绝覆盖已存在的包文件 (加 --force 强制重建): " + ", ".join(sorted(existing)))
    for rel in files:
        source = built_dir / rel
        target = pack_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(str(source), str(target))


def run_one(spec_path: Path, write: bool, force: bool) -> bool:
    pack_dir = spec_path.parent
    # 临时目录必须和目标在同一个卷上: os.replace 不支持跨卷 (Windows 的 C: -> D:)。
    built = Path(tempfile.mkdtemp(prefix=".pack-build-", dir=str(pack_dir)))
    try:
        info = materialize(spec_path, built)
        diffs = compare(pack_dir, built, info["files"])
        spec = info["spec"]
        print(f"[{spec['language']}] {pack_dir}")
        print(f"  词书并集 {spec['word_count']} 词 / 指纹 OK；释义 {info['pron']} 条；"
              f"例句 {info['sentence_rows']} 行 / {info['sentence_words']} 词")
        print(f"  无例句词条: {info['words_without_sentences']}；分册: "
              + ", ".join(f"{k}={v}" for k, v in info["book_rows"].items()))
        if write:
            apply_pack(pack_dir, built, info["files"], force)
            print(f"  已写入 {len(info['files'])} 个文件")
            return True
        if not diffs:
            print("  与磁盘上的包逐字节一致")
            return True
        for rel, reason, have, want in diffs:
            print(f"  差异 {rel}: {reason} 现有={str(have)[:12]} 期望={str(want)[:12]}")
        print("  提示: 加 --write --force 重建")
        return False
    finally:
        shutil.rmtree(str(built), ignore_errors=True)


def find_specs(root: Path) -> list:
    out = []
    for name in PROJECT_DIRS:
        packs = root / name / "packs"
        if not packs.is_dir():
            continue
        out.extend(sorted(packs.glob(f"*/{SPEC_NAME}")))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="按 pack.build.json 物化语言包")
    parser.add_argument("--spec", help=f"<项目>/packs/<lang>/{SPEC_NAME}")
    parser.add_argument("--check-all", metavar="INTEGRATION_ROOT",
                        help="检查所有 <项目>/packs/*/pack.build.json 是否与磁盘一致")
    parser.add_argument("--write", action="store_true", help="写入包文件")
    parser.add_argument("--check", action="store_true", help="只比对, 不写入 (默认)")
    parser.add_argument("--force", action="store_true", help="允许覆盖已存在的包文件")
    args = parser.parse_args()

    if args.check_all:
        specs = find_specs(Path(args.check_all).resolve())
        if not specs:
            print("没有找到任何 pack.build.json")
            return 0
        ok = True
        for spec_path in specs:
            ok = run_one(spec_path, write=False, force=False) and ok
        print("结果:", "PASS" if ok else "FAIL")
        return 0 if ok else 1

    if not args.spec:
        parser.error("需要 --spec 或 --check-all")
    ok = run_one(Path(args.spec).resolve(), write=args.write, force=args.force)
    if args.write:
        return 0
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
