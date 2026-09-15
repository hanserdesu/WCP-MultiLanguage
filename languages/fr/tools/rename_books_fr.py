# -*- coding: utf-8 -*-
"""给自定义词书槽位 2 写法语书名昵称 (仅游戏关闭时执行)。

逆向结论 (复用日语项目): 书单里的书名 = "自定义词书N（" + SelfBookNameN + ")"。
昵称不参与槽位身份 (ChosenBook_Para 才是), 随便写安全。
槽位 1、3、4 的昵称原样保留。

  python tools/rename_books_fr.py            # 写入法语昵称
  python tools/rename_books_fr.py --restore  # 还原槽位2-4为默认
"""
import json
import sys
from pathlib import Path

from es3_safe import require_game_closed, write_values

sys.stdout.reconfigure(encoding='utf-8')

SAVE = Path.home() / 'AppData' / 'LocalLow' / 'WCP' / 'wcp' / 'SaveFile.es3'

NAMES = {
    'SelfBookName2': '法语词库(猫条版)',
}
DEFAULT2 = {'SelfBookName2': '空槽位'}


def main():
    require_game_closed()
    if not SAVE.exists():
        print('SaveFile.es3 不存在:', SAVE)
        return 1
    doc = json.loads(SAVE.read_text(encoding='utf-8-sig'))
    want = DEFAULT2 if '--restore' in sys.argv else NAMES
    changed = []
    for k, name in want.items():
        cur = (doc.get(k) or {}).get('value')
        if cur != name:
            doc[k] = {'__type': 'string', 'value': name}
            changed.append(f'{k}: {cur!r} -> {name!r}')
    if not changed:
        print('书名已是目标值:', '; '.join(f'{k}={v}' for k, v in want.items()))
        return 0
    write_values(SAVE, {k: (v, 'string') for k, v in want.items()})
    back = json.loads(SAVE.read_text(encoding='utf-8-sig'))
    ok = all((back.get(k) or {}).get('value') == v for k, v in want.items())
    n1 = (back.get('SelfBookName1') or {}).get('value')
    print('已写入书名昵称:', '; '.join(changed))
    print('已创建完整备份 | 回读校验:', 'PASS' if ok else 'FAIL',
          '| 槽位1昵称保留:', repr(n1))
    print('游戏内显示: 自定义词书二（法语词库(猫条版)）等')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
