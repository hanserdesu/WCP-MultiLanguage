# -*- coding: utf-8 -*-
"""批次调度 (子代理用): 领取任务 / 报告状态。

子命令:
  claim          领取下一个未完成的批次 (打印 NN Y 类型 词数)
  claim-block NN 领取某词块所有未完成批次
  status         全局状态一览
  batch NN Y     打印该批次的词表 (含 reading/meaning/level/need)
  done           列出已达标批次
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / 'work'
TARGET = 3


def out_file(n, y):
    return WORK / f'gen_out_{n:02d}_{y}.json'


def words(n):
    f = WORK / f'gen_words_{n:02d}.json'
    if not f.exists():
        return []
    return list(json.loads(f.read_text(encoding='utf-8')).items())


def batches(n=None):
    rng = [n] if n is not None else range(40)
    for nn in rng:
        ws = words(nn)
        if not ws:
            continue
        for y in range(0, (len(ws) + 99) // 100):
            yield nn, y, ws[y * 100:(y + 1) * 100]


def gap(nn, y, sl):
    """返回 (类型, 缺口条数, 已存在的词条数)"""
    f = out_file(nn, y)
    if not f.exists():
        return 'NEW', len(sl) * TARGET, 0
    d = json.loads(f.read_text(encoding='utf-8'))
    g = 0
    for w, _ in sl:
        it = d.get(w, [])
        if len(it) < TARGET:
            g += TARGET - len(it)
    return ('PATCH' if g else 'DONE'), g, len(sl)


def cmd_claim(n=None):
    for nn, y, sl in batches(n):
        kind, g, _ = gap(nn, y, sl)
        if kind != 'DONE':
            print(f'{nn:02d} {y} {kind} {g} {len(sl)}')
            return
    print('NONE')


def cmd_status():
    from collections import Counter
    c = Counter()
    detail = []
    for nn, y, sl in batches():
        kind, g, _ = gap(nn, y, sl)
        c[kind] += 1
        if kind != 'DONE':
            detail.append((nn, y, kind, g))
    print('批次状态:', dict(c))
    print('待处理明细:')
    for nn, y, kind, g in detail:
        print(f'  {nn:02d}_{y} {kind} 缺{g}条')


def cmd_batch(nn, y):
    sl = words(nn)[y * 100:(y + 1) * 100]
    f = out_file(nn, y)
    exist = {}
    if f.exists():
        exist = json.loads(f.read_text(encoding='utf-8'))
    for w, v in sl:
        have = len(exist.get(w, []))
        flag = '' if have >= TARGET else f'  <<< 需补{TARGET-have}条'
        print(f'{w}\t{v["reading"]}\t{v["meaning"]}\t{v["level"]}\t已有{have}{flag}')


def main():
    c = sys.argv[1] if len(sys.argv) > 1 else 'status'
    if c == 'claim':
        cmd_claim(int(sys.argv[2]) if len(sys.argv) > 2 else None)
    elif c == 'status':
        cmd_status()
    elif c == 'batch':
        cmd_batch(int(sys.argv[2]), int(sys.argv[3]))
    elif c == 'done':
        for nn, y, sl in batches():
            kind, g, _ = gap(nn, y, sl)
            if kind == 'DONE':
                print(f'{nn:02d}_{y}')
    else:
        print(__doc__)


if __name__ == '__main__':
    main()
