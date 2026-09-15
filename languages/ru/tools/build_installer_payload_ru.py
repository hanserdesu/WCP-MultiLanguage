# -*- coding: utf-8 -*-
"""构建可移植俄语安装包 (WCP俄语词书安装包/):

  01_双击运行我.cmd       ← 唯一需要双击的入口
  使用说明.txt             ← 普通用户说明
  support/                 ← 安装脚本与运行资源
  support/payload/         ← 词书、BepInEx、插件与数据库补丁资源

用法: python tools/build_installer_payload_ru.py
"""
import json
import os
import re
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
import wcp_paths

OUT = ROOT / 'output'
PKG = OUT / 'installer_pkg' / 'WCP俄语词书安装包'
SUPPORT = PKG / 'support'
PAYLOAD = SUPPORT / 'payload'
PDA = Path.home() / 'AppData' / 'LocalLow' / 'WCP'

BOOK_FILES = ['俄语A1A2.xlsx', '俄语B1.xlsx', '俄语B2.xlsx', 'wcp_russian.db']

PLUGIN_FILES = {
    'RuWordListMod.dll': ROOT / 'mod_ru_wordlist' / 'RuWordListMod.dll',
    'BookNameMod.dll': ROOT / 'mod_book_name' / 'BookNameMod.dll',
    'SentenceAudioRuMod.dll': ROOT / 'mod_sentence_audio_ru' / 'SentenceAudioRuMod.dll',
}

DB_PAYLOAD_FILES = ['ru_pron.tsv', 'ru_sentences.tsv', 'ru_only_pron.tsv', 'manifest.json']

BEPINEX_ROOT_FILES = ['.doorstop_version', 'BepInEx-changelog.txt',
                      'doorstop_config.ini', 'winhttp.dll']


def collect_bepinex_runtime():
    game = wcp_paths.game_dir()
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
    raw = src.read_bytes()
    while raw.startswith(b'\xef\xbb\xbf'):
        raw = raw[3:]
    text = raw.decode('utf-8').replace('\r\n', '\n').replace('\r', '\n')
    normalized = text.replace('\n', '\r\n').encode('utf-8')
    if src.suffix.lower() == '.ps1':
        normalized = b'\xef\xbb\xbf' + normalized
    dst.write_bytes(normalized)


def main():
    if PKG.exists():
        shutil.rmtree(PKG)
    PAYLOAD.mkdir(parents=True)
    (PAYLOAD / 'books').mkdir()
    (PAYLOAD / 'plugins').mkdir()
    (PAYLOAD / 'ru_db_payload').mkdir()
    collect_bepinex_runtime()

    for name, dll in PLUGIN_FILES.items():
        if not dll.exists():
            raise FileNotFoundError(f'missing plugin build: {dll}')
        shutil.copy2(dll, PAYLOAD / 'plugins' / name)
    print(f'plugins: {", ".join(sorted(PLUGIN_FILES))}')

    for name in DB_PAYLOAD_FILES:
        src = OUT / 'ru_db_payload' / name
        if not src.exists():
            raise FileNotFoundError(f'missing database repair payload: {src}')
        shutil.copy2(src, PAYLOAD / 'ru_db_payload' / name)
    print(f'ru_db_payload: {len(DB_PAYLOAD_FILES)} 个文件')

    book_payload = OUT / 'catbar_russian_book.json'
    if not book_payload.exists():
        raise FileNotFoundError(f'missing combined book payload: {book_payload}')
    shutil.copy2(book_payload, PAYLOAD / book_payload.name)
    meta = json.loads(book_payload.read_text(encoding='utf-8'))
    if meta['word_count'] != 8451:
        raise RuntimeError(f'combined profile count mismatch: {meta["word_count"]}')
    print(f'{book_payload.name}: {meta["word_count"]} 词')

    for name in BOOK_FILES:
        src = OUT / 'import' / name
        if not src.exists():
            raise FileNotFoundError(f'missing book asset: {src}')
        shutil.copy2(src, PAYLOAD / 'books' / name)
    print(f'import books: {", ".join(BOOK_FILES)}')

    installer_dir = ROOT / 'installer'
    copy_windows_script(installer_dir / 'WcpEs3Helper.cs', SUPPORT / 'WcpEs3Helper.cs')
    copy_windows_script(installer_dir / 'SteamPaths.ps1', SUPPORT / 'SteamPaths.ps1')
    copy_windows_script(installer_dir / 'Install-WCP-Russian.ps1', SUPPORT / 'Install-WCP-Russian.ps1')
    copy_windows_script(installer_dir / 'check-compatibility.ps1', SUPPORT / 'check-compatibility.ps1')
    copy_windows_script(installer_dir / 'compatibility-help.cmd', SUPPORT / 'compatibility-help.cmd')
    copy_windows_script(installer_dir / 'run-installer.ps1', SUPPORT / 'run-installer.ps1')

    copy_windows_script(installer_dir / '一键安装俄语词书.cmd', PKG / '01_双击运行我.cmd')
    copy_windows_script(installer_dir / '一键安装俄语词书.cmd', PKG / '一键安装俄语词书.cmd')

    readme = '''WCP 俄语词书 (猫条版) 一键安装包
========================================
适用游戏: 万词破 - 单词女友 (Steam appid 1981560)
收录规模: CEFR A1-B2 全量俄语精选词书 8451 词 (猫条版完整词库)
包含特性:
  1. 槽位 3 自动配置「俄语词库(猫条版)」(槽位1日语/槽位2法语原样保留)
  2. BepInEx 5.4.23.5 自动化环境与核心插件 (RuWordListMod, BookNameMod, SentenceAudioRuMod)
  3. 离线数据库自愈支持 (ru_db_payload)
  4. 选书回读保护与跨词书绝对隔离

安装方法:
  1. 请先完全退出《万词破》游戏 (wcp.exe)。
  2. 双击运行「01_双击运行我.cmd」。
  3. 安装器会自动识别 Steam 库中游戏安装目录，并执行环境配置与词书载入。
  4. 提示安装成功后，重新启动游戏即可在「自定义词书三」中看到并学习俄语词库！
'''
    (PKG / '使用说明.txt').write_text(readme, encoding='utf-8')
    print('generated', PKG / '使用说明.txt')
    print(f'Package built: {PKG}')


if __name__ == '__main__':
    main()
