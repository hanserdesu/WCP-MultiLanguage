#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WCP 统一接入架构 — 就绪度自检

把 ARCHITECTURE-UNIFIED.md §5 的验收条款变成可执行检查。
可反复运行；退出码 0 = 无 FAIL。

用法:
    python tools/arch_check.py            # 全部检查
    python tools/arch_check.py -v         # 打印每条判据细节

设计原则: 每条检查都要能"指向一个具体文件/数字"，不产生无法行动的报告。
"""
import sys
import os
import re
import json
import glob
import hashlib
import pathlib

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = pathlib.Path(__file__).resolve().parents[1]
INTEGRATION_ROOT = ROOT.parent
PACKS = ROOT / "packs"
HOST = ROOT / "mod_host"

# 各语言项目的仓库根 + 注册表文件 + 词书载荷目录
PROJECTS = {
    "Japanese": INTEGRATION_ROOT / "Japanese",
    "French": INTEGRATION_ROOT / "French",
    "Russian": INTEGRATION_ROOT / "Russian",
    "German": INTEGRATION_ROOT / "German",
}
REGISTRY_CANDIDATES = ["mod_book_name/BookProfiles.cs"]
PAYLOAD_GLOBS = [
    "output/installer_pkg/*/support/payload/books",
    "wcp_wordbooks/output/installer_pkg/*/support/payload/books",
    "output/import",
]

VERBOSE = "-v" in sys.argv
FAILS = []
WARNS = []


def ok(tag, msg):
    print(f"  PASS  {tag}: {msg}")


def fail(tag, msg):
    FAILS.append(f"{tag}: {msg}")
    print(f"  FAIL  {tag}: {msg}")


def warn(tag, msg):
    WARNS.append(f"{tag}: {msg}")
    print(f"  WARN  {tag}: {msg}")


def info(msg):
    if VERBOSE:
        print(f"        {msg}")


def strip_comments(src: str) -> str:
    """去掉 // 与 /* */ 注释，用于"语言无关性"扫描。"""
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    src = re.sub(r"//[^\n]*", "", src)
    return src


def sha256_of_words(words) -> str:
    """与 C# BookRegistry.FingerprintOf 逐字节一致: 排序 + '\\n' 连接 + UTF-8。"""
    norm = sorted(w.strip() for w in words)
    return hashlib.sha256(("\n".join(norm) + "\n").encode("utf-8")).hexdigest()


def read_xlsx_words(path: pathlib.Path):
    import openpyxl
    wb = openpyxl.load_workbook(str(path), read_only=True)
    ws = wb.active
    out = []
    for row in ws.iter_rows(values_only=True):
        if row and row[0] not in (None, ""):
            out.append(str(row[0]))
    wb.close()
    return out


def find_book_file(name: str):
    """在所有项目的载荷目录里按 basename 找词书文件。"""
    for proj in PROJECTS.values():
        for g in PAYLOAD_GLOBS:
            for d in glob.glob(str(proj / g)):
                p = pathlib.Path(d) / name
                if p.exists():
                    return p
    return None


# ─────────────────────────── 检查 ───────────────────────────

def check_manifests():
    print("\n[1] 语言包清单")
    files = sorted(PACKS.glob("*/manifest.json"))
    if not files:
        fail("1.1", f"未找到任何 manifest: {PACKS}/*/manifest.json")
        return []
    manifests = []
    for f in files:
        try:
            m = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            fail("1.1", f"{f.parent.name}/manifest.json 解析失败: {e}")
            continue
        missing = [k for k in ("schema", "profile_id", "language", "display_name",
                               "word_count", "fingerprint_sha256", "es3_prefix",
                               "resources", "strategy") if k not in m]
        if missing:
            fail("1.2", f"{f.parent.name}: 缺必需字段 {missing}")
            continue
        res = m["resources"]
        rmiss = [k for k in ("books", "meaning_db", "sentence_table", "repair",
                             "word_audio", "sentence_audio") if k not in res]
        if rmiss:
            fail("1.3", f"{f.parent.name}: resources 缺 {rmiss}")
            continue
        if not re.fullmatch(r"[0-9a-f]{64}", m["fingerprint_sha256"]):
            fail("1.4", f"{f.parent.name}: fingerprint_sha256 不是 64 位小写十六进制")
            continue
        m["_path"] = f
        manifests.append(m)
    ok("1.1", f"{len(manifests)} 个语言包清单全部可解析且字段完整")
    return manifests


