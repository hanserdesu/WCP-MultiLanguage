# -*- coding: utf-8 -*-
"""解析 kanjidic2.xml -> 常用汉字书骨架 (grade 1-8 ≈ 常用汉字表 2136 字)。

输出: output/kanji_books.json
  rows: {word, onyomi[], kunyomi[], meaning_en[], grade, jlpt}
显示/音频在 merge_kanji.py 组装。
"""
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
OUT = ROOT / 'output'

MAX_ON = 3      # 展示的音读上限
MAX_KUN = 3     # 展示的训读上限


def clean_kun(k):
    """训读 'あ.う' 保留; 去掉后缀标记 (あ.う; つか.う→) 中的异常。"""
    k = k.split(';')[0].strip()
    k = re.sub(r'[（(].*?[)）]', '', k)
    return k.strip('- ')


def main():
    tree = ET.parse(DATA / 'kanjidic2.xml')
    rows = []
    for ch in tree.getroot().iter('character'):
        g = ch.find('./misc/grade')
        if g is None:
            continue
        grade = int(g.text)
        if not (1 <= grade <= 8):
            continue  # 常用汉字表以外(9/10为名字用)
        lit = ch.find('literal').text
        on = [r.text for r in ch.findall('./reading_meaning/rmgroup/reading')
              if r.get('r_type') == 'ja_on']
        kun = [clean_kun(r.text) for r in
               ch.findall('./reading_meaning/rmgroup/reading')
               if r.get('r_type') == 'ja_kun']
        kun = [k for k in kun if k]
        jlpt_el = ch.find('./misc/jlpt')
        jlpt = int(jlpt_el.text) if jlpt_el is not None else 0
        meanings = []
        for m in ch.findall('./reading_meaning/rmgroup/meaning'):
            if not m.get('m_lang'):  # 默认英语
                meanings.append((m.text or '').strip())
        rows.append({
            'word': lit,
            'onyomi': on[:MAX_ON],
            'kunyomi': kun[:MAX_KUN],
            'meaning_en': meanings[:3],
            'grade': grade,
            'jlpt': jlpt,
        })
    print('常用汉字数:', len(rows))
    result = {
        'meta': {
            'source': 'kanjidic2 (EDRDG, CC-BY-SA-4.0) grade 1-8 (常用汉字表)',
            'count': len(rows),
        },
        'books': {'kanji': rows},
    }
    (OUT / 'kanji_books_raw.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=1), encoding='utf-8')
    for r in rows[:8]:
        print(r['word'], r['onyomi'], r['kunyomi'], r['meaning_en'],
              'g', r['grade'], 'jlpt', r['jlpt'])


if __name__ == '__main__':
    main()
