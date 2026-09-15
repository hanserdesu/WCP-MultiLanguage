@echo off
setlocal EnableExtensions
chcp 65001 >nul
title WCP 日语词书安装器 - 兼容性提示
echo.
echo ========================================
echo   当前系统未找到可用的 PowerShell 运行环境
echo ========================================
echo.
echo 本安装器需要 Windows PowerShell 5.0 及以上版本，或 PowerShell 7。
echo 请安装或启用其中任意一个运行环境后，再双击根目录的
echo “01_双击运行我.cmd”。
echo.
echo 此窗口会保持打开，请点击右上角 X 关闭；按 Enter 不会关闭窗口。
cmd /k
