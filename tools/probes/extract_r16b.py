# -*- coding: utf-8 -*-
"""R16 deep-dive: full key lines."""
LOG = r"D:\ATooManyLanguage\probes\log_archive\round16_real_20260919_0020.log"
lines = open(LOG, "rb").read().decode("utf-8", errors="replace").splitlines()

# 1-based line numbers of interest
for n in [149, 154, 522, 701, 706, 707, 2124, 2133, 2143, 2151, 2152, 2153, 2180, 2488]:
    print("---- L%d ----" % n)
    print(lines[n - 1])
    print()

# NRE context
print("---- NRE context (L655..L670) ----")
for i in range(654, 670):
    print("L%d: %s" % (i + 1, lines[i][:160]))

# count switch-like events: lines containing 接管语言包 in long frames
print()
print("---- 接管/切换相关长帧全列 ----")
import re
for i, l in enumerate(lines):
    if "长帧" in l and ("身份:Evaluate" in l or "接管语言包" in l):
        print("L%d: %s" % (i + 1, l))
