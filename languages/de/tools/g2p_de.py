# -*- coding: utf-8 -*-
"""规则式德语正字法 -> IPA (轻量 G2P, 无第三方依赖) v2。

规则覆盖: sch/tsch/ch(x|ç|k)/ig-ç/tion, ei/ai/eu/äu/au 双元音,
ie/aa/ee/oo/元音+h 长音, 首音节开音节长音, 非重读 e→ə, st-/sp- 送气,
z=ts, v=f, w=v, ß=s, qu=kv, 叠辅音合并, 词尾清化, -er=ɐ。
常见不规则词/借词用 EXCEPTIONS 覆盖。
"""
import re

EXCEPTIONS = {
    'der': 'deːɐ', 'die': 'diː', 'das': 'das', 'und': 'ʊnt', 'ist': 'ɪst',
    'ich': 'ɪç', 'nicht': 'nɪçt', 'mit': 'mɪt', 'von': 'fɔn', 'zum': 't͡sʊm',
    'zur': 't͡suːɐ', 'im': 'ɪm', 'am': 'am', 'ja': 'jaː', 'nein': 'naɪn',
    'wir': 'viːɐ', 'sie': 'ziː', 'er': 'eːɐ', 'es': 'ɛs', 'du': 'duː',
    'was': 'vas', 'wie': 'viː', 'wo': 'voː', 'wer': 'veːɐ', 'wen': 'veːn',
    'haben': 'haːbən', 'sein': 'zaɪn', 'werden': 'veːɐdən', 'wissen': 'vɪsən',
    'ihr': 'iːɐ', 'uns': 'ʊns', 'euch': 'ɔʏç', 'jeder': 'jeːdɐ',
    'jede': 'jeːdə', 'jedes': 'jeːdəs', 'jeden': 'jeːdən', 'oft': 'ɔft',
    'ob': 'ɔp', 'bis': 'bɪs', 'los': 'loːs', 'weg': 'vɛk', 'Weg': 'veːk',
    'mal': 'maːl', 'morgen': 'mɔʁɡən', 'Tee': 'teː', 'Kaffee': 'kafeː',
    'Café': 'kafeː', 'See': 'zeː', 'Media': 'miːdia', 'Junge': 'jʊŋə',
    'leise': 'laɪzə', 'Weise': 'vaɪzə', 'Minute': 'miˈnuːtə',
    'Buch': 'buːx', 'Bücher': 'byːçɐ', 'Buchstabe': 'buːxʃtaːbə',
    'Tuch': 'tuːx', 'Kuchen': 'kuːxən', 'suchen': 'zuːxən',
    'Student': 'ʃtuːdɛnt', 'Studenten': 'ʃtuːdɛntən',
    'Studium': 'ʃtuːdiʊm', 'studieren': 'ʃtuˈdiːʁən',
    'Wunder': 'vʊndɐ', 'hundert': 'hʊndɐt', 'Sonne': 'zɔnə',
}


def _collapse(w: str) -> str:
    """叠辅音合并 (ck/ch/sch 等组合除外, ss→ß 的音值处理放主循环)。"""
    out = []
    i = 0
    n = len(w)
    while i < n:
        c = w[i]
        two = w[i:i + 2]
        if two in ('ck', 'ch', 'pf', 'th', 'ph', 'qu', 'ei', 'ai', 'eu',
                   'au', 'ie', 'äu'):
            out.append(two)
            i += 2
            continue
        if two == 'ss':
            out.append('ß\u0001')
            i += 2
            continue
        if c in 'bdfgklmnprt' and i + 1 < n and w[i + 1] == c:
            out.append(c + '')
            i += 2
            continue
        out.append(c)
        i += 1
    return ''.join(out)


def _dev(word: str) -> str:
    """词尾清化: b→p d→t g→k (ig 结尾除外, ig→ç 单独处理)。"""
    if word.endswith('ig'):
        return word
    if word and word[-1] == 'b':
        return word[:-1] + 'p'
    if word and word[-1] == 'd':
        return word[:-1] + 't'
    if word and word[-1] == 'g':
        return word[:-1] + 'k'
    return word


LONG = {'a': 'aː', 'e': 'eː', 'i': 'iː', 'o': 'oː', 'u': 'uː',
        'ä': 'ɛː', 'ö': 'øː', 'ü': 'yː'}
SHORT = {'a': 'a', 'e': 'ɛ', 'i': 'ɪ', 'o': 'ɔ', 'u': 'ʊ',
         'ä': 'ɛ', 'ö': 'œ', 'ü': 'ʏ', 'y': 'ʏ'}
VOWELS = 'aeiouäöüy'


