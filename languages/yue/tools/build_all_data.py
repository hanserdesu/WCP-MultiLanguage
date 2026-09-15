# -*- coding: utf-8 -*-
"""读取 data/*.json 数据并生成完整的粤语学习资源数据库、修复流与 JSON 交付件"""
import hashlib
import json
import os
import sqlite3
import sys
import unicodedata
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"
PAYLOAD_DIR = OUTPUT_DIR / "yue_db_payload"
PACK_DB_DIR = ROOT / "packs" / "yue" / "db"


def escape(value: str) -> str:
    return (value or "").replace("\\", "\\\\").replace("\t", "\\t").replace("\r", "").replace("\n", "\\n")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_of_words(words: list[str]) -> str:
    norm = [unicodedata.normalize('NFC', w.strip()) for w in words]
    norm.sort()
    payload = '\n'.join(norm) + '\n'
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PAYLOAD_DIR.mkdir(parents=True, exist_ok=True)
    PACK_DB_DIR.mkdir(parents=True, exist_ok=True)

    json_files = sorted(list(DATA_DIR.glob("*.json")))
    if not json_files:
        print("未找到任何数据文件！")
        sys.exit(1)

    all_words = {}
    levels_data = {}

    for jf in json_files:
        content = json.loads(jf.read_text(encoding='utf-8'))
        level = content.get("level", jf.stem)
        levels_data[level] = []
        words = content.get("words", [])
        for item in words:
            w = item["word"].strip()
            jp = item["jyutping"].strip()
            pos = item["pos"].strip()
            meaning = item["meaning"].strip()
            sentences = item.get("sentences", [])

            # 格式化统一展示释义：[粤拼] 中文释义〈词性〉
            formatted_meaning = f"[{jp}] {meaning}〈{pos}〉"

            word_entry = {
                "word": w,
                "jyutping": jp,
                "pos": pos,
                "meaning": meaning,
                "formatted_meaning": formatted_meaning,
                "sentences": sentences,
                "level": level
            }

            if w not in all_words:
                all_words[w] = word_entry
                levels_data[level].append(w)
            else:
                # 合并例句
                existing_s = {s["sentence"]: s for s in all_words[w]["sentences"]}
                for s in sentences:
                    if s["sentence"] not in existing_s:
                        all_words[w]["sentences"].append(s)

    sorted_words = sorted(all_words.keys())
    total_count = len(sorted_words)
    fingerprint = sha256_of_words(sorted_words)

    print(f"成功汇总粤语词条: {total_count} 词，去重计算指纹: {fingerprint}")

    # 1. 输出 output/cantonese_books.json
    books_data = {
        "title": "粤语词库(猫条版)",
        "language": "yue",
        "total_words": total_count,
        "fingerprint_sha256": fingerprint,
        "levels": {lvl: words for lvl, words in levels_data.items()},
        "vocabulary": [all_words[w] for w in sorted_words]
    }
    books_json_path = OUTPUT_DIR / "cantonese_books.json"
    books_json_path.write_text(json.dumps(books_data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"已生成: {books_json_path}")

    # 2. 输出 output/sentences_master.json 与 packs/yue/db/sentences.json
    sentences_master = {
        "schema": 1,
        "language": "yue",
        "total_words": total_count,
        "sentences": {
            w: all_words[w]["sentences"] for w in sorted_words
        }
    }
    master_json_path = OUTPUT_DIR / "sentences_master.json"
    master_json_path.write_text(json.dumps(sentences_master, ensure_ascii=False, indent=2), encoding='utf-8')
    pack_sent_path = PACK_DB_DIR / "sentences.json"
    pack_sent_path.write_text(json.dumps(sentences_master, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"已生成: {master_json_path} & {pack_sent_path}")

    # 3. 输出 packs/yue/db/meaning.sqlite
    sqlite_path = PACK_DB_DIR / "meaning.sqlite"
    if sqlite_path.exists():
        sqlite_path.unlink()
    conn = sqlite3.connect(sqlite_path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE pron (
            word TEXT PRIMARY KEY,
            ukPhonic TEXT,
            usPhonic TEXT,
            meaning TEXT
        )
    """)
    for w in sorted_words:
        entry = all_words[w]
        cur.execute(
            "INSERT INTO pron (word, ukPhonic, usPhonic, meaning) VALUES (?, ?, ?, ?)",
            (w, f"[{entry['jyutping']}]", "", entry["formatted_meaning"])
        )
    conn.commit()
    conn.close()
    print(f"已生成: {sqlite_path}")

    # 4. 生成 yue_pron.tsv, yue_sentences.tsv 与 repair.tsv
    pron_tsv_path = PAYLOAD_DIR / "yue_pron.tsv"
    sent_tsv_path = PAYLOAD_DIR / "yue_sentences.tsv"
    repair_tsv_path = PACK_DB_DIR / "repair.tsv"

    with pron_tsv_path.open("w", encoding="utf-8", newline="\n") as f_pron, \
         sent_tsv_path.open("w", encoding="utf-8", newline="\n") as f_sent, \
         repair_tsv_path.open("w", encoding="utf-8", newline="\n") as f_repair:

        f_repair.write("#\tschema=1\tkind\tword\tukPhonic\tusPhonic\tvalue\n")

        for w in sorted_words:
            entry = all_words[w]
            # yue_pron: word \t ukPhonic \t usPhonic \t meaning
            f_pron.write(f"{escape(w)}\t{escape('[' + entry['jyutping'] + ']')}\t\t{escape(entry['formatted_meaning'])}\n")
            f_repair.write(f"row\tpron\t{escape(w)}\t{escape('[' + entry['jyutping'] + ']')}\t\t{escape(entry['formatted_meaning'])}\t\n")

            # yue_sentences: word \t 例句格式
            for s in entry["sentences"]:
                sent_full = f"例句：{s['sentence']}（{s['translate']}）"
                f_sent.write(f"{escape(w)}\t{escape(sent_full)}\n")
                f_repair.write(f"row\tsentence\t{escape(w)}\t\t\t{escape(sent_full)}\t\n")

    print(f"已生成 TSV 修复载荷: {pron_tsv_path}, {sent_tsv_path}, {repair_tsv_path}")

    # 5. 输出 PAYLOAD manifest.json
    manifest_payload = {
        "version": 1,
        "language": "yue",
        "word_count": total_count,
        "fingerprint_sha256": fingerprint,
        "files": {
            "yue_pron.tsv": sha256_file(pron_tsv_path),
            "yue_sentences.tsv": sha256_file(sent_tsv_path),
            "repair.tsv": sha256_file(repair_tsv_path)
        }
    }
    payload_manifest_path = PAYLOAD_DIR / "manifest.json"
    payload_manifest_path.write_text(json.dumps(manifest_payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"已生成 Payload 清单: {payload_manifest_path}")


if __name__ == "__main__":
    main()
