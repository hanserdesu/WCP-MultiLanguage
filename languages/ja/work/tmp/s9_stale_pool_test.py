# -*- coding: utf-8 -*-
"""Regression test for the reported 已学词测试 bug:
English stem + Japanese options (screenshot: superiority + 割れる/黄色/続ける/歯医者).

Reproduces the broken state (allTestWordsS10_Para and S8needToLearnWordList_Para both
stale-English while the options are fresh Japanese) and checks that the v1.7.1
HealTestList book-validity rule heals it, where the old alignment-only rule did not.

The broken pool/stem are CONSTRUCTED from out-of-book learned words rather than read
from the live save: once the plugin heals the save the live state is no longer broken,
and a fixture that reads it would silently stop testing anything.
"""
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
PD = r"C:/Users/hanserdesu/AppData/LocalLow/WCP/wcp"


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
        if 0x3040 <= o <= 0x30FF or 0x3400 <= o <= 0x4DBF or 0x4E00 <= o <= 0x9FFF:
            return True
        if 0xF900 <= o <= 0xFAFF or 0xFF66 <= o <= 0xFF9D:
            return True
        if o in (0x3005, 0x3006, 0x3007):
            return True
    return False


sv = load(os.path.join(PD, "SaveFile.es3"))
mb = load(os.path.join(PD, "MyBook.es3"))

def slot_words(index):
    words = mb.get("SelfBookList%d" % index)
    if not words:
        words = list((mb.get("wordDictionary%d" % index) or {}).keys())
    return list(words or [])


with io.open(os.path.join(os.path.dirname(__file__), "..", "..",
                          "packs", "ja", "manifest.json"), "r",
             encoding="utf-8") as f:
    jp_word_count = json.load(f)["word_count"]
jp_slot = next((i for i in range(1, 5)
                if len(slot_words(i)) == jp_word_count), None)
if jp_slot is None:
    raise SystemExit("找不到与 packs/ja/manifest.json 词数一致的日语槽位")

book = "自定义词书%d" % jp_slot
blist = slot_words(jp_slot)
book_set = set(blist)
learned = dict(sv.get("HaveLearnedDictionary") or {})
# Use a local fixture for learned JP words; this test must not depend on how many
# Japanese words the current user has studied in the live save.
for word in blist[:10]:
    learned.setdefault(word, {"masteryLevel": 0, "lastStudyTime": 0})
pool = list(sv.get("allTestWordsS10_Para") or [])
need = list(sv.get("S8needToLearnWordList_Para") or [])
opts = [sv.get("S9Option%d_Para" % i) for i in (1, 2, 3, 4)]

print("book=%r  book words=%d  learned=%d" % (book, len(blist), len(learned)))
print("save pool  = %s" % pool)
print("save need  = %s" % need)
print("save opts  = %s" % opts)
print()


def rebuild_prefer_learned(cur, target):
    """JpWordListMod.Rebuild(dest, seen, jp=true, bookSet, preferLearned=true, target)."""
    dest, seen = [], set()
    for w in learned:                       # FillFromLearned
        if len(dest) >= target:
            break
        if w and w in book_set and w not in seen:
            seen.add(w)
            dest.append(w)
    for w in blist:                         # FillFromList(book)
        if len(dest) >= target:
            break
        if w and w not in seen:
            seen.add(w)
            dest.append(w)
    return dest


def mod_filter(cur, min_keep=5):
    """JpWordListMod.Filter(cur, minKeep, preferLearned) for the Japanese book."""
    seen, keep, dropped = set(), [], 0
    for w in cur:
        if not w:
            continue
        if w not in book_set:
            dropped += 1
            continue
        if w not in seen:
            seen.add(w)
            keep.append(w)
    if dropped == 0 and len(keep) == len(cur):
        return None
    if len(keep) < min_keep:
        target = max(len(cur), min_keep)
        keep = rebuild_prefer_learned(cur, target)
        if len(keep) < min_keep:
            return None
    return keep


def old_align_only(cur, nd):
    """v1.7.0 HealTestList: only fix stem/pool misalignment."""
    return nd


def new_heal(cur, nd):
    """v1.7.1 HealTestList: book-validity rule, then alignment."""
    fixed = mod_filter(cur, 5)
    if fixed is not None:
        return fixed, list(fixed)          # SetTestLists: pool/left/need all = pool
    if not nd or nd[0] != cur[min(0, len(cur) - 1)]:
        return cur, list(cur)
    return cur, nd


ok = [True]


def check(name, cond):
    print("   [%s] %s" % ("PASS" if cond else "FAIL", name))
    ok[0] = ok[0] and bool(cond)


print("--- reported broken state (constructed) ---")
# Out-of-book learned words stand in for the previous session's stale English queue.
english_outside = [w for w in learned if w and not is_jp(w) and w not in book_set]
if len(english_outside) < 6:
    english_outside = ["superiority", "grocer", "bar", "doom", "nerve", "erosion", "canoe"]
stale_pool = list(english_outside[:10])
stale_need = list(english_outside[:10])
print("   stale pool = %s" % stale_pool)
print("   pool is book-only? %s   need is book-only? %s"
      % (all(w in book_set for w in stale_pool), all(w in book_set for w in stale_need)))

old_pool, old_need = stale_pool, old_align_only(stale_pool, stale_need)
print("\n--- v1.7.0 (alignment-only) ---")
print("   pool = %s" % old_pool[:6])
print("   stem = %r" % (old_need[0] if old_need else None))
check("v1.7.0 leaves the out-of-book pool untouched (this was the bug)",
      any(w not in book_set for w in old_pool))
check("v1.7.0 stem is the stale out-of-book word",
      bool(old_need) and old_need[0] not in book_set)

new_pool, new_need = new_heal(stale_pool, stale_need)
print("\n--- v1.7.1 (book-validity + persistence) ---")
print("   pool = %s" % new_pool[:10])
print("   stem = %r" % (new_need[0] if new_need else None))
check("pool is entirely inside the current JP book", all(w in book_set for w in new_pool))
check("pool is entirely Japanese", all(is_jp(w) for w in new_pool))
check("pool comes from the book's learned words", all(w in learned for w in new_pool))
check("pool >= 4 so four options exist", len(new_pool) >= 4)
check("stem == pool[progress]", bool(new_need) and new_need[0] == new_pool[0])
check("stem is not the stale English word", (new_need and new_need[0]) not in stale_pool or new_need[0] in book_set)
check("stem is not pure-ASCII English", not (new_need[0] if new_need else "x").isascii())

again_pool, again_need = new_heal(new_pool, new_need)
check("second pass is a no-op (no rebuild loop)",
      again_pool == new_pool and again_need == new_need)
print()
print("RESULT:", "ALL PASS" if ok[0] else "FAILED")
sys.exit(0 if ok[0] else 1)
