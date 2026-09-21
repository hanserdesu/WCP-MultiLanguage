# -*- coding: utf-8 -*-
"""R15 real-machine extraction (build 6811430e)."""
import re, sys

LOG = r"D:\ATooManyLanguage\probes\log_archive\round15_real_20260918_2345.log"
lines = open(LOG, "rb").read().decode("utf-8", errors="replace").splitlines()

def find(pat, flags=0):
    return [(i + 1, l) for i, l in enumerate(lines) if re.search(pat, l, flags)]

print("=== 1) R15 markers ===")
for i, l in find(r"缓存复用生效|还原:分帧|批量写缓存|加载期安装|接线完成"):
    print(i, ":", l[:200])

print("\n=== 2) long frames (>=200ms) with mod spans ===")
for i, l in find(r"[2-9]\d\d\.\dms|\d{4}\.\dms"):
    if re.search(r"帧|长帧|hitch|场景|接管", l):
        print(i, ":", l[:220])

print("\n=== 3) window summaries ===")
for i, l in find(r"窗口汇总|TakeWindow|10s"):
    print(i, ":", l[:260])

print("\n=== 4) 槽位/队列/装载/ES3 spans ===")
for i, l in find(r"槽位归属|队列:规则|装载:|ES3[:：]批量|槽位词表指纹"):
    print(i, ":", l[:240])

print("\n=== 5) errors ===")
for i, l in find(r"Exception|错误|失败"):
    print(i, ":", l[:220])
