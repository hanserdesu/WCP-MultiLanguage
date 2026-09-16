# -*- coding: utf-8 -*-
"""构建 mods 载荷 zip（wcp-mods-payload.zip）。

条目约定：BepInEx 相对布局 plugins/<dll>，ZIP_STORED。
来源 = 仓库内规范副本：
  mod_host/WcpHost.dll、mod_custom_slots/CustomSlotsMod.dll、mod_book_name/BookNameMod.dll
  + languages/<lang>/ 下的 8 个语言词表/例句插件（de/fr/ru/yue，收敛版：
    只读 pack，Legacy/*Fallback 开关保留）。
    注：日语一键包自带 ja 系 5 插件；载荷里带上全部通用插件，保证任何
    渠道装完都是收敛版（覆盖用户机上可能残留的旧版 legacy 回退 DLL）。

用法: python tools/release/build_mods_payload.py [输出路径]
默认输出: MultiLanguage/_local/wcp-mods-payload.zip

打包后回读逐条目比对（大小 + CRC），并打印 size/sha256 供 catalog 更新。
发布（草稿→回读校验→发布→公开 URL 回读）见 references/moddev-release.md。
"""
import hashlib
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
FILES = [
    ('plugins/WcpHost.dll', ROOT / 'mod_host' / 'WcpHost.dll'),
    ('plugins/CustomSlotsMod.dll', ROOT / 'mod_custom_slots' / 'CustomSlotsMod.dll'),
    ('plugins/BookNameMod.dll', ROOT / 'mod_book_name' / 'BookNameMod.dll'),
    ('plugins/FrWordListMod.dll', ROOT.parent / 'French' / 'mod_fr_wordlist' / 'FrWordListMod.dll'),
    ('plugins/SentenceAudioFrMod.dll', ROOT.parent / 'French' / 'mod_sentence_audio_fr' / 'SentenceAudioFrMod.dll'),
    ('plugins/DeWordListMod.dll', ROOT.parent / 'German' / 'mod_de_wordlist' / 'DeWordListMod.dll'),
    ('plugins/SentenceAudioDeMod.dll', ROOT.parent / 'German' / 'mod_sentence_audio_de' / 'SentenceAudioDeMod.dll'),
    ('plugins/RuWordListMod.dll', ROOT.parent / 'Russian' / 'mod_ru_wordlist' / 'RuWordListMod.dll'),
    ('plugins/SentenceAudioRuMod.dll', ROOT.parent / 'Russian' / 'mod_sentence_audio_ru' / 'SentenceAudioRuMod.dll'),
    ('plugins/YueWordListMod.dll', ROOT.parent / 'Contonese' / 'mod_yue_wordlist' / 'YueWordListMod.dll'),
    ('plugins/SentenceAudioYueMod.dll', ROOT.parent / 'Contonese' / 'mod_sentence_audio_yue' / 'SentenceAudioYueMod.dll'),
]


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        ROOT / '_local' / 'wcp-mods-payload.zip')
    out.parent.mkdir(parents=True, exist_ok=True)
    for _, src in FILES:
        if not src.is_file():
            print('缺少源 DLL: %s' % src)
            return 1
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_STORED) as zf:
        for name, src in FILES:
            zf.write(src, name)
    # 回读校验：逐条目与源文件逐字节一致
    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
        expect = [n for n, _ in FILES]
        if names != expect:
            print('条目不符: %s != %s' % (names, expect))
            return 1
        for name, src in FILES:
            if zf.read(name) != src.read_bytes():
                print('字节不一致: %s' % name)
                return 1
    raw = out.read_bytes()
    print('输出: %s' % out)
    print('大小: %d' % len(raw))
    print('sha256: %s' % hashlib.sha256(raw).hexdigest())
    for name, src in FILES:
        print('  %-34s %8d bytes  %s' % (name, src.stat().st_size,
                                         hashlib.sha256(src.read_bytes()).hexdigest()[:16]))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
