# -*- coding: utf-8 -*-
"""构建可发布的 Gitee/GitHub Release 资源。

生成三类文件：
  1. WCP日语词书一键安装包-<tag>.zip  核心安装器和词书
  2. wcp-japanese-audio-words.zip   单词音频
  3. wcp-japanese-audio-sentences.zip 例句音频

核心包不内嵌大音频；Install-WCP-Japanese.ps1 按本清单探测 Gitee/GitHub
下载路由并校验两份音频，确保群友安装后的运行资源与作者本机一致。
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'output'
PKG = OUT / 'installer_pkg' / 'WCP日语词书安装包'
RELEASE = OUT / 'release'
# 宿主升级（0.3.0：词池只从当前词书重建 + 旧词表插件让位）之后必须换新 tag，
# 免得同一个 tag 下的 Release 资源被静默替换。可用环境变量覆盖。
MAIN_TAG = os.environ.get('WCP_MAIN_TAG', 'wcp-jp-v1.2.3')
RESOURCE_TAG = 'wcp-jp-resources-v1.1.0'
GITEE_REPO = os.environ.get(
    'WCP_GITEE_REPO',
    'https://gitee.com/cat-stripe/code-warehouse-for-cat-stripes',
).rstrip('/')
GITEE_URL_TEMPLATE = os.environ.get(
    'WCP_GITEE_URL_TEMPLATE',
    f'{GITEE_REPO}/releases/download/{RESOURCE_TAG}/{{name}}',
)
# Gitee applies a repository-wide attachment quota. Keep the source release
# as the primary domestic route, and place the remaining resource parts in
# two small resource-only repositories. Each part carries its own URL so the
# installer can span these repositories without changing the route contract.
GITEE_WORDS_REPO = os.environ.get(
    'WCP_GITEE_WORDS_REPO',
    'https://gitee.com/cat-stripe/wcp-jp-audio-words',
).rstrip('/')
GITEE_SENTENCES_REPO = os.environ.get(
    'WCP_GITEE_SENTENCES_REPO',
    'https://gitee.com/cat-stripe/wcp-jp-audio-sentences',
).rstrip('/')
GITEE_PRIMARY_SENTENCE_PARTS = int(
    os.environ.get('WCP_GITEE_PRIMARY_SENTENCE_PARTS', '22')
)
# Stay below the strict 50 MB single-file quota so the same parts can be
# uploaded even when a Gitee account applies repository-style limits.
GITEE_PART_SIZE = 45 * 1024 * 1024


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def zip_tree(source, target):
    if target.exists():
        target.unlink()
    files = [p for p in source.rglob('*') if p.is_file() and p.stat().st_size > 1000]
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_STORED, allowZip64=True) as z:
        for p in files:
            z.write(p, p.relative_to(source).as_posix())
    print(f'{target.name}: {len(files)} files, {target.stat().st_size / 1e9:.3f} GB')


def split_file(source, target_dir):
    """Split one resource for Gitee's per-attachment limit.

    The parts stay byte-for-byte concatenable. Each part is independently
    hashed so the installer can resume valid parts and reject corrupt ones.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    for old in target_dir.glob(source.name + '.*'):
        if old.is_file():
            old.unlink()
    parts = []
    with source.open('rb') as src:
        index = 0
        while True:
            block = src.read(GITEE_PART_SIZE)
            if not block:
                break
            index += 1
            part = target_dir / f'{source.name}.{index:03d}'
            part.write_bytes(block)
            parts.append({'name': part.name, 'size': part.stat().st_size,
                          'sha256': sha256(part)})
    print(f'{source.name}: {len(parts)} Gitee parts')
    return parts


def add_gitee_part_urls(parts, kind):
    """Attach the domestic Release URL for each generated split part.

    Gitee enforces a ~1 GB per-repository attachment quota, so the 32
    sentence parts cannot live in one repository.  Actual placement
    (verified 2026-09-15, 38/38 asset URLs reachable):
      word parts 001-004            -> wcp-jp-audio-words
      sentence parts 001-022        -> wcp-jp-audio-sentences
      sentence parts 023-032        -> wcp-jp-audio-words (quota spill)
    """
    for index, part in enumerate(parts, start=1):
        if kind == 'word_audio':
            repo = GITEE_WORDS_REPO
        elif index <= GITEE_PRIMARY_SENTENCE_PARTS:
            repo = GITEE_SENTENCES_REPO
        else:
            repo = GITEE_WORDS_REPO
        part['url_template'] = (
            f'{repo}/releases/download/{RESOURCE_TAG}/{{name}}'
        )


def zip_uncompressed_size(path):
    with zipfile.ZipFile(path) as archive:
        return sum(info.file_size for info in archive.infolist())


def build_core():
    subprocess.run([sys.executable, str(ROOT / 'tools' / 'build_installer_payload.py'),
                    '--skip-audio'], check=True)


