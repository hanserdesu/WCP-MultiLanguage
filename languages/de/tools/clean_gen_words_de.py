# -*- coding: utf-8 -*-
"""清理 gen_words 与 books 中中文释义残留的拉丁词"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def clean_pure_cjk(s):
    # 移除所有英文字符及转义符
    s = re.sub(r'[A-Za-z\/]+', '', s)
    s = s.replace('\n', '；').replace('\r', '')
    terms = []
    for chunk in re.split(r'[,，;；]', s):
        chunk = re.sub(r'\(.*?\)|\[.*?\]|（.*?）', '', chunk).strip()
        if chunk and chunk not in terms and len(chunk) <= 12:
            terms.append(chunk)
    return '；'.join(terms[:3]) if terms else '常用表达'

def main():
    books_p = ROOT / 'output' / 'german_books.json'
    books = json.loads(books_p.read_text('utf-8'))
    
    for lvl in ['b1', 'b2']:
        for it in books['levels'].get(lvl, []):
            it['zh'] = clean_pure_cjk(it['zh'])
            
    books_p.write_text(json.dumps(books, ensure_ascii=False, indent=2), encoding='utf-8')
    print("已清理 output/german_books.json 中 B1/B2 释义！")

if __name__ == '__main__':
    main()
