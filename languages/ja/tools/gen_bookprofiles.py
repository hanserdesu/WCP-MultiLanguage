#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从语言包清单生成 BookProfiles.cs（WcpBookProfiles 注册表）。

为什么要有这个脚本
──────────────────
`BookProfiles.cs` 原来是**手抄副本**：日语/法语/俄语/德语四个项目各带一份，
法语和俄语项目内部还各有 3 份拷贝。2026-09-14 实测漂移证据：

    日语项目 mod_book_name/BookProfiles.cs  sha256=a7f3dd58…  只登记 ja+fr
    法语项目 mod_book_name/BookProfiles.cs  sha256=a7f3dd58…  只登记 ja+fr
    俄语项目 mod_book_name/BookProfiles.cs  sha256=767adff6…  登记 ja+fr+ru

后果：**每加一种语言，其它语言项目的每一个 DLL 都必须重编译**，否则那些
DLL 会把新语言的词书当成「非受管词书」。这正是 fork 架构的结构性代价。

生成后，`packs/<lang>/manifest.json` 成为唯一事实来源；加语言只需要新增一个
语言包目录。本脚本用 `--check` 可以当 CI 用：清单改了但没重新生成 → 退出码 1。

指纹算法（FingerprintOf）必须是**逐字节**与下面两处一致，改动会让已导入的
词书全部失配：
    · 宿主  mod_host/Core/Manifest.cs  (BookRegistry.FingerprintOf)
    · 工具  tools/arch_check.py        (sha256_of_words)

用法
────
    python tools/gen_bookprofiles.py            # 只报告差异（dry-run）
    python tools/gen_bookprofiles.py --write    # 写入所有项目副本
    python tools/gen_bookprofiles.py --check    # CI：有差异则退出码 1
"""
import sys
import json
import glob
import hashlib
import pathlib

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = pathlib.Path(__file__).resolve().parents[1]
INTEGRATION_ROOT = ROOT.parent
PACKS = ROOT / "packs"


def pack_roots():
    """语言包的事实来源 = 所有 <项目>/packs 的并集。

    语言包可以放在各自项目目录里（例如 Contonese/packs/yue）。只扫 Japanese/packs 会让
    放在自己项目里的语言包悄悄消失：粤语包按设计就在 Contonese 项目内，注册表里因此
    没有 catbar-cantonese-complete 条目，粤语词书永远匹配不上身份
    （2026-09-15 实测：插件引用了 BookProfiles.Cantonese 常量，却匹配不到自己的书）。
    """
    roots = [PACKS]
    for root in PROJECT_ROOTS:
        cand = root / "packs"
        if cand.exists() and cand != PACKS:
            roots.append(cand)
    return roots
PROJECT_ROOTS = [
    INTEGRATION_ROOT / "Japanese",
    INTEGRATION_ROOT / "French",
    INTEGRATION_ROOT / "Russian",
    INTEGRATION_ROOT / "German",
    INTEGRATION_ROOT / "Contonese",
    INTEGRATION_ROOT / "Spanish",
    INTEGRATION_ROOT / "Portuguese",
    INTEGRATION_ROOT / "Arabic",
    INTEGRATION_ROOT / "korean",
]

# 语言代码 -> C# 常量名。未列出的语言回退成「首字母大写」。
LANG_CONST = {
    "ja": "Japanese", "fr": "French", "ru": "Russian",
    "de": "German", "es": "Spanish", "it": "Italian",
    "ko": "Korean", "zh": "Chinese", "en": "English",
    "pt": "Portuguese", "ar": "Arabic",
}

# 插件源码引用、但当前不一定有已部署语言包的语言常量。
#
# 为什么必须有这一层：注册表只登记「已存在的 packs/*/manifest.json」，
# 但每个语言的插件源码会**直接引用自己的语言常量**做身份判定，
# 例如 Contonese/mod_yue_wordlist/YueWordListMod.cs 里的
# `memoryProfile.Language != BookProfiles.Cantonese`。
# 粤语包按设计放在 Contonese 项目内、且槽位未占用，因此 Java/packs 下没有
# yue 清单 —— 早先版本只按清单生成常量，重新生成就把 `Cantonese` 常量
# 抹掉了，粤语插件随即编译失败（2026-09-15 实测 CS0117 ×5）。
# 常量与「是否注册了词书」是两件事：常量必须始终存在，注册表才按清单裁剪。
CONST_ONLY = {
    "yue": "Cantonese",
}

HEADER = """// Shared identity registry for the portable WCP word-book plugins.
//
// 生成物 — 不要手改。
//   事实来源: D:/ATooManyLanguage/Japanese/packs/<lang>/manifest.json
//   重新生成: python tools/gen_bookprofiles.py --write
//   漂移检查: python tools/gen_bookprofiles.py --check
//
// 以前这份注册表在 4 个项目里各有一份手抄副本（法语/俄语项目内部还各 3 份），
// 加一种语言就得同步改 N 处 —— 2026-09-14 实测漂移: 日语与法语项目的副本
// 只登记 ja+fr，缺 ru。改成从清单生成后，「加一种语言」只需要新增一个
// packs/<lang>/manifest.json，不必重编译任何现有语言的 DLL。
//
// FingerprintOf 必须与 mod_host/Core/Manifest.cs 逐字节一致。
"""

BODY_HEAD = """using System;
using System.Collections.Generic;
using System.Security.Cryptography;
using System.Text;

namespace WcpBookProfiles
{
    internal sealed class BookProfile
    {
        internal readonly string Id;
        internal readonly string Language;
        internal readonly string DisplayName;
        internal readonly int WordCount;
        internal readonly string Fingerprint;

