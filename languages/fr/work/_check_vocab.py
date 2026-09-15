# -*- coding: utf-8 -*-
import json, pathlib, sys
sys.stdout.reconfigure(encoding='utf-8')
V = pathlib.Path.home() / "AppData/LocalLow/WCP/vocabulary"
fr_words = set()
books = json.loads(open(r"D:/French/output/french_books.json", encoding='utf-8').read())
for lv in ("a1","a2","b1","b2"):
    for w in books["levels"][lv]:
        fr_words.add(w["word"].strip())
all_mp3 = {p.stem for p in V.glob("*.mp3")}
fr_mp3 = all_mp3 & fr_words
print("vocabulary mp3 total:", len(all_mp3))
print("french word mp3 present:", len(fr_mp3))
print("french words total:", len(fr_words))
print("non-french mp3 (english/jp/other):", len(all_mp3 - fr_words))
# 英法同形词: 看这 1638 个 changed 词里哪些有 mp3
try:
    manifest = json.loads(open(r"D:/French/output/audio_manifest_fr.json", encoding='utf-8').read())
    done = set(manifest.get("done", {}))
    print("manifest done:", len(done))
    fr_mp3_manifest = all_mp3 & done
    print("mp3 that match manifest (french generated):", len(fr_mp3_manifest))
except Exception as e:
    print("manifest err", e)
# 抽样看几个英法同形词的 mp3 时间
for w in ["ring","table","sweet","sun","team","accord","addition"]:
    p = V / (w + ".mp3")
    print(w, "->", p.exists(), p.stat().st_mtime if p.exists() else "")
