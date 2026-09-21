# -*- coding: utf-8 -*-
"""Per-tier English-cognate density of the French wordbook.

Uses the project's own pristine English baseline, not the patched live DB.
"""
import os
import re
import sqlite3
import sys
import zipfile
from xml.etree import ElementTree as ET

sys.stdout.reconfigure(encoding="utf-8")

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
IMP = r"D:/ATooManyLanguage/French/output/import"
BASE = r"D:/ATooManyLanguage/French/work/english_baseline/wcpFullEng.db"


def first_col(path):
    words = []
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.findall(NS + "si"):
                shared.append("".join(t.text or "" for t in si.iter(NS + "t")))
        sheet = [n for n in z.namelist() if n.startswith("xl/worksheets/sheet")][0]
        root = ET.fromstring(z.read(sheet))
        for row in root.iter(NS + "row"):
            for c in row.findall(NS + "c"):
                if re.match(r"([A-Z]+)", c.get("r") or "").group(1) == "A":
                    if c.get("t") == "inlineStr":
                        words.append("".join(
                            t.text or "" for t in c.find(NS + "is").iter(NS + "t")))
                    else:
                        v = c.find(NS + "v")
                        if v is not None:
                            words.append(shared[int(v.text)] if c.get("t") == "s" else v.text)
                    break
    return words


con = sqlite3.connect("file:%s?mode=ro" % BASE, uri=True)
eng = set(r[0] for r in con.execute("SELECT word FROM pron"))
con.close()
print("pristine english baseline pron words:", len(eng))

total = 0
total_ov = 0
for name in sorted(os.listdir(IMP)):
    if not name.endswith(".xlsx"):
        continue
    ws = first_col(os.path.join(IMP, name))
    ov = [w for w in ws if w and w in eng]
    total += len(ws)
    total_ov += len(ov)
    print("  %-16s %5d words, %5d identical to English (%5.1f%%)   e.g. %s"
          % (name, len(ws), len(ov), 100.0 * len(ov) / max(1, len(ws)), ", ".join(ov[:6])))
print("  TOTAL            %5d words, %5d identical (%5.1f%%)"
      % (total, total_ov, 100.0 * total_ov / max(1, total)))
