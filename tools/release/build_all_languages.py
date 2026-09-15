"""Build per-language audio resource zips for WCP-MultiLanguage releases.

Source of truth is the game's LocalLow audio cache, which the language
toolchains write to: %USERPROFILE%\\AppData\\LocalLow\\WCP\\wcp\\<lang>_{word,sentence}_audio.
Layout matches the existing Japanese/French resource zips: flat mp3 entries,
ZIP_STORED, no directory records.

usage: python build_all_languages.py [--only fr,de] [--force]
"""

import argparse
import hashlib
import json
import os
import time
import zipfile
from pathlib import Path

LOCALLOW = Path(os.environ["USERPROFILE"]) / "AppData" / "LocalLow" / "WCP" / "wcp"
OUTROOT = Path(r"D:\ATooManyLanguage\_local\release")
SUMMARY = OUTROOT / "build-summary.json"

# lang id -> (english name used in asset names, source dir prefix)
LANGS = {
    "ar": "arabic",
    "de": "german",
    "es": "spanish",
    "fr": "french",
    "ko": "korean",
    "pt": "portuguese",
    "ru": "russian",
    "yue": "cantonese",
    "ja": "japanese",
}

# Zips that already exist with the exact bytes a release needs (sha256 checked
# against the published/pinned digests) are reused instead of rebuilt.
REUSE = {
    "fr": {
        "word_audio": Path(r"D:\ATooManyLanguage\French\output\release\wcp-french-audio-words.zip"),
        "sentence_audio": Path(r"D:\ATooManyLanguage\French\output\release\wcp-french-audio-sentences.zip"),
    },
    "ja": {
        "word_audio": Path(r"D:\ATooManyLanguage\Japanese\wcp_wordbooks\output\release\wcp-japanese-audio-words.zip"),
        "sentence_audio": Path(r"D:\ATooManyLanguage\Japanese\wcp_wordbooks\output\release\wcp-japanese-audio-sentences.zip"),
    },
}

KINDS = ("word_audio", "sentence_audio")


def sha256_of(path, chunk=1 << 22):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def build_zip(src: Path, out: Path) -> int:
    files = sorted((p for p in src.iterdir() if p.is_file()), key=lambda p: p.name)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".part")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_STORED, allowZip64=True) as z:
        for path in files:
            z.write(path, arcname=path.name)
    tmp.replace(out)
    return len(files)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    wanted = [x.strip() for x in args.only.split(",") if x.strip()] or list(LANGS)

    summary = {}
    if SUMMARY.exists():
        summary = json.loads(SUMMARY.read_text(encoding="utf-8"))

    for lang in wanted:
        name = LANGS[lang]
        outdir = OUTROOT / lang
        entry = summary.setdefault(lang, {"id": lang, "name": name, "assets": {}})
        for kind in KINDS:
            suffix = "words" if kind == "word_audio" else "sentences"
            asset_name = f"wcp-{name}-audio-{suffix}.zip"
            out = outdir / asset_name
            srcdir = "word_audio" if kind == "word_audio" else "sentence_audio"
            src = LOCALLOW / f"{lang}_{srcdir}"
            reuse = REUSE.get(lang, {}).get(kind)
            if reuse is not None:
                if not reuse.exists():
                    raise SystemExit(f"reuse source missing: {reuse}")
                # Published/pinned bytes: upload straight from where they live.
                print(f"[reuse] {lang}/{kind}: {reuse}")
                out = reuse
            elif not out.exists() or args.force:
                if not src.exists():
                    print(f"[skip] {lang}/{kind}: {src} missing")
                    continue
                t0 = time.time()
                count = build_zip(src, out)
                print(f"[build] {lang}/{kind}: {count} files -> {out.name} in {time.time() - t0:.1f}s")
            size = out.stat().st_size
            digest = sha256_of(out)
            entry["assets"][kind] = {
                "name": asset_name,
                "size": size,
                "sha256": digest,
                "path": str(out),
                "source": str(src),
            }
            print(f"        {lang}/{kind}: {size / 1024 / 1024:.1f} MB  sha256={digest[:16]}...")
        summary[lang] = entry
        SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"summary -> {SUMMARY}")


if __name__ == "__main__":
    main()
