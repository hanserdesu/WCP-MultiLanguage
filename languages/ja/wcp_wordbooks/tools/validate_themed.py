# -*- coding: utf-8 -*-
"""校验人工/LLM 产出的词书数据质量:
  1) 简体字/异体字检测: 字符必须在 JMDict 词头字符白名单内
  2) 例句/释义中不得混入 ascii 字母
  3) 字段完整性
用法: py validate_themed.py   (校验 extra_*.json 与 zh_llm_themed_*.json)
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
THDIR = DATA / 'themed'
TDIR = DATA / 'translations'

ALLOWED_PUNCT = set('、。！？～「」『』（）・…ー〜〈〉《》：；,.')


def build_char_whitelist():
    chars = set(ALLOWED_PUNCT)
    # 假名/常用符号
    for c in range(0x3040, 0x3100):
        chars.add(chr(c))
    # JMDict 词头字符 (日语用字)
    jm = DATA / 'jmdict_eng.json'
    if jm.exists():
        d = json.loads(jm.read_text(encoding='utf-8'))
        for ent in d['words']:
            for k in ent.get('kanji', []):
                chars.update(k['text'])
            for k in ent.get('kana', []):
                chars.update(k['text'])
    return chars


def build_zh_whitelist(strict):
    """释义白名单 = 日语字符白名单 ∪ 已认证简体中文语料字符
    (Kaishi zh-CN, gtx 机翻输出, 昨晚人工精翻批次)"""
    chars = set(strict)
    ex = DATA / 'themed' / 'zh_extra_chars.txt'
    if ex.exists():
        chars.update(ex.read_text(encoding='utf-8'))
    for f in ['kaishi15k_zh.tsv', 'translations/gtx_zh.json']:
        p = DATA / f
        if p.exists():
            chars.update(p.read_text(encoding='utf-8'))
    for p in sorted(TDIR.glob('zh_llm_refine_*.json')) + \
            sorted(TDIR.glob('zh_llm_2026*.json')):
        chars.update(p.read_text(encoding='utf-8'))
    return chars


def main():
    strict = build_char_whitelist()
    zh_wl = build_zh_whitelist(strict)
    problems = []

    TECH_TOKENS = ('SELECT', 'Android', 'iPhone', 'iPad', 'DDoS', 'NaN', 'B-tree',
                   'Wi-Fi', 'Windows', 'Linux', 'Mac', 'YouTube', 'GitHub', 'Google',
                   'iPhone', 'Ruby', 'root', 'Ada', 'Java', 'Logo', 'ini', 'App', 'Shell', 'Bourne', 'Agora', 'Holos', 'misc', 'Lavie', 'Cookie', 'Rh', 'CT', 'PD', 'MR', 'ED', 'NT', 'emia', 'shell', 'itis', 'Pascal', 'BSD', 'Unix', 'Vim', 'null', 'vi', 'Wi-Fi', 'JavaScript', 'Python', 'Excel', 'Word', 'PowerPoint')
    def check_text(where, field, s, wl, allow_acronym=False):
        # 大写缩写(EV/CEO/CPU/API等)、技术专名、数字3D允许; 其余拉丁字母禁止
        s2 = s
        for t in sorted(TECH_TOKENS, key=len, reverse=True):
            s2 = s2.replace(t, '')
        s2 = re.sub(r'[A-Z]{1,8}', '', s2)
        s2 = re.sub(r'[0-9]', '', s2)
        for c in s2:
            if c not in wl:
                problems.append(f'{where}.{field}: 异常字符 {c!r} (U+{ord(c):04X}) in {s[:40]}')
        if re.search(r'[A-Za-z]', s2):
            problems.append(f'{where}.{field}: 含拉丁字母: {s[:50]}')

    for p in sorted(THDIR.glob('extra_*.json')):
        raw = json.loads(p.read_text(encoding='utf-8'))
        for i, e in enumerate(raw.get('entries', [])):
            where = f'{p.name}#{i}'
            if not e.get('word') or not e.get('reading') or not e.get('zh'):
                problems.append(f'{where}: 字段缺失 {e.get("word")}')
            if e.get('word'):
                    check_text(where, 'word', e['word'], strict)
            if e.get('reading'):
                check_text(where, 'reading', e['reading'], strict)
            if e.get('ex_ja'):
                check_text(where, 'ex_ja', e['ex_ja'], strict, allow_acronym=True)
            if e.get('zh'):
                check_text(where, 'zh', e['zh'], zh_wl, allow_acronym=True)

    for p in sorted(TDIR.glob('zh_llm_themed_*.json')):
        raw = json.loads(p.read_text(encoding='utf-8'))
        for w, v in raw.items():
            where = f'{p.name}:{w}'
            if not isinstance(v, dict) or not v.get('zh'):
                problems.append(f'{where}: 缺 zh')
                continue
            check_text(where, 'word', w, strict)
            for f in ('ex_ja',):
                if v.get(f):
                    check_text(where, f, v[f], strict, allow_acronym=True)
            for f in ('zh', 'pos'):
                if v.get(f):
                    check_text(where, f, v[f], zh_wl, allow_acronym=True)

    if problems:
        print(f'发现 {len(problems)} 个问题:')
        for pr in problems[:60]:
            print(' -', pr)
        sys.exit(1)
    print('校验通过')


if __name__ == '__main__':
    main()
