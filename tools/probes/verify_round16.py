# -*- coding: utf-8 -*-
"""Round 16 content verification (never trust timestamps/sizes — verify bytes)."""
import hashlib

REPO = r"D:\ATooManyLanguage\MultiLanguage\mod_host\WcpHost.dll"
DEP = r"E:\Steam\steamapps\common\WCP-WordGirlgriend\BepInEx\plugins\WcpHost.dll"

oks = []
def check(cond, label):
    oks.append(cond)
    print(("PASS  " if cond else "FAIL  ") + label)

# -- 1. source markers --------------------------------------------------------
ga = open(r"D:\ATooManyLanguage\MultiLanguage\mod_host\GameAdapter.cs", "rb").read().decode("utf-8")
check("DrainEs3Writes" in ga and "DrainEs3WritesAll" in ga, "源: GameAdapter 写后置消化口入口")
check("_pending.Add(this)" in ga, "源: Dispose 改为排队（写后置）")
check("_written[key] = value;\n                _dirty = true;\n                return true;" in ga,
      "源: Put 只记账不触 ES3")
check("batch.Commit()" in ga, "源: Drain 调 Commit（装载+应用+落盘）")

host = open(r"D:\ATooManyLanguage\MultiLanguage\mod_host\Host.cs", "rb").read().decode("utf-8")
check("GameAdapter.DrainEs3Writes();" in host, "源: Host.Update 每帧消化写后置")
check("GameAdapter.DrainEs3WritesAll();" in host, "源: OnDestroy 退出前冲干净")

gl = open(r"D:\ATooManyLanguage\MultiLanguage\mod_host\Core\GameLearnedStats.cs", "rb").read().decode("utf-8")
check("EnsureSnapshot" in gl and "LearnedSnapshot" in gl, "源: GameLearnedStats 快照类")
check("_entries.Contains(word)" not in gl, "负向: 逐词 Contains+索引 的旧 ReadInt 路径已移除")
check("LastBuildError" in gl, "源: 快照构建失败可见（不静默吞）")

ts = open(r"D:\ATooManyLanguage\MultiLanguage\mod_host\TakeoverScope.cs", "rb").read().decode("utf-8")
check("BookPool.Plan plan = new BookPool.Plan" in ts, "源: R14 Plan 仍在（回归保护）")

p4 = open(r"D:\ATooManyLanguage\probes\es3bench\probe4.cs", "rb").read().decode("utf-8")
check("write-behind semantics (round 16)" in p4 and "[7]" in p4, "源: probe4 PART4 写后置门禁")

# -- 2. DLL literal (PE bytes, utf-16-le) -------------------------------------
d = open(REPO, "rb").read()
def has(s):
    return d.find(s.encode("utf-16-le")) != -1
check(has("ES3 批量写已改为写后置"), "DLL: 写后置提示语在 PE 字面量中")
check(has("ES3 批量写缓存复用生效"), "DLL: 缓存复用提示语在 PE 字面量中")
check(has("WcpHost: ES3 批量写已启用"), "DLL: 批量启用提示语在 PE 字面量中")

# -- 3. repo == deployed ------------------------------------------------------
import os
dep = open(DEP, "rb").read()
ha, hb = hashlib.sha256(d).hexdigest()[:8], hashlib.sha256(dep).hexdigest()[:8]
print("repo : %d  %s" % (len(d), ha))
print("dep  : %d  %s" % (len(dep), hb))
check(d == dep, "repo == deployed 字节一致")

print()
print("VERIFY ROUND 16:", "ALL PASS (%d)" % len(oks) if all(oks) else "FAILED")
raise SystemExit(0 if all(oks) else 1)
