# -*- coding: utf-8 -*-
"""R14 内容级校验：源标记在源码与 DLL 中同时存在 + repo==deployed 字节一致"""
import hashlib, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPO = r"D:\ATooManyLanguage\MultiLanguage\mod_host\WcpHost.dll"
DEP  = r"E:\Steam\steamapps\common\WCP-WordGirlgriend\BepInEx\plugins\WcpHost.dll"
SRC  = {
    "BookPool.cs":     r"D:\ATooManyLanguage\MultiLanguage\mod_host\Core\BookPool.cs",
    "TakeoverScope.cs": r"D:\ATooManyLanguage\MultiLanguage\mod_host\TakeoverScope.cs",
    "SlotOwnership.cs": r"D:\ATooManyLanguage\MultiLanguage\mod_host\Core\SlotOwnership.cs",
}

fails = 0
def check(ok, label):
    global fails
    print(("PASS " if ok else "FAIL ") + label)
    if not ok: fails += 1

# 1. 源码标记（改动确实落在源上）
src_markers = {
    "BookPool.cs": [
        "internal sealed class Plan",
        "internal List<string> Rebuild(bool preferLearned, int target)",
        "internal static List<string> FilterOnly(IList<string> current, HashSet<string> bookSet)",
        "生命周期 = 一次 Enforce",
    ],
    "TakeoverScope.cs": [
        "BookPool.Plan plan = new BookPool.Plan(_bookWords, stats, order)",
        "private void EnforceList(FieldRule rule, HashSet<string> allowed,",
        "next = plan.Rebuild(rule.PreferLearned, target)",
        "BookPool.FilterOnly(current, allowed)",
    ],
    "SlotOwnership.cs": [
        "CheapRowHash",
        "_rowFingerprintMemo",
        "internal int MemoHits",
    ],
}
for fname, markers in src_markers.items():
    src = open(SRC[fname], "rb").read().decode("utf-8")
    for m in markers:
        check(m in src, f"{fname} 含标记: {m[:50]}")

# 2. DLL 内容级（PE 字节 literal 搜索，utf-16-le）—— 新逻辑真的编进 DLL
dll = open(REPO, "rb").read()
dll_needles = [
    "队列:规则",            # 既有探针仍在
    "槽位归属:重解析",       # 既有探针仍在
    "槽位归属:行指纹",       # 既有探针仍在
    "队列:授权集",
]
for n in dll_needles:
    check(dll.find(n.encode("utf-16-le")) != -1, f"DLL 含 literal: {n}")

# 3. repo == deployed 字节一致（防止部署了旧版）
dep = open(DEP, "rb").read()
check(hashlib.sha256(dll).hexdigest() == hashlib.sha256(dep).hexdigest(),
      f"repo==deployed 字节一致（sha256 {hashlib.sha256(dll).hexdigest()[:8]}）")

print()
print("ALL PASS" if fails == 0 else f"FAILURES: {fails}")
sys.exit(0 if fails == 0 else 1)
