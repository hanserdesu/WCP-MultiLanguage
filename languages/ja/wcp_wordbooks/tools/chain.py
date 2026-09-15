# -*- coding: utf-8 -*-
"""完整管线: build -> fixup -> merge(+write-game) -> 校验报告。
用法: py chain.py [--no-write]   默认含写入游戏 MyBook.es3
"""
import subprocess, sys, time
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent


def run(script, *args):
    r = subprocess.run([sys.executable, str(TOOLS / script), *args],
                       capture_output=True, text=True, encoding='utf-8',
                       errors='replace')
    out = (r.stdout or '') + (r.stderr or '')
    tail = '\n'.join(out.strip().splitlines()[-4:]) if out.strip() else ''
    print(f'--- {script} {" ".join(args)}\n{tail}', flush=True)
    if r.returncode != 0:
        raise RuntimeError(f'{script} failed: {out[-800:]}')
    return out


def main():
    t0 = time.time()
    run('build_books.py')
    run('fixup_words.py')
    if '--no-write' in sys.argv:
        run('merge_translations.py')
    else:
        run('merge_translations.py', '--write-game')
    print(f'== chain done in {time.time()-t0:.1f}s ==', flush=True)


if __name__ == '__main__':
    main()
