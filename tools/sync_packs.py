"""把各语言工程的 packs/<lang> 物化产物同步进 MultiLanguage/packs/<lang>。

- 只新增/覆盖双方都有的"构建产物"文件（manifest/books/db/audio 索引），
  不删除 ML 仓库里的多余文件（那是 pack_payload 时代遗留，另行处理）。
- manifest 以语言工程为准（项目里的 manifest 是 build_pack 生成物，语义最新）。
- 同步后逐文件 sha256 校验。
- --deploy/--check-deployed 是下一段链路：hub packs → 游戏实际加载的
  %USERPROFILE%\\AppData\\LocalLow\\WCP\\packs。只复制宿主读取的运行时文件，
  不碰音频、不删除任何部署侧文件。
用法: python tools/sync_packs.py [--check | --deploy | --check-deployed]
"""
import argparse
import hashlib
import json
import os
import shutil
import sys

SEP = chr(92)
HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(HUB)
PROJECTS = [('Japanese', 'ja'), ('French', 'fr'), ('Russian', 'ru'), ('German', 'de'),
            ('Contonese', 'yue'), ('Spanish', 'es'), ('Portuguese', 'pt'),
            ('Arabic', 'ar'), ('korean', 'ko')]

# pack 内部这些路径由语言工程持有，但仍要进仓库（宿主按 manifest 读取）。
# 不复制的东西: pack.build.json(构建配方, 仓库无需)、payload_dir 指向的源载荷。


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def collect(pack_dir):
    out = {}
    if not os.path.isdir(pack_dir):
        return out
    for root, _, names in os.walk(pack_dir):
        for n in names:
            full = os.path.join(root, n)
            rel = os.path.relpath(full, pack_dir).replace(SEP, '/')
            out[rel] = full
    return out


# 宿主运行时读取的文件。音频不在其中——部署侧音频在仓库里没有第二份，
# 所以这个名单同时是"允许被覆盖"的边界。
RUNTIME_FILES = ['manifest.json', 'db/meaning.sqlite', 'db/sentences.json', 'db/repair.tsv']


def deployed_root():
    return os.path.join(os.path.expanduser('~'), 'AppData', 'LocalLow', 'WCP', 'packs')


def deployed_diff(only_lang=None):
    """hub packs vs 部署侧 packs 的逐文件哈希差异。"""
    low = deployed_root()
    diffs = []
    for _, lang in PROJECTS:
        if only_lang and lang != only_lang:
            continue
        src = os.path.join(HUB, 'packs', lang)
        if not os.path.isdir(src):
            continue
        for rel in RUNTIME_FILES:
            s = os.path.join(src, rel.replace('/', SEP))
            if not os.path.exists(s):
                continue
            d = os.path.join(low, lang, rel.replace('/', SEP))
            if not os.path.exists(d):
                diffs.append((lang, rel, 'missing'))
            elif sha256(s) != sha256(d):
                diffs.append((lang, rel, 'content differs'))
    return diffs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='只报告差异，不复制')
    ap.add_argument('--deploy', action='store_true', help='hub packs → LocalLow 部署侧')
    ap.add_argument('--check-deployed', action='store_true', help='只报告部署侧与 hub 的哈希差异')
    args = ap.parse_args()

    if args.check_deployed or args.deploy:
        if args.deploy:
            low = deployed_root()
            for lang, rel, _ in deployed_diff():
                s = os.path.join(HUB, 'packs', lang, rel.replace('/', SEP))
                d = os.path.join(low, lang, rel.replace('/', SEP))
                os.makedirs(os.path.dirname(d), exist_ok=True)
                shutil.copy2(s, d)
                print(f'  ~ {lang}/{rel}')
        diffs = deployed_diff()
        if diffs:
            print('DEPLOY DRIFT:')
            for lang, rel, why in diffs:
                print(f'  ! {lang}/{rel}: {why}')
            sys.exit(1)
        print(f'verify-deployed: PASS（{len(PROJECTS)} 语运行时文件与 hub 逐字节一致）')
        sys.exit(0)

    problems = []
    for proj, lang in PROJECTS:
        src = os.path.join(ROOT, proj, 'packs', lang)
        dst = os.path.join(HUB, 'packs', lang)
        if not os.path.isdir(src):
            continue  # 该语言工程还没有 pack（es/pt/ko/ar），跳过
        src_files = collect(src)
        dst_files = collect(dst)
        for rel, full in sorted(src_files.items()):
            dpath = os.path.join(dst, rel.replace('/', SEP))
            if not os.path.exists(dpath):
                if args.check:
                    problems.append(f'{lang}/{rel}: missing in hub repo')
                else:
                    os.makedirs(os.path.dirname(dpath), exist_ok=True)
                    shutil.copy2(full, dpath)
                    print(f'  + {lang}/{rel}')
            elif sha256(full) != sha256(dpath):
                if args.check:
                    problems.append(f'{lang}/{rel}: content differs')
                else:
                    shutil.copy2(full, dpath)
                    print(f'  ~ {lang}/{rel} (updated)')
        if not args.check:
            print(f'{lang}: synced ({len(src_files)} files)')
    if args.check:
        if problems:
            print('DRIFT:')
            for p in problems:
                print('  !', p)
            sys.exit(1)
        print('packs 与语言工程一致')
    else:
        # 自检
        bad = 0
        for proj, lang in PROJECTS:
            src = os.path.join(ROOT, proj, 'packs', lang)
            dst = os.path.join(HUB, 'packs', lang)
            if not os.path.isdir(src):
                continue
            for rel, full in collect(src).items():
                dpath = os.path.join(dst, rel.replace('/', SEP))
                if not os.path.exists(dpath) or sha256(full) != sha256(dpath):
                    print(f'FAIL {lang}/{rel}')
                    bad += 1
        print('VERIFY:', 'PASS' if bad == 0 else f'{bad} FAIL')
        sys.exit(0 if bad == 0 else 1)


if __name__ == '__main__':
    main()
