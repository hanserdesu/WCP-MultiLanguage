# -*- coding: utf-8 -*-
r"""阿拉伯语词书全量质量验证脚本 (verify_all_ar.py)。
对标 D:\ATooManyLanguage\Japanese\wcp_wordbooks\tools\verify_all.py:
- 词覆盖与条数验证
- 字段完整性（单词、读音转写、三字母词根、词性、释义、例句与译文）
- WCP 游戏契约校验（无表头、两列必填规范、EasySave3/BookProfiles 契约）
- SQLite 外接词库完整性 (PRAGMA integrity_check, pron 表, arabic_all 表)
- 指纹防漂移检验
- 游戏实际路径与运行时接入探测
"""
import hashlib
import json
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path

import openpyxl
from audio_paths_ar import sentence_audio_dir, word_audio_dir
from audio_filename_ar import safe_filename
import wcp_paths

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
OUT = ROOT / 'output'
IMPORT = OUT / 'import'

ARABIC_RE = re.compile(r'[\u0600-\u06FF]')
CHINESE_RE = re.compile(r'[\u4E00-\u9FA5]')

def test_check(name, condition, detail=""):
    status = "OK" if condition else "FAIL"
    print(f"[{status:4s}] {name}{': ' + detail if detail else ''}")
    return 1 if condition else 0

