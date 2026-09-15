@echo off
rem 本文件是 UTF-8 编码, 先切到 65001 再调用中文文件名, 避免代码页把路径读坏。
chcp 65001 >nul
call "%~dp001_双击运行我.cmd" %*
