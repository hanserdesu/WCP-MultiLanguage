#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Repair the empty daily-study queue left by switching JP -> FR mid-session.

The game persists the daily source list and its remaining-list separately.  When
the old S8 page survives a book change, it can overwrite the new French
remaining-list with its completed Japanese state.  This repair is deliberately
fail-closed: it acts only for the French custom slot, only when the source list
is non-empty, and only when both the remaining and completed lists are empty.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
import shutil
import sys


SAVE = Path.home() / "AppData/LocalLow/WCP/wcp/SaveFile.es3"
FRENCH_SLOT = "自定义词书二"


def value(doc: dict, key: str, default):
    node = doc.get(key)
    if not isinstance(node, dict):
        return default
    return node.get("value", default)


def set_value(doc: dict, key: str, new_value) -> None:
    node = doc.get(key)
    if not isinstance(node, dict):
        raise RuntimeError(f"存档缺少 ES3 键: {key}")
    node["value"] = new_value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true",
                        help="write the guarded repair (default is dry-run)")
    args = parser.parse_args()

    if not SAVE.is_file():
        raise RuntimeError(f"找不到存档: {SAVE}")
    doc = json.loads(SAVE.read_text(encoding="utf-8-sig"))
    chosen = value(doc, "ChosenBook_Para", None)
    mode = value(doc, "S8ThisMode_Para", None)
    source = value(doc, "S8TestWordList_DailyStudy", None)
    left = value(doc, "S8TestWordList_DailyStudy_left", None)
    finished = value(doc, "S8TestWordList_DailyStudy_Finished", None)

    if chosen != FRENCH_SLOT:
        raise RuntimeError(f"当前不是法语槽位，拒绝修改: {chosen!r}")
    if mode != "每日学习":
        raise RuntimeError(f"当前不是每日学习，拒绝修改: {mode!r}")
    if not isinstance(source, list) or not source:
        raise RuntimeError("每日学习源题库为空，拒绝修改")
    if not isinstance(left, list) or not isinstance(finished, list):
        raise RuntimeError("每日学习队列格式异常，拒绝修改")
    if left or finished:
        raise RuntimeError(
            f"检测到实际进度（剩余 {len(left)}，完成 {len(finished)}），拒绝重置")

    print(f"可修复：法语每日学习源题库 {len(source)} 词，剩余/完成均为 0。")
    if not args.apply:
        print("DRY RUN；以 --apply 写入并自动备份。")
        return 0

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = SAVE.with_name(f"SaveFile.es3.before_stale_s8_fr_repair_{stamp}.bak")
    shutil.copy2(SAVE, backup)

    fresh = list(source)
    set_value(doc, "S8TestWordList_DailyStudy_left", fresh)
    set_value(doc, "S8TestWordList_Para", list(fresh))
    set_value(doc, "S8needToLearnWordList_Para", list(fresh))
    set_value(doc, "S8HaveLearnedWordList_Para", [])
    set_value(doc, "S8HaveLearnedStatusList_Para", [])
    set_value(doc, "S8VagueTimesThisTimeList_Para", [])
    set_value(doc, "S8ForgetThisTimeList_Para", [])
    set_value(doc, "S8Progress_Para", 0)
    set_value(doc, "S8LookBack_Para", 0)
    set_value(doc, "checkWordInDictionary", fresh[0])

    SAVE.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")),
                    encoding="utf-8")
    check = json.loads(SAVE.read_text(encoding="utf-8"))
    if value(check, "S8TestWordList_DailyStudy_left", None) != fresh:
        raise RuntimeError("回读校验失败；保留备份，未确认修复")
    print(f"已修复 {len(fresh)} 个待学法语词；备份: {backup}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
