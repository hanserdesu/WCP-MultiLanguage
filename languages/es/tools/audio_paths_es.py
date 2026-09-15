# -*- coding: utf-8 -*-
"""Private audio paths for Spanish project (multi-language isolation)."""
from pathlib import Path

def word_audio_dir():
    return Path.home() / 'AppData' / 'LocalLow' / 'WCP' / 'wcp' / 'es_word_audio'

def sentence_audio_dir():
    return Path.home() / 'AppData' / 'LocalLow' / 'WCP' / 'wcp' / 'es_sentence_audio'
