# -*- coding: utf-8 -*-
"""Build the one-click installer package for WCP-MultiLanguage.

学习 Japanese 一键包（build_installer_payload.py + normalize_installer_eol.py）的
发布经验：
  1. 打包集合 = Install-WCP-Wordbooks.ps1 + run-installer.ps1 + WordbookHub.psm1
     + catalog.json + 一键启动 cmd；
  2. .ps1/.cmd 统一 CRLF（PowerShell 进度块与 cmd 对 LF 敏感）；
  3. 产物 zip 的 sha256/size 写进 release-index.json（自更新索引），与安装包
     一起上传到 mods release；
  4. 版本号单一事实来源：本脚本 --version 传入后同时改写 run-installer.ps1
     的 $InstallerVersion 与 release-index.json 的 installer_version。

usage:
  python tools/release/build_installer.py --version wcp-installer-v0.2.0
  （不带 --version 时只打包，不改版本号）
"""
import argparse
import hashlib
import json
import subprocess
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FILES = [
    "Install-WCP-Wordbooks.ps1",
    "run-installer.ps1",
    "WordbookHub.psm1",
    "catalog.json",
]
REPO = "hanserdesu/WCP-MultiLanguage"


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize_eol(path: Path) -> None:
    data = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    path.write_bytes(data)


def gh_token() -> str:
    out = subprocess.run(["git", "credential", "fill"],
                         input="protocol=https\nhost=github.com\n",
                         capture_output=True, text=True).stdout
    for line in out.splitlines():
        if line.startswith("password="):
            return line.split("=", 1)[1]
    raise SystemExit("no stored github credential")


def find_mods_release(token: str) -> dict:
    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/releases?per_page=100",
        headers={"Authorization": f"token {token}", "User-Agent": "wcp-release"})
    with urllib.request.urlopen(req, timeout=60) as r:
        releases = json.loads(r.read())
    for rel in releases:
        if rel.get("tag_name", "").startswith("wcp-mods-"):
            return rel
    raise SystemExit("no wcp-mods-* release found; publish mods payload first")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", help="installer version, e.g. wcp-installer-v0.2.0")
    ap.add_argument("--out", default=str(ROOT / "output" / "installer_pkg"))
    ap.add_argument("--upload", action="store_true",
                    help="upload zip + release-index.json to the mods release")
    args = ap.parse_args()

    out_dir = Path(args.out)
    pkg_dir = out_dir / "package"
    pkg_dir.mkdir(parents=True, exist_ok=True)

    if args.version:
        runner = ROOT / "run-installer.ps1"
        text = runner.read_text(encoding="utf-8-sig")
        marker = "$InstallerVersion = '"
        head, sep, tail = text.partition(marker)
        if sep:
            _, _, rest = tail.partition("'")
            text = head + sep + args.version + "'" + rest
            runner.write_bytes(text.encode("utf-8-sig"))
            print(f"run-installer.ps1 version -> {args.version}")

    for name in FILES:
        src = ROOT / name
        if not src.exists():
            raise SystemExit(f"missing {src}")
        dst = pkg_dir / name
        dst.write_bytes(src.read_bytes())
        if dst.suffix in (".ps1", ".cmd"):
            normalize_eol(dst)
    (pkg_dir / "一键安装词书.cmd").write_bytes(
        ("@echo off\r\npowershell -NoProfile -ExecutionPolicy Bypass -File \"%~dp0run-installer.ps1\"\r\n"
         ).encode("gbk"))

    zip_path = out_dir / f"WCP-Wordbooks-OneClick-Installer-{args.version or 'dev'}.zip"
    import zipfile
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(pkg_dir.rglob("*")):
            if f.is_file():
                z.write(f, Path("WCP多语言词书安装包") / f.relative_to(pkg_dir))
    digest = sha256_of(zip_path)
    print(f"package: {zip_path}")
    print(f"  size   : {zip_path.stat().st_size}")
    print(f"  sha256 : {digest}")

    index = {
        "main_release": REPO,
        "index_updated": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "installer_version": args.version or "dev",
        "core_installer": {
            "name": zip_path.name,
            "size": zip_path.stat().st_size,
            "sha256": digest,
            "url": (f"https://github.com/{REPO}/releases/download/"
                    f"{args.version or 'dev'}/{zip_path.name}"),
        },
    }
    idx_path = out_dir / "release-index.json"
    idx_path.write_bytes((json.dumps(index, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(f"release-index: {idx_path}")

    if args.upload:
        token = gh_token()
        rel = find_mods_release(token)
        tag = rel["tag_name"]
        print(f"uploading to {tag} ...")
        for asset in (zip_path, idx_path):
            up = urllib.request.Request(
                f"https://uploads.github.com/repos/{REPO}/releases/{rel['id']}/assets"
                f"?name={asset.name}",
                data=asset.read_bytes(),
                method="POST",
                headers={"Authorization": f"token {token}",
                         "Content-Type": "application/octet-stream",
                         "User-Agent": "wcp-release"})
            with urllib.request.urlopen(up, timeout=600) as r:
                r.read()
            print(f"  uploaded {asset.name}")
        # 回读校验：GitHub 存的字节必须与本地一致（CDN 缓存不可信，用 API digest）
        req = urllib.request.Request(
            f"https://api.github.com/repos/{REPO}/releases/tags/{tag}",
            headers={"Authorization": f"token {token}", "User-Agent": "wcp-release"})
        with urllib.request.urlopen(req, timeout=60) as r:
            state = json.loads(r.read())
        landed = {a["name"]: (a.get("digest") or "").removeprefix("sha256:")
                  for a in state.get("assets", [])}
        ok = True
        for asset in (zip_path, idx_path):
            got = landed.get(asset.name, "")
            if got and got.lower() != sha256_of(asset):
                print(f"  !! MISMATCH {asset.name}: {got[:16]}...")
                ok = False
            elif not got:
                print(f"  !! missing {asset.name}")
                ok = False
        print("upload verify:", "OK" if ok else "FAILED")
        if not ok:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
