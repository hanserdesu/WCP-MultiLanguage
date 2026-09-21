# -*- coding: utf-8 -*-
"""Check whether the suspect battle-list words really exist in the French book."""
import json
import os
import re
import sqlite3
import sys
import zipfile
from xml.etree import ElementTree as ET

sys.stdout.reconfigure(encoding="utf-8")

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
IMP = r"D:/ATooManyLanguage/French/output/import"


def xlsx_first_col(path):
    """Headerless xlsx: first column of every row = the word."""
    words = []
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.findall(NS + "si"):
                shared.append("".join(t.text or "" for t in si.iter(NS + "t")))
        sheet = [n for n in z.namelist() if n.startswith("xl/worksheets/sheet")][0]
        root = ET.fromstring(z.read(sheet))
        def col_of(ref):
            m = re.match(r"([A-Z]+)", ref or "")
            return m.group(1) if m else ""

        for row in root.iter(NS + "row"):
            for c in row.findall(NS + "c"):
                if col_of(c.get("r")) == "A":
                    if c.get("t") == "inlineStr":
                        is_el = c.find(NS + "is")
                        words.append("".join(t.text or "" for t in is_el.iter(NS + "t")))
                    else:
                        v = c.find(NS + "v")
                        if v is None:
                            continue
                        words.append(shared[int(v.text)] if c.get("t") == "s" else v.text)
                    break
    return words


allwords = set()
for name in sorted(os.listdir(IMP)):
    if name.endswith(".xlsx"):
        ws = xlsx_first_col(os.path.join(IMP, name))
        print("  %-16s %d words" % (name, len(ws)))
        allwords |= set(ws)
print("union:", len(allwords))

suspect = ["collision", "confusion", "hamburger", "exact", "champion",
           "divorce", "capital", "crash", "miss", "profit", "module",
           "situation", "phrase", "people", "bus", "set", "dealer",
           "gay", "fan", "dingue", "sérum", "aura", "massacre",
           "conversation", "association", "permission", "imitation", "science"]
print("--- membership in French book ---")
for w in suspect:
    mark = "IN " if w in allwords else "OUT"
    print("  %s %s" % (mark, w))

# also compare against English base dictionary
SA = r"E:/Steam/steamapps/common/WCP-WordGirlgriend/wcp_Data/StreamingAssets"
con = sqlite3.connect("file:%s/wcpFullEng.db?mode=ro" % SA, uri=True)
eng = set(r[0] for r in con.execute("SELECT word FROM pron"))
con.close()
print("english pron words:", len(eng))
both = [w for w in suspect if w in allwords and w in eng]
print("suspect words in BOTH french book and english dict:", both)
