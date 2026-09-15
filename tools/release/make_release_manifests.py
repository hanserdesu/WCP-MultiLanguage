"""Turn build-summary.json into per-language release manifests plus catalog asset rows."""

import json
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(r"D:\ATooManyLanguage\_local\release")
REPO = "hanserdesu/WCP-MultiLanguage"
TAGS = {
    "ja": "wcp-ja-resources-v1.1.0",
}
DEFAULT_TAG = "wcp-{lang}-resources-v1.0.0"
DISPLAY = {
    "ar": "阿拉伯语",
    "de": "德语",
    "es": "西班牙语",
    "fr": "法语",
    "ja": "日语",
    "ko": "韩语",
    "pt": "葡萄牙语",
    "ru": "俄语",
    "yue": "粤语",
}


def main():
    summary = json.loads((ROOT / "build-summary.json").read_text(encoding="utf-8"))
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    catalog = {}
    for lang, entry in sorted(summary.items()):
        tag = TAGS.get(lang, DEFAULT_TAG.format(lang=lang))
        assets = []
        counts = {}
        unpacked = 0
        for kind in ("word_audio", "sentence_audio"):
            info = entry["assets"].get(kind)
            if not info:
                continue
            src = Path(info["source"])
            if src.is_dir():
                files = [p for p in src.iterdir() if p.is_file()]
                counts[kind] = len(files)
                unpacked += sum(p.stat().st_size for p in files)
            elif (zip_path := Path(info["path"])).exists():
                with zipfile.ZipFile(zip_path) as z:
                    infos = z.infolist()
                counts[kind] = len(infos)
                unpacked += sum(i.file_size for i in infos)
        for kind in ("word_audio", "sentence_audio"):
            info = entry["assets"].get(kind)
            if not info:
                continue
            url = f"https://github.com/{REPO}/releases/download/{tag}/{info['name']}"
            assets.append({
                "kind": kind,
                "name": info["name"],
                "size": info["size"],
                "sha256": info["sha256"],
                "url": url,
            })
        manifest = {
            "version": tag,
            "built": now,
            "base_urls": [f"https://github.com/{REPO}/releases/download/{tag}"],
            "assets": [{k: a[k] for k in ("kind", "name", "size", "sha256")} for a in assets],
        }
        outdir = ROOT / lang
        outdir.mkdir(parents=True, exist_ok=True)
        (outdir / "release-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        disk_mb = round(unpacked / 1024 / 1024)
        notes = [
            f"WCP {DISPLAY.get(lang, lang)}语音资源包（{tag}，安装器自动下载）",
            "",
            f"- 单词发音：{counts.get('word_audio', 0)} 个 mp3（{assets[0]['name']}）" if assets else "",
        ]
        if len(assets) > 1:
            notes.append(f"- 例句发音：{counts.get('sentence_audio', 0)} 个 mp3（{assets[1]['name']}）")
        notes += [
            f"- 解压后约 {disk_mb} MB，安装到 packs/{lang}/audio/{{word,sentence}}",
            "- 每个 zip 的 SHA-256 见 release-manifest.json 与 catalog.json，安装器会逐项校验",
            "",
            "资源自游戏缓存目录 word/sentence 音频打包，与日语资源包同一规范（平铺 mp3、ZIP_STORED）。",
        ]
        (outdir / "notes.md").write_text("\n".join(x for x in notes if x is not None) + "\n", encoding="utf-8")
        catalog[lang] = {
            "tag": tag,
            "repo": REPO,
            "assets": assets,
            "manifest": str(outdir / "release-manifest.json"),
            "notes": str(outdir / "notes.md"),
            "counts": counts,
            "disk_mb": disk_mb,
        }
        print(f"{lang}: {tag}  assets={len(assets)}")
    (ROOT / "catalog-assets.json").write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"catalog rows -> {ROOT / 'catalog-assets.json'}")


if __name__ == "__main__":
    main()
