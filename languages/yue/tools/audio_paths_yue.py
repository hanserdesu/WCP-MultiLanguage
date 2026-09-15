# -*- coding: utf-8 -*-
"""粤语私有音频路径配置，对齐多语言隔离架构规范"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
import wcp_paths


def word_audio_dir() -> Path:
    """运行态或安装目标单词音频私有目录"""
    d = wcp_paths.persistent_wcp() / 'yue_word_audio'
    d.mkdir(parents=True, exist_ok=True)
    return d


def sentence_audio_dir() -> Path:
    """运行态或安装目标例句音频私有目录"""
    d = wcp_paths.persistent_wcp() / 'yue_sentence_audio'
    d.mkdir(parents=True, exist_ok=True)
    return d


def pack_word_audio_dir() -> Path:
    """packs/yue 包内单词音频目录"""
    d = ROOT / 'packs' / 'yue' / 'audio' / 'word'
    d.mkdir(parents=True, exist_ok=True)
    return d


def pack_sentence_audio_dir() -> Path:
    """packs/yue 包内例句音频目录"""
    d = ROOT / 'packs' / 'yue' / 'audio' / 'sentence'
    d.mkdir(parents=True, exist_ok=True)
    return d
