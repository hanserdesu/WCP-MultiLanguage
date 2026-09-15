import glob, json, sqlite3, os
# gen_words chunk size
files = sorted(glob.glob(r'wcp_wordbooks/work/gen_words_*.json'))
if files:
    d = json.load(open(files[0], encoding='utf-8'))
    n = len(d) if isinstance(d, list) else len(d.get('words', d))
    print('gen_words[0] entries:', n)
    total = sum((lambda x: len(x) if isinstance(x, list) else len(x.get('words', x)))(json.load(open(f, encoding='utf-8'))) for f in files)
    print('gen_words total entries:', total, 'across', len(files), 'files')
# gen_out total words
outs = sorted(glob.glob(r'wcp_wordbooks/work/gen_out_*.json'))
print('gen_out files:', len(outs))
# grammar db
g = sqlite3.connect(r'wcp_wordbooks/output/grammar_book/wcp_grammar.db')
tables = [r[0] for r in g.execute("select name from sqlite_master where type='table'")]
print('grammar tables:', tables)
for t in tables:
    try:
        print(' ', t, g.execute(f'select count(*) from {t}').fetchone()[0])
    except Exception as e:
        print(' ', t, 'err', e)
g.close()
# game db jp coverage
db = sqlite3.connect(r'E:\Steam\steamapps\common\WCP-WordGirlgriend\wcp_Data\StreamingAssets\wcpFullEng.db')
jp_words = [r[0] for r in db.execute("select distinct word from pron where word glob '*[぀-ヿ]*' or word glob '*[归来]*'")]
print('distinct kana-word pron rows (approx JP):', len(jp_words))
if jp_words:
    ph = ','.join('?' for _ in jp_words[:900])
    sample = jp_words[:900]
    low = db.execute(f'select count(*) from (select word from sentence2 where word in ({ph}) group by word having count(*) >= 3)', sample).fetchone()[0]
    print(f'sample JP words with >=3 sentences: {low}/{len(sample)}')
db.close()
