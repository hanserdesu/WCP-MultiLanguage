# WCP 多语言词书扩展 —— 可复刻实现文档

> **目标读者**：把同一套实现复刻到新语言（韩语/法语/西语/俄语/…）的开发者或智能体。
> **写作口径**：以日语实现为工作样本，把「游戏机制契约」（语言无关）与「语言相关适配点」分开写。
> **上一手逆向记录**：`wcp_wordbooks/README.md`。
> **生产契约**：`wcp_wordbooks/work/AGENT_SPEC.md`（例句）、`PATCH_SPEC.md`（补丁）、`GRAMMAR_SPEC.md`（语法）。
>
> **证据等级约定**（本文所有结论必须可归因，读的人要知道哪些是实测、哪些是推断）：
> - `[实测]` 本次或历史会话在本机跑过、有输出可复算；
> - `[源码]` 直接读到了实现代码/文件内容；
> - `[推断]` 由前两者推出，未独立验证；
> - `[会话]` 来自历史会话记录，本机无法复现。
>
> **2026-09-14 修订说明**：本次按「交付给新语言能否完美复刻」的标准逐条核对文档与磁盘，
> 修正 6 处与实现不符的表述、补齐 4 个缺失章节（新项目骨架 / 多语言共存目录规约 /
> 契约→可执行检查映射 / 支线流水线），并把 §9 的验收数字换成实测值 + 可复算命令。
> 核对过程与发现记录在 `wcp_wordbooks/AUDIT-2026-09-14.md`。

---

## 0. 总体架构：一条数据流水线 + 三个运行时插件 + 两种交付形态

```
数据源 (CSV/XML/JSON)
        │
        ▼
 [阶段1] 词书构建 build_books.py / build_topic_books.py / extract_themed.py
        │     build_kanji_book.py / setb_build.py / build_grammar_book.py
        ▼
 [阶段2] 释义分层翻译（LLM 精翻 → 社区汉化 → 机翻兜底）
        │
        ▼
 [阶段3] 质量校验（读音 / 字符白名单 / 去重）
        │
        ▼
 [阶段4] 例句生产（子代理批量契约 + 逐批校验）  ──┐
        │                                        │
        ▼                                        ▼
 [阶段5] 音频生成（edge-tts, manifest 断点续传）  output/*.json（各语言统一中间格式）
        │
        ▼
 [阶段6] 交付落库 + 发布打包
        │
        ├───────────────◄───────────────┐
        ▼                               ▼
【形态 A：本机开发直连】          【形态 B：普通玩家一键安装包】
• patch_local_db.py 幂等灌库      • 01_双击运行我.cmd → support\run-installer.ps1
• write_catbar_combined.py 写槽位 • Install-WCP-Japanese.ps1（989 行）
• rename_books.py 写署名昵称      • WcpEs3Helper（C# 内存编译）：保型改 ES3、防元数据丢失
• make_import_files*.py 出导入件  • payload：catbar_book.json / books / plugins /
                                  •   bepinex / jp_db_payload / additions.db / manifest.json
                                  • 音频不在主包：运行时优先从 Gitee 分卷、回退 GitHub 下载（约 2.4 GB）
        │                               │
        └───────────────┬───────────────┘
                        ▼
          游戏运行时（Unity 2020.3 + BepInEx 5.4.23.5）
 ┌──────────────────────┼──────────────────────┐
 ▼                      ▼                      ▼
BookProfiles.cs +      SentenceAudioMod       JpWordListMod (v1.7.6)
BookNameMod            • 0.3s 反射扫描 exmplesentences
• SHA-256 词集指纹       + Harmony 前缀补丁（JpReadTag）
  识别（解耦槽位）      • sentence_audio\<md5(ja)>.mp3
• 选书回读拦截           • 作用域 Fail-Closed
  （SonBookChoose 前后  • 游戏更新导致类型变化 → 自动降级
  临时还原槽位名）                                    • 词书绝对隔离 + 跨词书启动基线还原 (JpWL_*)
                                                      • 假名题干 + 汉字/中文释义选项出题改造
                                                      • 全小游戏发音假名换回汉字取音（防回退英文 TTS）
                                                      • 官方更新覆写 StreamingAssets 后的离线自愈
```

**核心认知（决定项目成败的一条）**：词书文件本身只决定「学哪些词」。
游戏里**查词释义和例句的真正数据源是本地库** `wcpFullEng.db`（原库只有英语）。
只做词书不做灌库 → 游戏内每个词显示「本地暂未收录这个单词」、例句栏空白。
而官方更新会重置本地库，所以必须有运行时离线自愈机制（`jp_db_payload`）形成闭环。

**复刻成功的定义（三条同时成立才算复刻成功）**：
1. `patch_local_db` 之后，词表里**每一个词**在游戏内查词界面都能显示目标语言释义 + 读音 + ≥3 条例句；
2. 单词发音音频与例句朗读音频**都能被点响**（不是"文件存在"，是"按插件算法算出的文件名能命中"）；
3. 切回官方英语词书后，游戏行为与装插件前完全一致（无残留队列、无被点亮的图标、无被改写的 UI 文本）。

---

## 1. 目标项目骨架（复刻第一步：先铺对目录）

`D:/Japanese` 是**基准项目但布局特殊**：数据管线在 `wcp_wordbooks/tools/`，插件在根目录 `mod_*/`。
同构兄弟项目（`D:/French`、`D:/German`、`D:/Russian`）已统一为**更扁平、更好复刻**的布局，
**新语言请照这个铺**（`D:/French` 为已验证样本 `[实测]`）：

```
D:/<Lang>/
├─ tools/                  ← 全部 Python 脚本 + 该语言的共享常量模块（如 fr_audio_paths.py）
├─ data/                   ← 词源（CSV/XML/JSON，不进 git）+ translations/ + grammar/
├─ output/                 ← 产物（可由脚本重建，不进 git）：<lang>_books.json、import/、
│                             installer_pkg/、release/、<lang>_db_payload/
├─ work/                   ← 生成作业与中间产物：gen_words_NN.json、gen_out_NN_Y.json、
│                             *_SPEC.md（生产契约）
├─ logs/                   ← 进度、worklist、审计日记
├─ backups/                ← 数据库备份（按库文件绝对路径 SHA1 前 6 位做 tag）
├─ mod_book_name/          ← BookProfiles.cs（唯一正本，被所有插件共享编译）+ BookNameMod.cs + build.cmd
├─ mod_<lang>_wordlist/    ← 词书行为插件 + build.cmd
├─ mod_sentence_audio_<lang>/ ← 例句播放插件 + build.cmd
└─ installer/              ← Install-WCP-<Lang>.ps1 等安装器模板
```

**三条硬约束**：
1. **每个脚本的 `ROOT` 必须只解析一次且层数正确**。`Path(__file__).resolve().parent.parent`
   放到 `tools/deprecated/` 下就会解析到错误层，脚本将**从未成功跑过一次**且静默返回。
   `[实测]` 法语项目踩过：`tools/deprecated/isolate_word_audio_fr.py` 一直在找 `tools/output/…`。
2. **同一个路径常量只允许有一个定义处**。生成端、校验端、插件端必须 import 同一个模块
   （如 `tools/audio_paths_<lang>.py`）。`[实测]` 法语项目的教训：生成脚本写 `vocabulary/`、
   插件读 `<lang>_word_audio/`，两边各自硬编码，装完一个词都不响。
3. **`.cmd` / `.ps1` 含非 ASCII 一律存 UTF-8 with BOM**（见 §7.3）。

---

## 2. 游戏机制契约（逆向结论，语言无关，复刻必读）

全部逆向自 `Assembly-CSharp.dll`（工具 `tools/ildump.py` / ILSpy）。

### 2.1 自定义词书槽位（MyBook.es3）

| 项 | 值 |
|---|---|
| 文件 | `%USERPROFILE%\AppData\LocalLow\WCP\wcp\MyBook.es3` |
| 格式 | Easy Save 3 JSON，带 `__type` 类型包装 |
| 顶层键 | **8 个**：`SelfBookList1..4`（string[] 词表）+ `wordDictionary1..4`（词→释义） |

ES3 的类型包装字符串（写文件必须精确匹配，游戏靠它反序列化）：

