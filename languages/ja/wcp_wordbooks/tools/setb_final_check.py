# -*- coding: utf-8 -*-
"""Set B 交付终检: 词数/文件/音频/改名 四项核对。
用法: py setb_final_check.py
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'output'
VOCAB = Path.home() / 'AppData' / 'LocalLow' / 'WCP' / 'vocabulary'
PDIR = Path.home() / 'AppData' / 'LocalLow' / 'WCP' / 'wcp'
sys.stdout.reconfigure(encoding='utf-8')


def main():
    ok = True
    data = json.loads((OUT / 'setb_books.json').read_text(encoding='utf-8'))
    stats = data['meta']['stats']
    total = sum(stats.values())
    print(f'[1] 词书: {stats} 合计 {total}')

    import re
    INVALID = re.compile(r'[\\/:*?"<>|]')
    words = set()
    for rows in data['levels'].values():
        for r in rows:
            w = r['word'].strip()
            if w and not INVALID.search(w):
                words.add(w)

    m = json.loads((OUT / 'setb_audio_manifest.json').read_text(encoding='utf-8'))
    done = set(m['done'])
    missing = words - done
    print(f'[2] 音频: 可生成 {len(words)}, 已完成 {len(done & words)}, '
          f'缺失 {len(missing)}')
    if missing:
        print('    缺失样例:', sorted(missing)[:10])

    files = ['惯用句谚语.xlsx', '拟声拟态.xlsx', '四字熟语.xlsx',
             '高级词汇.xlsx', '商务敬语.xlsx', 'wcp_setb.db']
    missing_f = [f for f in files if not (PDIR / f).exists()]
    print(f'[3] persistentDataPath: '
          f'{"全部就绪" if not missing_f else "缺 " + str(missing_f)}')
    if missing_f:
        ok = False

    import sqlite3
    con = sqlite3.connect(PDIR / 'wcp_setb.db')
    n = con.execute('SELECT COUNT(*) FROM pron').fetchone()[0]
    con.close()
    print(f'[4] wcp_setb.db pron: {n} 词')

    r = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq wcp.exe'],
                       capture_output=True)
    out = (r.stdout or b'').decode('utf-8', errors='replace')
    running = 'wcp.exe' in out or 'wcp.exe' in (r.stdout or b'').decode(
        'gbk', errors='replace')
    print(f'[5] wcp.exe: {"运行中(改名待游戏关闭)" if running else "未运行"}')

    print('== 终检', '通过 ==' if (not missing and not missing_f) else '存在问题 ==')


if __name__ == '__main__':
    main()
