# -*- coding: utf-8 -*-
"""构建可移植安装包 (WCP日语词书安装包/):

  01_双击运行我.cmd       ← 唯一需要双击的入口，自动选择兼容运行环境
  使用说明.txt             ← 普通用户说明
  support/                 ← 安装脚本与所有运行资源，无需手动打开
  support/payload/         ← 词书、BepInEx、插件和数据库资源

用法: python tools/build_installer_payload.py [--skip-audio]
"""
import json
import os
import re
import shutil
import subprocess
import sqlite3
import sys
import time
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
OUT = ROOT / 'output'
PKG = OUT / 'installer_pkg' / 'WCP日语词书安装包'
SUPPORT = PKG / 'support'
PAYLOAD = SUPPORT / 'payload'
PDA = Path.home() / 'AppData' / 'LocalLow' / 'WCP'

BOOK_FILES = ['JLPT_N5N4_初级.xlsx', 'JLPT_N3.xlsx', 'JLPT_N2.xlsx',
              'JLPT_N1.xlsx', 'IT用语.xlsx',
              'wcp_jlpt.db', 'wcp_setb.db', 'wcp_themed.db',
              'wcp_kanji.db', 'wcp_all.db', 'wcp_grammar.db',
              '语法路线.xlsx']

PLUGIN_FILES = {
    # The host owns language selection, resource routing and game hooks.  Keep
    # the legacy Japanese plugins in the package during the migration window,
    # but ship the host and generic-slot UI as part of the actual installer.
    'WcpHost.dll': ROOT.parent / 'mod_host' / 'WcpHost.dll',
    'CustomSlotsMod.dll': ROOT.parent / 'mod_custom_slots' / 'CustomSlotsMod.dll',
    'JpWordListMod.dll': ROOT.parent / 'mod_jp_wordlist' / 'JpWordListMod.dll',
    'BookNameMod.dll': ROOT.parent / 'mod_book_name' / 'BookNameMod.dll',
    'SentenceAudioMod.dll': ROOT.parent / 'mod_sentence_audio' / 'SentenceAudioMod.dll',
}

PACK_SOURCE = ROOT.parent / 'packs' / 'ja'

BEPINEX_ROOT_FILES = ['.doorstop_version', 'BepInEx-changelog.txt',
                      'doorstop_config.ini', 'winhttp.dll']


def find_game_dir():
    """Find the local WCP install used to collect the exact BepInEx runtime."""
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


def build_combined_book_payload():
    """Write the exact profile recognized by BookProfiles.cs."""
    data = json.loads((OUT / 'jlpt_books.json').read_text(encoding='utf-8'))
    seen, words, meanings = set(), [], {}
    for level in ('n5', 'n4', 'n3', 'n2', 'n1'):
        for row in data['levels'][level]:
            word = (row.get('word') or '').strip()
            meaning = (row.get('meaning') or row.get('meaning_en') or '').strip()
            if not word or not meaning or word in seen:
                continue
            seen.add(word)
            words.append(word)
            meanings[word] = meaning
    if len(words) != 7922:
        raise RuntimeError(f'combined JLPT profile count mismatch: {len(words)}')
    payload = {
        'id': 'catbar-jlpt-complete',
        'language': 'ja',
        'display_name': '日语词库(猫条版)',
        'word_count': len(words),
        'fingerprint_sha256': '6d7a51c0c5d30dd63d8a6e3412bce1cf2419554fb8487cf5c8a205e43ac41663',
        'words': words,
        'meanings': meanings,
    }
    (PAYLOAD / 'catbar_book.json').write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'catbar_book.json: {len(words)} 词')


def collect_words():
    from patch_local_db import collect
    words = collect()
    # 语法占位词
    from build_grammar_book import load_curriculum, build_route, load_content
    route, _ = build_route(load_curriculum(None), load_content(), True)
    ph = {}
    for e in route:
        if e['kind'] in ('grammar', 'stage'):
            ph[e['word']] = {'reading': e['reading'], 'meaning': e['meaning'],
                             'ex_ja': '', 'ex_tr': ''}
    words.update(ph)
    return words, route


