# -*- coding: utf-8 -*-
"""语法路线词书构建器。

把 JLPT 五级 8,331 词按学习路线重排(Kaishi 频率优先), 每 block 个词后插入
1 个语法占位词, 语法讲解写入例句栏位(sentence2, 格式 `例句：ja（zh）`),
实现「单词 + 语法」系统学习。

输入:
  data/grammar/curriculum.json        5 阶段语法大纲 (block=每块词数)
  data/grammar/content/gc_*.json      语法讲解内容 {gid: [[ja,zh]x3]}
  output/jlpt_books.json              词源 (word/reading/meaning)
  data/kaishi15k_zh.tsv               频率序 (行序即 rank)

输出:
  output/grammar_route.json           全路线 (词/占位词混合有序表)
  output/grammar_book/语法路线.xlsx    A词 B义 (无表头, 游戏契约) C-F 人工参考
  output/grammar_book/wcp_grammar.db  pron(word,meaning) + route 明细
  --patch 时: wcpFullEng.db( pron+sentence2 ) / wcpOnlyWord.db( pron ) 灌占位词

用法:
  python tools/build_grammar_book.py [--stages 1,2] [--patch] [--dry-run]
  --stages 仅纳入指定阶段(缺省全部); 内容缺失的语法点会列出并跳过(--allow-missing 才放行)
"""
import argparse
import csv
import json
import re
import sqlite3
import sys
from pathlib import Path

import wcp_paths

sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
OUT = ROOT / 'output'
GB = OUT / 'grammar_book'
CONTENT_DIR = DATA / 'grammar' / 'content'
SA = wcp_paths.streaming_assets()

CN_NUM = ['一', '二', '三', '四', '五']

# 阶段头占位词的 3 条例句 (ja 自然日语可 TTS; zh 讲解)
STAGE_ROWS = {
    1: [['ここから日本語の第一歩、入門コースが始まります。',
         '阶段一(入门N5)：从判断句与基础助词学起，每15个单词后有一课语法。'],
        ['まず単語を覚えて、そのあと文法をひとつずつ見ていきましょう。',
         '用法：先过词块，再读占位词的3条例句讲解，例句栏=语法课。'],
        ['がんばって、毎日少しずつ続けるのが一番です。',
         '注意：占位词也有发音和例句朗读，可以当听力材料用。']],
    2: [['ここからは基礎コースです。文を作る力がぐんと上がります。',
         '阶段二(基础N4)：可能・被动・使役・四大条件等核心句型。'],
        ['じわじわ難しくなりますが、復習をかねて進みましょう。',
         '用法：语法讲解仍在占位词的例句栏，配合前面的词块复习。'],
        ['わからない文法があれば、前の段階に戻って確かめましょう。',
         '注意：条件形(と・ば・たら・なら)的差异是本阶段重点。']],
    3: [['ここからは中級コース、複合助詞がたくさん出てきます。',
         '阶段三(进阶N3)：依据・伴随・限界・逆接等复合助词系统化。'],
        ['似た文法の違いを意識しながら、例文で使い分けを覚えましょう。',
         '用法：注意条里常写近义辨析，例句栏的三句各有分工。'],
        ['新聞やドラマで聞いた文法を見つけたら、ここで確認するといいです。',
         '注意：本阶段起书面语增多，朗读例句有助培养语感。']],
    4: [['上級への桥渡し、ここでは書き言葉を中心に学びます。',
         '阶段四(上级N2)：报刊论说文级书面表达。'],
        ['ニュースや論説文でよく見かける形ばかりです。',
         '用法：讲解栏标注了书面语色彩，口语场合需谨慎替换。'],
        ['日本語の試験対策としても、この段階は重要です。',
         '注意：文语接续(つつ・まい等)的活用要背准。']],
    5: [['最後のコース、文語と高度な複合助詞の世界です。',
         '阶段五(精通N1)：文语・複雑複合助詞・新闻文学级。'],
        ['ここまで来れば、生の日本語をほぼ不自由なく読めます。',
         '用法：例句多为正式文体，注意条里附文语接续规则。'],
        ['この本を終えたら、あとは実践で磨くだけです。',
         '注意：同族辨析(いかん系列等)是本阶段最大难点。']],
}


def load_curriculum(stages):
    cur = json.loads((DATA / 'grammar' / 'curriculum.json').read_text(encoding='utf-8'))
    out = []
    for st in cur['stages']:
        if stages and st['id'] not in stages:
            continue
        out.append(st)
    return out