```json
{
  "SelfBookList1": {
    "__type": "System.String[],mscorlib",
    "value": ["単語1", "単語2", "..."]
  },
  "wordDictionary1": {
    "__type": "System.Collections.Generic.Dictionary`2[[System.String, mscorlib, Version=4.0.0.0, Culture=neutral, PublicKeyToken=b77a5c561934e089],[System.String, mscorlib, Version=4.0.0.0, Culture=neutral, PublicKeyToken=b77a5c561934e089]],mscorlib",
    "value": {"単語1": "【かな】释义〈词性〉"}
  }
}
```

写入工具：
- 本机开发：`tools/write_mybook.py` 或 `tools/write_catbar_combined.py`（写前自动备份，支持 `--dry-run`）。
- 玩家安装包：安装器内置 C# `WcpEs3Helper`（PowerShell `Add-Type` 内存编译）。

> **验收断言**（新语言必须实现）：`json.loads(MyBook.es3)` 后，每个顶层键都必须带 `__type`。
> `[实测]` 法语项目最初 `verify_all_fr.py` 完全没检查这条，本次复查补上。
> `[实测]` 本机 1.9 MB 的 `MyBook.es3` 顶层键带 `__type` 校验通过。

⚠️ **ES3 序列化致命坑**：PowerShell 原生 `ConvertTo-Json` 会剥除或展平对象的类型元数据
（丢掉深层 `__type`），导致游戏读档时反序列化失败，甚至将含 150+ 字段的 `SaveFile.es3`
破坏成缩水残卷，导致开局剧情（`Initial_PlotDone`）重置、全成就与货币清空。
**绝对禁止用简单 JSON 库直接回写 ES3 文件。**
正确做法有两种，都要保留：
- **保型文本改写**（推荐，法语项目采用 `[实测]`）：定位到值所在文本切片替换，不重新序列化，
  写前二次比对文件未被改动、原子替换、保留 BOM；
- **完整类型保持的定制序列化器**（日语安装器采用的 `WcpEs3Helper`，C# AST 级解析）。

### 2.2 书名约束与选书回读拦截（核心深坑）

- 书单显示名 = `"自定义词书N（" + SelfBookNameN + ")"`，括号内是**昵称/署名位**
  （存 `SaveFile.es3` 的 `SelfBookName1..4`）。
- **决定「词书内置释义字典是否加载」的是槽位身份**：选书状态 `ChosenBook_Para` 必须是
  规范槽位名 `自定义词书一~四`。游戏内改名 UI（`SaveSourceType.setBookName`）只写
  `SelfBookNameN`，**不碰 `ChosenBook_Para`**，所以改昵称安全。
- ⚠️ **选书回读深坑（为什么改按钮文字会崩游戏）**：
  `WordChooseButtonS10.SonBookChoose(int)` 在点击选书时会**反向读取按钮标签的文字**，
  取第一个 `（` 之前的部分赋给 `tem_ChosenBook`，再写入 `ChosenBook_Para`。
  如果直接把按钮文本改成「日语词库(猫条版)」，选书方法读到「日语词库(猫条版)》」，
  与 `自定义词书N` 校验不匹配 → 选书彻底失效、后续测试词表无法生成。
- **优雅解法（BookNameMod 的 Prefix/Postfix 拦截）**：
  `SonBookChoose` 执行前（Prefix）把标签临时换回 `自定义词书N`，执行后（Postfix）
  恢复为显示名。玩家看到的是美观名字，游戏底层读到的永远是规范槽位名。
- ⚠️ **`BookProfiles.cs` 必须逐字节单一正本**。危险组合是「测试编译副本 A、发货编译正本 B」
  —— 漂移 = 指纹失效 = 插件静默全失效。`[实测]` 法语项目三副本曾仅注释不同，已被强制一致化。
  校验方式：三份（或全部副本）逐字节 SHA-256 相同。

### 2.3 全局词书指纹识别（BookProfiles.cs）

插件不把逻辑写死在特定槽位，而是提取词书全部词条的 **FormC 规范化文本**，
**按序数排序**后拼接（每词后接 `\n`）计算 SHA-256 指纹。
无论词书在槽位 1/2/3/4，只要指纹匹配，插件即识别其所属语言与档案。

```csharp
internal static readonly BookProfile[] All = new BookProfile[]
{
    new BookProfile("catbar-jlpt-complete", BookProfiles.Japanese, "日语词库(猫条版)", 7922,
        "6d7a51c0c5d30dd63d8a6e3412bce1cf2419554fb8487cf5c8a205e43ac41663"),
    // 新语言扩展示例；Language 用 BookProfiles 里已登记的常量字符串，不要新造枚举
    // new BookProfile("french-vocab-core", BookProfiles.French, "法语基础词库", 5000,
    //     "<按词条 FormC 排序后算出的 SHA-256>")
};
```

> **指纹三方一致性**是可执行断言：`MyBook.es3` 槽位真实词表、`BookProfiles.cs` 常量、
> `<lang>_book.json` 里的 `fingerprint_sha256` 必须三者相同。
> `[实测]` 法语侧用 Python 复刻 `FingerprintOf`（Trim + FormC + 序数排序 + 每词后接 `\n`）
> 算出三方同为 `376af2eae029…`，与 C# 端测试互补，且不需要 csc 就能复核。

### 2.4 游戏内导入通道（SaveSourceType 逆向）

**Excel 导入**（`LoadDataAndSaveFromExcel`, NPOI）：
- 读第一个 sheet，**从第 0 行开始**，只读 **A 列=单词、B 列=释义**（游戏内显示文本）。
- C 列以后忽略，可放读音/例句等人工参考信息。
- ⚠️ **绝对不能加表头行** —— 加了表头，第一行「单词/释义」两个字符串会被当成词条收进词书。
`[实测]` 本项目出过事故（旧版 xlsx 有表头且 B 列=读音 → 导入出「读音当释义」的废词书）。
**可执行断言**：`openpyxl` 读第 1 行，断言 A1 **是词表里的真词**（不是「单词/Word」之类的表头）。

**外接词库**（`testConnect`/`StartSaveDataBase`）：
- 文件放 `%USERPROFILE%\AppData\LocalLow\WCP\wcp\`（persistentDataPath），游戏内输文件名。
- `.db` 走 `SELECT <词列>,<释义列> FROM <表>`，默认兼容 `pron(word, meaning)` 表。
- `.xls/.xlsx` 也从这个目录读取。

### 2.5 本地词库（查词释义/例句的真正数据源）

| 文件 | 用途 | 涉及表 |
|---|---|---|
| `wcp_Data/StreamingAssets/wcpFullEng.db` | 每日学习 + 词典查询（DatabaseManagerS8/S17） | `pron`、`sentence2`、`help` |
| `wcp_Data/StreamingAssets/wcpOnlyWord.db` | 其他查词界面 | **仅 `pron`**（无 `sentence2` 表） |

**表结构（`[实测]` 直接读 `sqlite_master`，两表都没有主键、没有唯一约束、没有索引）**：

```sql
CREATE TABLE pron (word, ukPhonic, usPhonic, meaning);
CREATE TABLE sentence2 (word, sentences);
```

> 这条结构事实决定了灌库只能用 **`DELETE WHERE word IN (…)` 再 `INSERT`** 的幂等方式，
> 不能用 `UPDATE … WHERE rowid=?`（见 §7.4.1 的 10,251 词写串事故）。

写入格式（`tools/patch_local_db.py`）：
```
pron:      (word, ukPhonic='[かな]', usPhonic='', meaning=游戏显示释义)
sentence2: (word, '例句：日本語。（中文翻译）')      -- 一条一条 INSERT，每词 3+ 行
```
`[实测]` 本机真实样本：
```
pron      ('全部', '[ぜんぶ]', '', '【ぜんぶ】全部；所有〈名〉')
sentence2 ('全部', '例句：それで全部？（就这些了吗？）')
```

- 例句字符串格式必须对齐原库：**前缀 `例句：` + 目标语原文 + `（中文翻译）`**，
  播放 Mod 靠剥离这个前缀+尾巴提取原文，见 §2.6。
- **灌库幂等**：探针词（日语用 低い/貶す/見積もり）释义全命中则跳过；`--force` 强制。
- **写前备份**：按「库文件绝对路径」SHA1 前 6 位做 tag（多副本安装互不覆盖），备份在项目 `backups/`。
- **游戏无需重启**：游戏每次查词现开数据库连接，灌完下一个词立即生效。

⚠️ **Steam 更新覆写问题与运行时离线自愈（核心落地保障）**：
Steam「验证游戏完整性」或官方补丁会把 `StreamingAssets` 下的 `.db` 还原回纯英文官方库。
- **开发环境**：重跑 `patch_local_db.py` + `build_grammar_book.py --patch`。
- **玩家环境**：`export_jp_db_payload.py` 把已灌好的目标语言数据导出为 TSV 补丁包
  （`jp_pron.tsv`、`jp_sentences.tsv`、`jp_only_pron.tsv` + `manifest.json`），
  随安装器置于**不受 Steam 更新影响**的 `%USERPROFILE%\AppData\LocalLow\WCP\wcp\jp_db_payload/`。
  `JpWordListMod`（v1.7.6+）后台探测探针词，检测到被覆写即静默重灌，
  写前把当前 DB 备份到 `jp_db_payload\backup`。
- **验收断言**：补丁包**五件套 + manifest 齐全**（`[实测]` 法语侧的对应检查项即照此写）。

### 2.6 音频查找契约与两大避坑点

**单词音频**：游戏在 `%USERPROFILE%\AppData\LocalLow\WCP\vocabulary` 找
`<单词文本>.mp3` / `.wav`，找不到才回退内置 AI（英语向）TTS。
⚠️ 这个目录是**所有语言共享**的 —— 拉丁语系语言必须改走私有目录，见 §3.2。

⚠️ **避坑点 1：Windows 保留设备名（CON, PRN, AUX, NUL, COM1..9, LPT1..9）**
- 词表里罗马音或缩写刚好与保留设备名重合的词（如 `aux`、`nul`）无法用常规接口写盘。
- **解法**：解压工具与安装器文件拷贝时，对这类文件名统一加 `\\?\` 扩展路径前缀
  （见安装器 `Copy-TreeNet` 与 `ExtendedPathIfNeeded`），并用底层 .NET `FileStream` 写入。
- **验收断言**：词表里 `con/prn/aux/nul/com1/lpt1` 开头的词，音频必须真实落地。

⚠️ **避坑点 2：假名出题与发音查词冲突（全小游戏假名换回汉字取音）**
- Mod 把题干改造为假名读音（如「ぜんぶ」），但磁盘上音频是按汉字词形命名的（`全部.mp3`）。
- 点击发音喇叭时，原版 `VocabularyAudioPlayer` 会拿题干文字去搜 `ぜんぶ.mp3` → 落空，
  错误回退到官方内置英文 AI TTS 朗读假名。
- **解法**：`JpWordListMod`（v1.7.5+）对 `VocabularyAudioPlayer.PlayWordAudio` 实施运行时拦截，
  发音前把假名临时映射回汉字形（`ぜんぶ` → `全部`），调用原生发音后还原。
  覆盖 Scene7 战斗机、Scene8 每日复习、Scene9 选词、Scene13 水果忍者、Scene15 棒球、
  Scene16 自由复习、Scene17 拼写等全部小游戏场景。

**例句音频**：`%USERPROFILE%\AppData\LocalLow\WCP\wcp\sentence_audio\<md5(ja)>.mp3`

文件名 = `md5(剥离后的纯目标语言句)` 的小写 hex。**两端必须逐字节一致**，任何一端改动都失效。

> ⚠️ **这里是最容易静默失效的地方，必须按完整语义复刻，不能只看「md5(ja)」四个字。**

`ExtractJa` 的**完整语义**（`[源码]` `mod_sentence_audio/SentenceAudioMod.cs:840`，逐条照抄）：
1. 空串 → `null`；
2. 正则删掉全部 `<...>` TMP 标记；
3. 删掉所有出现的 `例句：` 子串，然后 `Trim()`；
4. 空 → `null`；
5. 取第一个 `\n` 之前的内容并 `Trim()`（**换行会被截断**）；
6. 若以全角 `）` 结尾：找**最后一个** `（`，砍到它之前并 `Trim()`（**注意是最后一个，不是第一个**）；
7. 长度 < 2 → `null`；
8. **必须含至少一个 UTF-16 码点落在 `0x3040-0x30FF`（假名）或 `0x4E00-0x9FFF`（汉字）**，
   否则返回 `null` —— 这一步同时是「是否给这条例句挂 ▶ 按钮」的门。

⚠️⚠️ **真实事故（本次复查发现并量化，日语侧当前仍存在）**：
第 6 步取的是**最后一个** `（`。如果**中文译文自身含全角括号**，数据库字符串变成
`例句：うちの旦那。（我家的那位（丈夫）。）`，剥离结果是 `うちの旦那。（我家的那位`，
与原文 `うちの旦那。` 不等 → md5 不匹配 → **▶ 按钮在，点了没声音**。
- `[实测]` 复刻 `ExtractJa` 对 `sentences_master.json` 全量 57,687 条跑一遍：
  **386 条**命中此缺陷，且这 386 条正是「中文译文含全角 `（`/`）`」的全部集合，
  对应 mp3 文件在磁盘上都存在（永远查不到）。
- **根因**：日语侧的生产校验（`gen_pipeline.py` 第 4 条只拦「译文含目标语言假名」）
  **没有禁止中文译文含全角括号**。法语侧已在 `gen_pipeline_fr.py` 里加了这条禁令，
  等于无意中保护了契约 `[实测]`。
- **新语言必须做的两件事**：
  ① 例句契约里加硬规则「**译文不得含全角括号/换行**」，机检拦住；
  ② 写一条端到端断言：**在 Python 里 1:1 复刻插件的剥离函数**，对全部例句生成
  `例句：{原文}（{译文}）` → 剥离 → 断章 `== 原文`，并断言 `md5(剥离结果).mp3` **存在**。

**播放 Mod 的真实形态（文档旧版描述有误，此处更正）**：
- 启动**双通道**：① 每 `0.3s` 反射扫描 `exmplesentences` 文本挂 ▶ 按钮；
  ② **有 Harmony 前缀补丁**（`new Harmony("dev.hanserdesu.sentaudio").Patch(m, new HarmonyMethod(prefix))`），
  用一个 `JpReadTag` 标签做最后一道作用域检查。
  旧版文档写「不做 Harmony 补丁」是上一个版本的状态，**与当前源码不符** `[源码]`。
- 文档旧版「不 Harmony → 游戏更新可自动降级」的说法仍部分成立（反射扫描路径在类型变化时不显示按钮），
  但不能据此删掉 Harmony 补丁。
- 作用域严格 Fail-Closed：启动与每轮刷新均校验「当前内存词表 + 当前槽位 + 存档书名」三者的
  Profile 一致匹配，任何不一致即不挂载按钮，绝不干扰官方英语词书。
- `[实测]` 法语版每轮刷新读 `MyBook.es3` 1.13 MB + 存档书名 + 两份 `BookProfiles.Match`
  约 10–13 ms；这是**有意取舍**（缓存会削弱「同引用同长度但内容被改写必须被拒」的断言），
  不要为了省这点开销去加缓存。

### 2.7 游戏目录解析与多盘符容错

本机曾存在两份游戏副本，早期工具硬编码了没在跑的那份导致白灌。
`tools/wcp_paths.py` 统一解析：

```
WCP_GAME_DIR 环境变量 → 注册表 HKCU\Software\Valve\Steam (SteamPath/InstallPath)
  → 各库 libraryfolders.vdf 的 "path" → 已知候选目录
