# -*- coding: utf-8 -*-
"""把法语词的发音 mp3 从共享 vocabulary/ 隔离到 fr_word_audio/ (mod 专用)。

vocabulary/<word>.mp3 是游戏所有词书共用的查词发音目录。法语词形是拉丁字母,
其中 1638 个与内置英语词同形 (table/zoom/vote/…), 音頻留在共享目录会被
其它词书读到。因此法语词音频放私有目录
%USERPROFILE%\\AppData\\LocalLow\\WCP\\wcp\\fr_word_audio\\, 只由
FrWordListMod 拦截 VocabularyAudioPlayer.PlayWordAudio 播放。

实际执行结果 (2026-09-14): 全部 8,116 个法语词音频都已从 vocabulary/
移入 fr_word_audio/ (vocabulary/ 现存 16,312 个文件全部属于日语词书)。
gen_word_audio.py 现已直接生成到 fr_word_audio/, 本脚本只在下述情况需要:

用法: python tools/isolate_word_audio_fr.py [--restore]
  --restore 把 fr_word_audio/ 里的 mp3 移回 vocabulary/ (撤销隔离,
            会让 1638 个同形词重新污染共享目录, 仅用于回滚)
"""
import json
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
# tools/deprecated/ 下: 上一级是 tools/ (放 wcp_paths / audio_paths_fr),
# 项目根目录要再上一层 —— 原实现取 parent.parent 得到 tools/, 永远找不到
# output/french_books.json, 脚本从未真正跑起来过。
TOOLS = Path(__file__).resolve().parent.parent
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))
from audio_paths_fr import native_path, word_audio_dir

VOCAB = Path.home() / 'AppData' / 'LocalLow' / 'WCP' / 'vocabulary'
# 必须与 gen_word_audio.py / FrWordListMod 读的目录完全一致
FR_AUDIO = word_audio_dir()


def french_words():
    """返回受管法语书的所有词形，而非仅英法同形词。"""
    books = json.loads((ROOT / 'output' / 'french_books.json').read_text(
        encoding='utf-8'))
    french = set()
    for lv in ('a1', 'a2', 'b1', 'b2'):
        for item in books['levels'][lv]:
            french.add(item['word'])
    return sorted(french)


def main():
    restore = '--restore' in sys.argv
    words = set(french_words())
    print(f'受管法语词: {len(words)}')
    print(f'vocabulary = {VOCAB}')
    print(f'fr_word_audio = {FR_AUDIO}')
    if restore:
        FR_AUDIO.mkdir(parents=True, exist_ok=True)
        moved = 0
        for w in words:
            src = native_path(FR_AUDIO / (w + '.mp3'))
            if src.exists():
                shutil.move(str(src), str(native_path(VOCAB / (w + '.mp3'))))
                moved += 1
        print(f'已从 fr_word_audio 移回 vocabulary: {moved}')
        return
    VOCAB.mkdir(parents=True, exist_ok=True)
    FR_AUDIO.mkdir(parents=True, exist_ok=True)
    moved = conflicts = already = 0
    missing = []
    for w in sorted(words):
        src = native_path(VOCAB / (w + '.mp3'))
        dst = native_path(FR_AUDIO / (w + '.mp3'))
        if not src.exists():
            # 已经隔离过 (或从未生成) —— 与「丢了」要分开报, 否则每次都刷 8116 条
            if dst.exists():
                already += 1
            else:
                missing.append(w)
            continue
        # 已有私有副本时，来源可能是用户后来放回的自定义音频；不覆盖也
        # 不删除未知文件，留给用户人工决定。
        if dst.exists():
            conflicts += 1
            continue
        shutil.move(str(src), str(dst))
        moved += 1
    print(f'已移到 fr_word_audio: {moved}, 已在私有目录: {already}, '
          f'保留冲突: {conflicts}, 两处都无: {len(missing)}')
    if missing:
        print('真正缺失样例:', missing[:10])


if __name__ == '__main__':
    main()
