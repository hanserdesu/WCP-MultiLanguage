# -*- coding: utf-8 -*-
"""Private audio paths for Portuguese project (multi-language isolation)."""
from pathlib import Path

def word_audio_dir():
    return Path.home() / 'AppData' / 'LocalLow' / 'WCP' / 'wcp' / 'pt_word_audio'

def sentence_audio_dir():
    return Path.home() / 'AppData' / 'LocalLow' / 'WCP' / 'wcp' / 'pt_sentence_audio'
