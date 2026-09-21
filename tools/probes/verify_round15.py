# -*- coding: utf-8 -*-
"""Round 15 content-level verification (2026-09-18).

Checks, in order of strength:
  1. source markers present (the round-15 edits are actually in the tree)
  2. negative: old hot-path code gone (per-comparison reflection sort is out)
  3. DLL literals present in WcpHost.dll PE bytes (UTF-16LE #US heap search)
  4. repo == deployed (byte-identical)
"""
import hashlib
import os

REPO = r"D:\ATooManyLanguage\MultiLanguage\mod_host"
DEPLOY = r"E:\Steam\steamapps\common\WCP-WordGirlgriend\BepInEx\plugins\WcpHost.dll"

fails = []

def check(cond, label):
    print(("PASS " if cond else "FAIL ") + label)
    if not cond:
        fails.append(label)

def read(p):
    return open(p, "rb").read().decode("utf-8", errors="replace")

# -- 1. source markers -------------------------------------------------------
book = read(os.path.join(REPO, "Core", "BookPool.cs"))
ga = read(os.path.join(REPO, "GameAdapter.cs"))
hr = read(os.path.join(REPO, "HostRuntime.cs"))
host = read(os.path.join(REPO, "Host.cs"))
probe4 = read(r"D:\ATooManyLanguage\probes\es3bench\probe4.cs")

check("装饰-排序-脱饰" in book, "BookPool.cs: 装饰-排序-脱饰 注释标记")
check("Array.Sort(idx" in book, "BookPool.cs: 索引排序（零反射比较）")
check("string.CompareOrdinal(ws[a], ws[b])" in book, "BookPool.cs: 平级稳定化 tie-break")
check("_sharedSettings" in ga and "_cacheAlive" in ga, "GameAdapter.cs: 共享 settings + 缓存存活标记")
check("MatchesFile" in ga and "StampNow" in ga and "DropCache" in ga, "GameAdapter.cs: 戳校验三件套")
check("ES3 批量写缓存复用生效" in ga, "GameAdapter.cs: 复用生效日志（实机可查）")
check("DrainLabelRestores" in hr and "LabelRestoreBudgetMs" in hr, "HostRuntime.cs: 还原分帧")
check("RestoreLabels()" in hr and "_pendingRestore.Add" in hr, "HostRuntime.cs: RestoreLabels 移交队列")
check("DrainLabelRestores" in host, "Host.cs: 每帧消化口挂接")
check("还原:分帧" in hr, "HostRuntime.cs: 还原分帧探针标签")
check("PART 3: cache reuse" in probe4 and "wcp_r15_A" in probe4, "probe4.cs: PART 3 缓存复用实验")

# -- 2. negative: the old per-comparison sort must be gone -------------------
check("words.Sort(delegate(string a, string b)" not in book,
      "负向: BookPool 逐比较委托排序已移除")

# -- 3. DLL literals ----------------------------------------------------------
dll = open(os.path.join(REPO, "WcpHost.dll"), "rb").read()

def has_literal(s):
    return dll.find(s.encode("utf-16-le")) != -1

check(has_literal("WcpHost: ES3 批量写缓存复用生效（跳过整文件装载，路径戳一致）"),
      "DLL literal: 缓存复用生效日志")
check(has_literal("还原:分帧"), "DLL literal: 还原分帧探针标签")

# -- 4. repo == deployed ------------------------------------------------------
if os.path.exists(DEPLOY):
    dep = open(DEPLOY, "rb").read()
    same = dep == dll
    check(same, "repo == deployed 字节一致 (%d B, sha %s)" %
          (len(dll), hashlib.sha256(dll).hexdigest()[:8]))
    if not same and len(dep) > 0:
        print("   deployed differs: %d B sha %s" %
              (len(dep), hashlib.sha256(dep).hexdigest()[:8]))
else:
    print("SKIP repo==deployed: 部署目标不存在（尚未部署）")

print()
print("VERIFY ROUND 15: " + ("ALL PASS" if not fails else "FAIL %d" % len(fails)))
raise SystemExit(0 if not fails else 1)
