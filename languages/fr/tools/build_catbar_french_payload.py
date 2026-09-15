# -*- coding: utf-8 -*-
"""Generate catbar_french_book.json (8116 words merged single book) for French installer and offline tools."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'output'


def fmt_meaning(w):
    ipa = ('[' + w['ipa'] + '] ') if w.get('ipa') else ''
    return ipa + w['zh'] + '〈' + w['pos'] + '〉'


def main():
    books = json.loads((OUT / 'french_books.json').read_text(encoding='utf-8'))
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

    if len(words) != 8116:
        raise ValueError(f'Expected 8116 words, got {len(words)}')

    payload = {
        'id': 'catbar-french-cefr-complete',
        'language': 'fr',
        'display_name': '法语词库(猫条版)',
        'word_count': len(words),
        'fingerprint_sha256': '376af2eae0292052cefb4cb0d673f48a5ca480a38e25a6bf5353998caea17e9d',
        'words': words,
        'meanings': meanings
    }

    out_p = OUT / 'catbar_french_book.json'
    out_p.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'Generated {out_p}: {len(words)} words')


if __name__ == '__main__':
    main()

