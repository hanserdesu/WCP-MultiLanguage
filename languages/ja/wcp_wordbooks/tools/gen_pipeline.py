# -*- coding: utf-8 -*-
"""例句生成流水线: gen_words_NN.json (词块) -> gen_out_NN_Y.json (每100词一批)。

子命令:
  list            列出尚未完成/不达标的批次 (chunk y n_words)
  summary         总览: 覆盖词数 / 剩余批次
  check [all]     校验全部已产出批次
  check-one NN Y  校验单个批次 (供生产代理自检)
"""
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / 'work'

sys.path.insert(0, str(ROOT / 'tools'))
import validate_themed as vt  # noqa: E402

CHAR_WL = vt.build_char_whitelist()
EXTRA_OK = set('0123456789%+-.·:/ '
               '０１２３４５６７８９％　＿')
KANA_RE = re.compile(r'[\u3040-\u30ff]')
CJK_RE = re.compile(r'[\u4e00-\u9fff]')

# 2026-09-10 新标准: 每个词一律 3 条例句 (原 need 字段 2/3 混用已废弃)。
# 词形匹配、白名单等其余规则不变。设 GEN_MIN=need 可临时回到旧行为。
import os  # noqa: E402
MIN_EXAMPLES = int(os.environ.get('GEN_MIN', '3'))


def chunk_file(n):
    return WORK / f'gen_words_{n:02d}.json'


def out_file(n, y):
    return WORK / f'gen_out_{n:02d}_{y}.json'


def parts():
    """[(n, y, words_slice, need_sum)]"""
    out = []
    for n in range(40):
        cf = chunk_file(n)
        if not cf.exists():
            continue
        words = list(json.loads(cf.read_text(encoding='utf-8')).items())
        for y in range(0, (len(words) + 99) // 100):
            sl = words[y * 100:(y + 1) * 100]
            out.append((n, y, sl, sum(v['need'] for _, v in sl)))
    return out


def check_slice(n, y, sl):
    """校验单个批次, 返回 issues 列表 (空=通过)。"""
    f = out_file(n, y)
    if not f.exists():
        return ['FILE_MISSING']
    try:
        d = json.loads(f.read_text(encoding='utf-8'))
    except Exception as e:
        return [f'JSON_ERROR: {e}']
    issues = []
    for w, meta in sl:
        items = d.get(w)
        if not isinstance(items, list) or not items:
            issues.append(f'{w}: 缺失')
            continue
        need = MIN_EXAMPLES
        if len(items) < need:
            issues.append(f'{w}: {len(items)}/{need}条')
        seen_ja = set()
        for it in items:
            ja, zh = it.get('ja', ''), it.get('zh', '')
            if not ja or not KANA_RE.search(ja) and not CJK_RE.search(ja):
                issues.append(f'{w}: ja为空')
                break
            last = ja.rstrip('」』）"\'')
            if not last or last[-1] not in '。！？':
                issues.append(f'{w}: ja未以句号结尾')
                break
            # 简体字/非法字符 (白名单 + ASCII数字等)
            bad = [c for c in ja if c not in CHAR_WL
                   and c not in EXTRA_OK and ord(c) > 0x2000]
            if bad:
                issues.append(f'{w}: ja含白名单外字符 {bad[:3]}')
                break
            if not zh or not CJK_RE.search(zh):
                issues.append(f'{w}: zh缺中文')
                break
            if KANA_RE.search(zh):
                issues.append(f'{w}: zh含假名')
                break
            if ja in seen_ja:
                issues.append(f'{w}: ja重复')
                break
            seen_ja.add(ja)
        # 用词检查: 词形或去掉末尾假名的词干必须出现
        if d.get(w):
            allja = ''.join(i['ja'] for i in d[w])
            variants = w.split('/')
            # 敬语前缀词 (御主人/お茶) 容忍无前缀词形
            for v in list(variants):
                s = re.sub(r'^[御おご]', '', v)
                if s != v:
                    variants.append(s)
            hit = any(v in allja for v in variants)
            if not hit:
                stem = variants[0][:-1]
                if len(stem) >= 1 and stem in allja:
                    hit = True
            if not hit:
                issues.append(f'{w}: 词形未出现(活用?)')
    return issues


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'summary'
    ps = parts()
    if cmd == 'list':
        for n, y, sl, ns in ps:
            f = out_file(n, y)
            if not f.exists():
                print(f'{n:02d} {y} {len(sl)}')
        sys.exit(0)
    if cmd == 'summary':
        done_words = 0
        total_words = sum(len(sl) for _, _, sl, _ in ps)
        remain = []
        for n, y, sl, _ in ps:
            iss = check_slice(n, y, sl)
            if not iss:
                done_words += len(sl)
            else:
                remain.append(f'{n:02d}_{y}')
        print(f'词块总词数 {total_words}, 达标词数 {done_words}, '
              f'剩余批次 {len(remain)}')
        if remain:
            print('剩余:', ' '.join(remain[:40]),
                  ('...' if len(remain) > 40 else ''))
        sys.exit(0)
    if cmd == 'check-one':
        n, y = int(sys.argv[2]), int(sys.argv[3])
        sl = next(s for nn, yy, s, _ in ps if nn == n and yy == y)
        iss = check_slice(n, y, sl)
        if iss:
            print('FAIL')
            print('\n'.join(iss[:60]))
            sys.exit(1)
        print('PASS')
        sys.exit(0)
    if cmd == 'check':
        bad = 0
        for n, y, sl, _ in ps:
            f = out_file(n, y)
            if not f.exists():
                continue
            iss = check_slice(n, y, sl)
            tag = 'OK' if not iss else 'FAIL'
            if iss:
                bad += 1
            print(f'{f.name} {tag} {len(sl)}词'
                  + ('' if not iss else ' | ' + '; '.join(iss[:5])))
        print('FAIL 批次数:', bad)
        sys.exit(0)
    print('unknown cmd')
    sys.exit(2)


if __name__ == '__main__':
    main()
