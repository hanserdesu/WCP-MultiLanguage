#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把各语言工程仓库的当前工作区状态集成进本仓库的 languages/<code>/ 目录。

用法::

    python tools/integrate_languages.py                 # 只打印计划（默认 dry-run）
    python tools/integrate_languages.py --apply         # 实际复制并写 PROVENANCE.json
    python tools/integrate_languages.py --apply --only ja,ru

设计约定
--------
* 每个语言一个目录 languages/<code>/，完整保留该工程仓库内部的相对路径，
  使各工程自己的 tools/*.py 与 verify_all_*.py 仍能在该目录内直接运行。
* tracked 文件全部集成，不做删减；工作区里未提交的改动与新增文件同样集成，
  因为本仓库现在是所有语言唯一的提交目标，未发布的在研改动不能丢。
* 只排除可再生的大体积构建产物与工具缓存（见 UNTRACKED_EXCLUDES）：
  音频包与安装包归档由 Releases 承载，不进 git 历史。
* 语言工程自带的 .gitignore 原样保留（它们是各工程的产物边界声明）。
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(r"D:\ATooManyLanguage")
HUB_DIRNAME = "MultiLanguage"

# code -> (工作区目录名, GitHub 仓库, 备注)
LANGUAGES: dict[str, tuple[str, str, str]] = {
    "ja": ("Japanese", "hanserdesu/japanese", "日语：本体与语音资源保留在 hanserdesu/japanese"),
    "fr": ("French", "hanserdesu/WCP-French-Wordbook", ""),
    "ru": ("Russian", "hanserdesu/WCP-Russian-Wordbook", ""),
    "es": ("Spanish", "hanserdesu/WCP-Spanish-Wordbook", ""),
    "pt": ("Portuguese", "hanserdesu/WCP-Portuguese-Wordbook", ""),
    "de": ("German", "hanserdesu/WCP-German-Wordbook", ""),
    "ko": ("korean", "hanserdesu/WCP-Korean-Wordbook", ""),
    "ar": ("Arabic", "hanserdesu/WCP-Arabic-Wordbook", ""),
    "yue": ("Contonese", "hanserdesu/WCP-Cantonese-Wordbook", ""),
}

# 未跟踪文件的额外排除规则（tracked 文件永不排除）
UNTRACKED_EXCLUDES: list[tuple[str, str]] = [
    (r"(^|/)\.git/", "vcs"),
    (r"(^|/)\.serena/", "tool-cache"),
    (r"(^|/)\.zcode/", "tool-cache"),
    (r"(^|/)__pycache__/", "python-cache"),
    (r"\.pyc$", "python-cache"),
    (r"(^|/)[^/]*venv[^/]*/", "virtualenv"),
    (r"\.zip$", "build-archive"),
    (r"(^|/)output/release/", "release-artifacts"),
    (r"(^|/)output/installer_pkg/", "installer-package"),
    (r"(^|/)output/[^/]+/backup/", "payload-backup"),
    (r"(^|/)gitee-parts/", "release-artifacts"),
    (r"^packs/", "duplicate-pack-build"),
]

UNTRACKED_MAX_BYTES = 25 * 1024 * 1024


def _run_git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(
            "git " + " ".join(args) + " 失败于 " + str(repo) + ": "
            + proc.stderr.decode("utf-8", "replace").strip()
        )
    return proc.stdout.decode("utf-8", "replace")


def _split_z(raw: str) -> list[str]:
    return [part for part in raw.split("\0") if part]


def _read_state(repo: Path) -> tuple[list[str], list[str], list[str], list[str], list[str]]:
    """返回 (tracked, modified, added, removed, untracked)，均为仓库内相对路径。

    removed 指工作区中已被删除的受版本控制文件（已暂存或未暂存），
    它们代表该工程最新一轮改动主动删掉的内容，仅记录、不复制。
    """
    tracked = _split_z(_run_git(repo, "ls-files", "-z"))
    modified: list[str] = []
    added: list[str] = []
    removed: list[str] = []
    untracked: list[str] = []
    raw = _run_git(repo, "status", "--porcelain", "-z", "--untracked-files=all")
    parts = raw.split("\0")
    idx = 0
    while idx < len(parts):
        entry = parts[idx]
        idx += 1
        if len(entry) < 4:
            continue
        code, path = entry[:2], entry[3:]
        if code[0] == "R" or code[1] == "R":
            idx += 1  # 跳过 rename 记录的原始路径字段
        if code == "??":
            untracked.append(path)
        elif code[1] == "D":
            removed.append(path)
        elif code[0] == "D":
            removed.append(path)
        elif code[1] in "MT":
            modified.append(path)
        elif code[0] in "AM":
            added.append(path)
    return tracked, modified, added, removed, untracked


def _exclude_reason(rel: str, size: int | None) -> str | None:
    rel = rel.replace("\\", "/")
    for pattern, reason in UNTRACKED_EXCLUDES:
        if re.search(pattern, rel):
            return reason
    if size is not None and size > UNTRACKED_MAX_BYTES:
        return "oversize"
    return None


def _copy_hashed(src: Path, dst: Path) -> tuple[int, str]:
    dst.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    size = 0
    with open(src, "rb") as fin, open(dst, "wb") as fout:
        while True:
            chunk = fin.read(1 << 20)
            if not chunk:
                break
            size += len(chunk)
            digest.update(chunk)
            fout.write(chunk)
    shutil.copystat(src, dst)
    return size, digest.hexdigest()


