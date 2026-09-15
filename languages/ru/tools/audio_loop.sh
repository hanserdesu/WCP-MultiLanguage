#!/bin/bash
# 音频后台管线: 先单词音频 (books.json 已就绪), 然后循环例句音频
# (每轮: 重新合并已达标批次 -> 生成新增例句音频; 批次由例句代理逐步产出)。
cd /d/Russian || exit 1
export PYTHONIOENCODING=utf-8

echo "=== word audio start $(date +%T) ==="
python tools/gen_word_audio.py --retry-failed
echo "=== word audio done $(date +%T) ==="

for i in $(seq 1 60); do
  python tools/apply_sentences.py
  python tools/gen_sentence_audio_ru.py
  # 全部批次达标 (剩余 0) 且无缺失音频时退出循环
  REMAIN=$(python tools/gen_pipeline_ru.py list | wc -l)
  if [ "$REMAIN" -eq 0 ]; then
    python tools/apply_sentences.py
    python tools/gen_sentence_audio_ru.py
    if [ ! -s "$USERPROFILE/AppData/LocalLow/WCP/wcp/sentence_audio/failed_ru.txt" ]; then
      echo "=== all done $(date +%T) ==="
      break
    fi
    python - <<'EOF'
from pathlib import Path
f = Path.home() / 'AppData/LocalLow/WCP/wcp/sentence_audio/failed_ru.txt'
if f.exists():
    f.unlink()
EOF
  fi
  sleep 150
done
echo "=== audio loop exit $(date +%T) ==="