def main():
    build_core()
    audio_root = Path.home() / 'AppData' / 'LocalLow' / 'WCP'
    legacy_sentences = audio_root / 'wcp' / 'ja_sentence_audio'
    sentences = audio_root / 'packs' / 'ja' / 'audio' / 'sentence'
    if not sentences.is_dir():
        sentences = legacy_sentences
    shared_words = audio_root / 'vocabulary'
    private_words = audio_root / 'packs' / 'ja' / 'audio' / 'word'
    if not (private_words.is_dir() or shared_words.is_dir()) or not sentences.is_dir():
        raise FileNotFoundError('本机单词音频或例句音频目录不存在')
    RELEASE.mkdir(parents=True, exist_ok=True)
    word_zip = RELEASE / 'wcp-japanese-audio-words.zip'
    sentence_zip = RELEASE / 'wcp-japanese-audio-sentences.zip'
    if '--reuse-audio' not in sys.argv or not word_zip.exists():
        sys.path.insert(0, str(ROOT / 'tools'))
        from build_installer_payload import stage_word_audio
        from patch_local_db import collect
        word_stage = RELEASE / '.japanese_word_audio_stage'
        stage_word_audio(collect().keys(), word_stage)
        try:
            zip_tree(word_stage, word_zip)
        finally:
            if word_stage.exists():
                shutil.rmtree(word_stage)
    else:
        print(f'reuse {word_zip.name}')
    if '--reuse-audio' not in sys.argv or not sentence_zip.exists():
        zip_tree(sentences, sentence_zip)
    else:
        print(f'reuse {sentence_zip.name}')

    base = f'https://github.com/hanserdesu/japanese/releases/download/{RESOURCE_TAG}'
    assets = []
    gitee_parts = RELEASE / 'gitee-parts'
    for kind, path in (('word_audio', word_zip), ('sentence_audio', sentence_zip)):
        parts = split_file(path, gitee_parts)
        add_gitee_part_urls(parts, kind)
        assets.append({'kind': kind, 'name': path.name,
                       'size': path.stat().st_size,
                       'expanded_size': zip_uncompressed_size(path),
                       'sha256': sha256(path),
                       'parts': parts})
    release_manifest = {
        'version': RESOURCE_TAG,
        'built': time.strftime('%Y-%m-%d %H:%M:%S'),
        # Keep base_urls for older installers. New installers use route
        # metadata and can probe a domestic mirror before falling back to GitHub.
        'base_urls': [base],
        'download_routes': [
            {'id': 'gitee', 'name': '国内 Gitee Release', 'mode': 'parts',
             'url_template': GITEE_URL_TEMPLATE},
            {'id': 'github', 'name': 'GitHub Release',
             'url_template': base + '/{name}'},
        ],
        'assets': assets,
    }
    manifest = RELEASE / 'release-manifest.json'
    with manifest.open('w', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(release_manifest, ensure_ascii=False, indent=2) + '\n')
    shutil.copy2(manifest, PKG / 'support' / 'release-manifest.json')

    # release-index：自更新检查的数据源（installer_version + 新包 SHA-256）。
    # core_zip 的文件名在这里先定下来（SHA 待 zip 打包后回填）。
    core_zip = RELEASE / f'WCP-Japanese-OneClick-Installer-{MAIN_TAG}.zip'
    index = RELEASE / 'release-index.json'
    with index.open('w', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps({
            'main_release': MAIN_TAG,
            'resource_release': RESOURCE_TAG,
            # 安装器自更新比对用：老版本安装器读到与自身不同的值时提示升级。
            'installer_version': MAIN_TAG,
            'core_installer': {'name': core_zip.name},
            'resource_manifest': manifest.name,
        }, ensure_ascii=False, indent=2) + '\n')
    # 把 index 同步进安装包 support/（自更新检查直接读资源 Release 上的这份），
    # 并保留一份在 output/release/ 供上传脚本使用。
    shutil.copy2(index, PKG / 'support' / 'release-index.json')

    # GitHub release uploads can mangle non-ASCII asset names. Keep the
    # downloadable filename ASCII; the archive itself remains Chinese-first.
    # 注意：zip 必须在 index/manifest 都拷入 PKG 之后打包。
    if core_zip.exists():
        core_zip.unlink()
    with zipfile.ZipFile(core_zip, 'w', zipfile.ZIP_DEFLATED, allowZip64=True) as z:
        for p in PKG.rglob('*'):
            if p.is_file():
                z.write(p, p.relative_to(PKG.parent).as_posix())
    # zip 打包完成后回填 size/sha256 —— 自更新必须校验完整包。
    with index.open('w', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps({
            'main_release': MAIN_TAG,
            'resource_release': RESOURCE_TAG,
            'installer_version': MAIN_TAG,
            'core_installer': {'name': core_zip.name, 'size': core_zip.stat().st_size,
                               'sha256': sha256(core_zip)},
            'resource_manifest': manifest.name,
        }, ensure_ascii=False, indent=2) + '\n')
    print('release manifest:', manifest)
    print('release files:', RELEASE)


if __name__ == '__main__':
    main()
