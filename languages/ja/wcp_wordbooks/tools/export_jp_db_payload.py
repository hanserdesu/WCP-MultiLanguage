# -*- coding: utf-8 -*-
r"""把游戏词库(wcpFullEng.db / wcpOnlyWord.db)里的日文词条导出成可持久化的补丁包。

背景: 官方更新会覆盖 StreamingAssets 下的 .db, 而我们灌进去的日文释义/例句只在 DB 里。
MyBook.es3(LocalLow, 用户数据)不会被更新覆盖, 所以词书本体会留着, 但例句会丢。

这里把 DB 里的日文词条抽成两份 TSV, 存到 LocalLow(更新不会碰) + 仓库 output(可版本化):
  jp_pron.tsv      word / ukPhonic / usPhonic / meaning    (wcpFullEng.db)
  jp_sentences.tsv word / sentences                        (wcpFullEng.db)
  jp_only_pron.tsv word / ukPhonic / usPhonic / meaning    (wcpOnlyWord.db)
插件启动时若发现 DB 里没有这些词, 会用这份补丁包自动重新灌回去。
"""
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
import wcp_paths  # noqa: E402

PACK_DIR_NAME = 'jp_db_payload'


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


def jp_words():
    """词书里出现的全部词 (wordDictionary1..4 的键)。"""
    path = local_low_dir() / 'MyBook.es3'
    data = unwrap(json.load(io.open(path, encoding='utf-8')))
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
    words = jp_words()
    print('词书词条 %d' % len(words))
    full = wcp_paths.full_db()
    only = wcp_paths.only_db()
    print('wcpFullEng.db =', full)
    print('wcpOnlyWord.db =', only)
    full_pron = dump_pron(full, words)
    full_sent = dump_sentences(full, words)
    only_pron = dump_pron(only, words)
    print('FullEng pron %d, sentence2 %d; OnlyWord pron %d'
          % (len(full_pron), len(full_sent), len(only_pron)))
    targets = [local_low_dir() / PACK_DIR_NAME, ROOT / 'output' / PACK_DIR_NAME]
    manifest = {'words': len(words), 'full_pron': len(full_pron),
                'full_sentences': len(full_sent), 'only_pron': len(only_pron),
                'files': {}}
    for d in targets:
        d.mkdir(parents=True, exist_ok=True)
        write_tsv(d / 'jp_pron.tsv', full_pron)
        write_tsv(d / 'jp_sentences.tsv', full_sent)
        write_tsv(d / 'jp_only_pron.tsv', only_pron)
        print('written ->', d)
    for name in ('jp_pron.tsv', 'jp_sentences.tsv', 'jp_only_pron.tsv'):
        manifest['files'][name] = sha256(targets[0] / name)
    with io.open(targets[0] / 'manifest.json', 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    with io.open(targets[1] / 'manifest.json', 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print('manifest:', json.dumps(manifest['files'], ensure_ascii=False))


if __name__ == '__main__':
    main()
