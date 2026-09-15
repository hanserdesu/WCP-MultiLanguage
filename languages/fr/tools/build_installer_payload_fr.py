# -*- coding: utf-8 -*-
"""构建可移植安装包 (WCP法语词书安装包/):

  01_双击运行我.cmd       ← 唯一需要双击的入口
  使用说明.txt             ← 普通用户说明
  support/                 ← 安装脚本与运行资源
  support/payload/         ← 词书、BepInEx、插件与数据库补丁资源

用法: python tools/build_installer_payload_fr.py
"""
import json
import os
import re
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'output'
PKG = OUT / 'installer_pkg' / 'WCP法语词书安装包'
SUPPORT = PKG / 'support'
PAYLOAD = SUPPORT / 'payload'
PDA = Path.home() / 'AppData' / 'LocalLow' / 'WCP'

# 游戏内可导入的分级词书与外接词库 (README「换机/重装」通道)
BOOK_FILES = ['法语A1A2.xlsx', '法语B1.xlsx', '法语B2.xlsx', 'wcp_french.db']

PLUGIN_FILES = {
    'FrWordListMod.dll': ROOT / 'mod_fr_wordlist' / 'FrWordListMod.dll',
    'BookNameMod.dll': ROOT / 'mod_book_name' / 'BookNameMod.dll',
    'SentenceAudioFrMod.dll': ROOT / 'mod_sentence_audio_fr' / 'SentenceAudioFrMod.dll',
}

DB_PAYLOAD_FILES = ['fr_pron.tsv', 'fr_sentences.tsv', 'fr_only_pron.tsv',
                    'en_pron.tsv', 'en_sentences.tsv', 'manifest.json']

BEPINEX_ROOT_FILES = ['.doorstop_version', 'BepInEx-changelog.txt',
                      'doorstop_config.ini', 'winhttp.dll']


