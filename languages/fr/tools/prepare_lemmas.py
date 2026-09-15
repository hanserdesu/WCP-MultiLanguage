# -*- coding: utf-8 -*-
"""Lexique383.tsv -> data/lemmas_ranked.json

从 Lexique 3.83 (lexique.org, CC-BY) 提取按字幕频率排序的法语词元表:
  {word, ipa, pos, genre, freq, rank}
- 词元聚合: lemme 分组, freq = max(freqlemfilms2), cgram/genre/phon 取最高频行
- 过滤: 纯数字/含数字/单字母(保留 y, à)/纯专名(仅大写形式出现专名、无小写行)剔除
- 音标: Lexique phon 记号 -> IPA (phon_map), 转换失败的词标 ipa='' 由 LLM 兜底
"""
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'data' / 'raw' / 'Lexique383.tsv'
DST = ROOT / 'data' / 'lemmas_ranked.json'
TOP_N = 8600

# Lexique phon 记号 -> IPA (实测校验: anglais @glE/anglɛ̃→ɑ̃, de d°→də,
# bon b§→bɔ̃, vin v5→vɛ̃, deux d2→dø, oeuf 9f→œf, huit 8it→ɥit,
# oignon ON§→ɔɲɔ̃ (N=ɲ), bingo biGo→biŋgo (G=ŋ))
PHON_MAP = {
    '@': 'ɑ̃', '§': 'ɔ̃', '5': 'ɛ̃', '1': 'œ̃', '2': 'ø', '9': 'œ',
    '8': 'ɥ', 'E': 'ɛ', 'O': 'ɔ', 'R': 'ʁ', 'S': 'ʃ', 'Z': 'ʒ',
    'N': 'ɲ', 'G': 'ŋ', '°': 'ə',
}
IPA_OK = re.compile(
    r'^[abdfghjklmnoprstuvwxzæøœɛəɑɔ̃ɛ̃œ̃øɥʃʒŋɲʁyieayo\-.\' ]*$')

POS_LABEL = {
    'NOM': 'n', 'VER': 'v', 'ADJ': 'adj', 'ADV': 'adv', 'PRO': 'pron',
    'PRE': 'prép', 'CON': 'conj', 'DET': 'det', 'ART': 'art',
    'INTER': 'interj', 'ONO': 'onoma', 'NUM': 'num', 'AUX': 'aux',
}


def phon_to_ipa(phon: str) -> str:
    if not phon:
        return ''
    out = []
    for ch in phon:
        out.append(PHON_MAP.get(ch, ch))
    ipa = ''.join(out)
    # 词典记号里残留的非常规字符视为转换失败
    if not IPA_OK.match(ipa):
        return ''
    return ipa


def main():
    rows = list(csv.DictReader(SRC.open(encoding='utf-8', errors='replace'),
                               delimiter='\t'))
    # 先按词元聚合所有行, 音标/词性一律取「词元本形行」(ortho==lemme, islem=1);
    # 屈折行与词元行 freqlemfilms2 相同, 若按频率挑行会随机拿到 est/suis 等形式的音标
    groups = defaultdict(list)
    for r in rows:
        lem = (r.get('lemme') or '').strip()
        if not lem:
            continue
        try:
            freq = float(r.get('freqlemfilms2') or 0)
        except ValueError:
            freq = 0.0
        if freq <= 0:
            continue
        groups[lem.lower()].append((freq, lem, r))

    lemmas = {}
    for key, grows in groups.items():
        freq = max(g[0] for g in grows)
        lem_rows = [g for g in grows if g[1] == key and g[2].get('islem') == '1']
        # 多词性词元 (aller 名/动) 取最高频的词性行
        pick = (max(lem_rows, key=lambda g: g[0]) if lem_rows
                else max(grows, key=lambda g: g[0]))[2]
        lemmas[key] = {
            'freq': freq, 'lemme': pick['lemme'],
            'cgram': pick.get('cgram') or '', 'genre': pick.get('genre') or '',
            'phon': pick.get('phon') or '',
        }
    out = []
    for key, v in lemmas.items():
        lem = v['lemme']
        if not re.search(r'[a-zA-Zàâäéèêëîïôöùûüçœæ]', lem, re.I):
            continue  # 纯数字/符号
        if re.search(r'\d', lem):
            continue
        if len(lem) == 1 and lem not in ('y', 'à', 'a'):
            continue
        # 专名过滤: Lexique 普通词元一律小写, 首字母大写即专名/缩写 (Paris/SNCF)
        if lem[0].isupper():
            continue
        ipa = phon_to_ipa(v['phon'])
        pos = POS_LABEL.get(v['cgram'].split(':')[0], v['cgram'].lower())
        if v['cgram'].startswith('NOM') and v['genre'] in ('m', 'f'):
            pos = f"n.{v['genre']}"
        out.append({
            'word': lem, 'ipa': ipa, 'pos': pos,
            'freq': round(v['freq'], 1),
        })
    out.sort(key=lambda x: -x['freq'])
    for i, w in enumerate(out):
        w['rank'] = i + 1
    out = out[:TOP_N]
    DST.write_text(json.dumps(out, ensure_ascii=False, indent=0),
                   encoding='utf-8')
    no_ipa = sum(1 for w in out if not w['ipa'])
    print(f'词元 {len(out)} (TOP {TOP_N}), 无IPA {no_ipa}')
    for w in out[:15]:
        print(' ', w['word'], w['ipa'], w['pos'], w['freq'])
    print('  ...')
    for w in out[-5:]:
        print(' ', w['word'], w['ipa'], w['pos'], w['freq'])


if __name__ == '__main__':
    main()