def load_kaishi_rank():
    """word/reading/furigana形 -> 频率 rank (行序)。"""
    rank = {}
    r = 0
    with open(DATA / 'kaishi15k_zh.tsv', encoding='utf-8-sig', newline='') as f:
        for row in csv.reader(f, delimiter='\t'):
            r += 1
            if not row or row[0].startswith('#') or len(row) < 4:
                continue
            w = (row[1] or '').strip()
            if not w:
                continue
            rank.setdefault(w, r)
            rd = (row[2] or '').strip()
            if rd:
                rank.setdefault(rd, r)
            m = re.match(r'^(.*?)\[([^\]]+)\]$', (row[4] if len(row) > 4 else '').strip())
            if m:
                rank.setdefault(m.group(1).strip(), r)
                rank.setdefault(m.group(2).strip(), r)
    return rank


def load_words():
    books = json.loads((OUT / 'jlpt_books.json').read_text(encoding='utf-8'))
    return books['levels']


def load_content():
    """data/grammar/content/gc_*.json 合并 -> {gid: [[ja,zh]x3]}"""
    content = {}
    if CONTENT_DIR.exists():
        for p in sorted(CONTENT_DIR.glob('gc_*.json')):
            content.update(json.loads(p.read_text(encoding='utf-8')))
    return content


def build_route(stages, content, allow_missing):
    rank = load_kaishi_rank()
    words = load_words()
    route = []          # 有序条目
    missing = []        # 缺内容的语法点
    gid = 0
    for st in stages:
        lv = st['level'].lower()
        wlist = words[lv]
        wlist = sorted(wlist, key=lambda r: (rank.get(r['word'],
                      rank.get(r.get('reading', ''), 10 ** 6)), r['word']))
        # 阶段头
        route.append({
            'kind': 'stage', 'stage': st['id'], 'gid': '',
            'word': f"阶段{CN_NUM[st['id'] - 1]}・{st['name']}({st['level']})",
            'reading': '', 'meaning': f"〔阶段〕{st['intro']}",
            'rows': STAGE_ROWS[st['id']],
        })
        pts = st['points']
        blk = st['block']
        pi = 0
        for i in range(0, len(wlist), blk):
            for w in wlist[i:i + blk]:
                route.append({'kind': 'word', 'stage': st['id'], 'gid': '',
                              'word': w['word'], 'reading': w.get('reading', ''),
                              'meaning': w.get('meaning', ''), 'rows': []})
            if pi >= len(pts):
                continue
            gid += 1
            g = f'G{gid:03d}'
            p = pts[pi]
            rows = content.get(g)
            if not rows:
                missing.append((g, st['level'], p['name']))
            gentry = {'kind': 'grammar', 'stage': st['id'], 'gid': g,
                      'word': f"{g} {p['name']}", 'reading': p.get('kana', ''),
                      'meaning': f"〔文法〕{p['brief']}",
                      'rows': rows or [], 'name': p['name'],
                      'brief': p['brief']}
            route.append(gentry)
            pi += 1
        # 词块耗尽后剩余语法点挂尾部
        while pi < len(pts):
            gid += 1
            g = f'G{gid:03d}'
            p = pts[pi]
            rows = content.get(g)
            if not rows:
                missing.append((g, st['level'], p['name']))
            route.append({'kind': 'grammar', 'stage': st['id'], 'gid': g,
                          'word': f"{g} {p['name']}", 'reading': p.get('kana', ''),
                          'meaning': f"〔文法〕{p['brief']}", 'rows': rows or [],
                          'name': p['name'], 'brief': p['brief']})
            pi += 1
    return route, missing


def write_xlsx(route):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment
    wb = Workbook()
    ws = wb.active
    ws.title = '语法路线'
    for e in route:
        ws.append([e['word'], e['meaning'], e['reading'], e['kind'],
                   e['gid'], e['stage']])
    for col, w in zip('ABCDEF', (26, 46, 16, 8, 8, 6)):
        ws.column_dimensions[col].width = w
    for row in ws.iter_rows(min_row=1):
        for c in row:
            c.alignment = Alignment(vertical='center', wrap_text=True)
    GB.mkdir(parents=True, exist_ok=True)
    path = GB / '语法路线.xlsx'
    wb.save(path)
    print(f'{path.name}: {len(route)} 行 (无表头)')


