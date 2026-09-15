# -*- coding: utf-8 -*-
"""将旧版共享目录中仍属于俄语词书的音频复制到俄语私有目录。

这是一次性、只增不删且不覆盖的迁移工具。它只按俄语词书和句子清单
计算目标文件名，不会把共享目录中的其它语言音频整体复制过去。
"""
import argparse
import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WCP_ROOT = Path.home() / "AppData" / "LocalLow" / "WCP"
PRIVATE_ROOT = WCP_ROOT / "wcp"


def copy_missing(source: Path, target: Path, names: list[str], dry_run: bool) -> tuple[int, int]:
    copied = 0
    missing = 0
    if not dry_run:
        target.mkdir(parents=True, exist_ok=True)
    for name in names:
        src = source / name
        dst = target / name
        if dst.exists():
            continue
        if not src.exists():
            missing += 1
            continue
        if not dry_run:
            shutil.copy2(src, dst)
        copied += 1
    return copied, missing


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    books = json.loads((ROOT / "output" / "russian_books.json").read_text(encoding="utf-8"))
    words = [w["word"] + ".mp3" for level in books["levels"].values() for w in level]
    master = json.loads((ROOT / "data" / "translations" / "sentences_master.json").read_text(encoding="utf-8"))
    sentences = sorted({ru for pairs in master.values() for ru, _ in pairs})
    sentence_names = [hashlib.md5(ru.encode("utf-8")).hexdigest() + ".mp3" for ru in sentences]

    word_copied, word_missing = copy_missing(
        WCP_ROOT / "vocabulary", PRIVATE_ROOT / "ru_word_audio", words, args.dry_run
    )
    sentence_copied, sentence_missing = copy_missing(
        PRIVATE_ROOT / "sentence_audio", PRIVATE_ROOT / "ru_sentence_audio", sentence_names, args.dry_run
    )
    mode = "dry-run" if args.dry_run else "migrated"
    print(f"{mode}: word aliases copied={word_copied}, unresolved_shared={word_missing}")
    print(f"{mode}: sentence aliases copied={sentence_copied}, unresolved_shared={sentence_missing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
