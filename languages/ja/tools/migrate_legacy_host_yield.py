# -*- coding: utf-8 -*-
"""把"旧词表插件让位宿主"的隔离规则一次性写进 5 个语言词表插件。

背景(2026-09-15 根因): 5 个词表插件都往同一批全局方法挂补丁, 两个插件同时在场时
后写者胜 —— 上一本书的词会串进新书("俄语切日语后还出俄语")。修复方向是让语言包
只提供资源, 运行时补丁只有一个所有者(宿主 WcpHost):

  * 宿主把"确实成功接管的语言"落盘到 <BepInEx>/config/WcpHost.managed.txt;
  * 旧词表插件在 Awake 里读这份登记, 自己的语言在列就整场不打补丁(只留资源),
    并用 Legacy/YieldToHost 留一个强制旧模式的逃生门。

顺带清掉法语模板残留(FR/DE/YUE 里 FrenchBookSelected/FrenchProbeOk/frOk*/PlayFrenchWord、
粤语插件里印着 DEWordList 的日志与插件名), 让"新增语言 = 只给资源"成立。

脚本按字节保留原文件的 BOM 与换行; 每个锚点都要求出现次数精确命中, 任一不符即整体中止。
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TARGETS = [
    dict(path=r"Japanese\mod_jp_wordlist\JpWordListMod.cs", code="ja",
         tag="JPWordList", lang="日语", attr='"WCP JP Word List", "1.7.6"', ver_new="1.7.7",
         dbpack="jp_db_payload", attr_count=1, renames=False, template=False),
    dict(path=os.path.join("French", "mod_fr_wordlist", "FrWordListMod.cs"), code="fr",
         tag="FRWordList", lang="法语", attr='"WCP FR Word List", "1.1.0"', ver_new="1.2.0",
         dbpack="fr_db_payload", attr_count=1, renames=True, template=True),
    dict(path=os.path.join("German", "mod_de_wordlist", "DeWordListMod.cs"), code="de",
         tag="DEWordList", lang="德语", attr='"WCP DE Word List", "1.1.0"', ver_new="1.2.0",
         dbpack="de_db_payload", attr_count=1, renames=True, template=True,
         profile_id="catbar-german-complete"),
    dict(path=os.path.join("Russian", "mod_ru_wordlist", "RuWordListMod.cs"), code="ru",
         tag="RUWordList", lang="俄语", attr='"WCP RU Word List", "1.1.0"', ver_new="1.2.0",
         dbpack="ru_db_payload", attr_count=1, renames=False, template=False),
    dict(path=os.path.join("Contonese", "mod_yue_wordlist", "YueWordListMod.cs"), code="yue",
         tag="YueWordList", lang="粤语", attr='"WCP DE Word List", "1.1.0"',
         attr_new='"WCP Yue Word List", "1.2.0"', ver_new="1.2.0",
         dbpack="yue_db_payload", attr_count=1, renames=True, template=True,
         profile_id="catbar-cantonese-complete"),
]

RENAMES = [
    ("FrenchBookSelected", "ManagedBookSelected", 2),
    ("FrenchProbeOk", "ManagedProbeOk", 3),
    ("frOkFull", "probeOkFull", 3),
    ("frOkOnly", "probeOkOnly", 3),
    ("PlayFrenchWord", "PlayLocalWordAudio", 2),
]


def read(path):
    with open(path, "rb") as fh:
        raw = fh.read()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw[3:].decode("utf-8") if bom else raw.decode("utf-8")
    nl = "\r\n" if "\r\n" in text else "\n"
    return text, nl, bom


def write(path, text, nl, bom):
    data = text.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    with open(path, "wb") as fh:
        fh.write(data)
    return len(data)


def count(text, needle):
    return text.count(needle)


def replace_once(text, old, new, expected=1):
    got = count(text, old)
    if got != expected:
        raise AssertionError("锚点计数不符: %r 期望 %d 实际 %d" % (old[:60], expected, got))
    return text.replace(old, new)


def insert_after_line(text, anchor, block, nl):
    """在包含 anchor 的整行之后插入 block(block 内不带换行, 这里补)。"""
    got = count(text, anchor)
    if got != 1:
        raise AssertionError("锚点计数不符: %r 期望 1 实际 %d" % (anchor[:60], got))
    start = text.index(anchor)
    line_end = text.index(nl, start)
    return text[:line_end + len(nl)] + block + nl + text[line_end + len(nl):]


def yield_block(tag, lang, code, nl):
    lines = [
        '            _yieldToHost = Config.Bind("Legacy", "YieldToHost", true,',
        '                "宿主 WcpHost 接管本语言后, 旧词表插件自动让位(只保留语言资源)。'
        '设 false 强制以旧模式运行。");',
        '            if (HostTakesOver())',
        '            {',
        '                Log.LogWarning("' + tag + ': WcpHost 已接管' + lang +
        ', 旧词表插件不再打补丁 (Legacy/YieldToHost=false 可强制旧模式)。");',
        '                return;',
        '            }',
    ]
    return nl.join(lines)


def helper_block(tag, code, nl):
    lines = [
        '        // 语言资源隔离: 宿主 (WcpHost) 成功接管本语言后, 运行时补丁只能有一个所有者。',
        '        // 两个插件争抢同一批补丁时"后写者胜", 上一本书的词会串进新书 —— 这就是',
        '        // "俄语切日语后还出俄语"的成因。判定看宿主落盘的受管语言登记',
        '        // (<BepInEx>/config/WcpHost.managed.txt), 而不是"文件是否存在":',
        '        // 宿主没装或没接管本语言时, 本插件照旧按旧模式工作。',
        '        private static bool HostTakesOver()',
        '        {',
        '            try',
        '            {',
        '                if (_yieldToHost == null || !_yieldToHost.Value) return false;',
        '                string dir = Paths.ConfigPath;',
        '                if (string.IsNullOrEmpty(dir)) return false;',
        '                string marker = System.IO.Path.Combine(dir, "WcpHost.managed.txt");',
        '                if (!System.IO.File.Exists(marker)) return false;',
        '                string[] codes = System.IO.File.ReadAllLines(marker);',
        '                for (int i = 0; i < codes.Length; i++)',
        '                    if (string.Equals(codes[i].Trim(), PackLangCode, StringComparison.OrdinalIgnoreCase))',
        '                        return true;',
        '                return false;',
        '            }',
        '            catch (Exception e)',
        '            {',
        '                // 判定失败保持旧行为: 宿主不存在才是常态, 不能因为读不到文件就停摆。',
        '                Log.LogWarning("' + code + ' ' + tag + ': 宿主接管判定失败, 按旧模式继续打补丁: " + e.Message);',
        '                return false;',
        '            }',
        '        }',
        '',
    ]
    return nl.join(lines)


def migrate(target):
    path = os.path.join(ROOT, target["path"])
    text, nl, bom = read(path)
    if "YieldToHost" in text:
        print("SKIP %-58s 已迁移" % target["path"])
        return
    applied = []

    # 1) 配置字段
    text = insert_after_line(
        text,
        "        private static ConfigEntry<bool> _allowLegacySharedDbWrites;",
        "        private static ConfigEntry<bool> _yieldToHost;", nl)
    applied.append("decl")

    # 2) 语言代码常量(锚在 DbPackDir 之后)
    dbpack = 'private const string DbPackDir = "' + target["dbpack"] + '";'
    if "PackLangCode" in text:
        raise AssertionError("%s 里已经有 PackLangCode" % target["path"])
    text = insert_after_line(
        text, dbpack,
        nl + "        // 宿主资源包的语言代码: packs/<PackLangCode>/manifest.json" + nl +
        '        private const string PackLangCode = "' + target["code"] + '";', nl)
    applied.append("packlang")

    # 3) Awake 里的让位门(插在 AllowSharedDatabaseWrites 绑定语句之后)
    bind = '            _allowLegacySharedDbWrites = Config.Bind("Legacy", "AllowSharedDatabaseWrites", false,'
    if count(text, bind) != 1:
        raise AssertionError("AllowSharedDatabaseWrites 绑定锚点计数异常")
    start = text.index(bind)
    end = text.index(nl, text.index(");", start))
    text = (text[:end + len(nl)] +
            yield_block(target["tag"], target["lang"], target["code"], nl) + nl +
            text[end + len(nl):])
    applied.append("yield_gate")

    # 4) HostTakesOver 辅助方法(插在 PatchAll 之前)
    text = replace_once(text, "        private void PatchAll()",
                        helper_block(target["tag"], target["code"], nl) +
                        "        private void PatchAll()")
    applied.append("helper")

    # 5) 法语模板残留改名
    if target["renames"]:
        for old, new, expect in RENAMES:
            text = replace_once(text, old, new, expect)
        applied.append("renames")

    # 6) 按语言修插件名/版本/日志前缀
    if "attr_new" in target:
        text = replace_once(text, target["attr"], target["attr_new"], target["attr_count"])
        text = replace_once(text, "DEWordList:", "YueWordList:", 11)
        applied.append("name_and_log")
    else:
        text = replace_once(text, target["attr"],
                            target["attr"].replace('"1.1.0"', '"1.2.0"').replace('"1.7.6"', '"1.7.7"'),
                            target["attr_count"])
        applied.append("version")

    # 7) 头部注释里的模板指纹
    if "profile_id" in target:
        text = replace_once(text, "catbar-french-cefr-complete", target["profile_id"], 1)
        applied.append("profile_comment")

    size = write(path, text, nl, bom)
    print("OK  %-58s %s -> %d bytes" % (target["path"], ",".join(applied), size))


MARK = "WcpHost.managed.txt"

JP_INSTALLER_BLOCK = """# 运行时补丁所有权登记：宿主（WcpHost）运行时也会写这份文件，安装阶段先写好，
# 免得"装完第一次进游戏"仍是新旧两个词表插件同时打补丁 —— 后写者胜会把上一本书
# 的词串进新书（"俄语切日语后还出俄语"）。只追加不覆盖：其它语言安装器登记过的
# 语言保留，宿主启动后还会按"资源是否就绪"再校正一次。
$managedMarker = Join-Path (Join-Path $bepRoot 'config') 'WcpHost.managed.txt'
$managedLangs = @()
if (Test-Path -LiteralPath $managedMarker) {
    Copy-Item -LiteralPath $managedMarker -Destination (Join-Path $backup 'WcpHost.managed.txt') -Force
    $managedLangs = @(Get-Content -LiteralPath $managedMarker | Where-Object { $_ -match '^[a-z]{2,3}$' })
}
if ($managedLangs -notcontains 'ja') { $managedLangs = @($managedLangs) + 'ja' }
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $managedMarker) | Out-Null
[IO.File]::WriteAllLines($managedMarker, [string[]]$managedLangs, (New-Object System.Text.UTF8Encoding($false)))
Write-Host ('已登记宿主接管语言：' + ($managedLangs -join ', ')) -ForegroundColor DarkGray
"""

HUB_HELPER_BLOCK = r"""# 运行时补丁所有权登记（与日语一键安装器同一段逻辑）：按"资源确实就绪"判定受管语言，
# 写进 <游戏>\BepInEx\config\WcpHost.managed.txt。旧词表插件读到自己的语言在列时
# 整场不打补丁，运行时补丁只剩宿主一个所有者 —— 这是"俄语切日语后还出俄语"的根因修复。
function Update-ManagedLanguagesMarker([string]$gameRoot, [string]$packsDir) {
    $ready = New-Object System.Collections.Generic.List[string]
    if (-not (Test-Path -LiteralPath $packsDir)) { return $ready }
    foreach ($packDir in @(Get-ChildItem -LiteralPath $packsDir -Directory)) {
        $manifestPath = Join-Path $packDir.FullName 'manifest.json'
        if (-not (Test-Path -LiteralPath $manifestPath)) { continue }
        try { $m = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json } catch { continue }
        if (-not $m -or -not $m.language -or -not $m.resources) { continue }
        $need = New-Object System.Collections.Generic.List[string]
        foreach ($k in @('meaning_db', 'sentence_table', 'repair')) {
            if ($m.resources.$k) { $need.Add([string]$m.resources.$k) }
        }
        foreach ($b in @($m.resources.books)) { if ($b) { $need.Add([string]$b) } }
        $ok = $true
        foreach ($rel in $need) {
            if (-not (Test-Path -LiteralPath (Join-Path $packDir.FullName $rel))) { $ok = $false; break }
        }
        if ($ok) { $ready.Add([string]$m.language) }
    }
    $marker = Join-Path (Join-Path $gameRoot 'BepInEx') 'config'
    $marker = Join-Path $marker 'WcpHost.managed.txt'
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $marker) | Out-Null
    [IO.File]::WriteAllLines($marker, [string[]]$ready, (New-Object System.Text.UTF8Encoding($false)))
    return $ready
}

