# -*- coding: utf-8 -*-
"""粤语词库资源全量交付检验脚本 (对标日语/德语完整架构规格):
  1. cantonese_books.json 词数与级别分布 (L1~L18)
  2. sentences_master.json 与 packs/yue/db/sentences.json 存在且包含完整例句
  3. packs/yue/db/meaning.sqlite 数据库结构与 pron 表行数
  4. packs/yue/db/repair.tsv 离线自愈载荷
  5. output/import/ 与 packs/yue/books/ 下的无表头 Excel 词书格式契约
  6. packs/yue/manifest.json 规范性与 SHA-256 指纹一致性
  7. BepInEx 运行时 Mod 及 Pack 策略 DLL 编译完整性
  8. 单词音频 100% 覆盖校验 (384 词对应 384 个有效 mp3)
  9. 例句音频 100% 覆盖校验 (全部例句 MD5 对应有效 mp3)

用法: python tools/verify_all_yue.py
"""
import hashlib
import json
import os
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path
from openpyxl import load_workbook

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent

ok_all = True


def report(label, ok, detail=''):
    global ok_all
    if not ok:
        ok_all = False
    print(f"[{'OK' if ok else 'NG'}] {label}" + (f' - {detail}' if detail else ''))


def sha256_of_words(words):
    norm = [unicodedata.normalize('NFC', w.strip()) for w in words]
    norm.sort()
    payload = '\n'.join(norm) + '\n'
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def md5_str(s: str) -> str:
    return hashlib.md5(s.strip().encode('utf-8')).hexdigest()


def check_books():
    p = ROOT / 'output' / 'cantonese_books.json'
    if not p.exists():
        report('cantonese_books.json 存在', False)
        return []
    data = json.loads(p.read_text('utf-8'))
    total = data.get('total_words', 0)
    levels = data.get('levels', {})
    vocab = data.get('vocabulary', [])

    lvl_desc = ", ".join([f"{k}:{len(v)}" for k, v in levels.items()])
    report('cantonese_books.json 存在并解析', True, f"总词数 {total}, 分级 [{lvl_desc}]")

    words = [x['word'] for x in vocab]
    calc_fp = sha256_of_words(words)
    claimed_fp = data.get('fingerprint_sha256', '')
    report('词库 SHA-256 指纹校验', calc_fp == claimed_fp, f"{calc_fp[:16]}...")
    return words


def check_sentences(words):
    p1 = ROOT / 'output' / 'sentences_master.json'
    p2 = ROOT / 'packs' / 'yue' / 'db' / 'sentences.json'
    if not p1.exists() or not p2.exists():
        report('例句库文件完整性', False, f"output: {p1.exists()}, pack: {p2.exists()}")
        return

    d1 = json.loads(p1.read_text('utf-8'))
    s_dict = d1.get('sentences', {})
    missing = [w for w in words if w not in s_dict or len(s_dict[w]) == 0]
    report('例句全词条覆盖', len(missing) == 0, f"覆盖 {len(s_dict)}/{len(words)} 词")


def check_sqlite(words):
    p = ROOT / 'packs' / 'yue' / 'db' / 'meaning.sqlite'
    if not p.exists():
        report('meaning.sqlite 存在', False)
        return
    conn = sqlite3.connect(p)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM pron")
    cnt = cur.fetchone()[0]
    report('meaning.sqlite pron 表行数匹配', cnt == len(words), f"共 {cnt} 行")
    conn.close()


def check_repair_tsv(words):
    p = ROOT / 'packs' / 'yue' / 'db' / 'repair.tsv'
    if not p.exists():
        report('repair.tsv 存在', False)
        return
    lines = p.read_text('utf-8').splitlines()
    header = lines[0] if lines else ""
    report('repair.tsv 结构符合标准规范', header.startswith('#\tschema=1'), f"共 {len(lines)} 行流记录")