只认「存在 wcp_Data/StreamingAssets/wcpFullEng.db」的那份。
真身验证：%USERPROFILE%\AppData\LocalLow\WCP\wcp\Player.log 第一行 Mono path。
```

`[实测]` 本机 `wcp_paths.game_dir()` 返回 `E:\Steam\steamapps\common\WCP-WordGirlgriend`。

**必须统一改用它写库/校验的脚本清单**（`[源码]` README 2026-09-12 修正记录）：
`patch_local_db` / `apply_sentences` / `apply_readings` / `verify_all` /
`build_grammar_book` / `export_sentences` / `ildump`。
`patch_local_db.backup()` 也按库文件绝对路径加 tag，多副本互不覆盖。

- **安装器容错**：遍历 Steam 库目录时自动跳过注册表里已不存在或被拔除的盘符，
  防止无效路径抛错中断安装；存在多个有效副本时提供交互选择。

---

## 3. 运行时目录规约与多语言共存（**新语言必读，旧版文档完全缺失**）

`%USERPROFILE%\AppData\LocalLow\WCP\` 是**所有语言、所有插件共用**的目录。
`[实测]` 本机现状（三种语言共存）：

```
LocalLow\WCP\
├─ vocabulary\                    ← 共享：单词音频（日语、英语都用这里）
└─ wcp\                           ← persistentDataPath
   ├─ MyBook.es3 / SaveFile.es3   ← 游戏存档（共享，且语言互斥，见 3.3）
   ├─ sentence_audio\             ← 共享：例句音频（md5 命名，跨语言天然不冲突）
   ├─ fr_word_audio\              ← 法语私有：单词音频
   ├─ jp_db_payload\  fr_db_payload\  ru_db_payload\   ← 每语言私有的离线自愈包
   ├─ jpmod_backups\  rumod_backups\                  ← 每语言私有的安装备份
   └─ jpmod_downloads\            ← 安装器下载缓存
