"""为 es/pt/ko/ar 生成 **pack 专用载荷**（pron TSV + sentences TSV）。

为什么要单独一个目录
────────────────────
各语言工程的 `output/<lang>_db_payload/` 是**旧插件安装器**在用的形状：
  ko  ko_sentences.tsv = word \t JSON [[原文, 中文], ...]
  ar  ar_sentences.tsv = word \t JSON [{"es":原文, "zh":中文, "word":词}, ...]
而统一宿主 pack 要求的是 fr/de 那种**展平两列**：
  word \t 例句：<原文>（<中文>）
直接改写原目录会破坏旧安装器（2026-09-15 已踩坑并回滚）。因此本工具只**读**
原目录、把 pack 形状写到 `output/pack_payload/`。

词列统一 NFC 归一
────────────────
阿拉伯语 shadda/fatha 的书写顺序会产生视觉相同的两种码点序；词书 A 列已是 NFC，
payload 若不归一会与词书集合差 74 个词，build_pack 会直接拒绝。

用法:
    python tools/build_pack_payload.py                # 只报告
    python tools/build_pack_payload.py --write        # 写出到 <项目>/output/pack_payload
    python tools/build_pack_payload.py --write --only ar
"""
import argparse
import hashlib
import json
import os
import sqlite3
import sys
import unicodedata

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UP = os.path.dirname(ROOT)


def word_nfc(value):
    if value is None:
        return None
    return unicodedata.normalize("NFC", str(value).strip())


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def esc(v):
    return str(v).replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n")


def write_tsv(path, rows):
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write("\t".join(esc(v) for v in row) + "\n")


def pron_from_db(path):
    conn = sqlite3.connect(path)
    rows = conn.execute(
        "select word, coalesce(ukPhonic,''), coalesce(usPhonic,''), coalesce(meaning,'') "
        "from pron").fetchall()
    conn.close()
    return [(word_nfc(w), uk, us, m) for (w, uk, us, m) in rows]


def pron_from_tsv(path):
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\r\n")
            if not line:
                continue
            f = line.split("\t")
            if len(f) != 4:
                raise SystemExit("%s: 期望 4 列, 实际 %d" % (path, len(f)))
            rows.append((word_nfc(f[0]), f[1], f[2], f[3]))
    return rows


def sentences_pairs(path):
    """读取 {word: [[原文, 中文], ...]} 形状的 sentences_master.json。"""
    data = json.load(open(path, encoding="utf-8"))
    out = []
    for word, pairs in data.items():
        for pair in pairs:
            if isinstance(pair, list) and len(pair) >= 2 and pair[0] and pair[1]:
                out.append((word_nfc(word), pair[0], pair[1]))
    return out


def sentences_json_tsv(path, mode, key1=None, key2=None):
    """读取 word \\t JSON 数组形状的句子表。

    mode='pairs' -> [[原文, 中文], ...]；mode='dict' -> [{key1:原文, key2:中文}, ...]
    """
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\r\n")
            if not line:
                continue
            word, blob = line.split("\t", 1)
            try:
                items = json.loads(blob)
            except Exception as exc:
                raise SystemExit("句子 JSON 解析失败 %s: %s" % (word, exc))
            for item in items:
                if mode == "pairs":
                    if isinstance(item, list) and len(item) >= 2 and item[0] and item[1]:
                        out.append((word_nfc(word), item[0], item[1]))
                else:
                    orig = item.get(key1) or ""
                    zh = item.get(key2) or ""
                    if orig and zh:
                        out.append((word_nfc(word), orig, zh))
    return out


JOBS = {
    "es": dict(project="Spanish",
               pron=("db", "output/import/wcp_spanish.db"),
               sentences=("master", "data/translations/sentences_master.json"),
               name="es"),
    "pt": dict(project="Portuguese",
               pron=("db", "output/import/wcp_portuguese.db"),
               sentences=("master", "data/translations/sentences_master.json"),
               name="pt"),
    "ko": dict(project="korean",
               pron=("tsv", "output/ko_db_payload/ko_pron.tsv"),
               sentences=("json_tsv", "output/ko_db_payload/ko_sentences.tsv", "pairs"),
               name="ko"),
    "ar": dict(project="Arabic",
               pron=("tsv", "output/ar_db_payload/ar_pron.tsv"),
               sentences=("json_tsv", "output/ar_db_payload/ar_sentences.tsv", "dict",
                          "es", "zh"),
               name="ar"),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    langs = [x.strip() for x in args.only.split(",") if x.strip()] or list(JOBS)

    for lang in langs:
        job = JOBS[lang]
        base = os.path.join(UP, job["project"])
        name = job["name"]

        kind, rel = job["pron"][0], job["pron"][1]
        pron = pron_from_db(os.path.join(base, rel)) if kind == "db" \
            else pron_from_tsv(os.path.join(base, rel))

        s = job["sentences"]
        if s[0] == "master":
            pairs = sentences_pairs(os.path.join(base, s[1]))
        elif s[0] == "json_tsv" and s[2] == "pairs":
            pairs = sentences_json_tsv(os.path.join(base, s[1]), "pairs")
        else:
            pairs = sentences_json_tsv(os.path.join(base, s[1]), "dict", s[3], s[4])

        pron_words = [r[0] for r in pron]
        dup = len(pron_words) - len(set(pron_words))
        print("%s: pron=%d 例句=%d 重复词=%d" % (lang, len(pron), len(pairs), dup))
        if dup:
            raise SystemExit("%s: pron 有重复词, 先查源数据" % lang)

        non_nfc = sum(1 for w in pron_words if not unicodedata.is_normalized("NFC", w))
        if non_nfc:
            print("   注意: 归一后仍有 %d 个非 NFC 词" % non_nfc)

        if not args.write:
            continue

        out = os.path.join(base, "output", "pack_payload")
        os.makedirs(out, exist_ok=True)
        pron_name = "%s_pron.tsv" % name
        sent_name = "%s_sentences.tsv" % name
        write_tsv(os.path.join(out, pron_name),
                  [(r[0], r[1], r[2], r[3]) for r in pron])
        write_tsv(os.path.join(out, sent_name),
                  [(w, "例句：%s（%s）" % (orig, zh)) for (w, orig, zh) in pairs])

        files = {n: sha256(os.path.join(out, n)) for n in (pron_name, sent_name)}
        manifest = {
            "word_count": len(pron),
            "sentence_count": len(pairs),
            "files": files,
            "note": "本目录是 pack 专用载荷（展平两列），由 MultiLanguage/tools/"
                    "build_pack_payload.py 生成；原 output/%s_db_payload 保持不变，"
                    "仍供旧插件安装器使用。" % name,
        }
        with open(os.path.join(out, "manifest.json"), "w", encoding="utf-8",
                  newline="\n") as fh:
            json.dump(manifest, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        print("   写出 -> %s" % out)


if __name__ == "__main__":
    main()
