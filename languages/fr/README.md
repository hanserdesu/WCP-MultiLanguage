# WCP《万词破-单词女友》法语词书项目

复用 `D:\Japanese` (日语词书) 的全部管线逻辑与 `D:/Japanese/IMPLEMENTATION.md` 复刻契约，为 Steam 游戏《万词破 - 单词女友》
(WCP-WordGirlfriend, appid 1981560) 生成 **CEFR 分级法语词书 + 每词 3 条例句 + 单词/例句全套法语音频**。

## 交付总览

**合并单册形态** (与日语词库一致): 全部词写进游戏**自定义词书二**，
书名昵称「法语词库(猫条版)」；槽位一、三、四均不触及。

| 分册 | 词数 | 说明 |
|------|------|------|
| A1 | 699 | 词表内按 a1→a2→b1→b2 顺序排布, 每日学习按序推进 |
| A2 | 1,981 | |
| B1 | 2,902 | |
| B2 | 2,534 | |
| **合计** | **8,116** | 每词 3 条例句; 单词MP3 8,116 (0 失败); 例句MP3 24,328 唯一句 (0 失败) |

分级分册的 xlsx (`法语A1A2.xlsx`/`法语B1.xlsx`/`法语B2.xlsx`) 仍保留在
persistentDataPath, 想按级别分开学可用游戏内 Excel 导入占用槽位三/四。

- 书名昵称: `自定义词书二（法语词库(猫条版)）` (SaveFile.es3 `SelfBookName2`;
  合并单册, write_mybook_fr.py --split 可回到三册分级形态)
- **槽位一(日语合并书 7,922 词) 原样保留**, 未动任何日语数据
- 全量校验 `tools/verify_all_fr.py` = **ALL PASS**

## 与日语项目的对应关系 (对齐 IMPLEMENTATION.md 规范)

| 环节 | 日语 (D:\Japanese) | 法语 (D:\French) |
|------|--------------------|------------------|
| 词源 | OpenJLPT + LLM 精翻 | Lexique383 (lexique.org, 词元/词性/频率/音标) + LLM 精选 |
| 释义格式 | 【假名】中文〈词性〉 | [IPA] 中文〈词性〉 |
| 音标 | 假名 (kanjidic2 校验) | Lexique phon 记号→IPA 映射 (@=ɑ̃ §=ɔ̃ 5=ɛ̃ 1=œ̃ 2=ø 9=œ 8=ɥ °=ə N=ɲ G=ŋ R=ʁ S=ʃ Z=ʒ) |
| 词书写入 | write_mybook.py 槽位1-4 | write_mybook_fr.py **默认只写槽位2** |
| 词库数据源 | 共享本地库 wcpFullEng.db (pron + sentence2) | **共享本地库 wcpFullEng.db (pron 8,116 词 + sentence2 24,348 句)** |
| 单词音频 | edge-tts ja-JP-NanamiNeural → `vocabulary/<word>.mp3` | edge-tts **fr-FR-DeniseNeural** → **`fr_word_audio/<word>.mp3`** (8,116 全覆盖, 由 mod 拦截播放; 见下方「与契约的有意分歧」) |
| 例句音频 | gen_sentence_audio.py (md5(ja)) | gen_sentence_audio_fr.py (md5(fr), 同目录同规则, 24,328 句全覆盖) |
| 例句播放 Mod | mod_sentence_audio (ExtractJa 认日文字符) | **mod_sentence_audio_fr** (ExtractFr 认拉丁字母且禁CJK/假名, 绿色▶, FR 标签, 仅例句播放) |
| 词书隔离与测试 Mod | JpWordListMod (JpWL_* 基线还原, 假名题干) | **mod_fr_wordlist** (**FrWordListMod**, FrWL_* 隔离基线还原, 快速/已学词测试题干同步, 离线自愈) |
| 外观与回读拦截 Mod | BookNameMod (JP 发音标签, 选书回读拦截) | **mod_book_name** (通用多语言支持: FR/JP 标签, 自定义词书回读保护) |
| 校验管线 | gen_pipeline.py / verify_all.py | gen_pipeline_fr.py / **verify_all_fr.py** (全量复核) |

运行时插件集对齐 IMPLEMENTATION.md:
- **BookProfiles.cs + BookNameMod.dll**: 统一词书指纹识别，支持法语词库外观名与选书回读拦截 (防 SonBookChoose 崩溃)，发音按钮显示 FR 标签。
- **SentenceAudioFrMod.dll**: 监听 exmplesentences，朗读本地法语例句音频 (绿色 ▶ 按钮与 FR 标签)。
- **FrWordListMod.dll**: 严格 Fail-Closed 词书隔离 (FrWL_*)，修复游戏原生快速测试从全局抽取英语词及题干 need[0] 错位的 bug，确保已学词测试与自选测试只出法语题，并提供离线自愈 (fr_db_payload)。每日学习/复习的总表、剩余队列、已完成队列和完成标志也与日语复刻版保持一致，自动修复“2/100 却已完成”的跨会话残留状态。

