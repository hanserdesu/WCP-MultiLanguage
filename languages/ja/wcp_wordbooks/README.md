# WCP《万词破-单词女友》日语词书

这是一个给 Steam 游戏《万词破-单词女友》（WCP-WordGirlfriend）增加日语学习能力的 mod 项目。

它把日语词书、中文释义、读音、例句和音频接入游戏，让游戏可以用来学习日语，而不只是学习官方英语词库。

## 给普通用户看的说明

### 我应该下载什么？

只需要下载主 Release 里的一个安装包：

[下载 WCP 日语词书一键安装包 v1.2.8](https://github.com/hanserdesu/japanese/releases/download/wcp-jp-v1.2.8/WCP-Japanese-OneClick-Installer-wcp-jp-v1.2.8.zip)（发布页：[wcp-jp-v1.2.8](https://github.com/hanserdesu/japanese/releases/tag/wcp-jp-v1.2.8)）。正在使用旧版本的用户直接覆盖安装一次即可；v1.2.7 起安装器自带自更新，之后无需再手动换包。本次 v1.2.8 修复「部分机器上单词发音变成英语 AI 语音」：单词音频同步补进游戏原生目录，已安装的用户运行一次游戏即自动补缺，无需重装。

不要单独下载资源 Release。安装器会自动下载单词音频和例句音频（优先 Gitee 分片路由，失败自动切换 GitHub），下载后做 SHA-256 完整性校验，中断后保留缓存并断点续传。

> ℹ️ 本仓库继续负责日语词书的维护与用户反馈；法语、俄语、德语、西语、葡语、韩语、阿拉伯语、粤语等多语言版正在 [hanserdesu/WCP-MultiLanguage](https://github.com/hanserdesu/WCP-MultiLanguage) 统一开发，正式上线前不影响日语词书的使用与更新。

### 安装包会做什么？

解压后只需双击最外层的 `01_双击运行我.cmd`，不需要进入 `support` 文件夹。启动器会先创建一个持续保留的 CMD 会话，随后优先使用系统 Windows PowerShell，找不到时自动改用 PowerShell 7；下载和解压音频时会显示百分比、容量和速度，解压使用多线程；当前音频安装峰值约 7 GiB，建议 `%USERPROFILE%` 所在盘至少保留 10 GiB，安装器会在开始前显示实际空间检查；会自动跳过 Steam 注册表中已经不存在的盘符；上次失败留下的临时解压目录不会阻断新安装；不满足运行条件时会显示原因并保持窗口。

双击安装器后，它会自动：

1. 搜索 Steam 的所有游戏库，找到万词破实际安装目录，不要求固定盘符。
2. 如果电脑没有 BepInEx，会自动安装与作者实机一致的 BepInEx 5.4.23.5 和 Doorstop 启动文件。
3. 备份已有的词书存档、插件和旧 BepInEx 文件。
4. 安装日语词书插件、词书数据、数据库修复资源、例句播放插件。
5. 把完整 JLPT N5～N1 日语词书写入一个自定义词书槽，并自动切换到日语词库。
6. 下载并安装单词音频和例句音频；网络中断后重新运行会复用已完成资源，并继续未完成缓存。

安装完成后重新启动游戏即可。安装窗口会一直保留，请点击右上角 X 关闭；按 Enter 不会关闭窗口。

### 安装前需要什么？

- 电脑上已经安装 Steam 版《万词破-单词女友》游戏本体。
- Windows 系统。
- 安装时保持网络畅通，因为音频资源约 2.4 GB，建议预留至少 5 GB 磁盘空间。
- 安装前完全退出游戏。

不需要提前安装 BepInEx，也不需要手动复制 DLL。

### 会不会影响官方英语词库？

正常情况下不会。日语词书写入的是游戏的自定义词书槽，官方英语词库文件不会被替换。安装器还会自动备份 `MyBook.es3`、`SaveFile.es3`、已有插件和旧 BepInEx 文件。

如果四个自定义词书槽都已经占用，安装器会让你选择替换哪个槽位；替换前会创建备份。

已有其他 BepInEx mod 的用户，安装器会保留现有 BepInEx 核心，只补齐缺少的启动文件，并只安装本项目自己的三个插件。

### 这个项目包含哪些学习内容？

- JLPT N5、N4、N3、N2、N1 词汇。
- 中文释义、日语读音和本地单词音频。
- 查词例句、中文翻译和例句音频。
- IT 用语、商务日语、常用汉字、惯用句、拟声拟态、四字熟语等扩展词书。
- 语法路线词书和语法说明例句。

其中一键安装包默认导入的是 7922 词的完整 JLPT 日语词库；其他扩展词书也会随包安装，可在游戏内按需导入。

### 常见问题

**提示找不到游戏：** 确认游戏已经安装，并至少启动过一次；如果电脑有多个游戏目录，安装器会列出目录让你选择。

**提示找不到 E 盘或其他盘符：** 这是 Steam 注册表残留旧安装路径造成的。v1.1.5 会自动跳过不存在的盘符；如果仍然找不到游戏，请确认 Steam 游戏本体已安装并至少启动过一次。
**提示 The directory is not empty：** 这是旧版安装失败后遗留临时解压目录造成的。v1.1.6 每次使用独立临时目录，旧目录清理失败也不会阻止安装；如果磁盘空间不足，可在 `%USERPROFILE%\AppData\LocalLow\WCP\wcp` 中删除名称以 `jpmod_audio_stage` 开头的旧临时目录。
**提示解压速度慢或没有百分比：** 旧版使用 Windows PowerShell 自带的 Expand-Archive，进度显示不完整。v1.1.7 改为内置 .NET 多线程解压，并显示文件百分比、容量和速度。

**音频下载失败：** 检查网络和磁盘空间后重新运行安装器，已下载且校验正确的资源会复用。

`jpmod_downloads` 是持续保留的下载缓存；`jpmod_audio_stage_时间戳_GUID` 是解压临时目录，每次安装尝试使用新的目录。解压中断时会重新解压，但不会因此重新下载已经校验通过或已经保留了部分内容的音频。

**游戏启动后没有插件效果：** 确认游戏已完全退出后再安装，并检查游戏目录中是否存在 `BepInEx` 文件夹。安装器运行结束后要重新启动游戏。

**想恢复原来的词书：** 备份位于 `%USERPROFILE%\AppData\LocalLow\WCP\wcp\jpmod_backups`，每次安装都会生成一个带时间的备份目录。

## 开发者技术说明（可选阅读）

下面内容记录游戏词书格式、数据库结构、音频目录和构建脚本，普通用户不需要阅读。

## 词书机制 (逆向自 Assembly-CSharp.dll)

游戏的自定义词书有两个官方通道，本项目两者都支持:

| 通道 | 文件 | 说明 |
|------|------|------|
| 自定义词书1~4 | `%USERPROFILE%\AppData\LocalLow\WCP\wcp\MyBook.es3` | Easy Save 3 JSON: `SelfBookList1..4`(string[]词表) + `wordDictionary1..4`(词→释义) |
| 外接词库 | `StreamingAssets/wcpOnlyWord.db` 或 persistentDataPath 下 `.xlsx/.db` | SQLite `pron(word,meaning)` 表或 Excel, 游戏内 `SELECT <词列>,<释义列> FROM <表>` 导入 |

发音: 游戏在 `%USERPROFILE%\AppData\LocalLow\WCP\vocabulary` 下找
`<单词>.mp3` / `<单词>.wav`，找不到才回退内置AI(英语向)TTS。
日语词必须生成本地音频，本项目用 edge-tts (ja-JP-NanamiNeural)。

书名: SaveFile.es3 的 `SelfBookName1..4` 键(游戏内改名UI写这里)。

## 游戏内导入契约 (逆向自 SaveSourceType, 2026-09-06 会话B确认)

- **Excel 导入** (`LoadDataAndSaveFromExcel`, NPOI): 读第一个 sheet,
  **从第 0 行开始**, 只读 **A列=单词, B列=释义**(游戏内显示文本);
  C 列以后忽略。**因此 xlsx 不能加表头行** —— 本项目生成的 xlsx 均为
  无表头格式, C/D 列放读音/英文释义仅供人工参考。
- **外接词库** (`testConnect`/`StartSaveDataBase`): 文件须放
  `%USERPROFILE%\AppData\LocalLow\WCP\wcp\`(persistentDataPath),
  游戏内输入文件名; .db 走 `SELECT <词列>,<释义列> FROM <表>`,
  默认兼容 `pron(word, meaning)`; .xls/.xlsx 亦从此目录读取。
- 全部交付文件已复制到 persistentDataPath (见下方清单)。

## Set B-1 主题词书: 惯用句/拟声拟态/四字熟语 (2026-09-06 会话A新增)

| 词书 | 词数 | 词源 | 交付 |
|------|------|------|------|
| 惯用句·谚语 | 533 | IdiomKB 词表(270)+自选扩充, 释义全部重写 | `惯用句谚语.xlsx` + `wcp_setb.db` |
| 拟声拟态 | 638 | node-jp-giongo 词典(1649条筛选), 释义全部重写 | `拟声拟态.xlsx` + 同 db |
| 四字熟语 | 260 | 自选常用词表, 读音经 yoji_df.csv 逐条校验(修正13处) | `四字熟语.xlsx` + 同 db |
| 高级词汇 | 234 | N1+/文语/新闻语自选词表, 已对JLPT主词书去重 | `高级词汇.xlsx` + 同 db |
| 商务敬语 | 636 | 敬语・邮件套话・商务术语自建词表 | `商务敬语.xlsx` + 同 db |

- 词表: `data/topic/{idioms,giongo,yoji}.json` (LLM 精翻: 中文释义+词性+读音)
- 读音 QA: `tools/setb_check_readings.py` — kanjidic2 音训读分解校验
  (容忍促音/连浊/送假名); 1562 汉字词全部过检, 修正 虚栄心・再現手順 等;
  残留 flag 均为約音(お客→おきゃく)・転呼・熟字訓(塩梅/為替/十八番)・
  敬语特殊读音(仰る/召し上がる) 等合法现象, 人工逐条复核无错误
- 高频惯用句86条附日文例句+中文翻译 (惯用句谚语.xlsx E/F列, 游戏忽略,
  供人工学习参考; 源: data/topic/idioms_examples.json)
- 构建: `tools/setb_build.py` → `output/setb_books.json`;
  导入: `tools/setb_import.py` (无表头 A词/B义, 符合游戏契约) →
  `output/import/setb/` + `wcp_setb.db` (pron 1431 词 + setb_all 明细)
- 已复制到 persistentDataPath: 惯用句谚语.xlsx / 拟声拟态.xlsx /
  四字熟语.xlsx / wcp_setb.db
- 发音: `tools/setb_audio.py` (独立 manifest `setb_audio_manifest.json`,
  与 JLPT / topic 音频管线互不干扰)
- 夜间循环: `tools/night_loop.sh` → `setb_worker.py` (每5分钟一轮:
  补音频+重试失败+游戏关闭后改名, 止于 2026-09-07 09:00)

## 槽位规划

| 槽位 | 词书 | 词数 |
|------|------|------|
| 自定义词书一 (JLPT N5+N4) | N5(661) + N4(632) | 1293 |
| 自定义词书二 (JLPT N3) | N3 | 1784 |
| 自定义词书三 (JLPT N2) | N2 | 1791 |
| 自定义词书四 (JLPT N1) | N1 | 3463 |

合计 8331 词, 中文释义覆盖率 100% (en_only=0), 词性标注覆盖率 100%,
读音校正 83 条, 本地日语发音 MP3 8079 条 (0 失败)。

## Set B 专业词书 (2026-09-06 会话B新增)

| 词书 | 词数 | 词源 | 交付 |
|------|------|------|------|
| IT 用语 | 662 | JMdict 3.6.2 field=comp | `IT用语.xlsx` + `wcp_topic.db` |
| 商务日语 | 458 | JMdict 3.6.2 field=bus/finc(+econ/trade) | 同上合并 `wcp_topic.db` |

- 管线: `build_topic_books.py`(提取) -> LLM 精翻
  (`data/translations/topic_zh_*.json`; 翻译文件即保留清单, 未翻译词自动过滤,
  已剔除 COBOL/JIS 博物馆级冷僻词) -> `merge_topic.py --write-import`
  -> `gen_audio_topic.py`(独立 manifest: audio_manifest_topic.json)
- 发音 MP3 与 JLPT 一样放入游戏 vocabulary 目录, 词即文件名。
- `wcp_topic.db`: `pron` 表两书合并(1118 词)可直接作外接词库启用;
  `topic_all` 表含 topic 字段区分两书。
- 读音: JMdict + Bluskyo/Jisho 缓存补全, 汉字词 100% 有读音。
- **四字熟语/拟声拟态/惯用句** 由并发会话A制作 (09:09-09:12 下载词源),
  本会话未涉及, 分工见 `logs/agent_worklog.md`。

### Set B 交付文件 (已复制到游戏 persistentDataPath)

```
%USERPROFILE%\AppData\LocalLow\WCP\wcp\
  ├─ IT用语.xlsx          游戏内导入槽位用 (无表头, A词/B义)
  ├─ 商务日语.xlsx
  ├─ wcp_topic.db         外接词库 (pron 1118 词)
  ├─ 常用汉字.xlsx        常用汉字表 2136 字 (音训+字义)
  ├─ wcp_kanji.db         常用汉字 外接词库 (pron 2136 字)
  ├─ JLPT_N5N4_初级.xlsx  JLPT 四书导入用 (已修正为无表头 2 列格式)
  ├─ JLPT_N3.xlsx / JLPT_N2.xlsx / JLPT_N1.xlsx
  └─ wcp_jlpt.db          JLPT 外接词库 (pron 7922 词)
```

## Set C 常用汉字书 (2026-09-06 会话B新增)

| 词书 | 字数 | 词源 | 交付 |
|------|------|------|------|
| 常用汉字 | 2136 | kanjidic2 (EDRDG, grade 1-8 = 常用汉字表) | `常用汉字.xlsx` + `wcp_kanji.db` |

- 显示格式: `音:ア 訓:つ.ぐ｜亚；次之` (音读取前3/训读取前3, kanjidic2 顺序)
- 2136 字中文核心字义全部由 LLM 逐字精翻 (`data/translations/kanji_zh_*.json`),
  含 JLPT 级别标记 (xlsx F 列: G<grade> N<jlpt>)
- 音频特殊处理: 文件名 = 汉字(如 `愛.mp3`), 内容朗读该字音训读音
  (如 `アイ、いとしい`), 避免单字 TTS 误读音; manifest:
  `audio_manifest_kanji.json`
- 管线: `build_kanji_book.py`(解析 kanjidic2.xml) -> `merge_kanji.py
  --audio`(合并+导入文件+音频)
- 学习价值: 漢検/常用汉字训练、汉字音训掌握, 是 JLPT 词书之外的
  独立维度 (非词而字)。

### 释义质量分层 (优先级从高到低)

1. **LLM 精翻** (`data/translations/zh_llm_refine_00~28.json`, 29 个批次,
   8076 个词键): 全部 8073 个去重词逐词校正的中文释义 + 词性
   (名/动1/动2/动3/イ形/ナ形/副/接/惯/接头/接尾/量/代 等) + 读音校正;
   异体字/熟字训变体 (如 相変わらず/其れ/何時/御免なさい) 单独给出释义与读音
2. Kaishi 1.5k zh-CN 中文释义 (初级命中 2170 条)
3. Google 翻译 gtx 英文释义→中文 (兜底层)

最终 `zh_source` 为 `llm` 的词即经过精翻; 各层统计见
`output/jlpt_books.json` 的 `meta.translation_layers`。

若想换成其他组合，用 `output/import/` 里的官方导入文件在游戏内重新导入即可:
- `JLPT_N5N4_初级.xlsx` / `JLPT_N3.xlsx` / `JLPT_N2.xlsx` / `JLPT_N1.xlsx`
- `wcp_jlpt.db` — 全级别 SQLite 外接词库(`pron` 表 + `jlpt_all` 表)

## 数据源

- [OpenJLPT](https://github.com/evanclan/OpenJLPT) (CC-BY-SA-4.0): 词表主数据
  (单词/读音/英文释义/例句)
- [Kaishi 1.5k zh-CN](https://github.com/maimemo/kaishi-zh-cn): 中文释义(初级)
- [Bluskyo/JLPT_Vocabulary](https://github.com/Bluskyo/JLPT_Vocabulary): 读音交叉验证
- Google 翻译 gtx 端点: 剩余英文释义→中文 (`data/translations/gtx_zh.json`)
- Jisho API: 缺失读音补全 (`data/readings_jisho.json`)
- LLM 精翻批次 (`data/translations/zh_llm_*.json`): 人工质量层, 优先级最高

释义显示格式: 汉字词 `【假名】中文〈词性〉`；假名词直接 `中文`。

## 工具脚本 (tools/)

```
build_books.py          数据源 -> output/jlpt_books.json (重建基础数据)
write_mybook.py         词书写入游戏 MyBook.es3 (自动备份到 MyBook_backups/)
                        --dry-run 预览; --file 指定其他目标
make_import_files.py    生成 output/import/ 的 xlsx + sqlite 外接词库
                        (2026-09-06 修正: 无表头, A列词/B列义, 匹配游戏契约)
build_topic_books.py    JMdict 提取 IT/商务词条 -> output/topic_books.json
merge_topic.py          合并 topic_zh_*.json 精翻 -> topic_books.json
                        --write-import 生成 IT用语.xlsx/商务日语.xlsx/wcp_topic.db
gen_audio_topic.py      Set B 发音MP3 (独立 manifest, 与 JLPT 管线不互斥)
check_topic_keys.py     校验 topic 翻译键与源词表拼写一致
build_kanji_book.py     解析 kanjidic2.xml -> 常用汉字 2136 字骨架
merge_kanji.py          合并 kanji_zh_*.json -> 常用汉字书 + xlsx/db
                        --audio 生成音训朗读 MP3
night_worker.py         夜间工兵(计划任务 WCP_NightWorker 每20分钟): 补音频+
                        重建导入文件+本地词库补丁+恢复默认书名+到期自删除
patch_local_db.py       【关键】日文词/例句灌入游戏本地词库 wcpFullEng.db/
                        wcpOnlyWord.db (游戏内释义例句的真正数据源; 幂等)
gen_audio.py            批量生成发音MP3 -> 游戏 vocabulary 目录 (断点续传)
                        --limit N 分批; --retry-failed 重试失败项
translate_gtx.py        机翻英文释义 (断点续传, data/translations/gtx_zh.json)
fetch_readings.py       Jisho 补读音 (data/readings_jisho.json)
merge_translations.py   合并翻译/读音 -> 重建 jlpt_books.json
                        --write-game 同时重写 MyBook.es3 + 导入文件
make_llm_batch.py       导出下一批 LLM 精翻任务 llm_batch_pending.json
rename_books.py         SaveFile.es3 写入词书署名昵称 (仅游戏关闭时执行)
wcp_paths.py            解析「实际在跑的那份」游戏目录 (所有写库脚本共用)
auto_worker.py          夜间自动化工人: 音频+机翻+读音+合并+改名一轮跑完
                        (带锁防重入; 进度写 logs/progress.json)
ildump.py               游戏DLL IL 反汇编工具(逆向用)
```

## 已备份

- `MyBook.es3` 原始文件: `%USERPROFILE%\AppData\LocalLow\WCP\wcp\MyBook_backups\`

## 注意事项

- 游戏(经提权的 Steam 启动)运行时会用内存态覆盖 SaveFile.es3，故
  rename_books.py 仅在游戏关闭时生效。
- 含 `/` 等非法文件名字符的词(如 いい/よい)无法生成本地mp3，游戏会回退AI发音。
- MyBook.es3 只在创建词书时被游戏写入，平时只读，直接改是安全的。

## Set B-2 专业主题词书 9 册 (2026-09-06 会话C新增, JMDict 管线)

| 词书 | 词数 | 词源 | 交付 |
|------|------|------|------|
| IT·计算机 | 800 | JMDict field=comp | `主题_IT计算机·例句版.xlsx` + `wcp_themed.db` |
| 医学 | 800 | JMDict field=med/pathol/anat | `主题_医学·例句版.xlsx` + 同 db |
| 商务·经济 | 419 | JMDict field=bus/econ + LLM 增补 118 | `主题_商务日语·例句版.xlsx` + 同 db |
| 法律 | 600 | JMDict field=law | `主题_法律·例句版.xlsx` + 同 db |
| 惯用句 | 683 | JMDict misc=id + LLM 增补 96 | `主题_惯用句·例句版.xlsx` + 同 db |
| 拟声拟态 | 551 | JMDict misc=on-mim + LLM 增补 60 | `主题_拟声拟态·例句版.xlsx` + 同 db |
| 四字熟语 | 500 | JMDict misc=yoji | `主题_四字熟语·例句版.xlsx` + 同 db |
| 敬语 | 76 | LLM 自建 (尊敬/谦让/郑重/商务) | `主题_敬语·例句版.xlsx` + 同 db |
| 谚语·格言 | 67 | LLM 自建 ことわざ | `主题_谚语格言·例句版.xlsx` + 同 db |

- 提取: `tools/extract_themed.py` (过滤 rK/uK/iK 罕用词形、中文式叠词、
  与 JLPT 重叠的转义词; 读音必须匹配所选词形)
- 精翻: 24 批 `data/translations/zh_llm_themed_00~23.json` — 全部 4496 词
  逐词中文释义+词性+日文例句, 0 机翻残留; 人工增补 417 条在
  `data/themed/extra_*.json` (新增 keigo/kotowaza 两主题)
- 校验: `tools/validate_themed.py` (JMDict 字符白名单+简体语料白名单,
  拦截简体字混入日文例句); `tools/themed_check_readings.py`
  (kanjidic2 音训分解校验, 残留 flag 均为熟字训/连浊/约音合法现象)
- 合并: `tools/merge_themed.py` -> `output/themed_books.json`;
  导入: `tools/make_import_files_themed.py` (无表头 A词/B义 契约格式)
- 音频: `gen_audio.py` 已扩展读取 themed_books.json (与 JLPT 共用
  `audio_manifest.json`), 4479 词 MP3 后台生成
- 文件名「主题_·例句版」前缀避免与会话A/B 同名交付互相覆盖

## ⚠️ 灌库目标路径 (2026-09-12 修正, 必读)

**症状:** 游戏里仍然显示「[糟糕！本地暂未收录这个单词！我们会继续为您扩充
词库的！]」, 例句栏空白。

**原因:** 本机有两份游戏副本, 而工具硬编码的是**没在跑的那份**:

- 真正在跑的: `E:\Steam\steamapps\common\WCP-WordGirlgriend` —— 证据是
  `%USERPROFILE%\AppData\LocalLow\WCP\wcp\Player.log` 第一行
  `Mono path[0] = 'E:/Steam/.../wcp_Data/Managed'`; `E:\Steam` 是 Steam
  库 0 (见 `E:\Steam\steamapps\libraryfolders.vdf`)
- 被误灌的旧副本: `E:\SteamLibrary\...` —— 已不在任何 Steam 库里, 游戏
  永远读不到它

**修复:** 新增 `tools/wcp_paths.py` 统一解析游戏目录 (env `WCP_GAME_DIR` →
注册表 SteamPath/InstallPath → 各库 libraryfolders.vdf → 候选目录; 只认
「存在 `wcp_Data/StreamingAssets/wcpFullEng.db`」的那份)。写库/校验脚本
`patch_local_db` / `apply_sentences` / `apply_readings` / `verify_all` /
`build_grammar_book` / `export_sentences` / `ildump` 全部改用它;
`patch_local_db.backup()` 也改为按库文件绝对路径加 tag, 多副本互不覆盖。
`verify_all.py` 复核: pron 15812/15812、sentence2 每词 ≥3 条、音频
15812/15812、外接库同步。

**会被 Steam 还原:** 「验证游戏文件完整性」或游戏更新会把 StreamingAssets 下的
4 个 .db 换回英文原库 (2026-09-12 06:19 发生过一次)。之后重跑:

    python tools/patch_local_db.py
    python tools/build_grammar_book.py --patch

(persistentDataPath 里的词书文件与音频不受影响。)

**另一个坑 (已修):** `apply_sentences.py` 原先用 `logs/sentence_worklist.tsv`
里的 rowid 做 `UPDATE sentence2 ... WHERE rowid=?`, 而那份清单是
`patch_local_db.py` **重建 sentence2 之前**抓的 —— 行号早已指向别的词, 于是
10,251 条例句被写串到别的词上 (词数/条数全对, 内容全错)。现已改为按
「词 + 原句」定位, 幂等且不跨词覆盖。

## ⚠️ 词书署名 (2026-09-12)

游戏书单里的书名是 `"自定义词书一（" + SelfBookName1 + ")"`
(AddElementsToScrollView:180 / WordChooseButtonS10:1042), **括号内那段就是官方
留给玩家的昵称/署名位**, 存在 SaveFile.es3 的 `SelfBookName1..4`。

关键: 昵称**不参与**槽位身份。学习/查词看的是 `ChosenBook_Para`
(必须是 `自定义词书一`..`四`) + MyBook.es3 的 `SelfBookList1..4`; 游戏内
改名 UI (`SaveSourceType.setBookName`) 也只写 `SelfBookNameN`。所以改昵称
安全 (真正的字典开关是 `ChosenBook_Para`, 不要动它)。

`tools/rename_books.py` 已改为写署名, 游戏内显示为:

    自定义词书一（猫条·JLPT初级 N5+N4）
    自定义词书二（猫条·JLPT N3）
    自定义词书三（猫条·JLPT N2）
    自定义词书四（猫条·JLPT N1）

- 署名常量在脚本顶部的 `AUTHOR = '猫条'`, 换名字只改这一行
- `--restore` 还原为「自定义词书N（自定义词书N）」的默认状态
- 写前备份 SaveFile.es3, 只在 wcp.exe 未运行时执行, 写完回读校验
- night_worker / setb_worker / auto_worker 都调用它, 署名会被保持
- 改的是 `%USERPROFILE%\AppData\LocalLow\WCP\wcp\SaveFile.es3`; 若开了
  Steam 云同步, 换机时可能被云端旧存档覆盖, 重跑本脚本即可

## ⚠️ 游戏内释义/例句机制与书名约束 (2026-09-06 晚 关键逆向)

**为什么之前游戏里"本地暂未收录这个单词":**
1. 学习界面 (DatabaseManagerS8) 查释义/例句用的是 **StreamingAssets/wcpFullEng.db**
   (`pron` 表 + `sentence2` 例句表), 原库只有英文 — 日文词查不到;
2. 词书内置释义字典 (SelfBookMeaningDictionary) **只在书名等于
   「自定义词书一/二/三/四」时才加载** (GetSelfBookMeaningAfterSet::SetSelfBook
   精确匹配), 书名改成别的名字 → 字典不加载 → 全部落本地库。

**修复 (patch_local_db.py, 已执行):**
- 15,812 个日文词条 (JLPT 8331 + 会话A SetB 2301 + 会话B IT/商务 1120 +
  常用汉字 2136 + 会话C 主题 9+1 册, 去重) 写入 wcpFullEng.db 与
  wcpOnlyWord.db 的 `pron` 表 (ukPhonic=[かな]);
- 10,499 条日文例句写入 wcpFullEng.db `sentence2` (格式对齐原库:
  `例句：日本語。（翻译）`);
- 原库备份在 `backups/`; 补丁幂等 (词数增长才重灌), 已挂入夜班工兵;
- **游戏无需重启** — 每次查词现开数据库连接, 下一个词立即生效;
- 模拟游戏 SQL 抽验 (低い/焼け石に水/正規表現/愛) 释义+注音+例句全部命中。

**书名约束 (2026-09-12 更正):** 上面这条早期结论有误 —— 改的是**昵称**, 不是
槽位身份。真正决定「是否加载词书内置字典」的是 `ChosenBook_Para` (槽位名
`自定义词书一~四`), 由选书逻辑写入, 游戏内改名 UI 不会碰它。四个槽位名保持
`自定义词书一~四` 不变即可, 昵称随便写 (见上文「词书署名」)。

## 尚未完成 (下一步)

- **书名署名**: ✅ 已生效 — 昵称走 `SelfBookName1..4`, 与槽位名
  `ChosenBook_Para` 相互独立, 见上文「词书署名」。
- **~~四字熟语/拟声拟态/惯用句词书~~**: ✅ 会话A已交付 (Set B-1, 共1431词,
  见上文), 音频由 night_loop 后台续传。
- **JLPT 四书的表头行问题已修正**: 旧版 xlsx 有表头且 B列=读音, 直接导入会
  得到"读音当释义"的错误词书, 现已重新生成并复制到 persistentDataPath。

## 例句全覆盖 (2026-09-11 完成)

全部 15,812 词每词 3 条日文例句 + 中文翻译, 已写入游戏本地库。

- 管线: `build_sentence_jobs.py`(词块 gen_words_XX + 翻译块 tr_chunk_XX)
  → 子代理生产 `work/gen_out_NN_Y.json`(每批100词×3句, 契约见
  `work/AGENT_SPEC.md` + `work/PATCH_SPEC.md`, `gen_pipeline.py check-one`
  逐批校验) → `apply_sentences.py`(合并 master + 落库)
- 旧库已有例句 10,251 句的中文翻译全部补齐 (`work/tr_out_*.json`)
- 最终状态: `gen_pipeline.py summary` = 达标 15812/15812, 剩余批次 0;
  `sentences_master.json` 15,812 词 缺翻译 0 <3条 0;
  wcpFullEng.db sentence2 逐词全查 15,812 词全部 ≥3 条
- master: `data/translations/sentences_master.json` {word: [[ja,zh],...]},
  是 `patch_local_db.py` 灌 sentence2 的数据源 (幂等, 游戏无需重启)

## 语法路线词书 (2026-09-12 完成)

不单是背单词的「单词语法融合」词书: 8,331 个 JLPT 词按学习路线重排
(Kaishi 频率优先), 每 15/16/25/30/40 词一个词块, 块后插入 1 个语法
占位词 (G001...G304 + 5 个阶段头), **语法讲解写在占位词的例句栏**
(3 行 = 接续/用法/注意, ja 是可朗读例句, 中文讲解在括号内)。

- 5 阶段: 一 入门N5(45点) → 二 基础N4(40) → 三 进阶N3(72) →
  四 上级N2(60) → 五 精通N1(87), 大纲 `data/grammar/curriculum.json`
- 内容生产: 分片 `work/gchunk_XX.json` + 契约 `work/GRAMMAR_SPEC.md`
  → 子代理/主会话写 `work/grammar_out_XX.json` → 合并
  `data/grammar/content/gc_XX.json` → `check_grammar_content.py`
  全量校验 (304/304, 0 问题)
- 构建: `tools/build_grammar_book.py [--stages ...] [--patch]`
  → `output/grammar_route.json` (8,640 行) +
  `output/grammar_book/语法路线.xlsx` (无表头 A词B义) +
  `output/grammar_book/wcp_grammar.db` (pron + route 明细)
- 落库: `--patch` 把 309 个占位词灌 wcpFullEng.db (pron+ukPhonic+
  sentence2 共 927 条讲解) 与 wcpOnlyWord.db; 幂等, 游戏无需重启
- 发音: `tools/gen_grammar_audio.py` — 占位词朗读「读音+首例句」
  (vocabulary/<word>.mp3 共 309 个), 讲解例句与播放 Mod 同命名
  (sentence_audio md5(ja).mp3 共 927 条), 0 失败
- 已复制到 persistentDataPath: 语法路线.xlsx / wcp_grammar.db,
  导入任一自定义词书槽或外接词库即可开始; 词块单词的例句/发音
  复用既有 JLPT 数据

## 例句语音 + 播放 Mod (2026-09-12 完成)

56,941 条唯一例句全部生成日语语音 (edge-tts ja-JP-NanamiNeural),
配 BepInEx 插件在游戏内一键朗读。

- 生成: `tools/gen_sentence_audio.py` — 输出到
  `%USERPROFILE%\AppData\LocalLow\WCP\wcp\sentence_audio\<md5(ja)>.mp3`,
  断点续传(按文件存在+大小), 12 并发, 0 失败
- 播放: `mod_sentence_audio/` (BepInEx 5 插件, NETFX csc 编译,
  `build.cmd` 一键构建部署) — 每 0.3s 反射扫描 每日学习/词典查询 的
  `exmplesentences` 文本, 剥掉「例句：」前缀与「（中文）」后按 md5(ja)
  命中本地 mp3, 例句旁挂 ▶ 按钮; 不 Harmony 补丁, 游戏更新可自动降级
- 语法路线词书的 927 条讲解例句复用同目录同命名规则, 播放 Mod 直接命中
