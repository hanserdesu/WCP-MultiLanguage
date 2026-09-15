# -*- coding: utf-8 -*-
"""生成 catbar_russian_book.json (8451 词合并单册) 供俄语安装包与离线工具使用。"""
import hashlib
import json
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'output'


def fmt_meaning(w):
    stress = f"[{w['stress']}]" if w.get('stress') else ''
    return f"{stress}{w['zh']}〈{w['pos']}〉"


def compute_fingerprint(words):
    norm = sorted([unicodedata.normalize('NFC', w.strip()) for w in words])
    payload = '\n'.join(norm) + '\n'
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def main():
    books = json.loads((OUT / 'russian_books.json').read_text(encoding='utf-8'))
    seen = set()
    words = []
    meanings = {}

    for lvl in ['a1', 'a2', 'b1', 'b2']:
        for w in books['levels'][lvl]:
            word = w['word'].strip()
            meaning = fmt_meaning(w)
            if not word or not meaning or word in seen:
                continue
            seen.add(word)
            words.append(word)
            meanings[word] = meaning

    if len(words) != 8451:
        raise ValueError(f'Expected 8451 words, got {len(words)}')

    fp = compute_fingerprint(words)
    expected_fp = 'dfecb0ab75e9b3ef75aedd47c677d68594b060bfbb84cc6bd94efd7888f4b74e'
    if fp != expected_fp:
        raise ValueError(f'Fingerprint mismatch! Computed {fp} vs expected {expected_fp}')

    payload = {
        'id': 'catbar-russian-cefr-complete',
        'language': 'ru',
        'display_name': '俄语词库(猫条版)',
        'word_count': len(words),
        'fingerprint_sha256': fp,
        'words': words,
        'meanings': meanings
    }

    out_p = OUT / 'catbar_russian_book.json'
    out_p.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'Generated {out_p}: {len(words)} words, fingerprint: {fp}')


if __name__ == '__main__':
    main()