**共享词库 book-scoped 切换 (2026-09-13)**: 法语 8116 词中有 1638 个与英语原库同形 (table/zoom/vote/...)。共享库稳态 = 英文原版 + 法语独有词补丁 (6478 词)；选中法语书时 FrWordListMod 后台把同形词切成法语释义/例句，离开时自动还原英文，因此英语/日语词书完全不受法语影响，法语书的释义例句也完整。离线自愈 payload 同时携带两套基线 (fr_*.tsv / en_*.tsv)，官方更新覆盖后自动恢复。

## 与 IMPLEMENTATION.md 的有意分歧 (必须知道)

复刻文档 §1.5 规定单词音频放共享目录 `%USERPROFILE%\AppData\LocalLow\WCP\vocabulary\<word>.mp3`，
由游戏原生查表命中。**法语不复用这条**，原因是词形冲突：

- 日语词形是汉字/假名，与内置英语词不重名，共享目录天然安全。
- 法语词形是拉丁字母，8,116 词里 **1,638 个与英语原库同形**（table / zoom / vote / nation …）。
  若把法语发音写进共享 `vocabulary/`，英语/日语词书查这些词时会听到法语发音。

因此法语单词音频隔离到私有目录，并由插件接管播放：

| 项 | 值 |
|---|---|
| 音频目录 | `%USERPROFILE%\AppData\LocalLow\WCP\wcp\fr_word_audio\<word>.mp3` |
| 播放路径 | `FrWordListMod` 前缀拦截 `VocabularyAudioPlayer.PlayWordAudio`，命中本书指纹时才改放本地文件，否则原样放行 |
| 共享目录 | `vocabulary/` 只保留日语词书音频（16,312 个），法语词零残留（`verify_all_fr.py` 有专项检查） |
| 相关脚本 | `tools/audio_paths_fr.py`（两端统一的路径常量）、`tools/gen_word_audio.py`（直接生成到 fr_word_audio）、`tools/deprecated/isolate_word_audio_fr.py`（历史迁移 / `--restore` 回滚） |

其余契约（ES3 类型包装、选书回读拦截、槽位指纹识别、灌库幂等、例句 md5 命名、离线自愈 payload）
均按文档 1:1 复刻，未做改动。

## 数据流水线

```
Lexique383.tsv (142,694 行)
  └─ tools/prepare_lemmas.py      词元聚合(按词频) + 专名过滤 + phon→IPA
       → data/lemmas_ranked.json  8,600 词元
  └─ tools/build_curate_chunks.py 29 块 × 300 词 (work/cur_NN.json)
  └─ 子代理精选 (work/CUR_SPEC.md 契约 + curate_pipeline.py 校验)
       → work/cur_out_NN.json     drop 484 (专名/冷僻/屈折残留)
  └─ tools/merge_curated.py       → output/french_books.json 8,116 词
  └─ tools/build_gen_jobs.py      82 块 × 100 词 (work/gen_words_NN.json)
  └─ 子代理例句 (work/GEN_SPEC.md 契约 + gen_pipeline_fr.py check-one)
       → work/gen_out_NN_0.json   24,348 句 + 中文翻译
  └─ tools/apply_sentences.py     → data/translations/sentences_master.json
  └─ tools/make_import_files.py   → output/import/ 法语*.xlsx + wcp_french.db
  └─ tools/write_mybook_fr.py     → MyBook.es3 槽位2 (自动备份)
  └─ tools/patch_local_db_fr.py   → 灌库 wcpFullEng.db (pron+sentence2) 与 wcpOnlyWord.db
  │   (2026-09-13 起跳过 1638 个英法同形词, 英文内容由英文基线维护)
  └─ tools/restore_english_overlap_fr.py → 同形词英文还原 (一次性修复, 严格模式)
  └─ tools/rename_books_fr.py     → SaveFile.es3 昵称 (槽位1保留)
  └─ tools/gen_word_audio.py      → fr_word_audio/<word>.mp3 (断点续传, 见下方「有意分歧」)
  └─ tools/gen_sentence_audio_fr.py → sentence_audio/<md5(fr)>.mp3 (断点续传)
  └─ tools/export_fr_db_payload.py → fr_db_payload (离线自愈 TSV 补丁包,
  │   法语态 fr_*.tsv 全量 8116 词 + 英文态 en_*.tsv 同形词 1638 词)
  └─ tools/reset_stale_test_fr.py → 安全清理残留跨词书测试状态
  └─ tools/verify_all_fr.py       全量校验
```

