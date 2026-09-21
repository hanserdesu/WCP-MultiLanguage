#!/usr/bin/env python3
"""Round 10 -- verify the round-10 WcpHost build actually carries its changes.

Round 10 changed no behaviour: it only adds attribution tags, plus GC accounting in
PerfProbe. That makes verification *more* important, not less -- a diagnostic build
that silently failed to deploy would produce a log that looks exactly like "the host
did nothing", and the next round would draw conclusions from an empty dataset.

Same rule as round 9: PE section alignment means a changed DLL can keep the same file
size, so size/mtime prove nothing. Check (a) sha256 repo vs deployed, (b) the new
literals are present as UTF-16LE `.NET #US` heap entries.

Round-9 literals are re-checked too: they must still be there (regression guard).
"""
import hashlib
import os
import sys

GAME = r"E:\Steam\steamapps\common\WCP-WordGirlgriend"
REPO = r"D:\ATooManyLanguage\MultiLanguage\mod_host\WcpHost.dll"
DEPLOYED = os.path.join(GAME, "BepInEx", "plugins", "WcpHost.dll")

# (needle, why it must be present)
EXPECTED = [
    # ── round 10: Evaluate split into stages ──
    ("身份:读内存词表",
     "round-10: Evaluate stage 1 -- StaticField x2 + ToWordList"),
    ("身份:读落盘书名",
     "round-10: Evaluate stage 2 -- the one ES3 read that fires on every poll"),
    ("身份:槽号",
     "round-10: Evaluate stage 3 -- pure string parse, expected ~0ms"),
    ("身份:匹配内存词表",
     "round-10: Evaluate stage 4 -- BookRegistry.Match (measured 3.4ms off-line)"),
    ("身份:读槽位词表",
     "round-10: Evaluate stage 5 -- SlotWords, cache hit in steady state"),
    ("身份:匹配槽位词表",
     "round-10: Evaluate stage 6 -- second Match on the slot snapshot"),
    ("身份:槽位归属",
     "round-10: Evaluate stage 7 -- SlotOwnership.IsServed"),
    ("身份:装载",
     "round-10: Evaluate stage 8 -- SetIdentity / SetActive"),
    # ── round 10: previously untagged expensive paths ──
    ("场景:强制校正",
     "round-10: THE CLOSED HOLE -- EnforceNowForScene had no outermost span, so every "
     "correction fired from inside a game method was invisible to the sentinel's "
     "'mod busy ms' accounting"),
    ("运行态:场景校正",
     "round-10: EnforceNow tag, so patch-triggered corrections are distinguishable "
     "from the每秒 Tick one"),
    ("ES3:槽位计数探测",
     "round-10: NativeSlotCount() probes SelfBookList1..N with a full ES3 document "
     "parse per iteration and had no span"),
    ("槽位归属:重解析",
     "round-10: SlotOwnership cache-miss path (20 rows x StrList + FingerprintOf)"),
    ("槽位归属:行指纹",
     "round-10: the per-row FingerprintOf inside that miss path"),
    # ── round 10: which group of the 52 patch points is expensive ──
    ("补丁:场景钩子", "round-10: InstallFeatures group 1"),
    ("补丁:显示", "round-10: InstallFeatures group 2"),
    ("补丁:词典", "round-10: InstallFeatures group 3"),
    ("补丁:音频", "round-10: InstallFeatures group 4"),
    ("补丁:选词与刷新", "round-10: InstallFeatures group 5"),
    # ── round 10: GC accounting ──
    ("GC本帧=",
     "round-10: per-long-frame GC delta -- the only way to tell a slow span from a "
     "span that got hit by a stop-the-world collection"),
    ("GC窗口=", "round-10: per-window GC delta"),
    ("GC 基线建立",
     "round-10: first window forgoes the delta because there is no baseline yet"),
    # ── round 9 regression: the ES3 batch fix must still be in this binary ──
    ("ES3 批量写已启用", "round-9 regression: batch engaged log"),
    ("ES3 批量写不可用", "round-9 regression: Create() names the missing prerequisite"),
    ("ES3.Location 取不到 Cache 成员",
     "round-9 regression: the actual round-8 root cause diagnostic"),
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
        print("  %-30s %s" % (needle, "OK" if ok else "MISSING"))
        if not ok:
            fails.append("literal missing from deployed DLL: " + needle)
        else:
            print("      why: %s" % why)

    # The old round-8 TopN=8 must be gone: it is a const int, not a string, so it
    # cannot be checked textually -- assert it by absence of the *comment-era*
    # marker instead would be wrong. Skip; behaviour is covered by the gates.

    print()
    if fails:
        print("VERIFY ROUND 10: FAIL")
        for f in fails:
            print("  - " + f)
        return 1
    print("VERIFY ROUND 10: PASS (%d literals present, repo==deployed)" % len(EXPECTED))
    return 0


if __name__ == "__main__":
    sys.exit(main())
