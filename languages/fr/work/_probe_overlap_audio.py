# -*- coding: utf-8 -*-
import hashlib, json, pathlib, sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
m = json.load(open('D:/French/data/translations/sentences_master.json', encoding='utf-8'))
d = pathlib.Path.home() / 'AppData/LocalLow/WCP/wcp/sentence_audio'
db = sqlite3.connect('D:/French/backups/wcpFullEng.before_french_e32c01_20260913_101456.db')
eng = set(x[0] for x in db.execute('SELECT word FROM pron'))
db.close()
books = json.load(open('D:/French/output/french_books.json', encoding='utf-8'))
fr = {w['word'] for lv in books['levels'] for w in books['levels'][lv]}
ov = sorted(fr & eng)
print('overlap', len(ov))
miss = 0
for w in ov:
    for frs, zh in m.get(w, [])[:3]:
        p = d / (hashlib.md5(frs.encode('utf-8')).hexdigest() + '.mp3')
        if not p.exists():
            miss += 1
print('missing french sentence audio for overlap words:', miss)
