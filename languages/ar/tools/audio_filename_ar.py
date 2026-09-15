# -*- coding: utf-8 -*-
"""Stable Arabic word-audio filename contract.

Arabic tashkeel marks can have the same Unicode combining class in a different
order.  The WCP word fingerprint keeps the source spelling, but the audio
filename must use one deterministic order so equivalent spellings do not
produce two physical resources.
"""
import re
import unicodedata


BAD_CHARS_RE = re.compile(r'[\\/:*?"<>|\r\n\t]')


def canonical_audio_text(value: str) -> str:
    text = unicodedata.normalize('NFD', value.strip())
    out = []
    i = 0
    while i < len(text):
        base = text[i]
        i += 1
        marks = []
        while i < len(text) and unicodedata.combining(text[i]):
            marks.append(text[i])
            i += 1
        out.append(base + ''.join(sorted(marks, key=ord)))
    return unicodedata.normalize('NFC', ''.join(out))


def safe_filename(word: str) -> str:
    cleaned = BAD_CHARS_RE.sub('_', canonical_audio_text(word)).strip()
    if len(cleaned) > 60:
        cleaned = cleaned[:60]
    return cleaned + '.mp3'