```

`jpmod_downloads` 不按安装时间戳重建，完整资源、Gitee 已完成分片和未完成的 `.download` 文件都会跨运行保留；
`jpmod_audio_stage_<stamp>_<guid>` 则是一次安装专用的解压临时目录，解压中断后可以重新创建，不承担下载续传职责。

**规约（新语言必须遵守）**：

| 资源 | 命名规约 | 为什么 |
|---|---|---|
| 例句音频 | **共享** `wcp\sentence_audio\<md5(原文)>.mp3` | 文件名是目标语言原文的 md5，跨语言不可能撞名，无需隔离 |
| 单词音频 | 共享 `LocalLow\WCP\vocabulary\<词>.mp3` | 这是**游戏原生查找路径**，直连方案最省事 —— 但仅当词形不与英语原库冲突时才安全，见 3.2 |
| 单词音频（冲突时） | 私有 `wcp\<lang>_word_audio\<词>.mp3` + 插件拦截播放 | 隔离冲突词形 |
| 离线自愈包 | 私有 `wcp\<lang>_db_payload\` | 每语言探针词/格式不同，共享会互相覆盖 |
| 安装备份 | 私有 `wcp\<lang>mod_backups\<stamp>\` | 同上 |

### 3.1 为什么共享 `sentence_audio` 是安全的

文件名 = `md5(纯目标语言句)`。日语与法语、俄语的原文不同 → md5 不同 → 天然隔离，
且不会与英语原库冲突（原库没有句子音频机制）。
`[实测]` 本机 `sentence_audio\` 共 82,486 个 mp3，日语主表只占 56,661 个唯一 md5。

### 3.2 ⚠️ 拉丁语系语言必须把单词音频私有化（法语实证）

`vocabulary\` 是游戏原生查找路径，**但它被所有语言共享**。
法语 8,116 词中有 **1,638 个与英语原库同形**（`[实测]` 法语项目 verify 断言）。
若法语发音直接写进 `vocabulary\`：
- 玩家切到**英语或日语**词书时，这些同形词会播放**法语发音**；
- 安装器还会覆盖/污染其它语言的声音文件。

**法语的解法**（新语言若属拉丁/西里尔等与英语同形率高的语系，必须照做）：
1. 单词音频一律写私有 `LocalLow\WCP\wcp\<lang>_word_audio\<词>.mp3`；
2. 插件拦截 `VocabularyAudioPlayer.PlayWordAudio`，在受管词书内改从私有目录取音；
3. 装完后**断言共享 `vocabulary\` 里零本语言残留**（可执行检查，见 §8）。

> 这是一条**与 §2.6「游戏在 vocabulary 找音频」的有意分歧**。
> 复刻文档旧版没写这条分歧，照字面复刻会做出「英/日/法互相串音」的系统。
> 判定规则：先算「本语言词表 ∩ 英语原库词表」的同形率，
> 为 0 或极低（如日语汉字/假名词形）→ 可用共享目录；显著非零 → 必须私有化。

### 3.3 跨语言切换与状态隔离

游戏**只有一个存档**（`MyBook.es3` / `SaveFile.es3`），四种语言共用四个槽位。
因此"同时装两种语言"= 抢槽位。必须处理的状态污染：

- **`JpWL_*` 基线还原**：`JpWordListMod` 每次改写题干队列前，在 ES3 记录原始基线；
  一旦检测到当前**不是**日语词书，立即安全还原基线。
  （玩家在日语词书中途关游戏，下次进英语官方词书，英语书就会崩溃。）
- **`_lastVoiceLabel` 字符串比较而非 bool**：法语版把「是否日语书」的 bool 换成
  「当前发音标签字符串」比较，于是**日→法、法→日跨语言切换也能正确还原** UI；日语版漏了这条。
- **归一化书名的比较**：作用域校验要比对「内存词表 Profile == 槽位词表 Profile == 存档记录」，
  三者同 Id 才接管，任一不一致直接拒绝（Fail-Closed）。

---

## 4. 数据流水线（六阶段 + 五条支线）

### 阶段 1：词源获取与构建

主词源用结构化公开数据。`[实测]` 日语实际使用：
OpenJLPT CSV（N5–N1）+ Kaishi 1.5k（中文条目）+ Bluskyo（读音交叉验证）；
主题书用 JMDict 3.6.2 的 `field`/`misc` 标签提取；常用汉字用 `kanjidic2.xml`。

统一中间格式 `output/<lang>_books.json`，每条含
`{word, reading, meaning_en, example_ja, example_en, level, meaning_zh, meaning, zh_source, pos_zh}`。

**提取过滤**（`extract_themed.py` 的经验）：剔罕用词形标记（`rK/uK/iK`）、转义词、
与主词书重复项；**读音必须匹配所选词形**。

**便携合并单册**：`build_installer_payload.py` / `write_catbar_combined.py` 把 N5～N1
按顺序合并去重为 7922 词单册，输出标准化 `catbar_book.json`（见附录 B）。

### 阶段 2：释义分层翻译（质量分层优先级）

```
1. LLM 精翻（data/translations/zh_llm_*.json 批次文件，最高优先级）
2. 社区汉化数据（Kaishi zh-CN 等目标语资源）
3. 机翻兜底（Google gtx 端点，断点续传 → gtx_zh.json）
```

- 合并 `merge_translations.py`：低优先级在前、高优先级在后覆盖；键先经 `fix_word` 清洗迁移。
- **翻译文件即保留清单**：未翻译的词自动被过滤（剔除冷僻词的手段）。
- 显示格式契约：`汉字词 → 【假名】中文〈词性〉`；无汉字词直接 `中文`。
  新语言设计等价格式（音标/罗马音 + 目标语释义 + 词性）。

### 阶段 3：质量校验

- **读音校验**（`setb_check_readings.py` / `themed_check_readings.py`）：
  kanjidic2 音训读分解校验，容忍促音/连浊/送假名/約音/転呼/熟字訓。
  新语言换等价规则（韩语汉字音、法语联诵…）——校验目标是「读音与词形自洽」。
- **字符白名单**（`validate_themed.py`）：ja 每字符必须在 JMDict 日语用字白名单内，
  专拦**简体字混入日文**（选→選、气→気），也拦例句里的整词英文漂移。
  新语言建自己的字符白名单。
- 去重：全部词书合并后对主词书去重（`高级词汇` 即按此规则产生）。
- 全量复核 `verify_all.py`（检查项见 §8）。

### 阶段 4：例句生产（子代理批量契约 —— 本项目最成熟的方法论）

规模 `[实测]`：15,812 词 × 3 条（实际 57,687 条）+ 全部中文翻译。

流程：
1. `build_sentence_jobs.py` 切块：词块 `work/gen_words_NN.json`（每块 100 词）+ 翻译块 `tr_chunk_XX`。
2. 每个子代理拿一份**契约文档**（`work/AGENT_SPEC.md` + `PATCH_SPEC.md`），
   产出 `work/gen_out_NN_Y.json`（词 → [{ja, zh} × 3]）。
3. **写完立即自检**：`tools/gen_pipeline.py check-one NN Y` → 必须 PASS。
   **不许谎报 PASS**（主会话每波结束自己跑 `summary` 复核，子代理自述不算数）。

**硬性校验规则**（`gen_pipeline.py` 逐条机检，可整体复用；第 9 条是本次新增）：
1. 每词恰好 3 条例句；
2. ja 以 `。`/`！`/`？` 结尾；
3. ja 每字符在目标语言字符白名单内（禁混入简体字/英文漂移）；
4. zh 为目标译文，**绝不含目标语言假名**（扫 `[\u3040-\u30ff]`）；
5. 同词多条 ja 不得重复；
6. **词形必须字面出现在例句中**（原形或去尾词干；活用词用 `〜ために/〜べきだ/〜ことができる`
   等能带出原形的接续）—— 最易 FAIL 的一条；
7. JSON 合法 UTF-8，`ensure_ascii=False`；
8. 质量红线（机检不到、契约里写死）：自然地道、三句不同场景/搭配/语体、长度 10–40 字、翻译通顺不硬译；
9. 🆕 **译文不得含全角括号 `（）` 与换行** —— 这是 §2.6 音频契约的兜底，缺了它会有
   「按钮在但点不响」的静默缺陷（日语侧现有 386 条）。

PATCH 模式：文件已存在但不足 3 条时只补差额，新 ja 不得与已有重复，
用 `gen_helper.py merge NN Y patch.json` 合并后再 `check-one`。

### 阶段 5：音频生成

- 引擎 edge-tts（日语 `ja-JP-NanamiNeural`；新语言换对应 voice）。
- `tools/gen_audio.py`（单词，并发 8）/ `gen_sentence_audio.py`（例句，并发 12）：
  - **manifest 断点续传**（按文件存在 + 大小阈值判完成），失败重试 3 次，
    `--limit N` 分批、`--retry-failed` 重试；
  - 多套词书用**独立 manifest**（`audio_manifest.json` / `_topic` / `_kanji` / `setb_audio_manifest.json`）；
  - 生成量大时挂后台循环工兵（`night_worker`/`auto_worker`，带锁防重入，
    进度写 `logs/progress.json`）。
- 例句音频命名规则见 §2.6（**含完整剥离语义**）；语法词书 927 条讲解例句复用同一规则。
- ⚠️ **"0 失败"≠ 契约正确**：生成器只检查文件写盘成功，不检查
  「按插件算法算出的 md5 能不能命中」。必须另跑 §8 的端到端断言。

### 阶段 6：交付落库与发布打包

1. **本地开发落库**：
   - `patch_local_db.py`：汇总全部 books.json（按优先级去重合并）→ 灌 `wcpFullEng.db` +
     `wcpOnlyWord.db` 的 `pron`/`sentence2`（幂等，见 §2.5）。
     ⚠️ **全量落库要 6+ 分钟，必须后台 `-u` 跑**，前台 2min 超时会被 SIGTERM
     （单事务未 commit 无损，重跑即可）。
   - `make_import_files.py` / `make_import_files_themed.py`：生成无表头 A词/B义 xlsx +
     外接词库 `.db`（`pron` 表 + 明细表）→ 复制到 persistentDataPath。
   - `write_catbar_combined.py` / `write_mybook.py`：安全写入槽位 `MyBook.es3`。
   - `rename_books.py`：写署名昵称（保持槽位身份不变，见 §2.2）。
2. **发布包构建**：
   - `export_jp_db_payload.py`：导出 `jp_db_payload/` 纯文本补丁包（见 §2.5）。
   - `build_installer_payload.py [--skip-audio]`：从本机提纯净 BepInEx 运行时、
     3 个 Mod DLL、词书文件、`catbar_book.json`、全部 `books/`、`additions.db`、`jp_db_payload/`，
     组装 `output/installer_pkg/WCP日语词书安装包/`（真实布局见 §5.2）。
   - `build_release.py [--reuse-audio]`：产出 Release 资产（主安装包 Zip + 单词音频 Zip +
     例句音频 Zip）+ SHA-256 账本 `release-manifest.json`。

### 支线流水线（旧版文档只在 §5 列了成果，没给命令，这里补齐）

| 支线 | 构建 → 翻译 → 校验 → 导入 → 音频 |
|---|---|
| **主题册（JMDict field/misc）** | `extract_themed.py` → `themed_gtx.py` / LLM 批次 `data/translations/zh_llm_themed_*.json` → `validate_themed.py` + `themed_check_readings.py` → `merge_themed.py` → `make_import_files_themed.py` → `gen_audio.py`（读 `themed_books.json`，共用 `audio_manifest.json`） |
| **专业册（IT/商务）** | `build_topic_books.py` → `merge_topic.py`（`--write-import`）→ `check_topic_keys.py` → `gen_audio_topic.py`（独立 manifest `audio_manifest_topic.json`） |
| **SetB（惯用句/拟声/四字熟语/高级/商务敬语）** | `setb_build.py` → `setb_check_readings.py` → `setb_final_check.py` → `setb_import.py` → `setb_audio.py`（独立 manifest `setb_audio_manifest.json`），工兵 `setb_worker.py` |
| **常用汉字（非词而字）** | `build_kanji_book.py` → `merge_kanji.py --audio`（`--audio` 生成音训朗读 MP3，文件名=汉字如 `愛.mp3`，内容读「アイ、いとしい」，避免单字 TTS 误读） |
| **语法路线** | `data/grammar/curriculum.json` → 分片 `work/gchunk_XX.json` + `GRAMMAR_SPEC.md` → `work/grammar_out_XX.json` → `data/grammar/content/gc_XX.json` → `check_grammar_content.py` → `build_grammar_book.py [--stages …] [--patch]` → `gen_grammar_audio.py` |

**语法路线机制**（新语言要复刻的话，这是最巧的一条）：
8,331 个 JLPT 词按学习路线重排（Kaishi 频率优先），每 15/16/25/30/40 词一个词块，
块后插入 1 个**语法占位词**（`G001…G304` + 5 个阶段头），
**语法讲解写在占位词的例句栏**（3 行 = 接续/用法/注意，原文是可朗读例句、中文讲解在括号内）。
5 阶段：一 入门N5(45 点) → 二 基础N4(40) → 三 进阶N3(72) → 四 上级N2(60) → 五 精通N1(87)。

---

## 5. 交付形态（两部分：开发者直连 / 玩家一键包）

### 5.1 形态 A：本机开发直连

`patch_local_db.py`（灌库）→ `write_catbar_combined.py`（写槽位）→ `rename_books.py`（署名）
→ `make_import_files*.py`（出导入件）→ 复制 xlsx/`.db` 与本地音频到 persistentDataPath / `vocabulary`。

### 5.2 形态 B：玩家一键安装包（真实布局）

`[实测]` `output/installer_pkg/WCP日语词书安装包/` 的实际结构（旧版文档只提了其中三项）：

```
WCP日语词书安装包/                          ← 用户只解压这一层
├─ 01_双击运行我.cmd                        ← 唯一入口（用户不该进 support/）
├─ 使用说明.txt
└─ support/
   ├─ run-installer.ps1                     ← .cmd 实际调用的入口
   ├─ Install-WCP-Japanese.ps1              ← 989 行主逻辑
   ├─ check-compatibility.ps1               ← 运行环境探测
   ├─ compatibility-help.cmd                ← 不满足条件时的人工指引
   ├─ release-manifest.json                 ← 音频资产的下载地址 + SHA-256 账本
   └─ payload/
      ├─ manifest.json                      ← 载荷清单（pron 数 / 语法行数 / 插件列表 / size）
      ├─ bepinex/  (BepInEx\core + root)    ← BepInEx 5.4.23.5 运行时（用户没装则自动装）
      ├─ plugins/  (3 个 .dll)              ← 本项目插件；已有 BepInEx 的用户只补插件
      ├─ books/    (xlsx ×6 + db ×6)        ← 无表头导入件 + 外接词库
      ├─ catbar_book.json                   ← 7922 词单册
      ├─ additions.db                       ← 增量词库
      ├─ jp_db_payload/                     ← 离线自愈包（见 §2.5）
      └─ audio/                             ← **默认为空**：音频走远程下载
