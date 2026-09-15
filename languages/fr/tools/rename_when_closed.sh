#!/bin/bash
# 等 wcp.exe 退出后自动写入法语书名昵称 (每60s轮询, 最长约12小时)
cd /d/French || exit 1
for i in $(seq 1 720); do
  if ! tasklist //FI "IMAGENAME eq wcp.exe" 2>/dev/null | grep -q wcp.exe; then
    sleep 10  # 等游戏完全退出、写完存档
    echo "$(date +%T) wcp.exe 已退出, 执行改名"
    python tools/rename_books_fr.py
    exit $?
  fi
  sleep 60
done
echo "超时: 游戏一直未退出, 未改名"
exit 2
