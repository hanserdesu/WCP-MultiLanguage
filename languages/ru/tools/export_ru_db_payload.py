# -*- coding: utf-8 -*-
r"""将俄语词书数据导出成持久化离线自愈补丁包 (ru_db_payload)。

背景: 官方更新或验证游戏完整性会覆盖 StreamingAssets 下的 .db 文件，
导致灌库的俄语释义与例句丢失。
存放到 LocalLow/ru_db_payload 与 output/ru_db_payload。RuWordListMod 启动时
后台检测探测词，若发现被官方更新冲掉，会自动静默重灌还原。

产出:
  ru_pron.tsv       word \t ukPhonic \t usPhonic \t meaning  (wcpFullEng.db)
  ru_sentences.tsv  word \t sentences                         (wcpFullEng.db)
  ru_only_pron.tsv  word \t ukPhonic \t usPhonic \t meaning  (wcpOnlyWord.db)
  manifest.json     SHA-256 校验账本
"""
import hashlib
import json
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
import wcp_paths

PACK_DIR_NAME = 'ru_db_payload'


def local_low_dir():
    env = os.environ.get('WCP_LOCALLOW', '').strip()
    if env:
        return Path(env)
    return Path(os.path.expanduser('~')) / 'AppData' / 'LocalLow' / 'WCP' / 'wcp'


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def main():
    books_p = ROOT / 'output' / 'russian_books.json'
    if not books_p.exists():
        print("错误: 缺少 output/russian_books.json")
        sys.exit(1)
        
    books = json.loads(books_p.read_text(encoding='utf-8'))
    master_p = ROOT / 'data' / 'translations' / 'sentences_master.json'
    master = json.loads(master_p.read_text(encoding='utf-8')) if master_p.exists() else {}
    
    # 收集词条
    rows_pron = []
    rows_sentences = []
    seen = set()
    
    for lvl in ['a1', 'a2', 'b1', 'b2']:
        for w in books['levels'][lvl]:
            word = w['word'].strip()
            if not word or word in seen:
                continue
            seen.add(word)
            
            stress = f"[{w['stress']}]" if w.get('stress') else ''
            meaning = f"{w['zh']}〈{w['pos']}〉"
            rows_pron.append(f"{word}\t{stress}\t\t{meaning}")
            
            s_list = master.get(word, [])
            for ru, zh in s_list:
                s_text = f"例句：{ru}（{zh}）" if zh else f"例句：{ru}"
                rows_sentences.append(f"{word}\t{s_text}")
                
    # 目标目录
    out_dirs = [
        ROOT / 'output' / PACK_DIR_NAME,
        local_low_dir() / PACK_DIR_NAME
    ]
    
    manifest = {}
    for d in out_dirs:
        d.mkdir(parents=True, exist_ok=True)
        p_pron = d / 'ru_pron.tsv'
        p_sent = d / 'ru_sentences.tsv'
        p_only = d / 'ru_only_pron.tsv'
        
        p_pron.write_text('\n'.join(rows_pron) + '\n', encoding='utf-8', newline='\n')
        p_sent.write_text('\n'.join(rows_sentences) + '\n', encoding='utf-8', newline='\n')
        p_only.write_text('\n'.join(rows_pron) + '\n', encoding='utf-8', newline='\n')
        
        manifest = {
            'files': {
                'ru_pron.tsv': sha256_file(p_pron),
                'ru_sentences.tsv': sha256_file(p_sent),
                'ru_only_pron.tsv': sha256_file(p_only),
            },
            'ru_pron.tsv': sha256_file(p_pron),
            'ru_sentences.tsv': sha256_file(p_sent),
            'ru_only_pron.tsv': sha256_file(p_only),
            'word_count': len(rows_pron),
            'sentence_count': len(rows_sentences),
        }
        (d / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"已导出补丁包到 {d}: {len(rows_pron)} 词, {len(rows_sentences)} 条例句")

    print("离线自愈补丁包构建完成！")


if __name__ == '__main__':
    main()
