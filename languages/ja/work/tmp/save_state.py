# -*- coding: utf-8 -*-
"""Dump the game save state relevant to the JP word-list mod."""
import io, json, os, sys, collections

sys.stdout.reconfigure(encoding="utf-8")
PD = r"C:\Users\hanserdesu\AppData\LocalLow\WCP\wcp"
SAVE = os.path.join(PD, "SaveFile.es3")
MYBOOK = os.path.join(PD, "MyBook.es3")


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


def describe(name, val, limit=6):
    if isinstance(val, list):
        jp = sum(1 for w in val if is_jp(str(w)))
        print("%-32s len=%-5d jp=%-5d ascii=%-5d %s" % (name, len(val), jp, len(val) - jp, [str(x) for x in val[:limit]]))
    else:
        print("%-32s %r" % (name, val))


d = load(SAVE)
print("=== SaveFile.es3 ===")
for k in ["ChosenBook_Para", "S7FightWordType", "ReviewRange_Para", "S7FightWordMax",
          "TestWordsNum_Para", "level0If", "level1If", "level2If", "level3If", "level4If",
          "level5If", "WordPriority_Para", "FreeChooseMode", "LearnedWordOrderMethod",
          "S8ThisMode_Para", "testingIf_Para", "testingIf_CompleteIf", "S9CurrentArrayName_Para",
          "S8Progress_Para", "rightOption_S9"]:
    if k in d:
        describe(k, d[k])
    else:
        print("%-32s <missing>" % k)

print()
print("=== lists ===")
for k in ["ChosenBook_List", "S7TestWordList_Para", "allTestWordsS10_Para", "S9extraStudy_Para",
          "S9CurrentArray_Para", "S8TestWordList_DailyReview", "S8TestWordList_DailyReview_left",
          "S8TestWordList_DailyStudy", "S8TestWordList_ExtraReview", "S8TestWordList_ExtraStudy",
          "S8TestWordList_LearnedTest_left", "S9CurrentArrayUnChosen_Para"]:
    describe(k, d.get(k))

print()
hl = d.get("HaveLearnedDictionary") or {}
jp = [w for w in hl if is_jp(w)]
print("HaveLearnedDictionary total=%d jp=%d ascii=%d" % (len(hl), len(jp), len(hl) - len(jp)))
print("  jp sample:", jp[:8])

print()
print("=== MyBook.es3 ===")
mb = load(MYBOOK)
for k in sorted(mb.keys()):
    v = mb[k]
    if isinstance(v, list):
        jp2 = sum(1 for w in v if is_jp(str(w)))
        print("%-24s len=%-5d jp=%-5d %s" % (k, len(v), jp2, [str(x) for x in v[:4]]))
    elif isinstance(v, dict):
        print("%-24s dict keys=%d %s" % (k, len(v), list(v.keys())[:3]))
    else:
        print("%-24s %r" % (k, v))
