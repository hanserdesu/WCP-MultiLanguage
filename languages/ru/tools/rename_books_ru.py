# -*- coding: utf-8 -*-
"""给自定义词书槽位 3/4 写俄语书名昵称 (仅游戏关闭时执行)。

逆向结论 (复用日语项目): 书单里的书名 = "自定义词书N（" + SelfBookNameN + ")"。
昵称不参与槽位身份 (ChosenBook_Para 才是), 随便写安全。
槽位 1 (日语) / 槽位 2 (法语) 的昵称原样保留。

  python tools/rename_books_ru.py            # 写入俄语昵称
  python tools/rename_books_ru.py --restore  # 还原槽位3/4为默认
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

SAVE = Path.home() / 'AppData' / 'LocalLow' / 'WCP' / 'wcp' / 'SaveFile.es3'

NAMES = {
    'SelfBookName3': '俄语词库(猫条版)',
    'SelfBookName4': '空槽位',
}
DEFAULT = {'SelfBookName3': '空槽位', 'SelfBookName4': '空槽位'}


def game_running():
    tasklist = 'tasklist'
    sys32 = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32' / 'tasklist.exe'
    if sys32.exists():
        tasklist = str(sys32)
    try:
        r = subprocess.run([tasklist, '/FI', 'IMAGENAME eq wcp.exe'],
                           capture_output=True, text=True, encoding='gbk',
                           errors='replace')
        return 'wcp.exe' in (r.stdout or '').lower()
    except Exception:
        return False


def main():
    if game_running():
        print('wcp.exe 正在运行, 跳过(避免存档被覆盖)')
        return 1
    if not SAVE.exists():
        print('SaveFile.es3 不存在:', SAVE)
        return 1
    doc = json.loads(SAVE.read_text(encoding='utf-8-sig'))
    want = DEFAULT if '--restore' in sys.argv else NAMES
    changed = []
    for k, name in want.items():
        cur = (doc.get(k) or {}).get('value')
        if cur != name:
            doc[k] = {'__type': 'string', 'value': name}
            changed.append(f'{k}: {cur!r} -> {name!r}')
    if not changed:
        print('书名已是目标值:', '; '.join(f'{k}={v}' for k, v in want.items()))
        return 0
    bak = SAVE.with_suffix(f'.es3.bak_{time.strftime("%Y%m%d_%H%M%S")}')
    shutil.copy2(SAVE, bak)
    SAVE.write_text(json.dumps(doc, ensure_ascii=False, indent=1),
                    encoding='utf-8')
    back = json.loads(SAVE.read_text(encoding='utf-8-sig'))
    ok = all((back.get(k) or {}).get('value') == v for k, v in want.items())
    n1 = (back.get('SelfBookName1') or {}).get('value')
    n2 = (back.get('SelfBookName2') or {}).get('value')
    print('已写入书名昵称:', '; '.join(changed))
    print('备份:', bak.name, '| 回读校验:', 'PASS' if ok else 'FAIL',
          '| 槽位1昵称保留:', repr(n1), '| 槽位2昵称保留:', repr(n2))
    print('游戏内显示: 自定义词书三（俄语词库(猫条版)）')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
