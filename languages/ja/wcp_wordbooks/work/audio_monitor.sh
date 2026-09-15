#!/bin/bash
# 例句语音生成监控 (每段最长 ~9 分钟, 退出后由主会话接力重启)
export PATH="/c/Users/hanserdesu/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH"
OUT="$USERPROFILE/AppData/LocalLow/WCP/wcp/sentence_audio"
EXPECT=56941
STATIC=0
LAST=0
for i in $(seq 1 18); do
  N=$(ls "$OUT" 2>/dev/null | grep -c '\.mp3$')
  PY=$(tasklist //FI "IMAGENAME eq python.exe" 2>/dev/null | grep -c python.exe)
  echo "poll$i files=$N python_procs=$PY"
  if [ "$N" -ge "$EXPECT" ]; then echo "DONE_ALL files=$N"; exit 0; fi
  if [ "$N" -eq "$LAST" ]; then STATIC=$((STATIC+1)); else STATIC=0; fi
  if [ "$STATIC" -ge 3 ]; then
    echo "STALLED files=$N"
    if [ "$PY" -eq 0 ]; then
      cd /d/Japanese/wcp_wordbooks
      nohup python tools/gen_sentence_audio.py >> work/audio_gen.log 2>&1 &
      echo "RESTARTED gen pid=$!"
    fi
    STATIC=0
  fi
  LAST=$N
  sleep 30
done
echo "SEGMENT_END files=$N"
