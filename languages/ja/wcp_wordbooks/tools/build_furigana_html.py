# -*- coding: utf-8 -*-
"""生成 HTML 注音词表: <ruby> 标签把假名渲染在汉字正上方 (同拼音标注)。

数据: work/gen_words_NN.json (词/读音/释义/级别) + furigana_map.json
输出: output/furigana_注音词表.html
"""
import html
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / 'work'
OUT = ROOT / 'output' / 'furigana_注音词表.html'
FURIGANA = ROOT / 'data' / 'translations' / 'furigana_map.json'

SEG = re.compile(r'([^\[\]]+)\[([^\]]+)\]')
LEVELS = ['N5', 'N4', 'N3', 'N2', 'N1', 'IT', 'BIZ', '医', '法', '金融',
          'オノマトペ', '四字熟語', '慣用句', '敬語', '諺', '漢字']


def load_words():
    need = {}
    for n in range(40):
        p = WORK / f'gen_words_{n:02d}.json'
        if p.exists():
            need.update(json.loads(p.read_text(encoding='utf-8')).items())
    return need


def to_ruby(ann):
    """漢[かん]字[じ] -> <ruby>漢<rt>かん</rt></ruby>字"""
    out, pos = [], 0
    for m in SEG.finditer(ann):
        out.append(html.escape(ann[pos:m.start()]))
        out.append(f'<ruby>{html.escape(m.group(1))}'
                   f'<rt>{html.escape(m.group(2))}</rt></ruby>')
        pos = m.end()
    out.append(html.escape(ann[pos:]))
    return ''.join(out)


def main():
    need = load_words()
    furigana = json.loads(FURIGANA.read_text(encoding='utf-8'))
    by_lv = {}
    for w, v in need.items():
        by_lv.setdefault(v.get('level') or 'その他', []).append(
            (w, v, furigana.get(w)))
    lvs = [l for l in LEVELS if l in by_lv] + \
          sorted(l for l in by_lv if l not in LEVELS)
    parts = ['''<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8">
<title>日语词表 · 振假名注音版</title><style>
body{font-family:"Noto Sans JP","Microsoft YaHei",sans-serif;
 max-width:1100px;margin:24px auto;padding:0 12px;color:#222}
h2{border-bottom:2px solid #4a7;border-bottom:2px solid #4a90d9;
 padding-bottom:4px;margin-top:36px}
table{border-collapse:collapse;width:100%;font-size:15px}
td,th{border:1px solid #ccc;padding:4px 8px;vertical-align:top}
rt{color:#0a7;font-size:.62em}
.w{font-size:19px}ruby{ruby-align:center}
tr:nth-child(even){background:#f6f8fa}
.cnt{color:#888;font-weight:normal;font-size:14px}
</style></head><body>
<h1>日语词表 · 振假名注音版 <span class="cnt">(全 __TOTAL__ 词)</span></h1>''']
    total = len(need)
    parts[0] = parts[0].replace('__TOTAL__', str(total))
    for lv in lvs:
        rows = by_lv[lv]
        parts.append(f'<h2>{html.escape(str(lv))} '
                     f'<span class="cnt">({len(rows)} 词)</span></h2>')
        parts.append('<table><tr><th style="width:24%">单词(注音)</th>'
                     '<th style="width:14%">读音</th>'
                     '<th style="width:14%">词性·级别</th>'
                     '<th>释义</th></tr>')
        for w, v, ann in rows:
            word_cell = to_ruby(ann) if ann else html.escape(w)
            parts.append(
                f'<tr><td class="w">{word_cell}</td>'
                f'<td>{html.escape(v.get("reading") or w)}</td>'
                f'<td>{html.escape(str(v.get("level") or ""))}</td>'
                f'<td>{html.escape(v.get("meaning") or "")}</td></tr>')
        parts.append('</table>')
    parts.append('</body></html>')
    OUT.write_text('\n'.join(parts), encoding='utf-8')
    print('->', OUT, f'{OUT.stat().st_size/1e6:.1f} MB, {total} 词, '
          f'{len(lvs)} 个分级')


if __name__ == '__main__':
    main()
