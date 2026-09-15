# -*- coding: utf-8 -*-
r"""将游戏词库 (wcpFullEng.db / wcpOnlyWord.db) 里的德文词条导出成持久化离线自愈补丁包。

背景: 官方更新会覆盖 StreamingAssets 下的 .db 文件，导致我们灌进去的德语释义与例句丢失。
MyBook.es3 在 AppData\LocalLow\WCP\wcp 中，更新不会被覆盖，因此词书本身保留，但例句与查词会丢失。

本脚本导出五份 TSV 补丁包并计算哈希 manifest:
  de_pron.tsv      word / ukPhonic / usPhonic / meaning    (wcpFullEng.db)
  de_sentences.tsv word / sentences                        (wcpFullEng.db)
  de_only_pron.tsv word / ukPhonic / usPhonic / meaning    (wcpOnlyWord.db)
  en_pron.tsv      英德同形词英文原版 pron                  (english_baseline)
  en_sentences.tsv 英德同形词英文原版 sentence2             (english_baseline)

英德同形词 (99 个) 的英文释义/例句不允许被德语覆盖。运行时
FrWordListMod 按当前词书在这批词上双向切换英/法内容, 因此 payload
必须同时携带两套基线。共享库稳态 = 英文原版 + 德语独有词补丁;
德语书选中时插件把同形词切成德语, 离开时切回英文。

注意: de_pron/de_sentences/de_only_pron 仍覆盖全部 3488 词 (含同形
词的德语态), 用于德语书场景 (TickSharedDbSwitch 与 RunDbHeal)。
en_pron/en_sentences 仅含同形词英文原版, 数据源是德语灌库前的
原始库副本 (work/english_baseline), 用于还原英语态。

存放到 LocalLow/de_db_payload 与 output/de_db_payload。FrWordListMod 启动时后台检测探测词，
若发现被官方更新冲掉，会自动静默重灌还原。"""
import hashlib
import io
import json
import os
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import wcp_paths

PACK_DIR_NAME = 'de_db_payload'
EN_BASE_DIR = ROOT / 'work' / 'english_baseline'


def unwrap(node):
    if isinstance(node, dict):
        if '__type' in node and 'value' in node:
            return unwrap(node['value'])
        return {k: unwrap(v) for k, v in node.items()}
    if isinstance(node, list):
        return [unwrap(x) for x in node]
    return node


def local_low_dir():
    env = os.environ.get('WCP_LOCALLOW', '').strip()
    if env:
        return Path(env)
    return Path(os.path.expanduser('~')) / 'AppData' / 'LocalLow' / 'WCP' / 'wcp'


def de_words():
    books_p = ROOT / 'output' / 'german_books.json'
    if books_p.exists():
        data = json.loads(books_p.read_text(encoding='utf-8'))
        words = set()
        for lvl in data.get('levels', {}).values():
            for item in lvl:
                if item.get('word'):
                    words.add(item['word'].strip())
        if words:
            return words
    path = local_low_dir() / 'MyBook.es3'
    data = unwrap(json.load(io.open(path, encoding='utf-8-sig')))
    words = set()
    for i in range(1, 5):
        d = data.get('wordDictionary%d' % i)
        if isinstance(d, dict):
            words.update(k for k in d if k)
    return words


def esc(s):
    return (str(s) if s is not None else '').replace('\\', '\\\\').replace('\t', '\\t').replace('\r', '').replace('\n', '\\n')


def write_tsv(path, rows):
    with io.open(path, 'w', encoding='utf-8', newline='\n') as f:
        for r in rows:
            f.write('\t'.join(esc(c) for c in r) + '\n')


def dump_pron(db, words):
    con = sqlite3.connect(str(db))
    cur = con.cursor()
    out = []
    wl = sorted(words)
    for i in range(0, len(wl), 500):
        chunk = wl[i:i + 500]
        ph = ','.join('?' * len(chunk))
        cur.execute('SELECT word, ukPhonic, usPhonic, meaning FROM pron WHERE word IN (%s)' % ph, chunk)
        out.extend(cur.fetchall())
    con.close()
    out.sort(key=lambda r: r[0])
    return out


