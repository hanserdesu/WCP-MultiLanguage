import os
P = r'E:\Steam\steamapps\common\WCP-WordGirlgriend\BepInEx\plugins'
d = open(os.path.join(P,'WcpHost.dll'),'rb').read()
print("WcpHost.dll size =", len(d))
for s in ['忽略(保留设备名)','单词音频兼容层完成','ScanIdleInterval','IndexTargetDir','IsReservedDeviceName']:
    print("  %-22s : %s" % (s, s.encode('utf-16-le') in d))
