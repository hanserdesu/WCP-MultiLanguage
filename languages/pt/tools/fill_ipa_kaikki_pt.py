# -*- coding: utf-8 -*-
"""Second-pass IPA backfill: stream kaikki-pt.jsonl for words still missing IPA.

Old-orthography words often have their own Wiktionary entries with IPA that
the first build pass missed (headword normalization dropped them).
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
BOOKS = ROOT / 'output' / 'portuguese_books.json'
KAIKKI = ROOT / 'data' / 'raw' / 'kaikki-pt.jsonl'


def main():
    data = json.loads(BOOKS.read_text(encoding='utf-8'))
    missing = {}
    for lvl in data['levels'].values():
        for e in lvl:
            if not e.get('ipa') and e.get('word'):
                missing.setdefault(e['word'], []).append(e)
    print(f'targets: {len(missing)}')
    if not missing:
        return

    found = {}
    scanned = 0
    with KAIKKI.open(encoding='utf-8') as f:
        for line in f:
            if not any(w in line for w in missing):
                continue
            scanned += 1
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            w = entry.get('word', '')
            if w in missing and w not in found:
                for s in entry.get('sounds', []):
                    ipa = s.get('ipa', '')
                    if ipa:
                        found[w] = ipa.strip('/')
                        break

    filled = 0
    for w, entries in missing.items():
        ipa = found.get(w)
        if not ipa:
            continue
        for e in entries:
            e['ipa'] = ipa
            pos_zh = {'noun': '名', 'verb': '动', 'adj': '形', 'adv': '副',
                      'pron': '代', 'prep': '介', 'det': '限定',
                      'num': '数', 'conj': '连', 'intj': '叹'}.get(e.get('pos'), '?')
            e['meaning'] = f'[{ipa}] {e["zh"]}<{pos_zh}>'
            filled += 1
    BOOKS.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    still = [w for w in missing if w not in found]
    print(f'filled: {filled}, still missing: {len(still)}')
    if still:
        print('sample:', still[:40])


if __name__ == '__main__':
    main()
