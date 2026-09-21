# verify_round12.py — 第十二轮部署产物内容级校验（不看大小/时间戳，只看内容）
#
# 断言分两层：
#   A. 仓库 mod_host/WcpHost.dll 与游戏 BepInEx/plugins/WcpHost.dll 逐字节一致
#      （含 sha256）——「编译部署」这一步没有拿旧文件糊弄。
#   B. 本轮新增机制的标识字面量全部编进了 DLL（UTF-16LE 存储）：
#        - WordListMemo 守卫的两条快路径计数标签（Host.Evaluate）
#        - GameAdapter.SlotProfile 槽位词表归属缓存
#        - HostPatches.CensusAtAwake 的 Awake 期解析普查日志
#        - PerfProbe 窗口行「快路径命中=」摘要
#
# 用法: python verify_round12.py
import hashlib
import os
import sys

REPO = r"D:\ATooManyLanguage\MultiLanguage\mod_host\WcpHost.dll"
DEPLOYED = r"E:\Steam\steamapps\common\WCP-WordGirlgriend\BepInEx\plugins\WcpHost.dll"

LITERALS = [
    "内存词表指纹",
    "槽位词表指纹",
    "身份:读槽位词表",
    "Awake 期解析普查",
    "快路径命中=",
    "Harmony 接线完成",
    "ES3 批量写已启用",
]


def fail(msg):
    print("FAIL  " + msg)
    sys.exit(1)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    for p in (REPO, DEPLOYED):
        if not os.path.isfile(p):
            fail("missing: " + p)

    repo_bytes = open(REPO, "rb").read()
    dep_bytes = open(DEPLOYED, "rb").read()
    if repo_bytes != dep_bytes:
        fail("repo != deployed (sha256 repo=%s deployed=%s)" %
             (sha256(REPO), sha256(DEPLOYED)))
    print("OK  repo == deployed  sha256=%s  size=%d B" %
          (sha256(REPO), len(dep_bytes)))

    # .NET 托管字符串按 UTF-16LE 存。必须按**原始字节**找 needle.encode("utf-16-le")：
    # 整个 PE 文件按 UTF-16LE 解码会把字符串切到错误的码元边界上（上一轮脚本踩过），
    # 导致明明存在的字面量全部"缺失"。找不到时回退 UTF-8 字节再判缺。
    missing = []
    for lit in LITERALS:
        if dep_bytes.find(lit.encode("utf-16-le")) >= 0:
            print("OK  literal (utf-16le): " + lit)
        elif dep_bytes.find(lit.encode("utf-8")) >= 0:
            print("OK  literal (utf-8): " + lit)
        else:
            missing.append(lit)
    if missing:
        fail("MISSING literals: " + ", ".join(missing))

    print("VERIFY ROUND 12: PASS")


if __name__ == "__main__":
    main()
