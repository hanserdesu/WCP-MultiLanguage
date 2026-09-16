"""Publish one WCP-MultiLanguage audio release per language, safely.

Flow per language (never publishes unverified bytes):
  1. read build-summary.json entry (name/size/sha256/path per asset)
  2. create the GitHub release as a DRAFT with the zips + release-manifest.json
  3. re-read the assets from the API and compare size + digest to the local build
  4. only then flip the draft to published
  5. append the verified result to published-releases.json

All GitHub traffic is forced through the local mihomo mixed port so it uses the
良心云 route (see profiles\\Script.js), never the XSUS subscription.

usage: python publish_release.py <lang> [<lang> ...] [--repo owner/name] [--dry-run]
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"D:\ATooManyLanguage\_local\release")
SUMMARY_NAME = "build-summary.json"
PUBLISHED = ROOT / "published-releases.json"
DEFAULT_REPO = "hanserdesu/WCP-MultiLanguage"
PROXY = "http://127.0.0.1:7897"
TAG_VERSION = "v1.0.0"


def gh(args, timeout=3600):
    env = dict(os.environ)
    env.update({
        "HTTPS_PROXY": PROXY,
        "HTTP_PROXY": PROXY,
        "NO_PROXY": "localhost,127.0.0.1,::1",
        "GH_PAGER": "",
    })
    proc = subprocess.run(
        ["gh"] + args, capture_output=True, text=True, encoding="utf-8",
        errors="replace", env=env, timeout=timeout,
    )
    return proc.returncode, (proc.stdout or "").strip(), (proc.stderr or "").strip()


def find_release(repo, tag):
    """Release dict for tag, drafts included.

    The /releases/tags/<tag> lookup 404s for drafts (GitHub only creates the
    tag ref on publish), so list first and fall back to the tag endpoint.
    """
    code, out, err = gh(["api", f"repos/{repo}/releases?per_page=100"])
    if code == 0:
        for rel in json.loads(out):
            if rel.get("tag_name") == tag:
                return rel
    code, out, err = gh(["api", f"repos/{repo}/releases/tags/{tag}"])
    return json.loads(out) if code == 0 else None


def classify_assets(state, expected):
    """Split the release's assets into (mismatched, matched) against expected."""
    bad, good = [], []
    for asset in state.get("assets", []):
        name = asset["name"]
        if name not in expected:
            continue
        exp_size, exp_sha = expected[name]
        got_sha = (asset.get("digest") or "").removeprefix("sha256:").lower()
        if asset["size"] != exp_size or (got_sha and got_sha != exp_sha):
            bad.append(asset)
        else:
            good.append(asset)
    return bad, good


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("langs", nargs="+")
    ap.add_argument("--repo", default=DEFAULT_REPO)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--version", default=TAG_VERSION,
                    help="tag 版本段（默认 v1.0.0；tag=wcp-<lang>-resources-<version>）")
    ap.add_argument("--summary", default=SUMMARY_NAME,
                    help="build-summary 文件名（相对 ROOT，默认 build-summary.json）")
    ap.add_argument("--published", default=str(PUBLISHED),
                    help="发布记录输出 json（默认 published-releases.json）")
    ap.add_argument("--manifest-dir", default=None,
                    help="release-manifest.json/notes.md 所在根目录（默认 ROOT；v1.1.0 用 ROOT/v110）")
    ap.add_argument("--core-dir", default=None,
                    help="pack core zip + slot seed 所在根目录（默认不随发；ML 仓 tools/release/core）")
    ap.add_argument("--repair", action="store_true",
                    help="delete mismatched assets on the draft and re-upload them")
    args = ap.parse_args()

    mroot = Path(args.manifest_dir) if args.manifest_dir else ROOT
    summary = json.loads((ROOT / args.summary).read_text(encoding="utf-8"))
    published_path = Path(args.published)
    published = json.loads(published_path.read_text(encoding="utf-8")) if published_path.exists() else {}
    problems = []

    for lang in args.langs:
        entry = summary.get(lang)
        if not entry:
            problems.append(f"{lang}: not in {args.summary}")
            continue
        tag = f"wcp-{lang}-resources-{args.version}"
        paths, kinds = [], {}
        bad = False
        for kind, info in entry["assets"].items():
            p = Path(info["path"])
            if not p.exists():
                problems.append(f"{lang}/{kind}: missing {p}")
                bad = True
                continue
            if p.stat().st_size != info["size"]:
                problems.append(f"{lang}/{kind}: size drift {p.stat().st_size} != {info['size']}")
                bad = True
                continue
            paths.append(str(p))
            kinds[info["name"]] = kind
        if bad:
            continue

        manifest = mroot / lang / "release-manifest.json"
        notes = mroot / lang / "notes.md"
        if not manifest.exists() or not notes.exists():
            problems.append(f"{lang}: run make_release_manifests.py first ({manifest})")
            continue

        expected = {info["name"]: (info["size"], info["sha256"].lower()) for info in entry["assets"].values()}
        if args.core_dir:
            # 随发 pack core zip 与槽位 seed（以 manifest 条目为准，本地文件必须存在且一致）
            mjson = json.loads(manifest.read_text(encoding="utf-8"))
            for a in mjson.get("assets", []):
                if a.get("kind") not in ("pack", "slot_manifest"):
                    continue
                p = Path(args.core_dir) / lang / a["name"]
                if not p.exists():
                    problems.append(f"{lang}: core asset missing {p}")
                    bad = True
                    continue
                if p.stat().st_size != a["size"] or hashlib.sha256(p.read_bytes()).hexdigest() != a["sha256"]:
                    problems.append(f"{lang}: core asset drift {p}")
                    bad = True
                    continue
                paths.append(str(p))
                kinds[a["name"]] = a["kind"]
                expected[a["name"]] = (a["size"], a["sha256"].lower())
            if bad:
                continue
        print(f"[{lang}] {tag}: {len(paths)} zip(s) + manifest")
        if args.dry_run:
            for name, (size, sha) in sorted(expected.items()):
                print(f"        {name}  {size} bytes  sha256={sha[:16]}...")
            continue

        local_paths = {Path(p).name: p for p in paths + [str(manifest)]}
        state = find_release(args.repo, tag)
        if state is None:
            cmd = ["release", "create", tag, "-R", args.repo, "--draft",
                   "--title", f"WCP {lang} audio resources {args.version}",
                   "--notes-file", str(notes)] + paths + [str(manifest)]
            code, out, err = gh(cmd)
            # gh retries asset uploads; a retry that collides with an asset that
            # already landed reports 422 even when the release is complete, so
            # a nonzero exit is only a problem if nothing exists afterwards.
            state = find_release(args.repo, tag)
            if state is None:
                problems.append(f"{lang}: gh release create failed: {err or out}")
                continue
            if code != 0:
                print(f"[{lang}] create reported: {err or out} -- verifying what landed anyway")
        elif state.get("assets") and not state.get("draft"):
            print(f"[{lang}] already published, verifying only")

        if state.get("draft"):
            bad, _ = classify_assets(state, expected)
            if bad and args.repair:
                names = {a["name"] for a in bad}
                for asset in bad:
                    rc, _, _ = gh(["api", "-X", "DELETE", f"repos/{args.repo}/releases/assets/{asset['id']}"])
                    print(f"[{lang}] deleted mismatched asset {asset['name']} ({asset['size']} bytes) rc={rc}")
                state = find_release(args.repo, tag)
                bad = [a for a in state.get("assets", []) if a["name"] in names]
            present = {a["name"] for a in state.get("assets", [])}
            todo = [p for n, p in local_paths.items() if n not in present]
            if bad and todo:
                problems.append(
                    f"{lang}: refusing to upload over mismatched assets (use --repair): "
                    + ", ".join(a["name"] for a in bad)
                )
                continue
            if todo:
                code, out, err = gh(["release", "upload", tag, "-R", args.repo] + todo)
                if code != 0:
                    problems.append(f"{lang}: gh release upload failed: {err or out}")
                    continue
                state = find_release(args.repo, tag)

        # 3) verify what GitHub actually stored
        mismatch = []
        for asset in state.get("assets", []):
            name = asset["name"]
            if name not in expected:
                continue
            exp_size, exp_sha = expected[name]
            got_sha = (asset.get("digest") or "").removeprefix("sha256:")
            if asset["size"] != exp_size:
                mismatch.append(f"{name}: size {asset['size']} != {exp_size}")
            if got_sha and got_sha.lower() != exp_sha:
                mismatch.append(f"{name}: digest {got_sha[:16]}... != {exp_sha[:16]}...")
        missing_assets = [n for n in expected if n not in {a["name"] for a in state.get("assets", [])}]
        if missing_assets:
            mismatch.append(f"missing on release: {', '.join(missing_assets)}")
        if mismatch:
            problems.append(f"{lang}: NOT publishing -- " + "; ".join(mismatch))
            continue

        if state.get("draft"):
            code, out, err = gh(["release", "edit", tag, "-R", args.repo, "--draft=false"])
            if code != 0:
                problems.append(f"{lang}: publish failed: {err or out}")
                continue
            state = find_release(args.repo, tag)

        assets = []
        for asset in sorted(state.get("assets", []), key=lambda a: a["name"]):
            name = asset["name"]
            if name not in kinds:
                continue
            assets.append({
                "kind": kinds[name],
                "name": name,
                "size": asset["size"],
                "sha256": (asset.get("digest") or "").removeprefix("sha256:").lower(),
                "url": f"https://github.com/{args.repo}/releases/download/{tag}/{name}",
            })
        published[lang] = {
            "tag": tag,
            "repo": args.repo,
            "assets": assets,
            "published": bool(state.get("published_at")),
            "published_at": state.get("published_at"),
        }
        published_path.write_text(json.dumps(published, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"[{lang}] published: {state.get('html_url')}")
        for a in assets:
            print(f"        {a['kind']}: {a['name']}  {a['size']} bytes  {a['sha256'][:16]}...")

    if problems:
        print("problems:", file=sys.stderr)
        for p in problems:
            print("  -", p, file=sys.stderr)
        return 1
    print(f"published record -> {published_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
