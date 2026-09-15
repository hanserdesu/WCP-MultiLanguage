# -*- coding: utf-8 -*-
"""检查粤语词汇数据集格式与质量的校验脚本"""
import json
import re
import sys
from pathlib import Path

# 粤拼格式正则：字母加声调1-6，或者轻声/纯声母m4/ng4等
JYUTPING_PATTERN = re.compile(r'^[a-z1-6\s\-\,\.\'\?]+$', re.IGNORECASE)


def validate_file(path: Path) -> dict:
    if not path.exists():
        return {"file": str(path), "ok": False, "error": "文件不存在"}

    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception as e:
        return {"file": str(path), "ok": False, "error": f"JSON 解析失败: {e}"}

    words = data if isinstance(data, list) else data.get("words", [])
    if not words:
        return {"file": str(path), "ok": False, "error": "词条列表为空"}

    seen = set()
    errors = []
    for idx, item in enumerate(words):
        word = item.get("word", "").strip()
        jyutping = item.get("jyutping", "").strip()
        pos = item.get("pos", "").strip()
        meaning = item.get("meaning", "").strip()
        sentences = item.get("sentences", [])

        if not word:
            errors.append(f"第 {idx} 项缺少 word 字段")
            continue
        if word in seen:
            errors.append(f"重复词条: {word}")
        seen.add(word)

        if not jyutping:
            errors.append(f"[{word}] 缺少 jyutping 字段")
        if not meaning:
            errors.append(f"[{word}] 缺少 meaning 字段")
        if not pos:
            errors.append(f"[{word}] 缺少 pos 字段")

        if not sentences or len(sentences) < 1:
            errors.append(f"[{word}] 至少需要 1 条地条例句")
        else:
            for s_idx, s in enumerate(sentences):
                s_text = s.get("sentence", "").strip()
                s_trans = s.get("translate", "").strip()
                if not s_text:
                    errors.append(f"[{word}] 例句 {s_idx} 文本为空")
                if not s_trans:
                    errors.append(f"[{word}] 例句 {s_idx} 翻译为空")

    return {
        "file": str(path),
        "ok": len(errors) == 0,
        "count": len(words),
        "errors": errors[:10],
        "total_errors": len(errors)
    }


if __name__ == "__main__":
    files = sys.argv[1:] if len(sys.argv) > 1 else list(Path("data").glob("*.json"))
    all_ok = True
    total_words = 0
    for f in files:
        res = validate_file(Path(f))
        status = "OK" if res["ok"] else "FAIL"
        print(f"[{status}] {res['file']} - 词数: {res.get('count', 0)}")
        if not res["ok"]:
            all_ok = False
            for err in res["errors"]:
                print(f"    - {err}")
            if res["total_errors"] > len(res["errors"]):
                print(f"    ... 以及其他 {res['total_errors'] - len(res['errors'])} 处错误")
        else:
            total_words += res["count"]

    print(f"\n总计校验有效词条数: {total_words}")
    sys.exit(0 if all_ok else 1)