        internal BookProfile(string id, string language, string displayName,
                             int wordCount, string fingerprint)
        {
            Id = id;
            Language = language;
            DisplayName = displayName;
            WordCount = wordCount;
            Fingerprint = fingerprint;
        }
    }

    internal static class BookProfiles
    {
"""

BODY_TAIL = """
        // Fingerprints are SHA256 over the sorted full word-form set, so a book
        // matches in any custom slot. Registering every managed book here lets a
        // plugin positively identify — and therefore never touch — the others'.
        internal static readonly BookProfile[] All = new BookProfile[]
        {
%(entries)s        };

        internal static BookProfile Match(IList<string> words)
        {
            if (words == null || words.Count == 0) return null;
            string hash = null;
            for (int i = 0; i < All.Length; i++)
            {
                BookProfile p = All[i];
                if (words.Count != p.WordCount) continue;
                if (hash == null) hash = FingerprintOf(words);
                if (hash == p.Fingerprint) return p;
            }
            return null;
        }

        internal static bool IsManagedDisplayName(string text)
        {
            if (string.IsNullOrEmpty(text)) return false;
            for (int i = 0; i < All.Length; i++)
                if (text.StartsWith(All[i].DisplayName, StringComparison.Ordinal)) return true;
            return false;
        }

        internal static string FingerprintOf(IList<string> words)
        {
            if (words == null) return null;
            List<string> normalized = new List<string>(words.Count);
            for (int i = 0; i < words.Count; i++)
            {
                string word = words[i];
                if (word == null) return null;
                normalized.Add(word.Trim().Normalize(NormalizationForm.FormC));
            }
            normalized.Sort(StringComparer.Ordinal);
            StringBuilder payload = new StringBuilder();
            for (int i = 0; i < normalized.Count; i++)
                payload.Append(normalized[i]).Append('\\n');
            byte[] bytes = Encoding.UTF8.GetBytes(payload.ToString());
            using (SHA256 sha = SHA256.Create())
            {
                byte[] digest = sha.ComputeHash(bytes);
                StringBuilder hex = new StringBuilder(digest.Length * 2);
                for (int i = 0; i < digest.Length; i++) hex.Append(digest[i].ToString("x2"));
                return hex.ToString();
            }
        }
    }
}
"""


def load_manifests():
    out = []
    files = []
    for d in pack_roots():
        files.extend(sorted(d.glob("*/manifest.json")))
    for f in files:
        m = json.loads(f.read_text(encoding="utf-8"))
        need = ("profile_id", "language", "display_name", "word_count",
                "fingerprint_sha256")
        miss = [k for k in need if k not in m]
        if miss:
            raise SystemExit(f"清单 {f} 缺字段 {miss}")
        out.append(m)
    if not out:
        raise SystemExit("没有找到任何清单: <项目>/packs/*/manifest.json")
    langs = [m["language"] for m in out]
    dup = {x for x in langs if langs.count(x) > 1}
    if dup:
        raise SystemExit(f"语言代码重复，会生成重名常量: {dup}")
    # 固定顺序 ja, fr, ru, de… —— 与现有手抄副本的条目顺序一致，让 diff 只看内容。
    order = list(LANG_CONST.keys())
    def key(m):
        return (order.index(m["language"]) if m["language"] in order else len(order),
                m["language"])
    return sorted(out, key=key)


def render(manifests):
    consts = []
    # 常量的来源 = 已注册清单 ∪ 插件源码强制需要的语言。
    langs = []
    for m in manifests:
        if m["language"] not in langs:
            langs.append(m["language"])
    for code in CONST_ONLY:
        if code not in langs:
            langs.append(code)
    for code in langs:
        name = (LANG_CONST.get(code) or CONST_ONLY.get(code)
                or code.capitalize())
        consts.append('        internal const string %s = "%s";' % (name, code))

    entries = []
    for m in manifests:
        name = (LANG_CONST.get(m["language"]) or CONST_ONLY.get(m["language"])
                or m["language"].capitalize())
        entries.append(
            '            new BookProfile("%s", %s, "%s", %d,\n                "%s"),'
            % (m["profile_id"], name, m["display_name"], m["word_count"],
               m["fingerprint_sha256"]))
    body = BODY_HEAD + "\n".join(consts) + "\n" + \
        BODY_TAIL % {"entries": "\n".join(entries) + "\n"}
    text = HEADER + "\n" + body
    return text.replace("\n", "\r\n").encode("utf-8")   # CRLF, UTF-8 无 BOM


def targets():
    out = []
    for root in PROJECT_ROOTS:
        if not root.exists():
            continue
        for f in sorted(root.glob("mod_*/BookProfiles.cs")):
            out.append(f)
    return out


def main():
    write = "--write" in sys.argv
    check = "--check" in sys.argv
    payload = render(load_manifests())
    want_sha = hashlib.sha256(payload).hexdigest()

    print(f"生成内容: {len(payload)} 字节, sha256={want_sha[:16]}…")
    print(f"目标副本: {len(targets())} 个\n")

    changed, same = [], []
    for p in targets():
        cur = p.read_bytes()
        if cur == payload:
            same.append(p)
            print(f"  一致    sha={hashlib.sha256(cur).hexdigest()[:12]}  {p}")
            continue
        changed.append(p)
        old = hashlib.sha256(cur).hexdigest()[:12]
        n_old = cur.count(b"new BookProfile(")
        n_new = payload.count(b"new BookProfile(")
        print(f"  待更新  sha={old} -> {want_sha[:12]}  条目 {n_old} -> {n_new}  {p}")

    if write:
        for p in changed:
            p.write_bytes(payload)
        print(f"\n已写入 {len(changed)} 个副本，跳过 {len(same)} 个已一致的。")
    elif changed:
        print(f"\n(dry-run) 有 {len(changed)} 个副本需要更新，加 --write 落盘。")

    if check and changed:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
