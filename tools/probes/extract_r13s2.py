# -*- coding: utf-8 -*-
"""R13 第二采样: 验证切换帧三头叠加是否可复现"""
import re, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

LOG = r"D:\ATooManyLanguage\probes\log_archive\round13_real_20260918_2251.log"
lines = open(LOG, "rb").read().decode("utf-8", errors="replace").splitlines()

print("[版本确认]")
for i, ln in enumerate(lines[:90]):
    if "接线完成" in ln or "加载期安装" in ln:
        print(f"  L{i}: {ln.strip()[:180]}")

print("\n[接管事件与激活]")
for i, ln in enumerate(lines):
    if "接管语言包" in ln or "已激活" in ln:
        print(f"  L{i}: {ln.strip()[:180]}")

print("\n[长帧 >= 400ms]")
for i, ln in enumerate(lines):
    m = re.search(r"长帧 (\d+)ms — mod 本帧占用 ([\d.]+)ms（([\d.]+)%", ln)
    if m and int(m.group(1)) >= 400:
        print(f"  L{i}: 帧{m.group(1)}ms mod {m.group(2)}ms({m.group(3)}%)")
        for seg in re.findall(r"([\u4e00-\u9fa5A-Za-z0-9:]+) x\d+=[\d.]+ms", ln)[:8]:
            pass
        tops = re.findall(r"([^\s;（）]+ x\d+=[\d.]+ms(?:\(单次[\d.]+ms\))?)", ln)
        for t in tops[:12]:
            print(f"      {t}")

print("\n[队列:规则 按窗口]")
for i, ln in enumerate(lines):
    if "性能哨兵" in ln:
        m = re.search(r"队列:规则 x(\d+)=([\d.]+)ms\(单次([\d.]+)ms\)", ln)
        fps = re.search(r"fps=([\d.]+)", ln)
        if m:
            print(f"  L{i}: fps={fps.group(1) if fps else '?'} 队列:规则 x{m.group(1)}={m.group(2)}ms 单次{m.group(3)}ms")

print("\n[槽位归属:重解析 / 行指纹]")
for i, ln in enumerate(lines):
    if "槽位归属:重解析" in ln:
        m = re.search(r"槽位归属:重解析 x(\d+)=([\d.]+)ms", ln)
        print(f"  L{i}: 重解析 x{m.group(1)}={m.group(2)}ms")

print("\n[异常]")
for i, ln in enumerate(lines):
    if re.search(r"Exception|MissingMethod|TypeLoad", ln):
        print(f"  L{i}: {ln.strip()[:180]}")

print("\n[已移除/已安装]")
for i, ln in enumerate(lines):
    if "已移除" in ln or ("已安装" in ln and "接管" not in ln):
        print(f"  L{i}: {ln.strip()[:160]}")