def integrate(code: str, src_dir: str, repo_slug: str, note: str, apply: bool, hub: Path) -> dict:
    repo = WORKSPACE / src_dir
    dest_root = hub / "languages" / code
    if not repo.is_dir():
        return {"error": "源目录不存在: " + str(repo)}

    tracked, modified, added, removed, untracked = _read_state(repo)
    head = _run_git(repo, "log", "-1", "--format=%H%n%ci%n%s").strip().splitlines()
    branch = _run_git(repo, "rev-parse", "--abbrev-ref", "HEAD").strip()
    origin_head = _run_git(repo, "rev-parse", "origin/HEAD").strip() if _has_origin_ref(repo) else ""

    wanted: dict[str, str] = {}
    for path in tracked:
        wanted[path] = "tracked"
    for path in modified:
        wanted[path] = "modified"
    for path in added:
        wanted[path] = "added"

    excluded: dict[str, int] = {}
    excluded_bytes = 0
    excluded_samples: list[str] = []
    for path in untracked:
        abs_path = repo / path
        size = abs_path.stat().st_size if abs_path.is_file() else None
        reason = _exclude_reason(path, size)
        if reason is None:
            wanted[path] = "untracked"
        else:
            excluded[reason] = excluded.get(reason, 0) + 1
            if size:
                excluded_bytes += size
            if len(excluded_samples) < 12:
                excluded_samples.append(path + " (" + reason + ")")

    copied = 0
    total_bytes = 0
    digest = hashlib.sha256()
    states = {"tracked": 0, "modified": 0, "added": 0, "untracked": 0}
    missing: list[str] = []
    for rel in sorted(wanted):
        src = repo / rel
        if not src.is_file():
            missing.append(rel)
            continue
        if apply:
            size, sha = _copy_hashed(src, dest_root / rel)
            digest.update((rel + "\0" + str(size) + "\0" + sha + "\n").encode("utf-8"))
        else:
            size = src.stat().st_size
        copied += 1
        total_bytes += size
        states[wanted[rel]] += 1

    return {
        "source_dir": str(repo),
        "source_repo": "https://github.com/" + repo_slug + ".git",
        "source_branch": branch,
        "source_head": head[0] if head else "",
        "source_head_date": head[1] if len(head) > 1 else "",
        "source_head_subject": head[2] if len(head) > 2 else "",
        "source_origin_head": origin_head,
        "note": note,
        "files": copied,
        "bytes": total_bytes,
        "content_digest": ("sha256:" + digest.hexdigest()) if apply else "",
        "states": states,
        "absent_in_worktree": missing,
        "removed_in_worktree": sorted(removed),
        "excluded": excluded,
        "excluded_bytes": excluded_bytes,
        "excluded_samples": excluded_samples,
    }


def _has_origin_ref(repo: Path) -> bool:
    proc = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", "origin/HEAD"],
        capture_output=True,
        check=False,
    )
    return proc.returncode == 0


def main(argv: list[str] | None = None) -> int:
    global WORKSPACE
    parser = argparse.ArgumentParser(description="集成各语言工程到本仓库 languages/<code>/")
    parser.add_argument("--apply", action="store_true", help="实际复制文件（默认只打印计划）")
    parser.add_argument("--only", default="", help="逗号分隔的语言代码，如 ja,ru")
    parser.add_argument("--workspace", default=str(WORKSPACE), help="工作区根目录")
    args = parser.parse_args(argv)

    WORKSPACE = Path(args.workspace)
    hub = WORKSPACE / HUB_DIRNAME
    if not (hub / "catalog.json").is_file():
        print("找不到中枢仓库: " + str(hub), file=sys.stderr)
        return 2

    codes = [c.strip() for c in args.only.split(",") if c.strip()] or list(LANGUAGES)
    report: dict[str, dict] = {}
    for code in codes:
        if code not in LANGUAGES:
            print("未知语言代码: " + code, file=sys.stderr)
            return 2
        src_dir, repo_slug, note = LANGUAGES[code]
        result = integrate(code, src_dir, repo_slug, note, args.apply, hub)
        report[code] = result
        if "error" in result:
            print("[" + code + "] " + result["error"])
            continue
        print(
            "[" + code + "] files=" + str(result["files"])
            + " MB=" + format(result["bytes"] / 1048576, ".1f")
            + " states=" + json.dumps(result["states"], ensure_ascii=False)
            + " absent=" + str(len(result["absent_in_worktree"]))
            + " excluded=" + json.dumps(result["excluded"], ensure_ascii=False)
            + " excludedMB=" + format(result["excluded_bytes"] / 1048576, ".1f")
        )
        for sample in result["excluded_samples"]:
            print("        - " + sample)

    if args.apply:
        manifest = {
            "schema": 1,
            "integrated_at": _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "hub_repo": "hanserdesu/WCP-MultiLanguage",
            "policy": {
                "tracked": "全部集成，不删减",
                "worktree": "未提交的修改与新增一并集成（本仓库是唯一提交目标）",
                "untracked_excludes": [reason for _, reason in UNTRACKED_EXCLUDES],
                "untracked_max_mb": UNTRACKED_MAX_BYTES // 1048576,
            },
            "languages": report,
        }
        out = hub / "languages" / "PROVENANCE.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(manifest, fh, ensure_ascii=False, indent=2, sort_keys=True)
            fh.write("\n")
        print("已写出 " + str(out))
    else:
        print("（dry-run，未复制任何文件；加 --apply 生效）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
