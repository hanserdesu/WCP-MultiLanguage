# -*- coding: utf-8 -*-
"""Merge helper: python _merge.py <chunkfile>"""
import json, io, sys, importlib.util

p = r"D:\French\work\gen_out_62_0.json"
spec = importlib.util.spec_from_file_location("chunk", sys.argv[1])
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
base = json.load(io.open(p, encoding="utf-8"))
for k in list(base):
    if k.endswith("_SKIP") or k.endswith("_placeholder"):
        base.pop(k)
base.update(m.D)
json.dump(base, io.open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("keys:", len(base))