def build_additions(words, route):
    master = json.loads((ROOT / 'data' / 'translations' / 'sentences_master.json')
                        .read_text(encoding='utf-8'))
    furigana = json.loads((ROOT / 'data' / 'translations' / 'furigana_map.json')
                          .read_text(encoding='utf-8'))
    jlpt = json.loads((OUT / 'jlpt_books.json').read_text(encoding='utf-8'))
    path = PAYLOAD / 'additions.db'
    if path.exists():
        path.unlink()
    con = sqlite3.connect(path)
    cur = con.cursor()
    cur.execute('CREATE TABLE pron (word TEXT PRIMARY KEY, ukPhonic TEXT, meaning TEXT)')
    cur.execute('CREATE TABLE sentence2 (word TEXT, sentences TEXT)')
    cur.execute('CREATE TABLE help (word TEXT PRIMARY KEY, help TEXT)')
    cur.execute('CREATE TABLE bookslot (slot INTEGER, word TEXT, meaning TEXT)')
    n_p = n_s = n_h = n_b = 0
    for w, v in words.items():
        cur.execute('INSERT OR REPLACE INTO pron VALUES (?,?,?)',
                    (w, f"[{v['reading']}]" if v['reading'] else '', v['meaning']))
        n_p += 1
        for ja, zh in master.get(w, []):
            cur.execute('INSERT INTO sentence2 VALUES (?,?)',
                        (w, f'例句：{ja}（{zh}）' if zh else f'例句：{ja}'))
            n_s += 1
        if w in furigana:
            cur.execute('INSERT OR REPLACE INTO help VALUES (?,?)',
                        (w, f'振り仮名：{furigana[w]}'))
            n_h += 1
    for e in route:
        if e['kind'] in ('grammar', 'stage'):
            for ja, zh in e['rows']:
                cur.execute('INSERT INTO sentence2 VALUES (?,?)',
                            (e['word'], f'例句：{ja}（{zh}）'))
                n_s += 1
    slot_of = {'n5n4': 1, 'n3': 2, 'n2': 3, 'n1': 4}
    for lv, rows in jlpt['levels'].items():
        slot = slot_of.get(lv) or (1 if lv == 'n4' else None)
        for r in rows:
            if r.get('meaning'):
                cur.execute('INSERT INTO bookslot VALUES (?,?,?)',
                            (slot, r['word'], r['meaning']))
                n_b += 1
    con.commit()
    con.close()
    print(f'additions.db: pron {n_p}, sentence2 {n_s}, help {n_h}, bookslot {n_b}')


def zip_dir(src: Path, dst: Path):
    if dst.exists():
        dst.unlink()
    files = [p for p in src.rglob('*') if p.is_file() and p.stat().st_size > 1000]
    with zipfile.ZipFile(dst, 'w', zipfile.ZIP_STORED, allowZip64=True) as z:
        for p in files:
            z.write(p, p.name)
    print(f'{dst.name}: {len(files)} 文件, {dst.stat().st_size / 1e6:.0f}MB')


def stage_word_audio(words, target: Path):
    """Stage only this language's word audio from its pack or old shared dir."""
    private_source = PDA / 'packs' / 'ja' / 'audio' / 'word'
    source = private_source if private_source.is_dir() else PDA / 'vocabulary'
    if not source.is_dir():
        raise FileNotFoundError(f'missing Japanese word audio source: {source}')
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    missing = []
    copied = 0
    for word in sorted(set(words)):
        found = False
        for suffix in ('.mp3', '.wav'):
            src = source / f'{word}{suffix}'
            if src.is_file() and src.stat().st_size > 1000:
                shutil.copy2(src, target / src.name)
                copied += 1
                found = True
                break
        if not found:
            missing.append(word)
    if missing:
        sample = ', '.join(missing[:8])
        raise RuntimeError(
            f'Japanese word audio incomplete: {len(missing)} missing; sample={sample}')
    print(f'Japanese word audio staged: {copied} files -> {target}')


