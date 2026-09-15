# -*- coding: utf-8 -*-
"""例句生成辅助工具 (3 条标准, 2026-09-10)

子命令:
  plan [n]          按词块列出「需补条数」, 生成补写作业清单
  fix NN Y          给已完成但不足 3 条的批次补写缺口 (调用方提供补丁)
  merge NN Y patch  把补丁 json 合并进 gen_out_NN_Y.json 并排序
  audit             全量审计: 每词条数分布 + 不达标明细

设计: 不自动生成内容, 只做「找缺口 / 合并 / 校验」的机械工作。
内容仍由生成方提供 (人或 LLM), 工具负责保证契约不变。
"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / 'work'
TARGET = 3


def out_file(n, y):
    return WORK / f'gen_out_{n:02d}_{y}.json'


def chunk_words(n):
    f = WORK / f'gen_words_{n:02d}.json'
    if not f.exists():
        return []
    return list(json.loads(f.read_text(encoding='utf-8')).items())


def batches():
    for n in range(40):
        ws = chunk_words(n)
        if not ws:
            continue
        for y in range(0, (len(ws) + 99) // 100):
            yield n, y, ws[y * 100:(y + 1) * 100]


def cmd_plan(n=None):
    """列出每个批次缺多少条。"""
    rows = []
    for nn, y, sl in batches():
        if n is not None and nn != n:
            continue
        f = out_file(nn, y)
        if not f.exists():
            rows.append((nn, y, len(sl) * TARGET, len(sl), 'NEW'))
            continue
        d = json.loads(f.read_text(encoding='utf-8'))
        gap = 0
        short = 0
        for w, _ in sl:
            items = d.get(w, [])
            if len(items) < TARGET:
                gap += TARGET - len(items)
                short += 1
        if gap:
            rows.append((nn, y, gap, short, 'PATCH'))
    tot_gap = sum(r[2] for r in rows)
    print(f'需处理批次 {len(rows)}, 需补例句 {tot_gap} 条')
    print(f'{"批次":<10}{"类型":<8}{"缺口":>6}{"涉及词":>8}')
    for nn, y, gap, short, kind in rows:
        print(f'{nn:02d}_{y:<7}{kind:<8}{gap:>6}{short:>8}')


def cmd_audit():
    """全量审计条数分布。"""
    dist = Counter()
    for nn, y, sl in batches():
        f = out_file(nn, y)
        if not f.exists():
            dist['文件缺失'] += len(sl)
            continue
        d = json.loads(f.read_text(encoding='utf-8'))
        for w, _ in sl:
            dist[len(d.get(w, []))] += 1
    print('每词条数分布:', dict(sorted(dist.items(), key=lambda x: str(x[0]))))


def cmd_merge(nn, y, patch_path):
    """把补丁合并进批次文件 (只追加缺口, 不覆盖已有)。"""
    f = out_file(nn, y)
    meta = dict(chunk_words(nn))
    order = [w for w, _ in chunk_words(nn)][y * 100:(y + 1) * 100]
    cur = json.loads(f.read_text(encoding='utf-8')) if f.exists() else {}
    patch = json.loads(Path(patch_path).read_text(encoding='utf-8'))
    added = 0
    for w, items in patch.items():
        if w not in meta:
            print(f'警告: {w} 不在块 {nn} 批次 {y} 中, 跳过')
            continue
        exist = cur.get(w, [])
        havetext = {i['ja'] for i in exist}
        for it in items:
            if len(cur.get(w, [])) >= TARGET:
                break
            if it['ja'] in havetext:
                continue
            exist.append(it)
            havetext.add(it['ja'])
            added += 1
        cur[w] = exist
    # 按块内顺序重排
    ordered = {w: cur[w] for w in order if w in cur}
    for w in cur:
        if w not in ordered:
            ordered[w] = cur[w]
    f.write_text(json.dumps(ordered, ensure_ascii=False, indent=1),
                 encoding='utf-8')
    print(f'已合并 {added} 条 -> {f.name}')
    short = [w for w in order if len(ordered.get(w, [])) < TARGET]
    print(f'仍不足 {TARGET} 条的词: {len(short)}', short[:10])


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    c = sys.argv[1]
    if c == 'plan':
        cmd_plan(int(sys.argv[2]) if len(sys.argv) > 2 else None)
    elif c == 'audit':
        cmd_audit()
    elif c == 'merge':
        cmd_merge(int(sys.argv[2]), int(sys.argv[3]), sys.argv[4])
    else:
        print('unknown:', c)


if __name__ == '__main__':
    main()
