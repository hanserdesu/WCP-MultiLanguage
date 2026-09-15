# -*- coding: utf-8 -*-
"""定位《万词破-单词女友》游戏安装目录与路径。"""
import os
import re
from pathlib import Path

APP_DIR = 'WCP-WordGirlgriend'
DB_NAME = 'wcpFullEng.db'

FALLBACK_COMMON = [
    r'E:\Steam\steamapps\common',
    r'E:\SteamLibrary\steamapps\common',
    r'D:\SteamLibrary\steamapps\common',
    r'G:\SteamLibrary\steamapps\common',
    r'C:\Program Files (x86)\Steam\steamapps\common',
]

_cache = None


def _steam_roots():
    roots = []
    try:
        import winreg
    except ImportError:
        winreg = None
    if winreg is not None:
        for name in ('SteamPath', 'InstallPath'):
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                    r'Software\Valve\Steam') as key:
                    value, _ = winreg.QueryValueEx(key, name)
                if value:
                    roots.append(Path(str(value)))
            except OSError:
                pass
    for r in list(roots):
        vdf = r / 'steamapps' / 'libraryfolders.vdf'
        if not vdf.exists():
            continue
        text = vdf.read_text(encoding='utf-8', errors='ignore')
        for m in re.finditer(r'"path"\s*"([^"]+)"', text):
            roots.append(Path(m.group(1)))
    out, seen = [], set()
    for r in roots:
        key = str(r).lower().rstrip('\\')
        if key and key not in seen:
            seen.add(key)
            out.append(r)
    return out


def candidates():
    cands = []
    env = os.environ.get('WCP_GAME_DIR', '').strip()
    if env:
        cands.append(Path(env))
    cands += [r / 'steamapps' / 'common' / APP_DIR for r in _steam_roots()]
    cands += [Path(p) / APP_DIR for p in FALLBACK_COMMON]
    out, seen = [], set()
    for c in cands:
        key = str(c).lower().rstrip('\\')
        if key not in seen:
            seen.add(key)
            out.append(c)
    return out


def game_dir(force=False):
    global _cache
    if _cache is not None and not force:
        return _cache
    found = None
    for c in candidates():
        if (c / 'wcp_Data' / 'StreamingAssets' / DB_NAME).exists():
            found = c
            break
    if found is None:
        for c in candidates():
            if (c / 'wcp_Data').is_dir():
                found = c
                break
    _cache = found if found is not None else candidates()[0]
    return _cache


def streaming_assets():
    return game_dir() / 'wcp_Data' / 'StreamingAssets'


def full_db():
    return streaming_assets() / DB_NAME


def only_db():
    return streaming_assets() / 'wcpOnlyWord.db'


def persistent_dir():
    return Path.home() / 'AppData' / 'LocalLow' / 'WCP' / 'wcp'


def vocabulary_dir():
    return Path.home() / 'AppData' / 'LocalLow' / 'WCP' / 'vocabulary'