def copy_windows_script(src: Path, dst: Path):
    """Copy user-facing scripts with Windows-safe encoding and line endings."""
    raw = src.read_bytes()
    # Some editors/merges stack multiple BOMs; PowerShell 5.1 only strips the
    # first one and the leftovers glue onto the first token (e.g.
    # "' $ErrorActionPreference' is not recognized"). Strip all of them.
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
    skip_audio = '--skip-audio' in sys.argv
    normalize = ROOT / 'tools' / 'normalize_installer_eol.py'
    subprocess.run([sys.executable, str(normalize)], check=True)
    if PKG.exists():
        shutil.rmtree(PKG)
    PAYLOAD.mkdir(parents=True)
    (PAYLOAD / 'books').mkdir()
    (PAYLOAD / 'plugins').mkdir()
    (PAYLOAD / 'packs').mkdir()
    (PAYLOAD / 'jp_db_payload').mkdir()
    (PAYLOAD / 'audio').mkdir()
    collect_bepinex_runtime()

    words, route = collect_words()
    build_additions(words, route)
    build_combined_book_payload()

    for name in BOOK_FILES:
        src = PDA / 'wcp' / name
        if src.exists():
            shutil.copy2(src, PAYLOAD / 'books' / name)
        else:
            print(f'!! 缺词书文件: {name}')
    print(f'books: {len(list((PAYLOAD / "books").iterdir()))} 个')

    for name, dll in PLUGIN_FILES.items():
        if not dll.exists():
            raise FileNotFoundError(f'missing plugin build: {dll}')
        shutil.copy2(dll, PAYLOAD / 'plugins' / name)

    if not (PACK_SOURCE / 'manifest.json').exists():
        raise FileNotFoundError(f'missing Japanese resource pack: {PACK_SOURCE}')
    # Audio is published as separately hashed assets so the core installer
    # stays small; the installer materializes it under this same pack later.
    shutil.copytree(PACK_SOURCE, PAYLOAD / 'packs' / 'ja',
                    ignore=shutil.ignore_patterns('audio'))
    print(f'pack: {PACK_SOURCE} -> {PAYLOAD / "packs" / "ja"}')
    db_payload = ROOT / 'output' / 'jp_db_payload'
    for name in ('jp_pron.tsv', 'jp_sentences.tsv', 'jp_only_pron.tsv', 'manifest.json'):
        src = db_payload / name
        if not src.exists():
            raise FileNotFoundError(f'missing database repair payload: {src}')
        shutil.copy2(src, PAYLOAD / 'jp_db_payload' / name)

    combined = ROOT / 'output' / 'import' / '日语词库(猫条版).xlsx'
    if combined.exists():
        shutil.copy2(combined, PAYLOAD / 'books' / combined.name)
    else:
        print(f'!! 缺少可移植合并词书: {combined}')

    entry = ROOT / 'installer' / '一键安装日语词书.cmd'
    if not entry.exists():
        raise FileNotFoundError(f'missing installer entry: {entry}')
    # cmd.exe requires CRLF. Normalize during every build so a Unix checkout
    # cannot produce a Windows installer that flashes and exits immediately.
    copy_windows_script(entry, PKG / '01_双击运行我.cmd')

    readme = ROOT / 'installer' / '说明-给群友.txt'
    if not readme.exists():
        raise FileNotFoundError(f'missing installer readme: {readme}')
    shutil.copy2(readme, PKG / '使用说明.txt')

    for name in ('run-installer.ps1', 'Install-WCP-Japanese.ps1',
                 'check-compatibility.ps1', 'compatibility-help.cmd'):
        src = ROOT / 'installer' / name
        if not src.exists():
            raise FileNotFoundError(f'missing installer support file: {src}')
        dst = SUPPORT / name
        if src.suffix.lower() in ('.cmd', '.ps1'):
            copy_windows_script(src, dst)
        else:
            shutil.copy2(src, dst)

    if not skip_audio:
        t0 = time.time()
        from patch_local_db import collect
        word_stage = PAYLOAD / 'audio' / 'word_stage'
        stage_word_audio(collect().keys(), word_stage)
        zip_dir(word_stage, PAYLOAD / 'audio' / 'words.zip')
        shutil.rmtree(word_stage)
        private_sentences = PDA / 'packs' / 'ja' / 'audio' / 'sentence'
        legacy_sentences = PDA / 'wcp' / 'ja_sentence_audio'
        sentence_source = (private_sentences if private_sentences.is_dir()
                           else legacy_sentences)
        zip_dir(sentence_source, PAYLOAD / 'audio' / 'sentences.zip')
        print(f'音频打包用时 {(time.time() - t0) / 60:.1f}min')

    total = sum(f.stat().st_size for f in PAYLOAD.rglob('*') if f.is_file())
    manifest = {
        'built': time.strftime('%Y-%m-%d %H:%M'),
        'pron': len(words),
        'grammar_placeholders': sum(1 for e in route if e['kind'] == 'grammar'),
        'stages': 5,
        'route_rows': len(route),
        'skip_audio': skip_audio,
        'bundled_bepinex': True,
        'plugins': sorted(PLUGIN_FILES),
        'auto_import': True,
        'size_mb': round(total / 1e6, 1),
    }
    (PAYLOAD / 'manifest.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding='utf-8')
    print('manifest:', json.dumps(manifest, ensure_ascii=False))
    print('包目录 ->', PKG)


if __name__ == '__main__':
    main()