"""

HUB_CALL_BLOCK = """$managedLangs = @(Update-ManagedLanguagesMarker -gameRoot $game -packsDir $packsRoot)
if ($managedLangs.Count -gt 0) {
    Write-Host ('宿主受管语言登记：' + ($managedLangs -join ', ')) -ForegroundColor DarkGray
} else {
    Write-Host '宿主受管语言登记：无（语言包资源未就绪时旧插件继续兜底）' -ForegroundColor DarkGray
}
"""


def patch_installers():
    jp = os.path.join(ROOT, "Japanese", "wcp_wordbooks", "installer", "Install-WCP-Japanese.ps1")
    text, nl, bom = read(jp)
    if MARK in text:
        print("SKIP %-58s 已迁移" % "Install-WCP-Japanese.ps1")
    else:
        anchor = "Copy-TreeNet $jaPackPayload $jaPackTarget '日语语言资源包'"
        if count(text, anchor) != 1:
            raise AssertionError("日语安装器锚点计数异常: %d" % count(text, anchor))
        block = JP_INSTALLER_BLOCK.replace("\n", nl)
        text = insert_after_line(text, anchor, block.rstrip(nl), nl)
        size = write(jp, text, nl, bom)
        print("OK  %-58s marker -> %d bytes" % ("Install-WCP-Japanese.ps1", size))

    hub = os.path.join(ROOT, "hub", "Install-WCP-Wordbooks.ps1")
    text, nl, bom = read(hub)
    if MARK in text:
        print("SKIP %-58s 已迁移" % "Install-WCP-Wordbooks.ps1")
        return
    helper = HUB_HELPER_BLOCK.replace("\n", nl)
    text = replace_once(text, "$totalAssets = 0",
                        helper + "$totalAssets = 0", 1)
    call = HUB_CALL_BLOCK.replace("\n", nl)
    tail = "if ($errors.Count -gt 0) {"
    if count(text, tail) != 1:
        raise AssertionError("hub 安装器收尾锚点计数异常: %d" % count(text, tail))
    text = text.replace(tail, call + tail, 1)
    size = write(hub, text, nl, bom)
    print("OK  %-58s marker -> %d bytes" % ("Install-WCP-Wordbooks.ps1", size))


def main():
    for target in TARGETS:
        migrate(target)
    patch_installers()
    print("全部完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
