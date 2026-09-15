# -*- coding: utf-8 -*-
"""Replace the four former 猫条 chapters with one portable custom book.

Only the four custom-book payloads and their displayed nicknames are changed:
slot 1 receives the complete, de-duplicated JLPT book and slots 2--4 become
empty slots.  Original game wordbooks and all unrelated save fields are left
as-is.  Run only while wcp.exe is closed; both files are backed up first.
"""
import hashlib
import json
import shutil
import subprocess
import sys
import time
import unicodedata
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'output'
GAME_DIR = Path.home() / 'AppData' / 'LocalLow' / 'WCP' / 'wcp'
MYBOOK = GAME_DIR / 'MyBook.es3'
SAVE = GAME_DIR / 'SaveFile.es3'

CANONICAL_BOOK = '自定义词书一'
DISPLAY_NAME = '日语词库(猫条版)'
EMPTY_SLOT_NAME = '空槽位'
EXPECTED_WORD_COUNT = 7922
EXPECTED_FINGERPRINT = '6d7a51c0c5d30dd63d8a6e3412bce1cf2419554fb8487cf5c8a205e43ac41663'
ARR_TYPE = 'System.String[],mscorlib'
DICT_TYPE = ('System.Collections.Generic.Dictionary`2[[System.String, mscorlib, '
             'Version=4.0.0.0, Culture=neutral, PublicKeyToken=b77a5c561934e089],'
             '[System.String, mscorlib, Version=4.0.0.0, Culture=neutral, '
             'PublicKeyToken=b77a5c561934e089]],mscorlib')


def game_running():
    result = subprocess.run(
        ['tasklist', '/FI', 'IMAGENAME eq wcp.exe'],
        capture_output=True, text=True, encoding='gbk', errors='replace', check=False,
    )
    return 'wcp.exe' in result.stdout.lower()


def load_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def save_json(path, doc):
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding='utf-8')


def wrapped(type_name, value):
    return {'__type': type_name, 'value': value}


def set_wrapped(doc, key, value, fallback_type):
    """Change only the payload, retaining the game's original type wrapper."""
    entry = doc.get(key)
    if isinstance(entry, dict) and '__type' in entry:
        entry['value'] = value
    else:
        doc[key] = wrapped(fallback_type, value)


def fingerprint(words):
    normalized = sorted(unicodedata.normalize('NFC', word.strip()) for word in words)
    payload = ''.join(word + '\n' for word in normalized).encode('utf-8')
    return hashlib.sha256(payload).hexdigest()


def build_combined_book():
    levels = load_json(OUT / 'jlpt_books.json')['levels']
    seen, words, meanings = set(), [], {}
    for level in ('n5', 'n4', 'n3', 'n2', 'n1'):
        for row in levels[level]:
            word = row['word'].strip()
            meaning = (row.get('meaning') or row.get('meaning_en') or '').strip()
            if not word or not meaning or word in seen:
                continue
            seen.add(word)
            words.append(word)
            meanings[word] = meaning
    assert len(words) == EXPECTED_WORD_COUNT, len(words)
    assert fingerprint(words) == EXPECTED_FINGERPRINT
    return words, meanings


def backup(path, folder_name, stamp):
    folder = path.parent / folder_name
    folder.mkdir(exist_ok=True)
    target = folder / f'{path.name}.pre_catbar_combined.{stamp}.bak'
    shutil.copy2(path, target)
    return target


def verify(words, meanings):
    mybook = load_json(MYBOOK)
    save = load_json(SAVE)
    first = mybook['SelfBookList1']['value']
    first_dict = mybook['wordDictionary1']['value']
    assert first == words
    assert first_dict == meanings
    assert fingerprint(first) == EXPECTED_FINGERPRINT
    for slot in (2, 3, 4):
        assert mybook[f'SelfBookList{slot}']['value'] == []
        assert mybook[f'wordDictionary{slot}']['value'] == {}
    assert save['ChosenBook_Para']['value'] == CANONICAL_BOOK
    assert save['ChosenBook_List']['value'] == words
    assert save['SelfBookName1']['value'] == DISPLAY_NAME
    for slot in (2, 3, 4):
        assert save[f'SelfBookName{slot}']['value'] == EMPTY_SLOT_NAME


def main():
    if game_running():
        print('wcp.exe 正在运行，未写入。请先完全退出游戏。', file=sys.stderr)
        return 1
    if not MYBOOK.exists() or not SAVE.exists():
        print(f'缺少游戏数据文件: {MYBOOK} / {SAVE}', file=sys.stderr)
        return 1

    words, meanings = build_combined_book()
    mybook = load_json(MYBOOK)
    save = load_json(SAVE)
    stamp = time.strftime('%Y%m%d_%H%M%S')
    mybook_backup = backup(MYBOOK, 'MyBook_backups', stamp)
    save_backup = backup(SAVE, 'SaveFile_backups', stamp)

    set_wrapped(mybook, 'SelfBookList1', words, ARR_TYPE)
    set_wrapped(mybook, 'wordDictionary1', meanings, DICT_TYPE)
    for slot in (2, 3, 4):
        set_wrapped(mybook, f'SelfBookList{slot}', [], ARR_TYPE)
        set_wrapped(mybook, f'wordDictionary{slot}', {}, DICT_TYPE)

    # Keep the active custom-book pointer coherent.  Do not modify progress,
    # queues, collection data, or any built-in wordbook fields.
    set_wrapped(save, 'ChosenBook_Para', CANONICAL_BOOK, 'string')
    set_wrapped(save, 'ChosenBook_List', words,
                'System.Collections.Generic.List`1[[System.String, mscorlib, '
                'Version=4.0.0.0, Culture=neutral, PublicKeyToken=b77a5c561934e089]],mscorlib')
    set_wrapped(save, 'SelfBookName1', DISPLAY_NAME, 'string')
    for slot in (2, 3, 4):
        set_wrapped(save, f'SelfBookName{slot}', EMPTY_SLOT_NAME, 'string')

    save_json(MYBOOK, mybook)
    save_json(SAVE, save)
    try:
        verify(words, meanings)
    except Exception:
        shutil.copy2(mybook_backup, MYBOOK)
        shutil.copy2(save_backup, SAVE)
        raise

    print(f'已合并到槽位一: {len(words)} 词, sha256={EXPECTED_FINGERPRINT}')
    print('槽位二至四已清空并标记为空槽位。')
    print(f'MyBook 备份: {mybook_backup}')
    print(f'SaveFile 备份: {save_backup}')
    print('回读校验: PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