def check_identity_uniqueness(manifests):
    print("\n[2] 身份唯一性（profile_id / 指纹 / 语言 / 槽位 / ES3前缀）")
    for field, label in (("profile_id", "profile_id"), ("language", "language"),
                         ("fingerprint_sha256", "指纹"), ("es3_prefix", "ES3前缀")):
        vals = [m[field] for m in manifests]
        dup = {v for v in vals if vals.count(v) > 1}
        if dup:
            fail("2.x", f"{label} 重复: {dup}")
        else:
            ok(f"2.{field[:4]}", f"{label} 唯一（{len(vals)} 个）")
    slots = [(m["language"], m.get("observed_slot", 0)) for m in manifests]
    used = [s for _, s in slots if s > 0]
    if len(set(used)) != len(used):
        fail("2.5", f"observed_slot 重复: {slots}")
    else:
        ok("2.5", f"已分配 observed_slot 不重复，候选包=0: {dict(slots)}")
    if len(used) > 4:
        fail("2.6", f"预分配槽位 {len(used)} > 游戏硬上限 4 槽（候选包不占槽）")
    else:
        ok("2.6", f"预分配槽位 {len(used)} ≤ 4 槽预算，语言包目录 {len(manifests)} 个")


def check_fingerprint_recompute(manifests):
    """最强的一条: 从实际 xlsx 载荷复算并集指纹，必须等于 manifest 声明值。"""
    print("\n[3] 指纹复算（从实际 xlsx 载荷算并集，与 manifest 声明比对）")
    for m in manifests:
        names = m["resources"]["books"]
        files = []
        missing = []
        for n in names:
            p = find_book_file(pathlib.Path(n).name)
            if p is None:
                missing.append(n)
            else:
                files.append(p)
        if missing:
            warn("3.x", f"{m['language']}: 载荷目录里找不到 {missing}（未安装？跳过复算）")
            continue
        words = set()
        per = {}
        for p in files:
            w = read_xlsx_words(p)
            per[p.name] = len(w)
            words |= set(w)
        fp = sha256_of_words(words)
        if len(words) != m["word_count"]:
            fail("3.1", f"{m['language']}: 并集词数 {len(words)} ≠ 声明 {m['word_count']}")
        elif fp != m["fingerprint_sha256"]:
            fail("3.2", f"{m['language']}: 并集指纹 {fp[:16]}… ≠ 声明 "
                        f"{m['fingerprint_sha256'][:16]}…")
        else:
            ok("3.3", f"{m['language']}: {per} → 并集 {len(words)} 词，指纹吻合")


def check_registry_drift(manifests):
    """跨项目注册表漂移: 每个项目的 BookProfiles.cs 是否登记了全部语言。"""
    print("\n[4] 跨项目注册表漂移（fork 架构的直接代价）")
    entries = {}
    for name, proj in PROJECTS.items():
        found = []
        for rel in REGISTRY_CANDIDATES:
            p = proj / rel
            if p.exists():
                src = p.read_text(encoding="utf-8-sig", errors="replace")
                found = re.findall(r'new BookProfile\("([^"]+)",\s*(\w+),', src)
                entries[name] = (p, found)
                break
        if not found:
            info(f"{name}: 无注册表（尚未做插件）")
    if not entries:
        warn("4.0", "任何项目都没有注册表")
        return
    # 声明语言集合
    declared = {m["profile_id"] for m in manifests}
    for name, (p, found) in sorted(entries.items()):
        ids = {i for i, _ in found}
        miss = declared - ids
        sha = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
        if miss:
            fail("4.1", f"{name} 项目注册表（sha256={sha}）缺 {sorted(miss)} "
                        f"— 说明每加一种语言，其它语言项目的 DLL 都必须重编译")
        else:
            ok("4.2", f"{name} 项目注册表（sha256={sha}）登记齐全")
    # 副本一致性: 同一项目内多份 BookProfiles.cs 必须逐字节相同
    for name, proj in PROJECTS.items():
        copies = [p for p in proj.glob("mod_*/BookProfiles.cs")]
        if len(copies) < 2:
            continue
        hashes = {hashlib.sha256(p.read_bytes()).hexdigest() for p in copies}
        if len(hashes) > 1:
            fail("4.3", f"{name} 项目内 {len(copies)} 份 BookProfiles.cs 内容不一致: "
                        f"{[p.as_posix() for p in copies]}")
        else:
            ok("4.3", f"{name} 项目内 {len(copies)} 份副本逐字节一致")


def check_host_language_agnostic():
    print("\n[5] 宿主语言无关性（补丁点不随语言增长）")
    # strategies/ is the explicit L2 extension point; its language-specific
    # strings are the payload behavior being loaded by the language-agnostic
    # host, not a host branch. Keep the scan focused on L0/L1 mechanism code.
    srcs = sorted(p for p in HOST.rglob("*.cs")
                  if not ({"strategies", "tests"} & set(p.relative_to(HOST).parts)))
    if not srcs:
        fail("5.0", f"找不到宿主源码: {HOST}")
        return
    bad_tokens = ["假名", "汉字", "西里尔", "拉丁", "LooksJapanese", "LooksFrench",
                  "LooksRussian", "ExtractJa", "ExtractFr", "ExtractRu",
                  '"ja"', '"fr"', '"ru"', '"de"']
    hits = []
    for p in srcs:
        code = strip_comments(p.read_text(encoding="utf-8", errors="replace"))
        for tok in bad_tokens:
            if tok in code:
                hits.append(f"{p.relative_to(ROOT).as_posix()} 含 {tok!r}")
    if hits:
        fail("5.1", f"宿主代码里出现语言专属标识 {len(hits)} 处: {hits[:5]}")
    else:
        ok("5.1", f"{len(srcs)} 个宿主源文件均无语言专属分支（去注释后）")

    print("\n[6] 资源路由无跨语言路径串")
    router = HOST / "Core" / "ResourceRouter.cs"
    if not router.exists():
        fail("6.0", "缺少 Core/ResourceRouter.cs")
    else:
        code = strip_comments(router.read_text(encoding="utf-8", errors="replace"))
        leaked = [t for t in ["vocabulary", "jp_word_audio", "fr_word_audio",
                             "ru_word_audio", "_db_payload"] if t in code]
        if leaked:
            fail("6.1", f"路由器里出现共享/他语言路径常量: {leaked}")
        else:
            ok("6.1", "路由器不含任何共享或跨语言路径常量（路径全部来自 manifest）")


