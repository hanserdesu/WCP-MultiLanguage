import io
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

DB = r'E:\Steam\steamapps\common\WCP-WordGirlgriend\wcp_Data\StreamingAssets\wcpOnlyWord.db'
conn = sqlite3.connect(DB)
cur = conn.cursor()

cur.execute("select name from sqlite_master where type='table'")
print("tables:", [r[0] for r in cur.fetchall()])

cur.execute("select count(*) from pron")
print("pron rows:", cur.fetchone()[0])

samples = ['割れる', '黄色', '続ける', '歯医者', 'superiority', 'yellow', 'continue']
marks = "?" * len(samples)
cur.execute("select word from pron where word in (%s)" % ",".join(marks), samples)
print("sample hits:", sorted(r[0] for r in cur.fetchall()))

cur.execute("select word from pron")
words = [r[0] for r in cur.fetchall()]
jp = [w for w in words if any(0x3040 <= ord(c) <= 0x30FF or 0x4E00 <= ord(c) <= 0x9FFF for c in w)]
print("total %d, jp-like %d" % (len(words), len(jp)))
print("jp-like sample:", jp[:15])

cur.execute("select word, meaning from pron limit 3")
for w, m in cur.fetchall():
    print("row:", w, "=>", (m or "")[:60])

cur.execute("select word, usPhonic, ukPhonic from pron where word='superiority'")
print("superiority phonetics:", cur.fetchall())
