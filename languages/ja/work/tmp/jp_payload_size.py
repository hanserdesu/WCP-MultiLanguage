import sqlite3, sys, io, json
sys.stdout.reconfigure(encoding='utf-8')
DB = r'E:/Steam/steamapps/common/WCP-WordGirlgriend/wcp_Data/StreamingAssets/wcpFullEng.db'
JP = r'C:/Users/hanserdesu/AppData/LocalLow/WCP/wcp/MyBook.es3'
def unwrap(n):
    if isinstance(n, dict):
        if '__type' in n and 'value' in n:
            return unwrap(n['value'])
        return {k: unwrap(v) for k, v in n.items()}
    if isinstance(n, list):
        return [unwrap(x) for x in n]
    return n
book = unwrap(json.load(io.open(JP, encoding='utf-8'))['wordDictionary1'])
words = list(book.keys())
print('jp words in book:', len(words))
con = sqlite3.connect(DB)
cur = con.cursor()
cur.execute('PRAGMA table_info(pron)')
print('pron cols:', [r[1] for r in cur.fetchall()])
cur.execute('PRAGMA table_info(sentence2)')
print('sentence2 cols:', [r[1] for r in cur.fetchall()])
tot_pron = 0
tot_sent = 0
n_sent = 0
n_pron = 0
for i in range(0, len(words), 500):
    chunk = words[i:i+500]
    ph = ','.join('?' * len(chunk))
    for row in cur.execute('SELECT word, ukPhonic, usPhonic, meaning FROM pron WHERE word IN (%s)' % ph, chunk):
        tot_pron += sum(len(str(x)) for x in row)
        n_pron += 1
    for row in cur.execute('SELECT word, sentences FROM sentence2 WHERE word IN (%s)' % ph, chunk):
        tot_sent += sum(len(str(x)) for x in row)
        n_sent += 1
print('pron rows:', n_pron, 'approx bytes:', tot_pron)
print('sentence2 rows:', n_sent, 'approx bytes:', tot_sent)
con.close()
