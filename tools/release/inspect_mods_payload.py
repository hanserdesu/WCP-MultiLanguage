# -*- coding: utf-8 -*-
"""检查现网 mods 载荷的条目结构（对照新构建用）。

用法: python tools/release/inspect_mods_payload.py <zip 路径或 URL>
"""
import sys
import urllib.request
import zipfile
from pathlib import Path

PROXY = 'http://127.0.0.1:7897'


def fetch(url: str, dest: Path) -> Path:
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({'http': PROXY, 'https': PROXY}))
    with opener.open(url, timeout=60) as resp, open(dest, 'wb') as out:
        out.write(resp.read())
    return dest


def main() -> int:
    src = sys.argv[1] if len(sys.argv) > 1 else (
        'https://github.com/hanserdesu/WCP-MultiLanguage/releases/download/'
        'wcp-mods-v1.1.0/wcp-mods-payload.zip')
    if src.startswith('http'):
        dest = Path(__file__).resolve().parent.parent.parent / '_local' / 'inspect-mods-payload.zip'
        dest.parent.mkdir(parents=True, exist_ok=True)
        fetch(src, dest)
        path = dest
    else:
        path = Path(src)
    with zipfile.ZipFile(path) as zf:
        for info in zf.infolist():
            print('%-42s compress=%d size=%-8d crc=%08x' % (
                info.filename, info.compress_type, info.file_size, info.CRC))
        print('总条目:', len(zf.infolist()))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
