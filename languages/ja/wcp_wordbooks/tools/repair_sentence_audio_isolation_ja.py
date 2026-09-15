# -*- coding: utf-8 -*-
"""只增不删地迁移旧共享目录里的日语句音到 ja pack。"""
import argparse
import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WCP = Path.home() / "AppData" / "LocalLow" / "WCP" / "wcp"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    master = json.loads((ROOT / "data" / "translations" / "sentences_master.json").read_text(encoding="utf-8"))
    names = sorted({hashlib.md5(ja.encode("utf-8")).hexdigest() + ".mp3"
                    for pairs in master.values() for ja, _ in pairs})
    source = WCP / "sentence_audio"
    target = WCP.parent / "packs" / "ja" / "audio" / "sentence"
    if not args.dry_run:
        target.mkdir(parents=True, exist_ok=True)
    copied = missing = 0
    for name in names:
        src, dst = source / name, target / name
        if dst.exists():
            continue
        if not src.exists():
            missing += 1
            continue
        if not args.dry_run:
            shutil.copy2(src, dst)
        copied += 1
    mode = "dry-run" if args.dry_run else "migrated"
    print(f"{mode}: copied={copied}, unresolved_shared={missing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
