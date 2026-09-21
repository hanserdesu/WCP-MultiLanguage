"""Round-7 (2026-09-18) deployment verification for WcpHost.dll.

Why this file exists: the skill's rule is "不要用文件大小或时间戳判断改动有没有
编译进 DLL" —— PE 有节对齐，加几十字节代码可能完全不改变文件大小。唯一可靠的
办法是在 DLL 二进制里搜**字符串常量**（.NET 元数据里的字符串是 UTF-16LE）。

而且注释不会进 DLL（csc 不带 /doc），所以探针只能看见"代码里的字面量"。
本项目里恰好每个待验证的改动都有一句独有的日志/键名字面量，逐条对上即可：
  新增（必须 TRUE）
    wcp_owned_prefixes      所有权索引键名（RecoverStale 的 1 次读替代 2N 次读）
    本帧 Top=                探针改成按标签聚合后的新输出格式
    窗口 Top（累计）=        同上
    SaveFile.es3            DiskBookName 缓存判据改挂到正确的文件
  删除（必须 FALSE）
    身份:同名校正            删掉的重复 Enforce 分支的标签
    本帧最慢操作=            只报最外层作用域的旧字段（结构上无法给出信息）
    最深阶段=                同上
"""
import hashlib
import os

PLUGINS = r'E:\Steam\steamapps\common\WCP-WordGirlgriend\BepInEx\plugins'
REPO = r'D:\ATooManyLanguage\MultiLanguage\mod_host'

MUST_HAVE = ['wcp_owned_prefixes', '本帧 Top=', '窗口 Top（累计）=', 'SaveFile.es3',
             'ES3:槽位词表', '运行态:Tick', '槽位词表']
MUST_NOT_HAVE = ['身份:同名校正', '本帧最慢操作=', '最深阶段=']


def sha(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


def main():
    repo_dll = os.path.join(REPO, 'WcpHost.dll')
    game_dll = os.path.join(PLUGINS, 'WcpHost.dll')
    hr, hg = sha(repo_dll), sha(game_dll)
    print('repo  WcpHost.dll %s  %d B' % (hr, os.path.getsize(repo_dll)))
    print('game  WcpHost.dll %s  %d B' % (hg, os.path.getsize(game_dll)))
    print('byte-identical: %s' % ('YES' if hr == hg else 'NO'))
    print()

    data = open(game_dll, 'rb').read()
    ok = True
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
