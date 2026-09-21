#!/usr/bin/env python3
"""Round 9 -- verify the round-9 WcpHost build actually carries its changes.

The lesson this file exists to enforce (round 7): PE section alignment means a
changed DLL can keep the exact same file size, so size and mtime prove nothing.
The only reliable checks are (a) sha256 of repo vs deployed, and (b) searching for
the *new* string literals inside the binary.

Manageable literals are `.NET #US` heap entries -> UTF-16LE. Labels that were only
reworded in comments will NOT appear (comments are not compiled), so comment-only
edits are expected to show `False`; that is why every assertion here points at a
literal that is genuinely part of the emitted IL.
"""
import hashlib
import os
import sys

GAME = r"E:\Steam\steamapps\common\WCP-WordGirlgriend"
REPO = r"D:\ATooManyLanguage\MultiLanguage\mod_host\WcpHost.dll"
DEPLOYED = os.path.join(GAME, "BepInEx", "plugins", "WcpHost.dll")

# (needle, why it must be present)
EXPECTED = [
    ("ES3 批量写已启用",
     "round-9: one-time success log -- without it 'did the batch engage?' can only "
     "be reverse-engineered from stutter milliseconds, which is exactly how round 8 "
     "hid a 4-second bug for a full round"),
    ("ES3 批量写不可用",
     "round-9: Create() now names the missing prerequisite instead of returning null "
     "silently"),
    ("ES3.Location 取不到 Cache 成员",
     "round-9: the specific null that actually fired in rounds 8 (Location was queried "
     "on ES3Settings instead of ES3)"),
    ("ES3Settings.defaultSettings 找不到",
     "round-9: Missing() diagnostics for the other prerequisites"),
    ("ES3Settings.location 找不到",
     "round-9: Missing() diagnostics"),
    ("ES3Settings.Clone() 找不到",
     "round-9: Missing() diagnostics"),
    ("ES3.CacheFile(ES3Settings) 找不到",
     "round-9: Missing() diagnostics"),
    ("ES3.StoreCachedFile(ES3Settings) 找不到",
     "round-9: Missing() diagnostics"),
    ("ES3.Save<T>(string,T,ES3Settings) 找不到",
     "round-9: Missing() diagnostics"),
    ("默认设置读不到", "round-9: batch:defaults diagnostic"),
    ("Clone() 返回 null", "round-9: batch:clone diagnostic"),
    ("默认设置没有 path", "round-9: batch:path diagnostic -- this guard only runs now "
                          "that ES3Settings.path is resolved as a FIELD"),
    ("location setter 没生效", "round-9: batch:setter diagnostic"),
]

# Strings that must be GONE from the binary (round-8 phrasing).
ABSENT = []


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    fails = []
    if not os.path.exists(REPO):
        print("FAIL repo WcpHost.dll missing:", REPO)
        return 1
    if not os.path.exists(DEPLOYED):
        print("FAIL deployed WcpHost.dll missing:", DEPLOYED)
        return 1

    rs, ds = sha256(REPO), sha256(DEPLOYED)
    print("repo     WcpHost.dll %10d B  sha256=%s" % (os.path.getsize(REPO), rs))
    print("deployed WcpHost.dll %10d B  sha256=%s" % (os.path.getsize(DEPLOYED), ds))
    if rs != ds:
        fails.append("repo and deployed differ -- the built artifact is NOT what the game loads")
    print("repo == deployed (byte-identical):", rs == ds)

    data = open(DEPLOYED, "rb").read()
    print()
    print("--- literal presence (UTF-16LE) ---")
    for needle, why in EXPECTED:
        ok = data.find(needle.encode("utf-16-le")) >= 0
        print("  %-40s %s" % (needle, "OK" if ok else "MISSING"))
        if not ok:
            fails.append("literal missing from deployed DLL: " + needle)
        else:
            print("      why: %s" % why)
    for needle in ABSENT:
        ok = data.find(needle.encode("utf-16-le")) < 0
        print("  %-40s %s" % ("ABSENT " + needle, "OK" if ok else "STILL PRESENT"))
        if not ok:
            fails.append("literal should be gone but is present: " + needle)

    print()
    if fails:
        print("VERIFY ROUND 9: FAIL")
        for f in fails:
            print("  - " + f)
        return 1
    print("VERIFY ROUND 9: PASS (%d literals present, repo==deployed)" % len(EXPECTED))
    return 0


if __name__ == "__main__":
    sys.exit(main())
