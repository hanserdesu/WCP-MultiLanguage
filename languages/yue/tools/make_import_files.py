# -*- coding: utf-8 -*-
"""生成完全符合游戏《万词破-单词女友》无表头 NPOI 契约的 Excel 词书：
A列: 单词
B列: 释义 (游戏显示，格式: [粤拼] 中文释义〈词性〉)
C列: 粤拼 (供参考)
D列: 级别/分类 (供参考)
"""
import json
import sys
from pathlib import Path
from openpyxl import Workbook

sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parents[1]
BOOKS_JSON = ROOT / "output" / "cantonese_books.json"
OUTPUT_IMPORT = ROOT / "output" / "import"
PACK_BOOKS = ROOT / "packs" / "yue" / "books"


def build_excel():
    OUTPUT_IMPORT.mkdir(parents=True, exist_ok=True)
    PACK_BOOKS.mkdir(parents=True, exist_ok=True)

    if not BOOKS_JSON.exists():
        print(f"找不到 {BOOKS_JSON}，请先运行 build_all_data.py")
        sys.exit(1)

    data = json.loads(BOOKS_JSON.read_text(encoding='utf-8'))
    words = data.get("vocabulary", [])

    wb = Workbook()
    ws = wb.active
    ws.title = "粤语词库"

    # 严格遵循万词破契约：无表头行，从第 0 行 (openpyxl 行号 1) 开始直接填充数据
    for item in words:
        w = item["word"]
        meaning = item["formatted_meaning"]
        jp = item["jyutping"]
        lvl = item.get("level", "")
        ws.append([w, meaning, jp, lvl])

    filename = "粤语词库(猫条版).xlsx"
    target_1 = OUTPUT_IMPORT / filename
    target_2 = PACK_BOOKS / filename

    wb.save(target_1)
    wb.save(target_2)

    print(f"成功生成无表头 Excel 词书: {len(words)} 词")
    print(f"  - {target_1}")
    print(f"  - {target_2}")


if __name__ == "__main__":
    build_excel()
