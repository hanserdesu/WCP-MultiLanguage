# -*- coding: utf-8 -*-
"""俄语词书全量交付校验 (严格对齐 D:/ATooManyLanguage/Japanese/IMPLEMENTATION.md 复刻规范):
  - russian_books.json 词数/级别分布
  - sentences_master.json 每词 3 条
  - 单词音频 ru_word_audio/<word>.mp3 命中率
  - 例句音频 ru_sentence_audio/<md5(ru)>.mp3 命中率
  - 私有 wcp_russian.db pron 全查；例句由私有 sentences_master.json 提供
  - MyBook.es3 槽位 3 词数与 ES3 __type 类型包装完整性
  - 导入文件 xlsx 无表头契约与 wcp_russian.db 外接库
  - BookProfiles.cs 三副本逐字节一致
  - 词书指纹三方一致 (MyBook / C# 常量 / catbar payload)
  - ru_db_payload 离线自愈包与 manifest
  - 插件探针词 (DbProbes) 命中校验
  - 例句音频两端 md5 契约 (ExtractRu 模拟)
  - BepInEx 插件构建与游戏目录部署状态
  - 形态 B 一键安装包完整性

用法: python tools/verify_all_ru.py
"""
import hashlib
import json
import os
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path

import openpyxl

sys.stdout.reconfigure(encoding='utf-8')
import wcp_paths

ROOT = Path(__file__).resolve().parent.parent
RU_WORD_AUDIO = Path.home() / 'AppData' / 'LocalLow' / 'WCP' / 'wcp' / 'ru_word_audio'
RU_SENT_DIR = Path.home() / 'AppData' / 'LocalLow' / 'WCP' / 'wcp' / 'ru_sentence_audio'
MYBOOK = Path.home() / 'AppData' / 'LocalLow' / 'WCP' / 'wcp' / 'MyBook.es3'

ok_all = True


def report(label, ok, detail=''):
    global ok_all
    if not ok:
        ok_all = False
    print(f"[{'OK' if ok else 'NG'}] {label}" + (f' {detail}' if detail else ''))


def extract_ru(raw):
    """复刻 SentenceAudioRuMod.ExtractRu 剥离契约 (IMPLEMENTATION.md §1.5)。"""
    if not raw:
        return None
    s = re.sub(r'<[^>]+>', '', raw).replace('例句：', '').strip()
    if not s:
        return None
    nl = s.find('\n')
    if nl >= 0:
        s = s[:nl].strip()
    if s.endswith('）') or s.endswith(')'):
        i = s.rfind('（')
        if i < 0:
            i = s.rfind('(')
        if i > 0:
            s = s[:i].strip()
    s = s.rstrip('。 ')
    if len(s) < 2:
        return None
    has_cyr = any(('\u0400' <= c <= '\u04ff') or c in 'ёЁ' for c in s)
    if not has_cyr:
        return None
    for c in s:
        if ('A' <= c <= 'Z') or ('a' <= c <= 'z') or ('\u00c0' <= c <= '\u024f') or \
           ('\u3040' <= c <= '\u30ff') or ('\u3400' <= c <= '\u9fff') or ('\uf900' <= c <= '\ufaff'):
            return None
    return s


