# -*- coding: utf-8 -*-
"""语法讲解内容校验器。

校验 data/grammar/content/gc_*.json ( {gid: [[ja,zh]x3]} ) 对照
data/grammar/curriculum.json 的路线编号 (G001... 由 build_grammar_book 分配)。

规则 (每语法点 3 行):
  R1 结构: 3 行齐全; 第1行 zh 以「接续」起头, 第2行「用法」, 第3行「注意」
  R2 ja: 6~70 字; 以 。！？ 结尾; 无 ASCII 字母/数字; 无 ~ ～ 【】;
     每字符在 JMDict 日语用字白名单内 (绝不允许简体中文专用字);
     同点 3 句互不重复
  R3 zh: 1~60 字; 含汉字; ASCII 字母/数字不许; 假名只许出现在「」内
  R4 覆盖: 内容 gid 与路线 gid 完全一一对应 (缺/多都报)

用法: python tools/check_grammar_content.py [--stages 1,2]
退出码 0=全过, 1=有问题
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))

from validate_themed import build_char_whitelist  # noqa: E402
from build_grammar_book import build_route, load_content, load_curriculum  # noqa: E402

KANA = re.compile(r'[\u3040-\u30ff]')
FORBID_JA = re.compile(r'[A-Za-z0-9~〜【】～]')
END_OK = ('。', '！', '？')
PREFIX = ('接续', '用法', '注意')


def strip_kana_quotes(zh):
    return re.sub(r'「[^」]*」', '', zh)


def check_point(gid, name, rows, wl, errs):
    if not isinstance(rows, list) or len(rows) != 3:
        errs.append(f'{gid} {name}: 行数 {len(rows) if isinstance(rows, list) else "?"} ≠ 3')
        return
    jas = []
    for i, row in enumerate(rows):
        if not (isinstance(row, list) and len(row) == 2):
            errs.append(f'{gid} {name}: 第{i + 1}行不是 [ja, zh]')
            return
        ja, zh = row
        tag = f'{gid} {name} R{i + 1}'
        if not isinstance(ja, str) or not isinstance(zh, str):
            errs.append(f'{tag}: 类型错误')
            return
        if not 6 <= len(ja) <= 70:
            errs.append(f'{tag}: ja长度 {len(ja)}')
        if not ja.endswith(END_OK):
            errs.append(f'{tag}: ja结尾非。！？ -> …{ja[-4:]}')
        if FORBID_JA.search(ja):
            errs.append(f'{tag}: ja含 ASCII/波浪/【】')
        bad = [c for c in ja if c not in wl]
        if bad:
            errs.append(f'{tag}: ja含白名单外字符 {"".join(dict.fromkeys(bad))[:6]}')
        if not 1 <= len(zh) <= 60:
            errs.append(f'{tag}: zh长度 {len(zh)}')
        if not re.search(r'[\u4e00-\u9fff]', zh):
            errs.append(f'{tag}: zh无汉字')
        if re.search(r'[A-Za-z0-9]', zh):
            errs.append(f'{tag}: zh含 ASCII 字母/数字')
        outside = strip_kana_quotes(zh)
        if KANA.search(outside):
            # 允许「て形」等术语假名, 但整段日文(连续假名>=6)算违规
            runs = re.findall(r'[\u3040-\u30ff]{6,}', outside)
            if runs:
                errs.append(f'{tag}: zh含大段假名 {runs[0][:8]}')
        if not zh.startswith(PREFIX[i]):
            errs.append(f'{tag}: zh需以「{PREFIX[i]}」开头 -> {zh[:8]}')
        jas.append(ja)
    if len(set(jas)) != 3:
        errs.append(f'{gid} {name}: 3句 ja 有重复')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--stages', default='')
    args = ap.parse_args()
    stages = {int(x) for x in args.stages.split(',') if x.strip()}
    cur = load_curriculum(stages or None)
    content = load_content()
    route, _missing = build_route(cur, content, True)
    wl = build_char_whitelist()

    route_gids = {}
    for e in route:
        if e['kind'] == 'grammar':
            route_gids[e['gid']] = e['name']
    errs = []
    for gid, name in route_gids.items():
        rows = content.get(gid)
        if not rows:
            errs.append(f'{gid} {name}: 缺内容')
            continue
        check_point(gid, name, rows, wl, errs)
    extra = sorted(set(content) - set(route_gids))
    for g in extra:
        errs.append(f'{g}: 内容多于路线 (孤儿 gid, stages 过滤或编号错位)')

    n_ok = len(route_gids) - sum(1 for e in errs if e.split()[0] in route_gids
                                 and ('缺内容' in e or not e.split()[0]))
    print(f'路线语法点 {len(route_gids)}, 已有内容 {len(content) - len(extra)}, '
          f'问题 {len(errs)}')
    for e in errs[:80]:
        print(' ', e)
    if len(errs) > 80:
        print(f'  ... 其余 {len(errs) - 80} 条略')
    if extra:
        print('孤儿 gid:', ' '.join(extra))
    sys.exit(0 if not errs else 1)


if __name__ == '__main__':
    main()
