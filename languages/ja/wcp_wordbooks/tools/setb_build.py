# -*- coding: utf-8 -*-
"""构建 Set B-1 主题词书 (惯用句/拟声拟态/四字熟语)。

输入: data/topic/{idioms,giongo,yoji}.json  (LLM 精翻词表, 含读音+中文释义)
输出: output/setb_books.json  (与 jlpt_books.json 行结构一致)
释义格式: 汉字词 -> 【读音】中文〈词性〉; 假名词 -> 中文〈词性〉
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data' / 'topic'
OUT = ROOT / 'output'

sys.path.insert(0, str(ROOT / 'tools'))
from build_books import fmt_meaning_zh  # noqa: E402

BOOKS = {
    'idioms': '慣用句・諺',
    'giongo': 'オノマトペ',
    'yoji': '四字熟語',
    'advanced': '高級語彙',
    'business': 'ビジネス敬語',
}


def main():
    books = {}
    for key, label in BOOKS.items():
        entries = json.loads((DATA / f'{key}.json').read_text(encoding='utf-8'))
        rows, seen = [], set()
        for e in entries:
            w = e['w'].strip()
            r = e['r'].strip()
            zh = e['z'].strip()
            pos = e.get('p', '').strip()
            if not w or not r or not zh or w in seen:
                continue
            seen.add(w)
            rows.append({
                'word': w,
                'reading': r,
                'meaning_zh': zh,
                'pos_zh': pos,
                'meaning': fmt_meaning_zh(w, r, zh, pos),
                'meaning_en': '',
                'example_ja': e.get('ex_ja', ''),
                'example_en': '',
                'example_zh': e.get('ex_zh', ''),
                'level': label,
                'topic': key,
                'zh_source': 'llm',
            })
        books[key] = rows

    result = {
        'meta': {
            'generated': 'WCP SetB-1 主题词书 (惯用句/拟声拟态/四字熟语)',
            'sources': [
                'IdiomKB https://github.com/lishuang-w/IdiomKB (惯用句词表, 释义全重写)',
                'ryancahildebrandt/yoji (四字熟语读音校验)',
                'Pomax/node-jp-giongo (拟声拟态词表)',
                'LLM 精翻: data/topic/*.json',
            ],
            'stats': {k: len(v) for k, v in books.items()},
        },
        'levels': books,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / 'setb_books.json'
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1),
                   encoding='utf-8')
    print(json.dumps(result['meta']['stats'], ensure_ascii=False),
          f'-> {out}')


if __name__ == '__main__':
    main()