def main():
    books = json.loads((ROOT / 'output' / 'russian_books.json').read_text(
        encoding='utf-8'))
    levels = books['levels']
    n_words = {lv: len(levels[lv]) for lv in levels}
    all_words = [w for lv in levels for w in levels[lv]]
    words_set = {w['word'] for w in all_words}
    report('词书构建', True, f"{n_words} 合计 {len(all_words)}")

    master_p = ROOT / 'data' / 'translations' / 'sentences_master.json'
    if master_p.exists():
        master = json.loads(master_p.read_text(encoding='utf-8'))
        short = [w['word'] for w in all_words if len(master.get(w['word'], [])) < 3]
        report('例句 master (每词3条)', not short,
               f'{len(master)} 词' + (f', 缺: {short[:5]}' if short else ''))
    else:
        master = {}
        report('例句 master (每词3条)', False, '未生成 (缺少 sentences_master.json)')

    # 音频只允许俄语私有目录；共享 vocabulary 曾是跨语言串音来源。
    miss_w = [w['word'] for w in all_words
              if not (RU_WORD_AUDIO / f"{w['word']}.mp3").exists()]
    report('单词音频 (ru_word_audio/)', len(miss_w) == 0,
           f'{len(all_words) - len(miss_w)}/{len(all_words)}'
           + (f', 缺: {miss_w[:5]}' if miss_w else ''))

    sent_uni = {ru for v in master.values() for ru, _ in v}
    miss_s = [ru for ru in sent_uni
              if not (RU_SENT_DIR / (hashlib.md5(ru.encode('utf-8')).hexdigest()
                                 + '.mp3')).exists()]
    report('例句音频 ru_sentence_audio/', len(miss_s) == 0,
           f'{len(sent_uni) - len(miss_s)}/{len(sent_uni)}'
           + (f', 缺例: {miss_s[:2]}' if miss_s else ''))

    # 例句两端 md5 契约抽检
    extract_drift = 0
    for w, pairs in master.items():
        for ru, zh in pairs:
            raw = f'例句：{ru}（{zh}）'
            if extract_ru(raw) != ru:
                extract_drift += 1
    report('例句音频两端 md5 契约 (ExtractRu)', extract_drift == 0,
           f'{len(sent_uni)} 唯一句提取 0 漂移' if extract_drift == 0 else f'漂移 {extract_drift}')

    # 插件自愈探针词校验
    probes = ['стол', 'человек', 'хорошо', 'говорить']
    miss_probes = [p for p in probes if p not in words_set]
    report('自愈探针在词表中 (DbProbes)', not miss_probes,
           f'{len(probes)} 个探针全命中' if not miss_probes else f'缺 {miss_probes}')

    # 语言资源数据库必须是 pack 自己的 wcp_russian.db；不再要求或写入
    # 游戏共享 wcpFullEng.db / wcpOnlyWord.db。
    private_db = ROOT / 'output' / 'import' / 'wcp_russian.db'
    if not private_db.exists():
        report('私有 wcp_russian.db', False, '文件不存在')
    else:
        con = sqlite3.connect(str(private_db))
        cur = con.cursor()
        wl = list(words_set)
        miss_p = 0
        for i in range(0, len(wl), 500):
            chunk = wl[i:i + 500]
            p = ','.join('?' * len(chunk))
            n = cur.execute(f'SELECT COUNT(*) FROM pron WHERE word IN ({p})',
                            chunk).fetchone()[0]
            miss_p += len(chunk) - n
        report('私有 wcp_russian.db pron', miss_p == 0,
               f'{len(wl) - miss_p}/{len(wl)}')
        report('私有例句表 sentences_master', all(len(master.get(w, [])) >= 3 for w in words_set),
               f'{len(sent_uni)} 条唯一俄语句')
        con.close()

    source = (ROOT / 'mod_ru_wordlist' / 'RuWordListMod.cs').read_text(encoding='utf-8')
    report('俄语音频无共享 vocabulary 回退', '"vocabulary"' not in source,
           '只允许 ru_word_audio' if '"vocabulary"' not in source else '仍包含共享回退')

    # MyBook (合并单册: 槽位3 = 全部词, 槽位4 空, 槽位1/2 日法书不动)
    if not MYBOOK.exists():
        report('MyBook.es3 存在性', False, '文件不存在')
    else:
        doc = json.loads(MYBOOK.read_text(encoding='utf-8-sig'))
        want = {w['word'] for w in all_words}
        got = set(doc.get('SelfBookList3', {}).get('value', []))
        dct = doc.get('wordDictionary3', {}).get('value', {})
        report('MyBook 槽位3(俄语合并单册)',
               got == want and all(w in dct for w in got),
               f'{len(got)}/{len(want)} 词')
        n4 = len(doc.get('SelfBookList4', {}).get('value', []))
        slot4 = doc.get('SelfBookList4', {}).get('value', [])
        report('MyBook 槽位4 外部词书保留', isinstance(slot4, list), f'{n4} 词')
        jp = doc.get('SelfBookList1', {}).get('value', [])
        report('MyBook 槽位1 日语书保留', len(jp) == 7922, f'{len(jp)} 词')
        fr = doc.get('SelfBookList2', {}).get('value', [])
        report('MyBook 槽位2 法语书保留', len(fr) == 8116, f'{len(fr)} 词')

        bad_es3 = [k for k, v in doc.items() if isinstance(v, dict) and '__type' not in v]
        report('MyBook.es3 ES3 __type 包装完整', not bad_es3,
               f'缺: {bad_es3}' if bad_es3 else '全部顶层键包含 __type')

    # 导入文件与无表头契约
    imp = ROOT / 'output' / 'import'
    for f in ('俄语A1A2.xlsx', '俄语B1.xlsx', '俄语B2.xlsx', 'wcp_russian.db'):
        report(f'导入文件 {f}', (imp / f).exists())
    for f in ('俄语A1A2.xlsx', '俄语B1.xlsx', '俄语B2.xlsx'):
        xlsx_p = imp / f
        if xlsx_p.exists():
            wb = openpyxl.load_workbook(xlsx_p, read_only=True)
            first_cell = wb.active.cell(row=1, column=1).value
            report(f'xlsx 无表头 {f}', first_cell in words_set, f'A1={first_cell!r}')
    pdir = Path.home() / 'AppData' / 'LocalLow' / 'WCP' / 'wcp'
    for f in ('俄语A1A2.xlsx', '俄语B1.xlsx', '俄语B2.xlsx', 'wcp_russian.db'):
        report(f'persistentDataPath {f}', (pdir / f).exists())

    # BookProfiles.cs 三副本一致
    bp_paths = [
        ROOT / 'mod_book_name' / 'BookProfiles.cs',
        ROOT / 'mod_ru_wordlist' / 'BookProfiles.cs',
        ROOT / 'mod_sentence_audio_ru' / 'BookProfiles.cs',
    ]
    bp_hashes = [hashlib.sha256(p.read_bytes()).hexdigest() for p in bp_paths]
    report('BookProfiles.cs 三副本一致', len(set(bp_hashes)) == 1,
           f'sha256={bp_hashes[0][:16]}' if len(set(bp_hashes)) == 1 else '副本哈希不一致')

    # 词书指纹三方一致 (MyBook 词表 / C# 常量 / catbar payload)
    mb_words = doc.get('SelfBookList3', {}).get('value', [])
    norm = sorted([unicodedata.normalize('NFC', w.strip()) for w in mb_words])
    mb_fp = hashlib.sha256(('\n'.join(norm) + '\n').encode('utf-8')).hexdigest()
    catbar_p = ROOT / 'output' / 'catbar_russian_book.json'
    catbar = json.loads(catbar_p.read_text(encoding='utf-8')) if catbar_p.exists() else {}
    cat_fp = catbar.get('fingerprint_sha256')
    cs_code = bp_paths[0].read_text(encoding='utf-8')
    ru_m = re.search(r'\"catbar-russian-cefr-complete\"[\s\S]*?\"([0-9a-f]{64})\"', cs_code)
    cs_fp = ru_m.group(1) if ru_m else None
    report('词书指纹三方一致 (MyBook 词表 / C# 常量 / payload)',
           mb_fp == cat_fp == cs_fp,
           f'fp={mb_fp[:16]} 词数={len(mb_words)}')

    # ru_db_payload 离线自愈包
    payload_dir = ROOT / 'output' / 'ru_db_payload'
    needed_payload = ['ru_pron.tsv', 'ru_sentences.tsv', 'ru_only_pron.tsv', 'manifest.json']
    miss_payload = [f for f in needed_payload if not (payload_dir / f).exists()]
    report('ru_db_payload 离线自愈包', not miss_payload,
           f'齐全 (4 文件)' if not miss_payload else f'缺 {miss_payload}')

    # 插件构建与就绪
    report('插件 BookNameMod.dll', (ROOT / 'mod_book_name' / 'BookNameMod.dll').exists())
    report('插件 SentenceAudioRuMod.dll', (ROOT / 'mod_sentence_audio_ru' / 'SentenceAudioRuMod.dll').exists())
    report('插件 RuWordListMod.dll', (ROOT / 'mod_ru_wordlist' / 'RuWordListMod.dll').exists())

    # 游戏 plugins 目录部署状态
    game_dir = wcp_paths.game_dir()
    if game_dir:
        plugins_dir = game_dir / 'BepInEx' / 'plugins'
        for dll_name in ('BookNameMod.dll', 'SentenceAudioRuMod.dll', 'RuWordListMod.dll'):
            dll_p = plugins_dir / dll_name
            report(f'BepInEx {dll_name} 部署', dll_p.exists() and dll_p.stat().st_size > 10000)

    # 一键安装包构建与完整性
    pkg_dir = ROOT / 'output' / 'installer_pkg' / 'WCP俄语词书安装包'
    pkg_ok = pkg_dir.exists() and (pkg_dir / '01_双击运行我.cmd').exists() and (pkg_dir / 'support' / 'Install-WCP-Russian.ps1').exists()
    report('一键安装包目录与入口', pkg_ok)

    print('\n总体:', 'ALL PASS' if ok_all else '存在未通过项')


if __name__ == '__main__':
    main()
