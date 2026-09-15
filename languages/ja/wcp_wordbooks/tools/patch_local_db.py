# -*- coding: utf-8 -*-
"""【关键修复】把全部日文词条灌进游戏本地词库。

背景 (逆向确认 2026-09-06):
  - 每日学习界面 DatabaseManagerS8 的 databasePath = StreamingAssets/wcpFullEng.db
    查 pron(释义/音标) + sentence2(例句) + help;查不到 => 「本地暂未收录这个单词」
  - 自书字典 SelfBookMeaningDictionary 仅当书名 == 「自定义词书一~四」时由
    GetSelfBookMeaningAfterSet::SetSelfBook 装载; 每日学习模式可能不触发
  - 故需要把日文词直接写入 wcpFullEng.db; wcpOnlyWord.db(其他查词界面)同步

写入内容:
  pron:      (word, ukPhonic='[かな]', usPhonic='', meaning=游戏显示释义)
  sentence2: (word, '例句：日本語。（中文/英文翻译，如有）')

幂等: 先 DELETE 同批 word 再 INSERT。写前自动备份。
"""
import hashlib
import json
import re
import sqlite3
import shutil
import sys
import time
from pathlib import Path

import wcp_paths

sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'output'
SA = wcp_paths.streaming_assets()
FULL = wcp_paths.full_db()
ONLY = wcp_paths.only_db()
BACKUP_DIR = ROOT / 'backups'

KANA_OK = re.compile(r'^[\u3040-\u30ffー・]+$')


def collect():
    """汇总四源词条: {word: {reading, meaning, example_ja, example_zh_or_en}}"""
    words = {}

    def put(w, reading, meaning, ex_ja='', ex_tr='', prio=0):
        w = (w or '').strip()
        if not w or not meaning:
            return
        cur = words.get(w)
        if cur is None or prio > cur[0]:
            words[w] = (prio, {'reading': reading or '', 'meaning': meaning,
                               'ex_ja': ex_ja or '', 'ex_tr': ex_tr or ''})

    # 1. JLPT (优先级最高, 有例句)
    jlpt = json.loads((OUT / 'jlpt_books.json').read_text(encoding='utf-8'))
    for lv in ('n5', 'n4', 'n3', 'n2', 'n1'):
        for r in jlpt['levels'][lv]:
            put(r['word'], r.get('reading'), r.get('meaning'),
                r.get('example_ja'), r.get('example_en'), prio=3)
    # 2. SetB (会话A, 惯用句带中文例句翻译)
    setb = json.loads((OUT / 'setb_books.json').read_text(encoding='utf-8'))
    for lv, rows in setb['levels'].items():
        for r in rows:
            put(r['word'], r.get('reading'), r.get('meaning'),
                r.get('example_ja'), r.get('example_zh'), prio=2)
    # 3. 主题书 IT/商务 (会话B)
    topic = json.loads((OUT / 'topic_books.json').read_text(encoding='utf-8'))
    for tag in ('it', 'biz'):
        for r in topic['books'][tag]:
            put(r['word'], r.get('reading'), r.get('meaning'), prio=1)
    # 3b. 主题书 9-10 册 (会话C, 带日文例句)
    themed_p = OUT / 'themed_books.json'
    if themed_p.exists():
        themed = json.loads(themed_p.read_text(encoding='utf-8'))
        for tag, rows in themed.get('themes', {}).items():
            for r in rows:
                put(r['word'], r.get('reading'), r.get('meaning'),
                    r.get('example_ja'), r.get('example_zh'), prio=1)
    # 4. 常用汉字
    kanji = json.loads((OUT / 'kanji_books.json').read_text(encoding='utf-8'))
    for r in kanji['books']['kanji']:
        put(r['word'], r.get('reading'), r.get('meaning'), prio=0)
    return {w: v[1] for w, v in words.items()}


def backup(db: Path):
    """写前备份。按「库文件绝对路径」区分 —— 本机存在多份安装副本, 不能混用。"""
    BACKUP_DIR.mkdir(exist_ok=True)
    tag = hashlib.sha1(str(db.resolve()).lower().encode('utf-8')).hexdigest()[:6]
    if any(BACKUP_DIR.glob(f'{db.stem}.original_{tag}_*')):
        return None
    stamp = time.strftime('%Y%m%d_%H%M%S')
    dst = BACKUP_DIR / f'{db.stem}.original_{tag}_{stamp}{db.suffix}'
    shutil.copy2(db, dst)
    print('已备份 ->', dst.name)
    return dst


