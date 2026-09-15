# WCP 日语词书项目 — 长期记忆

## 关键结论（跨会话必须记住）

- **四个词书槽位必须保持默认书名**「自定义词书一/二/三/四」。改名会切断
  `SelfBookMeaningDictionary` 内置释义字典的加载路径（精确匹配书名）。
  `rename_books.py` 的职责是**恢复默认名**，不是改名。
- **xlsx 导入绝对不能加表头行**。游戏 `LoadDataAndSaveFromExcel` 从第 0 行读，
  A 列=单词、B 列=释义。加表头 → 得到「表头当单词」的错误词书。
- **游戏释义/例句的真正来源是本地库**（`StreamingAssets/wcpFullEng.db` 的
  `pron` + `sentence2` 表），不是词书自带的字典。日文词必须用
  `patch_local_db.py` 灌进去，否则显示「本地暂未收录这个单词」。
  该脚本幂等（探针跳过），游戏无需重启（每次查词现开连接）。
- **sentence2 的合并入口是 `apply_sentences.py`**（读 work/gen_out_* +
  work/tr_out_* + logs/sentence_worklist.tsv → 产出
  `data/translations/sentences_master.json`，patch_local_db 读它灌库）。
  全量落库要 6+ 分钟，**必须后台 -u 跑**，前台 2min 超时会 SIGTERM
  （单事务未 commit 无损，重跑即可）。
- **2026-09-11 例句全覆盖已达成**: 15,812 词 × 3 条 + 全部中文翻译，
  DB 逐词全查通过。只有新增词才需要重走这条管线
  （build_sentence_jobs.py → gen_out 生产 → apply_sentences.py）。
- **项目最重要的文档是** `wcp_wordbooks/README.md`（含全部逆向契约）。
  接手任何工作前先读它。例句生产契约在 `work/AGENT_SPEC.md` +
  `work/PATCH_SPEC.md`。

## 架构基线（2026-09-14 实测，做任何重构前先读）

- **统一接入架构设计在** `D:/Japanese/ARCHITECTURE-UNIFIED.md`（Host / Pack /
  Strategy 三层，状态：设计稿未实施）。审计证据在 `wcp_wordbooks/AUDIT-2026-09-14.md`。
- **复刻成本是 fork 不是复用**（实测 diff）：词表插件复用率 11%、例句 21%、
  **书名插件 96%**。四语言 × 3 = 12 个 DLL ≈ 11,700 行，真实独立逻辑 <1,500 行。
- **五处共享资源**：`BepInEx/plugins/`、`LocalLow/WCP/vocabulary/`、
  `LocalLow/WCP/wcp/sentence_audio/`、`LocalLow/WCP/wcp/*.xlsx`、
  `StreamingAssets/wcpFullEng.db`。仅 `<lang>_db_payload/` 已按语言命名空间化。
- **单词音频策略三语言互不一致**（JA 用游戏 `vocabulary/`、FR 私有、RU 私有+回退）
  → 这是"未解耦"的硬证据。例句音频全共享，隔离靠提取器谓词互斥（逻辑巧合）。
- **`wcpFullEng.db` 是单文件单主键（`word`）**，多语言同写会跨语言覆盖
  （法语 1,638/8,116 与英语同形）。按语言分表不可行 → 正解是宿主自服务。
- **槽位硬上限 4**（`_slotProfiles[4]` + 硬编码「自定义词书一~四」）。
  **槽位占用的唯一权威是存档，不是目录** —— `MyBook.es3` 的 `SelfBookList1..4`。
  实测 2026-09-14：槽1=7922(ja) 槽2=8116(fr) 槽3=8451(ru) 槽4=空
  → **三语已共存，剩 1 槽**。
- **一个语言包可以含多个 xlsx 分册**：日语单册；法语/俄语各 3 册（A1A2+B1+B2），
  **`fingerprint_sha256` 是对全部分册并集去重后算的**（已复算验证）。
  `JLPT_N1..N5N4/IT用语` 是合并前源片段，不列入 books、不占槽。
- **`BookProfiles.cs` 跨项目不同步（真问题）**：JA 与 FR 项目的注册表都缺俄语条目
  （sha256 `a7f3dd58`，只有 ja/fr），RU 项目的齐全（`767adff6`，三条）。
  → 每加一种语言，其它语言项目的 3 个 DLL 都得重编译。项目内多份副本本身逐字节一致。
  JA 是单份共享（`build.cmd` 引 `..\mod_book_name\BookProfiles.cs`），FR/RU 各 3 份。
- **运行态是全局单例**（`allTestWordsS10_Para` / `S8needToLearnWordList_Para` /
  `exmplesentences`）→ 多语言只能资源共存、运行态串行；
  接管-还原协议（JP 的 v1.7.2/1.7.3）要提升为宿主级，ES3 键加 `<lang>_` 前缀。

