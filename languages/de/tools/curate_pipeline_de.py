# -*- coding: utf-8 -*-
"""德语精选流水线: work/cand_NN.json -> work/cur_out_NN.json (主会话直写)。

子命令:
  list            未完成块
  summary         总览
  check [all]     校验全部
  check-one NN    校验单块

cur_out_NN.json 格式:
{
  "kept": [{"word": "hat", "lemma": "haben", "zh": "有", "level": "a1", "pos": "v."}, ...],
  "drop": [{"word": "aeaeae", "reason": "乱码"}]
}
- word 必须与输入词形完全一致; lemma 可省略 (=word)。
- 同一 lemma 跨块重复由 merge 阶段去重 (首见/最高频优先)。
"""
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / 'work'

CJK_RE = re.compile(r'[\u4e00-\u9fff]')
LATIN_WORD_RE = re.compile(r'[a-zA-ZäöüßÄÖÜ]{4,}')
MAX_DROP = 0.60
LEVELS = {'a1', 'a2', 'b1', 'b2'}
POS_OK = {'v.', 'n.', 'n.m.', 'n.f.', 'adj.', 'adv.', 'präp.', 'pron.',
          'konj.', 'num.', 'interj.', 'art.', 'phr.'}


def chunk_file(n):
    return WORK / f'cand_{n:02d}.json'


def out_file(n):
    return WORK / f'cur_out_{n:02d}.json'


def n_chunks():
    n = 0
    while chunk_file(n).exists():
        n += 1
    return n


def check_chunk(n):
    src = json.loads(chunk_file(n).read_text(encoding='utf-8'))
    words = [w['word'] for w in src]
    wset = set(words)
    f = out_file(n)
    if not f.exists():
        return ['FILE_MISSING']
    try:
        d = json.loads(f.read_text(encoding='utf-8'))
    except Exception as e:
        return [f'JSON_ERROR: {e}']
    kept = d.get('kept')
    drop = d.get('drop')
    dedup = d.get('dedup') or []
    if not isinstance(kept, list) or not isinstance(drop, list) or not isinstance(dedup, list):
        return ['kept/drop 字段缺失']
    issues = []
    seen = {}
    for it in kept:
        w = it.get('word')
        if w not in wset:
            issues.append(f'{w}: 不在输入中')
            continue
        if w in seen:
            issues.append(f'{w}: 重复出现')
            continue
        seen[w] = True
        zh = (it.get('zh') or '').strip()
        if not zh or not CJK_RE.search(zh):
            issues.append(f'{w}: zh缺中文')
            continue
        if len(zh) > 40:
            issues.append(f'{w}: zh过长')
            continue
        if LATIN_WORD_RE.search(zh):
            issues.append(f'{w}: zh含拉丁词 {zh[:20]}')
            continue
        if it.get('level') not in LEVELS:
            issues.append(f'{w}: level非法 {it.get("level")}')
        if it.get('pos') not in POS_OK:
            issues.append(f'{w}: pos非法 {it.get("pos")}')
        lemma = it.get('lemma') or w
        if not lemma or len(lemma) > 60:
            issues.append(f'{w}: lemma非法')
    for it in drop:
        w = it.get('word')
        if w not in wset:
            issues.append(f'drop {w}: 不在输入中')
            continue
        if w in seen:
            issues.append(f'{w}: kept/drop重复')
            continue
        seen[w] = True
        if not (it.get('reason') or '').strip():
            issues.append(f'drop {w}: 无理由')
    for it in dedup:
        w = it.get('word')
        if w not in wset:
            issues.append(f'dedup {w}: 不在输入中')
            continue
        if w in seen:
            issues.append(f'{w}: 重复出现')
            continue
        seen[w] = True
    missing = [w for w in words if w not in seen]
    if missing:
        issues.append(f'{len(missing)}词未处理: {missing[:8]}')
    if len(drop) > len(words) * MAX_DROP:
        issues.append(f'drop过多 {len(drop)}/{len(words)}')
    return issues


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'summary'
    total = n_chunks()
    if cmd == 'list':
        for n in range(total):
            f = out_file(n)
            if not f.exists() or check_chunk(n):
                print(n)
        sys.exit(0)
    if cmd == 'summary':
        done = 0
        remain = []
        for n in range(total):
            iss = check_chunk(n)
            if not iss:
                done += 1
            else:
                remain.append(str(n))
        print(f'共 {total} 块, 完成 {done}, 剩余 {len(remain)}: '
              + ' '.join(remain[:40]))
        sys.exit(0)
    if cmd == 'check-one':
        n = int(sys.argv[2])
        iss = check_chunk(n)
        if iss:
            print('FAIL')
            print('\n'.join(iss[:60]))
            sys.exit(1)
        print('PASS')
        sys.exit(0)
    if cmd == 'check':
        bad = 0
        for n in range(total):
            iss = check_chunk(n)
            tag = 'OK' if not iss else 'FAIL'
            if iss:
                bad += 1
            print(f'{n:02d} {tag}'
                  + ('' if not iss else ' | ' + '; '.join(iss[:5])))
        print('FAIL 块数:', bad)
        sys.exit(0)
    print('unknown cmd')
    sys.exit(2)


if __name__ == '__main__':
    main()
