# check_gates_r13.py — 汇总四个门禁的结果行（绕开 bash 文本工具偶发缺失）
import io
import sys

FILES = [
    (r"D:\ATooManyLanguage\work\takeover_out.txt", ["PASS", "FAIL", "Failures"]),
    (r"D:\ATooManyLanguage\work\gate_registry.txt", ["PASS", "FAIL", "Failures", "结果:"]),
    (r"D:\ATooManyLanguage\work\gate_slot.txt", ["PASS", "FAIL", "Failures", "ALL"]),
    (r"D:\ATooManyLanguage\work\gate_wac.txt", ["PASS", "FAIL", "Failures"]),
]

for path, keys in FILES:
    print("=== " + path.split("\\")[-1] + " ===")
    try:
        lines = io.open(path, encoding="utf-8", errors="replace").read().splitlines()
    except IOError as e:
        print("  READ ERROR: " + str(e))
        continue
    npass = sum(1 for l in lines if l.startswith("  PASS") or l.startswith("PASS "))
    nfail = sum(1 for l in lines if l.startswith("  FAIL") or l.startswith("FAIL "))
    print("  PASS lines: %d   FAIL lines: %d" % (npass, nfail))
    tail = [l for l in lines if any(k in l for k in keys)]
    for l in tail[-4:]:
        print("  " + l[:200])
print("DONE")
