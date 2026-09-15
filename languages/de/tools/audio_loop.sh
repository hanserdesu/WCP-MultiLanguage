#!/usr/bin/env bash
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "=== 启动德语单词音频生成 ==="
python tools/gen_word_audio.py >> logs/gen_word_audio.log 2>&1

echo "=== 启动德语例句音频生成 ==="
python tools/gen_sentence_audio_de.py >> logs/gen_sentence_audio.log 2>&1

echo "=== 全部音频生成已收工 ==="