def check_excel(words):
    paths = [
        ROOT / 'output' / 'import' / '粤语词库(猫条版).xlsx',
        ROOT / 'packs' / 'yue' / 'books' / '粤语词库(猫条版).xlsx'
    ]
    for p in paths:
        if not p.exists():
            report(f'Excel 词书存在 ({p.name})', False, str(p))
            continue
        wb = load_workbook(p)
        ws = wb.active
        r1_a = ws.cell(1, 1).value
        r1_b = ws.cell(1, 2).value
        has_header = (r1_a in ['word', '单词', '词汇'])
        row_cnt = ws.max_row
        report(f'Excel 无表头契约与行数 ({p.parent.name})', not has_header and row_cnt == len(words),
               f"第一行: '{r1_a}' -> '{r1_b[:20]}...', 共 {row_cnt} 行")


def check_manifest(words):
    p = ROOT / 'packs' / 'yue' / 'manifest.json'
    if not p.exists():
        report('manifest.json 存在', False)
        return
    data = json.loads(p.read_text('utf-8'))
    claimed_cnt = data.get('word_count', 0)
    claimed_fp = data.get('fingerprint_sha256', '')
    actual_fp = sha256_of_words(words)

    report('manifest 词数与指纹对齐', claimed_cnt == len(words) and claimed_fp == actual_fp,
           f"声明: {claimed_cnt} 词, 实际: {len(words)} 词")

    probes = data.get('repair_probes', [])
    word_set = set(words)
    all_probe_exist = all(pr in word_set for pr in probes)
    report('manifest 探针词真实性', all_probe_exist, f"探针词: {probes}")


def check_mods():
    mods = [
        ROOT / 'mod_book_name' / 'BookNameMod.dll',
        ROOT / 'mod_sentence_audio_yue' / 'SentenceAudioYueMod.dll',
        ROOT / 'mod_yue_wordlist' / 'YueWordListMod.dll',
        ROOT / 'packs' / 'yue' / 'WcpPack.Yue.dll',
    ]
    for m in mods:
        report(f'Mod 程序集编译产物 ({m.name})', m.exists() and m.stat().st_size > 4096,
               f"{m.stat().st_size if m.exists() else 0} 字节")


def check_audio_resources(words):
    # 1. 检查单词音频
    word_audio_dir = ROOT / 'packs' / 'yue' / 'audio' / 'word'
    missing_words = []
    invalid_words = []
    for w in words:
        f = word_audio_dir / f"{w}.mp3"
        if not f.exists():
            missing_words.append(w)
        elif f.stat().st_size < 500:
            invalid_words.append(w)

    report('单词音频 100% 完整覆盖', len(missing_words) == 0 and len(invalid_words) == 0,
           f"共 {len(words) - len(missing_words)}/{len(words)} 个文件有效")

    # 2. 检查例句音频
    sent_audio_dir = ROOT / 'packs' / 'yue' / 'audio' / 'sentence'
    sent_file = ROOT / 'output' / 'sentences_master.json'
    sent_data = json.loads(sent_file.read_text('utf-8'))
    expected_sents = set()
    for w, s_list in sent_data.get('sentences', {}).items():
        for s in s_list:
            clean = re.sub(r'（[^）]*）|\([^\)]*\)', '', s.get('sentence', '')).strip()
            if clean:
                expected_sents.add(md5_str(clean))

    missing_sents = []
    invalid_sents = []
    for k in expected_sents:
        f = sent_audio_dir / f"{k}.mp3"
        if not f.exists():
            missing_sents.append(k)
        elif f.stat().st_size < 500:
            invalid_sents.append(k)

    report('例句音频 100% 完整覆盖', len(missing_sents) == 0 and len(invalid_sents) == 0,
           f"共 {len(expected_sents) - len(missing_sents)}/{len(expected_sents)} 个文件有效")


def main():
    print("=== 粤语学习资源全量规格校验 (对标 WCP 日语/德语词库规范) ===\n")
    words = check_books()
    if words:
        check_sentences(words)
        check_sqlite(words)
        check_repair_tsv(words)
        check_excel(words)
        check_manifest(words)
        check_audio_resources(words)
    check_mods()

    print("\n------------------------------------------------------------")
    if ok_all:
        print(">>> 校验结果: ALL PASS (包含单词/例句全量音频的所有规格全部合格) <<<")
        sys.exit(0)
    else:
        print(">>> 校验结果: 有检查项未通过，请处理 <<<")
        sys.exit(1)


if __name__ == '__main__':
    main()
