# -*- coding: utf-8 -*-
"""合并 gen_out_NN_Y.json -> data/translations/sentences_master.json
{word: [[ru, zh], ...]} (每词3条)。只纳入通过 gen_pipeline_ru 校验的批次;
文件半写/损坏/未过检的批次自动跳过 (下一轮重跑会再纳入)。
可反复运行 (增量); 供例句音频管线周期性调用。"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / 'work'
DST = ROOT / 'data' / 'translations' / 'sentences_master.json'

sys.path.insert(0, str(ROOT / 'tools'))
import gen_pipeline_ru as gp  # noqa: E402


def main():
    master = {}
    skipped = []
    ps = gp.parts()
    for n, y, sl in ps:
        issues = gp.check_slice(n, y, sl)
        if issues:
            if issues != ['FILE_MISSING']:
                skipped.append(f'{n:02d}_{y}')
            continue
        d = json.loads(gp.out_file(n, y).read_text(encoding='utf-8'))
        for meta in sl:
            master[meta['word']] = [[it['ru'], it['zh']]
                                    for it in d[meta['word']][:3]]
    total_sent = sum(len(v) for v in master.values())
    unique = {ru for v in master.values() for ru, _ in v}
    DST.parent.mkdir(parents=True, exist_ok=True)
    DST.write_text(json.dumps(master, ensure_ascii=False, indent=0),
                   encoding='utf-8')
    words_total = sum(len(sl) for _, _, sl in ps)
    print(f'词 {len(master)}/{words_total}, 例句 {total_sent}, '
          f'唯一句 {len(unique)}, 未达标批次 {len(skipped)}'
          + (': ' + ' '.join(skipped[:15]) if skipped else ''))


if __name__ == '__main__':
    main()