```

**入口 `.cmd` 的真实行为**（旧版文档完全没写，复刻时必须照做）：
1. 若不带 `--keep-open` 参数，先 `cmd.exe /d /k call "%~f0" --keep-open` 再退出
   —— **先建立一个持续保留的 CMD 会话**，这样任何后续异常都不会"闪退看不到日志"
   （§7.3 的闪退坑就是这样解决的）；
2. 写启动日志 `installer-startup.log`；
3. 探测 PowerShell：优先 `%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe`
   （含 Sysnative 回退）→ 跑 `check-compatibility.ps1`；失败则找 `pwsh.exe`；
   都没有则调 `compatibility-help.cmd` 并保留窗口；
4. 用 `-NoLogo -NoProfile -ExecutionPolicy Bypass -NoExit -File` 调 `run-installer.ps1`。

> **源模板与交付件文件名不同**：`wcp_wordbooks/installer/` 下的**源**文件叫
> `一键安装日语词书.cmd`，`build_installer_payload.py` 打包装时改名为 `01_双击运行我.cmd`。
> 在 `installer/` 里找 `01_双击运行我.cmd` 是找不到的。

**音频不在主包内**：`payload/manifest.json` 里 `skip_audio: true`，
主包体积约 27.5 MB。安装时从 `release-manifest.json` 的 `download_routes`
探测 Gitee/GitHub 路由：Gitee Release 下载分卷并合并，GitHub Release 下载两份**整包**；
每个未完成分片或整包都会留在 `jpmod_downloads`，下一次运行优先使用 HTTP Range 续传：
`wcp-japanese-audio-words.zip`（约 394 MB）与 `wcp-japanese-audio-sentences.zip`（约 2.06 GB），
两种路由都带 SHA-256 校验、实时百分比/速度显示、多线程解压、失败复用已校验资源；
若服务端不支持 Range，则安全地从头传输并保留校验机制。清单记录 `expanded_size`，
安装器以“两份压缩缓存 + 解压临时目录 + 最终音频 + 1 GB 安全余量”估算峰值空间，
避免把只够放下载包的空间误判为足够。

**安装器其余必须复刻的行为**：自动扫描 Steam 全部库目录并跳过不存在的盘符；
多有效副本时交互选择；安装前备份到 `wcp\jpmod_backups\<stamp>\`；
四个自定义槽全占用时提示选择替换槽位；已有 BepInEx 时保留其核心只补启动文件与插件；
`Get-FileHash` 不可用时改用内置 .NET `SHA256`；仅对本地回环测试镜像取消代理，
远程 Release 下载保留系统代理。

---

## 6. 扩展到新语言的适配清单与插件移植指南

### 6.1 可直接复用（但要审计，不是"照抄就对"）

| 组件 | 复用程度 |
|---|---|
| `wcp_paths.py` | **原样复用**（语言无关，只认 DB 存在性） |
| 灌库幂等框架 `patch_local_db.py` | 框架复用，**探针词换成新语言的词**，并决定同形词策略（见 §3.2） |
| xlsx 无表头 A/B 列契约 `make_import_files*.py` | 框架复用，换词表与列内容 |
| `MyBook.es3` 写入逻辑 | ES3 类型包装串照抄（§2.1），字符编码按新语言 |
| 例句校验框架 `gen_pipeline.py` | 框架复用，**换字符白名单 + 词形匹配规则 + 加全角括号禁令** |
| 音频 manifest 断点续传 `gen_audio*.py` | 框架复用，换 voice 与输出目录 |
| `BookProfiles.cs` | 只**增**新 Profile，不改日语逻辑；注意保持单一正本 |
| 例句播放 Mod | ⚠️ **不是纯复用**（旧版文档写"纯复用"是错的）：`ExtractJa` 要换成
`Extract<Lang>`（第 8 步的码点白名单换成本语言范围），作用域校验里的
`BookProfiles.Japanese` 要换成本语言常量，私有音频目录策略可能还要多一条拦截 |
| 词书行为 Mod `JpWordListMod` | ⚠️ **必须重写语言逻辑**，但可整体照抄其骨架：
跨词书基线还原（`JpWL_*`）、读档完成门（防编译期默认值 69,313 词污染，见 §7.1.3）、
队列安全兜底（≥5 词）、指纹 Fail-Closed |
| 选书拦截 Mod `BookNameMod` | ⚠️ **不是"原样复用"**：`ForceJpLabels` / `ToCosmeticIfManaged`
绑定了语言 Profile 判定，需参数化；并且**必须保留 5 秒 TTL 指纹缓存**（见下） |
| 离线自愈架构 | 换数据库提取条件，插件端自愈逻辑复用 |
| 安装器框架 | **直接基于 `Install-WCP-Japanese.ps1` 做文案与资产替换，切忌从零重写** |

> ⚠️ **`SlotProfile()` 的 5 秒 TTL 缓存不能删** `[实测]`：法语版曾删掉它并改注释为
> 「每次重新验证以免覆盖槽位后误接管」，代价是**常驻 ~11.5 ms/秒的主线程开销**
> （每秒重新反序列化 1.08 MB 的 `MyBook.es3` + 对 8,116 词做两轮归一化/排序/SHA-256，
> `Match` 每次调用 2 次），外加每秒 2.4 万个字符串的 GC 分配。
> 缓存语义是「5 秒内不重复验指纹」，不影响 §2.6 的「每轮刷新校验作用域」。

### 6.2 必须换的部分

| 项 | 换成什么 |
|---|---|
| TTS voice | 目标语言的 edge-tts voice |
| 字符白名单 | 目标语言字符集（例句校验 + 简繁/变体拦截） |
| 词形出现规则 | 目标语言屈折规则（日语要求原形字面出现；韩语变音较多；拉丁语系可放宽为去屈折词尾后的词干匹配） |
| 释义显示格式 | 音标体系（IPA/罗马音/谚文）+ 模板（如 `【音标】中文〈词性〉`） |
| 词书行为 Mod 的语言逻辑 | 日语：假名题干 + 汉字/中文选项 + 假名转汉字取音。法语例：题干单词，选项给中文释义+词性，重音字符做特殊匹配 |
| 单词音频目录策略 | **按 §3.2 的同形率判定**：共享 `vocabulary/` 还是私有 `<lang>_word_audio/` |
| 例句剥离函数 + 作用域 Profile | `Extract<Lang>` + 本语言 `BookProfile` |
| 词源数据 | 对应语言公开词表 + 目标语翻译资源 |
| 翻译兜底链 | 目标语机翻端点 + LLM 精翻批次 |
| 路径常量、安装器文案、备份目录名 | `<lang>_db_payload` / `<lang>mod_backups` / Release 名 |

### 6.3 新语言接入顺序（照做即可）

1. 按 §1 铺目录骨架；先把 `wcp_paths.py` 与路径常量模块定下来。
2. 建词源 → 构建 `<lang>_books.json`；定释义显示格式。
3. 释义三层翻译链（LLM 精翻批次 → 机翻兜底），跑键校验。
4. 搭字符白名单 + 例句契约（**含译文禁全角括号/换行**）→ 子代理批量生产 → `check-one` 逐批收口
   → `gen_pipeline.py summary` 主会话复核。
5. 音频（单词 + 例句 md5 命名，对应语言 voice）；**先决定单词音频走共享还是私有（§3.2）**。
6. `BookProfiles.cs` 注册 Profile + 算指纹 → 声明**唯一正本**，其余副本逐字节同步。
7. `patch_local_db.py` 换探针词 → 灌库（后台跑）→ `export_<lang>_db_payload.py` 出自愈包。
8. 编译三个插件（§附录 D）并部署。
9. 跑 §8 的**全部契约检查**（不要只跑项目自带 verify），退出码 0 才算过。
10. `build_installer_payload` + `build_release` 产出安装包。
11. 游戏内实测抽词验证七项：释义 / 注音 / 例句文本 / 例句朗读 / 单词发音 /
    跨词书切换 / 小游戏发音。
12. 显式声明「未验证的边界」（见 §附录 E）。

---

## 7. 运维约束与已踩过的坑

### 7.1 游戏存档与状态机制坑

1. **PowerShell JSON 序列化损坏存档导致开局剧情重置（v1.2.0 恶性事故）**：
   `ConvertTo-Json` 丢失 ES3 所需的深层 `__type` 并简化复杂对象 → 游戏识别为坏档，
   重置为新玩家（`Initial_PlotDone <= 1`）。
   **解决**：弃用 PowerShell 内置 JSON cmdlet，改用内嵌 C# `WcpEs3Helper`（`Add-Type` 编译），
   严格保 `__type` 与字段层级；并加 `TryRepairSaveFile` 自愈历史受损存档。
   （或采用 §2.1 的保型文本改写方案。）
2. **游戏运行时内存覆盖 SaveFile.es3**：
   游戏运行中维持一份内存数据，退出时整盘覆盖写 `SaveFile.es3`。
   外部脚本任何改名/选书/改档操作**必须且仅在 wcp.exe 完全关闭时执行**，
   否则修改被顶掉，还极易引发写冲突。
3. **未读档前的编译期默认值覆盖存档（v1.7.0 事故）**：
   游戏启动初期 `MyParameters` 全是编译期默认值（默认英语书「四级大纲词汇」**69,313 词**）。
   在正式从 ES3 读档完成之前触发词表过滤和存档回写，这 69,313 个英语词会被误判为"异物"
   过滤并写回存档，造成不可逆损坏。
   `JpWordListMod` 必须**确认读档完成**（比对内存词书名与存档记录）后才允许状态干预。

### 7.2 题干与选项状态不同步坑

1. **快速测试题干与选项严重错位（英语题干配日语选项）**：
   `clickChangeImageSource.StartQuickTest` 从全局已学词典按等级和上次学习时间重采样生成
   选项词表 `allTestWordsS10_Para`；而题面显示的单词来自 `SetInputFieldValueS8.ShowTheWord`，
   它直接读存档的 `S8needToLearnWordList_Para[0]`。
   玩家上一轮在英语书 → 存档 `need` 队列还留着英语词 → 题面「superiority」、选项「全部/猪肉/破碎」，
   永远答不对。
   **解决**：拦截 `SyncStemQueue`，词池一换，题干队列与进度必须同步重置，
   且必须在游戏读 `need[0]` **之前**完成并持久化到 ES3。
2. **词表剔空越界崩溃（`ArgumentOutOfRangeException`）**：
   `MultipleChoiceGeneratorS9` 要求 `allTestWordsS10_Para.Count >= 5`（战斗模式 ≥4）。
   过滤逻辑若把词表剔空或少于 5 词，生成选项时直接抛异常卡死。
   **红线**：绝不允许回写空表或少于 5 词的队列；无合法词条则把本轮测试标记为已完成。
3. **跨词书切换与残留外语队列（`JpWL_*` 机制）**：见 §3.3。

### 7.3 音频与平台特性坑

1. **Windows 保留文件名冲突（`aux.mp3` / `nul.mp3`）**：见 §2.6 避坑点 1。
2. **假名出题导致原生发音查询落空**：见 §2.6 避坑点 2。
3. **PowerShell 5.1 BOM 解析失败**：
   PS 5.1 按 ANSI(GBK) 读**无 BOM** 的 `.ps1`。UTF-8 中文 3 字节/字、GBK 2 字节/字，
   **汉字串字节数为奇数时双字节配对越界，吞掉紧随的 ASCII 字符（引号/空格）**
   → 字符串未闭合 → ParseError → exit 1 且**零副作用**（连 finally 都不执行）。
   `[实测]` 受控 A/B（脚本其余完全相同）：`'中文标记'` 4 字/12B → exit 0；
   `'中文标记啊'` 5 字/15B → exit 1。所谓「时灵时不灵」只因汉字个数奇偶。
   **规则：含非 ASCII 的 `.ps1`/`.cmd` 一律存 UTF-8 with BOM（或纯 ASCII）。**
   转 BOM：`[IO.File]::WriteAllText($p,[IO.File]::ReadAllText($p,[Text.UTF8Encoding]::new($false)),[Text.UTF8Encoding]::new($true))`
   （同时注意**不要堆叠多个 BOM**。）
4. **安装器控制台异常关闭与闪退**：普通用户双击 `.ps1` 常因安全策略/默认关联/报错直接闪退，
   看不到日志。统一采用 `01_双击运行我.cmd` 入口 + `--keep-open` 自重启技巧（§5.2），
   固定保留控制台会话，右上角 X 关闭、按 Enter 不关闭。
5. **依赖 CLI 本地化输出**：`tasklist /FO CSV /NH` 无匹配时的提示在不同语言下
   落到 stdout 还是 stderr、文案都不同。判定只认「有没有目标进程那一行」
   （字段数 ≥2 且首列为 `wcp.exe`），别拿"stdout 是否为空"当成功标志。
   `[实测]` 中文 Windows 上该提示走 stdout；英文环境行为**未验证**，不声称会失败。

### 7.4 数据管线与落地坑

1. **例句灌库曾因 rowid 错位写乱 10,251 词**：
   早期 `apply_sentences.py` 用自增 `rowid` 做 `UPDATE sentence2 … WHERE rowid=?`，
   而那份 `logs/sentence_worklist.tsv` 是 `patch_local_db.py` **重建 sentence2 之前**抓的，
   行号早已指向别的词 → 10,251 条中文翻译写串到别的单词上（词数/条数全对，内容全错）。
   **现已全部改为基于 `word + 原文` 的复合主键定位更新**（配合 §2.5 的无约束表结构）。
2. **Steam 更新覆写 StreamingAssets 本地库**：见 §2.5。
3. **例句音频命名契约破裂**：见 §2.6（日语侧现存 386 条）。

---

## 8. 契约 → 可执行检查（**复刻验收的核心，旧版文档完全缺失**）

> `[实测]` 法语项目的教训：`verify_all_fr.py` 是 **ALL PASS**，但它当时**完全没检查**
> IMPLEMENTATION.md 里写明的事故点（ES3 `__type`、xlsx 表头、保留设备名、
> 例句音频跨端一致、离线自愈包完整性、指纹副本一致）。
> **自带校验通过 ≠ 没问题。** 逐条把 §2/§3 的 ⚠️ 变成断言，才是真正的验收。

| 契约条款 | 可执行断言 |
|---|---|
| §2.1 ES3 类型包装 | `json.loads(MyBook.es3)` 后，**每个顶层键**都有 `__type` |
| §2.1 存档保护 | 安装器/写盘前后比对真实 `MyBook.es3` / `SaveFile.es3` 的 SHA-256 **未被改写**（沙箱写入必须零副作用） |
| §2.2 指纹正本 | 全部 `BookProfiles.cs` 副本**逐字节 SHA-256 相同** |
| §2.3 指纹三方一致 | `MyBook.es3` 槽位真实词表 / `BookProfiles.cs` 常量 / `<lang>_book.json` 三点同值（Python 复刻 `FingerprintOf`，无需 csc） |
| §2.4 xlsx 无表头 | `openpyxl` 读第 1 行，断言 A1 **是词表里的真词**、B1 不是「释义/Meaning」 |
| §2.5 自愈包完整 | `<lang>_db_payload/` 五件套 + `manifest.json` 齐全；探针词必须在词表与 `*_pron.tsv` 中 |
| §2.5 自愈探针可区分 | `<lang>_pron.tsv` 的释义**不以英文原版开头**，`en_pron` 基线反之（防止稳态误判） |
| §2.5 插件探针常量可解析 | 从 `.cs` 源码里提取探针常量，与数据侧比对（常量漂移会静默误判稳态） |
| §2.6 保留设备名 | 词表里 `con/prn/aux/nul/com1/lpt1` 开头的词，音频必须真实落地 |
| §2.6 **例句音频跨端一致** | Python 复刻 `Extract<Lang>` → 对**全部**例句断言 `剥离(例句：{原文}（{译文}）) == 原文`，且 `md5(…).mp3` **存在** |
| §3.2 音频目录隔离 | 共享 `vocabulary/` 里**零本语言残留**（若采用私有目录方案） |
| §3.2 同形词稳态 | 用英文基线库逐词比对本语言同形词的 `pron`/`sentence2`，确认共享库停在英文态 |
| §3.3 Fail-Closed | 单测：同引用、同长度、内容被改写的词表**必须被拒**；不一致身份必须拒绝接管 |
| §7.3 BOM | 脚本文件头**恰好一个** UTF-8 BOM，无堆叠 |
| 全量 | `verify_all` 通过 + `gen_pipeline summary` 达标 + 三个运行时单测通过 |

**必须写成端到端断言的最后一条**（最容易被"文件存在"骗过去）：
音频不是"生成了"就算对，而是"**按插件算法算出的文件名能被插件找到**"才算对。

---

## 9. 交付物清单与实测基线

> **旧版文档的数字已过期**。以下 `[实测]` 值为 2026-09-14 从磁盘/数据库直接读出，
> 每条都给了复算方式；**新语言不要照抄数字，要照抄复算方法**。
> 共享目录（`vocabulary/`、`sentence_audio/`）会被多语言同时写入，
> **绝对数量不能作为单语言的验收基线**。

| 类别 | 实测值 `[实测]` | 复算方式 |
|---|---|---|
| 核心单册词书 | 猫条版 JLPT 完整词库 **7,922 词**，指纹 `6d7a51c0c5d30dd63d8a6e3412bce1cf2419554fb8487cf5c8a205e43ac41663` | 读 `payload/catbar_book.json` 的 `word_count` / `fingerprint_sha256` |
| JLPT 分册 | N5 661 / N4 632 / N3 1,784 / N2 1,791 / N1 3,463 = **8,331** | `output/jlpt_books.json` 的 `levels` |
| 主题册（JMDict） | **10 册**：it 800 / medical 800 / business 419 / law 600 / idiom 683 / onoma / yoji / keigo / kotowaza / talk，合计 **4,593 词** | `output/themed_books.json` 的 `meta.themes`（⚠️ 文档与 README 旧写「9 册」，实测 10 册，需核实统一） |
| 专业册 | **2 册**：IT 662 / 商务 458 | `output/topic_books.json` 的 `books` |
| SetB 5 册 | idioms 533 / giongo 638 / yoji 260 / advanced 234 / business 636 = **2,301** | `output/setb_books.json` 的 `levels` |
| 常用汉字 | **2,136 字** | `output/kanji_books.json` |
| 语法路线 | **8,640 行**（304 占位词 + 5 阶段头；讲解例句 927 条） | `output/grammar_route.json` 长度；`payload/manifest.json` 的 `route_rows` |
| 本地库 pron（含假名读音的日文词） | **14,972** 词口径 / sentence2 覆盖 **16,121** 词（含语法 309 占位词） | `SELECT COUNT(DISTINCT word) FROM pron WHERE ukPhonic GLOB '*[ぁ-んァ-ヶ]*'`；同上对 `sentence2` |
| sentence2 日文行数 | **58,578** 行 | `SELECT COUNT(*) FROM sentence2 WHERE CAST(sentences AS TEXT) GLOB '*[ぁ-んァ-ヶ]*'` |
| 例句音频（日语主表实际使用） | **56,661** 个唯一 md5，**0 缺失**（另有 **386 条**因 §2.6 缺陷不可达） | 见 §8 的端到端断言脚本 |
| 共享 `sentence_audio/` 目录总量 | **82,486** 个 mp3（多语言共享，非本语言基线） | `ls \| wc -l` |
| 共享 `vocabulary/` 目录总量 | **约 19,200** 个音频（多语言共享，非本语言基线） | `ls \| wc -l` |
| BepInEx 插件集 | `JpWordListMod.dll`（v1.7.6）/ `BookNameMod.dll` / `SentenceAudioMod.dll`（NETFX 4.0 csc，C# 5，共享 `BookProfiles.cs`） | `grep BepInPlugin` 取版本号 |
| 玩家一键安装包 | `WCP-Japanese-OneClick-Installer-wcp-jp-v1.2.2.zip`（约 12.3 MB） | `output/release/` |
| 音频 Release 资产 | words 394,614,754 B / sentences 2,057,214,618 B（各带 SHA-256） | `support/release-manifest.json` |

**三条验收命令**（都在 `D:/Japanese/wcp_wordbooks/` 下跑）：

```bash
python tools/verify_all.py            # 主词表 15812 词的覆盖/例句/音频/外接库
python tools/gen_pipeline.py summary  # 例句生产达标率（应 15812/15812，剩余批次 0）
cmd /c "cd /d D:\Japanese\mod_book_name && build.cmd"     # 改过 C# 必须重编译+部署
```
`[实测]` 本次运行结果：`verify_all.py` 全项输出正常（`[1]` 15812/15812、`[4]` 词表词不在 pron 0、
`[6]` 音频命中 15812/15812 缺 0）；`gen_pipeline.py summary` = 词块总词数 15812 / 达标 15812 / 剩余批次 0。
**但这两条都通不过 §8 的例句音频断言**（386 条破例在 §2.6）——
这就是"自带校验通过 ≠ 没问题"的现场例证。

---

## 附录 A：端到端 Runbook（命令级可执行序列）

工作目录 `D:\Japanese\wcp_wordbooks\`（**插件构建命令除外**，见文末）。
Python 用托管环境（`py` 代指）；**新语言项目请把这一行换成你自己项目的解释器/venv**，
不要把作者机器的绝对路径抄进文档。

```text
# ── 阶段1 词书构建 ────────────────────────────────────────────
py tools/build_books.py                       # -> output/jlpt_books.json
py tools/build_topic_books.py                 # -> output/topic_books.json（IT/商务）
py tools/extract_themed.py                    # -> 主题册骨架（JMDict field/misc）
py tools/build_kanji_book.py                  # -> output/kanji_books_raw.json
py tools/setb_build.py                        # -> output/setb_books.json

