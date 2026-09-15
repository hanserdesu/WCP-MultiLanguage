# -*- coding: utf-8 -*-
"""一键生成并编译德语三大运行时 Mod 并输出到各 mod 目录及部署到游戏 plugins"""
import os
import re
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
INTEGRATION_ROOT = ROOT.parent
JAPANESE_ROOT = INTEGRATION_ROOT / "Japanese"
FRENCH_ROOT = INTEGRATION_ROOT / "French"
sys.path.insert(0, str(ROOT / 'tools'))
import wcp_paths

CSC = r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"


def prepare_sources():
    # 1. BookProfiles.cs 复制到三个 mod 目录
    bp_src = ROOT / "mod_book_name" / "BookProfiles.cs"
    if not bp_src.exists():
        bp_src = JAPANESE_ROOT / "mod_book_name" / "BookProfiles.cs"
    bp_text = bp_src.read_text(encoding='utf-8')

    for m in ["mod_book_name", "mod_de_wordlist", "mod_sentence_audio_de"]:
        d = ROOT / m
        d.mkdir(parents=True, exist_ok=True)
        (d / "BookProfiles.cs").write_text(bp_text, encoding='utf-8')

    # 2. BookNameMod.cs & Diag.cs 从 French 复制并适配
    fr_bn = FRENCH_ROOT / "mod_book_name"
    bn_de = ROOT / "mod_book_name"
    diag_text = (fr_bn / "Diag.cs").read_text(encoding='utf-8')
    (bn_de / "Diag.cs").write_text(diag_text, encoding='utf-8')

    bn_text = (fr_bn / "BookNameMod.cs").read_text(encoding='utf-8')
    # 确保 VoiceLabelFor 支持 DE
    if 'BookProfiles.German' not in bn_text:
        bn_text = bn_text.replace(
            'if (profile.Language == BookProfiles.French) return "FR";',
            'if (profile.Language == BookProfiles.French) return "FR";\n'
            '            if (profile.Language == BookProfiles.German) return "DE";'
        )
    (bn_de / "BookNameMod.cs").write_text(bn_text, encoding='utf-8')

    # 3. SentenceAudioDeMod.cs 从 French 适配
    sa_fr_text = (FRENCH_ROOT / "mod_sentence_audio_fr" / "SentenceAudioFrMod.cs").read_text(encoding='utf-8')
    # 替换命名空间与类名
    sa_de_text = sa_fr_text
    sa_de_text = sa_de_text.replace("dev.hanserdesu.sentaudio.fr", "dev.hanserdesu.sentaudio.de")
    sa_de_text = sa_de_text.replace("WCP Sentence Audio FR", "WCP Sentence Audio DE")
    sa_de_text = sa_de_text.replace("SentenceAudioFr", "SentenceAudioDe")
    sa_de_text = sa_de_text.replace("FrSentenceAudioPlugin", "DeSentenceAudioPlugin")
    sa_de_text = sa_de_text.replace("FrReadBtnState", "DeReadBtnState")
    sa_de_text = sa_de_text.replace("FrSentencePlayButton", "DeSentencePlayButton")
    sa_de_text = sa_de_text.replace("FrSentenceState", "DeSentenceState")
    sa_de_text = sa_de_text.replace("ExtractFr", "ExtractDe")
    sa_de_text = sa_de_text.replace("BookProfiles.French", "BookProfiles.German")
    sa_de_text = sa_de_text.replace("fr_sentence_audio", "de_sentence_audio")
    sa_de_text = sa_de_text.replace('"FR"', '"DE"')
    sa_de_text = sa_de_text.replace("法语", "德语")
    (ROOT / "mod_sentence_audio_de" / "SentenceAudioDeMod.cs").write_text(sa_de_text, encoding='utf-8')

    # 4. DeWordListMod.cs 从 French 适配
    wl_fr_text = (FRENCH_ROOT / "mod_fr_wordlist" / "FrWordListMod.cs").read_text(encoding='utf-8')
    wl_de_text = wl_fr_text
    wl_de_text = wl_de_text.replace("dev.hanserdesu.frwordlist", "dev.hanserdesu.dewordlist")
    wl_de_text = wl_de_text.replace("WCP French Word List Isolation", "WCP German Word List Isolation")
    wl_de_text = wl_de_text.replace("FrWordListPlugin", "DeWordListPlugin")
    wl_de_text = wl_de_text.replace("FrWordList", "DeWordList")
    wl_de_text = wl_de_text.replace("FrWL_", "DeWL_")
    wl_de_text = wl_de_text.replace("FrBookProfiles", "DeBookProfiles")
    wl_de_text = wl_de_text.replace("BookProfiles.French", "BookProfiles.German")
    wl_de_text = wl_de_text.replace("fr_word_audio", "de_word_audio")
    wl_de_text = wl_de_text.replace("fr_db_payload", "de_db_payload")
    wl_de_text = wl_de_text.replace("fr_pron.tsv", "de_pron.tsv")
    wl_de_text = wl_de_text.replace("fr_sentences.tsv", "de_sentences.tsv")
    wl_de_text = wl_de_text.replace("fr_only_pron.tsv", "de_only_pron.tsv")
    wl_de_text = wl_de_text.replace("FR", "DE")
    wl_de_text = wl_de_text.replace("法语", "德语")
    # Shared SQLite ownership is asymmetric: the French build restores the
    # English baseline for Japanese/Russian, while German owns the database
    # only for the German profile.  Adapt the generated guard accordingly.
    wl_de_text = wl_de_text.replace(
        'if (state != 1 && CurrentManagedLanguage() == BookProfiles.German)\n'
        '                return; // 德语插件拥有共享库时，德语侧保持只读',
        'string currentLanguage = CurrentManagedLanguage();\n'
        '            if (state != 1 && currentLanguage != null &&\n'
        '                currentLanguage != BookProfiles.German)\n'
        '                return; // 其它受管词书由其语言插件/法语侧负责共享库')
    # Protect against a stale generated template containing the historical
    # typo that produced "near pron" on every German tick.
    wl_de_text = wl_de_text.replace(" DEOM ", " FROM ")
    # The French template carries French-only DB probes. Keep the generated
    # German mod aligned with packs/de/manifest.json instead of silently
    # validating the wrong language's repair payload.
    wl_de_text = wl_de_text.replace(
        'new string[] { "être", "coing", "vaguement" }',
        'new string[] { "gehen", "haben", "müssen" }')
    (ROOT / "mod_de_wordlist" / "DeWordListMod.cs").write_text(wl_de_text, encoding='utf-8')
    print("源码模板与配置文件准备就绪！")


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
    prepare_sources()
    print("游戏目录:", wcp_paths.game_dir())

    # 1. BookNameMod
    dir_bn = ROOT / "mod_book_name"
    ok1 = build_mod(
        "BookNameMod",
        [dir_bn / "BookNameMod.cs", dir_bn / "BookProfiles.cs", dir_bn / "Diag.cs"],
        dir_bn / "BookNameMod.dll"
    )

    # 2. SentenceAudioDeMod
    dir_sa = ROOT / "mod_sentence_audio_de"
    ok2 = build_mod(
        "SentenceAudioDeMod",
        [dir_sa / "SentenceAudioDeMod.cs", dir_sa / "BookProfiles.cs"],
        dir_sa / "SentenceAudioDeMod.dll"
    )

    # 3. DeWordListMod
    dir_wl = ROOT / "mod_de_wordlist"
    ok3 = build_mod(
        "DeWordListMod",
        [dir_wl / "DeWordListMod.cs", dir_wl / "BookProfiles.cs"],
        dir_wl / "DeWordListMod.dll",
        extra_refs=["System.Data.dll", "Mono.Data.Sqlite.dll"]
    )

    if ok1 and ok2 and ok3:
        print("\n>>> 德语三大运行时 Mod 全部编译成功并已部署到游戏 plugins！<<<")
    else:
        print("\n>>> 有 Mod 编译失败，请检查错误。<<<")
        sys.exit(1)


if __name__ == '__main__':
    main()