def find_game_dir():
    """Locate the local WCP install used to collect the exact BepInEx runtime."""
    candidates = []
    explicit = os.environ.get('WCP_GAME_DIR')
    if explicit:
        candidates.append(Path(explicit))
    try:
        import winreg
        for hive, key in ((winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam'),
                          (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\WOW6432Node\Valve\Steam'),
                          (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Valve\Steam')):
            try:
                with winreg.OpenKey(hive, key) as handle:
                    for name in ('SteamPath', 'InstallPath'):
                        try:
                            candidates.append(Path(winreg.QueryValueEx(handle, name)[0]))
                        except OSError:
                            pass
            except OSError:
                pass
    except ImportError:
        pass
    libraries = []
    for root in candidates:
        if root not in libraries:
            libraries.append(root)
        vdf = root / 'steamapps' / 'libraryfolders.vdf'
        if vdf.exists():
            raw = vdf.read_text(encoding='utf-8', errors='ignore')
            for match in re.finditer(r'"path"\s*"([^"]+)"', raw):
                path = Path(match.group(1).replace('\\\\', '\\'))
                if path not in libraries:
                    libraries.append(path)
    for library in libraries:
        game = library / 'steamapps' / 'common' / 'WCP-WordGirlgriend'
        if (game / 'wcp_Data' / 'Managed' / 'Assembly-CSharp.dll').exists():
            return game
    return None


def collect_bepinex_runtime():
    """Copy clean loader/runtime files, excluding logs, cache, and user plugins."""
    source_text = os.environ.get('WCP_BEPINEX_SOURCE')
    game = Path(source_text) if source_text else find_game_dir()
    if game is None:
        raise FileNotFoundError('cannot find WCP game directory for BepInEx collection')
    source = game / 'BepInEx'
    if not (source / 'core' / 'BepInEx.dll').exists():
        raise FileNotFoundError(f'BepInEx 5 runtime not found: {source}')
    target = PAYLOAD / 'bepinex'
    root_target = target / 'root'
    core_target = target / 'BepInEx' / 'core'
    config_target = target / 'BepInEx' / 'config'
    root_target.mkdir(parents=True)
    core_target.mkdir(parents=True)
    config_target.mkdir(parents=True)
    for name in BEPINEX_ROOT_FILES:
        src = game / name
        if not src.exists():
            raise FileNotFoundError(f'BepInEx bootstrap file not found: {src}')
        shutil.copy2(src, root_target / name)
    for src in (source / 'core').iterdir():
        if src.is_file():
            shutil.copy2(src, core_target / src.name)
    default_cfg = source / 'config' / 'BepInEx.cfg'
    if default_cfg.exists():
        shutil.copy2(default_cfg, config_target / default_cfg.name)
    print(f'bepinex runtime: {source} -> {target}')


def copy_windows_script(src: Path, dst: Path):
    """Copy user-facing scripts with Windows-safe encoding and line endings."""
    raw = src.read_bytes()
    # Some editors/merges stack multiple BOMs; PowerShell 5.1 only strips the
    # first one and the leftovers glue onto the first token. Strip all of them,
    # and strip the BOM from .cmd files entirely (cmd.exe chokes on it too).
    while raw.startswith(b'\xef\xbb\xbf'):
        raw = raw[3:]
    text = raw.decode('utf-8').replace('\r\n', '\n').replace('\r', '\n')
    normalized = text.replace('\n', '\r\n').encode('utf-8')
    # Windows PowerShell 5.1 treats UTF-8 without a BOM as the ANSI code page.
    # A BOM makes Chinese messages and parser behavior deterministic.
    if src.suffix.lower() == '.ps1':
        normalized = b'\xef\xbb\xbf' + normalized
    dst.write_bytes(normalized)


def main():
    if PKG.exists():
        shutil.rmtree(PKG)
    PAYLOAD.mkdir(parents=True)
    (PAYLOAD / 'books').mkdir()
    (PAYLOAD / 'plugins').mkdir()
    (PAYLOAD / 'fr_db_payload').mkdir()
    collect_bepinex_runtime()

    for name, dll in PLUGIN_FILES.items():
        if not dll.exists():
            raise FileNotFoundError(f'missing plugin build: {dll}')
        shutil.copy2(dll, PAYLOAD / 'plugins' / name)
    print(f'plugins: {", ".join(sorted(PLUGIN_FILES))}')

    for name in DB_PAYLOAD_FILES:
        src = OUT / 'fr_db_payload' / name
        if not src.exists():
            raise FileNotFoundError(f'missing database repair payload: {src}')
        shutil.copy2(src, PAYLOAD / 'fr_db_payload' / name)
    print(f'fr_db_payload: {len(DB_PAYLOAD_FILES)} 个文件')

    book_payload = OUT / 'catbar_french_book.json'
    if not book_payload.exists():
        raise FileNotFoundError(f'missing combined book payload: {book_payload}')
    shutil.copy2(book_payload, PAYLOAD / book_payload.name)
    meta = json.loads(book_payload.read_text(encoding='utf-8'))
    if meta['word_count'] != 8116:
        raise RuntimeError(f'combined profile count mismatch: {meta["word_count"]}')
    print(f'{book_payload.name}: {meta["word_count"]} 词')

    for name in BOOK_FILES:
        src = PDA / 'wcp' / name
        if not src.exists():
            raise FileNotFoundError(f'missing importable book file: {src}')
        shutil.copy2(src, PAYLOAD / 'books' / name)
    print(f'books: {len(BOOK_FILES)} 个 (分级词书 + 外接词库)')

    entry = ROOT / 'installer' / '一键安装法语词书.cmd'
    if not entry.exists():
        raise FileNotFoundError(f'missing installer entry: {entry}')
    # cmd.exe requires CRLF. Normalize during every build so a Unix checkout
    # cannot produce a Windows installer that flashes and exits immediately.
    copy_windows_script(entry, PKG / '01_双击运行我.cmd')

    readme = ROOT / 'installer' / '说明-给法语群友.txt'
    if not readme.exists():
        raise FileNotFoundError(f'missing installer readme: {readme}')
    copy_windows_script(readme, PKG / '使用说明.txt')

    for name in ('run-installer.ps1', 'Install-WCP-French.ps1',
                 'check-compatibility.ps1', 'compatibility-help.cmd'):
        src = ROOT / 'installer' / name
        if not src.exists():
            raise FileNotFoundError(f'missing installer support file: {src}')
        dst = SUPPORT / name
        if src.suffix.lower() in ('.cmd', '.ps1'):
            copy_windows_script(src, dst)
        else:
            shutil.copy2(src, dst)

    total = sum(f.stat().st_size for f in PAYLOAD.rglob('*') if f.is_file())
    manifest = {
        'profile': meta['id'],
        'fingerprint_sha256': meta['fingerprint_sha256'],
        'words': meta['word_count'],
        'plugins': sorted(PLUGIN_FILES),
        'db_payload_files': DB_PAYLOAD_FILES,
        'books': BOOK_FILES,
        'bundled_bepinex': True,
        'audio': 'downloaded from release-manifest.json',
        'size_mb': round(total / 1e6, 1),
    }
    (PAYLOAD / 'manifest.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding='utf-8')
    print('manifest:', json.dumps(manifest, ensure_ascii=False))
    print('包目录 ->', PKG)


if __name__ == '__main__':
    main()
