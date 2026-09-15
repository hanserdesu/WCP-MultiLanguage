# -*- coding: utf-8 -*-
"""Backfill missing IPA in portuguese_books.json from data/raw/ipa_pt_BR.txt.

Lookup strategy: exact match, then lowercase match. Strips / slashes.
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
BOOKS = ROOT / 'output' / 'portuguese_books.json'
IPA_RAW = ROOT / 'data' / 'raw' / 'ipa_pt_BR.txt'


def load_ipa_table():
    table = {}
    lower = {}
    for line in IPA_RAW.read_text(encoding='utf-8').splitlines():
        parts = line.split('\t', 1)
        if len(parts) != 2:
            continue
        word, ipa = parts[0].strip(), parts[1].strip().strip('/')
        if word and ipa and word not in table:
            table[word] = ipa
            lower.setdefault(word.lower(), ipa)
    return table, lower


# Pre-1990 European orthography -> modern spelling rules (ordered).
ORTHO_RULES = [
    ('cc', 'c'),
    ('cç', 'ç'),
    ('ct', 't'),
]

# Common accent misspellings -> correct form.
ACCENT_FIX = {
    'nao': 'não',
    'familia': 'família',
    'ja': 'já',
    'ha': 'há',
    'gloria': 'glória',
    'victoria': 'vitória',
    'historia': 'história',
    'memoria': 'memória',
    'vitoria': 'vitória',
    'necessidade': 'necessidade',
    'ideia': 'ideia',
}

# High-frequency words absent from the BR dictionary file; hand IPA (BR norm).
HAND_IPA = {
    'da': 'da',
    'no': 'nu',
    'ti': 'tʃi',
    'meus': 'mewʃ',
    'oh': 'o',
    'hey': 'hei',
    'eh': 'ɛ',
    'ler': 'ler',
    'sr': 'seˈɲoɾ',
    'sr.': 'seˈɲoɾ',
    'dr.': 'doˈtɔɾ',
    'sra.': 'seˈɲoɾa',
    's.': 'sɛˈɡʊ̃du',
    'd.': 'dɔˈtɔɾ',
    'fim-de-semana': 'fĩ dʒi siˈmɐ̃na',
    'hei-de': 'ej dʒi',
    'há-de': 'a dʒi',
    'big': 'big',
    'star': 'istaʁ',
    'so': 'sɔ',
    'bo': 'bo',
}


def main():
    table, lower = load_ipa_table()
    data = json.loads(BOOKS.read_text(encoding='utf-8'))
    filled = 0
    still = []

    def lookup(word):
        ipa = table.get(word) or lower.get(word.lower(), '')
        if ipa:
            return ipa
        # spelling-variant candidates (old -> new orthography)
        cands = {word}
        for a, b in ORTHO_RULES:
            cands = {c.replace(a, b) for c in cands}
        for c in cands:
            ipa = table.get(c) or lower.get(c.lower(), '')
            if ipa:
                return ipa
        # accent fix
        fixed = ACCENT_FIX.get(word.lower())
        if fixed:
            ipa = table.get(fixed) or lower.get(fixed.lower(), '')
            if ipa:
                return ipa
        # hand map
        return HAND_IPA.get(word.lower(), '')

    for lvl in data['levels'].values():
        for e in lvl:
            if e.get('ipa'):
                continue
            w = e.get('word', '')
            ipa = lookup(w)
            if ipa:
                e['ipa'] = ipa
                pos_zh = {'noun': '名', 'verb': '动', 'adj': '形', 'adv': '副',
                          'pron': '代', 'prep': '介', 'det': '限定',
                          'num': '数', 'conj': '连', 'intj': '叹'}.get(e.get('pos'), '?')
                e['meaning'] = f'[{ipa}] {e["zh"]}<{pos_zh}>'
                filled += 1
            else:
                still.append(w)
    BOOKS.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'filled: {filled}, still missing: {len(still)}')
    if still:
        print('sample:', still[:20])


if __name__ == '__main__':
    main()
