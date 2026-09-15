# -*- coding: utf-8 -*-
"""法语例句流水线: gen_words_NN.json (100词/块) -> gen_out_NN_Y.json (每批100词)。

子命令:
  list            未完成批次
  summary         总览
  check [all]     校验全部
  check-one NN Y  校验单批 (供生产代理自检)
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / 'work'

CJK_RE = re.compile(r'[\u4e00-\u9fff]')
BAD_IN_FR_RE = re.compile(r'[\u4e00-\u9fff\u3040-\u30ff{}_<>|*]|__')
LATIN4_RE = re.compile(r'[A-Za-z]{4,}')

# 词形无法用「原形/词干子串」覆盖的不规则词 (整词信任派; 派生动词按后缀规则)
IRREG_EXACT = {
    'être', 'avoir', 'aller', 'faire', 'dire', 'voir', 'savoir', 'pouvoir',
    'vouloir', 'venir', 'tenir', 'devoir', 'prendre', 'mettre', 'lire',
    'boire', 'vivre', 'suivre', 'connaître', 'connaitre', 'croire',
    'écrire', 'ecrire', 'naître', 'naitre', 'mourir', 'rire', 'plaire',
    'falloir', 'valoir', 'pleuvoir', 'envoyer', 'recevoir', 'apercevoir',
    'asseoir', 'se taire', 'taire', 'oeil', 'œil', 'travail', 'monsieur',
    'madame', 'mademoiselle', 'beau', 'bel', 'nouveau', 'nouvel', 'vieux',
    'vieil', 'frais', 'fraîche', 'frais', 'sec', 'sèche', 'doux', 'faux',
    'roux', 'fou', 'mou', 'tout', 'toute', 'tous',
}
IRREG_SUFFIX = ('tenir', 'venir', 'prendre', 'mettre', 'écrire', 'ecrire',
                'connaitre', 'naître', 'naitre', 'faire', 'devoir',
                'oyer', 'uyer', 'ayer', 'savoir', 'vouloir', 'pouvoir')


def norm(s: str) -> str:
    s = unicodedata.normalize('NFD', s.casefold())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return s.replace('œ', 'oe').replace('æ', 'ae')


def verb_stem(w: str):
    for suf in ('oir', 'er', 'ir', 're'):
        if w.endswith(suf) and len(w) - len(suf) >= 2:
            return w[:-len(suf)]
    return None


def word_hit(word: str, pos: str, all_text: str) -> bool:
    """词形是否出现: 原形子串 -> 不规则白名单(全词性) -> 动词词干。"""
    w = norm(word)
    if w in all_text:
        return True
    if word.strip().lower() in IRREG_EXACT:
        return True
    if pos.startswith('v'):
        wl = norm(word)
        if any(wl.endswith(s) for s in IRREG_SUFFIX):
            return True
        stem = verb_stem(w)
        if stem and len(stem) >= 3 and stem in all_text:
            return True
        return False
    return False


def chunk_file(n):
    return WORK / f'gen_words_{n:02d}.json'


def out_file(n, y):
    return WORK / f'gen_out_{n:02d}_{y}.json'


def parts():
    out = []
    files = sorted(WORK.glob('gen_words_*.json'))
    if not files:
        raise ValueError('No generation chunks found')
    numbers = [int(f.stem.rsplit('_', 1)[1]) for f in files]
    if numbers != list(range(len(numbers))):
        raise ValueError('Generation chunk sequence has gaps')
    for n in numbers:
        words = json.loads(chunk_file(n).read_text(encoding='utf-8'))
        for y in range(0, (len(words) + 99) // 100):
            out.append((n, y, words[y * 100:(y + 1) * 100]))
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
        seen_fr = set()
        ok_texts = []
        for it in items[:3]:
            fr = (it.get('fr') or '').strip()
            zh = (it.get('zh') or '').strip()
            if not fr:
                issues.append(f'{w}: fr为空')
                break
            if BAD_IN_FR_RE.search(fr):
                issues.append(f'{w}: fr含非法字符 {fr[:30]}')
                break
            last = fr.rstrip('\'"”’')
            if not last or last[-1] not in '.!?':
                issues.append(f'{w}: fr未以句号结尾 {fr[-15:]}')
                break
            if not zh or not CJK_RE.search(zh):
                issues.append(f'{w}: zh缺中文')
                break
            m = LATIN4_RE.search(zh)
            if m:
                issues.append(f'{w}: zh含拉丁词 {m.group()}')
                break
            if '（' in zh or '）' in zh or '(' in zh or ')' in zh:
                issues.append(f'{w}: zh含括号')
                break
            if fr in seen_fr:
                issues.append(f'{w}: fr重复')
                break
            seen_fr.add(fr)
            ok_texts.append(fr)
        if d.get(w):
            all_text = norm(' '.join(i.get('fr', '') for i in d[w]))
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
        sys.exit(1 if remain else 0)
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
            iss = check_slice(n, y, sl)
            tag = 'OK' if not iss else 'FAIL'
            if iss:
                bad += 1
            print(f'{out_file(n,y).name} {tag} {len(sl)}词'
                  + ('' if not iss else ' | ' + '; '.join(iss[:4])))
        print('FAIL 批次数:', bad)
        sys.exit(1 if bad else 0)
    print('unknown cmd')
    sys.exit(2)


if __name__ == '__main__':
    main()
