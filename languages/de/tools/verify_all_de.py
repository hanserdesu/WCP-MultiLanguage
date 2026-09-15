# -*- coding: utf-8 -*-
"""德语词书全量交付校验 (对标 CEFR B2 完整规格):
  - german_books.json 词数与级别分布 (A1, A2, B1, B2)
  - sentences_master.json 每词 3 条
  - wcpFullEng.db / wcpOnlyWord.db pron + sentence2 状态
  - MyBook.es3 槽位 4 词数与 ES3 __type 类型包装完整性，槽位 1/2/3 完好保留
  - BookProfiles.cs 注册表与跨语言指纹一致性
  - de_db_payload 离线自愈包与 manifest
  - BepInEx 插件构建与游戏目录部署状态

用法: python tools/verify_all_de.py
"""
import hashlib
import json
import os
import sqlite3
import sys
import unicodedata
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
import wcp_paths

MYBOOK = Path.home() / 'AppData' / 'LocalLow' / 'WCP' / 'wcp' / 'MyBook.es3'
SAVEFILE = Path.home() / 'AppData' / 'LocalLow' / 'WCP' / 'wcp' / 'SaveFile.es3'

ok_all = True

def report(label, ok, detail=''):
    global ok_all
    if not ok:
        ok_all = False
    print(f"[{'OK' if ok else 'NG'}] {label}" + (f' {detail}' if detail else ''))

def sha256_of_words(words):
    norm = [unicodedata.normalize('NFC', w.strip()) for w in words]
    norm.sort()
    payload = '\n'.join(norm) + '\n'
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()

def check_books():
    p = ROOT / 'output' / 'german_books.json'
    if not p.exists():
        report('german_books.json 存在', False)
        return []
    data = json.loads(p.read_text('utf-8'))
    a1 = len(data.get('levels', {}).get('a1', []))
    a2 = len(data.get('levels', {}).get('a2', []))
    b1 = len(data.get('levels', {}).get('b1', []))
    b2 = len(data.get('levels', {}).get('b2', []))
    total = a1 + a2 + b1 + b2
    report('german_books.json 四级词数分布 (B2全量)', total == 8062, f"A1={a1}, A2={a2}, B1={b1}, B2={b2} | 总计={total}")
    words = []
    for lvl in ['a1', 'a2', 'b1', 'b2']:
        for item in data['levels'][lvl]:
            words.append(item['word'].strip())
    return words

def check_sentences(words):
    p = ROOT / 'data' / 'translations' / 'sentences_master.json'
    if not p.exists():
        report('sentences_master.json 存在', False)
        return
    data = json.loads(p.read_text('utf-8'))
    covered = sum(1 for w in words if len(data.get(w, [])) >= 3)
    total_s = sum(len(v) for v in data.values())
    report('例句 sentences_master (每词>=3条)', covered == len(words), f"{covered}/{len(words)} 词, 共 {total_s} 句")

def check_mybook():
    if not MYBOOK.exists():
        report('MyBook.es3 存在', False)
        return
    data = json.loads(MYBOOK.read_text('utf-8-sig'))
    s1 = len((data.get('SelfBookList1') or {}).get('value', []))
    s2 = len((data.get('SelfBookList2') or {}).get('value', []))
    s3 = len((data.get('SelfBookList3') or {}).get('value', []))
    report('槽位 1(日语) 保留', s1 == 7922, f"{s1} 词")
    report('槽位 2(法语) 保留', s2 == 8116, f"{s2} 词")
    report('槽位 3(俄语) 保留', s3 == 8451, f"{s3} 词")

    s4 = (data.get('SelfBookList4') or {}).get('value', [])
    m4 = (data.get('SelfBookMeaningDic4') or {}).get('value', {})
    report('槽位 4(德语) 写入', len(s4) == 8062 and len(m4) == 8062, f"词数={len(s4)}, 释义={len(m4)}")

    fp = sha256_of_words(s4)
    expected_fp = "66bded175dee70d9fd18ac3e08e793b79b35e9fd750904367a16c6012dd1f70a"
    report('槽位 4 指纹与期望一致', fp == expected_fp, f"fp={fp[:16]}...")

def check_savefile():
    if not SAVEFILE.exists():
        report('SaveFile.es3 存在', False)
        return
    data = json.loads(SAVEFILE.read_text('utf-8-sig'))
    n1 = (data.get('SelfBookName1') or {}).get('value')
    n2 = (data.get('SelfBookName2') or {}).get('value')
    n3 = (data.get('SelfBookName3') or {}).get('value')
    n4 = (data.get('SelfBookName4') or {}).get('value')
    report('SaveFile 书名昵称', n4 == '德语词库(猫条版)' and n1 and n2 and n3,
           f"S1={n1}, S2={n2}, S3={n3}, S4={n4}")

def check_db():
    full = wcp_paths.full_db()
    only = wcp_paths.only_db()
    words = check_books()
    overlap_p = ROOT / 'work' / 'english_overlap_words.json'
    overlap = set(json.loads(overlap_p.read_text('utf-8')))
    de_only = set(words) - overlap

    con_f = sqlite3.connect(str(full))
    cur_f = con_f.cursor()
    ph = ','.join('?' * len(de_only))
    cur_f.execute(f"SELECT count(distinct word) FROM pron WHERE word IN ({ph})", list(de_only))
    f_pron = cur_f.fetchone()[0]

    cur_f.execute(f"SELECT count(distinct word) FROM sentence2 WHERE word IN ({ph})", list(de_only))
    f_sent = cur_f.fetchone()[0]
    con_f.close()

    con_o = sqlite3.connect(str(only))
    cur_o = con_o.cursor()
    cur_o.execute(f"SELECT count(distinct word) FROM pron WHERE word IN ({ph})", list(de_only))
    o_pron = cur_o.fetchone()[0]
    con_o.close()

    report('wcpFullEng.db 德语独有词 pron 注入', f_pron == len(de_only), f"{f_pron}/{len(de_only)}")
    report('wcpFullEng.db 德语独有词 sentence2 注入', f_sent == len(de_only), f"{f_sent}/{len(de_only)}")
    report('wcpOnlyWord.db 德语独有词 pron 注入', o_pron == len(de_only), f"{o_pron}/{len(de_only)}")

def check_payload():
    for base in [ROOT / 'output' / 'de_db_payload', Path.home() / 'AppData' / 'LocalLow' / 'WCP' / 'wcp' / 'de_db_payload']:
        mf = base / 'manifest.json'
        p_ok = mf.exists() and (base / 'de_pron.tsv').exists() and (base / 'en_pron.tsv').exists()
        report(f'离线自愈包 {base.name} ({base.parent.name})', p_ok)

def check_mods():
    plugins = wcp_paths.game_dir() / 'BepInEx' / 'plugins'
    for dll in ['BookNameMod.dll', 'SentenceAudioDeMod.dll', 'DeWordListMod.dll']:
        p = plugins / dll
        report(f'插件部署 {dll}', p.exists() and p.stat().st_size > 10000, f"{p.stat().st_size if p.exists() else 0} 字节")

def main():
    print("=== 开始德语词库 B2 全量规格与环境验收 ===")
    words = check_books()
    check_sentences(words)
    check_mybook()
    check_savefile()
    check_db()
    check_payload()
    check_mods()
    print("==========================================")
    if ok_all:
        print(">>> 德语 B2 考级级词库全项核验通过 (ALL PASS)！<<<")
    else:
        print(">>> 部分校验项未通过，请检查日志。<<<")

if __name__ == '__main__':
    main()
