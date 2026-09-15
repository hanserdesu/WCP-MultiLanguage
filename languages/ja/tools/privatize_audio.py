#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""阶段 1 数据半场 —— 把共享音频目录按语言分流到 packs/<lang>/audio/。

背景（2026-09-14 实测）
──────────────────────
现在三种语言往同一批目录里倒音频：

    单词音频   JA -> LocalLow\\WCP\\vocabulary\\<词>.mp3      （游戏原生目录，共享）
               FR -> LocalLow\\WCP\\wcp\\fr_word_audio\\         （已私有）
               RU -> LocalLow\\WCP\\vocabulary\\<词>.mp3      （回退到共享！见 RuWordListMod.cs）
    例句音频   JA/FR/RU 全部 -> LocalLow\\WCP\\wcp\\sentence_audio\\<md5>.mp3

隔离目前靠「三个语言的提取器谓词互斥」这一**逻辑巧合**（假名/拉丁/西里尔），
不是文件系统的物理保证。加一门纯拉丁语系语言就直接串音 —— 这正是本阶段要
消掉的东西。

目标布局
────────
    LocalLow\\WCP\\packs\\<lang>\\audio\\word\\<词>.mp3
    LocalLow\\WCP\\packs\\<lang>\\audio\\sentence\\<md5>.mp3

分流规则（内容寻址，不猜）
──────────────────────────
· 例句音频文件名 = md5(该语言剥离函数在「例句：xx（译文）」上的结果)。
  所以对每个语言复算它的 md5 集合，文件归到命中的那个语言。
· 单词音频文件名 = 词形本身。所以用该语言词书 xlsx 的 A 列做集合。
· 命中 0 个语言 = 孤儿（如游戏原生的英语单词音频），**保留原处不动**。
· 命中 >1 个语言 = 冲突，只报告不搬（正常应为 0，因为谓词互斥）。

安全约定
────────
· 默认 dry-run。真跑要显式 --write。
· **只 copy 不 move**：legacy 目录原地保留，谁写的都不删（别人的活在别人手里）。
· legacy 目录近 --quiet-seconds 秒内被写过 => 判定有并发写入者，拒绝 --write
  （除非 --force）。这是 2026-09-14 踩过的坑：RU 的
  gen_sentence_audio_ru.py 正在往 sentence_audio\\ 灌文件，边写边搬必然赛跑。
· 幂等：目标已存在且字节数相同则跳过。

用法
────
    python tools/privatize_audio.py                 # dry-run，打印分流报告
    python tools/privatize_audio.py --write         # 真搬（会先做静默检查）
    python tools/privatize_audio.py --lang ja       # 只处理一种语言
    python tools/privatize_audio.py --no-cache      # 忽略缓存索引
