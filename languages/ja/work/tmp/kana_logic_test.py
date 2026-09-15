# -*- coding: utf-8 -*-
"""Validate the mod's KanaOf / KanjiOption logic against real MyBook.es3 + SaveFile.es3 data.

Mirrors the C# in JpWordListMod.cs (KanaOf / KanjiOption / EntryOf) 1:1.
"""
import io, json, os, sys, collections

sys.stdout.reconfigure(encoding="utf-8")
PD = r"C:/Users/hanserdesu/AppData/LocalLow/WCP/wcp"
MYBOOK = os.path.join(PD, "MyBook.es3")
SAVE = os.path.join(PD, "SaveFile.es3")


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


def is_kana_only(s):
    for ch in s:
        o = ord(ch)
        if 0x3040 <= o <= 0x30FF:
            continue
        if o in (0x30FB, 0x30FC, 0x3099, 0x309A, 0x309B, 0x309C):
            continue
        if 0xFF66 <= o <= 0xFF9F:
            continue
        if ch in " .\u3000-":
            continue
        return False
    return True


ESC_NL = "\\n"


def clean_entry(v):
    return v.replace(ESC_NL, "\n")


def kana_of(entry):
    """C# KanaOf: pull 【kana】 out of a raw dictionary entry."""
    if not entry:
        return None
    e = clean_entry(entry)
    a = e.find("【")
    if a < 0:
        return None
    b = e.find("】", a + 1)
    if b < 0 or b <= a + 1:
        return None
    k = e[a + 1:b].strip()
    if not k or not is_kana_only(k):
        return None
    return k


def kanji_option(word, entry):
    """C# KanjiOption: 'word + ' + entry-with-【kana】-removed."""
    if not word or not entry:
        return None
    e = clean_entry(entry)
    a = e.find("【")
    if a < 0:
        return None
    b = e.find("】", a + 1)
    if b < 0:
        return None
    rest = (e[:a] + e[b + 1:]).strip()
    if not rest:
        return None
    return word + " " + rest


def is_jp(w):
    for ch in w or "":
        o = ord(ch)
        if 0x3040 <= o <= 0x30FF or 0x3400 <= o <= 0x4DBF or 0x4E00 <= o <= 0x9FFF \
           or 0xF900 <= o <= 0xFAFF or 0xFF66 <= o <= 0xFF9D or o in (0x3005, 0x3006, 0x3007):
            return True
    return False


mb = load(MYBOOK)
sv = load(SAVE)
book = sv.get("ChosenBook_Para")
blist = sv.get("ChosenBook_List") or []
learned = sv.get("HaveLearnedDictionary") or {}

print("ChosenBook_Para =", repr(book), " ChosenBook_List n =", len(blist))

which = None
for i in (1, 2, 3, 4):
    d = mb.get("wordDictionary%d" % i) or {}
    if "歯医者" in d:
        which = i
        print("歯医者 found in wordDictionary%d (n=%d)" % (i, len(d)))
for i in (1, 2, 3, 4):
    lst = mb.get("SelfBookList%d" % i)
    if lst is not None:
        print("SelfBookList%d n=%d jp=%d" % (i, len(lst), sum(1 for w in lst if is_jp(w))))

d = mb.get("wordDictionary%d" % (which or 1)) or {}

bracket = [w for w in d if "【" in (d[w] or "")]
no_bracket = [w for w in d if "【" not in (d[w] or "")]
print("entries=%d  with【】=%d  without=%d" % (len(d), len(bracket), len(no_bracket)))

# --- how many bracket entries fail the kana-only gate (would leave the stem as 漢字) ---
bad_kana = []
multi = []
empty_rest = []
for w in bracket:
    e = clean_entry(d[w])
    k = kana_of(e)
    if k is None:
        bad_kana.append((w, d[w]))
    if e.count("【") > 1:
        multi.append((w, d[w]))
    if kanji_option(w, e) is None:
        empty_rest.append((w, d[w]))
print("【】 entries whose reading is NOT kana-only:", len(bad_kana))
for w, v in bad_kana[:12]:
    print("   ", repr(w), "=>", repr(v))
print("entries with multiple 【 :", len(multi), multi[:5])
print("entries where option text would be empty:", len(empty_rest), empty_rest[:5])

print()
print("--- sample conversions (word -> stem kana | option) ---")
for w in ["歯医者", "続ける", "全部", "豚肉", "工業", "黄色", "今週", "止む", "割れる", "世話する"]:
    if w in d:
        print("  %-8s kana=%-12s opt=%s" % (w, kana_of(d[w]), kanji_option(w, d[w])))
    else:
        print("  %-8s <not in dict>" % w)

print()
print("--- kana-only words (no 【】): stem stays as the word, options keep plain meaning ---")
for w in no_bracket[:8]:
    print("  %-10s => %r" % (w, d[w]))

print()
# --- coverage over the learned Japanese words the test actually uses ---
jp_learned = [w for w in blist if w in learned and is_jp(w)]
print("book learned jp words =", len(jp_learned))
have = [w for w in jp_learned if kana_of(d.get(w)) is not None]
print("  of those, entry gives a kana reading (stem becomes kana):", len(have))
nokey = [w for w in jp_learned if w not in d]
print("  of those, missing from dictionary:", len(nokey), nokey[:10])
noread = [w for w in jp_learned if w in d and kana_of(d[w]) is None and any(0x4E00 <= ord(c) <= 0x9FFF for c in w)]
print("  kanji words with NO kana reading in entry:", len(noread), noread[:15])
for w in noread[:10]:
    print("      ", repr(w), "=>", repr(d[w]))

print()
print("--- full-book coverage ---")
kanji_words = [w for w in blist if any(0x4E00 <= ord(c) <= 0x9FFF for c in w)]
withread = [w for w in kanji_words if w in d and kana_of(d[w]) is not None]
print("book words containing kanji = %d ; with a usable kana reading = %d (%.1f%%)"
      % (len(kanji_words), len(withread), 100.0 * len(withread) / max(1, len(kanji_words))))
print("book words missing from the meaning dictionary =", sum(1 for w in blist if w not in d))
