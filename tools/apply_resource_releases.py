"""Rewrite catalog.json resource pins from published release metadata.

catalog.json stays the single source of truth the installer packages; this
tool keeps it in sync with what actually sits in the WCP-MultiLanguage
releases.  Input is a JSON map:

    { "<lang id>": { "tag": "wcp-fr-resources-v1.0.0",
                     "repo": "hanserdesu/WCP-French-Wordbook",
                     "disk_mb": 842,
                     "assets": [ {kind, name, size, sha256, url}, ... ] } }

"disk_mb" is optional; when present it refreshes the entry's disk.extract_mb
preflight number (zip entries are stored, so it is the extracted size).
"repo" is optional and overrides the repo field per language: the installer's
online discovery indexes the catalog by repo, so two wordbooks sharing one repo
would collapse into a single entry (resources may still be hosted elsewhere;
the asset URLs decide where the bytes come from).

usage: python tools/apply_resource_releases.py releases.json [--repo owner/name] [--dry-run]
"""

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CATALOG = REPO_ROOT / "catalog.json"
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
# pack/slot_manifest 由 P1-3 起随行分发（安装器按 name/kind 装载 core zip 与槽位种子）
KINDS = ("word_audio", "sentence_audio", "pack", "slot_manifest")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("releases")
    ap.add_argument("--repo", default="hanserdesu/WCP-MultiLanguage")
    ap.add_argument("--keep-repo", action="append", default=[],
                    help="language ids whose repo field must not be rewritten")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    releases = json.loads(Path(args.releases).read_text(encoding="utf-8"))
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    problems = []

    for wb in catalog["wordbooks"]:
        lang = wb["id"]
        if lang not in releases:
            continue
        rel = releases[lang]
        tag = rel["tag"]
        assets = []
        for asset in rel["assets"]:
            name, size, sha, kind = asset["name"], int(asset["size"]), str(asset["sha256"]).lower(), asset["kind"]
            url = asset["url"]
            if kind not in KINDS:
                problems.append(f"{lang}: unexpected kind {kind}")
            if size <= 0:
                problems.append(f"{lang}/{name}: bad size {size}")
            if not SHA_RE.match(sha):
                problems.append(f"{lang}/{name}: bad sha256 {sha}")
            if f"/releases/download/{tag}/{name}" not in url:
                problems.append(f"{lang}/{name}: url does not match tag {tag}")
            assets.append({"kind": kind, "name": name, "size": size, "sha256": sha, "url": url})
        if problems:
            continue
        wb["release_tag"] = tag
        wb["version"] = tag
        wb["assets"] = assets
        wb["status"] = "available" if assets else "pending_release"
        disk_mb = rel.get("disk_mb")
        if isinstance(disk_mb, int) and disk_mb > 0:
            wb.setdefault("disk", {})["extract_mb"] = disk_mb
        if rel.get("repo"):
            wb["repo"] = rel["repo"]
        elif lang not in args.keep_repo:
            wb["repo"] = args.repo
        print(f"{lang}: {tag}  {len(assets)} asset(s)  repo={wb['repo']}  status={wb['status']}")

    if problems:
        print("problems:", file=sys.stderr)
        for p in problems:
            print("  -", p, file=sys.stderr)
        return 1

    if args.dry_run:
        print("dry run: catalog.json untouched")
        return 0

    # newline="\n": the repo keeps LF (only *.cmd is pinned to CRLF), and the
    # Windows text-mode default would otherwise rewrite every line as CRLF.
    CATALOG.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8", newline="\n")
    print("catalog.json updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
