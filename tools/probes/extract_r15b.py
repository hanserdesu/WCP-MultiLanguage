# -*- coding: utf-8 -*-
"""R15 deep dive: full key lines + daily-study scene attribution + cache-reuse check."""
import re

LOG = r"D:\ATooManyLanguage\probes\log_archive\round15_real_20260918_2345.log"
lines = open(LOG, "rb").read().decode("utf-8", errors="replace").splitlines()

print("=== A) full switch-frame lines 625/633/642 ===")
for n in (625, 633, 642):
    print(n, ":", lines[n - 1])
    print()

print("=== B) daily-study scene frames (589/590/670/671/679/680/859/860) ===")
for n in (589, 590, 670, 671, 679, 680, 859, 860):
    print(n, ":", lines[n - 1][:600])
    print()

print("=== C) cache-reuse log line search ===")
hits = [(i + 1, l) for i, l in enumerate(lines) if "缓存复用" in l or "批量写" in l]
print("hits:", len(hits))
for i, l in hits:
    print(i, ":", l[:240])

print("\n=== D) all 场景:强制校正 / 场景校正 lines ===")
for i, l in enumerate(lines):
    if "场景:强制校正" in l or "场景校正" in l:
        print(i + 1, ":", l[:400])

print("\n=== E) 槽位归属:重解析 / 指纹 lines ===")
for i, l in enumerate(lines):
    if "重解析" in l or "行指纹" in l:
        print(i + 1, ":", l[:300])
