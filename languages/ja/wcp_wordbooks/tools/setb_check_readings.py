# -*- coding: utf-8 -*-
"""用 kanjidic2 校验 Set B 词表中汉字词读音的合理性。

规则: 词的读音应能分解为各汉字的音/训读 (+ 每字后至多3个送假名,
末尾至多3个假名)。分解失败即为可疑读音, 输出人工复核。
kanjidic2.xml 由另一管线下载, 此处只读。
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KXML = ROOT / 'data' / 'kanjidic2.xml'
DATA = ROOT / 'data' / 'topic'
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
    return ''.join(chr(ord(c) - 96) if 'ァ' <= c <= 'ン' else c
                   for c in s)


DAKU = str.maketrans('かきくけこさしすせそたちつてとはひふへほ',
                     'がぎぐげござじずぜぞだぢづでどばびぶべぼ')
HANDAKU = str.maketrans('はひふへほ', 'ぱぴぷぺぽ')


def variants(v):
    """读音候选: 原形 / 连浊(首假名浊化) / 半浊化 / 促音变(尾つくち→っ)。"""
    out = {v}
    if v:
        out.add(v[0].translate(DAKU) + v[1:])
        out.add(v[0].translate(HANDAKU) + v[1:])
        if v[-1] in 'つくちき':
            out.add(v[:-1] + 'っ')
    return {x for x in out if x}


def check(word, reading, rd):
    if not re.search(r'[\u4e00-\u9fff々]', word):
        return True  # 纯假名词跳过
    r = hira(reading)
    kanjis = [c for c in word if re.match(r'[\u4e00-\u9fff々々]', c)]
    if not kanjis:
        return True
    MAX_OKURI = 4  # 汉字间送假名/活用形容忍

    def rec(ki, pos):
        if ki == len(kanjis):
            return pos >= len(r) - 4  # 末尾残余≤4假名
        cand = set()
        for v in rd.get(kanjis[ki], ()):  # 音/训读
            v = hira(v)
            v = re.sub(r'\([^)]*\)', '', v)
            v = v.split('.')[0]
            for vv in variants(v):
                if r.startswith(vv, pos):
                    cand.add(pos + len(vv))
        for p in cand:  # 送假名 0..4
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
    total = bad = 0
    for key in ('idioms', 'giongo', 'yoji', 'advanced', 'business', 'it')
        entries = json.loads((DATA / f'{key}.json').read_text(encoding='utf-8'))
        for e in entries:
            w, r = e['w'], e['r']
            if not re.search(r'[\u4e00-\u9fff々]', w):
                continue
            total += 1
            if not check(w, r, rd):
                bad += 1
                print(f'[?] {key}: {w} -> {r}')
    print(f'汉字词 {total} 个, 可疑读音 {bad} 个')


if __name__ == '__main__':
    main()
