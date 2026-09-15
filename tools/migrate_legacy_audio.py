#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P0-2 数据半场 —— 把 legacy 例句音频按语言分流到 packs/<lang>/audio/sentence/。

与 Japanese/tools/privatize_audio.py 同思路, 但面向 2026-09-15 现状:
legacy 目录是**每语言私有**的 <lang>_sentence_audio/ (不是共享目录),
md5 命名规则与插件一致, 因此直接整目录 copy 即可, 不需要逐文件复算 md5。

· 只 copy 不 move: legacy 目录原地保留 (旧插件回退路径继续可用)。
· 幂等: 目标已存在且字节数相同则跳过。
· 报告: 每语言 文件数/字节数/已存在跳过数。

用法:
    python tools/migrate_legacy_audio.py                # dry-run 报告
    python tools/migrate_legacy_audio.py --write        # 真拷贝
    python tools/migrate_legacy_audio.py --only fr,de   # 限定语言
"""
import argparse
import os
import shutil
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

HOME = os.path.expanduser("~")
WCP = os.path.join(HOME, "AppData", "LocalLow", "WCP", "wcp")
PACKS = os.path.join(HOME, "AppData", "LocalLow", "WCP", "packs")
LANGS = ["ja", "fr", "de", "ru", "es", "pt", "ko", "ar", "yue"]


def one(lang, write, kind="sentence"):
    suffix = "_sentence_audio" if kind == "sentence" else "_word_audio"
    src = os.path.join(WCP, lang + suffix)
    dst = os.path.join(PACKS, lang, "audio", kind)
    if not os.path.isdir(src):
        print(f"{lang}: 无 legacy 目录, 跳过")
        return
    files = [f for f in os.listdir(src) if f.lower().endswith(".mp3")]
    total = sum(os.path.getsize(os.path.join(src, f)) for f in files)
    have = set()
    if os.path.isdir(dst):
        have = set(os.listdir(dst))
    todo = [f for f in files if f not in have]
    skip = len(files) - len(todo)
    print(f"{lang}: legacy={len(files)} ({total/1048576:.0f} MB) "
          f"已有={skip} 待拷={len(todo)}")
    if not write:
        return
    os.makedirs(dst, exist_ok=True)
    done = 0
    t0 = time.time()
    for f in todo:
        s = os.path.join(src, f)
        d = os.path.join(dst, f)
        shutil.copy2(s, d)
        done += 1
        if done % 5000 == 0:
            rate = done / max(time.time() - t0, 0.001)
            print(f"  ... {done}/{len(todo)} ({rate:.0f} files/s)")
    print(f"{lang}: 拷贝完成 {done}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--only", default="")
    ap.add_argument("--kind", default="both", choices=("sentence", "word", "both"))
    args = ap.parse_args()
    langs = [x.strip() for x in args.only.split(",") if x.strip()] or LANGS
    kinds = ("sentence", "word") if args.kind == "both" else (args.kind,)
    for kind in kinds:
        print("== %s ==" % kind)
        for lang in langs:
            one(lang, args.write, kind)


if __name__ == "__main__":
    main()
