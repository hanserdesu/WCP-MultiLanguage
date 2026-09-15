"""为 es/pt/ko/ar 生成 packs/<lang>/pack.build.json（数据来自 build_pack_payload.py）。

指纹算法统一为宿主实现: Trim().Normalize(FormC) 排序后逐词 + '\\n' 再 SHA-256。
注意 es/pt 的 catalog.json 里存的是**旧算法**（'\n'.join 无尾换行）的指纹 —— 那是
2026-09-15 之前 verify_all_es/pt.py 的算法, 与宿主不兼容, 必须换成新算法,
否则装好词书后宿主身份门永远不命中。
"""
import hashlib
import json
import sys
import unicodedata

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import openpyxl

UP = 'D:/ATooManyLanguage'
JOBS = {
    "es": dict(project="Spanish", slot=0, es3="es",
               display="西班牙语词库(猫条版)", layout="single",
               books=["output/import/西班牙语考级词库(猫条版).xlsx"],
               pron="es_pron.tsv", sentences="es_sentences.tsv",
               payload="output/es_db_payload",
               probes=["decir", "tiempo", "hacer"]),
    "pt": dict(project="Portuguese", slot=0, es3="pt",
               display="葡萄牙语词库(猫条版)", layout="single",
               books=["output/import/葡萄牙语考级词库(猫条版).xlsx"],
               pron="pt_pron.tsv", sentences="pt_sentences.tsv",
               payload="output/pt_db_payload",
               probes=["fazer", "tempo", "muito"]),
    "ko": dict(project="korean", slot=0, es3="ko",
               display="韩语词库(猫条版)", layout="single",
               books=["output/import/韩语全量.xlsx"],
               pron="ko_pron.tsv", sentences="ko_sentences.tsv",
               payload="output/ko_db_payload",
               probes=["사랑", "시간", "하다"]),
    "ar": dict(project="Arabic", slot=0, es3="ar",
               display="阿拉伯语词库(猫条版)", layout="single",
               books=["output/import/阿拉伯语考级词库(猫条版).xlsx"],
               pron="ar_pron.tsv", sentences="ar_sentences.tsv",
               payload="output/ar_db_payload",
               probes=["أنا", "كتاب", "درس"]),
}


def norm(v):
    if v is None:
        return None
    t = unicodedata.normalize("NFC", str(v)).strip()
    return t or None


def fp(words):
    return hashlib.sha256(
        "".join(w + "\n" for w in sorted(words)).encode("utf-8")).hexdigest()


def book_words(path):
    ws = openpyxl.load_workbook(path, read_only=True).active
    out = set()
    for row in ws.iter_rows(min_col=1, max_col=1, values_only=True):
        w = norm(row[0])
        if w:
            out.add(w)
    return out


for lang, job in JOBS.items():
    words = set()
    for rel in job["books"]:
        words |= book_words(UP + "/" + job["project"] + "/" + rel)
    print(lang, "words=", len(words), "fp=", fp(words))

    spec = {
        "schema": 1,
        "language": lang,
        "profile_id": "catbar-%s-complete" % lang,
        "display_name": job["display"],
        "word_count": len(words),
        "fingerprint_sha256": fp(words),
        "observed_slot": job["slot"],
        "es3_prefix": job["es3"],
        "book_layout": job["layout"],
        "strategy": {"assembly": "$host", "type": "WcpHost.GenericLanguageStrategy"},
        "payload_dir": job["payload"],
        "pron": job["pron"],
        "sentences": job["sentences"],
        "books": job["books"],
        "repair_probes": job["probes"],
        "notes": [
            "word_count / fingerprint_sha256 是对 resources.books 全部分册的"
            "并集去重后排序算的 SHA-256（宿主算法: 逐词 + '\\n'）。",
            "observed_slot=0: 该语言尚未在任何存档槽位实测过, 身份判定只看指纹, "
            "导入任意空槽都能被认出。",
            "资源包复用宿主通用策略（$host），语言差异只在 manifest 与资源里。",
        ],
    }
    out = "%s/%s/packs/%s/pack.build.json" % (UP, job["project"], lang)
    import os
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(spec, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print("  写出", out)