def to_ipa(word: str) -> str:
    word = word.strip()
    if word in EXCEPTIONS:
        return EXCEPTIONS[word]
    w = _dev(_collapse(word))
    low = w.lower()
    out = []
    i = 0
    n = len(low)
    vowels_seen = 0

    def is_v(j):
        return 0 <= j < n and low[j] in VOWELS

    while i < n:
        c = low[i]
        # --- 多字符组合 ---
        if low[i:i + 4] == 'tion':
            out.append('t͡sjoːn')
            i += 4
            continue
        if low[i:i + 4] == 'tial' or low[i:i + 4] == 'ziell':
            out.append('t͡sjaːl')
            i += 4
            continue
        if low[i:i + 4] == 'tsch':
            out.append('t͡ʃ')
            i += 4
            continue
        if low[i:i + 3] == 'sch':
            out.append('ʃ')
            i += 3
            continue
        if low[i:i + 3] == 'chs':
            out.append('ks')
            i += 3
            continue
        if low[i:i + 2] == 'ch':
            nxt = low[i + 2] if i + 2 < n else ''
            if i == 0 and nxt in 'aou':
                out.append('k')
            elif i > 0 and low[i - 1] in 'aou':
                out.append('x')
            else:
                out.append('ç')
            i += 2
            continue
        if low[i:i + 2] == 'ig' and i + 2 == n:
            out.append('ɪç')
            i += 2
            continue
        if low[i:i + 2] in ('pf', 'ph', 'ck', 'qu'):
            out.append({'pf': 'pf', 'ph': 'f', 'ck': 'k', 'qu': 'kv'}[
                low[i:i + 2]])
            i += 2
            continue
        if low[i:i + 2] == 'th':
            out.append('t')
            i += 2
            continue
        # --- 双元音 ---
        if low[i:i + 2] in ('ei', 'ai'):
            out.append('aɪ')
            i += 2
            vowels_seen += 1
            continue
        if low[i:i + 2] in ('eu', 'äu'):
            out.append('ɔʏ')
            i += 2
            vowels_seen += 1
            continue
        if low[i:i + 2] == 'au':
            out.append('aʊ')
            i += 2
            vowels_seen += 1
            continue
        if low[i:i + 2] == 'ie':
            if is_v(i + 2):
                out.append('i̯e')
            else:
                out.append('iː')
            i += 2
            vowels_seen += 1
            continue
        if low[i:i + 2] == 'aa':
            out.append('aː')
            i += 2
            vowels_seen += 1
            continue
        if low[i:i + 2] == 'ee':
            out.append('eː')
            i += 2
            vowels_seen += 1
            continue
        if low[i:i + 2] == 'oo':
            out.append('oː')
            i += 2
            vowels_seen += 1
            continue
        # --- 词尾组 (-er/-ern/-en/-el/-em/-es) ---
        if low[i:i + 3] == 'ern' and i + 3 == n:
            out.append('ɐn')
            i += 3
            continue
        if low[i:i + 2] == 'er' and i + 2 == n:
            out.append('ɐ')
            i += 2
            continue
        if low[i:i + 2] == 'en' and i + 2 == n:
            out.append('ən')
            i += 2
            continue
        if low[i:i + 2] == 'el' and i + 2 == n:
            out.append('əl')
            i += 2
            continue
        if low[i:i + 2] == 'em' and i + 2 == n:
            out.append('əm')
            i += 2
            continue
        if low[i:i + 2] == 'es' and i + 2 == n:
            out.append('əs')
            i += 2
            continue
        # --- 元音 + h 长音 ---
        if c in 'aeiouäöü' and i + 1 < n and low[i + 1] == 'h':
            out.append(LONG.get(c, c))
            i += 2
            vowels_seen += 1
            continue
        # --- 单元音 ---
        if c in 'aeiouäöü':
            vowels_seen += 1
            if c == 'e' and i == n - 1:
                out.append('ə')
                i += 1
                continue
            # 非首音节的 e 弱化 (后接辅音)
            if c == 'e' and vowels_seen > 1 and i + 1 < n and \
                    not is_v(i + 1):
                out.append('ə')
                i += 1
                continue
            # 开音节长音: 首音节 元音+单辅音+元音
            if i + 3 == n and low[i + 1:i + 3] == 'ch':
                out.append(LONG.get(c, c))
                i += 1
                continue
            if vowels_seen <= 1 and i + 2 < n and \
                    low[i + 1] in 'mnrlbdfgkpstvzß\u0001' and is_v(i + 2):
                out.append(LONG.get(c, c))
                i += 1
                continue
            # 词尾 元音+单辅音 → 长音 (Tag)
            if i + 2 == n and low[i + 1] not in VOWELS and \
                    low[i + 1] not in 'shx':
                out.append(LONG.get(c, c))
                i += 1
                continue
            out.append(SHORT.get(c, c))
            i += 1
            continue
        # --- 辅音 ---
        if low[i:i + 2] in ('st', 'sp') and i == 0:
            out.append('ʃ')
            i += 1
            continue
        if c == 'ß' or c == 'ss'[:2]:
            out.append('s')
            i += 1
            continue
        if c == 's':
            if i == 0 and low[i + 1:i + 2] and low[i + 1] not in VOWELS:
                out.append('s')
            elif i + 1 < n and is_v(i + 1):
                out.append('z')
            else:
                out.append('s')
            i += 1
            continue
        if low[i:i + 2] == 'tz':
            out.append('t͡s')
            i += 2
            continue
        if c == 'z':
            out.append('t͡s')
            i += 1
            continue
        if c == 'x':
            out.append('ks')
            i += 1
            continue
        if c == 'v':
            out.append('f')
            i += 1
            continue
        if c == 'w':
            out.append('v')
            i += 1
            continue
        if c == 'j':
            out.append('j')
            i += 1
            continue
        if c == 'r':
            if i == n - 1 and out and out[-1][-1] in 'aɑeɛiɪoɔuʊyʏøœː':
                out.append('ɐ')
            else:
                out.append('ʁ')
            i += 1
            continue
        if c == 'h':
            if i == 0 or low[i - 1] not in VOWELS:
                out.append('h')
            i += 1
            continue
        if c == 'c':
            out.append('k')
            i += 1
            continue
        if c == 'y':
            if i == 0:
                out.append('j')
            else:
                out.append('ʏ')
            i += 1
            continue
        if c == 'g':
            out.append('ɡ')
            i += 1
            continue
        if c == '':
            i += 1
            continue
        out.append(c)
        i += 1
    s = ''.join(out)
    s = re.sub(r'ɡ$', 'k', s)
    s = re.sub(r'b$', 'p', s)
    s = re.sub(r'd$', 't', s)
    return s
