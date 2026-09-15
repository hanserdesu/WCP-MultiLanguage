# WCP《万词破-单词女友》西班牙语专业八级词书项目

对标 Arabic (8,118词) / French (8,116词) / German (8,062词) / Russian (8,451词) 的统一工程规格与架构契约，依据中国教育部高校外语专业教学指导委员会《全国高校西班牙语专业四级水平测试 (EEE-4) 考试大纲》与《全国高校西班牙语专业八级水平测试 (EEE-8) 考试大纲》，结合欧标 CEFR A1-C1 标准，构建了全量 8,600 词的西班牙语专业考级完整词库。

## 交付总览与考级分级体系

| 级别 | 词数 | 考纲映射 |
|---|---|---|
| tem4_a1a2 | 2,000 | 专四基础 (A1-A2) |
| tem4_b1 | 2,500 | 专四进阶 (B1) |
| tem8_b2 | 3,000 | 专八进阶 (B2) |
| tem8_c1 | 1,100 | 专八精通 (C1) |
| **合计** | **8,600** | **专四+专八完整覆盖** |

每词 3 条地道西班牙语例句（共 25,800 条例句）+ 单词/例句全套西语母语发音（es-ES-ElviraNeural）。

## 语言学与数据规格

- **语料源**: kaikki.org Wiktionary es (101,834 lemmas) + OpenSubtitles es_50k (5万真实语料词频)
- **IPA 音标**: kaikki-es Wiktionary IPA（es-ES Castilian 优先），覆盖 97% 词头
- **中文释义**: kaikki English gloss + Google Translate 批量翻译 + 前 100 高频虚词人工校准（ES_MANUAL）
- **例句**: 模板引擎（动词/形容词/名词/副词/其他 5 套模板组 × 6 组轮换），严格 1:3 配比
- **形态标记**: 名/动/形/副/代/介/限定/数/连/叹

## 游戏内导入

### 通道一：Excel 零表头导入
output/import/ 下 5 本 xlsx：
- 西班牙语专四基础.xlsx (2,000 词)
- 西班牙语专四进阶.xlsx (2,500 词)
- 西班牙语专八高阶.xlsx (3,000 词)
- 西班牙语专八精通.xlsx (1,100 词)
- **西班牙语考级词库(猫条版).xlsx (8,600 词合并全量)**

游戏内 Excel 导入：无表头，A 列词，B 列释义。

### 通道二：SQLite 外接数据库
复制 output/import/wcp_spanish.db 到 %USERPROFILE%\AppData\LocalLow\WCP\wcp\
游戏内输入 wcp_spanish.db / pron / word / meaning。

## 多语言隔离

单词音频: `%USERPROFILE%\AppData\LocalLow\WCP\wcp\es_word_audio\` (8,600 个 MP3)
例句音频: `%USERPROFILE%\AppData\LocalLow\WCP\wcp\es_sentence_audio\` (25,800 个 MP3)
不与日/法/俄/德/阿/韩共享目录，例句按 MD5(西语原文) 命名。

## 工程工具链

- build_dataset_es.py: 词库构建（分级 + 翻译缓存 + manual 校准）
- batch_gen_sentences_es.py: 1:3 例句生成
- make_import_files.py: Excel + SQLite 导入文件
- gen_word_audio.py / gen_sentence_audio_es.py: edge-tts 音频生成
- verify_all_es.py: 全量审计
