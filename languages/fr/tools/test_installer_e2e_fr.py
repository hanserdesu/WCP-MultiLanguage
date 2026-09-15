# -*- coding: utf-8 -*-
"""沙箱端到端验证法语一键安装链路 (不触碰真实游戏目录与真实存档)。

流程与真实玩家完全一致，只是把落点换成沙箱:
  1. 伪造 USERPROFILE 与一个假游戏目录 (wcp_Data 标记文件齐备);
  2. 用本地 HTTP 服务充当 GitHub Release, 把 support/release-manifest.json
     的 base_urls 改写成 http://127.0.0.1:<port>;
  3. 运行 support/Install-WCP-French.ps1 完整走
     下载 -> SHA-256 校验 -> 解压 -> 落位 -> 写 MyBook 槽位2;
  4. 断言插件/词书/音频/存档全部就位, 且真实目录未被触碰。

用法: python tools/test_installer_e2e_fr.py [--keep]
"""
import hashlib
import functools
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'output'
PKG = OUT / 'installer_pkg' / 'WCP法语词书安装包'
RELEASE = OUT / 'release'
SANDBOX = ROOT / 'scratch' / 'e2e_installer'
REAL_DATA = Path.home() / 'AppData' / 'LocalLow' / 'WCP' / 'wcp'
WORD_ZIP = RELEASE / 'wcp-french-audio-words.zip'
SENT_ZIP = RELEASE / 'wcp-french-audio-sentences.zip'

failures = []
checks = 0


def check(name, ok, detail=''):
    global checks
    checks += 1
    mark = 'PASS' if ok else 'FAIL'
    print(f'[{mark}] {name}{(" — " + detail) if detail else ""}')
    if not ok:
        failures.append(name)


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def start_server(directory):
    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(directory))
    handler.log_message = lambda *a, **k: None
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, server.server_address[1]


