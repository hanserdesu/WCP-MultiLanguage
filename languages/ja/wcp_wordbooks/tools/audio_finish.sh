#!/bin/bash
# 等待 gen_audio 主进程日志停滞后: 重试失败 -> 补跑新增词 -> 完成
cd /d/Japanese/wcp_wordbooks
while true; do
  sleep 120
  LAST=$(stat -c %Y logs/gen_audio_themed.log 2>/dev/null || echo 0)
  NOW=$(date +%s)
  if [ $((NOW - LAST)) -gt 300 ]; then break; fi
done
py tools/gen_audio.py --retry-failed --limit 400 >> logs/gen_audio_retry.log 2>&1
py tools/gen_audio.py --limit 600 >> logs/gen_audio_retry.log 2>&1
echo "finish pass done $(date)" >> logs/gen_audio_retry.log
