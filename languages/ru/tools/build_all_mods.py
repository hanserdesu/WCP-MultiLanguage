# -*- coding: utf-8 -*-
"""一键编译俄语三大运行时 Mod 并输出到各 mod 目录 (及可选部署到游戏 plugins)"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
import wcp_paths

CSC = r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"

def build_mod(name, sources, out_dll, extra_refs=None):
    game_dir = wcp_paths.game_dir()
    mgd = game_dir / "wcp_Data" / "Managed"
    bep_core = game_dir / "BepInEx" / "core"
    
    refs = [
        bep_core / "BepInEx.dll",
        bep_core / "0Harmony.dll",
        mgd / "Assembly-CSharp.dll",
        mgd / "Assembly-CSharp-firstpass.dll",
        mgd / "netstandard.dll",
        mgd / "mscorlib.dll",
        mgd / "System.dll",
        mgd / "System.Core.dll",
        mgd / "UnityEngine.dll",
        mgd / "UnityEngine.CoreModule.dll",
        mgd / "UnityEngine.UIModule.dll",
        mgd / "UnityEngine.AudioModule.dll",
        mgd / "UnityEngine.UnityWebRequestModule.dll",
        mgd / "UnityEngine.UnityWebRequestAudioModule.dll",
        mgd / "UnityEngine.UI.dll",
        mgd / "UnityEngine.TextRenderingModule.dll",
        mgd / "Unity.TextMeshPro.dll",
    ]
    if extra_refs:
        for r in extra_refs:
            refs.append(mgd / r)
            
    cmd = [
        CSC, "/nologo", "/noconfig", "/nostdlib+", "/target:library",
        "/langversion:5", "/optimize+", "/codepage:65001",
    ]
    for r in refs:
        cmd.append(f"/r:{r}")
    cmd.append(f"/out:{out_dll}")
    for s in sources:
        cmd.append(str(s))
        
    print(f"=== 编译 {name} ===")
    res = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if res.returncode != 0:
        print("编译失败:")
        print(res.stdout)
        print(res.stderr)
        return False
    print(f"编译成功 -> {out_dll.name} ({out_dll.stat().st_size} 字节)")
    
    # 部署
    plugins_dir = game_dir / "BepInEx" / "plugins"
    if plugins_dir.exists():
        target = plugins_dir / out_dll.name
        try:
            target.write_bytes(out_dll.read_bytes())
            print(f"已自动部署到 {target}")
        except Exception as e:
            print(f"自动部署跳过 (可能游戏正在运行): {e}")
    return True

def main():
    print("游戏目录:", wcp_paths.game_dir())
    
    # 1. BookNameMod
    dir_bn = ROOT / "mod_book_name"
    ok1 = build_mod(
        "BookNameMod",
        [dir_bn / "BookNameMod.cs", dir_bn / "BookProfiles.cs", dir_bn / "Diag.cs"],
        dir_bn / "BookNameMod.dll"
    )
    
    # 2. SentenceAudioRuMod
    dir_sa = ROOT / "mod_sentence_audio_ru"
    ok2 = build_mod(
        "SentenceAudioRuMod",
        [dir_sa / "SentenceAudioRuMod.cs", dir_sa / "BookProfiles.cs"],
        dir_sa / "SentenceAudioRuMod.dll"
    )
    
    # 3. RuWordListMod
    dir_wl = ROOT / "mod_ru_wordlist"
    ok3 = build_mod(
        "RuWordListMod",
        [dir_wl / "RuWordListMod.cs", dir_wl / "BookProfiles.cs"],
        dir_wl / "RuWordListMod.dll",
        extra_refs=["System.Data.dll", "Mono.Data.Sqlite.dll"]
    )
    
    if ok1 and ok2 and ok3:
        print("\n>>> 所有三大 Mod 全部编译成功并就绪！<<<")
    else:
        print("\n>>> 有 Mod 编译失败，请检查错误。<<<")
        sys.exit(1)

if __name__ == '__main__':
    main()
