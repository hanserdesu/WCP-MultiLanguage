# -*- coding: utf-8 -*-
"""主会话人工精选的紧凑辅助:
  view NN          -> 打印 work/cur_view_NN.txt: word|pos|rank (每行一词)
  make NN FILE     -> FILE(kept行: word<TAB>zh<TAB>level; drop行: word<TAB>-<TAB>drop:理由)
                      转成 work/cur_out_NN.json 并自检
"""
import json
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / 'work'


def view(nn):
    src = json.loads((WORK / f'cur_{int(nn):02d}.json').read_text(
        encoding='utf-8'))
    lines = [f"{w['word']}|{w['pos']}|{w['rank']}" for w in src]
    print('\n'.join(lines))


def make(nn, path):
    kept, drop = [], []
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split('\t')
        if len(parts) == 3 and parts[1] == '-':
            drop.append({'word': parts[0].strip(),
                         'reason': parts[2].split('drop:', 1)[1].strip()})
        elif len(parts) == 3:
            kept.append({'word': parts[0].strip(), 'zh': parts[1].strip(),
                         'level': parts[2].strip()})
        elif len(parts) == 2:
            kept.append({'word': parts[0].strip(), 'zh': parts[1].strip(),
                         'level': ''})
    out = WORK / f'cur_out_{int(nn):02d}.json'
    out.write_text(json.dumps({'kept': kept, 'drop': drop},
                              ensure_ascii=False, indent=1), encoding='utf-8')
    print('written', out.name, len(kept), 'kept', len(drop), 'drop')
    r = subprocess.run([sys.executable, str(ROOT / 'tools' /
                        'curate_pipeline.py'), 'check-one', str(int(nn))],
                       capture_output=True, text=True, encoding='utf-8')
    print(r.stdout[-1500:])
    if r.returncode != 0:
        sys.exit(1)


def main():
    cmd = sys.argv[1]
    if cmd == 'view':
        view(sys.argv[2])
    elif cmd == 'make':
        make(sys.argv[2], sys.argv[3])


if __name__ == '__main__':
    main()
