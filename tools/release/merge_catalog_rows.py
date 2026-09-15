"""Merge published release records + the Japanese stable pin into one catalog row map.

Inputs:
  published-releases.json  -- written by publish_release.py (WCP-MultiLanguage)
  catalog-assets.json      -- written by make_release_manifests.py (exact disk sizes)
  ja-pin.json              -- Japanese stays in hanserdesu/japanese; pinned to the
                              last public resource release, never the draft

Output: catalog-releases.json for MultiLanguage/tools/apply_resource_releases.py
"""

import json
from pathlib import Path

ROOT = Path(r"D:\ATooManyLanguage\_local\release")

# 每本词书的 GitHub 仓库。安装器的在线发现按 repo 给目录建索引，两本词书共用一个 repo
# 会被折叠成一条（9 本只剩 2 本），所以 repo 必须保持一语言一仓；语音资源包放在哪个
# release 由 asset 的 url 决定。
WORDBOOK_REPOS = {
    "ja": "hanserdesu/japanese",
    "fr": "hanserdesu/WCP-French-Wordbook",
    "ru": "hanserdesu/WCP-Russian-Wordbook",
    "de": "hanserdesu/WCP-German-Wordbook",
    "yue": "hanserdesu/WCP-Cantonese-Wordbook",
    "ko": "hanserdesu/WCP-Korean-Wordbook",
    "ar": "hanserdesu/WCP-Arabic-Wordbook",
    "es": "hanserdesu/WCP-Spanish-Wordbook",
    "pt": "hanserdesu/WCP-Portuguese-Wordbook",
}


def load(name):
    path = ROOT / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def main():
    published = load("published-releases.json")
    assets = load("catalog-assets.json")
    ja_pin = load("ja-pin.json")

    rows = {}
    for lang, rel in published.items():
        rows[lang] = {
            "tag": rel["tag"],
            "repo": WORDBOOK_REPOS.get(lang, rel.get("repo", "hanserdesu/WCP-MultiLanguage")),
            "assets": rel["assets"],
        }
        disk_mb = (assets.get(lang) or {}).get("disk_mb")
        if disk_mb:
            rows[lang]["disk_mb"] = disk_mb

    # Japanese is preserved in its own repo; the pin file wins over any row the
    # build produced (the build reuses the draft v1.1.0 bytes, which must not ship).
    for lang, rel in ja_pin.items():
        row = {k: rel[k] for k in ("tag", "repo", "assets") if k in rel}
        if rel.get("disk_mb"):
            row["disk_mb"] = rel["disk_mb"]
        rows[lang] = row
        print(f"[pin] {lang}: {row['tag']} (from {row['repo']})")

    out = ROOT / "catalog-releases.json"
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n{len(rows)} row(s) -> {out}")
    for lang in sorted(rows):
        rel = rows[lang]
        total = sum(a["size"] for a in rel["assets"])
        print(f"  {lang:4s} {rel['tag']:32s} disk_mb={rel.get('disk_mb', '?'):>5} "
              f"assets={len(rel['assets'])} {total / 1048576:.1f} MiB")


if __name__ == "__main__":
    main()
