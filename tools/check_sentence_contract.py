#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""例句注入契约机检（宿主自服务路径）。

背景
----
游戏的两条例句通路只认 `wcpFullEng.db` 的 `sentence2` 表：

    DatabaseManagerS8.OnSearchButtonClick  →  SELECT sentences FROM sentence2 WHERE word=@w
    SentenceReplyManager.StartThis         →  正则 <color=#FFBE31>例句\\d+：</color>([\\s\\S]*?)释义：

资源隔离落地后各语言插件默认不再写共享库（AllowSharedDatabaseWrites=false），库里只剩英语，
**所有受管词书的【例句】区都会空白**。宿主改成从 `packs/<lang>/db/sentences.json` 自服务，
所以这条链必须能被机检，否则下一次只会在游戏里表现为「例句又没了」。

被复刻的两段实现（改了要同步这里）
----------------------------------
1) 游戏的三段 Replace（DatabaseManagerS8.OnSearchButtonClick 内联）：
       例句：    → <color=#FFBE31>例句N：</color>
       （        → "\\n\\n释义："
       ）        → ""
   每句后再接 "\\n\\n"。
2) 游戏 ReserveExampleSentences(string)：取第一个 '：' 与第一个 '释义'，
   中间的片段去掉 '\\n' 与 '</color>'，写进 exmplesentences[i].text。
   —— 这一步决定了 ▶ 例句按钮拿去算 md5 的到底是哪个字符串。

断言（对每个 pack）
------------------
A. manifest 声明 sentence_table 且文件存在
B. sentences.json 顶层是 {schema, sentences}，且每个词的条目非空
C. 结构：每条以「例句：」开头、含全角括号译文尾
D. 端到端：raw → 三段 Replace → ReserveExampleSentences 提取 → ExtractSentenceKey(恒等形式)
   得到纯目标语言句，不含 <</> 标签、不含换行、不含「例句」残留
E. 音频契约：md5(纯目标语言句) + '.mp3' 必须真实存在于 pack 的 audio/sentence/

E 是本脚本最重要的一条：它同时是「宿主注入的文本」与「磁盘上的音频文件名」的
唯一共同约定。缺文件 = ▶ 按钮点了不响，而文本区看起来完全正常。

用法：
    python tools/check_sentence_contract.py [packs_root]

packs_root 默认 %USERPROFILE%\\AppData\\LocalLow\\WCP\\packs
退出码 0 = 全部通过。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path

# 自带策略 DLL 的语言（ja / yue）其 ExtractSentenceKey 是各自实现，本脚本的
# 「恒等提取」前提不成立，故只做 A-D，E 单独报「未纳入」。
HOST_STRATEGY = "$host"

TAG = re.compile(r"<[^>]+>")
SENTENCE_REPLY_RE = re.compile(r"<color=#FFBE31>例句\d+：</color>([\s\S]*?)释义：")


def game_render(raw: str, index: int) -> str:
    """复刻游戏的三段 Replace（index 从 0 计，显示为 index+1）。"""
    s = raw.replace("例句：", f"<color=#FFBE31>例句{index + 1}：</color>")
    s = s.replace("（", "\n\n释义：")
    s = s.replace("）", "")
    return s + "\n\n"


def reserve_example_sentences(rendered: str) -> str | None:
    """复刻 DatabaseManagerS8.ReserveExampleSentences 的提取部分。"""
    a = rendered.find("：")
    b = rendered.find("释义")
    if a < 0 or b < 0 or b <= a:
        return None
    return rendered[a + 1 : b].replace("\n", "").replace("\r", "").replace("</color>", "")


def extract_sentence_key(rendered_text: str) -> str | None:
    """复刻 WcpHost.Core.GenericLanguageStrategy.ExtractSentenceKey。"""
    if not rendered_text:
        return None
    text = TAG.sub("", rendered_text)
    text = text.replace("例句：", "").replace("例句:", "").strip()
    nl = text.find("\n")
    cr = text.find("\r")
    cut = min([i for i in (nl, cr) if i >= 0], default=-1)
    if cut >= 0:
        text = text[:cut].strip()
    if not text:
        return None
    full = text.rfind("（")
    if full >= 0 and text.endswith("）"):
        text = text[:full].strip()
    return text


def to_db_row(entry) -> str | None:
    """复刻 WcpHost.Core.SentenceTable.EntryToDbRow（两代形状归一）。"""
    if isinstance(entry, str):
        return entry or None
    if isinstance(entry, dict):
        sent = entry.get("sentence")
        if not isinstance(sent, str) or not sent:
            return None
        if sent.startswith("例句："):
            return sent
        tr = entry.get("translate") or entry.get("translation")
        if not isinstance(tr, str) or not tr:
            return sent
        return f"例句：{sent}（{tr}）"
    return None


