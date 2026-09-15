# -*- coding: utf-8 -*-
"""Compare key list fields across SaveFile.es3 snapshots."""
import io, json, os, sys

sys.stdout.reconfigure(encoding="utf-8")
PCL = r"C:/Users/hanserdesu/AppData/LocalLow/WCP/wcp"
FILES = [
    "SaveFile.es3",
    os.path.join("_bak_20260912_2100", "SaveFile.es3"),
    "SaveFile_Copy8.es3",
    "SaveFile_Copy7.es3",
]
KEYS = ["S9CurrentArray_Para", "S9extraStudy_Para", "S9CurrentArrayName_Para",
        "S9CurrentArrayUnChosen_Para", "allTestWordsS10_Para", "S7TestWordList_Para",
        "S8TestWordList_LearnedTest_left", "ChosenBook_Para", "S8Progress_Para"]


def unwrap(node):
    if isinstance(node, dict):
        if "__type" in node and "value" in node:
            return unwrap(node["value"])
        return {k: unwrap(v) for k, v in node.items()}
    if isinstance(node, list):
        return [unwrap(x) for x in node]
    return node


def load(path):
    with io.open(path, "r", encoding="utf-8") as f:
        return {k: unwrap(v) for k, v in json.load(f).items()}


def is_jp(w):
    for ch in w or "":
        o = ord(ch)
        if 0x3040 <= o <= 0x30FF or 0x3400 <= o <= 0x4DBF or 0x4E00 <= o <= 0x9FFF \
           or 0xF900 <= o <= 0xFAFF or 0xFF66 <= o <= 0xFF9D or o in (0x3005, 0x3006, 0x3007):
            return True
    return False


for name in FILES:
    path = os.path.join(PCL, name)
    if not os.path.exists(path):
        print("== %s : MISSING" % name)
        continue
    d = load(path)
    print("== %s  (%d bytes)" % (name, os.path.getsize(path)))
    for k in KEYS:
        v = d.get(k)
        if isinstance(v, list):
            jp = sum(1 for w in v if is_jp(str(w)))
            print("   %-32s len=%-7d jp=%-7d %s" % (k, len(v), jp, [str(x) for x in v[:3]]))
        else:
            print("   %-32s %r" % (k, v))
    print()
