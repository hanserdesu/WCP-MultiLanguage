# -*- coding: utf-8 -*-
"""构建可发布的 GitHub Release 资源。

生成四类文件：
  1. WCP-French-OneClick-Installer-<tag>.zip  核心安装器（不含大音频）
  2. wcp-french-audio-words.zip               单词音频 (fr_word_audio 8,116)
  3. wcp-french-audio-sentences.zip           法语例句音频 (md5(fr) 24,328)
  4. release-manifest.json / release-index.json

核心包不内嵌大音频；Install-WCP-French.ps1 按清单从 GitHub Release
下载并校验两份音频，确保群友安装后的运行资源与作者本机一致。

用法: python tools/build_release_fr.py [--reuse-audio]
"""
import hashlib
import json
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
OUT = ROOT / 'output'
PKG = OUT / 'installer_pkg' / 'WCP法语词书安装包'
RELEASE = OUT / 'release'
MAIN_TAG = 'wcp-fr-v1.0.0'
RESOURCE_TAG = 'wcp-fr-resources-v1.0.0'
REPO = 'hanserdesu/WCP-French-Wordbook'


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def zip_flat(files, target, display):
    """Flat archive: entry name = file name, stored (mp3 is already compressed)."""
    from audio_paths_fr import native_path
    files = [p for p in files if p.stat().st_size > 1000]
    if target.exists():
        target.unlink()
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_STORED, allowZip64=True) as z:
        for p in files:
            # fr_word_audio contains Windows reserved device names (aux/con/nul);
            # plain open() resolves those to devices, so read via \\?\ paths.
            z.write(native_path(p), p.name)
    print(f'{display}: {len(files)} files, {target.stat().st_size / 1e6:.0f}MB')
    return len(files)


def french_sentence_files():
    """md5(fr).mp3 files for every unique French sentence, same rule as the mod."""
    master = json.loads((ROOT / 'data' / 'translations' /
                         'sentences_master.json').read_text(encoding='utf-8'))
    audio_dir = Path.home() / 'AppData' / 'LocalLow' / 'WCP' / 'wcp' / 'fr_sentence_audio'
    sentences = set()
    for items in master.values():
        for fr, _zh in items:
            sentences.add(fr)
    files, missing = [], []
    for fr in sorted(sentences):
        p = audio_dir / (hashlib.md5(fr.encode('utf-8')).hexdigest() + '.mp3')
        (files if p.exists() else missing).append(p)
    if missing:
        raise FileNotFoundError(f'{len(missing)} 法语例句音频缺失，例: {missing[0]}')
    return files


def build_core():
    subprocess.run([sys.executable, str(ROOT / 'tools' / 'build_installer_payload_fr.py')],
                   check=True)


def main():
    build_core()
    word_dir = Path.home() / 'AppData' / 'LocalLow' / 'WCP' / 'wcp' / 'fr_word_audio'
    if not word_dir.is_dir():
        raise FileNotFoundError(f'本机法语单词音频目录不存在: {word_dir}')
    RELEASE.mkdir(parents=True, exist_ok=True)
    word_zip = RELEASE / 'wcp-french-audio-words.zip'
    sentence_zip = RELEASE / 'wcp-french-audio-sentences.zip'

    if '--reuse-audio' not in sys.argv or not word_zip.exists():
        n_words = zip_flat(sorted(word_dir.glob('*.mp3')), word_zip, '单词音频')
        if n_words != 8116:
            raise RuntimeError(f'单词音频数量异常: {n_words} != 8116')
    else:
        print(f'reuse {word_zip.name}')
    if '--reuse-audio' not in sys.argv or not sentence_zip.exists():
        n_sent = zip_flat(french_sentence_files(), sentence_zip, '例句音频')
        if n_sent != 24328:
            raise RuntimeError(f'例句音频数量异常: {n_sent} != 24328')
    else:
        print(f'reuse {sentence_zip.name}')

    base = f'https://github.com/{REPO}/releases/download/{RESOURCE_TAG}'
    assets = []
    for kind, path in (('word_audio', word_zip), ('sentence_audio', sentence_zip)):
        assets.append({'kind': kind, 'name': path.name,
                       'size': path.stat().st_size, 'sha256': sha256(path)})
    release_manifest = {
        'version': RESOURCE_TAG,
        'built': time.strftime('%Y-%m-%d %H:%M:%S'),
        'base_urls': [base],
        'assets': assets,
    }
    manifest = RELEASE / 'release-manifest.json'
    manifest.write_text(json.dumps(release_manifest, ensure_ascii=False, indent=2) + '\n',
                        encoding='utf-8')
    shutil.copy2(manifest, PKG / 'support' / 'release-manifest.json')

    # GitHub release uploads can mangle non-ASCII asset names. Keep the
    # downloadable filename ASCII; the archive itself remains Chinese-first.
    core_zip = RELEASE / f'WCP-French-OneClick-Installer-{MAIN_TAG}.zip'
    if core_zip.exists():
        core_zip.unlink()
    with zipfile.ZipFile(core_zip, 'w', zipfile.ZIP_DEFLATED, allowZip64=True) as z:
        for p in PKG.rglob('*'):
            if p.is_file():
                z.write(p, p.relative_to(PKG.parent).as_posix())
    index = RELEASE / 'release-index.json'
    index.write_text(json.dumps({
        'main_release': MAIN_TAG,
        'resource_release': RESOURCE_TAG,
        'core_installer': {'name': core_zip.name, 'size': core_zip.stat().st_size,
                           'sha256': sha256(core_zip)},
        'resource_manifest': manifest.name,
    }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('release manifest:', manifest)
    print('release files:', RELEASE)


if __name__ == '__main__':
    main()