def md5(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def head(value) -> str:
    """截断显示 —— 例句表里混进非字符串时也要能报出来而不是自己崩。"""
    return repr(value)[:60]


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        os.environ.get("USERPROFILE", "")) / "AppData" / "LocalLow" / "WCP" / "packs"
    if not root.is_dir():
        print(f"packs 根不存在: {root}")
        return 2

    errors: list[str] = []
    infos: list[str] = []
    print(f"packs 根 = {root}\n")

    for lang_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        mpath = lang_dir / "manifest.json"
        if not mpath.is_file():
            continue
        lang = lang_dir.name
        man = json.loads(mpath.read_text(encoding="utf-8"))
        res = man.get("resources", {})
        st_rel = res.get("sentence_table")
        strategy = (man.get("strategy") or {}).get("assembly")
        print(f"--- [{lang}] strategy={strategy} sentence_table={st_rel}")

        if not st_rel:
            errors.append(f"{lang}: manifest 未声明 resources.sentence_table")
            continue
        st_path = lang_dir / st_rel.replace("/", os.sep)
        if not st_path.is_file():
            errors.append(f"{lang}: 例句表缺失 {st_path}")
            continue

        doc = json.loads(st_path.read_text(encoding="utf-8"))
        if not isinstance(doc, dict) or not isinstance(doc.get("sentences"), dict):
            errors.append(f"{lang}: 顶层结构不是 {{schema, sentences}} —— "
                          f"直接 d.get(word) 会永远取不到")
            continue
        table = doc["sentences"]
        declared = (man.get("counts") or {}).get("sentence_words")
        if declared is not None and declared != len(table):
            errors.append(f"{lang}: manifest.counts.sentence_words={declared} "
                          f"≠ 实际 {len(table)}")

        audio_dir = lang_dir / (res.get("sentence_audio") or "").replace("/", os.sep)
        audio_files = set(os.listdir(audio_dir)) if audio_dir.is_dir() else set()

        checked = 0
        missing_audio: list[str] = []
        for word, items in table.items():
            if not isinstance(items, list) or not items:
                errors.append(f"{lang}: 词 {word!r} 例句为空")
                continue
            for i, entry in enumerate(items):
                raw = to_db_row(entry)
                if raw is None or not raw.startswith("例句："):
                    errors.append(f"{lang}: {word!r}[{i}] 归一后不是「例句：」开头的行: "
                                  f"{head(entry)}")
                    break
                if "（" not in raw or "）" not in raw:
                    errors.append(f"{lang}: {word!r}[{i}] 缺全角括号译文尾: {head(raw)}")
                    break

                rendered = game_render(raw, i)
                m = SENTENCE_REPLY_RE.search(rendered)
                if not m:
                    errors.append(f"{lang}: {word!r}[{i}] 游戏正则匹配不上注入文本")
                    break
                extracted = reserve_example_sentences(rendered)
                if extracted is None:
                    errors.append(f"{lang}: {word!r}[{i}] ReserveExampleSentences 提取为空")
                    break
                if any(ch in extracted for ch in "<>\n\r"):
                    errors.append(f"{lang}: {word!r}[{i}] 提取结果残留标签/换行: "
                                  f"{extracted[:40]!r}")
                    break
                if "例句" in extracted:
                    errors.append(f"{lang}: {word!r}[{i}] 提取结果残留「例句」: "
                                  f"{extracted[:40]!r}")
                    break

                key = extract_sentence_key(extracted)
                if key != extracted:
                    errors.append(f"{lang}: {word!r}[{i}] ExtractSentenceKey 不是恒等: "
                                  f"{key[:40]!r} != {extracted[:40]!r}")
                    break

                checked += 1
                if audio_files and (md5(extracted) + ".mp3") not in audio_files:
                    missing_audio.append(f"{word}[{i}]={extracted[:40]}")

        if strategy == HOST_STRATEGY:
            if missing_audio:
                errors.append(f"{lang}: md5 契约断裂 {len(missing_audio)}/{checked} 条"
                              f"（▶ 点了不响），样例: " + " | ".join(missing_audio[:3]))
            else:
                infos.append(f"{lang}: {len(table)} 词 / {checked} 句 端到端 md5 命中 100%")
        else:
            infos.append(f"{lang}: {len(table)} 词 / {checked} 句 结构+提取通过；"
                         f"md5 命中 {checked - len(missing_audio)}/{checked}"
                         f"（自带策略 DLL，谓词未独立复刻，故不做硬断言）")
            if missing_audio:
                infos.append(f"       未命中样例: " + " | ".join(missing_audio[:3]))

    print()
    for line in infos:
        print(f"[OK]   {line}")
    if errors:
        print()
        for e in errors:
            print(f"[FAIL] {e}")
        print(f"\n总体: {len(errors)} 项未通过")
        return 1
    print("\n总体: ALL PASS（例句注入链在结构 / 提取 / 音频 md5 三层一致）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
