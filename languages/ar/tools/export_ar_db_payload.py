# -*- coding: utf-8 -*-
"""导出阿拉伯语离线自愈数据库 Payload (ar_db_payload)。

对标 ko_db_payload / de_db_payload 的统一契约:
  - ar_pron.tsv (word, ukPhonic, usPhonic, meaning)
  - ar_sentences.tsv (word, sentences JSON)
  - ar_only_pron.tsv (wcpOnlyWord 结构)
  - manifest.json (SHA-256 校验清单)

数据源: output/arabic_books.json (books -> 词 -> meaning/example_ar)
"""
import hashlib
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
PAYLOAD_DIR = ROOT / 'output' / 'ar_db_payload'
BOOKS_FILE = ROOT / 'output' / 'arabic_books.json'


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main():
    PAYLOAD_DIR.mkdir(parents=True, exist_ok=True)
    data = json.loads(BOOKS_FILE.read_text(encoding='utf-8'))
    books = data['books']

    ar_pron_lines = []
    ar_sent_lines = []
    seen_words = set()

    for _book, entries in books.items():
        for it in entries:
            w = it['word']
            if w in seen_words:
                continue
            seen_words.add(w)
            meaning = it.get('meaning', '')
            # 标音词形含 Tashkeel; 探针字段用原文, 音标字段留空 (无拉丁 IPA)
            ar_pron_lines.append(f"{w}\t\t\t{meaning}\n")
            sents = []
            raw = it.get('example_ar', '')
            s = re.sub(r'<[^>]+>', '', raw or '').strip()
            if len(s) >= 2:
                sents.append({'es': s, 'zh': it.get('example_zh', ''), 'word': w})
            ar_sent_lines.append(f"{w}\t{json.dumps(sents, ensure_ascii=False)}\n")

    pron_file = PAYLOAD_DIR / 'ar_pron.tsv'
    pron_bytes = ''.join(ar_pron_lines).encode('utf-8')
    pron_file.write_bytes(pron_bytes)

    only_file = PAYLOAD_DIR / 'ar_only_pron.tsv'
    only_bytes = ''.join(ar_pron_lines).encode('utf-8')
    only_file.write_bytes(only_bytes)

    sent_file = PAYLOAD_DIR / 'ar_sentences.tsv'
    sent_bytes = ''.join(ar_sent_lines).encode('utf-8')
    sent_file.write_bytes(sent_bytes)

    manifest = {
        'ar_pron.tsv': sha256_bytes(pron_bytes),
        'ar_only_pron.tsv': sha256_bytes(only_bytes),
        'ar_sentences.tsv': sha256_bytes(sent_bytes),
        'word_count': len(ar_pron_lines),
        'sentence_count': sum(1 for line in ar_sent_lines if len(line.split('\t', 1)[1]) > 4),
    }
    (PAYLOAD_DIR / 'manifest.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'已生成 ar_db_payload (共 {len(ar_pron_lines)} 词, '
          f'{manifest["sentence_count"]} 句含例句)')


if __name__ == '__main__':
    main()
