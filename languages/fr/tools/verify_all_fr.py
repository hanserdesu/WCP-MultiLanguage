# -*- coding: utf-8 -*-
"""法语词书全量交付校验 (对标 D:/ATooManyLanguage/Japanese/IMPLEMENTATION.md 规范):
  - french_books.json 词数/级别分布
  - sentences_master.json 每词 3 条
  - 单词音频 fr_word_audio/<word>.mp3 命中率
  - 例句音频 fr_sentence_audio/<md5(fr)>.mp3 命中率
- 游戏本地库 wcpFullEng.db pron + sentence2 灌库覆盖与探针校验
- 外接词库 wcpOnlyWord.db pron 覆盖与探针校验
- 英法同形词英文原版还原校验 (1638 词, book-scoped 切换基线)
  - MyBook.es3 槽位 2 词数与释义 (槽位 1 日语书保留)
  - 导入文件 (xlsx / .db) 存在性与 persistentDataPath 同步
  - BepInEx 插件 SentenceAudioFrMod.dll 部署状态
用法: python tools/verify_all_fr.py
"""
import hashlib
import json
import os
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
import wcp_paths
from audio_paths_fr import native_path, word_audio_dir

ROOT = Path(__file__).resolve().parent.parent
VOCAB_DIR = word_audio_dir()
SENT_DIR = Path.home() / 'AppData' / 'LocalLow' / 'WCP' / 'wcp' / 'fr_sentence_audio'
MYBOOK = Path.home() / 'AppData' / 'LocalLow' / 'WCP' / 'wcp' / 'MyBook.es3'

# Windows 保留设备名 —— 常规接口写不进去, 必须走 \\?\ 扩展路径 (IMPLEMENTATION.md §1.5)
RESERVED = {'con', 'prn', 'aux', 'nul',
            'com1', 'com2', 'com3', 'com4', 'lpt1', 'lpt2'}

_TAG_RE = re.compile(r'<[^>]+>')


def _tsv_map(path):
    """word -> [cols]; 供两端探针常量比对用 (行内不含未转义的制表符)。"""
    out = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line:
            continue
        parts = line.split('\t')
        out[parts[0]] = parts
    return out


def _extract_fr(raw):
    """复刻 SentenceAudioFrMod.ExtractFr 的剥离逻辑 (IMPLEMENTATION.md §1.5)。

    两端任何一处改动都会让发音按钮挂上却点不出声音, 因此必须端到端比对。
    """
    if not raw:
        return None
    s = _TAG_RE.sub('', raw).replace('例句：', '').strip()
    if not s:
        return None
    nl = s.find('\n')
    if nl >= 0:
        s = s[:nl].strip()
    if s.endswith('）'):
        i = s.rfind('（')
        if i > 0:
            s = s[:i].strip()
    if len(s) < 2:
        return None
    has_latin = any(('A' <= c <= 'Z') or ('a' <= c <= 'z')
                    or ('\u00c0' <= c <= '\u024f') or c in 'œŒæÆ' for c in s)
    if not has_latin:
        return None
    for c in s:
        if ('\u3040' <= c <= '\u30ff') or ('\u3400' <= c <= '\u9fff') \
                or ('\uf900' <= c <= '\ufaff'):
            return None
    return s

ok_all = True


def report(label, ok, detail=''):
    global ok_all
    if not ok:
        ok_all = False
    print(f"[{'OK' if ok else 'NG'}] {label}" + (f' {detail}' if detail else ''))


