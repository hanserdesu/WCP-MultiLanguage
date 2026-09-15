# -*- coding: utf-8 -*-
"""合并分主题词书:
  1) 增补词库 data/themed/extra_<theme>.json (人工精翻, 优先级最高)
     -> 新增主题 kotowaza(谚语) / keigo(敬语), 其余并入现有主题
  2) 机翻层 data/translations/gtx_zh_themed.json (基线)
  3) LLM 精翻层 data/translations/zh_llm_themed_*.json (覆盖机翻)
产出: output/themed_books.json (含 meaning_zh/pos_zh/zh_source/example_ja/meaning)
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'output'
DATA = ROOT / 'data'
TDIR = DATA / 'translations'
THDIR = DATA / 'themed'

sys.path.insert(0, str(ROOT / 'tools'))
from build_books import fmt_meaning_zh  # noqa: E402

THEME_LABEL = {
    'it': 'IT·计算机', 'medical': '医学', 'business': '商务·经济',
    'law': '法律', 'idiom': '惯用句', 'onoma': '拟声拟态',
    'yoji': '四字熟语', 'kotowaza': '谚语·格言', 'keigo': '敬语',
    'talk': '日常会话',
}


def load_extras(books):
    """extras 并入 themes; 返回 {theme: [extra_entry,...]}"""
    added = {}
    for p in sorted(THDIR.glob('extra_*.json')):
        theme = p.stem[len('extra_'):]
        raw = json.loads(p.read_text(encoding='utf-8'))
        entries = raw.get('entries', [])
        if theme not in books['themes']:
            books['themes'][theme] = []
            books['meta']['themes'][theme] = {'count': 0, 'common': 0}
        existing = {r['word'] for r in books['themes'][theme]}
        new = []
        for e in entries:
            if e['word'] in existing:
                # extras 覆盖同名条目 (人工释义优先)
                books['themes'][theme] = [r for r in books['themes'][theme]
                                          if r['word'] != e['word']]
            new.append({
                'word': e['word'], 'reading': e.get('reading', ''),
                'meaning_en': '', 'pos_en': '',
                'pos_zh': e.get('pos', ''), 'meaning_zh': e.get('zh', ''),
                'zh_source': 'llm', 'example_ja': e.get('ex_ja', ''),
                'common': False, 'extra': True,
            })
        books['themes'][theme] = new + books['themes'][theme]
        added[theme] = len(new)
    return added


def load_translation_layers():
    layers = []
    gtxf = TDIR / 'gtx_zh_themed.json'
    if gtxf.exists():
        raw = json.loads(gtxf.read_text(encoding='utf-8'))
        layers.append(('gtx', {k: {'zh': v.get('zh', '')}
                               for k, v in raw.items() if v.get('zh')}))
    for p in sorted(TDIR.glob('zh_llm_themed_*.json')):
        raw = json.loads(p.read_text(encoding='utf-8'))
        layers.append(('llm:' + p.name, raw))
    return layers


def main():
    books = json.loads((OUT / 'themed_books.json').read_text(encoding='utf-8'))
    exclf = THDIR / 'exclude.json'
    excl = set(json.loads(exclf.read_text(encoding='utf-8'))) if exclf.exists() else set()
    for t in list(books['themes']):
        books['themes'][t] = [r for r in books['themes'][t] if r['word'] not in excl]

    # 规范化 extraction 条目字段
    for theme, rows in books['themes'].items():
        for r in rows:
            r.setdefault('pos_en', r.get('pos', ''))
            r.setdefault('pos_zh', '')
            r.setdefault('meaning_zh', '')
            r.setdefault('zh_source', '')
            r.setdefault('example_ja', '')

    extras = load_extras(books)
    layers = load_translation_layers()

    zh_map, pos_map, ex_map, rd_map = {}, {}, {}, {}
    llm_words = set()
    for name, layer in layers:
        for k, v in layer.items():
            if not isinstance(v, dict):
                if v:
                    zh_map[k] = {'zh': str(v)}
                continue
            rec = {'zh': v.get('zh', '')}
            if v.get('pos'):
                rec['pos'] = v['pos']
            if v.get('ex_ja'):
                rec['ex'] = v['ex_ja']
            if v.get('reading'):
                rec['reading'] = v['reading']
            if rec['zh']:
                zh_map[k] = rec
            if name.startswith('llm') and rec['zh']:
                llm_words.add(k)
                if rec.get('pos'):
                    pos_map[k] = rec['pos']
                if rec.get('ex'):
                    ex_map[k] = rec['ex']
                if rec.get('reading'):
                    rd_map[k] = rec['reading']

    stats_apply = {'zh': 0, 'pos': 0, 'ex': 0, 'reading': 0}
    for theme, rows in books['themes'].items():
        for r in rows:
            w = r['word']
            rec = zh_map.get(w)
            if rec:
                if rec['zh'] != r['meaning_zh']:
                    r['meaning_zh'] = rec['zh']
                    stats_apply['zh'] += 1
                r['zh_source'] = 'llm' if w in llm_words else (
                    'extra' if r.get('extra') else 'gtx')
            if r.get('extra'):
                r['zh_source'] = 'llm'
            if w in pos_map and pos_map[w] != r.get('pos_zh', ''):
                r['pos_zh'] = pos_map[w]
                stats_apply['pos'] += 1
            elif not r.get('pos_zh') and r.get('pos'):
                pass  # JMDict 英文词性不直接展示
            if w in ex_map and ex_map[w] != r.get('example_ja', ''):
                r['example_ja'] = ex_map[w]
                stats_apply['ex'] += 1
            if w in rd_map and rd_map[w] != r.get('reading', ''):
                r['reading'] = rd_map[w]
                stats_apply['reading'] += 1
            r['meaning'] = fmt_meaning_zh(w, r['reading'],
                                          r['meaning_zh'], r.get('pos_zh', ''))
            if not r['meaning'] and r['meaning_en']:
                r['meaning'] = r['meaning_en']

    # 统计
    stats = {}
    for theme, rows in books['themes'].items():
        stats[theme] = {
            'count': len(rows),
            'zh': sum(1 for r in rows if r['meaning_zh']),
            'llm': sum(1 for r in rows if r['zh_source'] == 'llm'),
            'gtx': sum(1 for r in rows if r['zh_source'] == 'gtx'),
            'en_only': sum(1 for r in rows if not r['meaning_zh']),
            'example': sum(1 for r in rows if r['example_ja']),
        }
        books['meta']['themes'][theme] = {**books['meta'].get('themes', {}).get(theme, {}),
                                          **stats[theme]}
        books['meta']['themes'][theme]['label'] = THEME_LABEL.get(theme, theme)
    books['meta']['stats'] = stats
    books['meta']['translation_layers'] = [n for n, _ in layers]
    books['meta']['theme_labels'] = THEME_LABEL

    (OUT / 'themed_books.json').write_text(
        json.dumps(books, ensure_ascii=False, indent=1), encoding='utf-8')
    print('extras 并入:', json.dumps(extras, ensure_ascii=False))
    print('应用统计:', json.dumps(stats_apply, ensure_ascii=False))
    for t, s in stats.items():
        print(f"{t}({THEME_LABEL.get(t, t)}): {s['count']}词 "
              f"zh={s['zh']} llm={s['llm']} gtx={s['gtx']} "
              f"en_only={s['en_only']} 例句={s['example']}")


if __name__ == '__main__':
    main()
