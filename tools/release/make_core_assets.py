# -*- coding: utf-8 -*-
"""Generate per-language core pack zip + slot seed json for the unified installer.

Inputs (read-only):
  packs/<lang>/manifest.json, db/, books/, optional strategy DLL, optional audio/

Outputs (under tools/release/core/<lang>/):
  wcp-<lang>-core.zip       entries are pack-root relative (manifest.json, db/.., books/..)
  wcp-<lang>-slot-seed.json {"schema":1,"selected":0,"slots":[<one managed row>]}

The seed row's word list is rebuilt from packs/<lang>/db/meaning.sqlite (pron
table) and must reproduce manifest.fingerprint_sha256 exactly (host fingerprint
algorithm: sha256 of sorted words each followed by "\n").  A mismatch aborts
the build for that language - never publish an unverifiable identity.

usage: python tools/release/make_core_assets.py <lang> [<lang> ...]
"""
import hashlib
import json
import sqlite3
import sys
import unicodedata
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "tools" / "release" / "core"


def fingerprint_of(words):
    """与宿主 BookRegistry.FingerprintOf / build_pack.fingerprint_of 逐字节一致。"""
    payload = "".join(w + "\n" for w in sorted(words))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def norm(value):
    text = unicodedata.normalize("NFC", str(value)).strip()
    return text


def build(lang):
    pack = ROOT / "packs" / lang
    manifest = json.loads((pack / "manifest.json").read_text(encoding="utf-8"))

    con = sqlite3.connect(pack / "db" / "meaning.sqlite")
    words = {norm(w) for (w,) in con.execute("SELECT word FROM pron") if norm(w)}
    con.close()
    got = fingerprint_of(words)
    if got != manifest["fingerprint_sha256"] or len(words) != manifest["word_count"]:
        raise SystemExit(
            f"{lang}: 指纹/词数不符 manifest (n={len(words)}/{manifest['word_count']}, "
            f"fp={got} != {manifest['fingerprint_sha256']}) - 拒绝生成 seed")

    dest = OUT / lang
    dest.mkdir(parents=True, exist_ok=True)

    core_zip = dest / f"wcp-{lang}-core.zip"
    with zipfile.ZipFile(core_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted(pack.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(pack).as_posix()
            if rel.startswith("audio/"):
                continue  # 音频由独立的 word_audio/sentence_audio 资产承载
            z.write(path, rel)

    seed = {
        "schema": 1,
        "selected": 0,
        "slots": [{
            "number": 1,
            "id": manifest["profile_id"],
            "name": manifest["display_name"],
            "language": manifest["language"],
            "owner": "mod",
            "managed": True,
            "nativeSlot": 0,
            "words": sorted(words),
        }],
    }
    seed_json = dest / f"wcp-{lang}-slot-seed.json"
    seed_json.write_text(json.dumps(seed, ensure_ascii=False, indent=1), encoding="utf-8")

    print(json.dumps({
        "lang": lang,
        "core": {"name": core_zip.name, "size": core_zip.stat().st_size,
                 "sha256": hashlib.sha256(core_zip.read_bytes()).hexdigest()},
        "seed": {"name": seed_json.name, "size": seed_json.stat().st_size,
                 "sha256": hashlib.sha256(seed_json.read_bytes()).hexdigest()},
        "words": len(words),
    }, ensure_ascii=False))


if __name__ == "__main__":
    for lang in (sys.argv[1:] or ["ja", "fr", "ru", "de", "yue", "es", "pt", "ko", "ar"]):
        build(lang)
