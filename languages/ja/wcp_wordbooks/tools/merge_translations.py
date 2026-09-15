# -*- coding: utf-8 -*-
"""把翻译(data/translations/*.json)合并回词书数据, 重建 output/jlpt_books.json,
并(可选)重写 MyBook.es3 与导入文件。

优先级: LLM人工批注(zh_llm_*.json, 按时间倒序) > gtx_zh.json > Kaishi > 英文回退
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'output'
TDIR = ROOT / 'data' / 'translations'

sys.path.insert(0, str(ROOT / 'tools'))
from build_books import fmt_meaning_zh  # noqa: E402
from fixup_words import fix_word  # noqa: E402


def load_translations():
    """返回按应用顺序排列的层: 低优先级在前, 高优先级在后(后者覆盖前者)。
    优先级: gtx < llm(按文件名时间升序, 新的覆盖旧的)
    旧层的键会先经过 fix_word 迁移(词字段清洗导致改名)。"""
    layers = []
    if TDIR.exists():
        gtx = TDIR / 'gtx_zh.json'
        if gtx.exists():
            raw = json.loads(gtx.read_text(encoding='utf-8'))
            zh = {}
            for k, v in raw.items():
                if v.get('zh'):
                    zh[fix_word(k)] = v['zh']
            layers.append(('gtx', zh))
        llm = sorted(TDIR.glob('zh_llm_*.json'))
        for p in llm:
            raw = json.loads(p.read_text(encoding='utf-8'))
            layer = {}
            for k, v in raw.items():
                k2 = fix_word(k)
                if isinstance(v, dict):
                    v = dict(v)
                    v['zh'] = v.get('zh', '')
                    layer[k2] = v
                elif v:
                    layer[k2] = v
            layers.append(('llm:' + p.name, layer))
    return layers


def apply_readings(data):
    rf = ROOT / 'data' / 'readings_jisho.json'
    if not rf.exists():
        return 0
    rmap = json.loads(rf.read_text(encoding='utf-8'))
    n = 0
    for lv, rows in data['levels'].items():
        for r in rows:
            if not r['reading'] and rmap.get(r['word']):
                r['reading'] = rmap[r['word']]
                n += 1
    return n


def main():
    write_game = '--write-game' in sys.argv
    data = json.loads((OUT / 'jlpt_books.json').read_text(encoding='utf-8'))
    layers = load_translations()
    readings_added = apply_readings(data)

    zh_map = {}
    pos_map = {}
    reading_map = {}
    llm_words = set()
    for name, layer in layers:
        for k, v in layer.items():
            if isinstance(v, dict):
                pos = v.get('pos', '')
                reading = v.get('reading', '')
                v = v.get('zh', '')
                if pos:
                    pos_map[k] = pos
                if reading:
                    reading_map[k] = reading
            if v:
                zh_map[k] = v
                if name.startswith('llm'):
                    llm_words.add(k)

    updated = 0
    pos_updated = 0
    reading_updated = 0
    for lv, rows in data['levels'].items():
        for r in rows:
            w = r['word']
            new_zh = zh_map.get(w, '')
            if new_zh and new_zh != r['meaning_zh']:
                r['meaning_zh'] = new_zh
                r['zh_source'] = 'llm' if w in llm_words else 'gtx'
                updated += 1
            new_pos = pos_map.get(w, '')
            if new_pos and new_pos != r.get('pos_zh', ''):
                r['pos_zh'] = new_pos
                pos_updated += 1
            new_reading = reading_map.get(w, '')
            if new_reading and new_reading != r.get('reading', ''):
                r['reading'] = new_reading
                reading_updated += 1
            r['meaning'] = fmt_meaning_zh(w, r['reading'],
                                          r['meaning_zh'],
                                          r.get('pos_zh', ''))
            if not r['meaning'] and r['meaning_en']:
                r['meaning'] = r['meaning_en']

    stats = {}
    for lv, rows in data['levels'].items():
        stats[lv] = {'count': len(rows),
                     'zh': sum(1 for r in rows if r['meaning_zh']),
                     'en_only': sum(1 for r in rows if not r['meaning_zh'])}
    data['meta']['stats'] = stats
    data['meta']['translation_layers'] = [n for n, _ in layers]

    (OUT / 'jlpt_books.json').write_text(
        json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(stats, ensure_ascii=False))
    print(f'更新释义 {updated} 条, 更新词性 {pos_updated} 条, 修正读音 {reading_updated} 条, Jisho补读音 {readings_added} 条')

    if write_game:
        import subprocess
        for script in ('write_mybook.py', 'make_import_files.py'):
            subprocess.run([sys.executable, str(ROOT / 'tools' / script)],
                           check=True)


if __name__ == '__main__':
    main()
