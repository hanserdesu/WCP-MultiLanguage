# -*- coding: utf-8 -*-
"""给四个自定义词书槽位写上「署名」昵称 (仅游戏关闭时执行)。

逆向结论 (AddElementsToScrollView:180 / WordChooseButtonS10:1042):
  书单里的书名 = "自定义词书一（" + SelfBookName1 + ")" —— 括号里那段就是
  游戏留给玩家自定义的**昵称/署名**, 由 SaveFile.es3 的 SelfBookName1..4 驱动。
  昵称**不影响**槽位身份: 学习/查词走的是 ChosenBook_Para(
  "自定义词书一".."四") + MyBook.es3 的 SelfBookList1..4, 与昵称无关。
  所以写昵称安全; 但昵称留成槽位名时游戏里只会显示
  「自定义词书一（自定义词书一）」, 正是要避免的。

本脚本: 把署名写进昵称。配合 mod_book_name 插件 (把前缀显示成「日语词书N」),
游戏里显示为:
  日语词书一（猫条）
夜班工人 (night_worker / setb_worker / auto_worker) 会调用它, 保持署名生效。

  python tools/rename_books.py            # 昵称 = 猫条
  python tools/rename_books.py --detail   # 昵称 = 猫条·JLPT N2 (带词书信息)
  python tools/rename_books.py --restore  # 还原默认空昵称(旧行为)
"""
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

SAVE = Path.home() / 'AppData' / 'LocalLow' / 'WCP' / 'wcp' / 'SaveFile.es3'

# 署名 (想换名字只改这一行)
AUTHOR = '猫条'

# 各槽位的词书内容 (与 README「槽位规划」一致; 词数由 MyBook.es3
# SelfBookList1..4 核对: 1293 / 1784 / 1791 / 3463)。--detail 时拼到署名后。
DETAIL = {
    'SelfBookName1': 'JLPT初级 N5+N4',
    'SelfBookName2': 'JLPT N3',
    'SelfBookName3': 'JLPT N2',
    'SelfBookName4': 'JLPT N1',
}

DEFAULT = {'SelfBookName1': '自定义词书一', 'SelfBookName2': '自定义词书二',
           'SelfBookName3': '自定义词书三', 'SelfBookName4': '自定义词书四'}


def target_names():
    if '--restore' in sys.argv:
        return dict(DEFAULT)
    if '--detail' in sys.argv:
        return {k: f'{AUTHOR}·{v}' for k, v in DETAIL.items()}
    return {k: AUTHOR for k in DETAIL}


def game_running():
    r = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq wcp.exe'],
                       capture_output=True, text=True, encoding='gbk',
                       errors='replace')
    return 'wcp.exe' in (r.stdout or '')


def main():
    if game_running():
        print('wcp.exe 正在运行, 跳过(避免存档被覆盖)')
        return 1
    if not SAVE.exists():
        print('SaveFile.es3 不存在:', SAVE)
        return 1
    doc = json.loads(SAVE.read_text(encoding='utf-8-sig'))
    want = target_names()
    changed = []
    for k, name in want.items():
        cur = (doc.get(k) or {}).get('value')
        if cur != name:
            doc[k] = {'__type': 'string', 'value': name}
            changed.append(f'{k}: {cur!r} -> {name!r}')
    if not changed:
        print('书名已是目标值, 无需修改:',
              '; '.join(f'{k}={v}' for k, v in want.items()))
        return 0
    bak = SAVE.with_suffix(f'.es3.bak_{time.strftime("%Y%m%d_%H%M%S")}')
    shutil.copy2(SAVE, bak)
    SAVE.write_text(json.dumps(doc, ensure_ascii=False, indent=1),
                    encoding='utf-8')
    back = json.loads(SAVE.read_text(encoding='utf-8-sig'))
    ok = all((back.get(k) or {}).get('value') == v for k, v in want.items())
    print('已写入书名昵称:', '; '.join(changed))
    print('备份:', bak.name, '| 回读校验:', 'PASS' if ok else 'FAIL')
    print('游戏内显示示例: 自定义词书一（%s）' % want['SelfBookName1'])
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
