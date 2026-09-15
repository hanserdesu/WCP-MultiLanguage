# -*- coding: utf-8 -*-
"""一键生成并编译粤语三大运行时 Mod (BookNameMod, YueWordListMod, SentenceAudioYueMod)"""
import os
import re
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
INTEGRATION_ROOT = ROOT.parent
GERMAN_ROOT = INTEGRATION_ROOT / "German"
sys.path.insert(0, str(ROOT / 'tools'))
import wcp_paths

CSC = r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"


def prepare_sources():
    # 1. 确保三个目录存在，并同步 BookProfiles.cs
    bp_src = ROOT / "mod_book_name" / "BookProfiles.cs"
    bp_text = bp_src.read_text(encoding='utf-8')

    for m in ["mod_book_name", "mod_yue_wordlist", "mod_sentence_audio_yue"]:
        d = ROOT / m
        d.mkdir(parents=True, exist_ok=True)
        (d / "BookProfiles.cs").write_text(bp_text, encoding='utf-8')

    # 2. Diag.cs
    de_bn = GERMAN_ROOT / "mod_book_name"
    bn_yue = ROOT / "mod_book_name"
    diag_text = (de_bn / "Diag.cs").read_text(encoding='utf-8')
    (bn_yue / "Diag.cs").write_text(diag_text, encoding='utf-8')

    # 3. BookNameMod.cs
    bn_text = (de_bn / "BookNameMod.cs").read_text(encoding='utf-8')
    if 'BookProfiles.Cantonese' not in bn_text:
        bn_text = bn_text.replace(
            'if (profile.Language == BookProfiles.German) return "DE";',
            'if (profile.Language == BookProfiles.German) return "DE";\n'
            '            if (profile.Language == BookProfiles.Cantonese) return "YUE";'
        )
    (bn_yue / "BookNameMod.cs").write_text(bn_text, encoding='utf-8')

    # 4. SentenceAudioYueMod.cs
    sa_de_text = (GERMAN_ROOT / "mod_sentence_audio_de" / "SentenceAudioDeMod.cs").read_text(encoding='utf-8')
    sa_yue_text = sa_de_text
    sa_yue_text = sa_yue_text.replace("dev.hanserdesu.sentaudio.de", "dev.hanserdesu.sentaudio.yue")
    sa_yue_text = sa_yue_text.replace("WCP Sentence Audio DE", "WCP Sentence Audio YUE")
    sa_yue_text = sa_yue_text.replace("SentenceAudioDe", "SentenceAudioYue")
    sa_yue_text = sa_yue_text.replace("DeSentenceAudioPlugin", "YueSentenceAudioPlugin")
    sa_yue_text = sa_yue_text.replace("DeReadBtnState", "YueReadBtnState")
    sa_yue_text = sa_yue_text.replace("DeSentencePlayButton", "YueSentencePlayButton")
    sa_yue_text = sa_yue_text.replace("DeSentenceState", "YueSentenceState")
    sa_yue_text = sa_yue_text.replace("ExtractDe", "ExtractYue")
    sa_yue_text = sa_yue_text.replace("BookProfiles.German", "BookProfiles.Cantonese")
    sa_yue_text = sa_yue_text.replace("de_sentence_audio", "yue_sentence_audio")
    sa_yue_text = sa_yue_text.replace('"DE"', '"YUE"')
    sa_yue_text = sa_yue_text.replace("德语", "粤语")

    sa_yue_text = sa_yue_text.replace(
        'private static readonly Regex GermanTextRegex = new Regex(@"[A-Za-zÄÖÜäöüß]", RegexOptions.Compiled);',
        '// 粤语例句提取：检测汉字与粤拼\n'
        '        private static readonly Regex CantoneseTextRegex = new Regex(@"[\\u4e00-\\u9fa5]", RegexOptions.Compiled);'
    )
    sa_yue_text = sa_yue_text.replace("GermanTextRegex", "CantoneseTextRegex")
    (ROOT / "mod_sentence_audio_yue" / "SentenceAudioYueMod.cs").write_text(sa_yue_text, encoding='utf-8')

    # 5. YueWordListMod.cs
    wl_de_text = (GERMAN_ROOT / "mod_de_wordlist" / "DeWordListMod.cs").read_text(encoding='utf-8')
    wl_yue_text = wl_de_text
    wl_yue_text = wl_yue_text.replace("dev.hanserdesu.dewordlist", "dev.hanserdesu.yuewordlist")
    wl_yue_text = wl_yue_text.replace("WCP German Word List Isolation", "WCP Cantonese Word List Isolation")
    wl_yue_text = wl_yue_text.replace("DeWordListPlugin", "YueWordListPlugin")
    wl_yue_text = wl_yue_text.replace("DeWordList", "YueWordList")
    wl_yue_text = wl_yue_text.replace("DeWL_", "YueWL_")
    wl_yue_text = wl_yue_text.replace("DeBookProfiles", "YueBookProfiles")
    wl_yue_text = wl_yue_text.replace("BookProfiles.German", "BookProfiles.Cantonese")
    wl_yue_text = wl_yue_text.replace("de_word_audio", "yue_word_audio")
    wl_yue_text = wl_yue_text.replace("de_db_payload", "yue_db_payload")
    wl_yue_text = wl_yue_text.replace("de_pron.tsv", "yue_pron.tsv")
    wl_yue_text = wl_yue_text.replace("de_sentences.tsv", "yue_sentences.tsv")
    wl_yue_text = wl_yue_text.replace("de_only_pron.tsv", "yue_only_pron.tsv")
    wl_yue_text = wl_yue_text.replace("德语", "粤语")
    wl_yue_text = wl_yue_text.replace('"DE"', '"YUE"')
    wl_yue_text = wl_yue_text.replace(
        'new string[] { "gehen", "haben", "müssen" }',
        'new string[] { "食", "睇", "搞掂" }'
    )
    (ROOT / "mod_yue_wordlist" / "YueWordListMod.cs").write_text(wl_yue_text, encoding='utf-8')
    print("源码准备与多语言适配完成。")


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

    # 2. SentenceAudioYueMod
    dir_sa = ROOT / "mod_sentence_audio_yue"
    ok2 = build_mod(
        "SentenceAudioYueMod",
        [dir_sa / "SentenceAudioYueMod.cs", dir_sa / "BookProfiles.cs"],
        dir_sa / "SentenceAudioYueMod.dll"
    )

    # 3. YueWordListMod
    dir_wl = ROOT / "mod_yue_wordlist"
    ok3 = build_mod(
        "YueWordListMod",
        [dir_wl / "YueWordListMod.cs", dir_wl / "BookProfiles.cs"],
        dir_wl / "YueWordListMod.dll",
        extra_refs=["System.Data.dll", "Mono.Data.Sqlite.dll"]
    )

    if ok1 and ok2 and ok3:
        print("\n>>> 粤语三大运行时 Mod 全部编译成功！<<<")
    else:
        print("\n>>> 有 Mod 编译失败，请检查错误。<<<")
        sys.exit(1)


if __name__ == '__main__':
    main()
