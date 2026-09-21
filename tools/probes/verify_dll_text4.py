import os, glob
P = r'E:\Steam\steamapps\common\WCP-WordGirlgriend\BepInEx\plugins'
d = open(os.path.join(P,'WcpHost.dll'),'rb').read()
print("WcpHost.dll size =", len(d))
print("-- 方法名在元数据里是 UTF-8，须按 ASCII 字节找 --")
for s in ['IndexTargetDir','IsReservedDeviceName','AlreadyPresentIn','EnsureManagers','ScanIdleInterval','_mirrorRoutine']:
    print("  %-24s : %s" % (s, s.encode('utf-8') in d))
print("-- 中文日志文案（UTF-16LE）--")
for s in ['忽略(保留设备名)','单词音频兼容层完成']:
    print("  %-24s : %s" % (s, s.encode('utf-16-le') in d))
print()
print("-- 仓库侧 WcpHost.dll 位置 --")
for p in glob.glob(r'D:\ATooManyLanguage\MultiLanguage\**\WcpHost.dll', recursive=True):
    print("  ", p, os.path.getsize(p))