def patch(db: Path, words: dict, with_sentence: bool, force=False):
    # 幂等跳过: 三个跨源探针词的释义都一致则视为已打过补丁
    probes = ['低い', '貶す', '見積もり']
    if db.exists() and not force:
        try:
            con = sqlite3.connect(str(db), timeout=10)
            cur = con.cursor()
            hit = 0
            for p in probes:
                if p in words:
                    cur.execute('SELECT meaning FROM pron WHERE word=?', (p,))
                    row = cur.fetchone()
                    if row and row[0] == words[p]['meaning']:
                        hit += 1
            con.close()
            if hit == len([p for p in probes if p in words]):
                print(f'{db.name}: 补丁已存在(探针 {hit}/{len(probes)} 命中), 跳过 (--force 可强制)')
                return
        except sqlite3.Error:
            pass
    backup(db)
    con = sqlite3.connect(str(db), timeout=30)
    con.execute('PRAGMA busy_timeout=30000')
    cur = con.cursor()
    wl = list(words)
    # 清掉本批词的旧行 (幂等)
    cur.execute('BEGIN')
    for i in range(0, len(wl), 500):
        chunk = wl[i:i + 500]
        ph = ','.join('?' * len(chunk))
        cur.execute(f'DELETE FROM pron WHERE word IN ({ph})', chunk)
        if with_sentence:
            cur.execute(f'DELETE FROM sentence2 WHERE word IN ({ph})', chunk)
    n_pron = n_sent = 0
    # 例句主文件: {word: [[ja, zh], ...]} (apply_sentences.py 维护, 每词>=3条)
    master_p = ROOT / 'data' / 'translations' / 'sentences_master.json'
    master = json.loads(master_p.read_text(encoding='utf-8')) \
        if master_p.exists() else {}
    for i in range(0, len(wl), 500):
        chunk = wl[i:i + 500]
        ph = ','.join('?' * len(chunk))
        cur.execute(f'DELETE FROM pron WHERE word IN ({ph})', chunk)
        if with_sentence:
            cur.execute(f'DELETE FROM sentence2 WHERE word IN ({ph})', chunk)
    for w, v in words.items():
        ph = f'[{v["reading"]}]' if v['reading'] else ''
        cur.execute('INSERT INTO pron (word, ukPhonic, usPhonic, meaning) '
                    'VALUES (?,?,?,?)', (w, ph, '', v['meaning']))
        n_pron += 1
        if with_sentence:
            items = master.get(w) or []
            if not items and v['ex_ja']:
                tr = v['ex_tr'] if (v['ex_tr'] and not KANA_OK.search(v['ex_tr'])) else ''
                items = [[v['ex_ja'], tr]]
            for ja, zh in items:
                s = f'例句：{ja}（{zh}）' if zh else f'例句：{ja}'
                cur.execute('INSERT INTO sentence2 (word, sentences) '
                            'VALUES (?,?)', (w, s))
                n_sent += 1
    con.commit()
    # 回读校验
    sample = wl[len(wl) // 2]
    cur.execute('SELECT meaning FROM pron WHERE word=?', (sample,))
    ok1 = cur.fetchone()
    cur.execute('SELECT COUNT(*) FROM pron WHERE word IN (?,?)',
                (wl[0], wl[-1]))
    ok2 = cur.fetchone()[0]
    con.close()
    print(f'{db.name}: pron +{n_pron}, sentence2 +{n_sent}; '
          f'抽检[{sample}] -> {str(ok1)[:40]}; 双端命中 {ok2}/2')


def main():
    force = '--force' in sys.argv
    words = collect()
    ex = sum(1 for v in words.values() if v['ex_ja'])
    print(f'游戏目录 {wcp_paths.game_dir()}')
    print(f'汇总词条 {len(words)} (含例句 {ex})')
    patch(FULL, words, with_sentence=True, force=force)
    patch(ONLY, words, with_sentence=False, force=force)


if __name__ == '__main__':
    main()
