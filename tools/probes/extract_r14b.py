# -*- coding: utf-8 -*-
"""R14 deep-dive: print FULL key lines."""
import re

LOG = r"D:\ATooManyLanguage\probes\log_archive\round14_real_20260918_2314.log"
text = open(LOG, "rb").read().decode("utf-8", errors="replace")
lines = text.splitlines()

# Full lines for switch-frame and window summaries
want = [450, 591, 592, 620, 621, 649, 676, 677, 718, 722, 723]
print("===== full key lines =====")
for n in want:
    if n <= len(lines):
        print(f"--- L{n} ---")
        print(lines[n - 1])

print("\n===== every line containing 队列:规则 / 槽位归属 / 归授权集 =====")
for i, l in enumerate(lines):
    if ("队列:规则" in l or "槽位归属" in l) and "性能哨兵" not in l and "长帧" not in l:
        print(f"L{i+1}:", l)

print("\n===== build/version markers =====")
for i, l in enumerate(lines[:120]):
    if ("接线" in l or "接管" in l and False or "批量写已启用" in l or "Census" in l or "加载期" in l):
        print(f"L{i+1}:", l)
