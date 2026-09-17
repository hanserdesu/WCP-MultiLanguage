# -*- coding: utf-8 -*-
"""导出韩语离线自愈数据库 Payload (ko_db_payload)。

包含:
  - ko_pron.tsv (word, ukPhonic, usPhonic, meaning)
  - ko_sentences.tsv (word, sentences JSON)
  - ko_only_pron.tsv (wcpOnlyWord 结构)
  - manifest.json (SHA-256 校验清单)
"""
import hashlib
import json
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
PAYLOAD_DIR = ROOT / 'output' / 'ko_db_payload'
BOOKS_FILE = ROOT / 'output' / 'korean_books.json'
MASTER_FILE = ROOT / 'data' / 'translations' / 'sentences_master.json'


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def main():
    PAYLOAD_DIR.mkdir(parents=True, exist_ok=True)
    books = json.loads(BOOKS_FILE.read_text(encoding='utf-8'))
    master = json.loads(MASTER_FILE.read_text(encoding='utf-8'))

    ko_pron_lines = []
    ko_sent_lines = []

    for lv in books['levels'].values():
        for item in lv:
            w = item['word']
            ipa = item.get('ipa', '')
            meaning = item.get('meaning', '')
            ko_pron_lines.append(f"{w}\t{ipa}\t{ipa}\t{meaning}\n")

            sents = master.get(w, [])
            # 格式化例句: 每句用 / 分割或 JSON 存储
            sent_str = json.dumps(sents, ensure_ascii=False)
            ko_sent_lines.append(f"{w}\t{sent_str}\n")

    pron_file = PAYLOAD_DIR / 'ko_pron.tsv'
    pron_file.write_text(''.join(ko_pron_lines), encoding='utf-8', newline='\n')

    only_pron_file = PAYLOAD_DIR / 'ko_only_pron.tsv'
    only_pron_file.write_text(''.join(ko_pron_lines), encoding='utf-8', newline='\n')

    sent_file = PAYLOAD_DIR / 'ko_sentences.tsv'
    sent_file.write_text(''.join(ko_sent_lines), encoding='utf-8', newline='\n')

    manifest = {
        'ko_pron.tsv': sha256(pron_file),
        'ko_only_pron.tsv': sha256(only_pron_file),
        'ko_sentences.tsv': sha256(sent_file),
        'word_count': len(ko_pron_lines),
        'sentence_count': sum(len(master.get(w, [])) for w in master)
    }

    (PAYLOAD_DIR / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8', newline='\n')
    print(f'已生成 ko_db_payload (共 {len(ko_pron_lines)} 词, {manifest["sentence_count"]} 例句)')


if __name__ == '__main__':
    main()
