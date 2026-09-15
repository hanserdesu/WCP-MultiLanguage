# -*- coding: utf-8 -*-
import json, io, collections
SAVE = r"C:\Users\hanserdesu\AppData\LocalLow\WCP\wcp\SaveFile.es3"
OUT = r"D:\Japanese\work\tmp\learned_report.txt"

def unwrap(node):
    if isinstance(node, dict):
        if "__type" in node and "value" in node:
            return unwrap(node["value"])
        return {k: unwrap(v) for k, v in node.items()}
    if isinstance(node, list):
        return [unwrap(x) for x in node]
    return node

def is_jp(w):
    for ch in w or "":
        o = ord(ch)
        if 0x3040 <= o <= 0x30FF or 0x3400 <= o <= 0x4DBF or 0x4E00 <= o <= 0x9FFF \
           or 0xF900 <= o <= 0xFAFF or 0xFF66 <= o <= 0xFF9D or o in (0x3005,0x3006,0x3007):
            return True
    return False

with io.open(SAVE, "r", encoding="utf-8") as f:
    raw = json.load(f)
d = {k: unwrap(v) for k, v in raw.items()}
hl = d.get("HaveLearnedDictionary") or {}
lv = collections.Counter()
for w, info in hl.items():
    if is_jp(w):
        lv[info.get("masteryLevel") if isinstance(info, dict) else "?"] += 1
lines = ["日语词的 masteryLevel 分布: %r" % dict(lv)]
labels = {
    "weibiaoReview_If": "未标(0)", "yiwangReview_If": "易忘(1)", "yibanReview_If": "一般(2)",
    "jiaohaoReview_If": "较好(3)", "henhaoReview_If": "很好(4)", "cipoReview_If": "词破(5)"
}
for k, name in labels.items():
    lines.append("  %s = %r" % (name, d.get(k)))
lines.append("")
lines.append("S8TestWordList_DailyReview n = %d" % len(d.get("S8TestWordList_DailyReview") or []))
lines.append("  含日语 = %d" % sum(1 for w in (d.get("S8TestWordList_DailyReview") or []) if is_jp(w)))
lines.append("allTestWordsS10_Para n = %d" % len(d.get("allTestWordsS10_Para") or []))
lines.append("  含日语 = %d" % sum(1 for w in (d.get("allTestWordsS10_Para") or []) if is_jp(w)))
with io.open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
print("ok")

