#!/bin/bash
# Set B 夜间循环: 每5分钟一轮 setb_worker, 至 2026-09-07 09:00 为止。
cd "D:/ATooManyLanguage/Japanese/wcp_wordbooks"
DEADLINE=$(date -d "2026-09-07 09:00" +%s 2>/dev/null)
if [ -z "$DEADLINE" ]; then DEADLINE=$(date -v+1d +%s); fi
echo "night loop start $(date), deadline $(date -d @$DEADLINE 2>/dev/null || date -r $DEADLINE)"
while [ "$(date +%s)" -lt "$DEADLINE" ]; do
  py tools/setb_worker.py --audio-limit 500 >> logs/night_loop.log 2>&1
  sleep 300
done
echo "night loop end $(date)" >> logs/night_loop.log
