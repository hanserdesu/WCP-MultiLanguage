# -*- coding: utf-8 -*-
r"""重置 SaveFile.es3 中残留的跨词书测试队列 (清理遗留英语词)。

安全规范:
  1. 必须确认 wcp.exe 完全关闭
  2. 操作前自动创建带时间戳的完整备份
  3. 严格保留 Easy Save 3 JSON 的 __type 类型包装，防止损坏存档"""
import os
import sys
from pathlib import Path

from es3_safe import require_game_closed, write_values

sys.stdout.reconfigure(encoding='utf-8')

SAVE_FILE = Path(os.path.expanduser('~')) / 'AppData' / 'LocalLow' / 'WCP' / 'wcp' / 'SaveFile.es3'


def reset_stale_test():
    require_game_closed()

    if not SAVE_FILE.exists():
        print(f'存档不存在: {SAVE_FILE}')
        return False

    updates = {}

    def set_val(k, val, tname):
        updates[k] = (val, tname)

    set_val('testingIf_Para', False, 'bool')
    set_val('testingIf_CompleteIf', True, 'bool')
    set_val('S8Progress_Para', 0, 'int')
    set_val('S8LookBack_Para', 0, 'int')
    set_val('allTestWordsS10_Para', [], 'System.Collections.Generic.List`1[[System.String, mscorlib, Version=4.0.0.0, Culture=neutral, PublicKeyToken=b77a5c561934e089]],mscorlib')
    set_val('S8needToLearnWordList_Para', [], 'System.Collections.Generic.List`1[[System.String, mscorlib, Version=4.0.0.0, Culture=neutral, PublicKeyToken=b77a5c561934e089]],mscorlib')
    set_val('S8TestWordList_LearnedTest_left', [], 'System.Collections.Generic.List`1[[System.String, mscorlib, Version=4.0.0.0, Culture=neutral, PublicKeyToken=b77a5c561934e089]],mscorlib')
    set_val('S8TestWordList_LearnedTest_Finished', [], 'System.Collections.Generic.List`1[[System.String, mscorlib, Version=4.0.0.0, Culture=neutral, PublicKeyToken=b77a5c561934e089]],mscorlib')

    write_values(SAVE_FILE, updates)

    print('已成功重置残留测试状态: testingIf_Para=False, 队列已清空，下次进入将由 FrWordListMod 重新按法语已学词生成。')
    return True


if __name__ == '__main__':
    sys.exit(0 if reset_stale_test() else 1)