# ── 阶段2 释义分层翻译 ────────────────────────────────────────
py tools/translate_gtx.py                     # 机翻兜底 -> data/translations/gtx_zh.json
py tools/themed_gtx.py                        # 主题册机翻
py tools/fetch_readings.py                    # Jisho 补读音 -> data/readings_jisho.json
py tools/make_llm_batch.py                    # 导出下一批精翻任务 llm_batch_pending.json
py tools/merge_translations.py --write-game   # 重建 jlpt_books.json + MyBook.es3 + 导入文件
py tools/merge_topic.py --write-import        # 主题/专业册合并 + 导入件
py tools/merge_themed.py                      # -> output/themed_books.json
py tools/merge_kanji.py --audio               # 常用汉字 + 音训朗读 MP3

# ── 阶段3 质量校验 ────────────────────────────────────────────
py tools/validate_themed.py                   # 字符白名单（拦简体字混入）
py tools/setb_check_readings.py               # kanjidic2 音训读分解校验
py tools/themed_check_readings.py
py tools/check_topic_keys.py                  # 翻译键与源词表拼写一致
py tools/check_grammar_content.py             # 语法内容全量校验

# ── 阶段4 例句生产（子代理批量） ──────────────────────────────
py tools/build_sentence_jobs.py               # 切块 -> work/gen_words_NN.json
py tools/gen_dispatch.py status               # 总进度
py tools/gen_dispatch.py batch NN Y           # 看某批词表+缺口
py tools/gen_pipeline.py check-one NN Y       # 每批写完立即校验，必须 PASS
py tools/gen_helper.py merge NN Y work/patch_NN_Y.json   # PATCH 模式合并后重新 check
py tools/gen_pipeline.py summary              # 主会话复核（子代理自述不算数）
py -u tools/apply_sentences.py                # [BG] 合并 gen_out_* + tr_out_* + 翻译
                                              #   -> sentences_master.json + 落 sentence2
