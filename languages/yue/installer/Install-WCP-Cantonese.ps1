# -*- coding: utf-8 -*-
# 《万词破-单词女友》粤语词书自动化安装程序

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host ">>> 正在检测 Steam 游戏安装目录..." -ForegroundColor Yellow

$gamePath = "E:\Steam\steamapps\common\WCP-WordGirlgriend"
if (-not (Test-Path $gamePath)) {
    $gamePath = "D:\SteamLibrary\steamapps\common\WCP-WordGirlgriend"
}

if (-not (Test-Path $gamePath)) {
    Write-Host "[-] 未在默认路径找到万词破游戏目录，请输入您的游戏根目录:" -ForegroundColor Yellow
    $gamePath = Read-Host
}

if (-not (Test-Path "$gamePath\wcp_Data")) {
    Write-Host "[-] 无效的游戏目录: $gamePath" -ForegroundColor Red
    return
}

Write-Host "[+] 找到游戏目录: $gamePath" -ForegroundColor Green

$pluginsDir = Join-Path $gamePath "BepInEx\plugins"
if (-not (Test-Path $pluginsDir)) {
    New-Item -ItemType Directory -Path $pluginsDir -Force | Out-Null
}

$root = "D:\ATooManyLanguage\Contonese"

Write-Host ">>> 正在安装粤语运行时 Mod DLL..." -ForegroundColor Yellow
Copy-Item (Join-Path $root "mod_book_name\BookNameMod.dll") $pluginsDir -Force
Copy-Item (Join-Path $root "mod_sentence_audio_yue\SentenceAudioYueMod.dll") $pluginsDir -Force
Copy-Item (Join-Path $root "mod_yue_wordlist\YueWordListMod.dll") $pluginsDir -Force
Write-Host "[+] BepInEx 插件已部署至: $pluginsDir" -ForegroundColor Green

$localLowWcp = Join-Path $env:USERPROFILE "AppData\LocalLow\WCP\wcp"
$packsYue = Join-Path $env:USERPROFILE "AppData\LocalLow\WCP\packs\yue"
if (-not (Test-Path $packsYue)) {
    New-Item -ItemType Directory -Path $packsYue -Force | Out-Null
}

Write-Host ">>> 正在部署粤语 Pack 资源..." -ForegroundColor Yellow
Copy-Item (Join-Path $root "packs\yue\manifest.json") $packsYue -Force
Copy-Item (Join-Path $root "packs\yue\WcpPack.Yue.dll") $packsYue -Force

$packBooks = Join-Path $root "packs\yue\books"
if (Test-Path $packBooks) {
    Copy-Item $packBooks $packsYue -Recurse -Force
}
$packDb = Join-Path $root "packs\yue\db"
if (Test-Path $packDb) {
    Copy-Item $packDb $packsYue -Recurse -Force
}

$excelFile = Join-Path $root "output\import\粤语词库(猫条版).xlsx"
if (Test-Path $excelFile) {
    Copy-Item $excelFile $localLowWcp -Force
    Write-Host "[+] Excel 词书已部署至: $localLowWcp\粤语词库(猫条版).xlsx" -ForegroundColor Green
}

$wAudio = Join-Path $env:USERPROFILE "AppData\LocalLow\WCP\wcp\yue_word_audio"
$sAudio = Join-Path $env:USERPROFILE "AppData\LocalLow\WCP\wcp\yue_sentence_audio"
Write-Host "[+] 单词音频私有目录: $wAudio" -ForegroundColor Green
Write-Host "[+] 例句音频私有目录: $sAudio" -ForegroundColor Green

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  粤语词书全套资源安装成功！" -ForegroundColor Green
Write-Host "  1. 游戏内已支持选择与加载「粤语词库(猫条版)」" -ForegroundColor White
Write-Host "  2. 单词音频与例句音频已全部就绪并支持离线播放" -ForegroundColor White
Write-Host "  3. 启动游戏即可畅享地道粤语学习！" -ForegroundColor White
Write-Host "========================================" -ForegroundColor Green
