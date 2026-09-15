# -*- coding: utf-8 -*-
"""Verify the portable, profile-only scope in WCP JP plugins v1.6.0 / v1.2.0.

The source of truth is the selected custom book's full registered fingerprint,
not its slot number and not a language heuristic.
"""
import hashlib
import io
import json
import os
import sys
import unicodedata

sys.stdout.reconfigure(encoding="utf-8")
PD = r"C:/Users/hanserdesu/AppData/LocalLow/WCP/wcp"
CANON = ["自定义词书一", "自定义词书二", "自定义词书三", "自定义词书四"]
COSMETIC = "日语词库(猫条版)"
PROFILES = {
    (7922, "6d7a51c0c5d30dd63d8a6e3412bce1cf2419554fb8487cf5c8a205e43ac41663"): "catbar-jlpt-complete",
}


def unwrap(node):
    if isinstance(node, dict):
        if "__type" in node and "value" in node:
            return unwrap(node["value"])
        return {k: unwrap(v) for k, v in node.items()}
    if isinstance(node, list):
        return [unwrap(v) for v in node]
    return node


def load(path):
    with io.open(path, "r", encoding="utf-8") as f:
        return {k: unwrap(v) for k, v in json.load(f).items()}


def looks_japanese(word):
    for c in word or "":
        o = ord(c)
        if 0x3040 <= o <= 0x30FF or 0x3400 <= o <= 0x4DBF or 0x4E00 <= o <= 0x9FFF:
            return True
        if 0xF900 <= o <= 0xFAFF or 0xFF66 <= o <= 0xFF9D or o in (0x3005, 0x3006, 0x3007):
            return True
    return False


def fingerprint(words):
    normalized = sorted(unicodedata.normalize("NFC", word.strip()) for word in words)
    payload = "".join(word + "\n" for word in normalized)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def profile_of(words):
    if not words:
        return None
    return PROFILES.get((len(words), fingerprint(words)))


def slot_of(name):
    if not name:
        return -1
    for i, prefix in enumerate(CANON):
        if name.startswith(prefix):
            return i
    return -1


def book_state(name, loaded_words, slot_words):
    """Mirrors JpWordListPlugin.BookStateRaw: 1=active, 0=do nothing."""
    slot = slot_of(name)
    if slot < 0 or len(loaded_words) < 5:
        return 0
    mem = profile_of(loaded_words)
    disk = profile_of(slot_words)
    return 1 if mem is not None and mem == disk else 0


def display_name(name, current_name, slot_words):
    """Mirrors BookNamePlugin.ToCosmeticIfManaged."""
    slot = slot_of(name)
    if slot < 0 or slot != slot_of(current_name):
        return name
    return COSMETIC if profile_of(slot_words) is not None else name


def canonical_when_clicked(label, button_index):
    """Mirrors guarded SonBookChoose prefix."""
    return CANON[button_index] if label == COSMETIC else label


mb = load(os.path.join(PD, "MyBook.es3"))
sv = load(os.path.join(PD, "SaveFile.es3"))
en = load(os.path.join(PD, "SaveFile_Copy4.es3"))
slots = [list(mb.get("SelfBookList%d" % i) or []) for i in range(1, 5)]
jp_list = sv.get("ChosenBook_List") or []
en_list = en.get("ChosenBook_List") or []
levels = load(r"D:/Japanese/wcp_wordbooks/output/jlpt_books.json").get("levels") or {}
combined = []
seen = set()
for level in ("n5", "n4", "n3", "n2", "n1"):
    for row in levels.get(level) or []:
        word = (row.get("word") or "").strip()
        meaning = (row.get("meaning") or row.get("meaning_en") or "").strip()
        if word and meaning and word not in seen:
            seen.add(word)
            combined.append(word)

# Test the retired four-chapter layout from the source corpus, rather than
# reading the live slots: after migration slot 1 intentionally holds `combined`.
legacy_chapters = []
for chapter_levels in (("n5", "n4"), ("n3",), ("n2",), ("n1",)):
    chapter = []
    for level in chapter_levels:
        for row in levels.get(level) or []:
            word = (row.get("word") or "").strip()
            meaning = (row.get("meaning") or row.get("meaning_en") or "").strip()
            if word and meaning:
                chapter.append(word)
    legacy_chapters.append(chapter)

print("MyBook slots (full profile only; their numbers are deliberately not part of the identity):")
for i, words in enumerate(slots):
    print("  slot %d: words=%d Japanese=%d profile=%s" % (i + 1, len(words), sum(1 for w in words if looks_japanese(w)), profile_of(words)))
print("real original-book sample: %r words=%d profile=%s" % (en.get("ChosenBook_Para"), len(en_list), profile_of(en_list)))
print("combined portable book: words=%d profile=%s" % (len(combined), profile_of(combined)))
print()

ok = [True]


def check(label, got, want):
    good = got == want
    print("  [%s] %-70s got=%r want=%r" % ("PASS" if good else "FAIL", label, got, want))
    ok[0] = ok[0] and good


print("=== plugin activity scope ===")
for i in range(4):
    check("combined portable book imported in slot %d is active when selected" % (i + 1), book_state(CANON[i], combined, combined), 1)
for i, words in enumerate(legacy_chapters):
    check("legacy separate Japanese book in slot %d is inert" % (i + 1), book_state(CANON[i], words, words), 0)
for i in range(4):
    check("English portable book imported in slot %d is inert" % (i + 1), book_state(CANON[i], en_list, en_list), 0)
other_jp = list(combined)
other_jp[-1] = "別の日语词书"
check("unrelated Japanese custom book with the same size is inert", book_state(CANON[0], other_jp, other_jp), 0)
check("built-in original English book is inert", book_state(en.get("ChosenBook_Para"), en_list, en_list), 0)
check("transition: slot says English but loaded profile is managed -> inert", book_state(CANON[1], combined, en_list), 0)
check("transition: slot says managed but loaded profile is English -> inert", book_state(CANON[1], en_list, combined), 0)
print()

print("=== book-title scope and click safety ===")
for i in range(4):
    check("selected combined slot %d gets exact requested title" % (i + 1), display_name(CANON[i], CANON[i], combined), COSMETIC)
    other_i = (i + 1) % 4
    check("non-current slot %d keeps its original label" % (other_i + 1), display_name(CANON[other_i], CANON[i], combined), CANON[other_i])
    check("clicking cosmetic title in slot %d restores canonical game name" % (i + 1), canonical_when_clicked(COSMETIC, i), CANON[i])
check("selected English custom slot keeps original label", display_name(CANON[0], CANON[0], en_list), CANON[0])
print()

print("=== static write-gate audit ===")
source = io.open(r"D:/Japanese/mod_jp_wordlist/JpWordListMod.cs", encoding="utf-8").read()
for needle in ["if (state != 1) return;", "if (BookState() != 1) return;", "RestoreSharedFields();", "RegenerateByGame();"]:
    check("source contains guard: " + needle, needle in source, True)
check("managed queue repair persists ES3 values so game reloads the repaired pool",
      "ES3.Save(" in source, True)
check("leaving profile restores game-owned runtime queues", "RestoreSharedFields();" in source, True)
print()
print("RESULT:", "ALL PASS" if ok[0] else "FAILED")
sys.exit(0 if ok[0] else 1)