py -u tools/patch_local_db.py                 # [BG] 全部 books.json -> 灌 pron + sentence2

# ── 阶段5 音频 ────────────────────────────────────────────────
py tools/gen_audio.py --limit 400             # 单词 MP3
py tools/gen_audio.py --retry-failed
py tools/gen_audio_topic.py                   # 专业册（独立 manifest）
py tools/setb_audio.py                        # SetB（独立 manifest）
py tools/gen_sentence_audio.py --limit 2000   # 例句 -> sentence_audio/<md5(原文)>.mp3
py tools/gen_grammar_audio.py                 # 语法占位词 + 927 条讲解例句

# ── 阶段6 交付与打包 ──────────────────────────────────────────
py tools/build_grammar_book.py --patch        # 语法路线构建 + 落库
py tools/make_import_files.py                 # output/import/：无表头 xlsx + wcp_jlpt.db
py tools/make_import_files_themed.py          # 主题册导入件
py tools/setb_import.py                       # SetB 导入件
py tools/write_catbar_combined.py             # 写 7922 词单册到槽位1并清理槽位2~4
py tools/rename_books.py                      # 写署名昵称（槽位身份不变）
py tools/export_jp_db_payload.py              # 导出离线自愈包 -> output/jp_db_payload/
py tools/build_installer_payload.py [--skip-audio]
py tools/build_release.py --reuse-audio

# ── Steam 更新还原 .db 之后 ───────────────────────────────────
py -u tools/patch_local_db.py && py tools/build_grammar_book.py --patch

# ── BepInEx 插件编译（在 PowerShell 工具里跑；Bash 沙箱禁 csc）────
cmd /c "cd /d D:\Japanese\mod_book_name && build.cmd"
cmd /c "cd /d D:\Japanese\mod_jp_wordlist && build.cmd"
cmd /c "cd /d D:\Japanese\mod_sentence_audio && build.cmd"
```

## 附录 B：中间文件与数据库 Schema（实测结构）

**`payload/catbar_book.json`**（安装包标准化单册词书）`[实测]` 键序与结构：
```json
{
  "id": "catbar-jlpt-complete",
  "language": "ja",
  "display_name": "日语词库(猫条版)",
  "word_count": 7922,
  "fingerprint_sha256": "6d7a51c0c5d30dd63d8a6e3412bce1cf2419554fb8487cf5c8a205e43ac41663",
  "words": ["単語1", "単語2"],
  "meanings": {"単語1": "【かな】释义〈词性〉"}
}
```

**`output/jlpt_books.json`**（构建管线主中间形态）：
```json
{"meta": {"sources": [], "stats": {"n5": {"count":661,"zh":661,"en_only":0}},
          "translation_layers": {}},
 "levels": {"n5..n1": [{"word","reading","meaning_en","example_ja","example_en",
                         "level","meaning_zh","meaning","zh_source","pos_zh"}]}}
