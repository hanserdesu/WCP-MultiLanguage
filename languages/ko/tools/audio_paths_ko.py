# -*- coding: utf-8 -*-
"""韩语单词和例句音频路径配置。"""
import os
from pathlib import Path


def native_path(path):
    path = os.path.abspath(os.fspath(path))
    if os.name == 'nt' and not path.startswith('\\\\?\\'):
        path = '\\\\?\\UNC\\' + path[2:] if path.startswith('\\\\') else '\\\\?\\' + path
    return Path(path)


def word_audio_dir():
    local = os.environ.get('WCP_LOCALLOW')
    base = Path(local) if local else Path.home() / 'AppData' / 'LocalLow' / 'WCP' / 'wcp'
    d = base / 'ko_word_audio'
    d.mkdir(parents=True, exist_ok=True)
    return d


def sentence_audio_dir():
    local = os.environ.get('WCP_LOCALLOW')
    base = Path(local) if local else Path.home() / 'AppData' / 'LocalLow' / 'WCP' / 'wcp'
    d = base / 'ko_sentence_audio'
    d.mkdir(parents=True, exist_ok=True)
    return d
