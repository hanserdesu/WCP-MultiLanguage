# -*- coding: utf-8 -*-
"""导出一批待LLM精翻/复核的词条给自动化agent处理。

输出 data/translations/llm_batch_pending.json:
  [{word, reading, meaning_en, meaning_zh(可空), example_ja, level}]
处理完成后agent把结果写入 data/translations/zh_llm_<时间戳>.json:
  {word: "中文释义"}
并调用 merge_translations.py 合并。

选择策略: 优先 1) 无中文释义的;  2) 有中文但可疑(过短/含英文残留/以'到'结尾等)的
"""
import json
import random
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'output'
TDIR = ROOT / 'data' / 'translations'
PENDING = TDIR / 'llm_batch_pending.json'


def suspicious(zh, en):
    if not zh:
        return False  # 缺失由 missing 队列负责
    # 括号内的注音/用法说明(假名/英文)是合法内容, 先剔除再检查
    zh_core = re.sub(r'（[^）]*）|\([^)]*\)', '', zh)
    # 含未翻译英文残留(排除常用缩写)
    if re.search(r'[A-Za-z]{3,}', zh_core) and 'pH' not in zh_core:
        return True
    # 中文与英文原文相同 => 实际未翻译
    if zh.strip().lower() == en.strip().lower():
        return True
    # 假名残留(未翻译的日文)
    if re.search(r'[\u3040-\u30ff]', zh_core):
        return True
    return False


def main():
    n_missing, n_bad = 80, 40
    data = json.loads((OUT / 'jlpt_books.json').read_text(encoding='utf-8'))
    seen, items = set(), []
    for lv in ['n5', 'n4', 'n3', 'n2', 'n1']:
        for r in data['levels'][lv]:
            w = r['word']
            if w in seen:
                continue
            seen.add(w)
            items.append({
                'word': w,
                'reading': r['reading'],
                'meaning_en': r['meaning_en'],
                'meaning_zh': r['meaning_zh'],
                'example_ja': r['example_ja'],
                'level': r['level'],
            })
    missing = [it for it in items if not it['meaning_zh']]
    bad = [it for it in items if it['meaning_zh']
           and suspicious(it['meaning_zh'], it['meaning_en'])]
    random.shuffle(bad)
    batch = (bad[:n_bad] + missing[:n_missing])[:n_missing + n_bad]
    TDIR.mkdir(parents=True, exist_ok=True)
    PENDING.write_text(json.dumps(batch, ensure_ascii=False, indent=1),
                       encoding='utf-8')
    print(f'pending={len(batch)} (missing={len(missing)}, suspicious={len(bad)})')
    for it in batch[:5]:
        print(' ', it['word'], '|', it['meaning_zh'] or '(空)', '|', it['meaning_en'][:40])


if __name__ == '__main__':
    main()
