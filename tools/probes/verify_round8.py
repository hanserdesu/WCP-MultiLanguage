"""Round-8 (2026-09-18) deployment verification for WcpHost.dll.

Why this file exists: 文件大小/时间戳都不能证明改动编译进了 DLL（PE 有节对齐）。
唯一可靠的办法是在二进制里搜**字符串常量**（.NET 元数据字符串是 UTF-16LE）。
注释不进 DLL（csc 不带 /doc），所以探针只能看见代码里的字面量 —— 本项目里刚好
每个待验证的改动都有一句独有的字面量（反射用的类型名/方法名）。

本轮改动：ES3 整文件写 → 批量写（ES3.CacheFile / ES3.Save(settings) /
ES3.StoreCachedFile）。反射目标名就是天然探针，且这些名字**只在 GameAdapter.cs
的第八轮代码里出现**（离线 grep 核对过），所以命中即可判定 Round-8 代码在 DLL 里。

证据等级：本脚本只证明「新代码在部署的 DLL 里，且 repo 与游戏目录逐字节一致」。
它**不**证明性能收益 —— 性能证据在 probes/es3bench/es3_ab_report.txt（真实 ES3
程序集 + 真实 6MB 存档副本的 A/B），实机数字要等用户进游戏后读 Player.log。
"""
import hashlib
import os

PLUGINS = r'E:\Steam\steamapps\common\WCP-WordGirlgriend\BepInEx\plugins'
REPO = r'D:\ATooManyLanguage\MultiLanguage\mod_host'

# 第八轮新增的反射目标名（只在 GameAdapter.cs 的批量写代码里出现）。
MUST_HAVE = [
    'ES3Settings',        # AccessTools.TypeByName("ES3Settings")
    'defaultSettings',    # ES3Settings.defaultSettings（格式契约来源）
    'StoreCachedFile',    # ES3.StoreCachedFile（一次整档写提交）
    'RemoveCachedFile',   # ES3File.RemoveCachedFile（收尾清我们自己的缓存条目）
    'CacheFile',          # ES3.CacheFile（一次整档读装载）
    'ES3:批量写(装载)',    # PerfProbe 标签：装载
    'ES3:批量写(提交)',    # PerfProbe 标签：提交
    # ── 第六/七轮的字面量必须仍在（防回归）──
    'wcp_owned_prefixes', '本帧 Top=', '窗口 Top（累计）=', 'SaveFile.es3',
    '运行态:Tick', '槽位词表',
]
# 第七轮已经删掉的结构性旧字段。它们必须保持消失。
MUST_NOT_HAVE = ['身份:同名校正', '本帧最慢操作=', '最深阶段=']


def sha(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


def main():
    repo_dll = os.path.join(REPO, 'WcpHost.dll')
    game_dll = os.path.join(PLUGINS, 'WcpHost.dll')
    hr, hg = sha(repo_dll), sha(game_dll)
    print('repo  WcpHost.dll %s  %d B' % (hr, os.path.getsize(repo_dll)))
    print('game  WcpHost.dll %s  %d B' % (hg, os.path.getsize(game_dll)))
    identical = hr == hg
    print('byte-identical: %s' % ('YES' if identical else 'NO'))
    print()

    # 探针读**部署的那一份**：用户实际加载的才是要验的对象。
    data = open(game_dll, 'rb').read()
    ok = identical
    for s in MUST_HAVE:
        hit = s.encode('utf-16-le') in data
        ok = ok and hit
        print('  %-22s present=%s' % (s, hit))
    print()
    for s in MUST_NOT_HAVE:
        hit = s.encode('utf-16-le') in data
        ok = ok and (not hit)
        print('  %-22s still_present=%s  (期望 False)' % (s, hit))
    print()
    print('RESULT: %s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
