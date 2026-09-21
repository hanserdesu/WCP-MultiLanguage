# 许可范围与来源署名

Required Notice: Copyright (c) 2026 hanserdesu（猫条）

本仓库包含本项目编写的代码与内容，以及少量从第三方词典数据集派生的逐项数值。两类材料适用不同条款，范围以本文件为准。

## 一、代码：PolyForm Noncommercial License 1.0.0

适用：`mod_host/`、`mod_book_name/`、`mod_custom_slots/`、`languages/*/mod_*/`、`tools/`、`languages/*/tools/`、`tests/`，以及根目录的 `Install-WCP-Wordbooks.ps1`、`run-installer.ps1`、`WordbookHub.psm1` 与 `*.cmd`。完整文本见 [LICENSE](LICENSE)。

你可以为非商业目的使用、修改并再分发这些代码；商业用途需要另行取得授权。

## 二、内容：CC BY-NC 4.0

适用本项目自己编写、生成或整理的材料：

- 选词、分级与编排：`languages/*/data/`、`packs/*/books/`、各语言 `output/import/*.xlsx`
- 中文释义、例句与翻译：`languages/*/data/translations/`、`packs/*/db/sentences.json`、`packs/*/db/meaning.sqlite` 中的释义字段、`packs/*/db/repair.tsv`
- 语音：`packs/*/audio/`、`languages/*/output/*_audio*/`、各语言的 `*_word_audio` 与 `*_sentence_audio` 目录
- 本项目自行生成的读音：德语正字法转 IPA 规则、粤语粤拼、阿拉伯语拉丁转写

释义与例句由大模型生成后逐条精校，语音用 edge-tts 调用微软神经网络音色批量合成。你可以复制、改编、再分发，条件有三条：署名、不得用于商业目的、不得对他人施加额外限制。

法律文本（简体中文）：https://creativecommons.org/licenses/by-nc/4.0/legalcode.zh-Hans

### 上游数值与署名

少数列是从第三方词典数据集提取或机械转换得到的逐项数值。它们不属于上一节的授权范围，继续按上游条款提供：署名必须保留，衍生数据以相同方式共享，能否商用由上游决定。整包因为混合了上一节的内容，整体仍然不可商用。

| 语言 | 逐项数值 | 上游数据集 | 上游许可 | 仓库内脚本 |
| --- | --- | --- | --- | --- |
| ja | 假名读音、汉字音训读 | JMdict 与 kanjidic2（EDRDG，读音经 Jisho 接口取回后校对） | CC BY-SA 4.0 | `languages/ja/wcp_wordbooks/tools/fetch_readings.py`、`build_kanji_book.py`、`furigana.py` |
| fr | 音标（Lexique phon 记号转 IPA） | Lexique 3.83（lexique.org） | CC BY-SA 4.0 | `languages/fr/tools/prepare_lemmas.py` |
| ru | 重音标注 | kaikki.org（Wiktionary wiktextract） | CC BY-SA 4.0，与 GFDL 双许可 | `languages/ru/tools/enrich_stress.py` |
| es | 音标 | kaikki.org | 同 ru | `languages/es/tools/build_dataset_es.py` |
| pt | 音标 | kaikki.org | 同 ru | `languages/pt/tools/fill_ipa_kaikki_pt.py` |
| ko | 音标 | kaikki.org | 同 ru | `languages/ko/tools/build_ko_v2.py` |
| de | 无，正字法转 IPA 由本项目规则生成 | 不适用 | 不适用 | `languages/de/tools/g2p_de.py` |
| ar | 无，拉丁转写为自建 | 不适用 | 不适用 | `languages/ar/tools/build_tem_arabic_dataset.py` |
| yue | 无，粤拼为自建 | 不适用 | 不适用 | `languages/yue/data/cantonese_*.json` |

法律文本（简体中文）：https://creativecommons.org/licenses/by-sa/4.0/legalcode.zh-Hans

上游位置：Lexique 见 lexique.org；Wiktionary 数据提取见 kaikki.org；JMdict 与 kanjidic2 见 EDRDG（www.edrdg.org）。这些数据集按现行版本以 CC BY-SA 4.0 分发，早期版本曾以 3.0 发布，两种版本都只要求署名与相同方式共享。

## 构建期使用、未随包分发

下列数据只参与构建期的筛选、排序与对齐，数值与文本都没有进入发布态的 xlsx、sqlite 与语音包：

- ECDICT（github.com/skywind3000/ECDICT，MIT License）：德语候选词过滤，阿拉伯语把英文义项对齐成中文释义。阿拉伯语最终释义是项目重写内容，2026-09-21 逐条比对 8118 条释义，与 ECDICT 条目文本无一相同。
- FreeDict ara_eng（Arabic-English FreeDict Dictionary 0.6.3，作者 Arabeyes.org，GPL-2.0-or-later）：阿拉伯语高频词条挖掘与英文义项对齐，释义文本未随包分发。
- OpenSubtitles 词频表（github.com/hermitdave/FrequencyWords，CC BY-SA 4.0）：各语言按频率排序，只影响取词顺序。
- 各语考级大纲词表（TOPIK、CEFR、TEM-4 与 TEM-8、JLPT）：只用于确定教学范围。

## 待核实

- 语音由 edge-tts 调用微软神经网络音色合成，不是游戏内资源；涉及微软服务条款的部分不在本仓库的授权范围内。
- 韩语词表的分级参考了 TOPIK 与 NIKL 等级词汇的合并表，该表在仓库内没有附带来源说明，NIKL 部分的确切授权版本需要回韩国国立国语院原始发布页确认。

## 与游戏的关系

本仓库不包含《万词破－单词女友》（WCP-WordGirlfriend, appid 1981560）的任何游戏本体资源。词书与音频通过 BepInEx 在运行时注入，游戏文件未被修改或再分发。

## 商业授权

代码与内容两层都支持单独协商的商业授权。上游数值那部分由上游条款决定，本项目不代为授权。
