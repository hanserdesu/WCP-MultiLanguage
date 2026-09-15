# -*- coding: utf-8 -*-
"""用 kanjidic2 校验主题词书(含人工增补)中汉字词读音的合理性。
规则同 setb_check_readings.py: 读音应能分解为各汉字音/训读+送假名。
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KXML = ROOT / 'data' / 'kanjidic2.xml'
OUT = ROOT / 'output'
THDIR = ROOT / 'data' / 'themed'
sys.stdout.reconfigure(encoding='utf-8')

KANA = re.compile(r'^[\u3041-\u3096ー]+$')


def load_readings():
    import xml.etree.ElementTree as ET
    rd = {}
    for _, el in ET.iterparse(str(KXML), events=('end',)):
        if el.tag != 'character':
            continue
        ch = el.findtext('literal')
        readings = set()
        for r in el.iter('reading'):
            if r.get('r_type') in ('ja_on', 'ja_kun'):
                v = (r.text or '').strip()
                if v:
                    readings.add(v)
        if ch:
            rd[ch] = readings
        el.clear()
    return rd


def hira(s):
    return ''.join(chr(ord(c) - 96) if 'ァ' <= c <= 'ン' else c for c in s)


DAKU = str.maketrans('かきくけこさしすせそたちつてとはひふへほ',
                     'がぎぐげござじずぜぞだぢづでどばびぶべぼ')
HANDAKU = str.maketrans('はひふへほ', 'ぱぴぷぺぽ')


def variants(v):
    out = {v}
    if v:
        out.add(v[0].translate(DAKU) + v[1:])
        out.add(v[0].translate(HANDAKU) + v[1:])
        if v[-1] in 'つくちき':
            out.add(v[:-1] + 'っ')
    return {x for x in out if x}


def check(word, reading, rd):
    if not re.search(r'[\u4e00-\u9fff々]', word):
        return True
    r = hira(reading)
    kanjis = [c for c in word if re.match(r'[\u4e00-\u9fff々]', c)]
    if not kanjis:
        return True
    MAX_OKURI = 4

    def rec(ki, pos):
        if ki == len(kanjis):
            return pos >= len(r) - 4
        cand = set()
        for v in rd.get(kanjis[ki], ()):
            v = hira(v)
            v = re.sub(r'\([^)]*\)', '', v)
            v = v.split('.')[0]
            for vv in variants(v):
                if r.startswith(vv, pos):
                    cand.add(pos + len(vv))
        for p in cand:
            for extra in range(0, MAX_OKURI + 1):
                if p + extra <= len(r) and rec(ki + 1, p + extra):
                    return True
        return False

    return rec(0, 0)


def main():
    if not KXML.exists():
        print('kanjidic2.xml 不存在, 跳过')
        return
    rd = load_readings()
    print(f'kanjidic2 载入 {len(rd)} 字')
    pairs = []
    books = json.loads((OUT / 'themed_books.json').read_text(encoding='utf-8'))
    for t, rows in books['themes'].items():
        for e in rows:
            pairs.append((t, e['word'], e['reading'], e.get('extra', False)))
    total = bad = 0
    flags = []
    for t, w, r, is_extra in pairs:
        if not re.search(r'[\u4e00-\u9fff々]', w):
            continue
        total += 1
        if r and not check(w, r, rd):
            bad += 1
            flags.append(f"[{'X' if is_extra else '-'}] {t}: {w} -> {r}")
    print(f'汉字词 {total} 个, 可疑读音 {bad} 个 (X=人工增补条目)')
    for f in flags[:80]:
        print(f)
    (ROOT / 'logs' / 'themed_reading_flags.txt').write_text(
        '\n'.join(flags), encoding='utf-8')


if __name__ == '__main__':
    main()
