# -*- coding: utf-8 -*-
"""R13 实机日志验证:五项检查点"""
import re, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

LOG = r"C:\Users\hanserdesu\AppData\LocalLow\WCP\wcp\Player.log"
data = open(LOG, "rb").read()
text = data.decode("utf-8", errors="replace")
lines = text.splitlines()

print("=" * 60)
print("[A] 加载期 Harmony 安装标志")
for i, ln in enumerate(lines):
    if "加载期安装" in ln or "接线完成" in ln:
        print(f"  L{i}: {ln.strip()[:200]}")
census = [ln for ln in lines if "Census" in ln or "普查" in ln]
print(f"  census lines: {len(census)}")
for ln in census[:3]:
    print(f"    {ln.strip()[:160]}")

print("=" * 60)
print("[B] 补丁:Sync span 出现情况")
sync_spans = [ln for ln in lines if "补丁:Sync" in ln]
print(f"  补丁:Sync lines: {len(sync_spans)}")
for ln in sync_spans[:5]:
    print(f"    {ln.strip()[:200]}")

print("=" * 60)
print("[C] 已移除/已安装 抖动")
rm = [ln for ln in lines if "已移除" in ln]
ins = [ln for ln in lines if "已安装" in ln and "未" not in ln]
print(f"  '已移除': {len(rm)}   '已安装': {len(ins)}")
for ln in (rm + ins)[:6]:
    print(f"    {ln.strip()[:180]}")

print("=" * 60)
print("[D] 异常 / 错误")
errs = [ln for ln in lines if re.search(r"Exception|error CS|MissingMethod|TypeLoadException|NullReference", ln, re.I)]
print(f"  exception-ish lines: {len(errs)}")
for ln in errs[:10]:
    print(f"    {ln.strip()[:200]}")

print("=" * 60)
print("[E] 窗口汇总 (TakeWindowSummary) — 最近 6 个窗口")
# PerfProbe 窗口行特征: 含 '窗口' 或 '长帧' 或 'GC'
win = [ln for ln in lines if ("窗口" in ln or "TopN" in ln or "快路径" in ln)]
for ln in win[-8:]:
    print(f"  {ln.strip()[:250]}")

print("=" * 60)
print("[F] 长帧行 (最近 15 条)")
lf = [ln for ln in lines if ("长帧" in ln or "Tick" in ln or "ms" in ln and "帧" in ln)]
for ln in lf[-15:]:
    print(f"  {ln.strip()[:220]}")

print("=" * 60)
print("[G] 关键 span 汇总 (首次接管/装载/队列:规则)")
keys = ["接管", "装载", "队列:规则", "槽位归属", "标签还原", "指纹", "Match"]
for k in keys:
    hits = [ln for ln in lines if k in ln]
    print(f"  --- '{k}' ({len(hits)} lines) 最近3条:")
    for ln in hits[-3:]:
        print(f"    {ln.strip()[:220]}")
