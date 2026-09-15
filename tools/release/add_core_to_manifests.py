# -*- coding: utf-8 -*-
"""Add pack + slot_manifest entries to each language release's manifest asset.

The unified installer's online discovery trusts release-manifest.json when a
release carries one, so the new core/seed assets must be recorded there.
Because GitHub cannot replace an asset in place, the updated manifest is
uploaded under the same name after deleting the old asset (name-keyed lookups
elsewhere stay stable).  Every rewritten manifest keeps the original word/
sentence audio entries byte-for-byte.

usage: python tools/release/add_core_to_manifests.py
"""
import hashlib
import json
import subprocess
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "tools" / "release" / "core"
REPO = "hanserdesu/WCP-MultiLanguage"

# ja 的资源 release 在 japanese 仓库（见 catalog.json / ja-pin.json 的既定决策）
LANGS = {
    "ja": ("hanserdesu/japanese", "wcp-jp-resources-v1.0.0"),
    "fr": (REPO, "wcp-fr-resources-v1.0.0"),
    "ru": (REPO, "wcp-ru-resources-v1.0.0"),
    "de": (REPO, "wcp-de-resources-v1.0.0"),
    "yue": (REPO, "wcp-yue-resources-v1.0.0"),
    "es": (REPO, "wcp-es-resources-v1.0.0"),
    "pt": (REPO, "wcp-pt-resources-v1.0.0"),
    "ko": (REPO, "wcp-ko-resources-v1.0.0"),
    "ar": (REPO, "wcp-ar-resources-v1.0.0"),
}


def token():
    out = subprocess.run(["git", "credential", "fill"],
                         input="protocol=https\nhost=github.com\n",
                         capture_output=True, text=True).stdout
    for line in out.splitlines():
        if line.startswith("password="):
            return line.split("=", 1)[1]
    raise SystemExit("no stored github credential")


T = token()
H = {"Authorization": f"token {T}", "User-Agent": "wcp-release"}


def api(url, method="GET", data=None, headers=None, raw=False):
    h = dict(H)
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    with urllib.request.urlopen(req, timeout=300) as r:
        b = r.read()
        return (r.status, b) if raw else json.loads(b)


def upload_asset(repo, upload_url, path):
    data = path.read_bytes()
    asset = api(upload_url + f"?name={path.name}", method="POST", data=data,
                headers={"Content-Type": "application/octet-stream"})
    req = urllib.request.Request(asset["url"], headers={**H, "Accept": "application/octet-stream"})
    with urllib.request.urlopen(req, timeout=300) as r:
        blob = r.read()
    ok = hashlib.sha256(blob).hexdigest() == hashlib.sha256(data).hexdigest()
    return asset, ok


def process(lang, repo, tag):
    d = CORE / lang
    core = d / f"wcp-{lang}-core.zip"
    seed = d / f"wcp-{lang}-slot-seed.json"

    rel = api(f"https://api.github.com/repos/{repo}/releases/tags/{tag}")
    upload_url = rel["upload_url"].split("{")[0]

    manifest_asset = next((a for a in rel["assets"] if a["name"] == "release-manifest.json"), None)
    if not manifest_asset:
        raise SystemExit(f"{lang}: release 无 release-manifest.json，拒绝盲改")
    req = urllib.request.Request(manifest_asset["url"],
                                 headers={**H, "Accept": "application/octet-stream"})
    with urllib.request.urlopen(req, timeout=300) as r:
        manifest = json.loads(r.read())

    base = f"https://github.com/{repo}/releases/download/{tag}"
    existing_kinds = {a.get("kind") for a in manifest.get("assets", [])}
    new_entries = [
        {"kind": "pack", "name": core.name,
         "size": core.stat().st_size,
         "sha256": hashlib.sha256(core.read_bytes()).hexdigest(), "url": f"{base}/{core.name}"},
        {"kind": "slot_manifest", "name": seed.name,
         "size": seed.stat().st_size,
         "sha256": hashlib.sha256(seed.read_bytes()).hexdigest(), "url": f"{base}/{seed.name}"},
    ]
    # 幂等：先剔除同名旧条目，再追加（保留原有音频条目原样）
    keep = [a for a in manifest.get("assets", [])
            if a.get("name") not in {core.name, seed.name}]
    manifest["assets"] = keep + new_entries
    manifest["base_urls"] = [base]

    body = json.dumps(manifest, ensure_ascii=False, indent=1).encode("utf-8")
    tmp = d / "release-manifest.json"
    tmp.write_bytes(body)
    if manifest_asset:
        api(f"https://api.github.com/repos/{repo}/releases/assets/{manifest_asset['id']}",
            method="DELETE")
    _, ok = upload_asset(repo, upload_url, tmp)
    tmp.unlink()
    return ok


if __name__ == "__main__":
    bad = []
    for lang, (repo, tag) in LANGS.items():
        ok = process(lang, repo, tag)
        print(f"{lang}: manifest updated verified={ok}", flush=True)
        if not ok:
            bad.append(lang)
    print("DONE. failures:", bad if bad else "none")
