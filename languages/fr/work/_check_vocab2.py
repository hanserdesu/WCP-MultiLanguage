# -*- coding: utf-8 -*-
import json, pathlib, sys
sys.stdout.reconfigure(encoding='utf-8')
V = pathlib.Path.home() / "AppData/LocalLow/WCP/vocabulary"
books = json.loads(open(r"D:/French/output/french_books.json", encoding='utf-8').read())
fr_words = set()
for lv in ("a1","a2","b1","b2"):
    for w in books["levels"][lv]:
        fr_words.add(w["word"].strip())
all_mp3 = {p.stem for p in V.glob("*.mp3")}
non_fr = all_mp3 - fr_words
# 抽样看非法语 mp3 构成
sample = sorted(non_fr)[:40]
print("non-french mp3 count:", len(non_fr))
print("sample:", sample)
# 看有没有 ASCII 词形的（可能是英语语音包解压出来的）
import re
ascii_names = [w for w in non_fr if re.fullmatch(r"[a-zA-Z0-9'\- ]+", w)]
print("ascii-like english names:", len(ascii_names), "sample:", sorted(ascii_names)[:40])
cjk = [w for w in non_fr if re.search(r"[\u4e00-\u9fff]", w)]
print("cjk names (jp generated):", len(cjk), "sample:", cjk[:10])
kana = [w for w in non_fr if re.search(r"[\u3040-\u30ff]", w)]
print("kana names:", len(kana), "sample:", kana[:10])
# 同形词 mp3 是否存在英语备份: 检查 rar 无法解压, 看有没有别的备份目录
print()
print("vocabulary dirs:", [p.name for p in V.parent.iterdir() if p.is_dir()])
