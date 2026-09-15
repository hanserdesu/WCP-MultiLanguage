# -*- coding: utf-8 -*-
r"""定位《万词破-单词女友》**实际在运行**的那份安装目录。

背景 (2026-09-12 修正):
  多个脚本把游戏目录硬编码成 E:\SteamLibrary\... —— 那是一份已经不被
  Steam 加载的旧副本 (E:\Steam\steamapps\libraryfolders.vdf 里只有
  E:\Steam / D:\SteamLibrary / G:\SteamLibrary)。灌库灌进副本, 游戏读的是
  E:\Steam\..., 结果就是「本地暂未收录这个单词」加上空例句。
  游戏真正的位置可由 Player.log 第一行的 Mono path 证实。

解析顺序:
  1. 环境变量 WCP_GAME_DIR (游戏根目录, 含 wcp_Data; 便于临时指向别的安装)
  2. 注册表 HKCU\Software\Valve\Steam 的 SteamPath/InstallPath
     + 各 Steam 库 libraryfolders.vdf 中的 path
  3. 已知候选目录
  只认「目录下存在 wcp_Data/StreamingAssets/wcpFullEng.db」的路径。
"""
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
    """注册表里的 Steam 根目录 + libraryfolders.vdf 里的各个库。"""
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
    """按优先级给出候选游戏根目录 (去重)。"""
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
    """游戏根目录 (含 wcp_Data 的那一层)。设 WCP_GAME_DIR 可强制覆盖。"""
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


def managed_dll():
    return game_dir() / 'wcp_Data' / 'Managed' / 'Assembly-CSharp.dll'
