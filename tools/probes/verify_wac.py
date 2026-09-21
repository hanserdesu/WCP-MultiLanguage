import os
P = r'E:\Steam\steamapps\common\WCP-WordGirlgriend\BepInEx\plugins\WcpHost.dll'
d = open(P,'rb').read()
print("WcpHost.dll size =", len(d))
print()
print("-- 新增方法名（元数据 UTF-8）--")
for s in ['StampPrefix','SourceDirTicks','IsPresentIn','IndexBatchPerFrame']:
    print("  %-20s : %s" % (s, s.encode('utf-8') in d))
print("-- 已移除方法名（期望 False）--")
for s in ['AlreadyPresentIn','IndexTargetDir']:
    print("  %-20s : %s" % (s, s.encode('utf-8') in d))
print("-- 保留的旧 API（harness 依赖，期望 True）--")
for s in ['ListSourceFiles','AlreadyPresent','CandidateForms']:
    print("  %-20s : %s" % (s, s.encode('utf-8') in d))
print("-- 新日志文案（UTF-16LE）--")
for s in ['镜像耗时','目标库','源枚举','目标枚举']:
    print("  %-20s : %s" % (s, s.encode('utf-16-le') in d))
