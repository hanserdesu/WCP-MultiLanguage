# -*- coding: utf-8 -*-
"""解析 Steam 云同步缓存 remotecache.vdf，统计同步范围与体积。"""
import re
from collections import defaultdict
from pathlib import Path

VDF = Path(r'E:/Steam/userdata/1427245836/1981560/remotecache.vdf')

text = VDF.read_text(encoding='utf-8', errors='replace')
lines = text.splitlines()

# 条目形如：  "WCP/wcp/xxx"
#             {
#               "size"  "123"
entries = []  # (path, size)
path_re = re.compile(r'^\t"([^"]+)"\s*$')
size_re = re.compile(r'^\t\t"size"\s+"(\d+)"')
cur = None
for i, line in enumerate(lines):
    m = path_re.match(line)
    if m:
        cur = m.group(1)
        # 下一行应是 {
        if i + 1 < len(lines) and lines[i + 1].strip() == '{':
            continue
        cur = None
        continue
    m = size_re.match(line)
    if m and cur:
        entries.append((cur, int(m.group(1))))
        cur = None

print('同步条目总数:', len(entries))
total = sum(s for _, s in entries)
print('同步总体积: %.1f MB' % (total / 1048576))

groups = defaultdict(lambda: [0, 0])
for p, s in entries:
    parts = p.split('/')
    key = '/'.join(parts[:3]) if len(parts) > 3 else p
    g = groups[key]
    g[0] += 1
    g[1] += s

print()
print('%-46s %8s %12s' % ('路径前缀（前 3 段）', '文件数', '体积 MB'))
for key in sorted(groups, key=lambda k: -groups[k][1]):
    n, s = groups[key]
    print('%-46s %8d %12.2f' % (key, n, s / 1048576))

print()
print('=== 关键文件是否在同步范围 ===')
keys = ['WCP/wcp/MyBook.es3', 'WCP/wcp/SaveFile.es3', 'WCP/wcp/WcpCustomSlots.json',
        'WCP/wcp/jpmod_install.json', 'WCP/wcp/hub-state.json']
for k in keys:
    hit = [e for e in entries if e[0] == k]
    print('%-40s %s' % (k, ('在，%d 字节' % hit[0][1]) if hit else '不在'))
print()
print('=== 大目录明细（>=100 文件）===')
for key in sorted(groups, key=lambda k: -groups[k][0]):
    n, s = groups[key]
    if n >= 100:
        print('%-46s %8d 文件 %10.1f MB' % (key, n, s / 1048576))
