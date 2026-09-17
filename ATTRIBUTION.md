# 许可范围与来源署名

Required Notice: Copyright (c) 2026 hanserdesu（猫条）

本仓库同时包含我自己生产的代码与内容，以及从第三方词典数据集派生的逐项数值。三类材料适用不同许可，范围以本文件为准。

## 一、代码：PolyForm Noncommercial License 1.0.0

适用：`mod_host/`、`mod_book_name/`、`mod_custom_slots/`、`languages/*/mod_*/`、`tools/`、`languages/*/tools/`、`tests/`，以及根目录的 `Install-WCP-Wordbooks.ps1`、`run-installer.ps1`、`WordbookHub.psm1` 与 `*.cmd`。完整文本见 [LICENSE](LICENSE)。

你可以为非商业目的使用、修改并再分发这些代码；商业用途需要另行取得授权。

## 二、我生产的内容：CC BY-NC-SA 4.0

适用：

- 选词、分级与编排：`languages/*/data/`、`packs/*/books/`、各语言 `output/import/*.xlsx`
- 中文释义、例句与翻译：`languages/*/data/translations/`、`packs/*/db/sentences.json`、`packs/*/db/meaning.sqlite` 中的释义字段
- 语音：`packs/*/audio/`、`languages/*/output/*_audio*/`、各语言 `*_word_audio` 与 `*_sentence_audio` 目录

例句与释义由大模型生成后逐条精校，语音用 edge-tts 调用微软神经网络音色批量合成。你可以复制、改编、再分发，条件只有三条：署名、不得用于商业目的、改编作品以相同方式共享。

法律文本（简体中文）：https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode.zh-Hans

## 三、词典数据：CC BY-SA 4.0

适用：从第三方词典数据集提取或机械转换得到的逐项数值，即音标、重音标注、汉字音训读等，例如各语言载荷与 `packs/*/db/` 中的音标列。这些值不是我生产的，按上游要求以 CC BY-SA 4.0 提供，署名与相同方式共享两项必须保留。

法律文本（简体中文）：https://creativecommons.org/licenses/by-sa/4.0/legalcode.zh-Hans

## 上游来源对照

| 语言 | 逐项数值来源 | 上游许可 | 仓库内脚本 |
| --- | --- | --- | --- |
| ja | 汉字音训读：kanjidic2（EDRDG） | EDRDG 官方为 CC BY-SA 3.0，本仓库脚本内标注为 4.0 | `languages/ja/wcp_wordbooks/tools/build_kanji_book.py` |
| fr | 音标：Lexique 3.83（lexique.org）的 phon 记号转为 IPA | CC BY-SA（脚本注释记为 CC-BY，早期版本以 CC BY 发布） | `languages/fr/tools/prepare_lemmas.py` |
| ru | 重音：kaikki.org（Wiktionary wiktextract）；词频排序：hermitdave/FrequencyWords（OpenSubtitles 2018） | kaikki 与 Wiktionary 为 CC BY-SA 与 GFDL 双许可；FrequencyWords 内容为 CC BY-SA 4.0 | `languages/ru/tools/enrich_stress.py`、`languages/ru/tools/prepare_lemmas_ru.py` |
| de | 词频候选：OpenSubtitles de_50k（FrequencyWords） | CC BY-SA 4.0 | `languages/de/tools/prepare_candidates.py` |
| es | 音标：kaikki-es；词频：OpenSubtitles es_50k | 同 ru | `languages/es/tools/build_dataset_es.py` |
| pt | 音标：kaikki-pt；词频：OpenSubtitles pt_50k | 同 ru | `languages/pt/tools/fill_ipa_kaikki_pt.py` |
| ko | 词表：TOPIK 词表加 kaikki 补充词形 | kaikki 部分同 ru | `languages/ko/tools/build_ko_v2.py` |
| ar | 词表：FreeDict ara_eng；词频：OpenSubtitles ar_50k | 待核实 | `languages/ar/tools/build_tem_arabic_dataset.py` |
| yue | 未使用第三方词典数据集，选词与粤拼为自建 | 不适用 | `languages/yue/data/cantonese_*.json` |

上游位置：Lexique 见 lexique.org；Wiktionary 数据提取见 kaikki.org；OpenSubtitles 词频表见 github.com/hermitdave/FrequencyWords；kanjidic2 见 EDRDG（www.edrdg.org）。

词频数值只在构建阶段用于排序与筛选，没有进入发布态的 xlsx 与 sqlite，列在这里是为了完整说明来源。真正进入发布态的上游数值是音标、重音与汉字读音三列。

## 待核实

- 阿拉伯语工程引用的 ECDICT 与 FreeDict ara_eng，其再分发条款没有逐项核对，以各自上游声明为准。
- 语音由 edge-tts 调用微软神经网络音色合成，不是游戏内资源；涉及微软服务条款的部分不在本仓库的授权范围内。

## 与游戏的关系

本仓库不包含《万词破－单词女友》（WCP-WordGirlfriend, appid 1981560）的任何游戏本体资源。词书与音频通过 BepInEx 在运行时注入，游戏文件未被修改或再分发。

## 商业授权

上述三层都支持单独协商的商业授权。
