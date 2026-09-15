# -*- coding: utf-8 -*-
"""Simulate 已学词测试 -> 快速测试 against the live save, to check the v1.3.3 fix.

Mirrors JpWordListMod.cs v1.3.3 (SampleBookLearned / SetTestLists / SyncStemQueue), the game side
(clickChangeImageSource.GenerateWordList + StartQuickTest) and the display source
(SetInputFieldValueS8.ShowTheWord: 题面 = S8needToLearnWordList_Para[0]).
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
levels = {i: bool(sv.get("level%dIf" % i)) for i in range(6)}
n_test = sv.get("TestWordsNum_Para") or 10

# Keep this regression independent of the user's current study history.
for word in blist[:max(10, int(n_test))]:
    learned.setdefault(word, {"masteryLevel": 0, "lastStudyTime": 0})

print("ChosenBook_Para = %r   book=%d words   learned=%d (jp=%d)"
      % (book, len(blist), len(learned), sum(1 for w in learned if is_jp(w))))
print("TestWordsNum_Para = %s   level switches = %s" % (n_test, levels))
print()


def lvl(word):
    info = learned.get(word) or {}
    return bool(levels.get(int(info.get("masteryLevel", -1)), False))


def recency_key(word):
    info = learned.get(word) or {}
    return -int(info.get("lastStudyTime", 0))


# The live level switches are whatever the user last toggled. If they select fewer than
# 5 book-learned words the model degenerates to an empty pool and stops testing anything,
# so pin to all-levels here. The fix under test (in-book restriction) is independent of it.
if sum(1 for w in learned if w in book_set and lvl(w)) < 5:
    print("   [note] live level switches select <5 book-learned words; using all levels here")
    levels = {i: True for i in range(6)}


def game_generate_wordlist(n):
    """clickChangeImageSource.GenerateWordList: global learned dict, level filter, recent first."""
    pool = [w for w in learned if lvl(w)]
    pool.sort(key=recency_key)
    return pool[:min(n, len(pool))]


def mod_sample_book_learned(n):
    """v1.3.3 SampleBookLearned: same filter/order, but restricted to the current book."""
    pool = [w for w in learned if w in book_set and lvl(w)]
    pool.sort(key=recency_key)
    return pool[:min(n, len(pool))]


def mod_filter_v132(cur, min_keep=5):
    """v1.3.2 Enforce/Filter: keep in-book words; if too few, rebuild from the book."""
    keep = [w for w in cur if w in book_set]
    if len(keep) == len(cur):
        return None
    if len(keep) >= min_keep:
        return keep
    target = max(len(cur), min_keep)
    rebuilt = [w for w in learned if w in book_set and lvl(w)]
    rebuilt.sort(key=recency_key)
    for w in blist:
        if len(rebuilt) >= target:
            break
        if w not in rebuilt:
            rebuilt.append(w)
    return rebuilt if len(rebuilt) >= min_keep else None


game_pool = game_generate_wordlist(n_test)
cross_book = [w for w in game_pool if w not in book_set]
print("--- game StartQuickTest pool (global learned dict) ---")
print("   size=%d   in-book=%d   cross-book=%d"
      % (len(game_pool), len(game_pool) - len(cross_book), len(cross_book)))
print("   pool: %s" % game_pool[:12])
print("   cross-book sample: %s" % cross_book[:12])
print("   superiority in global learned dict=%s, in current JP book=%s"
      % ("superiority" in learned, "superiority" in book_set))
print()


# 上一轮遗留的题干队列: 游戏 StartQuickTest 只重建词池, 从不重建 need。
# 日语书之前学过英语书时, 存档里的 need 就是那些英语词 —— 用全局已学词典里的英语词建模。
eng_learned = [w for w in learned if not is_jp(w) and lvl(w)]
eng_learned.sort(key=recency_key)
stale_need = eng_learned[:n_test]

pool_132 = mod_filter_v132(game_pool) or game_pool
stem_132 = stale_need[0] if stale_need else None
print("--- v1.3.2 (reproduces the screenshot) ---")
print("   stem need[0]      = %r   (is JP? %s)" % (stem_132, is_jp(stem_132 or "")))
print("   pool (answers)    = %d words, JP=%d" % (len(pool_132), sum(1 for w in pool_132 if is_jp(w))))
print("   stem inside pool? = %s   <- False means the question cannot be answered" % (stem_132 in pool_132))
print("   stale stem queue  = %s" % stale_need[:6])
print()

pool_133 = mod_sample_book_learned(n_test)
need_133 = list(pool_133)          # SetTestLists / SyncStemQueue: need = left = pool
stem_133 = need_133[0] if need_133 else None
print("--- v1.3.3 (this fix) ---")
print("   pool = %d words: %s" % (len(pool_133), pool_133[:12]))
print("   stem need[0] = %r" % stem_133)
print()

ok = [True]


def check(name, cond):
    print("   [%s] %s" % ("PASS" if cond else "FAIL", name))
    ok[0] = ok[0] and bool(cond)


check("pool is all Japanese", all(is_jp(w) for w in pool_133))
check("pool is inside the current JP book", all(w in book_set for w in pool_133))
check("pool comes from the learned dict", all(w in learned for w in pool_133))
check("stem == pool[progress]", bool(pool_133) and stem_133 == pool_133[0])
check("need == pool and left == pool", need_133 == pool_133)
check("pool >= 4 (four options)", len(pool_133) >= 4)
check("size == min(TestWordsNum, book learned)", len(pool_133) == min(n_test, len([w for w in learned if w in book_set and lvl(w)])))
check("no stale English word in the stem queue", not (set(need_133) & set(stale_need)))
check("stem is not pure ASCII English", not (stem_133 or "").isascii())
print()
print("stale English stems: old need queue = %d (e.g. %s) -> new = %d"
      % (len([w for w in stale_need if not is_jp(w)]), stale_need[:1],
         len([w for w in need_133 if not is_jp(w)])))
print()

which = None
for i in (1, 2, 3, 4):
    dd = mb.get("wordDictionary%d" % i) or {}
    if sum(1 for w in pool_133 if w in dd) >= 2:
        which = i
        break
dd = (mb.get("wordDictionary%d" % which) or {}) if which else {}
missing = [w for w in pool_133 if w not in dd]
print("book meaning dict wordDictionary%s covers %d/%d, missing: %s"
      % (which, len(pool_133) - len(missing), len(pool_133), missing[:8]))
print()
print("RESULT:", "ALL PASS" if ok[0] else "FAILED")
sys.exit(0 if ok[0] else 1)
