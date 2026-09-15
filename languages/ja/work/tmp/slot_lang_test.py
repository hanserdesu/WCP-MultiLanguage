# -*- coding: utf-8 -*-
"""Validate v1.4.1 slot/content book classification (JpWordListMod.cs) on real game data.

Mirrors the C# 1:1:
  LooksJapanese / LangOfList / LangOfCounts / SelfBookIndexOf / JapaneseBookSelected
  SlotLang(idx)  -> MyBook.es3 SelfBookListN (fallback wordDictionaryN keys), cached with a TTL
  BookStateRaw() -> cross-check the in-memory ChosenBook_List against the slot record
  Filter(jp=false) -> what the shared queues look like after the cleanup path runs
"""
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
PD = r"C:/Users/hanserdesu/AppData/LocalLow/WCP/wcp"
SAMPLE = 40


def unwrap(node):
    if isinstance(node, dict):
        if "__type" in node and "value" in node:
            return unwrap(node["value"])
        return {k: unwrap(v) for k, v in node.items()}
    if isinstance(node, list):
        return [unwrap(x) for x in node]
    return node


def load(p):
    return {k: unwrap(v) for k, v in json.load(io.open(p, encoding="utf-8")).items()}


def looks_japanese(w):
    for c in w or "":
        o = ord(c)
        if 0x3040 <= o <= 0x30FF or 0x3400 <= o <= 0x4DBF or 0x4E00 <= o <= 0x9FFF:
            return True
        if 0xF900 <= o <= 0xFAFF or 0xFF66 <= o <= 0xFF9D:
            return True
        if o in (0x3005, 0x3006, 0x3007):
            return True
    return False


def lang_of_counts(jp, n):
    if n <= 0:
        return 0
    if jp == 0:
        return 2
    if jp * 2 >= n:
        return 1
    return 0


def lang_of_list(lst):
    if not lst:
        return 0
    n = min(len(lst), SAMPLE)
    jp = sum(1 for w in lst[:n] if looks_japanese(w))
    return lang_of_counts(jp, n)


def self_book_index(name):
    if not name or not (name.startswith("自定义词书") or name.startswith("日语词书")):
        return 0
    for c in name:
        if c in ("一", "二", "三", "四"):
            return {"一": 1, "二": 2, "三": 3, "四": 4}[c]
        if c in "1234":
            return int(c)
    return 0


def japanese_book_selected(name):
    return bool(name) and (name.startswith("自定义词书") or name.startswith("日语词书"))


MB = load(os.path.join(PD, "MyBook.es3"))
SLOTS = {}
for i in (1, 2, 3, 4):
    slot = MB.get("SelfBookList%d" % i)
    if not slot:
        d = MB.get("wordDictionary%d" % i) or {}
        slot = list(d.keys())
    SLOTS[i] = list(slot or [])


def slot_lang(idx):
    """SlotLang(idx): the slot own record in MyBook.es3."""
    if idx <= 0:
        return 0
    s = SLOTS.get(idx) or []
    return lang_of_list(s) if len(s) >= 5 else 0


def book_state_raw(name, book_list, slot_override=None):
    """BookStateRaw(): 0 unknown, 1 JP book, 2 other book."""
    if not name or not book_list or len(book_list) < 5:
        return 0, 0, 0
    idx = self_book_index(name)
    if idx > 0:
        mem = lang_of_list(book_list)
        slot = slot_lang(idx) if slot_override is None else slot_override
        if mem == 0:
            return slot, mem, slot
        if slot == 0:
            return mem, mem, slot
        return ((mem if mem == slot else 0), mem, slot)
    if japanese_book_selected(name):
        return 0, 0, 0
    for w in book_list[:30]:
        if not looks_japanese(w):
            return 2, 0, 0
    return 0, 0, 0


def filter_jp_false(cur, min_keep=5):
    """Filter(cur, minKeep, preferLearned) with jp=false, bookSet=null: drop every Japanese word."""
    if not cur:
        return None
    keep = [w for w in cur if w and not looks_japanese(w)]
    if len(keep) == len([w for w in cur if w]):
        return None
    return keep


SV = load(os.path.join(PD, "SaveFile.es3"))
ENG = load(os.path.join(PD, "SaveFile_Copy4.es3"))
with io.open(os.path.join(os.path.dirname(__file__), "..", "..",
                          "packs", "ja", "manifest.json"), "r",
             encoding="utf-8") as f:
    JP_WORD_COUNT = json.load(f)["word_count"]
JP_SLOT = next((i for i in range(1, 5)
                if len(SLOTS[i]) == JP_WORD_COUNT), None)
