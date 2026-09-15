import json, sqlite3, pathlib, sys, hashlib, unicodedata
import wcp_paths
BEFORE_FULL = pathlib.Path(r"D:/French/backups/wcpFullEng.before_french_e32c01_20260913_101456.db")
BEFORE_ONLY = pathlib.Path(r"D:/French/backups/wcpOnlyWord.before_french_657afe_20260913_101457.db")
FULL = wcp_paths.full_db()
ONLY = wcp_paths.only_db()

def load(db, table, cols):
    con = sqlite3.connect(str(db))
    cur = con.cursor()
    d = {}
    for row in cur.execute("SELECT " + ",".join(cols) + " FROM " + table):
        d[row[0]] = row[1:]
    con.close()
    return d

def compare(before, now, table, cols, label):
    b = load(before, table, cols)
    n = load(now, table, cols)
    changed = []
    added = []
    removed = []
    for w in n:
        if w not in b:
            added.append(w)
        elif b[w] != n[w]:
            changed.append((w, b[w], n[w]))
    for w in b:
        if w not in n:
            removed.append(w)
    print("=== " + label + " " + table)
    print("  words changed:", len(changed), "added:", len(added), "removed:", len(removed))
    for w, old, new in changed[:12]:
        print("   CHG", repr(w), "| old:", repr(old), "| new:", repr(new))
    for w in added[:6]:
        print("   ADD", repr(w))
    for w in removed[:6]:
        print("   DEL", repr(w))
    return changed, added, removed

full_changed, full_added, full_removed = compare(BEFORE_FULL, FULL, "pron", ["word","ukPhonic","usPhonic","meaning"], "wcpFullEng")
compare(BEFORE_FULL, FULL, "sentence2", ["word","sentences"], "wcpFullEng")
only_changed, _, _ = compare(BEFORE_ONLY, ONLY, "pron", ["word","ukPhonic","usPhonic","meaning"], "wcpOnlyWord")

# how many of the changed words are real English words (had an English meaning before)?
import re
def is_english_meaning(m):
    if not m: return False
    # English meanings are latin text; french patch meanings are Chinese
    return re.search(r"[a-zA-Z]{2,}", m) is not None and not re.search(r"[一-鿿]", m)

eng_overwritten = [(w, old, new) for w, old, new in full_changed if is_english_meaning(old[2])]
print("FULL: overwritten words that previously had an ENGLISH meaning:", len(eng_overwritten))
for w, old, new in eng_overwritten[:25]:
    print("   ", repr(w), "| EN meaning:", repr(old[2][:60]), "-> FR:", repr(new[2][:60]))