def main():
    # 英法同形词: 共享库稳态 = 英文原版 + 法语独有词补丁。
    # 同形词的英文 pron/sentence2 必须与英文基线一致, 才能保证
    # 英语/日语词书不受法语影响 (运行时由 FrWordListMod 双向切换)。
    # (2026-09-13 新增检查项, 对应 restore_english_overlap_fr.py 的数据修复)
    ov_p = ROOT / 'work' / 'english_overlap_words.json'
    base_p = ROOT / 'work' / 'english_baseline' / 'wcpFullEng.db'
    if ov_p.exists() and base_p.exists():
        overlap = set(json.loads(ov_p.read_text(encoding='utf-8')))
        bcon = sqlite3.connect(str(base_p))
        en_pron = {r[0]: (r[1], r[2], r[3]) for r in bcon.execute(
            'SELECT word, ukPhonic, usPhonic, meaning FROM pron '
            f'WHERE word IN ({",".join("?"*len(overlap))})', list(overlap))}
        en_sent = {}
        for w, s in bcon.execute(
                'SELECT word, sentences FROM sentence2 '
                f'WHERE word IN ({",".join("?"*len(overlap))})', list(overlap)):
            en_sent.setdefault(w, []).append(s)
        bcon.close()
        full_db0 = wcp_paths.full_db()
        with sqlite3.connect(str(full_db0)) as con:
            cur = con.cursor()
            ph = ','.join('?' * len(overlap))
            en_hits = 0
            for r in cur.execute(
                    f'SELECT word, ukPhonic, usPhonic, meaning FROM pron '
                    f'WHERE word IN ({ph})', list(overlap)):
                if (r[1], r[2], r[3]) == en_pron.get(r[0]):
                    en_hits += 1
            got_sent = {}
            for w, s in cur.execute(
                    f'SELECT word, sentences FROM sentence2 WHERE word IN ({ph})',
                    list(overlap)):
                got_sent.setdefault(w, []).append(s)
        sent_ok = all(sorted(got_sent.get(w, [])) == sorted(en_sent.get(w, []))
                      for w in overlap)
        report('英法同形词英文还原 (FullEng)', en_hits == len(en_pron) == len(overlap) and sent_ok,
               f'pron {en_hits}/{len(en_pron)}, sentence2 '
               f'{"一致" if sent_ok else "不一致"}')
        only_db0 = wcp_paths.only_db()
        if only_db0.is_file():
            with sqlite3.connect(str(only_db0)) as con:
                only_hits = 0
                for r in con.execute(
                        f'SELECT word, ukPhonic, usPhonic, meaning FROM pron '
                        f'WHERE word IN ({ph})', list(overlap)):
                    if (r[1], r[2], r[3]) == en_pron.get(r[0]):
                        only_hits += 1
            report('英法同形词英文还原 (OnlyWord)',
                   only_hits == len(en_pron) == len(overlap),
                   f'pron {only_hits}/{len(en_pron)}')
    else:
        report('英法同形词英文还原基线文件', False, f'{ov_p} / {base_p}')

    books = json.loads((ROOT / 'output' / 'french_books.json').read_text(
        encoding='utf-8'))
    levels = books['levels']
    n_words = {lv: len(levels[lv]) for lv in levels}
    all_words = [w for lv in levels for w in levels[lv]]
    report('词书构建', True,
           f"{n_words} 合计 {len(all_words)}")

    master = json.loads((ROOT / 'data' / 'translations' / 'sentences_master.json')
                        .read_text(encoding='utf-8'))
    short = [w['word'] for w in all_words if len(master.get(w['word'], [])) < 3]
    report('例句 master (每词3条)', not short,
           f'{len(master)} 词' + (f', 缺: {short[:5]}' if short else ''))

    # 音频均从法语私有目录读取，不能回退到其它语言的共享目录。
    miss_w = [w['word'] for w in all_words
              if not native_path(VOCAB_DIR / f"{w['word']}.mp3").is_file()
              or native_path(VOCAB_DIR / f"{w['word']}.mp3").stat().st_size < 1000]
    report('单词音频 fr_word_audio/', len(miss_w) == 0,
           f'{len(all_words) - len(miss_w)}/{len(all_words)}'
           + (f', 缺: {miss_w[:5]}' if miss_w else ''))

    sent_uni = {fr for v in master.values() for fr, _ in v}
    miss_s = [fr for fr in sent_uni
              if not (SENT_DIR / (hashlib.md5(fr.encode('utf-8')).hexdigest()
                                 + '.mp3')).exists()]
    report('例句音频 fr_sentence_audio/', len(miss_s) == 0,
           f'{len(sent_uni) - len(miss_s)}/{len(sent_uni)}'
           + (f', 缺例: {miss_s[:2]}' if miss_s else ''))

    # 游戏本地库: wcpFullEng.db (查词释义与例句数据源)
    words_set = {w['word'] for w in all_words}
    word_list = sorted(words_set)

    # 插件源码里的判定常量 (自愈探针 / 英法切换探针): 必须与数据侧一致, 否则
    # 「稳态被误判为遭覆盖」或「法语态认不出来」都会静默发生。
    mod_src = (ROOT / 'mod_fr_wordlist' / 'FrWordListMod.cs').read_text(
        encoding='utf-8-sig')
    probes_m = re.search(r'DbProbes\s*=\s*new string\[\]\s*\{([^}]*)\}', mod_src)
    probes = re.findall(r'"([^"]+)"', probes_m.group(1)) if probes_m else []
    en_word_m = re.search(r'EnProbeWord\s*=\s*"([^"]+)"', mod_src)
    en_text_m = re.search(r'EnProbeText\s*=\s*"([^"]+)"', mod_src)
    report('插件探针常量可解析',
           bool(probes) and bool(en_word_m) and bool(en_text_m),
           f'DbProbes={probes} EnProbe={en_word_m.group(1) if en_word_m else "?"}')
    if probes and en_word_m and en_text_m:
        pack_repo = ROOT / 'output' / 'fr_db_payload'
        fr_rows = _tsv_map(pack_repo / 'fr_pron.tsv')
        en_rows = _tsv_map(pack_repo / 'en_pron.tsv')
        miss_probe = [w for w in probes if w not in words_set or w not in fr_rows]
        report('自愈探针在词表与 fr_pron.tsv 中', not miss_probe,
               f'{probes}' + (f' 缺 {miss_probe}' if miss_probe else ''))
        w0 = en_word_m.group(1)
        t0 = en_text_m.group(1)
        en_row = en_rows.get(w0) or []
        fr_row = fr_rows.get(w0) or []
        en_m = en_row[3] if len(en_row) > 3 else ''
        fr_m = fr_row[3] if len(fr_row) > 3 else ''
        report('英法切换探针两端可区分 (en_pron/fr_pron)',
               en_m.startswith(t0) and bool(fr_m) and not fr_m.startswith(t0),
               f'{w0}: en={en_m[:14]!r} fr={fr_m[:14]!r}')
    full_db = wcp_paths.full_db()
    if full_db.exists():
        with sqlite3.connect(str(full_db)) as con:
            cur = con.cursor()
            p_hits = cur.execute(
                f"SELECT count(*) FROM pron WHERE word IN ({','.join('?'*len(probes))})",
                probes).fetchone()[0] if probes else 0
            found_pron = 0
            for start in range(0, len(word_list), 500):
                chunk = word_list[start:start + 500]
                found_pron += cur.execute(
                    f"SELECT count(*) FROM pron WHERE word IN ({','.join('?'*len(chunk))})",
                    chunk).fetchone()[0]
            report('wcpFullEng.db pron 覆盖', found_pron == len(word_list),
                   f'{found_pron}/{len(word_list)} (探针命中 {p_hits}/{len(probes)})')
            found_sent = 0
            for start in range(0, len(word_list), 500):
                chunk = word_list[start:start + 500]
                found_sent += cur.execute(
                    f"SELECT count(*) FROM sentence2 WHERE word IN ({','.join('?'*len(chunk))})",
                    chunk).fetchone()[0]
            report('wcpFullEng.db sentence2 覆盖', found_sent >= len(word_list) * 3,
                   f'{found_sent} 条 (预期 ≥{len(word_list)*3})')
    else:
        report('wcpFullEng.db 存在性', False, f'{full_db} 不存在')

    # Counts alone can hide a missing word behind duplicate rows, or stale meanings.
    from patch_local_db_fr import collect, content_matches, load_overlap
    expected = collect()
    excluded = load_overlap(expected)
    expected = {w: value for w, value in expected.items() if w not in excluded}
    for db, sentences in ((full_db, True), (wcp_paths.only_db(), False)):
        if db.is_file():
            with sqlite3.connect(db.as_uri() + '?mode=ro', uri=True) as con:
                report(f'{db.name} 法语独有词全量内容',
                       content_matches(con, expected, sentences))

    # 外接词库: wcpOnlyWord.db
    only_db = wcp_paths.only_db()
    if only_db.exists():
        with sqlite3.connect(str(only_db)) as con:
            cur = con.cursor()
            found_only = 0
            for start in range(0, len(word_list), 500):
                chunk = word_list[start:start + 500]
                found_only += cur.execute(
                    f"SELECT count(*) FROM pron WHERE word IN ({','.join('?'*len(chunk))})",
                    chunk).fetchone()[0]
            report('wcpOnlyWord.db pron 覆盖', found_only == len(word_list),
                   f'{found_only}/{len(word_list)}')
    else:
        report('wcpOnlyWord.db 存在性', False, f'{only_db} 不存在')

    # MyBook（默认合并单册只写槽位2；其它槽位不得由法语工具改动）
    doc = json.loads(MYBOOK.read_text(encoding='utf-8-sig'))
    want = {w['word'] for w in all_words}
    got = set(doc.get('SelfBookList2', {}).get('value', []))
    dct = doc.get('wordDictionary2', {}).get('value', {})
    report('MyBook 槽位2(法语合并单册)',
           got == want and all(w in dct for w in got),
           f'{len(got)}/{len(want)} 词')
    jp = doc.get('SelfBookList1', {}).get('value', [])
    report('MyBook 槽位1 日语书保留', len(jp) == 7922, f'{len(jp)} 词')

    # 导入文件
    imp = ROOT / 'output' / 'import'
    for f in ('法语A1A2.xlsx', '法语B1.xlsx', '法语B2.xlsx', 'wcp_french.db'):
        report(f'导入文件 {f}', (imp / f).exists())
    pdir = Path.home() / 'AppData' / 'LocalLow' / 'WCP' / 'wcp'
    for f in ('法语A1A2.xlsx', '法语B1.xlsx', '法语B2.xlsx', 'wcp_french.db'):
        report(f'persistentDataPath {f}', (pdir / f).exists())

    # BepInEx 插件
    mod_dll = wcp_paths.game_dir() / 'BepInEx' / 'plugins' / 'SentenceAudioFrMod.dll'
    report('BepInEx SentenceAudioFrMod.dll 部署', mod_dll.exists() and mod_dll.stat().st_size > 10000,
           f'{mod_dll.name} ({mod_dll.stat().st_size if mod_dll.exists() else 0} bytes)')
    wl_dll = wcp_paths.game_dir() / 'BepInEx' / 'plugins' / 'FrWordListMod.dll'
    report('BepInEx FrWordListMod.dll 部署', wl_dll.exists() and wl_dll.stat().st_size > 10000,
           f'{wl_dll.name} ({wl_dll.stat().st_size if wl_dll.exists() else 0} bytes)')
    bn_dll = wcp_paths.game_dir() / 'BepInEx' / 'plugins' / 'BookNameMod.dll'
    report('BepInEx BookNameMod.dll 部署', bn_dll.exists() and bn_dll.stat().st_size > 10000,
           f'{bn_dll.name} ({bn_dll.stat().st_size if bn_dll.exists() else 0} bytes)')

    # ── IMPLEMENTATION.md 契约补检 (2026-09-14 补齐) ─────────────────

    # §1.1 ES3 每个顶层键都必须带 __type, 否则游戏读档反序列化失败
    bad_es3 = [k for k, node in doc.items()
               if isinstance(node, dict) and '__type' not in node]
    report('MyBook.es3 ES3 __type 包装完整', not bad_es3,
           f'{len(doc)} 个顶层键' + (f', 缺: {bad_es3[:3]}' if bad_es3 else ''))

    # §1.3 xlsx 必须无表头, A=单词 B=释义 (加表头会把表头行当词条收进词书)
    try:
        import openpyxl
    except ImportError:
        openpyxl = None
    if openpyxl is None:
        report('xlsx 无表头契约', False, 'openpyxl 不可用, 无法校验')
    else:
        for f in ('法语A1A2.xlsx', '法语B1.xlsx', '法语B2.xlsx'):
            p = imp / f
            if not p.is_file():
                continue
            wb = openpyxl.load_workbook(p, read_only=True)
            ws = wb[wb.sheetnames[0]]
            first = next(ws.iter_rows(min_row=1, max_row=1, values_only=True), None)
            wb.close()
            head = first[0] if first else None
            report(f'xlsx 无表头 {f}', head in want, f'A1={head!r}')

    # §1.5 保留设备名 (aux/nul/con …) 的音频必须真实落地
    reserved = sorted(w for w in want
                      if w.strip().lower().split('.')[0] in RESERVED)
    miss_res = [w for w in reserved
                if not native_path(VOCAB_DIR / f'{w}.mp3').is_file()]
    report('保留设备名词音频', not miss_res,
           (f'{len(reserved)} 个 {reserved}' if reserved else '本词表无保留名词')
           + (f', 缺 {miss_res}' if miss_res else ''))

    # §1.5 词音频隔离: 共享 vocabulary/ 是英语/日语词书的发音源, 不得残留法语
    shared_dir = Path.home() / 'AppData' / 'LocalLow' / 'WCP' / 'vocabulary'
    leftover = []
    if shared_dir.is_dir():
        leftover = [n for n in os.listdir(shared_dir)
                    if n.lower().endswith('.mp3') and n[:-4] in want]
    report('词音频隔离 (vocabulary/ 无法语残留)', not leftover,
           f'残留 {len(leftover)}' + (f': {leftover[:5]}' if leftover else ''))

    # §1.5 例句音频两端 md5 必须一致 (此处复刻插件侧剥离逻辑做端到端比对)
    sent_total = sum(len(v) for v in master.values())
    drift = []
    for w, items in master.items():
        for fr, zh in items:
            if _extract_fr(f'例句：{fr}（{zh}）') != fr:
                drift.append(w)
                break
    report('例句音频两端 md5 契约 (ExtractFr)', not drift,
           f'{sent_total} 句' + (f', 漂移: {drift[:5]}' if drift else ''))

    # §1.4 / §3.2 离线自愈补丁包必须五件套齐全 (Steam 更新后靠它还原)
    pack = Path.home() / 'AppData' / 'LocalLow' / 'WCP' / 'wcp' / 'fr_db_payload'
    need = ['fr_pron.tsv', 'fr_sentences.tsv', 'fr_only_pron.tsv',
            'en_pron.tsv', 'en_sentences.tsv', 'manifest.json']
    miss_pack = [n for n in need if not (pack / n).is_file()]
    report('fr_db_payload 离线自愈包', not miss_pack,
           f'缺 {miss_pack}' if miss_pack else f'{pack}')

    # 附录D 三个插件必须编译同一份 BookProfiles.cs (指纹算法跨插件绝对一致)
    profs = [ROOT / 'mod_book_name' / 'BookProfiles.cs',
             ROOT / 'mod_fr_wordlist' / 'BookProfiles.cs',
             ROOT / 'mod_sentence_audio_fr' / 'BookProfiles.cs']
    digests = {hashlib.sha256(p.read_bytes()).hexdigest()
               for p in profs if p.is_file()}
    report('BookProfiles.cs 三副本一致',
           len(digests) == 1 and all(p.is_file() for p in profs),
           f'{len(profs)} 份, 不同内容 {len(digests)} 种')

    # §3.1 / 附录D 词书指纹: 插件靠「排序后的完整词形集合 SHA-256」识别词书。
    # 常量 / payload / MyBook 实际词表三者不一致 = 插件永远认不出自己的书
    # (全功能静默失效)。此处复刻 BookProfiles.FingerprintOf 的算法 (Trim +
    # FormC + 序数排序 + 每词后接 '\n') 做端到端比对。
    mod_fp = re.search(r'catbar-french-cefr-complete[\s\S]{0,300}?"([0-9a-f]{64})"',
                       (ROOT / 'mod_book_name' / 'BookProfiles.cs')
                       .read_text(encoding='utf-8'))
    payload_fp = json.loads((ROOT / 'output' / 'catbar_french_book.json')
                            .read_text(encoding='utf-8')).get('fingerprint_sha256')
    norm = sorted(unicodedata.normalize('NFC', w.strip()) for w in got)
    calc_fp = hashlib.sha256(
        ''.join(w + '\n' for w in norm).encode('utf-8')).hexdigest()
    const_fp = mod_fp.group(1) if mod_fp else '<未解析>'
    report('词书指纹三方一致 (MyBook 词表 / C# 常量 / payload)',
           bool(mod_fp) and const_fp == calc_fp == payload_fp,
           f'词表 {calc_fp[:12]}… / 常量 {const_fp[:12]}… / '
           f'payload {str(payload_fp)[:12]}…')

    # 形态 B 打包契约: 发布清单、音频 zip、安装包载荷三者必须自洽。
    # 清单指向过期音频 = 群友装完无声, 因此体积与 SHA-256 必须逐一核对。
    rel_manifest = ROOT / 'output' / 'release' / 'release-manifest.json'
    pkg = ROOT / 'output' / 'installer_pkg' / 'WCP法语词书安装包'
    if rel_manifest.is_file():
        man = json.loads(rel_manifest.read_text(encoding='utf-8'))

        def _sha256_file(p):
            h = hashlib.sha256()
            with p.open('rb') as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b''):
                    h.update(chunk)
            return h.hexdigest()

        drift = []
        for asset in man.get('assets', []):
            z = ROOT / 'output' / 'release' / asset.get('name', '')
            if not z.is_file():
                drift.append(f'{asset.get("name")} 缺失')
            elif z.stat().st_size != asset['size']:
                drift.append(f'{z.name} 体积漂移')
            elif _sha256_file(z) != asset['sha256']:
                drift.append(f'{z.name} SHA-256 漂移')
        report('Release 清单与音频 zip 一致', not drift,
               '; '.join(drift) if drift else f'{len(man.get("assets", []))} 份资产')
        report('Release 下载地址指向法语仓库',
               all('WCP-French-Wordbook' in b for b in man.get('base_urls', [])),
               man.get('base_urls', ['<空>'])[0])
        pkg_man = pkg / 'support' / 'release-manifest.json'
        report('安装包内 release-manifest 与发布清单一致',
               pkg_man.is_file() and pkg_man.read_bytes() == rel_manifest.read_bytes())

        need_pkg = [pkg / 'support' / 'payload' / 'plugins' / n for n in
                    ('FrWordListMod.dll', 'BookNameMod.dll', 'SentenceAudioFrMod.dll')]
        need_pkg.append(pkg / 'support' / 'payload' / 'catbar_french_book.json')
        need_pkg.append(pkg / '01_双击运行我.cmd')
        need_pkg.append(pkg / '使用说明.txt')
        need_pkg += [pkg / 'support' / 'payload' / 'fr_db_payload' / n for n in
                     ('fr_pron.tsv', 'fr_sentences.tsv', 'fr_only_pron.tsv',
                      'en_pron.tsv', 'en_sentences.tsv', 'manifest.json')]
        need_pkg += [pkg / 'support' / 'payload' / 'books' / n for n in
                     ('法语A1A2.xlsx', '法语B1.xlsx', '法语B2.xlsx', 'wcp_french.db')]
        miss_pkg = [p.name for p in need_pkg if not p.is_file()]
        report('安装包载荷齐全', not miss_pkg, f'缺 {miss_pkg}' if miss_pkg else f'{len(need_pkg)} 项')
    else:
        report('形态 B 发布清单 (未构建则跳过)', True, '先运行 tools/build_release_fr.py')

    print('\n总体:', 'ALL PASS' if ok_all else '存在未通过项')
    return 0 if ok_all else 1


if __name__ == '__main__':
    sys.exit(main())
