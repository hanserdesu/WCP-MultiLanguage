# -*- coding: utf-8 -*-
"""Validate the v1.4.0 stem/option rewrite (JpWordListMod.cs) against the live game data.

Mirrors the C# 1:1:
  ReadingOf(entry)   -> kana inside 【】, must be kana-only
  StripReading(entry)-> entry minus 【..】, None when there is no bracket / nothing left
  KanjiOption(w, o)  -> rest of o (or of the book entry), prefixed with w unless rest already starts with w
  PostMcGen          -> stem = reading of the correct option meaning, options = KanjiOption

Inputs: the live SaveFile.es3 (book, pools, learned dict) and wcpOnlyWord.db `pron.meaning`,
which is the source the game actually rendered from in the screenshots (SelfBookMeaningConnectIf=false).
"""
import io
import json
import os
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")
PD = r"C:/Users/hanserdesu/AppData/LocalLow/WCP/wcp"
G = r"E:/Steam/steamapps/common/WCP-WordGirlgriend"


def unwrap(node):
    if isinstance(node, dict):
        if "__type" in node and "value" in node:
            return unwrap(node["value"])
        return {k: unwrap(v) for k, v in node.items()}
    if isinstance(node, list):
        return [unwrap(x) for x in node]
    return node


sv = {k: unwrap(v) for k, v in json.load(io.open(os.path.join(PD, "SaveFile.es3"), encoding="utf-8")).items()}
mb = {k: unwrap(v) for k, v in json.load(io.open(os.path.join(PD, "MyBook.es3"), encoding="utf-8")).items()}

BOOK = sv.get("ChosenBook_Para")
BLIST = sv.get("ChosenBook_List") or []
IDX = {"一": 1, "二": 2, "三": 3, "四": 4}
which = IDX.get([c for c in BOOK if c in IDX][0], 1) if BOOK else 1
BDICT = mb.get("wordDictionary%d" % which) or {}

con = sqlite3.connect("file:%s?mode=ro" % os.path.join(G, "wcp_Data", "StreamingAssets", "wcpOnlyWord.db"), uri=True)
MEANING = dict(con.execute("SELECT word, meaning FROM pron").fetchall())
con.close()
print("book=%r idx=%d  words=%d  book_dict=%d  db_entries=%d"
      % (BOOK, which, len(BLIST), len(BDICT), len(MEANING)))


def is_kana_only(s):
    for c in s:
        o = ord(c)
        if 0x3040 <= o <= 0x30FF or o in (0x30FB, 0x30FC, 0x3099, 0x309A, 0x309B, 0x309C):
            continue
        if 0xFF66 <= o <= 0xFF9F or c in " .\u3000-":
            continue
        return False
    return True


def has_kanji(w):
    return any(0x3400 <= ord(c) <= 0x4DBF or 0x4E00 <= ord(c) <= 0x9FFF or 0xF900 <= ord(c) <= 0xFAFF for c in w)


def reading_of(entry):
    if not entry:
        return None
    a = entry.find("【")
    if a < 0:
        return None
    b = entry.find("】", a + 1)
    if b < 0 or b <= a + 1:
        return None
    k = entry[a + 1:b].strip()
    if not k or not is_kana_only(k):
        return None
    return k


def strip_reading(entry):
    if not entry:
        return None
    a = entry.find("【")
    if a < 0:
        return None
    b = entry.find("】", a + 1)
    if b < 0:
        return None
    rest = (entry[:a] + entry[b + 1:]).strip()
    return rest or None


def kanji_option(word, orig):
    if not word or not orig:
        return orig
    rest = strip_reading(orig)
    if rest is None:
        rest = strip_reading(BDICT.get(word))
        if rest is None:
            return orig
    if rest.startswith(word):
        return rest
    return word + " " + rest


# every word of the book that the game can render a meaning for
words = [w for w in BLIST if w in MEANING or w in BDICT]
no_entry = [w for w in BLIST if w not in MEANING and w not in BDICT]
print("book words with a usable entry: %d  (no entry at all: %d)" % (len(words), len(no_entry)))
print()

fail = []
n_kana_word = 0
n_kanji_word = 0
n_reading = 0
leak = []
missing_kanji = []
for w in words:
    entry = MEANING.get(w) or BDICT.get(w)
    kana = reading_of(entry)
    opt = kanji_option(w, entry)
    stem = kana or w
    if has_kanji(w):
        n_kanji_word += 1
        if kana:
            n_reading += 1
            # requirement: options show the kanji spelling + Chinese meaning
            if w not in opt:
                missing_kanji.append((w, entry, opt))
            # invariant: the rewrite must not invent content -- it is exactly rest, or word + " " + rest
            rest = strip_reading(entry)
            if opt not in (rest, w + " " + rest):
                fail.append((w, entry, opt, "invented content"))
            # invariant: the option must not open with the kana reading (that would give the answer away)
            if opt.startswith(kana):
                leak.append((w, entry, opt))
        else:
            # no reading in the data -> stem stays as the kanji word (nothing we can do)
            pass
    else:
        n_kana_word += 1
        # kana word: the option must stay the plain meaning (no echo of the kana word)
        if opt != entry:
            fail.append((w, entry, opt, "kana word option changed"))
    if not is_kana_only(stem) and has_kanji(w) and kana:
        fail.append((w, entry, opt, "stem is not kana"))

print("words with kanji = %d   (of those, entry carries a kana reading = %d)" % (n_kanji_word, n_reading))
print("kana-only words  = %d" % n_kana_word)
print()


def show(name, rows, limit=6):
    print("   %-46s %d" % (name, len(rows)))
    for r in rows[:limit]:
        print("        %r" % (r,))


show("options missing the kanji spelling", missing_kanji)
show("options still containing the kana reading (leak)", leak)
show("other violations", fail)
print()

# ---- the screenshot case, replayed ----
print("=== the screenshot question replayed (stem + 4 options) ===")
S9 = [sv.get("S9Option%d_Para" % i) for i in (1, 2, 3, 4)]
stem_word = "全部"
opts_words = ["絵", "つける", "うち", "全部"]
print("   before:")
print("       stem      = %s" % stem_word)
for w in opts_words:
    print("       option    = %s" % (MEANING.get(w) or BDICT.get(w)))
print("   after:")
print("       stem      = %s" % (reading_of(MEANING.get(stem_word)) or stem_word))
for w in opts_words:
    print("       option    = %s" % kanji_option(w, MEANING.get(w) or BDICT.get(w)))
print()

ok = not missing_kanji and not leak and not fail
print("RESULT:", "ALL PASS" if ok else "FAILED")
sys.exit(0 if ok else 1)