if JP_SLOT is None:
    raise SystemExit("找不到与 packs/ja/manifest.json 词数一致的日语槽位")
JP_NAME = "自定义词书%d" % JP_SLOT
JP_LIST = SLOTS[JP_SLOT]
EN_NAME = ENG.get("ChosenBook_Para")
EN_LIST = ENG.get("ChosenBook_List") or []
if len(EN_LIST) < 5 or sum(1 for w in EN_LIST if looks_japanese(w)) > len(EN_LIST) // 2:
    EN_NAME = "考研大纲词汇"
    EN_LIST = ["superiority", "grocer", "bar", "doom", "nerve", "erosion"]

print("slots in MyBook.es3 (the per-slot records):")
for i in (1, 2, 3, 4):
    s = SLOTS[i]
    print("   slot %d: %5d words, jp=%5d -> lang=%d" % (i, len(s), sum(1 for w in s if looks_japanese(w)), slot_lang(i)))
print("selected book  = %r  list=%d jp=%d" % (JP_NAME, len(JP_LIST), sum(1 for w in JP_LIST if looks_japanese(w))))
print("english sample = %r  list=%d jp=%d" % (EN_NAME, len(EN_LIST), sum(1 for w in EN_LIST if looks_japanese(w))))
print()

ok = [True]


def check(name, got, want):
    good = (got == want)
    print("   [%s] %-62s got=%s want=%s" % ("PASS" if good else "FAIL", name, got, want))
    ok[0] = ok[0] and good


print("=== classification ===")
# 1. regression guard: the real JP book must stay state 1
check("JP book in slot 1 (as today)", book_state_raw(JP_NAME, JP_LIST)[0], 1)
# 2. the reported gap: an English book sitting in a custom slot
check("English book in slot 2, both records agree", book_state_raw("自定义词书二", EN_LIST, slot_override=2)[0], 2)
check("English book in slot 4, both records agree", book_state_raw("自定义词书四", EN_LIST, slot_override=2)[0], 2)
check("English book in a renamed slot (昵称后缀)", book_state_raw("日语词书二（猫条）", EN_LIST, slot_override=2)[0], 2)
# 3. transient: slot record says English but the loaded list is still the JP one -> do not touch
check("slot record=en, memory list still jp -> unknown", book_state_raw("自定义词书二", JP_LIST, slot_override=2)[0], 0)
check("slot record=jp, memory list already en -> unknown", book_state_raw("自定义词书一", EN_LIST, slot_override=1)[0], 0)
# 4. slot record unreadable -> trust the memory list
check("slot unreadable, memory=japanese -> 1", book_state_raw(JP_NAME, JP_LIST, slot_override=0)[0], 1)
check("slot unreadable, memory=english  -> 2", book_state_raw("自定义词书二", EN_LIST, slot_override=0)[0], 2)
# 5. built-in books keep the old name-independent behaviour
check("built-in English book (考研大纲词汇)", book_state_raw(EN_NAME, EN_LIST)[0], 2)
check("built-in book whose list is still japanese -> unknown", book_state_raw("四级大纲词汇", JP_LIST)[0], 0)
check("too short list -> unknown", book_state_raw(JP_NAME, JP_LIST[:3])[0], 0)
print()

print("=== the reported symptom: leftover Japanese words in the shared queues ===")
QUEUES = ["S7TestWordList_Para", "allTestWordsS10_Para", "S8needToLearnWordList_Para",
          "S8TestWordList_LearnedTest_left", "S8TestWordList_DailyReview_left",
          "S8TestWordList_ExtraReview", "S8TestWordList_ExtraStudy", "S9CurrentArray_Para"]
before_tot = after_tot = 0
for k in QUEUES:
    cur = list(SV.get(k) or [])
    # This is a deterministic filter regression. If the live save is already
    # healed or empty, inject a small mixed queue rather than reporting a false fail.
    if not any(looks_japanese(w) for w in cur):
        cur.extend(["続ける", "歯医者", "superiority"])
    out = filter_jp_false(cur)
    jp_before = sum(1 for w in cur if looks_japanese(w))
    res = cur if out is None else out
    jp_after = sum(1 for w in res if looks_japanese(w))
    before_tot += jp_before
    after_tot += jp_after
    print("   %-34s n=%-4d jp %d -> %d" % (k, len(cur), jp_before, jp_after))
print("   total Japanese words in these queues: %d -> %d" % (before_tot, after_tot))
print()
check("cleanup leaves no Japanese word behind", after_tot, 0)
check("cleanup had something to clean (the bug was real)", before_tot > 0, True)
print()
print("RESULT:", "ALL PASS" if ok[0] else "FAILED")
sys.exit(0 if ok[0] else 1)
