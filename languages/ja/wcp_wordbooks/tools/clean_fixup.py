# -*- coding: utf-8 -*-
"""Remove no-op entries (key == value) from WORD_FIX in fixup_words.py"""
import re
p = 'D:/ATooManyLanguage/Japanese/wcp_wordbooks/tools/fixup_words.py'
src = open(p, encoding='utf-8').read()
# remove lines like "    'X': 'X'," where key==value
lines = src.split('\n')
out = []
removed = 0
for line in lines:
    m = re.match(r"^    '(.+)': '(.+)',$", line)
    if m and m.group(1) == m.group(2):
        removed += 1
        continue
    out.append(line)
open(p, 'w', encoding='utf-8').write('\n'.join(out))
print(f'removed {removed} no-op entries')
