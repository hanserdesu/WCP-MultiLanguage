#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验 languages/<code>/ 与原语言仓库工作区是否逐字节一致。

用法::

    python tools/verify_integration.py            # 全量校验
    python tools/verify_integration.py --only ja  # 只校验指定语言

应与 tools/integrate_languages.py 用同一套文件集合规则：tracked 全量、未跟踪按排除
规则过滤。逐文件比对 sha256，并报告多余文件；任何缺失、内容不一致都以非零码结束。
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import integrate_languages as il


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def expected_files(repo: Path) -> dict[str, str]:
    tracked, modified, added, removed, untracked = il._read_state(repo)
    wanted: dict[str, str] = {}
    for path in tracked:
        wanted[path] = "tracked"
    for path in modified:
        wanted[path] = "modified"
    for path in untracked:
        abs_path = repo / path
        size = abs_path.stat().st_size if abs_path.is_file() else None
        if il._exclude_reason(path, size) is None:
            wanted[path] = "untracked"
    return wanted


def check(code: str, hub: Path) -> tuple[int, list[str], list[str], list[str]]:
    repo = il.WORKSPACE / il.LANGUAGES[code][0]
    dest = hub / "languages" / code
    wanted = expected_files(repo)
    ok = 0
    missing: list[str] = []
    mismatch: list[str] = []
    for rel in sorted(wanted):
        src = repo / rel
        dst = dest / rel
        if not src.is_file():
            continue
        if not dst.is_file():
            missing.append(rel)
            continue
        if sha256(src) != sha256(dst):
            mismatch.append(rel)
            continue
        ok += 1
    have = {
        str(p.relative_to(dest)).replace("\\", "/")
        for p in dest.rglob("*")
        if p.is_file()
    }
    extra = sorted(have - set(wanted))
    return ok, missing, mismatch, extra


def main(argv: list[str] | None = None) -> int:
    global WORKSPACE
    parser = argparse.ArgumentParser(description="校验 languages/ 与原语言仓库工作区一致性")
    parser.add_argument("--only", default="", help="逗号分隔的语言代码，如 ja,ru")
    parser.add_argument("--workspace", default=str(il.WORKSPACE), help="工作区根目录")
    args = parser.parse_args(argv)

    il.WORKSPACE = Path(args.workspace)
    hub = il.WORKSPACE / il.HUB_DIRNAME
    codes = [c.strip() for c in args.only.split(",") if c.strip()] or list(il.LANGUAGES)

    failed = 0
    for code in codes:
        ok, missing, mismatch, extra = check(code, hub)
        status = "PASS" if not (missing or mismatch or extra) else "FAIL"
        if status == "FAIL":
            failed += 1
        print(
            "[" + code + "] " + status + " ok=" + str(ok)
            + " missing=" + str(len(missing))
            + " mismatch=" + str(len(mismatch))
            + " extra=" + str(len(extra))
        )
        for label, items in (("missing", missing), ("mismatch", mismatch), ("extra", extra)):
            for item in items[:10]:
                print("    " + label + ": " + item)
    print("RESULT: " + ("FAIL" if failed else "PASS") + " (" + str(len(codes)) + " languages)")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
