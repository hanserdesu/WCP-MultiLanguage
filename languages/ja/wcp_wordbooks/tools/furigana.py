# -*- coding: utf-8 -*-
"""为含汉字的日语词生成逐字振假名标注 (漢[かん]字[じ])。

像中文拼音标在汉字上一样, 把词的读音按字面拆解回每个汉字:
  食べる + たべる  -> 食[た]べる
  東京   + とうきょう -> 東[とう]京[きょう]
拆解依据 kanjidic2 的音/训读, 容忍连浊/半浊/促音变体 (复用 setb_check_readings
的变体思路)。拆不开的熟字训 (塩梅[あんばい]) 或含罗马字词回退为整词标注;
纯假名词自身即读音, 不需标注。

输出: data/translations/furigana_map.json  {word: 标注串}
用法: python tools/furigana.py [--sample N]
"""
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / 'work'
KXML = ROOT / 'data' / 'kanjidic2.xml'
OUTJSON = ROOT / 'data' / 'translations' / 'furigana_map.json'

KANA = re.compile(r'[\u3041-\u30ffー・]')
KANJI = re.compile(r'[\u4e00-\u9fff々]')
NONJP = re.compile(r'[A-Za-z0-9Ａ-Ｚａ-ｚ０-９]')

DAKU = str.maketrans('かきくけこさしすせそたちつてとはひふへほ',
                     'がぎぐげござじずぜぞだぢづでどばびぶべぼ')
HANDAKU = str.maketrans('はひふへほ', 'ぱぴぷぺぽ')


def hira(s):
    return ''.join(chr(ord(c) - 96) if 'ァ' <= c <= 'ン' else c
                   for c in s)


def variants(v):
    """读音候选: 原形/连浊/半浊/促音变(つくちき→っ)。"""
    out = {v}
    if v:
        out.add(v[0].translate(DAKU) + v[1:])
        out.add(v[0].translate(HANDAKU) + v[1:])
        if v[-1] in 'つくちき':
            out.add(v[:-1] + 'っ')
    return {x for x in out if x}


def load_readings():
    """kanjidic2 -> {汉字: 候选读音集合(平文, 已去送假名点)}"""
    rd = {}
    for _, el in ET.iterparse(str(KXML), events=('end',)):
        if el.tag != 'character':
            continue
        ch = el.findtext('literal')
        cands = set()
        for r in el.iter('reading'):
            if r.get('r_type') not in ('ja_on', 'ja_kun'):
                continue
            v = (r.text or '').strip()
            if not v:
                continue
            v = v.split('.')[0]          # 训读词干 (食べる 的 た)
            v = re.sub(r'\(.*?\)', '', v)  # 去括注 あき(らか)
            v = hira(v)
            if v:
                cands.add(v)
        full = set()
        for v in cands:
            full |= variants(v)
        if ch:
            rd[ch] = full
        el.clear()
    return rd