def main():
    keep = '--keep' in sys.argv
    for p in (WORD_ZIP, SENT_ZIP, PKG / 'support' / 'release-manifest.json'):
        if not p.exists():
            raise FileNotFoundError(f'先运行 tools/build_release_fr.py 生成 {p}')
    if subprocess.run(['tasklist', '/FI', 'IMAGENAME eq wcp.exe'], capture_output=True,
                      text=True, errors='replace').stdout.lower().count('wcp.exe'):
        raise RuntimeError('检测到万词破正在运行，请先退出游戏再跑沙箱验证。')

    real_mybook = REAL_DATA / 'MyBook.es3'
    real_save = REAL_DATA / 'SaveFile.es3'
    if not real_mybook.exists():
        raise FileNotFoundError(f'缺少真实 MyBook.es3 作为沙箱样本: {real_mybook}')
    real_hashes = {str(p): sha256(p) for p in (real_mybook, real_save) if p.exists()}

    if SANDBOX.exists():
        shutil.rmtree(SANDBOX)
    profile = SANDBOX / 'profile'
    data = profile / 'AppData' / 'LocalLow' / 'WCP' / 'wcp'
    game = SANDBOX / 'game'
    data.mkdir(parents=True)
    (game / 'wcp_Data' / 'Managed').mkdir(parents=True)
    (game / 'wcp_Data' / 'StreamingAssets').mkdir(parents=True)
    for marker in (game / 'wcp_Data' / 'Managed' / 'Assembly-CSharp.dll',
                   game / 'wcp_Data' / 'StreamingAssets' / 'wcpFullEng.db',
                   game / 'wcp_Data' / 'StreamingAssets' / 'wcpOnlyWord.db'):
        marker.write_bytes(b'')
    shutil.copy2(real_mybook, data / 'MyBook.es3')
    if real_save.exists():
        shutil.copy2(real_save, data / 'SaveFile.es3')
    pkg_copy = SANDBOX / 'pkg'
    shutil.copytree(PKG, pkg_copy)

    server, port = start_server(RELEASE)
    manifest_path = pkg_copy / 'support' / 'release-manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    manifest['base_urls'] = [f'http://127.0.0.1:{port}']
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                             encoding='utf-8')
    print(f'沙箱: {SANDBOX}  (下载源 http://127.0.0.1:{port})')

    env = os.environ.copy()
    env['USERPROFILE'] = str(profile)
    env['WCP_GAME_DIR'] = str(game)
    # Windows PowerShell derives its module-analysis cache from these; without
    # an override it drops a Microsoft\Windows\PowerShell tree into the cwd.
    env['LOCALAPPDATA'] = str(profile / 'AppData' / 'Local')
    env['APPDATA'] = str(profile / 'AppData' / 'Roaming')
    (profile / 'AppData' / 'Local').mkdir(parents=True, exist_ok=True)
    (profile / 'AppData' / 'Roaming').mkdir(parents=True, exist_ok=True)
    install = pkg_copy / 'support' / 'Install-WCP-French.ps1'
    t0 = time.time()
    proc = subprocess.run(
        ['powershell.exe', '-NoLogo', '-NoProfile', '-ExecutionPolicy', 'Bypass',
         '-Command', f'& "{install}"; exit $LASTEXITCODE'],
        env=env, cwd=str(SANDBOX), capture_output=True, text=True,
        encoding='utf-8', errors='replace', timeout=3600)
    print(proc.stdout[-3000:])
    if proc.stderr.strip():
        print('STDERR:', proc.stderr[-2000:])
    print(f'安装器退出码 {proc.returncode}, 用时 {(time.time() - t0) / 60:.1f} 分钟')
    check('安装器正常结束', proc.returncode == 0)

    # --- 游戏目录: BepInEx 与插件 ---
    for name in ('winhttp.dll', '.doorstop_version', 'doorstop_config.ini'):
        check(f'游戏目录 {name}', (game / name).exists())
    check('BepInEx 运行时', (game / 'BepInEx' / 'core' / 'BepInEx.dll').exists())
    for name in ('FrWordListMod.dll', 'BookNameMod.dll', 'SentenceAudioFrMod.dll'):
        got = game / 'BepInEx' / 'plugins' / name
        want = pkg_copy / 'support' / 'payload' / 'plugins' / name
        check(f'插件 {name}', got.exists() and sha256(got) == sha256(want))

    # --- 存档目录: 词书 / 补丁包 / 音频 ---
    for name in ('法语A1A2.xlsx', '法语B1.xlsx', '法语B2.xlsx', 'wcp_french.db',
                 'frmod_install.json'):
        check(f'存档目录 {name}', (data / name).exists())
    for name in ('fr_pron.tsv', 'fr_sentences.tsv', 'fr_only_pron.tsv',
                 'en_pron.tsv', 'en_sentences.tsv', 'manifest.json'):
        check(f'fr_db_payload/{name}', (data / 'fr_db_payload' / name).exists())

    words = sorted((data / 'fr_word_audio').glob('*.mp3'))
    check('单词音频 8,116', len(words) == 8116, f'实际 {len(words)}')
    src_aux = REAL_DATA / 'fr_word_audio' / 'aux.mp3'
    got_aux = data / 'fr_word_audio' / 'aux.mp3'
    check('保留设备名音频 aux.mp3 内容一致',
          got_aux.exists() and src_aux.exists() and sha256(got_aux) == sha256(src_aux))

    master = json.loads((ROOT / 'data' / 'translations' /
                         'sentences_master.json').read_text(encoding='utf-8'))
    fr_sentences = {f for items in master.values() for f, _ in items}
    missing = [s for s in fr_sentences
        if not (data / 'fr_sentence_audio' /
                       (hashlib.md5(s.encode('utf-8')).hexdigest() + '.mp3')).exists()]
    check('例句音频 24,328 全到齐', not missing,
          f'缺 {len(missing)} 例: {missing[0] if missing else ""}')

    # --- MyBook 槽位2 与 SaveFile ---
    payload = json.loads((OUT / 'catbar_french_book.json').read_text(encoding='utf-8'))
    book = json.loads((data / 'MyBook.es3').read_text(encoding='utf-8'))
    slot2 = book.get('SelfBookList2', {}).get('value', [])
    check('MyBook 槽位2 = 8,116 词', len(slot2) == 8116, f'实际 {len(slot2)}')
    check('MyBook 槽位2 词表与 payload 一致', slot2 == payload['words'])
    dict2 = book.get('wordDictionary2', {}).get('value', {})
    check('MyBook wordDictionary2 释义 8,116', len(dict2) == 8116, f'实际 {len(dict2)}')
    original_book = json.loads(real_mybook.read_text(encoding='utf-8'))
    slot1_preserved = book.get('SelfBookList1') == original_book.get('SelfBookList1')
    check('槽位一(日语书)原样保留', slot1_preserved)
    check('MyBook 全部键保留', set(book) == set(original_book),
          f'丢失 {sorted(set(original_book) - set(book))[:3]}')
    if real_save.exists():
        save = json.loads((data / 'SaveFile.es3').read_text(encoding='utf-8'))
        original_save = json.loads(real_save.read_text(encoding='utf-8'))
        check('SaveFile 选中书目 = 自定义词书二',
              save.get('ChosenBook_Para', {}).get('value') == '自定义词书二')
        check('SaveFile ChosenBook_List = 法语词表',
              save.get('ChosenBook_List', {}).get('value') == payload['words'])
        check('SaveFile SelfBookName2 昵称',
              save.get('SelfBookName2', {}).get('value') == '法语词库(猫条版)')
        check('SaveFile 其它字段未被改动',
              set(save) == set(original_save),
              f'多出 {sorted(set(save) - set(original_save))[:3]}')

    # --- 真实目录未被触碰 ---
    for path, digest in real_hashes.items():
        check(f'真实文件未被改写 {Path(path).name}', sha256(Path(path)) == digest)

    server.shutdown()
    if not keep:
        shutil.rmtree(SANDBOX, ignore_errors=True)

    print()
    if failures:
        print(f'FAILED: {len(failures)}/{checks} 项未通过: {failures[:5]}')
        sys.exit(1)
    print(f'ALL PASS ({checks}/{checks}) — 一键安装链路沙箱验证通过')


if __name__ == '__main__':
    main()
