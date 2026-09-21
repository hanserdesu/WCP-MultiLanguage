# verify_round13.py — 第十三轮部署产物内容级校验
#
# 本轮改动：Harmony 接线从"首次接管帧"搬到 Awake（普查 59/59 给的 Go），
# 删除 Awake 干跑普查（被取代）。校验：
#   A. repo == deployed 逐字节一致；
#   B. 新日志行「行为 Harmony 接线已在加载期安装」必须**在**；
#   C. 被取代的两行必须**不在**（普查行 / "等待身份门通过"行）——
#      它们若还在，说明搬的是假把式。
import hashlib
import os
import sys

REPO = r"D:\ATooManyLanguage\MultiLanguage\mod_host\WcpHost.dll"
DEPLOYED = r"E:\Steam\steamapps\common\WCP-WordGirlgriend\BepInEx\plugins\WcpHost.dll"

PRESENT = [
    "行为 Harmony 接线已在加载期安装",
    "身份门通过前所有处理器空转",
    "Harmony 接线完成",
    "快路径命中=",
]
ABSENT = [
    "Awake 期解析普查",
    "行为接线等待身份门通过",
]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    fails = []
    for p in (REPO, DEPLOYED):
        if not os.path.isfile(p):
            print("FAIL missing: " + p)
            return 1
    data = open(DEPLOYED, "rb").read()
    rs, ds = sha256(REPO), sha256(DEPLOYED)
    print("repo == deployed (byte-identical): %s  sha256=%s  size=%d B" %
          (rs == ds, ds, len(data)))
    if rs != ds:
        fails.append("repo != deployed")

    for lit in PRESENT:
        ok = data.find(lit.encode("utf-16-le")) >= 0
        print("  present %-28s %s" % (lit, "OK" if ok else "MISSING"))
        if not ok:
            fails.append("literal missing: " + lit)
    for lit in ABSENT:
        ok = data.find(lit.encode("utf-16-le")) < 0
        print("  absent  %-28s %s" % (lit, "OK" if ok else "STILL PRESENT"))
        if not ok:
            fails.append("superseded literal still present: " + lit)

    if fails:
        print("VERIFY ROUND 13: FAIL")
        for f in fails:
            print("  - " + f)
        return 1
    print("VERIFY ROUND 13: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
