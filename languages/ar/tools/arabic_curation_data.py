# -*- coding: utf-8 -*-
"""阿拉伯语专业词库生成器: 构建分级词书与专业领域词书数据集。
主会话直写，产出结构化 JSON 数据集到 data/ 目录。
"""
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
LEVELS_DIR = DATA / 'levels'
THEMED_DIR = DATA / 'themed'

TASHKEEL_REGEX = re.compile(r'[\u064B-\u0652\u0670\u0640]')

def strip_tashkeel(text: str) -> str:
    """去除阿拉伯语标音符号 (Tashkeel) 得到规范检索形。"""
    return TASHKEEL_REGEX.sub('', text)

def make_entry(word, transliteration, root, pos, meaning, example_ar, example_zh, category, level):
    return {
        "word": word.strip(),
        "unvocalized": strip_tashkeel(word).strip(),
        "transliteration": transliteration.strip(),
        "root": root.strip() if root else "",
        "pos": pos.strip(),
        "meaning": f"[{transliteration}] {meaning}〈{pos}〉",
        "raw_meaning": meaning.strip(),
        "example_ar": example_ar.strip(),
        "example_zh": example_zh.strip(),
        "category": category.strip(),
        "level": level.strip()
    }
