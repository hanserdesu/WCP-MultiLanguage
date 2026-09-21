# -*- coding: utf-8 -*-
"""从 Player.log 按行号精确提取（Python 按字节读 -> 保证 UTF-8 不被管道破坏）。"""
import sys, io

LOG = r"C:\Users\hanserdesu\AppData\LocalLow\WCP\wcp\Player.log"
OUT = r"D:\ATooManyLanguage\probes\log_archive\round11_build_6f7becf4.txt"

raw = open(LOG, "rb").read()
lines = raw.split(b"\n")

targets = [144, 146, 149, 156, 435, 436, 519, 527, 528, 548, 549,
           551, 574, 581, 582, 583, 590, 592, 596, 608, 615,
           645, 646, 648, 699, 700, 701, 704]

out = io.open(OUT, "w", encoding="utf-8", newline="\r\n")
out.write(u"# 第十一轮构建（WcpHost.dll 6f7becf4dae...）实机日志证据\n")
out.write(u"# 源：" + LOG + u"\n")
out.write(u"# 文件 %d B；采集时间 2026-09-18 20:41:5x（mtime 20:41:33）\n" % len(raw))
out.write(u"# 行号即原文件行号。本文件由 Python 逐字节解码写出，无管道截断。\n\n")

for n in targets:
    if n - 1 >= len(lines):
        out.write(u"--- L%d --- (超出文件范围)\n\n" % n)
        continue
    try:
        s = lines[n - 1].decode("utf-8")
    except Exception as e:
        s = u"<decode fail: %s>" % e
    out.write(u"--- L%d ---\n%s\n\n" % (n, s))

# 附带：所有含 ES3:批量写 / 队列: / 装载: 的行的行号与内容
out.write(u"\n===== 标签检索 =====\n")
marks = [u"ES3:批量写", u"队列:", u"装载:", u"槽位归属", u"运行态:书名扫描", u"场景:强制校正"]
for m in marks:
    hits = []
    for i, ln in enumerate(lines):
        try:
            s = ln.decode("utf-8")
        except Exception:
            continue
        if m in s:
            hits.append(i + 1)
    out.write(u"\n-- %s : %d 行  行号=%s\n" % (m, len(hits), ",".join(str(h) for h in hits)))

out.close()
print("ok ->", OUT)
