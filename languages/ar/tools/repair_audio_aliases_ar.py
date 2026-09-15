# -*- coding: utf-8 -*-
"""Backfill stable filenames for already generated Arabic word audio.

The operation is additive: it only copies an existing audio file to a missing
canonical filename and never removes or overwrites a user file.
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
from audio_filename_ar import canonical_audio_text, safe_filename  # noqa: E402
from audio_paths_ar import word_audio_dir  # noqa: E402


def main() -> int:
    source = ROOT / 'output' / 'arabic_books.json'
    data = json.loads(source.read_text(encoding='utf-8'))
    words = {
        canonical_audio_text(entry['word'])
        for rows in data['books'].values()
        for entry in rows
    }
    audio_dir = word_audio_dir()
    audio_dir.mkdir(parents=True, exist_ok=True)
    by_key = {}
    for path in audio_dir.glob('*.mp3'):
        by_key.setdefault(canonical_audio_text(path.stem), path)

    copied = 0
    unresolved = []
    for word in sorted(words):
        target = audio_dir / safe_filename(word)
        if target.exists():
            continue
        source_audio = by_key.get(canonical_audio_text(word))
        if source_audio is None:
            unresolved.append(word)
            continue
        shutil.copy2(source_audio, target)
        copied += 1

    print(f'canonical aliases copied: {copied}')
    print(f'unresolved words: {len(unresolved)}')
    for word in unresolved[:20]:
        print('  ' + word)
    return 1 if unresolved else 0


if __name__ == '__main__':
    raise SystemExit(main())
