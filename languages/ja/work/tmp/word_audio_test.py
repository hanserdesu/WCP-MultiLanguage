# -*- coding: utf-8 -*-
"""Model check for the word-audio fix (JpWordListPlugin v1.7.5).

Local word audio lives in <persistentDataPath>/../vocabulary named by the KANJI
surface (e.g. 筋.mp3), while the plugin rewrites the question stem to KANA (すじ).
PrePlayWordAudio swaps the shown kana back to the surface before the lookup.

Checks, on the real book dictionary and the real audio folder:
  * the pre-fix lookup (kana) misses,
  * the fix's kana -> surface mapping resolves it,
  * how often the mapping reaches an existing mp3.
"""
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
SAVE_DIR = r"C:/Users/hanserdesu/AppData/LocalLow/WCP/wcp"
AUDIO_DIR = r"C:/Users/hanserdesu/AppData/LocalLow/WCP/vocabulary"


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
    if not s:
        return False
    for c in s:
        o = ord(c)
        ok = (0x3040 <= o <= 0x30FF) or o in (0x30FB, 0x30FC, 0x3099, 0x309A,
                                              0x309B, 0x309C, 0x20, 0x2E,
                                              0x3000, 0x2D) or (0xFF66 <= o <= 0xFF9F)
        if not ok:
            return False
    return True


def reading_of(entry):
    """JpWordListPlugin.ReadingOf: text inside the brackets when it is kana-only."""
    if not entry:
        return None
    a = entry.find("\u3010")
    if a < 0:
        return None
    b = entry.find("\u3011", a + 1)
    if b < 0 or b <= a + 1:
        return None
    kana = entry[a + 1:b].strip()
    return kana if (kana and is_kana_only(kana)) else None


def build_kana_map(book_dict):
    """JpWordListPlugin.BuildKanaMap: kana -> surface, shortest surface wins."""
    out = {}
    for surface, entry in (book_dict or {}).items():
        if not surface:
            continue
        kana = reading_of(entry)
        if kana is None or kana == surface:
            continue
        cur = out.get(kana)
        if cur is None or len(surface) < len(cur):
            out[kana] = surface
    return out


def mp3(word):
    return bool(word) and os.path.exists(os.path.join(AUDIO_DIR, word + ".mp3"))


ok = [True]


def check(name, cond):
    print("   [%s] %s" % ("PASS" if cond else "FAIL", name))
    ok[0] = ok[0] and bool(cond)


mybook = load(os.path.join(SAVE_DIR, "MyBook.es3"))
book_dict = mybook.get("wordDictionary1") or {}
kana_map = build_kana_map(book_dict)
print("book dictionary: %d entries, kana map: %d readings" % (len(book_dict), len(kana_map)))
print()

print("--- the screenshot's word (suji) ---")
check("stem kana has no mp3 (pre-fix lookup would miss)", not mp3("\u3059\u3058"))
surface = kana_map.get("\u3059\u3058")
print("   kana -> %r" % surface)
check("kana map resolves the reading to its surface", surface is not None)
check("the resolved surface has a local mp3 (post-fix hits)", mp3(surface))

print()
print("--- coverage over the whole book ---")
kanji_words = [s for s in book_dict if reading_of(book_dict[s]) and reading_of(book_dict[s]) != s]
hit = [s for s in kanji_words if mp3(kana_map.get(reading_of(book_dict[s])))]
rate = 100.0 * len(hit) / max(1, len(kanji_words))
print("   kanji words with a reading: %d, mapping reaches an mp3: %d (%.1f%%)"
      % (len(kanji_words), len(hit), rate))
check("a clear majority of kana stems resolve to a local mp3", len(hit) * 2 >= len(kanji_words))

print()
print("RESULT:", "ALL PASS" if ok[0] else "FAILED")
sys.exit(0 if ok[0] else 1)