def check_probes_are_real(manifests):
    """探针词必须真出现在对应语言的插件源码里 —— 防止清单里编造数据。"""
    print("\n[7] 自愈探针词与插件源码一致")
    src_for = {
        "Japanese": "mod_jp_wordlist/JpWordListMod.cs",
        "French": "mod_fr_wordlist/FrWordListMod.cs",
        "Russian": "mod_ru_wordlist/RuWordListMod.cs",
        "German": "mod_de_wordlist/DeWordListMod.cs",
    }
    for m in manifests:
        proj = next((k for k, v in {"Japanese": "ja", "French": "fr",
                                    "Russian": "ru", "German": "de"}.items()
                     if v == m["language"]), None)
        if proj is None:
            warn("7.x", f"{m['language']}: 无对应插件源码，跳过")
            continue
        p = PROJECTS[proj] / src_for[proj]
        if not p.exists():
            warn("7.x", f"{m['language']}: 找不到 {p}")
            continue
        src = p.read_text(encoding="utf-8-sig", errors="replace")
        miss = [w for w in m.get("repair_probes", []) if w not in src]
        if miss:
            fail("7.1", f"{m['language']}: 探针词 {miss} 未出现在 {p.name} 中（清单数据存疑）")
        else:
            ok("7.2", f"{m['language']}: 探针词 {len(m.get('repair_probes', []))} 个全部见于源码")


def check_build_artifacts():
    print("\n[8] 宿主构建产物")
    dll = HOST / "WcpHost.dll"
    if dll.exists():
        ok("8.1", f"WcpHost.dll 存在（{dll.stat().st_size} 字节）")
    else:
        fail("8.1", "WcpHost.dll 未构建（跑 mod_host/build.cmd）")
    deployed = pathlib.Path("E:/Steam/steamapps/common/WCP-WordGirlgriend/"
                            "BepInEx/plugins/WcpHost.dll")
    if deployed.exists():
        # 已部署是合法状态（阶段 1 起）；此时改为校验部署件与本地构建一致
        if dll.exists():
            a = hashlib.sha256(dll.read_bytes()).hexdigest()
            b = hashlib.sha256(deployed.read_bytes()).hexdigest()
            if a == b:
                ok("8.2", f"已部署且与本地构建一致（sha256={a[:16]}…）")
            else:
                fail("8.2", "已部署的 WcpHost.dll 与本地构建不一致——重新部署或重编译")
        else:
            warn("8.2", f"宿主已部署到游戏目录但本地无构建产物（{deployed}）")
    else:
        ok("8.2", "未部署到游戏目录")
    # packs 清单：部署一致性（LocalLow/WCP/packs/<lang>/manifest.json）
    ll_packs = pathlib.Path(os.path.expanduser(
        "~/AppData/LocalLow/WCP/packs"))
    if ll_packs.is_dir():
        for mf in sorted((ROOT / "packs").glob("*/manifest.json")):
            dep = ll_packs / mf.parent.name / "manifest.json"
            if dep.exists():
                if hashlib.sha256(mf.read_bytes()).hexdigest() == \
                        hashlib.sha256(dep.read_bytes()).hexdigest():
                    ok("8.3", f"packs/{mf.parent.name}/manifest.json 已部署且一致")
                else:
                    fail("8.3", f"packs/{mf.parent.name}/manifest.json 部署件与源不一致")
            else:
                warn("8.3", f"packs/{mf.parent.name}/manifest.json 本地有、未部署")


def main():
    print("=" * 72)
    print("WCP 统一接入架构 — 就绪度自检")
    print("=" * 72)
    manifests = check_manifests()
    if manifests:
        check_identity_uniqueness(manifests)
        check_fingerprint_recompute(manifests)
        check_probes_are_real(manifests)
    check_registry_drift(manifests)
    check_host_language_agnostic()
    check_build_artifacts()

    print("\n" + "=" * 72)
    print(f"结果: {len(FAILS)} FAIL / {len(WARNS)} WARN")
    for f in FAILS:
        print(f"  FAIL  {f}")
    for w in WARNS:
        print(f"  WARN  {w}")
    print("=" * 72)
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
