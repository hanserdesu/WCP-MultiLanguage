#!/usr/bin/env python3
"""Round 11 -- verify the round-11 WcpHost build actually carries its changes.

Round 11 makes one behavioural change (coalesce the per-frame ES3 batch scopes into
a single load+store) plus two instrumentation changes (split the two remaining
black boxes: 身份:装载's inner 207 ms and 运行态:队列校正's inner work; and make the
Harmony install report how many target methods it actually hit).

Same rule as rounds 9 and 10: PE section alignment means a changed DLL can keep the
same file size, so size/mtime prove nothing. Check (a) sha256 repo vs deployed,
(b) the new literals are present as UTF-16LE `.NET #US` heap entries.

Round-9 and round-10 literals are re-checked too (regression guard): the ES3 batch
mechanism and the GC accounting must still be in the binary.
"""
import hashlib
import os
import sys

GAME = r"E:\Steam\steamapps\common\WCP-WordGirlgriend"
REPO = r"D:\ATooManyLanguage\MultiLanguage\mod_host\WcpHost.dll"
DEPLOYED = os.path.join(GAME, "BepInEx", "plugins", "WcpHost.dll")

# (needle, why it must be present)
EXPECTED = [
    # ── round 11: split 身份:装载 (measured 404.6 ms on the 切书 frame) ──
    ("装载:范围进入",
     "round-11: the 197.7 ms 身份:接管语言包 block, part 1 -- TakeoverScope.Enter"),
    ("装载:服务就绪",
     "round-11: the same block, part 2 -- EnsureServices"),
    ("装载:离开",
     "round-11: LeaveCurrent -- the prime suspect for 身份:装载's unexplained 207 ms"),
    ("装载:离开·标签还原",
     "round-11: RestoreLabels inside LeaveCurrent (a full-scene text scan)"),
    # ── round 11: split 运行态:队列校正 (measured 257.8 ms on the 切书 frame) ──
    ("队列:授权集",
     "round-11: BookPool.ToSet over the active book -- HashSet build, no attribution before"),
    ("队列:规则",
     "round-11: the 17-field rule loop"),
    ("队列:对齐",
     "round-11: AlignTestQueue"),
    # ── round 11: make the 1890 ms Harmony install countable ──
    ("Harmony 接线完成",
     "round-11: logs how many target methods were actually patched, so 1890 ms can be "
     "split into 'too many points' vs 'too expensive per point'"),
    # ── round 10 regression: stage tags + the closed accounting hole ──
    ("身份:读内存词表", "round-10 regression: Evaluate stage 1"),
    ("身份:装载", "round-10 regression: Evaluate stage 8"),
    ("场景:强制校正",
     "round-10 regression: the outermost span on EnforceNowForScene -- without it every "
     "patch-triggered correction is invisible to the sentinel"),
    ("槽位归属:重解析", "round-10 regression: SlotOwnership cache-miss path"),
    ("补丁:场景钩子", "round-10 regression: InstallFeatures group 1"),
    ("补丁:选词与刷新", "round-10 regression: InstallFeatures group 5"),
    ("GC本帧=", "round-10 regression: per-long-frame GC delta"),
    ("GC窗口=", "round-10 regression: per-window GC delta"),
    # ── round 9 regression: the ES3 batch fix must still be in this binary ──
    ("ES3 批量写已启用", "round-9 regression: batch engaged log"),
    ("ES3 批量写不可用", "round-9 regression: Create() names the missing prerequisite"),
    ("ES3:批量写(装载)",
     "round-9 regression: per-batch load span. Round 11 must make its xN count drop "
     "from 3 to 1 per 切书 frame -- if this literal vanished, that claim would be "
     "unfalsifiable in the next real-machine log."),
    ("ES3:批量写(提交)", "round-9 regression: per-batch store span"),
]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    fails = []
    for p in (REPO, DEPLOYED):
        if not os.path.exists(p):
            print("FAIL missing:", p)
            return 1

    rs, ds = sha256(REPO), sha256(DEPLOYED)
    print("repo     WcpHost.dll %10d B  sha256=%s" % (os.path.getsize(REPO), rs))
    print("deployed WcpHost.dll %10d B  sha256=%s" % (os.path.getsize(DEPLOYED), ds))
    if rs != ds:
        fails.append("repo and deployed differ -- the built artifact is NOT what the game loads")
    print("repo == deployed (byte-identical):", rs == ds)
    print()

    data = open(DEPLOYED, "rb").read()
    print("--- literal presence (UTF-16LE) ---")
    for needle, why in EXPECTED:
        ok = data.find(needle.encode("utf-16-le")) >= 0
        print("  %-24s %s" % (needle, "OK" if ok else "MISSING"))
        if not ok:
            fails.append("literal missing from deployed DLL: " + needle)
        else:
            print("      why: %s" % why)

    print()
    if fails:
        print("VERIFY ROUND 11: FAIL")
        for f in fails:
            print("  - " + f)
        return 1
    print("VERIFY ROUND 11: PASS (%d literals present, repo==deployed)" % len(EXPECTED))
    return 0


if __name__ == "__main__":
    sys.exit(main())
