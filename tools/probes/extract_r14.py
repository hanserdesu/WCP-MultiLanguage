# -*- coding: utf-8 -*-
"""R14 real-machine log extraction: verify three predictions + switch-frame attribution."""
import re, sys

LOG = r"D:\ATooManyLanguage\probes\log_archive\round14_real_20260918_2314.log"
data = open(LOG, "rb").read()
text = data.decode("utf-8", errors="replace")
lines = text.splitlines()
print("total lines:", len(lines))

def find_all(pat, flags=0, limit=40):
    out = []
    for i, l in enumerate(lines):
        if re.search(pat, l, flags):
            out.append((i + 1, l.strip()))
            if len(out) >= limit:
                break
    return out

# 0. build identity
print("\n===== [0] build identity =====")
for n, l in find_all(r"WcpHost|版本|Version", limit=10):
    print(n, l[:140])

# 1. slot re-resolution cost per switch
print("\n===== [1] 槽位归属:重解析 =====")
for n, l in find_all(r"槽位归属:重解析"):
    print(n, l[:160])

# 2. row fingerprint cost + memo hits
print("\n===== [2] 槽位归属:行指纹 / memo =====")
for n, l in find_all(r"槽位归属:行指纹|MemoHits|指纹缓存|FNV"):
    print(n, l[:160])

# 3. queue rules cost
print("\n===== [3] 队列:规则 =====")
for n, l in find_all(r"队列:规则"):
    print(n, l[:160])

# 4. window summaries
print("\n===== [4] 10s 窗口汇总 =====")
for n, l in find_all(r"窗口|窗口汇总|TopN", limit=60):
    print(n, l[:200])

# 5. long frames
print("\n===== [5] 长帧 =====")
for n, l in find_all(r"长帧|Tick|frameMs|帧耗时", limit=60):
    print(n, l[:200])

# 6. errors / exceptions
print("\n===== [6] 异常 =====")
for n, l in find_all(r"Exception|错误|Error", flags=re.IGNORECASE, limit=30):
    print(n, l[:160])

# 7. batch scope / ES3
print("\n===== [7] ES3 批量 =====")
for n, l in find_all(r"ES3|批量写|装载:提交|装载:落盘", limit=40):
    print(n, l[:160])
