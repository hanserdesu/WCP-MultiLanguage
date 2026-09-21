# -*- coding: utf-8 -*-
"""R13c: 完整关键行 + 窗口 Top 全文"""
import re, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

LOG = r"C:\Users\hanserdesu\AppData\LocalLow\WCP\wcp\Player.log"
lines = open(LOG, "rb").read().decode("utf-8", errors="replace").splitlines()

print("[完整长帧行] L538, L594, L624, L648")
for i in [538, 594, 624, 648, 661, 746, 754]:
    print(f"\n--- L{i} (len={len(lines[i])}):")
    print(lines[i])

print("\n" + "=" * 60)
print("[L624 前后 12 行上下文 — fr 接管帧]")
for j in range(615, 640):
    print(f"  L{j}: {lines[j].strip()[:260]}")

print("\n" + "=" * 60)
print("[L589-L600 上下文 — ru 接管帧]")
for j in range(586, 602):
    print(f"  L{j}: {lines[j].strip()[:260]}")

print("\n" + "=" * 60)
print("[每窗口 队列校正/队列:规则 抽取]")
for i, ln in enumerate(lines):
    if "性能哨兵" in ln:
        m1 = re.search(r"运行态:队列校正 x(\d+)=([\d.]+)ms\(单次([\d.]+)ms\)", ln)
        m2 = re.search(r"队列:规则 x(\d+)=([\d.]+)ms\(单次([\d.]+)ms\)", ln)
        if m1 or m2:
            print(f"  L{i}: 队列校正 x{m1.group(1) if m1 else '?'}={m1.group(2) if m1 else '?'}ms ; 队列:规则 x{m2.group(1) if m2 else '?'}={m2.group(2) if m2 else '?'}ms(单次{m2.group(3) if m2 else '?'})")

print("\n" + "=" * 60)
print("[槽位归属 全行]")
for i, ln in enumerate(lines):
    if "槽位归属" in ln and ("性能哨兵" in ln or "长帧" in ln):
        print(f"  L{i}: {ln.strip()[:600]}")