"""
import sys
import os
import re
import json
import glob
import time
import shutil
import hashlib
import pathlib
import argparse

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

HOME = pathlib.Path(os.path.expanduser("~"))
LOCALLOW = HOME / "AppData" / "LocalLow" / "WCP"
RUNTIME_PACKS = LOCALLOW / "packs"
SENT_DIR = LOCALLOW / "wcp" / "sentence_audio"

# 单词音频的 legacy 来源。key = 目录标识, value = (路径, 是否共享)
WORD_SOURCES = [
    ("vocabulary", LOCALLOW / "vocabulary", True),
    ("fr_word_audio", LOCALLOW / "wcp" / "fr_word_audio", False),
    ("ru_word_audio", LOCALLOW / "wcp" / "ru_word_audio", False),
]

ROOT = pathlib.Path(__file__).resolve().parents[1]
INTEGRATION_ROOT = ROOT.parent
INDEX_CACHE = ROOT / "work" / "privatize_index"

# 各语言的例句主表与剥离函数。剥离函数必须是插件里 C# 版本的逐行翻译 ——
# 差一个字符 md5 就对不上，文件会被误判成孤儿。
LANG_SOURCES = {
    "ja": dict(project=ROOT / "wcp_wordbooks",
               master="data/translations/sentences_master.json",
               extractor="ja"),
    "fr": dict(project=INTEGRATION_ROOT / "French",
               master="data/translations/sentences_master.json",
               extractor="fr"),
    "ru": dict(project=INTEGRATION_ROOT / "Russian",
               master="data/translations/sentences_master.json",
               extractor="ru"),
}


# ─────────────────────── 剥离函数（C# 逐行翻译） ───────────────────────

def _common(raw):
    s = re.sub(r"<[^>]+>", "", raw or "")
    s = s.replace("例句：", "").strip()
    if not s:
        return None
    nl = s.find("\n")
    if nl >= 0:
        s = s[:nl].strip()
    return s


def extract_ja(raw):
    """mod_sentence_audio/SentenceAudioMod.cs :: ExtractJa"""
    s = _common(raw)
    if not s:
        return None
    if s.endswith("）"):
        i = s.rfind("（")
        if i > 0:
            s = s[:i].strip()
    if len(s) < 2:
        return None
    ok = any(0x3040 <= ord(c) <= 0x30FF or 0x4E00 <= ord(c) <= 0x9FFF for c in s)
    return s if ok else None


def extract_fr(raw):
    """D:/ATooManyLanguage/French/mod_sentence_audio_fr/SentenceAudioFrMod.cs :: ExtractFr"""
    s = _common(raw)
    if not s:
        return None
    if s.endswith("）"):
        i = s.rfind("（")
        if i > 0:
            s = s[:i].strip()
    if len(s) < 2:
        return None
    has_latin = any(
        ("A" <= c <= "Z") or ("a" <= c <= "z") or
        (0x00C0 <= ord(c) <= 0x024F) or c in "œŒæÆ"
        for c in s)
    if not has_latin:
        return None
    for c in s:
        if 0x3040 <= ord(c) <= 0x30FF or 0x3400 <= ord(c) <= 0x9FFF \
           or 0xF900 <= ord(c) <= 0xFAFF:
            return None
    return s


def extract_ru(raw):
    """D:/ATooManyLanguage/Russian/mod_sentence_audio_ru/SentenceAudioRuMod.cs :: ExtractRu
    注意与 ja/fr 的两处差异: 半角括号也算切尾符; 末尾要 TrimEnd('。',' ')。"""
    s = _common(raw)
    if not s:
        return None
    if s.endswith("）") or s.endswith(")"):
        i = s.rfind("（")
        if i < 0:
            i = s.rfind("(")
        if i > 0:
            s = s[:i].strip()
    s = s.rstrip("。 ")
    if len(s) < 2:
        return None
    has_cyr = any(0x0400 <= ord(c) <= 0x04FF or c in "ёЁ" for c in s)
    if not has_cyr:
        return None
    for c in s:
        o = ord(c)
        if ("A" <= c <= "Z") or ("a" <= c <= "z") or \
           (0x00C0 <= o <= 0x024F) or (0x3040 <= o <= 0x30FF) or \
           (0x3400 <= o <= 0x9FFF) or (0xF900 <= o <= 0xFAFF):
            return None
    return s


EXTRACTORS = {"ja": extract_ja, "fr": extract_fr, "ru": extract_ru}


def md5(s):
    return hashlib.md5(s.encode("utf-8")).hexdigest()


# ─────────────────────── 词书 / 清单 ───────────────────────

def load_manifest(lang):
    p = PACKS / lang / "manifest.json"
    if not p.exists():
        raise SystemExit(f"缺少清单: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def find_payload(name):
    """按 basename 在各项目的安装载荷目录里找词书 xlsx。"""
    for proj in (ROOT / "wcp_wordbooks", INTEGRATION_ROOT / "French", INTEGRATION_ROOT / "Russian"):
        hits = glob.glob(str(proj / "output" / "installer_pkg" / "*" / "support" / "payload" / "books" / name))
        if hits:
            return pathlib.Path(hits[0])
    return None


def read_xlsx_words(path):
    import openpyxl
    wb = openpyxl.load_workbook(str(path), read_only=True)
    ws = wb.active
    out = set()
    for row in ws.iter_rows(values_only=True):
        if row and row[0] not in (None, ""):
            out.add(str(row[0]).strip())
    wb.close()
    return out


def build_index(lang, use_cache=True):
    cache = INDEX_CACHE / f"{lang}.json"
    src = LANG_SOURCES[lang]
    master = src["project"] / src["master"]
    books = load_manifest(lang)["resources"]["books"]
    stamp = {
        "master_mtime": master.stat().st_mtime if master.exists() else 0,
        "books": books,
    }
    if use_cache and cache.exists():
        try:
            d = json.loads(cache.read_text(encoding="utf-8"))
            if d.get("stamp") == stamp:
                return set(d["sentence_md5"]), set(d["words"]), True
        except Exception:
            pass

    if not master.exists():
        raise SystemExit(f"缺少例句主表: {master}")

    ex = EXTRACTORS[src["extractor"]]
    raw = json.loads(master.read_text(encoding="utf-8"))
    md5s, rejected = set(), 0
    for _word, arr in raw.items():
        for pair in arr:
            if not (isinstance(pair, (list, tuple)) and len(pair) >= 2):
                rejected += 1
                continue
            ja, zh = pair[0], pair[1]
            # 与数据库实际存储格式一致：例句：{原文}（{译文}）
            got = ex(f"例句：{ja}（{zh}）")
            if got is None:
                rejected += 1
                # 剥离函数拒绝但它确实被写进了库 => 该条音频必然点不响，计入
                continue
            md5s.add(md5(got))

    words = set()
    missing = []
    for b in books:
        p = find_payload(pathlib.Path(b).name)
        if p is None:
            missing.append(b)
        else:
            words |= read_xlsx_words(p)

    INDEX_CACHE.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(
        {"stamp": stamp, "sentence_md5": sorted(md5s), "words": sorted(words),
         "rejected": rejected, "missing_books": missing},
        ensure_ascii=False), encoding="utf-8")
    return md5s, words, False


# ─────────────────────── legacy 扫描 ───────────────────────

def scan_dir(d):
    """返回 {stem: 文件路径}。忽略非音频文件与读不到的项。"""
    out = {}
    if not d.exists():
        return out
    for p in os.scandir(d):
        try:
            if not p.is_file():
                continue
            stem, ext = os.path.splitext(p.name)
            if ext.lower() not in (".mp3", ".wav"):
                continue
            out[stem] = pathlib.Path(p.path)
        except OSError:
            continue
    return out


def newest_mtime(dirs):
    newest = 0.0
    for d in dirs:
        try:
            if d.exists():
                newest = max(newest, d.stat().st_mtime)
        except OSError:
            pass
    return newest


# ─────────────────────── 主流程 ───────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="真搬（默认 dry-run）")
    ap.add_argument("--lang", action="append", help="只处理指定语言，可重复")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--force", action="store_true", help="跳过并发写入检查")
    ap.add_argument("--quiet-seconds", type=int, default=90)
    ap.add_argument("--limit", type=int, default=0, help="每种语言最多搬 N 个（试跑）")
    args = ap.parse_args()

    langs = args.lang or sorted(LANG_SOURCES)
    print("=" * 74)
    print("阶段 1 数据半场 — 共享音频目录按语言分流" + ("（DRY-RUN）" if not args.write else "（WRITE）"))
    print("=" * 74)

    # 1. 各语言索引
    print("\n[1] 各语言索引（例句 md5 集合 + 词书词集）")
    tables = {}
    for lang in langs:
        md5s, words, cached = build_index(lang, not args.no_cache)
        tables[lang] = (md5s, words)
        print(f"  {lang}: 例句 md5={len(md5s)}  词书词={len(words)}"
              f"  {'(缓存)' if cached else '(现场重算)'}")

    # 2. 互斥性断言 —— 整个隔离方案成立的前提
    print("\n[2] 语言间互斥性（这是'靠逻辑巧合隔离'的可执行证据）")
    ok_disjoint = True
    for i, a in enumerate(langs):
        for b in langs[i + 1:]:
            inter = tables[a][0] & tables[b][0]
            if inter:
                ok_disjoint = False
                print(f"  FAIL  {a} ∩ {b} 例句 md5 交集 = {len(inter)}（会串音）")
            else:
                print(f"  PASS  {a} ∩ {b} 例句 md5 交集 = 0")
            wi = tables[a][1] & tables[b][1]
            if wi:
                print(f"  WARN  {a} ∩ {b} 词书词交集 = {len(wi)}，样本 "
                      f"{list(sorted(wi))[:5]}")
    if not ok_disjoint:
        print("  => 存在交集，先别搬；隔离假设不成立。")

    # 3. 扫描 legacy
    print("\n[3] legacy 目录扫描")
    sent = scan_dir(SENT_DIR)
    print(f"  sentence_audio/  {len(sent)} 个音频"
          f"  mtime={time.strftime('%H:%M:%S', time.localtime(SENT_DIR.stat().st_mtime)) if SENT_DIR.exists() else '-'}")
    wordsrc = {}
    for key, path, shared in WORD_SOURCES:
        w = scan_dir(path)
        wordsrc[key] = (path, shared, w)
        print(f"  {key + '/':16s} {len(w)} 个音频"
              f"  {'(共享)' if shared else '(私有)'}"
              f"  mtime={time.strftime('%H:%M:%S', time.localtime(path.stat().st_mtime)) if path.exists() else '-'}")

    # 4. 分流
    print("\n[4] 分流结果")
    plan = {lang: {"sentence": [], "word": []} for lang in langs}
    conflict, orphan = [], []
    md5_owner = {}
    for lang in langs:
        for h in tables[lang][0]:
            md5_owner.setdefault(h, []).append(lang)
    word_owner = {}
    for lang in langs:
        for w in tables[lang][1]:
            word_owner.setdefault(w, []).append(lang)

    for stem, path in sent.items():
        owners = md5_owner.get(stem.lower(), [])
        if len(owners) == 1 and owners[0] in plan:
            plan[owners[0]]["sentence"].append((path, stem))
        elif len(owners) > 1:
            conflict.append(("sentence", stem, owners))
        else:
            orphan.append(("sentence", stem))

    for key, path, shared in WORD_SOURCES:
        pre = key.split("_")[0] if not shared else None
        for stem, fp in wordsrc[key][2].items():
            owners = word_owner.get(stem, [])
            if pre and pre in plan and pre in owners:
                plan[pre]["word"].append((fp, stem))
            elif len(owners) == 1 and owners[0] in plan:
                plan[owners[0]]["word"].append((fp, stem))
            elif len(owners) > 1:
                conflict.append(("word", stem, owners))
            else:
                orphan.append(("word", stem))

    for lang in langs:
        s, w = len(plan[lang]["sentence"]), len(plan[lang]["word"])
        print(f"  {lang}: 例句 {s} 个 / 单词 {w} 个 -> "
              f"{RUNTIME_PACKS / lang / 'audio'}")
    print(f"  冲突（多语言同时命中）= {len(conflict)}"
          + (f"  样本 {conflict[:5]}" if conflict else ""))
    print(f"  孤儿（任何语言都不认，保留原处）= {len(orphan)}"
          + (f"  样本 {orphan[:5]}" if orphan else ""))

    # 5. 并发写入检查
    legacy_dirs = [SENT_DIR] + [p for _k, p, _s in WORD_SOURCES]
    newest = newest_mtime(legacy_dirs)
    age = time.time() - newest if newest else 1e9
    active = age < args.quiet_seconds
    print(f"\n[5] 并发写入检查: legacy 目录最新改动 {age:.0f}s 前"
          f"  -> {'检测到写入者' if active else '已静默'}")

    if not args.write:
        print("\n(dry-run) 未写任何文件。加 --write 落盘。")
        return 0
    if active and not args.force:
        print(f"\n拒绝写入: legacy 目录 {args.quiet_seconds}s 内有改动，"
              f"边写边搬会赛跑（2026-09-14 实测 RU 生成器正在灌 sentence_audio/）。")
        print("等写入者停止，或确认安全后加 --force。")
        return 2

    # 6. 执行
    print("\n[6] 执行 copy（不动 legacy 原目录）")
    total = copied = skipped = 0
    for lang in langs:
        for kind, sub in (("sentence", "sentence"), ("word", "word")):
            dst_dir = RUNTIME_PACKS / lang / "audio" / sub
            items = plan[lang][kind]
            if args.limit:
                items = items[:args.limit]
            if not items:
                continue
            dst_dir.mkdir(parents=True, exist_ok=True)
            for src, stem in items:
                ext = src.suffix.lower()
                dst = dst_dir / (stem + ext)
                total += 1
                try:
                    if dst.exists() and dst.stat().st_size == src.stat().st_size:
                        skipped += 1
                        continue
                    shutil.copy2(src, dst)
                    copied += 1
                except OSError as e:
                    print(f"    ERR {src.name}: {e}")
            print(f"  {lang}/{sub}: {len(items)} 个 -> {dst_dir}")
    print(f"\n完成: 计划 {total}, 复制 {copied}, 跳过(已存在) {skipped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
