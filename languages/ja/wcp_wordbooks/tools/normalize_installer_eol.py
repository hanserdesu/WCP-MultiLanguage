# -*- coding: utf-8 -*-
"""Normalize installer script line endings for Windows packaging.

Git autocrlf leaves .ps1 files with mixed EOL on disk; cmd.exe is strict
about its own scripts and PowerShell progress blocks break on LF-only lines
in some editors. Running this before packaging makes every script CRLF.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / 'installer'
TARGETS = ['Install-WCP-Japanese.ps1', 'run-installer.ps1',
           'check-compatibility.ps1', 'compatibility-help.cmd',
           '一键安装日语词书.cmd']


def main():
    for name in TARGETS:
        path = ROOT / name
        if not path.exists():
            continue
        data = path.read_bytes().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
        path.write_bytes(data)
        print(f'normalized {name}')


if __name__ == '__main__':
    main()