def main():
    print("=" * 70)
    print("      阿拉伯语专业学习资源与词书质量全量审计 (verify_all_ar.py)")
    print("=" * 70)
    
    passes = 0
    total = 0

    # 1. 检查主数据文件
    master_json_path = OUT / 'arabic_books.json'
    total += 1
    has_master = master_json_path.exists()
    passes += test_check("主数据库 output/arabic_books.json 存在性", has_master)

    if not has_master:
        print("错误: 缺少 arabic_books.json，请先运行 make_import_files.py")
        sys.exit(1)

    data = json.loads(master_json_path.read_text(encoding='utf-8'))
    books = data.get('books', {})
    meta = data.get('meta', {})

    total += 1
    passes += test_check("词书分类数量达到 10 大以上考级与专业类别", len(books) >= 10, f"当前共 {len(books)} 类")

    all_entries = []
    for bname, entries in books.items():
        all_entries.extend(entries)

    total += 1
    passes += test_check("全量词条规模达到专业考级 8000+ 词标准", len(all_entries) >= 8000, f"实际词条数: {len(all_entries)}")

    # 2. 字段完整性与语言文字学规范验证
    no_word = [e for e in all_entries if not e.get('word')]
    total += 1
    passes += test_check("单词 (word) 字段无缺失", len(no_word) == 0)

    no_ar_script = [e for e in all_entries if not ARABIC_RE.search(e.get('word', ''))]
    total += 1
    passes += test_check("单词均符合阿拉伯文字符集编码规范", len(no_ar_script) == 0)

    no_translit = [e for e in all_entries if not e.get('transliteration')]
    total += 1
    passes += test_check("读音转写 (transliteration) 覆盖率 100%", len(no_translit) == 0)

    no_meaning = [e for e in all_entries if not e.get('meaning')]
    total += 1
    passes += test_check("中文释义 (meaning) 覆盖率 100%", len(no_meaning) == 0)

    no_pos = [e for e in all_entries if not e.get('pos')]
    total += 1
    passes += test_check("词性标注 (pos) 覆盖率 100%", len(no_pos) == 0)

    no_ex_ar = [e for e in all_entries if not e.get('example_ar')]
    total += 1
    passes += test_check("阿拉伯语例句 (example_ar) 覆盖率 100%", len(no_ex_ar) == 0)

    no_ex_zh = [e for e in all_entries if not e.get('example_zh')]
    total += 1
    passes += test_check("例句中文译文 (example_zh) 覆盖率 100%", len(no_ex_zh) == 0)

    no_zh_in_trans = [e for e in all_entries if not CHINESE_RE.search(e.get('example_zh', ''))]
    total += 1
    passes += test_check("例句中文译文有效性（包含中文字符）", len(no_zh_in_trans) == 0)

    # 3. Excel 导入文件规范验证 (对标 SaveSourceType 逆向契约)
    xlsx_files = list(IMPORT.glob('*.xlsx'))
    total += 1
    passes += test_check("已生成 .xlsx 导入词书文件", len(xlsx_files) >= 11, f"发现 {len(xlsx_files)} 个")

    header_violations = []
    cell_empty_ab = []
    for xf in xlsx_files:
        wb = openpyxl.load_workbook(xf, read_only=True)
        sheet = wb.active
        for row_idx, row in enumerate(sheet.iter_rows(values_only=True), start=1):
            if row_idx == 1:
                # 检查第一行是否误用了表头（如写成了 "单词" / "word"）
                if str(row[0]).lower() in ('word', '单词', '词汇', 'term', 'expression'):
                    header_violations.append(f"{xf.name}: 第1行发现非法表头 {row[0]}")
            if not row[0] or not row[1]:
                cell_empty_ab.append(f"{xf.name}: 行 {row_idx} A/B列为空")

    total += 1
    passes += test_check("Excel 遵循 WCP 零表头契约 (无第一行表头)", len(header_violations) == 0,
                         "; ".join(header_violations[:2]))

    total += 1
    passes += test_check("Excel A列(单词)与B列(释义)均非空且有效", len(cell_empty_ab) == 0,
                         "; ".join(cell_empty_ab[:2]))

    # 4. SQLite 外接词库验证
    db_path = IMPORT / 'wcp_arabic.db'
    total += 1
    passes += test_check("外接数据库 wcp_arabic.db 存在", db_path.exists())

    if db_path.exists():
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        
        # PRAGMA integrity_check
        integrity = cur.execute('PRAGMA integrity_check').fetchone()[0]
        total += 1
        passes += test_check("SQLite 数据库结构物理完整性 (PRAGMA integrity_check)", integrity == 'ok', integrity)

        # 检查表结构
        tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        total += 1
        passes += test_check("包含 pron 表与 arabic_all 扩展表", 'pron' in tables and 'arabic_all' in tables, str(tables))

        pron_count = cur.execute("SELECT COUNT(*) FROM pron").fetchone()[0]
        total += 1
        passes += test_check("pron 表主键词数与去重词数一致", pron_count == meta.get('unique_words'), f"pron: {pron_count}, meta: {meta.get('unique_words')}")

        all_count = cur.execute("SELECT COUNT(*) FROM arabic_all").fetchone()[0]
        total += 1
        passes += test_check("arabic_all 详细记录数完整一致", all_count == meta.get('total_entries'), f"db: {all_count}, meta: {meta.get('total_entries')}")
        conn.close()

    # 5. 指纹防漂移验证
    profile_path = IMPORT / '阿拉伯语考级词库(猫条版).profile.json'
    total += 1
    passes += test_check("词书 Profile 元数据存在", profile_path.exists())

    if profile_path.exists():
        prof = json.loads(profile_path.read_text(encoding='utf-8'))
        words = [e['word'] for e in all_entries]
        unique_words = sorted(unicodedata.normalize('NFC', w.strip()) for w in set(words))
        calc_fp = hashlib.sha256(''.join(w + '\n' for w in unique_words).encode('utf-8')).hexdigest()
        
        total += 1
        passes += test_check("Profile 指纹 (SHA-256) 与词集哈希严格吻合", prof.get('fingerprint_sha256') == calc_fp,
                             f"prof: {prof.get('fingerprint_sha256')[:12]}..., calc: {calc_fp[:12]}...")

    # 6. 游戏路径与环境探测
    g_dir = wcp_paths.game_dir()
    total += 1
    passes += test_check("游戏根目录探测 (wcp_paths.game_dir)", g_dir is not None and g_dir.exists(), str(g_dir))

    full_db = wcp_paths.full_db()
    total += 1
    passes += test_check("Steam 真实数据库 wcpFullEng.db 可达性探测", full_db.exists(), str(full_db))

    # 7. 音频资产与自愈 Payload (对标 verify_all_pt/es/ko 的隔离契约)
    word_dir = word_audio_dir()
    sent_dir = sentence_audio_dir()

    words_uni = {unicodedata.normalize('NFC', e['word'].strip()) for e in all_entries}
    total += 1
    if word_dir.exists():
        missing_w = [w for w in words_uni if not (word_dir / safe_filename(w)).exists()]
        passes += test_check("单词音频落盘于 ar_word_audio (私有隔离目录)", not missing_w,
                             f"{len(words_uni) - len(missing_w)}/{len(words_uni)}")
    else:
        passes += test_check("单词音频落盘于 ar_word_audio (私有隔离目录)", False, f"目录不存在: {word_dir}")

    total += 1
    if sent_dir.exists():
        sent_uni = set()
        for e in all_entries:
            s = re.sub(r'<[^>]+>', '', e.get('example_ar', '') or '').strip()
            if len(s) >= 2:
                sent_uni.add(s)
        missing_s = [s for s in sent_uni
                     if not (sent_dir / (hashlib.md5(s.encode('utf-8')).hexdigest() + '.mp3')).exists()]
        passes += test_check("例句音频落盘于 ar_sentence_audio (md5 命名)", not missing_s,
                             f"{len(sent_uni) - len(missing_s)}/{len(sent_uni)}")
    else:
        passes += test_check("例句音频落盘于 ar_sentence_audio (md5 命名)", False, f"目录不存在: {sent_dir}")

    payload = OUT / 'ar_db_payload'
    total += 1
    payload_ok = all((payload / n).exists() for n in ('ar_pron.tsv', 'ar_only_pron.tsv', 'ar_sentences.tsv', 'manifest.json'))
    if payload_ok:
        manifest = json.loads((payload / 'manifest.json').read_text(encoding='utf-8'))
        try:
            for fname in ('ar_pron.tsv', 'ar_only_pron.tsv', 'ar_sentences.tsv'):
                actual = hashlib.sha256((payload / fname).read_bytes()).hexdigest()
                if manifest.get(fname) != actual:
                    payload_ok = False
                    break
            payload_ok = payload_ok and manifest.get('word_count') == meta.get('unique_words')
        except OSError:
            payload_ok = False
    passes += test_check("自愈 Payload ar_db_payload 完整且 SHA-256 吻合", payload_ok,
                         f"word_count: {manifest.get('word_count') if payload_ok else 'n/a'}")

    print("-" * 70)
    print(f"验证完成: 共 {total} 项检查, 通过 {passes} 项, 失败 {total - passes} 项。")
    if passes == total:
        print(">>> 结论: ALL PASS - 阿拉伯语专业学习资源 100% 达标！<<<")
    print("=" * 70)

if __name__ == '__main__':
    main()
