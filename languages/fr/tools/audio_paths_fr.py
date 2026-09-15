"""Native Windows paths, including French words such as aux and nul."""
import os
from pathlib import Path


def native_path(path):
    path = os.path.abspath(os.fspath(path))
    if os.name == 'nt' and not path.startswith('\\\\?\\'):
        path = '\\\\?\\UNC\\' + path[2:] if path.startswith('\\\\') else '\\\\?\\' + path
    return Path(path)


def word_audio_dir():
    local = os.environ.get('WCP_LOCALLOW')
    return (Path(local) if local else Path.home() / 'AppData' / 'LocalLow' / 'WCP' / 'wcp') / 'fr_word_audio'