def write_db(route):
    path = GB / 'wcp_grammar.db'
    if path.exists():
        path.unlink()
    con = sqlite3.connect(path)
    cur = con.cursor()
    cur.execute('CREATE TABLE pron (word TEXT PRIMARY KEY, meaning TEXT)')
    cur.execute('''CREATE TABLE route (word TEXT, kind TEXT, gid TEXT,
        stage INTEGER, reading TEXT, meaning TEXT)''')
    n = 0
    for e in route:
        if not e['meaning']:
            continue
        cur.execute('INSERT OR IGNORE INTO pron VALUES (?,?)',
                    (e['word'], e['meaning']))
        n += 1
        cur.execute('INSERT INTO route VALUES (?,?,?,?,?,?)',
                    (e['word'], e['kind'], e['gid'], e['stage'],
                     e['reading'], e['meaning']))
    con.commit()
    con.close()
    print(f'{path.name}: pron {n}, route {len(route)}')


def patch_local(route):
    """占位词灌 wcpFullEng.db (pron+sentence2) / wcpOnlyWord.db (pron)。"""
    from patch_local_db import backup
    ph = [e for e in route if e['kind'] in ('grammar', 'stage')]
    words = {e['word']: {'reading': e['reading'], 'meaning': e['meaning'],
                         'ex_ja': '', 'ex_tr': ''} for e in ph}
    print(f'占位词 {len(ph)} (语法 {sum(1 for e in ph if e["kind"] == "grammar")}'
          f' + 阶段头 {sum(1 for e in ph if e["kind"] == "stage")})')
    for db, with_sent in ((SA / 'wcpFullEng.db', True),
                          (SA / 'wcpOnlyWord.db', False)):
        if not db.exists():
            print(f'{db.name}: 不存在, 跳过')
            continue
        backup(db)
        con = sqlite3.connect(str(db), timeout=30)
        con.execute('PRAGMA busy_timeout=30000')
        cur = con.cursor()
        cur.execute('BEGIN')
        wl = list(words)
        for i in range(0, len(wl), 500):
            chunk = wl[i:i + 500]
            p = ','.join('?' * len(chunk))
            cur.execute(f'DELETE FROM pron WHERE word IN ({p})', chunk)
            if with_sent:
                cur.execute(f'DELETE FROM sentence2 WHERE word IN ({p})', chunk)
        n_pron = n_sent = 0
        for e in ph:
            k = f"[{e['reading']}]" if e['reading'] else ''
            cur.execute('INSERT INTO pron (word, ukPhonic, usPhonic, meaning) '
                        'VALUES (?,?,?,?)',
                        (e['word'], k, '', e['meaning']))
            n_pron += 1
            if with_sent:
                for ja, zh in e['rows']:
                    cur.execute('INSERT INTO sentence2 (word, sentences) '
                                'VALUES (?,?)', (e['word'], f'例句：{ja}（{zh}）'))
                    n_sent += 1
        con.commit()
        # 回读
        cur.execute('SELECT COUNT(*) FROM pron WHERE word LIKE "G%" '
                    'OR word LIKE "阶段%"')
        hit = cur.fetchone()[0]
        con.close()
        print(f'{db.name}: pron +{n_pron}, sentence2 +{n_sent}, 占位词在场 {hit}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--stages', default='')
    ap.add_argument('--patch', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--allow-missing', action='store_true')
    args = ap.parse_args()
    stages = [int(x) for x in args.stages.split(',') if x.strip()]
    cur = load_curriculum(set(stages) if stages else None)
    content = load_content()
    route, missing = build_route(cur, content, args.allow_missing)
    n_g = sum(1 for e in route if e['kind'] == 'grammar')
    n_w = sum(1 for e in route if e['kind'] == 'word')
    n_ok = sum(1 for e in route if e['kind'] == 'grammar' and e['rows'])
    print(f'路线: 词 {n_w} + 语法占位 {n_g} (有内容 {n_ok}) + 阶段头 '
          f'{len(cur)}; 共 {len(route)} 行')
    if missing:
        print(f'缺内容 {len(missing)}:')
        for g, lv, name in missing:
            print(f'  {g} {lv} {name}')
        if not args.allow_missing:
            print('→ 生成 data/grammar/content/gc_*.json 后重跑, '
                  '或加 --allow-missing 先出预览')
            if not args.dry_run:
                return 1
    if args.dry_run:
        return 0
    write_xlsx(route)
    write_db(route)
    (OUT / 'grammar_route.json').write_text(
        json.dumps(route, ensure_ascii=False, indent=1), encoding='utf-8')
    print('output/grammar_route.json 已写')
    if args.patch:
        patch_local(route)
    return 0


if __name__ == '__main__':
    sys.exit(main())
