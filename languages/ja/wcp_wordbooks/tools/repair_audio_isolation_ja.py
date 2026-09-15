# -*- coding: utf-8 -*-
"""只增不删地把日语单词音频从历史共享目录分流到 ja pack。"""
import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WCP = Path.home() / "AppData" / "LocalLow" / "WCP"
SOURCE = WCP / "vocabulary"
TARGET = WCP / "packs" / "ja" / "audio" / "word"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    import sys
    sys.path.insert(0, str(ROOT / "tools"))
    from patch_local_db import collect

    words = sorted(collect())
    if not SOURCE.is_dir():
        raise FileNotFoundError(SOURCE)
    if not args.dry_run:
        TARGET.mkdir(parents=True, exist_ok=True)

    copied = present = missing = 0
    for word in words:
        found = None
        for suffix in (".mp3", ".wav"):
            candidate = SOURCE / (word + suffix)
            if candidate.is_file() and candidate.stat().st_size > 1000:
                found = candidate
                break
        if found is None:
            missing += 1
            continue
        destination = TARGET / found.name
        if destination.is_file() and destination.stat().st_size > 1000:
            present += 1
            continue
        if not args.dry_run:
            shutil.copy2(found, destination)
        copied += 1

    print("Japanese word audio isolation:")
    print("  words:", len(words))
    print("  present:", present, "copyable:", copied, "missing:", missing)
    print("  source:", SOURCE)
    print("  target:", TARGET)
    if missing:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
