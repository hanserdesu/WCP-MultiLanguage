import os, time, tempfile
# 交叉确认假设：Windows 上「目录 mtime」在增删文件后确实会变化。
d = tempfile.mkdtemp(prefix='wcp_dirmtime_')
t0 = os.stat(d).st_mtime_ns
time.sleep(1.1)
open(os.path.join(d,'a.mp3'),'wb').write(b'1')
t1 = os.stat(d).st_mtime_ns
time.sleep(1.1)
# 覆盖已有文件内容：目录 mtime 是否变？（这是我们关心的边界）
open(os.path.join(d,'a.mp3'),'wb').write(b'22')
t2 = os.stat(d).st_mtime_ns
time.sleep(1.1)
open(os.path.join(d,'b.mp3'),'wb').write(b'3')
t3 = os.stat(d).st_mtime_ns
time.sleep(1.1)
os.remove(os.path.join(d,'b.mp3'))
t4 = os.stat(d).st_mtime_ns
print("空目录基线      :", t0)
print("新增 a.mp3      :", t1, "CHANGED" if t1!=t0 else "same")
print("覆盖 a.mp3 内容 :", t2, "CHANGED" if t2!=t1 else "SAME(未变)")
print("新增 b.mp3      :", t3, "CHANGED" if t3!=t2 else "same")
print("删除 b.mp3      :", t4, "CHANGED" if t4!=t3 else "same")
os.remove(os.path.join(d,'a.mp3')); os.rmdir(d)