## 游戏内生效方式

1. **词书已直接写入** MyBook.es3 槽位2, 进游戏书单即可见
   `自定义词书二（法语词库(猫条版)）`, 无需手动导入。
2. 游戏内释义/例句原生生效, 发音由插件接管:
   - 释义/例句: 游戏从本地词库 `wcpFullEng.db` 查 `pron` 表的 `[IPA] 中文〈词性〉` 与 `sentence2` 的 3 条例句
   - 发音: 游戏先查共享 `vocabulary/`, 命中法语书指纹时由 `FrWordListMod` 改放
     `fr_word_audio/<word>.mp3` (fr-FR-DeniseNeural); 法语词不写共享目录 (见下方「有意分歧」)
3. **例句朗读**: BepInEx 插件 `SentenceAudioFrMod.dll` (已部署到
   `E:\Steam\steamapps\common\WCP-WordGirlgriend\BepInEx\plugins\`),
   例句旁挂 ▶ / 游戏读例句按钮接管为 FR 标签, 播放 `sentence_audio/<md5(fr)>.mp3`。
   插件带词书指纹闸门 (WcpBookProfiles, 与日语版同源): 只在当前词书就是
   本法语书 (8,116 词指纹 `376af2ea...`) 时才显示按钮/接管朗读, 切到其它任何词书
   立即无损还原游戏原 UI。
4. 换机/重装: persistentDataPath (`%USERPROFILE%\AppData\LocalLow\WCP\wcp\`)
   里有 `法语A1A2.xlsx` / `法语B1.xlsx` / `法语B2.xlsx` (无表头 A词B义契约格式,
   C-F 列为 IPA/释义/词性/级别参考) 和 `wcp_french.db` (pron 8,116 词 +
   french_all 明细), 游戏内 Excel/外接词库通道导入即可。

## 打包与发布 (形态 B, 与日语项目同构)

```bash
python tools/build_installer_payload_fr.py   # 组装安装包载荷 (BepInEx + 3 插件 + 词书/补丁/导入文件)
python tools/build_release_fr.py             # 打包两份音频 zip + release-manifest.json + 核心安装包 zip
python tools/test_installer_e2e_fr.py        # 沙箱端到端验收 (不触碰真实游戏与存档)
```

- 群友形态在 `output/installer_pkg/WCP法语词书安装包/`：`01_双击运行我.cmd`（唯一双击入口）+
  `使用说明.txt` + `support/`（脚本、`release-manifest.json`、`payload/`）。
- 发布件在 `output/release/`：`wcp-french-audio-words.zip`（8,116 词）与
  `wcp-french-audio-sentences.zip`（24,328 句）作为 GitHub Release 资产（tag `wcp-fr-resources-v1.0.0`），
  核心安装包 zip 走 `wcp-fr-v1.0.0`。
- 安装包**不内嵌大音频**：`Install-WCP-French.ps1` 按 `support/release-manifest.json` 下载两份音频并逐一
  SHA-256 校验。因此音频有改动时必须重跑 `build_release_fr.py` 并重新上传 Release 资产，否则群友会下载到过期资源。
- `tools/verify_all_fr.py` 会自动核对「发布清单 ↔ 音频 zip ↔ 安装包载荷」三者一致（未构建时跳过）。
- 日语项目遗留的兼容性修正已一并复刻：.ps1 打包时去除堆叠 BOM 并统一 CRLF；.cmd 去 BOM；
  音频 zip 含 `aux/nul/con` 保留设备名，解压与落位全程走 `\\?\` 扩展路径。

## 维护注意 (与日语项目相同)

- Steam 验证游戏完整性或游戏更新会还原 StreamingAssets 的 `.db` 文件。
  重跑 `python tools/patch_local_db_fr.py` 即可一键恢复灌库。
- 写 SaveFile.es3 的书名昵称需 wcp.exe 关闭; MyBook.es3 随时可写。
- 备份: 游戏库改前备份在本项目 `backups/`; MyBook/SaveFile 备份在
  `MyBook_backups/` 和 `SaveFile.es3.bak_*`。
- **改过 `mod_*/**.cs` 后必须重跑对应 `build.cmd`**: 源码在仓库里、DLL 不进版本库
  (`*.dll` 已 gitignore), 只改源码不重编译等于没改。三个插件的指纹算法共用
  `mod_book_name/BookProfiles.cs`, 该文件有 3 份副本 (`mod_fr_wordlist/` 供
  `tools/test_runtime_scope_fr.py` 编译), **必须逐字节一致**, `verify_all_fr.py`
  会校验这一点。
- 全量验收只需一条命令: `python tools/verify_all_fr.py` (含契约补检项, 退出码 0 = ALL PASS)。
