# -*- coding: utf-8 -*-
"""生成法语书插件私有内容清单并部署到 persistentDataPath。

游戏的 SQLite 词典由所有词书共享，不能拿它承载法语释义/例句。此脚本从
项目源数据生成 ``fr_book_content.tsv``；每项均以 base64 UTF-8 编码，避免
法语例句中的制表符、换行或中文标点破坏分隔格式。
"""
import base64
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'output'
PERSISTENT = Path.home() / 'AppData' / 'LocalLow' / 'WCP' / 'wcp'
TARGET = PERSISTENT / 'fr_book_content.tsv'


def enc(value: str) -> str:
    return base64.b64encode(value.encode('utf-8')).decode('ascii')


def meaning(item: dict) -> str:
    ipa = f"[{item['ipa']}] " if item.get('ipa') else ''
    return f"{ipa}{item['zh']}〈{item['pos']}〉"


def main() -> None:
    books = json.loads((OUT / 'french_books.json').read_text(encoding='utf-8'))
    sentences = json.loads((ROOT / 'data' / 'translations' /
                            'sentences_master.json').read_text(encoding='utf-8'))
    lines, seen = [], set()
    for level in ('a1', 'a2', 'b1', 'b2'):
        for item in books['levels'][level]:
            word = item['word'].strip()
            pairs = sentences.get(word, [])
            if not word or word in seen or len(pairs) != 3:
                raise ValueError(f'内容不完整或重复: {word!r}, 例句={len(pairs)}')
            seen.add(word)
            fields = [word, meaning(item)]
            for fr, zh in pairs:
                fields.extend((fr, zh))
            if any(not isinstance(v, str) or not v for v in fields):
                raise ValueError(f'空内容: {word!r}')
            lines.append('\t'.join(enc(v) for v in fields))

    target = TARGET
    if '--output' in sys.argv:
        target = Path(sys.argv[sys.argv.index('--output') + 1])
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + '.tmp')
    temporary.write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')
    temporary.replace(target)
    print(f'已写入 {target}: {len(lines)} 词，每词 3 例句')


if __name__ == '__main__':
    main()
