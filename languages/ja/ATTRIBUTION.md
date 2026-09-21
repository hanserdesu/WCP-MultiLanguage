# 许可范围与来源署名

Required Notice: Copyright (c) 2026 hanserdesu（猫条）

本仓库是《万词破－单词女友》日语词书的历史仓库，内容已冻结在群友在用的稳定版；后续开发在多语言工程 hanserdesu/WCP-MultiLanguage，两处适用同一套许可。仓库包含本项目编写的代码与内容，以及从第三方数据集派生的词表与读音。两类材料适用不同条款，范围以本文件为准。

## 一、代码：PolyForm Noncommercial License 1.0.0

适用：`mod_host/`、`mod_jp_wordlist/`、`mod_sentence_audio/`、`mod_book_name/`、`mod_custom_slots/`、`tools/`、`scripts/`、`wcp_wordbooks/tools/`、`wcp_wordbooks/installer/`，以及 `*.cmd` 与 `*.ps1`。完整文本见 [LICENSE](LICENSE)。

你可以为非商业目的使用、修改并再分发这些代码；商业用途需要另行取得授权。

## 二、内容：CC BY-NC 4.0

适用本项目自己编写、生成或整理的材料：

- 中文释义、例句与翻译：`wcp_wordbooks/data/translations/`、`packs/ja/db/sentences.json`、`packs/ja/db/meaning.sqlite` 中的释义字段
- 语音：`packs/ja/audio/`、`wcp_wordbooks/output/` 下的语音载荷
- 各分册的编排、等级划分文案与显示格式

释义与例句由大模型生成后逐条精校，语音用 edge-tts 调用微软神经网络音色批量合成。你可以复制、改编、再分发，条件有三条：署名、不得用于商业目的、不得对他人施加额外限制。

法律文本（简体中文）：https://creativecommons.org/licenses/by-nc/4.0/legalcode.zh-Hans

### 上游词表、读音与署名

日语分册的取词范围、JLPT 分级与读音来自下列数据集，它们不属于上一节的授权范围，继续按上游条款提供：署名必须保留，衍生数据以相同方式共享，能否商用由上游决定。整包因为混合了上一节的内容，整体仍然不可商用。

| 分册或列 | 上游数据集 | 上游许可 | 仓库内脚本 |
| --- | --- | --- | --- |
| JLPT N5 到 N1 词书的取词与分级 | OpenJLPT（github.com/evanclan/OpenJLPT） | CC BY-SA 4.0 | `wcp_wordbooks/tools/build_books.py` |
| 中文释义对照 | Kaishi 1.5k 汉化版（github.com/maimemo/kaishi-zh-cn） | 见「待核实」 | 同上 |
| 假名读音交叉校验 | Bluskyo/JLPT_Vocabulary | 见「待核实」 | 同上 |
| 缺读音词条的假名读音 | JMdict（EDRDG），经 Jisho 接口取回后校对 | CC BY-SA 4.0 | `wcp_wordbooks/tools/fetch_readings.py` |
| 常用汉字册的音训读、逐字振假名拆分 | kanjidic2（EDRDG） | CC BY-SA 4.0 | `wcp_wordbooks/tools/build_kanji_book.py`、`furigana.py` |
| 主题册（IT、商务、医学、法律、惯用句、拟声拟态、四字熟语）的取词范围 | JMdict 3.6.2（EDRDG）的 field 与 misc 标签 | CC BY-SA 4.0 | `wcp_wordbooks/tools/extract_themed.py`、`build_topic_books.py` |

上游位置：JMdict 与 kanjidic2 见 EDRDG（www.edrdg.org）。这些数据集按现行版本以 CC BY-SA 4.0 分发，早期版本曾以 3.0 发布，两种版本都只要求署名与相同方式共享。

法律文本（简体中文）：https://creativecommons.org/licenses/by-sa/4.0/legalcode.zh-Hans

## 待核实

- 语音由 edge-tts 调用微软神经网络音色合成，不是游戏内资源；涉及微软服务条款的部分不在本仓库的授权范围内。
- Kaishi 1.5k zh-CN 与 Bluskyo/JLPT_Vocabulary 两个上游仓库在本地没有附带许可文件，本项目只把它们用于释义对照与读音校验，确切条款需要回上游仓库确认。

## 与游戏的关系

本仓库不包含《万词破－单词女友》（WCP-WordGirlfriend, appid 1981560）的任何游戏本体资源。词书与音频通过 BepInEx 在运行时注入，游戏文件未被修改或再分发。

## 商业授权

代码与内容两层都支持单独协商的商业授权。上游词表与读音那部分由上游条款决定，本项目不代为授权。
