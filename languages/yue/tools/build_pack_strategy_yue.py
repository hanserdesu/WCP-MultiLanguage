# -*- coding: utf-8 -*-
"""编译 packs/yue/WcpPack.Yue.dll 统一架构策略程序集"""
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
import wcp_paths

CSC = r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"


def main():
    game_dir = wcp_paths.game_dir()
    mgd = game_dir / "wcp_Data" / "Managed"

    host_dll = Path("D:/ATooManyLanguage/Japanese/mod_host/WcpHost.dll")
    if not host_dll.exists():
        print(f"警告: {host_dll} 不存在")
        sys.exit(1)

    out_dll = ROOT / "packs" / "yue" / "WcpPack.Yue.dll"
    source = ROOT / "packs" / "yue" / "CantoneseStrategy.cs"

    refs = [
        host_dll,
        mgd / "netstandard.dll",
        mgd / "mscorlib.dll",
        mgd / "System.dll",
        mgd / "System.Core.dll",
        mgd / "System.Data.dll",
        mgd / "Mono.Data.Sqlite.dll"
    ]

    cmd = [
        CSC, "/nologo", "/noconfig", "/nostdlib+", "/target:library",
        "/langversion:5", "/optimize+", "/codepage:65001",
    ]
    for r in refs:
        cmd.append(f"/r:{r}")
    cmd.append(f"/out:{out_dll}")
    cmd.append(str(source))

    print(f"=== 编译 WcpPack.Yue.dll ===")
    res = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if res.returncode != 0:
        print("编译失败:")
        print(res.stdout)
        print(res.stderr)
        sys.exit(1)
    print(f"编译成功 -> {out_dll} ({out_dll.stat().st_size} 字节)")


if __name__ == '__main__':
    main()
