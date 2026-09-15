import sqlite3
base = r'wcp_wordbooks/output/jp_db_payload'
words = set()
with open(base + '\\jp_pron.tsv', encoding='utf-8') as fh:
    for line in fh:
        words.add(line.split('\t')[0])
db = sqlite3.connect(r'E:\Steam\steamapps\common\WCP-WordGirlgriend\wcp_Data\StreamingAssets\wcpFullEng.db')
in_db = set()
chunk = 500
wl = sorted(words)
for i in range(0, len(wl), chunk):
    part = wl[i:i+chunk]
    ph = ','.join('?' for _ in part)
    in_db.update(r[0] for r in db.execute(f'select distinct word from pron where word in ({ph})', part))
print('payload words found in db pron:', len(in_db & words), '/', len(words))
missing = sorted(words - in_db)
print('missing:', len(missing), missing[:20])
db.close()