```
（`themed_books.json` / `kanji_books.json` 用 `books` 键；`topic_books.json` 用 `books`；
`setb_books.json` 用 `levels`；`grammar_route.json` 是**顶层数组**，不是对象。）

**`payload/manifest.json`**（载荷清单）`[实测]` 字段：
`built`, `pron`, `grammar_placeholders`, `stages`, `route_rows`, `skip_audio`,
`bundled_bepinex`, `plugins[]`, `auto_import`, `size_mb`。

**`support/release-manifest.json`**（音频资产账本）：
`version`, `built`, `base_urls[]`（旧版兼容）、`download_routes[]`（Gitee 分卷/GitHub 整包）、`assets[]`（`kind`/`name`/`size`/`expanded_size`/`sha256`/`parts[]`）。

**`<lang>_db_payload/` 离线自愈补丁包**（四件）：
- `jp_pron.tsv`：`word \t ukPhonic \t usPhonic \t meaning`
- `jp_sentences.tsv`：`word \t sentences`
- `jp_only_pron.tsv`：同 `jp_pron.tsv`（针对 `wcpOnlyWord.db`）
- `manifest.json`：条目数/构建时间等

**本地库表结构** `[实测]`：见 §2.5（两表均无主键/唯一约束/索引）。

## 附录 C：脚本 CLI 速查

| 脚本 | 调用方式 |
|---|---|
| `verify_all.py` | 无参数，全量复核（7 组检查，见 §8 的缺口说明） |
| `gen_pipeline.py` | `summary`(默认) / `list` / `check [all]` / `check-one NN Y`；env `GEN_MIN` 改每词条数 |
| `gen_helper.py` | `plan [N]` / `audit` / `merge NN Y <补丁.json>` |
| `gen_dispatch.py` | `status` / `claim [N]` / `batch NN Y` / `done` |
| `gen_audio.py` | `--limit N`（默认 500）/ `--retry-failed` |
| `gen_sentence_audio.py` | `--limit N`（默认 0 = 不限） |
| `make_import_files.py` | 无参数 / `--combined-only` |
| `build_installer_payload.py` | `[--skip-audio]`；env `WCP_GAME_DIR`、`WCP_BEPINEX_SOURCE` |
| `build_release.py` | `[--reuse-audio]` |
| `patch_local_db.py` | `[--force]` |
| `build_grammar_book.py` | `[--stages …] [--patch] [--dry-run] [--allow-missing]` |
| `rename_books.py` | 无参数（写署名）/ `--restore` / `--detail` |
| `write_mybook.py` | `[--dry-run] [--file <目标>]` |
| `write_catbar_combined.py` | 直接运行：清空槽位 2~4，7922 词写入槽位 1，设外观名 |
| `export_jp_db_payload.py` | 导出当前游戏库日文数据至 `jp_db_payload`；env `WCP_LOCALLOW` 可覆盖数据目录 |

## 附录 D：BepInEx 插件构建（**按 build.cmd 实际内容抄，不要按旧版文档的引用清单抄**）

- 编译器：**NETFX 自带 csc**（`C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe`）。
  不使用 dotnet/msbuild —— 游戏跑在 Mono NETFX 上，源码刻意保持 **C# 5 语法**。
- 完整参数（`[源码]` `mod_book_name/build.cmd`）：
  ```
  /nologo /noconfig /nostdlib+ /target:library /langversion:5 /optimize+ [ /codepage:65001 ]
  ```
  > `/codepage:65001` 只在 `mod_jp_wordlist/build.cmd` 里出现；
  > ⚠️ 旧版文档把引用清单写漏了，照抄会编译失败。
- 引用清单（`%GAME%\wcp_Data\Managed`，除 BepInEx 两项）：
  `BepInEx\core\BepInEx.dll`、`BepInEx\core\0Harmony.dll`、
  **`Assembly-CSharp.dll`、`Assembly-CSharp-firstpass.dll`**、
  **`netstandard.dll`、`mscorlib.dll`、`System.dll`、`System.Core.dll`**、
  **`UnityEngine.dll`、`UnityEngine.CoreModule.dll`、`UnityEngine.UIModule.dll`、
  `UnityEngine.UI.dll`、`UnityEngine.TextRenderingModule.dll`、`Unity.TextMeshPro.dll`**；
  `mod_jp_wordlist` 额外需要 **`System.Data.dll`、`Mono.Data.Sqlite.dll`**（自愈用 Sqlite）。
- **共享编译**：所有插件的 `build.cmd` 把 `mod_book_name\BookProfiles.cs` 编进同一 `csc` 调用，
  保证指纹算法跨插件绝对一致。**该文件是唯一正本**，其他任何副本必须逐字节相同。
- **三个环境变量**（旧版文档没写，复刻时必须知道）：
  - `WCP_GAME_DIR`：覆盖游戏目录。`build.cmd` 里的默认值是硬编码的
    `E:\Steam\steamapps\common\WCP-WordGirlgriend`，**换机器必改或用环境变量**。
  - `WCP_NO_DEPLOY=1`：只编译不部署（用于 CI/交叉验证，避免动到运行中的游戏目录）。
  - `WCP_BEPINEX_SOURCE`：`build_installer_payload.py` 用它指定纯净 BepInEx 来源。
- 编译脚本自带守卫：找不到 `BepInEx\core\BepInEx.dll` 直接 `exit /b 1` 提示先装 BepInEx；
  部署用 `copy /y` 到 `%GAME%\BepInEx\plugins\`，失败（游戏运行时 dll 被锁）会打印
  `DEPLOY FAILED - game is probably running` 并 `exit /b 1`。

## 附录 E：诚实边界 —— 文档无法 1:1 传递的部分

以下是**文档照抄也复刻不出来**、必须人工/会话内决策的点：

1. **LLM 精翻的 prompt 本体没有落盘**。例句/语法有契约文件（`AGENT_SPEC.md` 等），
   但释义精翻是交互式完成的，批任务文件只有词条没有完整 prompt —— 新语言需自定精翻要求。
2. **词源人工筛选的判断**。SetB 的惯用句/四字熟语/高级词汇/主题册的增补标准（417 条人工增补）
   散落在会话记录里，只留了结果文件。
3. **子代理编排策略**（每波代理数、波次复核节奏）是会话级实践；附录 A 固化的是工具链序列。
4. **安装器与自愈实现代码量**：`Install-WCP-Japanese.ps1` 989 行，含 C# AST 嵌入式解析器、
   多线程 Zip 会话与异常保护。**应直接基于该脚本做文案与资产替换，切忌从零重写。**
5. 🆕 **"要不要隔离单词音频"是语言级判断题**，取决于「本语言词表 ∩ 英语原库」的同形率。
   文档给了判定规则（§3.2）和已算出的数字（法语 1,638/8,116），但**新语言的数字要自己算**。
6. 🆕 **多语言共存时的实机切换矩阵未验证**。`[实测]` 法语侧目前只做到「同一语言内一致」，
   「法语 → 英语 → 日语 → 法语」完整切换 + 共享库切换时的真实界面与音频行为，
   必须在**受控关闭游戏、备份存档**后做实机验证。本文档**不声称**这条已经验证过。
7. 🆕 **日语侧现存 386 条例句音频不可达**（§2.6），根因已定位、已量化，
   修复方式是「译文去掉全角括号 → 重算这些例句的音频文件名」，**本次未执行**（涉及写游戏库）。

除以上七点外，本文档 + 仓库脚本 + 三份 SPEC 足以支撑新语言复刻整条管线与运行时架构。

## 附录 F：本机环境硬约束（省时间用，会随环境变）

- Bash 工具的 PATH 经常是坏的，每条命令前先 `export PATH="/c/Windows/System32:/c/Windows:/usr/bin:/bin:$PATH"`。
- 沙箱禁止 Bash 调 `cmd.exe`；**任何含 `csc.exe` 字样的命令都被拒** ——
  编译 C# 插件只能在 **PowerShell 工具**里 `& "D:\<Lang>\mod_x\build.cmd"`。
- PowerShell 工具 **stdout 恒为空**：把输出 `Out-File` 到文件再用 Read 读那个文件。
- Glob 在工作区外不可靠（`C:/Windows/...` 返回 No files found），用 bash `ls` 确认。
- 改完 DLL 必须重新部署；`*.dll` 已 gitignore，**仓库里没有 DLL**。
- ⚠️ **并发写入是真实存在的**：审计期间可能有第二方进程同时改这个项目
  （搬文件、重写共享库、重建部署 DLL、提交推送仓库）。判据：游戏目录里文件/目录 mtime
  落在审计时间窗内、`git status` 自己变短。
  遇到不可复现的失败，如实写成「观察到 N 次、M 次通过、根因未定位、进程未定位」，
  **不要编叙事补坑**。

---

*本文档基于 2026-09-14 项目最新状态（Installer v1.2.2 / JpWordListMod v1.7.6）对齐；
契约细节以代码与真实运行时行为为准。发现文档与实现不符时，先改文档并说明理由。*
