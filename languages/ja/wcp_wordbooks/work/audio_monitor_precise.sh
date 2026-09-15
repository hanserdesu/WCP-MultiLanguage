#!/bin/bash
# 例句语音收尾监控 (精确指标: master 唯一例句缺失数, 每段最长 ~9 分钟)
export PATH="/c/Users/hanserdesu/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH"
cd /d/Japanese/wcp_wordbooks
for i in $(seq 1 18); do
  MISS=$(python -c "
import json, hashlib
from pathlib import Path
m=json.load(open('data/translations/sentences_master.json',encoding='utf-8'))
seen=set()
for v in m.values():
    for ja,zh in v: seen.add(ja)
S=Path.home()/'AppData/LocalLow/WCP/wcp/sentence_audio'
n=sum(1 for ja in seen if not ((S/(hashlib.md5(ja.encode('utf-8')).hexdigest()+'.mp3')).exists() and (S/(hashlib.md5(ja.encode('utf-8')).hexdigest()+'.mp3')).stat().st_size>1000))
print(n)
" 2>/dev/null)
  echo "poll$i missing=$MISS"
  if [ "$MISS" = "0" ]; then echo "DONE_PRECISE"; exit 0; fi
  sleep 28
done
echo "SEGMENT_END missing=$MISS"