## 阶段 0.5 已交付（2026-09-14）

- `packs/{ja,fr,ru}/manifest.json` — 语言包清单，字段值全部实测。
  schema 见 `ARCHITECTURE-UNIFIED.md` §2.2。
- `mod_host/` — 宿主骨架，**已编译通过**（`WcpHost.dll` 19,456 字节，未部署）：
  `Core/{Json,Manifest,ResourceRouter,ILanguageStrategy}.cs` + `GameAdapter.cs`
  + `Host.cs`(v0.1.0，只读：载注册表/按指纹认身份/fail-closed) + `build.cmd`。
- `tools/arch_check.py` — 设计文档 §5 验收的机检实现，退出码 0 = 无 FAIL。
  首次运行 2 FAIL = 注册表漂移；**每次改动后都跑它**。

### 不可让步的三条技术约定

1. **指纹算法一个字都不能改**：`SHA-256` over「`Trim().Normalize(FormC)` →
   `StringComparer.Ordinal` 排序 → `'\n'` 连接 → UTF-8」。改了则已导入词书全部失配。
2. **路由未激活时返回 `null`，绝不回退到别的语言**（RU 现有代码回退 `vocabulary/`
   是绕过隔离的缺陷，接入宿主时必须去掉）。
3. **编译只能用 PowerShell 工具跑 `build.cmd`**（Bash 拒 `csc.exe`）；
   骨架/开发阶段设 `WCP_NO_DEPLOY=1`，别动游戏安装。
- **跨语言复刻契约在 `D:/Japanese/IMPLEMENTATION.md`**（2026-09-14 重写过）。
  三条容易漏的：① 例句音频文件名 = `md5(ExtractJa 剥离结果)`，`ExtractJa` 有 8 步语义
  （含 `\n` 截断、**取最后一个 `（` 切尾**、必须含假名/汉字码点）；② `vocabulary/` 与
  `sentence_audio/` 是**多语言共享**目录，`<lang>_word_audio/`、`<lang>_db_payload/`、
  `<lang>mod_backups/` 是**每语言私有**；③ 拉丁语系与英语同形词多（法语 1,638/8,116），
  共享 `vocabulary/` 会让英/日词书串音 → 必须私有化 + 拦截 `PlayWordAudio`。
- ⚠️ **已知缺陷（未修）：日语侧 386 条例句音频「按钮在但点不响」**。
  根因：中文译文含全角括号 → `ExtractJa` 取最后一个 `（` 切尾 → 剥离结果 ≠ 原文 →
  md5 不匹配（mp3 文件其实存在）。386 条 = 译文含全角括号的全部集合。
  修复方向：例句契约加硬规则「**译文不得含全角括号/换行**」（法语侧已加），
  再重算这批例句的音频文件名。三处现有检查都不覆盖这条（gen_pipeline 只拦假名、
  verify_all 只数条数、音频生成只报写盘成功）。

## 目录约定

- 主战场：`D:/Japanese/wcp_wordbooks/`
- 脚本：`tools/`（45 个）；产物：`output/`（可由脚本重建，不入 git）
- 输入数据：`data/`；中间产物与生成作业：`work/`
- 外部数据源（JMDict/kanjidic2 等，不入 git）也在 `data/`

## 环境

- Python 优先用托管版：
  `C:/Users/hanserdesu/.workbuddy/binaries/python/versions/3.13.12/python.exe`
- 脚本均带 `sys.stdout.reconfigure(encoding='utf-8')`，Windows 控制台中文正常
- 会话级坑（2026-09-11 实测）：PowerShell stdout 捕获可能整个坏掉（连 echo 都
  空）→ 只用 bash；bash PATH 缺 coreutils（ls/head/dirname 挂），需要时先
  `export PATH="/c/Users/hanserdesu/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH"`
- 坑（2026-09-14 新增）：① **同一文件的多个 Edit 并行发会写竞争丢改动**（5 落 2）
  → 同文件编辑必须串行；② **新编译未签名 exe 首跑被杀软拖 ~4 分钟且短暂锁
  exe 文件**（上次的"文件锁"就是它）→ 编译产物放 `%TEMP%`，耐心等首扫；
  ③ cmd 里写中文 rem 会因 ANSI 读取碎成乱码命令 → build.cmd 只用 ASCII。

## 工作方式约定

- 生成类任务：写完 **立即** 跑校验（如 `gen_pipeline.py check-one NN Y`），
  不批量攒完再验。
- 并行子代理的 PASS 自述**不算数**，每波结束主会话自己跑 summary 复核；
  子代理偶发重复实例/越界做批次，靠 check_slice 统一收口，无损。
- 不声称跑过的检查没跑过；无法复现的通道要明说「无法复现」，不编造。