def align(word, reading, rd):
    """把 reading 拆回 word 的每个字符。

    返回 [(char, kana_or_None), ...], kana=None 表示该字不需注音
    (假名/罗马字本身), 或拆解失败。三种模式:
      strict: 每个汉字逐一匹配 kanjidic2 读音
      group:  连续汉字段整体消费一段读音 (熟字训)
      None:   拆不开
    """
    reading = hira(reading)

    def strict(i, p, assign, prev_kanji):
        if i == len(word):
            return p == len(reading)
        c = word[i]
        if c == '々':
            for v in variants(prev_kanji or ''):
                if len(v) <= len(reading) - p and reading.startswith(v, p):
                    assign.append((c, v))
                    if strict(i + 1, p + len(v), assign, prev_kanji):
                        return True
                    assign.pop()
            return False
        if KANJI.match(c):
            for v in rd.get(c, ()):
                if len(v) <= len(reading) - p and reading.startswith(v, p):
                    assign.append((c, v))
                    if strict(i + 1, p + len(v), assign, c):
                        return True
                    assign.pop()
            return False
        if KANA.match(c) or c in '・':
            hc = hira(c)
            if p < len(reading) and reading[p] == hc:
                assign.append((c, None))
                if strict(i + 1, p + 1, assign, None):
                    return True
                assign.pop()
            return False
        # 罗马字等非日文字符: 不消费读音
        assign.append((c, None))
        if strict(i + 1, p, assign, None):
            return True
        assign.pop()
        return False

    def group(i, p, assign):
        if i == len(word):
            return p == len(reading)
        if KANJI.match(word[i]):
            j = i
            while j < len(word) and KANJI.match(word[j]):
                j += 1
            for take in range(1, len(reading) - p + 1):
                assign.append((word[i:j], reading[p:p + take]))
                if group(j, p + take, assign):
                    return True
                assign.pop()
            return False
        if KANA.match(word[i]) or word[i] in '・':
            if p < len(reading) and reading[p] == hira(word[i]):
                assign.append((word[i], None))
                if group(i + 1, p + 1, assign):
                    return True
                assign.pop()
            return False
        assign.append((word[i], None))
        if group(i + 1, p, assign):
            return True
        assign.pop()
        return False

    a1 = []
    if strict(0, 0, a1, None):
        return a1, 'strict'
    a2 = []
    if group(0, 0, a2):
        return a2, 'group'
    return None, None


def annotate(word, reading, rd):
    parts, mode = align(word, reading, rd)
    if parts is None:
        return f'{word}[{reading}]', 'whole'
    out = []
    for ch, k in parts:
        if k:
            out.append(f'{ch}[{k}]')
        else:
            out.append(ch)
    return ''.join(out), mode


def main():
    sample_n = 0
    if '--sample' in sys.argv:
        sample_n = int(sys.argv[sys.argv.index('--sample') + 1])
    need = {}
    for n in range(40):
        p = WORK / f'gen_words_{n:02d}.json'
        if p.exists():
            need.update(json.loads(p.read_text(encoding='utf-8')).items())
    rd = load_readings()
    print('kanjidic2 字数:', len(rd))

    furigana = {}
    stats = {'strict': 0, 'group': 0, 'whole': 0, 'skip_kana': 0}
    fails = []
    for w, v in need.items():
        reading = (v.get('reading') or '').strip()
        if not reading:
            if not KANJI.search(w):
                stats['skip_kana'] += 1   # 纯假名/罗马字词: 自身即读音
                continue
            reading = w                    # 兜底 (理论上不该发生)
        if not KANJI.search(w):
            stats['skip_kana'] += 1
            continue
        ann, mode = annotate(w, reading, rd)
        furigana[w] = ann
        stats[mode] += 1
        if mode == 'whole':
            fails.append(w)

    # 一致性校验: 逐字/整段模式下, 拼回的读音(括号内+词中假名)必须等于原读音
    bad = []
    for w, ann in furigana.items():
        parts, mode = align(w, need[w]['reading'], rd)
        if parts is None:
            continue   # 整词回退: 标注本身就是 word[reading], 恒一致
        rebuilt = ''.join(
            k if k else (c if KANA.match(c) else '')
            for c, k in parts)   # 罗马字等字符的读音在整段括号里, 不参与拼回
        if hira(rebuilt) != hira(need[w]['reading']):
            bad.append((w, ann, need[w]['reading']))
    print(f'词数 {len(need)} | 逐字拆解 {stats["strict"]} | '
          f'熟字训整段 {stats["group"]} | 整词回退 {stats["whole"]} | '
          f'纯假名跳过 {stats["skip_kana"]}')
    print(f'拼回校验不一致: {len(bad)}', bad[:5])
    OUTJSON.write_text(json.dumps(furigana, ensure_ascii=False, indent=1),
                       encoding='utf-8')
    print('->', OUTJSON)
    if sample_n:
        import random
        keys = random.sample(list(furigana), min(sample_n, len(furigana)))
        for k in keys:
            print(f'  {k} {need[k]["reading"]} -> {furigana[k]}')
        print('整词回退示例:')
        for k in fails[:15]:
            print(f'  {k} {need[k]["reading"]} -> {furigana[k]}')


if __name__ == '__main__':
    main()
