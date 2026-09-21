# -*- coding: utf-8 -*-
"""R13 深挖: NRE 上下文 / 已移除位置 / 补丁:Sync 数值 / 接管帧"""
import re, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

LOG = r"C:\Users\hanserdesu\AppData\LocalLow\WCP\wcp\Player.log"
lines = open(LOG, "rb").read().decode("utf-8", errors="replace").splitlines()

def ctx(idx, before=3, after=8):
    for j in range(max(0, idx - before), min(len(lines), idx + after)):
        mark = ">>" if j == idx else "  "
        print(f"  {mark} L{j}: {lines[j].strip()[:230]}")

print("=" * 60)
print("[1] NRE 上下文")
for i, ln in enumerate(lines):
    if "NullReferenceException" in ln:
        ctx(i)

print("=" * 60)
print("[2] '已移除' 出现位置")
for i, ln in enumerate(lines):
    if "已移除" in ln:
        ctx(i, before=6, after=4)

print("=" * 60)
print("[3] 补丁:Sync 全部出现(完整行)")
for i, ln in enumerate(lines):
    if "补丁" in ln:
        print(f"  L{i}: {ln.strip()[:400]}")

print("=" * 60)
print("[4] 接管/语言包切换事件 + 相邻长帧")
for i, ln in enumerate(lines):
    if "接管语言包" in ln:
        print(f"  L{i}: {ln.strip()[:200]}")

print("=" * 60)
print("[5] 所有长帧 >= 400ms (mod占比高者优先)")
for i, ln in enumerate(lines):
    m = re.search(r"长帧 (\d+)ms — mod 本帧占用 ([\d.]+)ms（([\d.]+)%", ln)
    if m and int(m.group(1)) >= 400:
        print(f"  L{i}: {ln.strip()[:260]}")

print("=" * 60)
print("[6] 退出前尾部 10 行")
for ln in lines[-10:]:
    print(f"  {ln.strip()[:200]}")
