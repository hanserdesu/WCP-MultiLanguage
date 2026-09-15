# -*- coding: utf-8 -*-
"""德语例句流水线: gen_words_NN.json (100词/块) -> gen_out_NN_0.json。

子命令:
  list            未完成批次
  summary         总览
  check [all]     校验全部
  check-one NN Y  校验单批

gen_out_NN_Y.json 格式: {word: [{"de": ..., "zh": ...} x 3]}
校验规则 (对标 IMPLEMENTATION.md 阶段4):
  1. 每词恰好 3 条
  2. de 以 . ! ? 结尾
  3. de 无中日韩字符/花括号/模板残留
  4. zh 为中文, 不含 ≥4 连续拉丁字母 (德语词漂移拦截)
  5. 同词 de 不重复
  6. 词的某种自然形式必须字面出现 (原形/去屈折词干, 大小写不敏感,
     变音符折叠 ä→a ö→o ü→u ß→ss)
"""
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / 'work'

CJK_RE = re.compile(r'[\u4e00-\u9fff]')
BAD_IN_DE_RE = re.compile(r'[\u4e00-\u9fff\u3040-\u30ff{}_<>|*]|__')
LATIN4_RE = re.compile(r'[A-Za-zäöüÄÖÜß]{4,}')


def norm(s: str) -> str:
    s = s.casefold()
    for a, b in (('ä', 'a'), ('ö', 'o'), ('ü', 'u'), ('ß', 'ss')):
        s = s.replace(a, b)
    return s


def verb_stem(w: str):
    """动词词干: 去词尾 -eln/-ern/-en/-n; 可再加 e。"""
    for suf in ('eln', 'ern', 'en', 'n'):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            return w[:-len(suf)]
    return None


def word_hit(word: str, pos: str, all_text: str) -> bool:
    w = norm(word)
    if w in all_text:
        return True
    if pos.startswith('v'):
        stem = verb_stem(w)
        if stem and len(stem) >= 3 and stem in all_text:
            return True
        # 可分动词: anrufen -> ruf ... an / angerufen: 前缀剥离再试
        for pre in ('an', 'auf', 'aus', 'ab', 'ein', 'mit', 'vor', 'zu',
                    'zurück', 'weg', 'her', 'hin', 'los', 'fern', 'über',
                    'unter', 'heim', 'rein', 'raus', 'aufs', 'fest'):
            if w.startswith(pre) and len(w) - len(pre) >= 4:
                base = w[len(pre):]
                stem = verb_stem(base)
                if stem and len(stem) >= 3 and stem in all_text:
                    return True
                if base in all_text:
                    return True
    if pos.startswith('n') or pos.startswith('adj'):
        # 名词/形容词去尾 (复数 -e/-er/-en/-n/-s, 阴性 -in)
        for suf in ('nen', 'en', 'er', 'e', 'n', 's'):
            if w.endswith(suf) and len(w) - len(suf) >= 4 and \
                    w[:-len(suf)] in all_text:
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
        seen_de = set()
        ok_texts = []
        for it in items[:3]:
            de = (it.get('de') or '').strip()
            zh = (it.get('zh') or '').strip()
            if not de:
                issues.append(f'{w}: de为空')
                break
            if BAD_IN_DE_RE.search(de):
                issues.append(f'{w}: de含非法字符 {de[:30]}')
                break
            last = de.rstrip('\'"”’')
            if not last or last[-1] not in '.!?':
                issues.append(f'{w}: de未以句号结尾 {de[-15:]}')
                break
            if not zh or not CJK_RE.search(zh):
                issues.append(f'{w}: zh缺中文')
                break
            m = LATIN4_RE.search(zh)
            if m:
                issues.append(f'{w}: zh含拉丁词 {m.group()}')
                break
            if de in seen_de:
                issues.append(f'{w}: de重复')
                break
            seen_de.add(de)
            ok_texts.append(de)
        if d.get(w):
            all_text = norm(' '.join(i.get('de', '') for i in d[w]))
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
