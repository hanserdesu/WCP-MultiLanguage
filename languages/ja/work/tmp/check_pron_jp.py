import sqlite3, re
db = sqlite3.connect(r'E:\Steam\steamapps\common\WCP-WordGirlgriend\wcp_Data\StreamingAssets\wcpFullEng.db')
kana = re.compile(r'[\u3040-\u30ff]')
jp = set()
total = 0
for (w,) in db.execute('select word from pron'):
    total += 1
    if w and kana.search(w):
        jp.add(w)
print('pron total rows:', total)
print('distinct kana-containing words:', len(jp))
# also count via jp payload union
base = r'wcp_wordbooks/output/jp_db_payload'
pl = set()
with open(base + '\\jp_pron.tsv', encoding='utf-8') as fh:
    for line in fh:
        pl.add(line.split('\t')[0])
print('payload words:', len(pl), '| payload words missing from db pron:', len(pl - jp))
db.close()