def dump_sentences(db, words):
    con = sqlite3.connect(str(db))
    cur = con.cursor()
    out = []
    wl = sorted(words)
    for i in range(0, len(wl), 500):
        chunk = wl[i:i + 500]
        ph = ','.join('?' * len(chunk))
        cur.execute('SELECT word, sentences FROM sentence2 WHERE word IN (%s)' % ph, chunk)
        out.extend(cur.fetchall())
    con.close()
    out.sort(key=lambda r: (r[0], r[1]))
    return out


def sha256(path):
    h = hashlib.sha256()
    with io.open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 16), b''):
            h.update(b)
    return h.hexdigest()


def main():
    words = de_words()
    print('德语词条数: %d' % len(words))
    full = wcp_paths.full_db()
    only = wcp_paths.only_db()
    print('wcpFullEng.db =', full)
    print('wcpOnlyWord.db =', only)
    # 德语内容从仓库数据确定性生成 (german_books.json + sentences_master.json),
    # 不依赖当前 DB 状态 — 否则英文还原后再重跑会抓到英文内容。
    books = json.loads((ROOT / 'output' / 'german_books.json').read_text(
        encoding='utf-8'))
    master_p = ROOT / 'data' / 'translations' / 'sentences_master.json'
    master = json.loads(master_p.read_text(encoding='utf-8')) \
        if master_p.exists() else {}
    full_pron = []
    full_sent = []
    only_pron = []
    for lv in ('a1', 'a2', 'b1', 'b2'):
        for w in books['levels'][lv]:
            if w['word'] not in words:
                continue
            ipa = '[%s]' % w['ipa'] if w.get('ipa') else ''
            meaning = '%s〈%s〉' % (w['zh'], w['pos'])
            row = (w['word'], ipa, '', meaning)
            full_pron.append(row)
            only_pron.append(row)
            for de_s, zh_s in master.get(w['word'], []):
                full_sent.append((w['word'], u'例句：%s（%s）' % (de_s, zh_s)))
    full_pron.sort(key=lambda r: r[0])
    full_sent.sort(key=lambda r: (r[0], r[1]))
    only_pron.sort(key=lambda r: r[0])
    # 英文基线 (仅英德同形词) — 数据源是德语灌库前的原始库副本
    en_base = EN_BASE_DIR / 'wcpFullEng.db'
    en_pron = dump_pron(en_base, words) if en_base.exists() else []
    en_sent = dump_sentences(en_base, words) if en_base.exists() else []
    if not en_pron:
        raise RuntimeError('缺少英文基线，拒绝生成不可还原的 payload: %s' % en_base)
    overlap_file = ROOT / 'work' / 'english_overlap_words.json'
    expected_overlap = set(json.loads(overlap_file.read_text(encoding='utf-8')))
    if {row[0] for row in en_pron} != expected_overlap:
        raise RuntimeError('英文基线覆盖与同形词清单不一致，拒绝导出')
    print('FullEng pron: %d, sentence2: %d; OnlyWord pron: %d; '
          'EN overlap pron: %d, sentence2: %d'
          % (len(full_pron), len(full_sent), len(only_pron),
             len(en_pron), len(en_sent)))
    targets = [local_low_dir() / PACK_DIR_NAME, ROOT / 'output' / PACK_DIR_NAME]
    manifest = {'words': len(words), 'full_pron': len(full_pron),
                'full_sentences': len(full_sent), 'only_pron': len(only_pron),
                'en_pron': len(en_pron), 'en_sentences': len(en_sent),
                'files': {}}
    for d in targets:
        d.mkdir(parents=True, exist_ok=True)
        write_tsv(d / 'de_pron.tsv', full_pron)
        write_tsv(d / 'de_sentences.tsv', full_sent)
        write_tsv(d / 'de_only_pron.tsv', only_pron)
        if en_pron:
            write_tsv(d / 'en_pron.tsv', en_pron)
        if en_sent:
            write_tsv(d / 'en_sentences.tsv', en_sent)
        print('已生成 ->', d)
    names = ['de_pron.tsv', 'de_sentences.tsv', 'de_only_pron.tsv']
    if en_pron:
        names.append('en_pron.tsv')
    if en_sent:
        names.append('en_sentences.tsv')
    for name in names:
        manifest['files'][name] = sha256(targets[0] / name)
    with io.open(targets[0] / 'manifest.json', 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    with io.open(targets[1] / 'manifest.json', 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print('Manifest 校验完成:', json.dumps(manifest['files'], ensure_ascii=False))


if __name__ == '__main__':
    main()
