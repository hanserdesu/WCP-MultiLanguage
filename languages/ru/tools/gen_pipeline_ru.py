# -*- coding: utf-8 -*-
"""俄语例句流水线: gen_words_NN.json (100词/块) -> gen_out_NN_Y.json (每批100词)。

子命令:
  list            未完成批次
  summary         总览
  check [all]     校验全部
  check-one NN Y  校验单批 (供生产代理自检)
"""
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / 'work'

CJK_RE = re.compile(r'[\u4e00-\u9fff]')
# 俄语例句禁止: CJK/假名/拉丁词(3连)/JSON模板残留
BAD_IN_RU_RE = re.compile(r'[\u4e00-\u9fff\u3040-\u30ff{}_<>|*]|__|[A-Za-z]{3}')
CYR_RUN_IN_ZH_RE = re.compile(r'[а-яёА-ЯЁ]{2,}')
LATIN_IN_ZH_RE = re.compile(r'[A-Za-z]{4,}')

# 词形无法用「词干前缀子串」覆盖的异干/超不规则词形 -> 接受这些词干
IRREG_STEMS = {
    'идти': ['ид', 'ойд', 'ш', 'йд'],
    'пойти': ['пойд', 'ш', 'йд'],
    'прийти': ['прид', 'прий', 'ш', 'йд'],
    'зайти': ['зайд', 'ш', 'йд'],
    'найти': ['найд', 'най', 'ш', 'йд'],
    'уйти': ['уйд', 'уй', 'ш', 'йд'],
    'войти': ['войд', 'вой', 'ш', 'йд'],
    'выйти': ['выйд', 'вый', 'ш', 'йд'],
    'перейти': ['перейд', 'перей', 'ш', 'йд'],
    'сойти': ['сойд', 'сой', 'ш', 'йд'],
    'человек': ['челов', 'лю'],
    'ребёнок': ['ребён', 'ребен', 'дет'],
    'друг': ['друг', 'друж', 'друз'],
    'брать': ['бра', 'бер', 'бир', 'воз'],
    'взять': ['взя', 'воз', 'бер'],
    'мочь': ['мог', 'мож'],
}


def norm(s: str) -> str:
    return s.casefold().replace('ё', 'е')


def word_hit(word: str, pos: str, all_text: str) -> bool:
    """词形是否出现: 原形子串 -> 异干预备词干 -> 词干前缀 (1~4字尾缀剥离)。"""
    w = norm(word)
    if w in all_text:
        return True
    for stem in IRREG_STEMS.get(word, []):
        if norm(stem) in all_text:
            return True
    min_len = max(3, len(w) - 4)
    for cut in range(1, len(w) - min_len + 1):
        if w[:-cut] in all_text:
            return True
    return False


def chunk_file(n):
    return WORK / f'gen_words_{n:02d}.json'


def out_file(n, y):
    return WORK / f'gen_out_{n:02d}_{y}.json'


def parts():
    out = []
    n = 0
    while chunk_file(n).exists():
        words = json.loads(chunk_file(n).read_text(encoding='utf-8'))
        for y in range(0, (len(words) + 99) // 100):
            out.append((n, y, words[y * 100:(y + 1) * 100]))
        n += 1
    return out


def check_slice(n, y, sl):
    f = out_file(n, y)
    if not f.exists():
        return ['FILE_MISSING']
    try:
        d = json.loads(f.read_text(encoding='utf-8'))
    except Exception as e:
        return [f'JSON_ERROR: {e}']
    issues = []
    for meta in sl:
        w = meta['word']
        items = d.get(w)
        if not isinstance(items, list) or not items:
            issues.append(f'{w}: 缺失')
            continue
        if len(items) < 3:
            issues.append(f'{w}: {len(items)}/3条')
            continue
        seen_ru = set()
        for it in items[:3]:
            ru = (it.get('ru') or '').strip()
            zh = (it.get('zh') or '').strip()
            if not ru:
                issues.append(f'{w}: ru为空')
                break
            if BAD_IN_RU_RE.search(ru):
                issues.append(f'{w}: ru含非法字符 {ru[:30]}')
                break
            last = ru.rstrip('\'"”’')
            if not last or last[-1] not in '.!?':
                issues.append(f'{w}: ru未以句号结尾 {ru[-15:]}')
                break
            if not re.search(r'[а-яёА-ЯЁ]', ru):
                issues.append(f'{w}: ru不含西里尔字母')
                break
            if not zh or not CJK_RE.search(zh):
                issues.append(f'{w}: zh缺中文')
                break
            m = LATIN_IN_ZH_RE.search(zh) or CYR_RUN_IN_ZH_RE.search(zh)
            if m:
                issues.append(f'{w}: zh含外文 {m.group()}')
                break
            if '（' in zh or '）' in zh or '(' in zh or ')' in zh:
                issues.append(f'{w}: zh含括号')
                break
            if ru in seen_ru:
                issues.append(f'{w}: ru重复')
                break
            seen_ru.add(ru)
        if d.get(w):
            all_text = norm(' '.join(i.get('ru', '') for i in d[w]))
            if not word_hit(w, meta.get('pos', ''), all_text):
                issues.append(f'{w}: 词形未出现({meta.get("pos")})')
    return issues


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'summary'
    ps = parts()
    if cmd == 'list':
        for n, y, sl in ps:
            if not out_file(n, y).exists() or check_slice(n, y, sl):
                print(f'{n:02d} {y} {len(sl)}')
        sys.exit(0)
    if cmd == 'summary':
        done = 0
        remain = []
        total = 0
        for n, y, sl in ps:
            total += len(sl)
            iss = check_slice(n, y, sl)
            if not iss:
                done += len(sl)
            else:
                remain.append(f'{n:02d}_{y}')
        print(f'词块总词数 {total}, 达标 {done}, 剩余批次 {len(remain)}: '
              + ' '.join(remain[:40]))
        sys.exit(0)
    if cmd == 'check-one':
        n, y = int(sys.argv[2]), int(sys.argv[3])
        sl = next(s for nn, yy, s in ps if nn == n and yy == y)
        iss = check_slice(n, y, sl)
        if iss:
            print('FAIL')
            print('\n'.join(iss[:60]))
            sys.exit(1)
        print('PASS')
        sys.exit(0)
    if cmd == 'check':
        bad = 0
        for n, y, sl in ps:
            if not out_file(n, y).exists():
                continue
            iss = check_slice(n, y, sl)
            tag = 'OK' if not iss else 'FAIL'
            if iss:
                bad += 1
            print(f'{out_file(n,y).name} {tag} {len(sl)}词'
                  + ('' if not iss else ' | ' + '; '.join(iss[:4])))
        print('FAIL 批次数:', bad)
        sys.exit(0)
    print('unknown cmd')
    sys.exit(2)


if __name__ == '__main__':
    main()
