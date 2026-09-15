# -*- coding: utf-8 -*-
"""Shared model of JpWordListPlugin.RestoreSharedFields / CrossBookGuard (v1.7.3)."""
import io
import json
import os
import sys

PD = r"C:/Users/hanserdesu/AppData/LocalLow/WCP/wcp"

POOL = "allTestWordsS10_Para"
NEED = "S8needToLearnWordList_Para"
LEFT = "S8TestWordList_LearnedTest_left"
OWNED_LISTS = "JpWL_owned_lists"
OWNED_ARRAYS = "JpWL_owned_arrays"
BAK = "JpWL_bak_"
JP_FIELDS = (POOL, NEED, LEFT)
ARRAY_FIELDS = ("S9extraStudy_Para",)


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


def looks_japanese(w):
    for ch in w or "":
        o = ord(ch)
        if 0x3040 <= o <= 0x30FF or 0x3400 <= o <= 0x4DBF or 0x4E00 <= o <= 0x9FFF:
            return True
        if 0xF900 <= o <= 0xFAFF or 0xFF66 <= o <= 0xFF9D:
            return True
        if o in (0x3005, 0x3006, 0x3007):
            return True
    return False


def contains_japanese(seq):
    for w in seq or []:
        if looks_japanese(w):
            return True
    return False


SV = load(os.path.join(PD, "SaveFile.es3"))
LEARNED = SV.get("HaveLearnedDictionary") or {}
ENGLISH_LEARNED = [w for w in LEARNED if not looks_japanese(w)][:10]
JP_POOL = ["続ける", "歯医者", "全部", "うち", "豚肉", "工業", "割れる", "黄色", "今週", "止む"]


def fresh_save():
    d = {
        POOL: list(JP_POOL),
        NEED: list(JP_POOL),
        LEFT: list(JP_POOL),
        "S8Progress_Para": 0,
        "testingIf_Para": True,
        "testingIf_CompleteIf": False,
        OWNED_LISTS: list(JP_FIELDS),
        OWNED_ARRAYS: [],
    }
    for k in JP_FIELDS:
        d[BAK + k] = list(ENGLISH_LEARNED)
    return d


def pool_too_short(save):
    """Mirror JpWordListPlugin.PoolTooShort: < 5 words crashes GenerateOptions."""
    pool = save.get(POOL)
    return not pool or len(pool) < 5


def restore_shared_fields(save, touched_lists=(), touched_arrays=(), mem=None):
    """Mirror JpWordListPlugin.RestoreSharedFields + RestoreQueues (v1.7.3).

    Restore range = fields touched this session (in-memory baseline in ``mem``)
    union the takeover markers persisted in the save (disk backup ``JpWL_bak_*``).
    A queue whose baseline is missing or itself Japanese is emptied.  The unfinished
    test is ended when a queue was emptied or the restored pool has < 5 words.
    Returns (save, ended).
    """
    mem = mem or {}
    list_keys = []
    for k in list(touched_lists) + list(save.get(OWNED_LISTS) or []):
        if k not in list_keys:
            list_keys.append(k)
    arr_keys = []
    for k in list(touched_arrays) + list(save.get(OWNED_ARRAYS) or []):
        if k not in arr_keys:
            arr_keys.append(k)

    cleared = False
    for k in list_keys + arr_keys:
        # ES3.Load returns the default (empty) for a missing key, so a missing
        # backup is an empty baseline, not an error.
        base = mem.get(k, save.get(BAK + k, []))
        if base is None or contains_japanese(base):
            save[k] = []
            cleared = True
        else:
            save[k] = list(base)

    acted = bool(list_keys or arr_keys)
    ended = acted and (cleared or pool_too_short(save))
    if ended:
        save["S8Progress_Para"] = 0
        save["testingIf_Para"] = False
        save["testingIf_CompleteIf"] = True
    save[OWNED_LISTS] = []
    save[OWNED_ARRAYS] = []
    return save, ended


def cross_book_guard(save, book_state, touched_lists=(), touched_arrays=(), mem=None):
    """Mirror JpWordListPlugin.CrossBookGuard (restart into a non-JP book)."""
    if book_state == 1:
        return save, "in-jp-book-noop"
    owned = save.get(OWNED_LISTS) or []
    owned_arrays = save.get(OWNED_ARRAYS) or []
    if not owned and not owned_arrays:
        return save, "not-owned-noop"
    save, ended = restore_shared_fields(save, touched_lists, touched_arrays, mem)
    return save, ("restored+ended" if ended else "restored")


OK = [True]


def check(name, cond):
    print("   [%s] %s" % ("PASS" if cond else "FAIL", name))
    OK[0] = OK[0] and bool(cond)
