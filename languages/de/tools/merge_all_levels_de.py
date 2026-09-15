# -*- coding: utf-8 -*-
"""将精炼后的 B1/B2 数据合并入 output/german_books.json"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def clean_zh_strict(zh):
    zh = zh.replace('\n', '；').replace('\n', '；').replace('\r', '')
    terms = []
    for chunk in re.split(r'[,，;；/]', zh):
        chunk = re.sub(r'^[a-z]+\.\s*', '', chunk.strip())
        chunk = re.sub(r'\(.*?\)|\[.*?\]|（.*?）', '', chunk.strip())
        if chunk and chunk not in terms and len(chunk) <= 10:
            terms.append(chunk)
    return '；'.join(terms[:3]) if terms else '实用表达'

def main():
    books_p = ROOT / 'output' / 'german_books.json'
    books = json.loads(books_p.read_text('utf-8'))
    
    refined = json.loads((ROOT / 'work' / 'b1_b2_refined.json').read_text('utf-8'))
    
    # 保持 A1, A2
    a1 = books['levels'].get('a1', [])
    a2 = books['levels'].get('a2', [])
    
    # 清洗 B1, B2
    b1 = []
    for it in refined['b1']:
        it['zh'] = clean_zh_strict(it['zh'])
        b1.append(it)
        
    b2 = []
    for it in refined['b2']:
        it['zh'] = clean_zh_strict(it['zh'])
        b2.append(it)
        
    books['levels']['b1'] = b1
    books['levels']['b2'] = b2
    
    total = len(a1) + len(a2) + len(b1) + len(b2)
    books_p.write_text(json.dumps(books, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'成功合并全量四级德语词书: A1={len(a1)}, A2={len(a2)}, B1={len(b1)}, B2={len(b2)} | 总计={total} 词')

if __name__ == '__main__':
    main()
