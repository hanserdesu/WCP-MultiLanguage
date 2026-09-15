# -*- coding: utf-8 -*-
"""Generate catbar_german_book.json (8062 words merged single book) for German installer and offline tools."""
import hashlib
import json
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'output'


def fmt_meaning(w):
    ipa = ('[' + w['ipa'] + '] ') if w.get('ipa') else ''
    return ipa + w['zh'] + '〈' + w['pos'] + '〉'


def fingerprint_of(words):
    norm = [unicodedata.normalize('NFC', w.strip()) for w in words]
    norm.sort()
    payload = '\n'.join(norm) + '\n'
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def main():
    books = json.loads((OUT / 'german_books.json').read_text(encoding='utf-8'))
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

    if len(words) != 8062:
        raise ValueError(f'Expected 8062 words, got {len(words)}')

    fp = fingerprint_of(words)

    payload = {
        'id': 'catbar-german-complete',
        'language': 'de',
        'display_name': '德语词库(猫条版)',
        'word_count': len(words),
        'fingerprint_sha256': fp,
        'words': words,
        'meanings': meanings
    }

    out_p = OUT / 'catbar_german_book.json'
    out_p.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'Generated {out_p}: {len(words)} words, fp={fp}')


if __name__ == '__main__':
    main()
