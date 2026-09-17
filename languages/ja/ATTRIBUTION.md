# 许可范围与来源署名

Required Notice: Copyright (c) 2026 hanserdesu（猫条）

本仓库是《万词破－单词女友》日语词书的历史仓库，内容已冻结在群友在用的稳定版；后续开发在多语言工程 hanserdesu/WCP-MultiLanguage，两处适用同一套许可。仓库同时包含我自己生产的代码与内容，以及从第三方词典数据集派生的逐项数值，范围以本文件为准。

## 一、代码：PolyForm Noncommercial License 1.0.0

适用：`mod_host/`、`mod_jp_wordlist/`、`mod_sentence_audio/`、`mod_book_name/`、`mod_custom_slots/`、`tools/`、`scripts/`、`wcp_wordbooks/tools/`、`wcp_wordbooks/installer/`，以及 `*.cmd` 与 `*.ps1`。完整文本见 [LICENSE](LICENSE)。

你可以为非商业目的使用、修改并再分发这些代码；商业用途需要另行取得授权。

## 二、我生产的内容：CC BY-NC-SA 4.0

适用：

- 选词、分级与编排：`wcp_wordbooks/data/`、`packs/ja/books/`、`wcp_wordbooks/output/import/*.xlsx`
- 中文释义与例句：`wcp_wordbooks/data/translations/`、`packs/ja/db/sentences.json`、`packs/ja/db/meaning.sqlite` 中的释义字段
- 语音：`packs/ja/audio/`、`wcp_wordbooks/output/` 下的语音载荷

例句与释义由大模型生成后逐条精校，语音用 edge-tts 调用微软神经网络音色批量合成。你可以复制、改编、再分发，条件只有三条：署名、不得用于商业目的、改编作品以相同方式共享。

法律文本（简体中文）：https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode.zh-Hans

## 三、词典数据：CC BY-SA 4.0

适用：从第三方词典数据集提取或机械转换得到的逐项数值，主要是汉字音训读与假名标注校验所用的数据，例如 `packs/ja/db/` 与常用汉字书中的读音列。这些值不是我生产的，按上游要求以 CC BY-SA 4.0 提供，署名与相同方式共享两项必须保留。

法律文本（简体中文）：https://creativecommons.org/licenses/by-sa/4.0/legalcode.zh-Hans

| 材料 | 逐项数值来源 | 上游许可 | 仓库内脚本 |
| --- | --- | --- | --- |
| 常用汉字书的音训读 | kanjidic2（EDRDG） | EDRDG 官方为 CC BY-SA 3.0，本仓库脚本内标注为 4.0 | `wcp_wordbooks/tools/build_kanji_book.py` |
| 假名注音校验 | kanjidic2（EDRDG） | 同上 | `wcp_wordbooks/tools/furigana.py` |
| JLPT N5 到 N1 词表 | 社区整理的 JLPT 词表 CSV（含 Genki 章节交叉标签，文件内未记录来源） | 只用于确定教学范围，词条集合本身独创性有限 | `tools/prep_worklist.py`、`wcp_wordbooks/tools/build_books.py` |

## 待核实

- 语音由 edge-tts 调用微软神经网络音色合成，不是游戏内资源；涉及微软服务条款的部分不在本仓库的授权范围内。

## 与游戏的关系

本仓库不包含《万词破－单词女友》（WCP-WordGirlfriend, appid 1981560）的任何游戏本体资源。词书与音频通过 BepInEx 在运行时注入，游戏文件未被修改或再分发。

## 商业授权

上述三层都支持单独协商的商业授权。
