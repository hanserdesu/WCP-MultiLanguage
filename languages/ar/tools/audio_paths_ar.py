# -*- coding: utf-8 -*-
"""Private audio paths for Arabic project (multi-language isolation).

对标 audio_paths_pt.py / audio_paths_es.py / audio_paths_ko.py:
单词与例句音频分别落在 LocalLow/WCP/wcp/ 下的 ar_* 私有目录,
不进入游戏原生 vocabulary/ 或 sentence_audio/ 共享目录。
"""
from pathlib import Path


def word_audio_dir():
    return Path.home() / 'AppData' / 'LocalLow' / 'WCP' / 'wcp' / 'ar_word_audio'


def sentence_audio_dir():
    return Path.home() / 'AppData' / 'LocalLow' / 'WCP' / 'wcp' / 'ar_sentence_audio'
