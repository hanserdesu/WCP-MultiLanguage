import sqlite3
base = r'wcp_wordbooks/output/jp_db_payload'
for f in ['jp_pron.tsv', 'jp_only_pron.tsv', 'jp_sentences.tsv']:
    with open(base + '\\' + f, encoding='utf-8') as fh:
        n = sum(1 for _ in fh)
    print(f, 'lines:', n)
# full sentence coverage check on game db using jp_pron words
words = []
with open(base + '\\jp_pron.tsv', encoding='utf-8') as fh:
    for line in fh:
        words.append(line.split('\t')[0])
words = sorted(set(words))
print('unique jp pron words:', len(words))
db = sqlite3.connect(r'E:\Steam\steamapps\common\WCP-WordGirlgriend\wcp_Data\StreamingAssets\wcpFullEng.db')
ok = 0
chunk = 500
for i in range(0, len(words), chunk):
    part = words[i:i+chunk]
    ph = ','.join('?' for _ in part)
    got = {r[0] for r in db.execute(f'select word from sentence2 where word in ({ph}) group by word having count(*) >= 3', part)}
    ok += len(got)
print(f'JP words with >=3 sentences: {ok}/{len(words)}')
db.close()
