# -*- coding: utf-8 -*-
"""R16 real-machine log extraction: verify R16 markers + attribute lag."""
import re, sys

LOG = r"D:\ATooManyLanguage\probes\log_archive\round16_real_20260919_0020.log"
raw = open(LOG, "rb").read()
text = raw.decode("utf-8", errors="replace")
lines = text.splitlines()
print("total lines:", len(lines))

def show(patterns, label, limit=60):
    print("\n===== %s =====" % label)
    n = 0
    for i, l in enumerate(lines):
        if any(p in l for p in patterns):
            print("L%d: %s" % (i + 1, l[:230]))
            n += 1
            if n >= limit:
                print("  ... (truncated)")
                break
    if n == 0:
        print("  (none)")

# 1. R16 build markers
show(["批量写已改为写后置", "缓存复用生效", "批量写已启用"], "R16/R15 标记")

# 2. enforcement spans
show(["强制校正", "队列:规则"], "强制校正 / 队列:规则", 80)

# 3. ES3 batch
show(["批量写", "槽位词表"], "ES3 批量写 / 槽位词表", 80)

# 4. restore/labels
show(["还原:分帧", "标签还原", "装载:离开"], "还原 / 标签 / 装载", 40)

# 5. long frames (Tick)
show(["Tick", "帧长", "长帧"], "长帧记录", 60)

# 6. exceptions
show(["NullReferenceException", "MissingMethod", "TypeLoad", "Exception"], "异常", 30)
