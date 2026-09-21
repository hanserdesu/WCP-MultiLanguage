# -*- coding: utf-8 -*-
"""Read-only probe of the three WCP game databases.

Answers: which DB actually carries French/Russian content, and how the
battle (S7) path sources its words.
"""
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")

SA = r"E:/Steam/steamapps/common/WCP-WordGirlgriend/wcp_Data/StreamingAssets"
DBS = ["wcpFight.db", "wcpOnlyWord.db", "wcpFullEng.db"]
PROBES = ["accord", "ring", "acheter", "table", "zoom", "vote",
          "стол", "человек", "хорошо", "one", "two", "three"]


def tables(cur):
    return [r[0] for r in cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")]


def cols(cur, t):
    try:
        return [r[1] for r in cur.execute('PRAGMA table_info("%s")' % t)]
    except Exception as e:
        return ["<err %s>" % e]


for name in DBS:
    path = "%s/%s" % (SA, name)
    print("=" * 60)
    print("DB:", name)
    try:
        con = sqlite3.connect("file:%s?mode=ro" % path, uri=True)
    except Exception as e:
        print("  open failed:", e)
        continue
    cur = con.cursor()
    ts = tables(cur)
    print("  tables:", ts)
    for t in ts:
        try:
            n = cur.execute('SELECT COUNT(*) FROM "%s"' % t).fetchone()[0]
        except Exception as e:
            n = "<err %s>" % e
        print("    %-16s rows=%s cols=%s" % (t, n, cols(cur, t)))
    for t in ts:
        c = cols(cur, t)
        if "word" not in c:
            continue
        hits = []
        for w in PROBES:
            try:
                r = cur.execute(
                    'SELECT COUNT(*) FROM "%s" WHERE word=?' % t, (w,)).fetchone()[0]
            except Exception:
                r = -1
            if r:
                hits.append("%s=%s" % (w, r))
        print("    probes[%s]: %s" % (t, ", ".join(hits) or "(none)"))
    con.close()
