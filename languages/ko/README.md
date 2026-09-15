# WCP《万词破-单词女友》韩语词书项目

复用 `D:\ATooManyLanguage\Japanese` (日语词书) / `D:\ATooManyLanguage\French` (法语词书) / `D:\ATooManyLanguage\Russian` (俄语词书) / `D:\ATooManyLanguage\German` (德语词书) 的全部管线逻辑与架构契约，为 Steam 游戏《万词破 - 单词女友》(WCP-WordGirlfriend, appid 1981560) 生成 **TOPIK 分级韩语词书 + 每词 3 条地道例句 + 单词/例句全套韩语发音**。

## 交付总览

**合并形态**: 书名昵称「韩语词库(猫条版)」；多语言私有化物理隔离，互不干扰。

| 分级 | 词数 | 说明 |
| :--- | :--- | :--- |
| TOPIK 1 (初级) | 1,495 | 日常高频生活与基础语法词汇 |
| TOPIK 2 (中级) | 1,230 | 进阶实用、社交与工作场景词汇 |
| TOPIK 3~6 (高级) | 398 | 政治、经济、法律、哲学与学术论说文核心词汇 |
| **合计** | **3,123** | **每词 3 条地道例句 (共 9,369 条例句，配比严格 1:3.00)** |

- **全量校验**: `python tools/verify_all_ko.py` = **ALL PASS**

## 核心资产与工程落盘

1. **词书与释义 (JSON & Excel & SQLite)**:
   - `output/korean_books.json`: 3,123 词，含韩文原形、IPA 国际音标、中文释义及 3 条例句。
   - `output/import/`:
     - `韩语TOPIK1.xlsx` (1,495 词)
     - `韩语TOPIK2.xlsx` (1,230 词)
     - `韩语TOPIK3.xlsx` (398 词)
     - `韩语全量.xlsx` (3,123 词)
     - `wcp_korean.db` (3,123 词 SQLite 数据库)
2. **多模态音频资产 (私有命名空间物理隔离)**:
   - 单词音频目录: `%USERPROFILE%\AppData\LocalLow\WCP\wcp\ko_word_audio\` (**3,131 个 MP3**, 31.30 MB)
   - 例句音频目录: `%USERPROFILE%\AppData\LocalLow\WCP\wcp\ko_sentence_audio\` (**9,397 个 MP3**, 263.48 MB)
   - 发音人: 韩国首尔音顶级女声 `ko-KR-SunHiNeural` (24kHz 高保真，0 坏死文件)。
3. **离线自愈补丁包 (Payload)**:
   - `output/ko_db_payload/`: 含 `ko_pron.tsv`、`ko_sentences.tsv`、`ko_only_pron.tsv` 与 SHA-256 `manifest.json`，防止官方更新冲掉游戏数据库。
4. **单卡汇总**:
   - `output/catbar_korean_book.json`: 3,123 张标准词卡数据。
