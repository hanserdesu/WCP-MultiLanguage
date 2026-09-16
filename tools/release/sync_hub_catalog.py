# -*- coding: utf-8 -*-
"""从 MultiLanguage/catalog.json 生成 hub/catalog.json 副本。

约定（P1-7）：hub catalog 是 ML catalog 的**生成副本**，不要手工维护；
行尾 CRLF、无 BOM，内容与 ML 语义等价（json.load 比较，别比原始字节）。

用法: python tools/release/sync_hub_catalog.py
"""
import json
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[3]
ML_CATALOG = Path(__file__).resolve().parents[2] / 'catalog.json'
HUB_CATALOG = WORKSPACE / 'hub' / 'catalog.json'


def main() -> int:
    if not ML_CATALOG.is_file():
        print('找不到源 catalog: %s' % ML_CATALOG)
        return 1
    data = json.loads(ML_CATALOG.read_text(encoding='utf-8'))
    text = json.dumps(data, ensure_ascii=False, indent=2)
    hub_bytes = (text.replace('\n', '\r\n') + '\r\n').encode('utf-8')
    HUB_CATALOG.write_bytes(hub_bytes)

    # 复证：语义等价 + 行尾/编码符合约定
    again = json.loads(HUB_CATALOG.read_text(encoding='utf-8'))
    if again != data:
        print('语义不等价！')
        return 1
    raw = HUB_CATALOG.read_bytes()
    if raw[:3] == b'\xef\xbb\xbf':
        print('hub catalog 不应带 BOM')
        return 1
    if b'\r\n' not in raw[:2000]:
        print('提示：hub catalog 行尾不是 CRLF')
        return 1
    mods = data.get('mods', {}).get('version')
    wb = len(data.get('wordbooks', []))
    print('hub catalog 已生成: %s（词书 %d，mods %s，%d 字节）' % (
        HUB_CATALOG, wb, mods, len(raw)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
