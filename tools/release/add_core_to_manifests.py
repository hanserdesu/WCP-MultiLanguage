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
        if raw:
            return (r.status, b)
        if not b:  # 204 No Content 等（DELETE 资产）没有响应体
            return (r.status, None)
        return (r.status, json.loads(b))


def upload_asset(repo, upload_url, path):
    data = path.read_bytes()
    _, asset = api(upload_url + f"?name={path.name}", method="POST", data=data,
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

    rel = api(f"https://api.github.com/repos/{repo}/releases/tags/{tag}")[1]
    upload_url = rel["upload_url"].split("{")[0]

    manifest_asset = next((a for a in rel["assets"] if a["name"] == "release-manifest.json"), None)
    base = f"https://github.com/{repo}/releases/download/{tag}"
    if manifest_asset:
        req = urllib.request.Request(manifest_asset["url"],
                                     headers={**H, "Accept": "application/octet-stream"})
        with urllib.request.urlopen(req, timeout=300) as r:
            manifest = json.loads(r.read())
    else:
        # 上一轮删除旧 manifest 后中断过：从 release 现存资产重建条目，
        # sha256 优先用本地文件（上传时已逐字节回读校验），音频本地没有，
        # 用随包 catalog.json 里已验证的哈希补齐。
        known_sha = {}
        cat_path = ROOT / "catalog.json"
        if cat_path.exists():
            cat = json.loads(cat_path.read_text(encoding="utf-8"))
            row = next((w for w in cat["wordbooks"] if w["id"] == lang), None)
            if row:
                known_sha = {a["name"]: a["sha256"] for a in row.get("assets", [])}
        manifest = {"version": tag, "built": "reconstructed", "base_urls": [base], "assets": []}
        for a in rel["assets"]:
            name = a["name"]
            if name == "release-manifest.json":
                continue
            kind = ("word_audio" if "words" in name
                    else "sentence_audio" if "sentences" in name
                    else "pack" if name == f"wcp-{lang}-core.zip"
                    else "slot_manifest" if name == f"wcp-{lang}-slot-seed.json"
                    else "payload")
            local_path = d / name
            sha = (hashlib.sha256(local_path.read_bytes()).hexdigest()
                   if local_path.exists() else known_sha.get(name, ""))
            manifest["assets"].append({"kind": kind, "name": name,
                                       "size": a["size"], "sha256": sha,
                                       "url": f"{base}/{name}"})

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
