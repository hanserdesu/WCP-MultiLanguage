# WCP 多语言词书 — 统一接入架构设计（Host / Pack / Strategy）

> 目标：**资源逻辑与接入逻辑解耦**。所有语言共用一套接入逻辑（宿主），
> 每套语言资源（词库/释义/例句/音频）互相隔离、互不读写，只有被选中的词书
> 才由宿主激活。语言词书与游戏本体玩法解耦，语言词书之间也解耦，
> 但全部通过同一套接入逻辑集成。
>
> 状态：**阶段 2 实施中**。注册表、资源路由、日语策略、宿主构建、20 个逻辑槽位和
> 日语安装包交付已落地；多语言行为接管与切书矩阵仍未完成实机验收。
> 游戏目录当前保留可运行的只读旧宿主，
> 新宿主的运行时替换必须以启动日志和切书实测为准。
> 语言资源可以物理隔离并由清单路由；真正不能数据化的只有语言行为策略，
> 因此新语言可以只新增资源包并复用宿主通用策略，特殊语言才需要自己的策略程序集。

---

## §0 结论（先行）

| 判断 | 结论 |
|---|---|
| 目标架构可行性 | **可行**。身份层（`BookProfile`）已经打好地基，缺的是资源路由与策略抽离。 |
| 能否做到"语言包 = 纯数据"？ | **不能**。至少 4 类逻辑是行为而非资源，必须留一个小的策略实现（约 150 行/语言）。 |
| 多语言能否同时共存？ | **资源可共存，运行态串行。** 实测原生存档占 3 槽（ja=1 / fr=2 / ru=3）；20 个逻辑槽位负责目录管理，运行时仍只激活当前选择。 |
| 最深的耦合在哪？ | **往 `wcpFullEng.db` 写语言内容**。这是单文件、单主键（`word`）的表，跨语言同形词会互相覆盖。必须停止写入，改由宿主自服务。 |
| 原生槽位边界 | 游戏仍只有 **4 个 `SelfBookListN` 原生字段**；宿主不伪造第五个字段。 |
| 用户可见槽位 | `CustomSlotsMod` 提供 **20 个逻辑槽位**，同一页 `ScrollRect` 滚轮选择；外部词书保持 external，不被覆盖。 |

**最高优先级动作**：把例句音频与单词音频目录**按语言私有化**，不再共享
`LocalLow\WCP\packs\<lang>\audio\word\` 与
`LocalLow\WCP\packs\<lang>\audio\sentence\`。
这是当前唯一能让"新加一种拉丁语系语言就串音"的真实风险归零的改动，
且不需要动游戏数据库、不需要动运行态协议。

---

## §1 现状实测：耦合到底在哪

### 1.1 接入逻辑是 fork，不是复用（实测 diff）

去掉 CRLF 噪声后逐行 diff（`diff --strip-trailing-cr`）：

| 模块 | 源码行数 | JP→FR 差异 | JP→RU 差异 | 复用率 |
|---|---|---|---|---|
| 词表插件 `*WordListMod.cs` | 2,339 | **2,084** | **1,811** | 11% / 23% |
| 例句音频 `SentenceAudio*Mod.cs` | 923 | **732** | **527** | 21% / 43% |
| 书名插件 `BookNameMod.cs` | 693 | **26** | — | **96%** |

- 书名插件基本就是复用品（26 行差异），证明**抽象的边界是成立的** —— 只要接口切对，95% 可以共用。
- 词表插件 80~89% 在重复。四语言 × 三个 DLL = **12 个 DLL、约 11,700 行**，
  其中真正的独立逻辑估计不足 1,500 行。

复算命令：

```bash
diff --strip-trailing-cr \
  D:/Japanese/mod_jp_wordlist/JpWordListMod.cs \
  D:/French/mod_fr_wordlist/FrWordListMod.cs | grep -cE '^[<>]'
```

### 1.2 五处共享资源，三套互相不一致的命名空间

安装器把四语言资源倒进同一批全局位置（`Install-WCP-*.ps1` 实测）：

| # | 共享资源 | 物理位置 | 各语言怎么处理 | 风险 |
|---|---|---|---|---|
| 1 | 单词音频 | `LocalLow\WCP\packs\<lang>\audio\word\` | 宿主按当前 manifest 路由；日语迁移脚本按 15,812 个词从旧共享目录分流，生成器以后直接写 ja pack | **已修复**：当前语言之外的文件不进入该语言包 |
| 2 | 例句音频 | `LocalLow\WCP\packs\<lang>\audio\sentence\` | 宿主按当前 manifest 路由；日语 56,941 个文件已迁移，日语旧插件不再回退共享目录 | **已修复**：物理目录隔离，不依赖语言提取谓词互斥 |
| 3 | 词书文件 | `LocalLow\WCP\wcp\*.xlsx` | 同目录，靠文件名区分 | 中：无命名空间，靠约定 |
| 4 | 游戏数据库 | `StreamingAssets\wcpFullEng.db` 的 `pron` / `sentence2` | 各语言按 `word` 主键写入 | **最高**：单文件单主键，跨语言同形词互相覆盖（实测法语 8,116 词中 **1,638 个与英语同形**） |
| 5 | BepInEx 插件 | `BepInEx\plugins\*.dll` | 每语言 3 个 DLL，线性增长 | 低：靠文件名区分 |

对比：**已经做对的**是自愈包 `jp_db_payload` / `fr_db_payload` / `ru_db_payload`
—— 这是全项目唯一一处已经按语言命名空间化的资源。

### 1.3 已经存在的地基（不要推倒）

`mod_book_name/BookProfiles.cs`（93 行）已经实现了目标架构最关键的两件事：

1. **身份层**：`BookProfile { Id, Language, DisplayName, WordCount, Fingerprint }`，
   指纹 = 对排序后的全词形集合做 SHA-256。**一本书在任何槽位都能被认出来**。
2. **负面识别（negative identification）**：注册表 `All[]` **登记全部语言**，
   每个插件只碰自己那一份，其它语言正面识别为"别人的"。
   法语项目注释原文：*"Registering the Japanese book here as well lets the FR plugin
   positively identify (and therefore never touch) it."*

再加上词表插件的 **fail-closed 作用域门**（内存词表 / 槽位 / 落盘书名三者一致才动手，
不一致一律不接管）—— 这是整个架构里最值得保留的设计。

**但有两个问题**：

- **副本漂移**：JA 项目是单份共享（`mod_jp_wordlist/build.cmd` 引用
  `%~dp0..\mod_book_name\BookProfiles.cs`）；FR/RU 项目各带 **3 份拷贝**
  （`mod_book_name/`、`mod_*_wordlist/`、`mod_sentence_audio_*/`）→ 已经开始漂移。
- **注册表与代码一起编译进 DLL**，新增语言要改源码、重编全部 DLL。
  应外置成数据。

### 1.4 槽位：原生 4 槽，用户可见 20 个逻辑槽位

游戏只有 **4 个自定义词书原生字段**，前缀「自定义词书一~四」是硬编码字面量
（`BookNameMod.cs` 第 5 行注释、`_slotProfiles[4]` 数组）。
`Japanese/mod_custom_slots` 不改写这些内部字段，而是维护 20 行独立状态，
在一个可滚动页面上管理；选中时只把词书物化到空闲或本 mod 已拥有的原生槽位。
非 mod 词书标记为 `external`，没有安全复用的原生槽位时 fail-closed。
且**改名会切断 `SelfBookMeaningDictionary` 的加载路径** —— 身份键只能读书名，不能改书名。

**实测存档 `LocalLow\WCP\wcp\MyBook.es3`**（2026-09-14）：

| 槽 | `SelfBookListN` 词数 | SHA-256（前 16） | 语言 |
|---|---|---|---|
| 1 | 7,922 | `6d7a51c0c5d30dd6` | ja |
| 2 | 8,116 | `376af2eae0292052` | fr |
| 3 | 8,451 | `dfecb0ab75e9b3ef` | ru |
| 4 | 0 | — | 空 |

三条关键结论：

1. **三语已经在共存。** 用户要的"多语言共存"不是设想，是磁盘上的既成事实。
2. **一个语言包 = 一个槽 = 一条 `BookProfile`。**
   但"一册书"在磁盘上可以是多个 xlsx 片段：日语是单册
   （`日语词库(猫条版).xlsx` = 7,922 词），法语/俄语各是三个分册
   （A1A2 + B1 + B2 = 2,680+2,902+2,534 / 2,930+3,026+2,495），
   游戏导入后并成一个槽。**`fingerprint_sha256` 是对并集去重后算的** —— 已复算验证，
   三种语言的并集指纹与注册表声明值逐字节一致。
3. **原生 4 槽是运行态物理边界，不是用户目录上限。** 20 个逻辑槽位可保存和管理更多外部/受管词书，
   但同一时刻仍只能把一个词书物化到游戏的 4 个原生字段之一。

`JLPT_N1/N2/N3/N5N4、IT用语` 是日语合并前的源片段，不列入 `books`、不占槽。

---

## §2 目标架构：三层

```
┌─────────────────────────────────────────────────────────────┐
│ L0 宿主  WcpHost.dll        （1 个，语言无关，唯一会碰游戏的地方） │
│  ├ 补丁层：全部 Harmony 补丁点，固定集合，不再随语言增长          │
│  ├ 适配层：MyParameters / 场景类名 / ES3 键的反射封装 + 降级      │
│  ├ 身份层：BookProfile 注册表（外置数据） + SHA-256 指纹          │
│  ├ 作用域门：fail-closed（内存/槽位/落盘三者一致才动手）           │
│  ├ 路由层：ResourceRouter (lang, kind, key) → 物理路径 / 记录     │
│  └ 接管层：TakeoverScope 统一接管-还原协议（运行态串行化）          │
└───────────────┬─────────────────────────────────────────────┘
                │ 只加载 activeLang 的 pack；其它 pack 处于 unmounted
    ┌───────────┴───────────┬───────────┬───────────┐
    ▼                       ▼           ▼           ▼
┌─────────┐          ┌─────────┐  ┌─────────┐  ┌─────────┐
│ L1 ja   │          │ L1 fr   │  │ L1 ru   │  │ L1 de   │
│ Pack    │          │ Pack    │  │ Pack    │  │ Pack    │
│ 纯数据  │          │ 纯数据  │  │ 纯数据  │  │ 纯数据  │
├─────────┤          ├─────────┤  ├─────────┤  ├─────────┤
│manifest │          │manifest │  │manifest │  │manifest │
│books/   │          │books/   │  │books/   │  │books/   │
│db/      │          │db/      │  │db/      │  │db/      │
│audio/   │          │audio/   │  │audio/   │  │audio/   │
└────┬────┘          └────┬────┘  └────┬────┘  └────┬────┘
     ▼                    ▼            ▼            ▼
┌─────────┐          ┌─────────┐  ┌─────────┐  ┌─────────┐
│ L2 ja   │          │ L2 fr   │  │ L2 ru   │  │ L2 de   │
│Strategy │          │Strategy │  │Strategy │  │Strategy │
│ ~150 行 │          │ ~150 行 │  │ ~150 行 │  │ ~150 行 │
└─────────┘          └─────────┘  └─────────┘  └─────────┘
```

### 2.1 L0 宿主：唯一会碰游戏的地方

宿主承担"机制"，与语言无关：

- **补丁层**：合并现有三套插件的补丁点，成为固定集合。
  已知补丁点（实测）：
  - `VocabularyAudioPlayer.PlayWordAudio`（单词音频，三语言都已用，前缀/后缀）
  - `WordChooseButtonS10.SonBookChoose`、`changePreferredSoundS8/S9.*`、
    `ChangeLocalVoiceIf.*`、`SoundLocalManager.*`（书名显示，6 处，`BookNameMod.cs`）
  - `MultipleChoiceGenerator/S9`、`ChooseWordManager.ResetTestListQuick*`、
    `SetInputFieldValueS8.ShowTheWord` 等（题干/选项/队列，`JpWordListMod.cs`）
  - `DatabaseManagerS8`、`S8checkWordMeaning`、`ButtonTextTransfer.OnSearchButtonClick`（查词面板）
  - 家族 7 个场景的 `Awake/Start`（批量挂载点）
- **反射适配层**：所有 `MyParameters` 字段访问走 `GetField/SetParameterField`，
  字段改名只记日志不抛异常（现有 `JpWordListMod` 已实现，提升到宿主）。
- **身份层**：从 `packs/*/manifest.json` 读注册表，不再硬编码进 DLL。
- **启动安全门**：身份通过轮询确认；迁移期不重复安装旧 `BookNameMod` 已拥有的
  `SonBookChoose` 钩子，语言行为钩子只在对应策略实际装载后安装，离开时移除。
- **作用域门**：现成的 fail-closed 三一致检查，原样保留。
- **路由层**：见 §2.4。
- **接管层**：见 §3.1。

### 2.2 L1 语言包：纯数据，manifest 驱动

```
LocalLow\WCP\packs\
  ja\
    manifest.json
    books\日语词库(猫条版).xlsx
    db\meaning.sqlite         # 释义（原 pron 表）
    db\sentences.json         # 例句 + 中文翻译（原 sentences_master.json）
    db\repair.tsv             # 自愈载荷（原 jp_db_payload）
    audio\word\*.mp3          # 单词音频，按词形命名
    audio\sentence\*.mp3      # 例句音频，按 md5(例句原文) 命名
  fr\ ...
  ru\ ...
  de\ ...
```

`manifest.json` schema（草案）：

```json
{
  "schema": 1,
  "profile_id": "catbar-jlpt-complete",
  "language": "ja",
  "display_name": "日语词库(猫条版)",
  "word_count": 7922,
  "fingerprint_sha256": "6d7a51c0c5d30dd63d8a6e3412bce1cf2419554fb8487cf5c8a205e43ac41663",
  "observed_slot": 1,
  "es3_prefix": "ja",
  "book_layout": "single",
  "strategy": { "assembly": "WcpPack.Ja.dll", "type": "WcpPack.Ja.JapaneseStrategy" },
  "resources": {
    "books":          ["books/日语词库(猫条版).xlsx"],
    "meaning_db":     "db/meaning.sqlite",
    "sentence_table": "db/sentences.json",
    "repair":         "db/repair.tsv",
    "word_audio":     "audio/word/",
    "sentence_audio": "audio/sentence/"
  },
  "repair_probes": ["歯医者", "続ける", "工業"]
}
```

已实作的三份清单在 `packs/{ja,fr,ru}/manifest.json`，字段值全部来自实测。

要点：

- `fingerprint_sha256` **与 `word_count` 一起**是权威身份键，值与现有 `BookProfile`
  逐字节相同。算法不可改：`SHA-256` over「`Trim().Normalize(FormC)` →
  `StringComparer.Ordinal` 排序 → `'\n'` 连接 → UTF-8」。
- **`fingerprint_sha256` 是对 `resources.books` 全部分册的并集去重后算的。**
  日语是单册（`book_layout: "single"`）；法语/俄语各三个分册
  （`book_layout: "fragmented"`），游戏导入后并成一个槽。
  `tools/arch_check.py` 每次运行都会从实际 xlsx 复算并集指纹做比对。
- `observed_slot` 是**实测**槽位（从存档读到的），只用于槽位预算核算与诊断，
  **不作为身份条件** —— 身份只看指纹，所以同一本书导入任意槽都能被认出。
- `es3_prefix` 给运行态键加命名空间。现状是全局 `JpWL_*`，第二个语言接进来必撞车。
- `repair_probes` 必须是该语言插件源码里**真实存在**的探针词
  （ja: `歯医者/続ける/工業`、fr: `être/coing/vaguement`、
  ru: `стол/человек/хорошо/говорить`）。`arch_check.py` 回查源码，防止清单里编造数据。

### 2.3 L2 语言策略：约 150 行的接口实现

**这是"不能做到纯数据"的诚实回应。** 以下 4 类必须留代码：

```csharp
public interface ILanguageStrategy
{
    string Language { get; }

    /// 句子层：从游戏渲染出来的文本里切出"可命名的一段"。
    /// 返回 null = 这句话不属于本语言，宿主不得接管其 ▶ 按钮。
    /// JA=ExtractJa  FR=ExtractFr  RU=ExtractRu（谓词即互斥性来源）
    string ExtractSentenceKey(string renderedText);

    /// 单词层：题干 / 选项的显示形。
    /// JA：题干假名化、选项汉字+中文释义；FR/RU：原形直出
    string StemDisplay(string canonicalWord, string meaning);
    string OptionDisplay(string canonicalWord, string meaning);

    /// 单词音频：题干被改写后，用哪个词形去查音频文件。
    /// JA：假名→汉字临时换回；FR/RU：原形
    string AudioLookupForm(string displayedForm, string canonicalWord);

    /// 查词面板：本地释义 / 注音（宿主自服务，不再查游戏 DB）
    bool ProvideMeaning(string word, out string meaning, out string phonic);

    /// 自愈探针词
    IList<string> RepairProbes { get; }
}
```

把 2,084 行的 fork 差异收敛成这个接口 —— 这就是收益的来源。

### 2.4 路由：显式语言标签，取代内容寻址

```
ResourceRouter.Resolve(kind, key):
    activeLang = ActiveBook().Language      // 来自作用域门，失败则返回 None
    switch kind:
      WordAudio      → packs/<activeLang>/audio/word/<key>.mp3
      SentenceAudio  → packs/<activeLang>/audio/sentence/<md5(key)>.mp3
      Meaning        → packs/<activeLang>/db/meaning.sqlite  WHERE word = key
      Sentences      → packs/<activeLang>/db/sentences.json[key]
```

**关键性质**：语言 A 的代码路径里**不存在**语言 B 的路径字符串。
隔离是**文件系统层面的物理保证**，不再依赖"提取器谓词刚好互斥"这种逻辑巧合。
新增一种拉丁语系语言（德语/西班牙语）不会串音。

---

## §3 三处必须显式处理的约束（只有一处是硬限制）

> **更正（2026-09-14，第二轮）**：本节初版标题写的是「三处**物理上无法解耦**」，
> 那是错的。逐条复核后：**只有 3.1 是硬限制，而且它恰好就是需求本身的语义**；
> 3.2 与 3.3 都是有解的设计约束，3.3 的解法已在下面给出。
> 保留这段更正是为了不让错误论据留在文档里。

| # | 约束 | 性质 | 是否阻碍目标架构 |
|---|---|---|---|
| 3.1 | 运行态是全局单例 | **硬限制**（游戏只有一份内存与一套 UI） | **否** —— "只有被选中的词书才启用"本身就要求串行 |
| 3.2 | 语言策略是行为不是数据 | 设计取舍 | **否** —— 抽成 `ILanguageStrategy`（§2.3），每语言约 150 行 |
| 3.3 | 数据库单文件单主键 | 设计约束 | **否** —— 改用宿主自服务，解法见 3.3 |

### 3.1 运行态是全局单例 → 只能串行（这正是需求本身）

游戏只有一套全局内存：

- `MyParameters.allTestWordsS10_Para`（测试词池）
- `S8needToLearnWordList_Para`（题干队列）
- `S9extraStudy_Para`（自选勾选）
- `exmplesentences` 数组 + 例句 ▶ 按钮是**所有词书共用的一套 UI**

所以"多个语言包共存"是**资源的共存**，不是**运行态的共存**。
同一时刻只有一个语言能接管队列。

宿主必须实现统一的 `TakeoverScope`：

```
进入语言 L 的词书时：
  1. 对每个受管字段 (allTestWordsS10_Para, S8needToLearnWordList_Para,
     S9extraStudy_Para, …) 记录 (字段, 原值) 到 ES3 键 "<prefix>_TAKEOVER"
  2. 把字段改成本书的内容
离开 / 切到别的词书时：
  3. 若原值可用 → 还原
  4. 原值不可用（读不到 / 本身就是本语言）→ 清空队列 + 标记本轮测试已完成
     ※ 绝不能给游戏留 < 5 个词的词池，`GenerateOptions` 会越界崩
```

这套协议 **JP 已经实现并踩过全部坑**（`JpWordListMod.cs` 头部注释 K 段，
v1.7.2 / v1.7.3 两次补漏："游戏内切书"与"基线读不到时 ES3 返回空表"）。
**要求：原样提升为宿主级协议，并把 ES3 键加 `es3_prefix` 命名空间** ——
现在是全局 `JpWL_*`，第二个语言接进来必然撞车。

### 3.2 数据库是单文件单主键 → 必须停止写入

`wcpFullEng.db` 的 `pron` / `sentence2` 都以 `word` 为主键。
四语言同时写入 → 跨语言同形词互相覆盖（法语实测 1,638/8,116 与英语同形）。

**否决方案**：按语言分表（`pron_ja` / `pron_fr`）。
理由：游戏侧查询代码不受我们控制，改表名等于全面 patch 游戏的 SQL，脆弱且不可维护。

**采纳方案**：宿主自服务。查词/例句不再从游戏 DB 取，宿主按
`(activeLang, word)` 从 pack 读取，并 patch 查词面板与例句渲染的返回值。
依据：`JpWordListMod.cs` 的 M① 段已经在做这件事的雏形
（"受管词书下改用本书释义，音标位填假名读音"）—— 已经是同一个形状，泛化即可。

副作用：`HealExampleDatabase`（自愈写库）整个机制变成**历史遗留**，可以退役。
顺带消除 2026-09-14 审计发现的**例句音频 386 条契约漂移**问题：
根因是"写进游戏 DB → 游戏渲染文本 → 反推 md5"这条链路里，
中文译文含全角括号时被 `rfind('（')` 误切。停止写 DB 就直接从根上断掉这条链路。

### 3.3 原生槽位只有 4 个，逻辑槽位扩展到 20 个

原生游戏字段仍只有 `SelfBookList1..4`，运行态也只能选择其中一个。
`CustomSlotsMod` 把可见管理面提升为 20 行：状态保存在自己的 JSON，已有原生书导入为
`external`，只有 manifest/种子标记为 `managed` 的词书才获得本 mod 的资源服务。
这解决了用户目录上限，同时不伪造游戏内部第五个字段，也不覆盖其它自定义词书。

另注：`SelfBookMeaningDictionary` 靠**精确书名**匹配，
所以路由不能改书名，只能按名字识别（`BookNameMod` 已正确实现：只改显示、不动落盘值）。

---

## §4 迁移路径（分 4 阶段，每阶段独立验收）

原则：**每阶段都不破坏现有可用状态**，且不依赖后续阶段。

### 阶段 0（已完成）— 身份层
`BookProfile` + SHA-256 指纹 + 负面识别 + fail-closed 门。保留，不动。

### 阶段 0.5（已完成，见 §9）— 清单数据化 + 宿主骨架
`packs/*/manifest.json` 四份落地（值全部实测）→ `mod_host/` 宿主核心
（注册表 / 路由 / 策略接口 / 反射适配）→ 编译通过 → `tools/arch_check.py` 机检。
游戏外回归已通过；运行目录仍以已验证的旧宿主作为可恢复基线。

### 阶段 1 — 资源命名空间化（低风险，收益最大）
1. `BookProfiles.cs` 收敛为**单份共享**（消除 FR/RU 的 3 副本漂移）。
2. 例句音频：`sentence_audio\` → `packs\<lang>\audio\sentence\`。
3. 单词音频：三语言统一私有 `packs\<lang>\audio\word\`；
   **停止把日语音频倒进游戏原生 `vocabulary\`**。
4. 安装器支持 `--lang <code>`，只写自己的 pack 目录。
5. 迁移脚本：把现有共享目录里的文件按语言分流到各自 pack。

验收：德语包（纯拉丁）与法语包同时安装，法语词书下点例句 ▶ 播放的是法语音频。
**不动游戏 DB，不动运行态协议。**

### 阶段 2 — 抽宿主（进行中）
1. 新建 `WcpHost.dll`：合并三套补丁点 + 反射适配层。
2. 语言策略实现 `ILanguageStrategy`，编成 `WcpPack.<Lang>.dll`（JA 已落地，FR/RU/DE 待迁移）。
3. 注册表外置到 `packs\*/manifest.json`。
4. 保留作用域门与接管协议，接管键加 `es3_prefix`。
5. 启动阶段只做身份轮询；策略存在且身份确认后才接入行为补丁。无宿主自有接管标记时，
   残留清理不得向 `MyBook.es3` 写空标记。

验收：删除任一语言包，其余语言功能无损；宿主日志不含任何语言专属字符串。

### 阶段 3 — 切断 DB 依赖（风险最高，需实机验证）
1. 宿主自服务查词面板与例句渲染。
2. `HealExampleDatabase` 退役。
3. 从 `wcpFullEng.db` 移除已注入的语言内容，恢复到干净游戏原版。

验收：干净游戏原版 DB 下，日语词书查词/例句/音频全部正常。

### 阶段 4 — 接入第 5 语言（验证架构）
用一个纯拉丁语系语言（德语）走完整流程，验证：
新增一种语言**不需要修改任何现有语言的代码**，只需要：
`manifest.json` + 数据 + 一个 `ILanguageStrategy` 实现。

---

## §5 验收标准（已机检化：`tools/arch_check.py`）

下表 1–8 条已实现为可执行检查，`python tools/arch_check.py` 一条命令跑完；
退出码 0 = 无 FAIL。首次运行结果见 §9。

| # | 检查 | 命令 / 方法 | 期望 |
|---|---|---|---|
| 1 | 宿主无语言专属标识 | `arch_check.py` [5]：去注释后扫 `mod_host/**/*.cs` | 0 命中 |
| 2 | 路由无跨语言路径串 | `arch_check.py` [6]：扫 `ResourceRouter.cs` 的共享/他语言路径常量 | 0 命中（路径全来自 manifest） |
| 3 | 清单字段完整且身份唯一 | `arch_check.py` [1][2] | 无缺字段；id/语言/指纹/词数/槽位均不重复 |
| 4 | 指纹可从载荷复算 | `arch_check.py` [3]：读实际 xlsx，算并集去重指纹 | 与 manifest 声明逐字节相同 |
| 5 | 清单数据不是编造的 | `arch_check.py` [7]：探针词回查插件源码 | 全部命中 |
| 6 | 注册表漂移可见 | `arch_check.py` [4]：各项目注册表 vs 全部语言包 | 无缺失（**当前 2 条 FAIL**） |
| 7 | 补丁点固定 | 统计宿主 `Harmony.Patch` 调用数 | 不随语言数量增长（阶段 2 后才有内容） |
| 8 | 作用域门 fail-closed | `Host.cs::Evaluate()` 三分支（空词表/书名不一致/指纹不命中） | 一律返回未激活 |
| 9 | 跨语言不串音 | 装 2 种拉丁语系语言，互相切换 | 例句/音频/释义各归各（阶段 1 后验证） |
| 10 | 游戏更新可恢复 | 用原版 `wcpFullEng.db` 覆盖 | 全部功能正常（阶段 3 后验证） |

---

## §6 否决方案

| 方案 | 否决理由 |
|---|---|
| 按语言分表写游戏 DB（`pron_ja`/`pron_fr`） | 游戏侧 SQL 不受控，等于全面 patch 查询逻辑，脆弱 |
| 语言包做成纯数据、零代码 | 4 类行为逻辑无法数据化（§2.3），强行做会变成"配置里塞代码" |
| 多语言运行态并存 | 游戏内存是全局单例，物理上不可能；只能串行 + 接管-还原 |
| 保留共享 `sentence_audio\`，靠提取器谓词互斥 | 逻辑巧合式隔离。新增同字母系统语言即失效（§1.2 #2） |
| 改名区分词书身份 | 会切断 `SelfBookMeaningDictionary` 的加载路径（精确书名匹配） |

---

## §7 改动量估算与收益

| 项 | 现状 | 目标 |
|---|---|---|
| 插件 DLL 数 | 4 语言 × 3 = **12** | 1 宿主 + N 策略（4 语言 = 5） |
| 接入逻辑代码 | ~11,700 行（80% 重复） | ~1,500 行宿主 + 4 × ~150 行策略 |
| 新增一种语言 | 改 3 个插件源码 + 重编全部 DLL | 加数据 + 写 1 个 manifest + 1 个策略类 |
| 资源隔离 | 逻辑巧合（谓词互斥）+ 3 套不一致策略 | 文件系统物理隔离 |
| 游戏 DB 依赖 | 写入 `pron`/`sentence2`，更新即被覆盖 | 不依赖，更新无损 |

---

## §8 未验证边界（不声称）

- 阶段 3（宿主自服务）的实机表现**未验证**。风险最高，需要干净 DB 上跑完整流程。
- 德语策略的具体差异面**未逐行读完**（德语项目目前只有数据管线，插件目录为空）。
  差异量只对 JA/FR/RU 三对做了实测 diff。
- 运行态接管协议在多语言间切换的**完整矩阵未验证**（JP 单语言路径已有实机依据）。
- 槽位上限 4 的**代码侧**依据已坐实（`_slotProfiles[4]` + 硬编码字面量 + 存档 4 条
  `SelfBookListN`）；**未做"导入第 5 本书"的实机验证**。
- v0.2.0 宿主曾做过一次真实启动尝试；旧版固定行为接线触发后出现 Unity 原生
  `amdxx64.dll → d3d11 → UnityPlayer` 崩溃（Windows 事件为 `0xc0000005`），
  没有托管异常证据。随后加入启动门控、取消与旧 `BookNameMod` 的重复选书钩子，
  并恢复旧宿主作为运行基线；俄语→法语切书矩阵仍未宣称通过。
- 当前运行目录不是新宿主的验收结果：源码 DLL 和 pack 仍保留在工作区，必须在游戏完全退出后
  重新部署并采集新日志，不能用 DLL 哈希替代实机行为证据。
- 审计期间 `LocalLow\WCP\wcp\` 目录计数持续变化（19,141→19,196），
  且 `俄语A1A2/B1/B2.xlsx` 的 mtime 落在本轮勘查时间窗内（07:31），
  **存在第二方进程并发写入**，部分读数可能是中间状态。

---

## §9 已交付增量（2026-09-14 第二轮）

不是设计稿范围之外的东西——这些是**已经落在磁盘上、可运行、可复算**的部分。

### 9.1 新增文件

| 路径 | 内容 | 状态 |
|---|---|---|
| `mod_host/Core/Json.cs` | 极简 JSON 解析器（C#5，无外部依赖；游戏只带 netstandard，没有 Newtonsoft） | 已编译 |
| `mod_host/Core/Manifest.cs` | `BookProfile` / `LanguageManifest` / `BookRegistry`；指纹算法与 `BookProfiles.cs` 逐字节一致 | 已编译 |
| `mod_host/Core/ResourceRouter.cs` | `(lang, kind, key)` → 物理路径；未激活一律返回 `null`，**不回退到别的语言** | 已编译 |
| `mod_host/Core/ILanguageStrategy.cs` | 语言策略接口与可选 pack 绑定扩展，逐条注明现有 fork 版本里的对应行号 | 已编译 |
| `mod_host/GameAdapter.cs` | 反射封装；字段/方法消失只记日志不抛异常（沿用它 L 段的约定） | 已编译 |
| `mod_host/Host.cs` | 宿主插件 v0.2.0：身份轮询、策略门控、作用域接管与可逆行为补丁 | 已编译，实机门控待验 |
| `mod_host/build.cmd` | 构建脚本，已实作编译通过（`WCP_NO_DEPLOY=1` 时不部署） | BUILD OK |
| `packs/{ja,fr,ru}/manifest.json` | 三份语言包清单，字段值全部来自实测 | 已复算验证 |
| `tools/arch_check.py` | §5 验收的机检实现，退出码 0 = 无 FAIL | 已运行 |
| `tools/gen_bookprofiles.py` | 从清单生成 `BookProfiles.cs`（7 份副本收敛为同一生成物，sha 一致） | 已运行 |
| `tools/privatize_audio.py` | 共享音频按语言分流到 `packs/<lang>/audio/`（copy 不 move、幂等、默认 dry-run） | dry-run 已验证 |
| `mod_host/tests/RegistryTest.cs` (+`run_registry_test.cmd`) | 身份与策略回归：游戏外引用同一 `WcpHost.dll`，输入是真实 packs 与真实存档 | 全部通过 / exit 0 |

新宿主 DLL 已在工作区构建，`packs/{ja,fr,ru}/manifest.json` 与日语 pack 已同步到
`LocalLow/WCP/packs/`；一次门控前版本的实机启动曾触发原生 D3D11 崩溃，故游戏目录当前
恢复为旧宿主备份，源码改动和崩溃版 DLL 均保留在 `work/tmp/host-deploy-backup-20260914/`。
该状态不等于统一宿主已完成游戏内切书验收。

### 9.2 首次 `arch_check.py` 运行结果

```
[1] 语言包清单 ................... PASS  3 个清单字段完整
[2] 身份唯一性 ................... PASS  id/语言/指纹/词数/槽位均唯一
[3] 指纹复算（从实际 xlsx 算并集）.. PASS  ja 7922 / fr 8116 / ru 8451，三者指纹全部吻合
[4] 跨项目注册表漂移 ............. FAIL  2 条（见下）
[5] 宿主语言无关性 ............... PASS  6 个源文件去注释后无语言专属分支
[6] 路由无跨语言路径串 ........... PASS  0 命中
[7] 探针词回查源码 ............... PASS  10 个探针词全部见于源码
[8] 构建产物 ..................... PASS  WcpHost.dll 存在；未部署

结果: 2 FAIL / 0 WARN
```

### 9.3 两条 FAIL 是真问题（fork 架构的直接代价）

```
FAIL 4.1: Japanese 项目注册表（sha256=a7f3dd58）缺 ['catbar-russian-cefr-complete']
FAIL 4.1: French   项目注册表（sha256=a7f3dd58）缺 ['catbar-russian-cefr-complete']
PASS 4.2: Russian  项目注册表（sha256=767adff6）登记齐全
```

日语与法语项目的注册表**不知道俄语词书的存在**；俄语项目的注册表知道全部三种。
同一项目内的多份副本倒是逐字节一致（`4.3` PASS），所以不是副本损坏，是**跨项目不同步**。

- 当前危害**有限**：识别是 fail-closed 的（只碰自己的指纹），缺条目只会让日语插件
  把俄语书当成"未知"从而不接管 —— 安全。
- 但它把 fork 架构的**结构性代价**摊开了：**每加一种语言，其它语言项目的 3 个 DLL
  都得重编译**，否则注册表就残缺。三语言尚可忍，五语言就是 15 个 DLL 的重编译与回归。
- 这正是宿主方案要消掉的东西：注册表改成从 `packs/*/manifest.json` 读之后，
  加语言不再需要碰任何现有语言的代码。`arch_check.py` [4] 会一直盯着这条。

### 9.4 下一步（按风险从低到高）

1. **阶段 1**：音频目录按语言私有化（改路径 + 迁移文件 + 安装器支持 `--lang`）。
   不动 DB、不动运行态协议，却是唯一能让"新增拉丁语系语言就串音"归零的改动。
2. 把 `BookProfiles.cs` 换成从 manifest 读（消掉 §9.3 的两条 FAIL）。
3. **阶段 2**：把三个插件的补丁点搬进宿主，语言差异搬进 `ILanguageStrategy`。
4. 部署 `WcpHost.dll` 进游戏，验证 v0.1.0 的识别与作用域门（需游戏关闭）。

### 9.5 第三轮执行结果（2026-09-14，用户批准后）

上表 4 项中 **2 项完成、1 项半程、1 项未动**：

- **[2] 注册表收敛 → 完成。** `gen_bookprofiles.py --write` 从三份清单生成单一
  `BookProfiles.cs`，JA/FR/RU 全部 7 份副本 sha 一致（`04afa538…`）。
  `arch_check.py` [4] 的 2 条 FAIL 清零，现在 **0 FAIL / 0 WARN**。
  语义等价已先验证：生成物与俄语原版条目集合、方法体逐行一致（仅注释差异）。
- **[4] 部署 + 游戏外回归 → 完成。** `RegistryTest.exe` 用真实 `MyBook.es3`：
  3 槽指纹与清单逐一对上、空槽 fail-closed、唯一性矩阵无歧义，15 PASS。
  编译耗时 4 分钟是杀软对新生成未签名 exe 的首扫，非代码问题（复跑同慢，结果一致）。
- **[1] 阶段 1 → 半程。** JA 例句插件已加 pack 优先 + legacy 回退并部署
  （pack 目录不存在时行为与旧版完全等价）；`privatize_audio.py` dry-run 验证：
  三语言例句 md5 **交集为 0**（隔离假设成立）、JA 56,661 / FR 24,328 / RU 13,876、
  冲突 0、孤儿 9,588（英语原生）。**`--write` 被真实写入者阻塞**：俄语项目的
  `gen_sentence_audio_ru.py` 仍在往共享 `sentence_audio/` 写（08:37 采样 12s +56 文件），
  批量分流必须等它停。
  附带发现：JA 词表插件**没有自己的音频目录解析**——它只 Harmony 修
  `PlayWordAudio` 的假名↔汉字形，播放走游戏原生 `vocabulary/`，
  所以"pack 优先"对它不适用，单词音频的 pack 化归宿主接管（阶段 2）。
- **[3] 阶段 2 → 未动。**

回滚：删 `BepInEx/plugins/WcpHost.dll` 与 `LocalLow/WCP/packs/` 即回到部署前状态；
JA 例句插件的新 DLL 在 pack 目录为空时与旧版行为一致，无需回滚。

### 9.6 第四轮执行结果（2026-09-14，本轮）

本轮继续把宿主从“能识别”推进到“可安全承载策略”的机制层，仍不接管旧插件的
Harmony 行为，也不部署到游戏目录。

- **清单运行时校验补齐。** `Manifest.cs` 现在拒绝不支持的 schema、空身份、非法
  指纹、越界槽位、缺资源字段和 pack 外路径；`BookRegistry` 同时拒绝重复的
  `profile_id`、语言、指纹、词数和槽位。静态 `arch_check.py` 之外，游戏内加载器
  也 fail-closed。
- **资源路由修正。** `ResourceRouter` 的单词/例句音频路径现在先解析 manifest
  的 pack 相对目录，再生成绝对路径；未激活、空 key 和 `..` 越界路径一律返回
  `null`。此前音频路由会把 `audio/word/` 当作当前工作目录，这是一个实际的
  可用性 bug。
- **策略装载边界落地。** 新增 `mod_host/StrategyLoader.cs` 与
  `Core/StrategyContext.cs`：只从当前 pack 内的 `strategy.assembly` 反射加载
  `ILanguageStrategy`，校验类型和 language 码，并把 manifest 已校验的资源绝对路径
  注入实现 `IPackBoundStrategy` 的策略；缺失或不匹配只阻止该策略，不影响其它清单
  的身份层。
- **回归测试去除三语言硬编码。** `RegistryTest` 已覆盖当前 1–4 个语言包、四槽
  指纹矩阵、未激活 fail-closed、pack 内资源路由和越界拒绝；德语加入后不再因
  “必须正好 3 个包”产生假失败。
- **四语言验收纳入。** `arch_check.py` 已能从 `D:\German\output\import` 复算
  德语 3,488 词指纹，并检查德语自愈探针；德语生成模板已修正残留的法语探针。

本轮结果：`RegistryTest` 全部通过，其中包含真实加载 `packs/ja/WcpPack.Ja.dll`、
嵌套译文括号回归、pack 内 `pron` 查询、假名音频回查和未收录词 fail-closed；
`WcpHost.dll` 与 JA 策略 DLL 均编译通过；日语 pack 的 7,922 条释义、30,894 条例句
已物化为独立资源。未完成/未声称的仍是：宿主 Harmony 接线、FR/RU/DE 策略迁移、
宿主新 DLL/德语 manifest 的游戏目录部署，以及游戏内四语言切换和音频行为。

### 9.7 第五轮执行结果（2026-09-14，本轮）

- `IPackBoundStrategy` + `StrategyContext` 将策略与资源路径解耦；策略只能使用当前
  manifest 解析后的 `MeaningDbPath` 等路径，不能猜测其它语言目录。
- 新增 `mod_host/strategies/JapaneseStrategy.cs` 与 `build_ja.cmd`。策略迁移了日语
  句子键提取、假名题干、汉字选项、假名到汉字音频回查和本地 `pron` 查词；句子提取
  修复中文译文嵌套全角括号导致的旧 `rfind('（')` 契约漂移。
- 新增 `tools/build_pack_ja.py`，从已校验的 `jp_db_payload` 生成 `meaning.sqlite`、
  `sentences.json`、`repair.tsv` 和日语词书副本；不访问、不修改游戏目录数据库。
- `RegistryTest` 现在引用与游戏相同的 `WcpHost.dll`，并实测装载 JA 策略；为离线 SQLite
  回归只复制测试所需的游戏 provider/native sqlite 到临时目录，不部署任何 DLL。
- 本轮验证：宿主 BUILD OK；JA 策略 BUILD OK；`RegistryTest` 全部通过；身份/指纹/路由
  静态检查均通过，`arch_check.py` 的唯一预期 FAIL 是游戏目录仍是旧版 `WcpHost.dll`，
  因本轮明确没有部署。

### 9.8 第六轮执行结果（2026-09-15，安装与隔离交付）

- 日语词/句音频已从历史共享目录按语言分流到 `packs/ja/audio/{word,sentence}`；
  日语质量校验为 15,812/15,812 词音频命中、56,941 个例句音频可迁移，缺失为 0。
- 日语一键包现在实际携带 `WcpHost.dll`、`CustomSlotsMod.dll`、`packs/ja` 元数据/策略，
  安装脚本合并写入 `LocalLow/WCP/packs/ja`，不删除其它语言 pack；音频 ZIP 只包含日语词表文件。
- `probes/test_isolation_contract.ps1` 当前 19/19 通过；安装包发布检查确认单词 ZIP 15,812 文件、
  例句 ZIP 56,941 文件；核心包为 `WCP-Japanese-OneClick-Installer-wcp-jp-v1.2.2.zip`。
- 20 逻辑槽位的模型/UI 回归、GitHub 目录发现/选择性安装/峰值磁盘计划/差异更新已有离线与在线检查。
  仍不声称真实游戏内 `Russian → Japanese` 或 `French → English → Japanese → French` 切换矩阵通过，
  需在实际运行目录采集新宿主日志和 UI/战斗证据。

---


## 附录 A：勘查命令

```bash
# fork 差异量
diff --strip-trailing-cr D:/Japanese/mod_jp_wordlist/JpWordListMod.cs \
     D:/French/mod_fr_wordlist/FrWordListMod.cs | grep -cE '^[<>]'

# 补丁点
grep -nE '\[HarmonyPatch|Harmony\.Patch' mod_*/*.cs

# 共享资源目标
grep -nE 'vocabulary|sentence_audio|_db_payload|_word_audio' \
     D:/French/installer/Install-WCP-French.ps1

# 身份注册表
cat mod_book_name/BookProfiles.cs
```

## 附录 B：相关文档与产物

- `IMPLEMENTATION.md` — 复刻契约（当前 fork 架构的完整说明）
- `wcp_wordbooks/AUDIT-2026-09-14.md` — 2026-09-14 审计与核对记录
- `wcp_wordbooks/README.md` — 逆向契约
- `packs/{ja,fr,ru}/manifest.json` — 已实作的语言包清单（§9.1）
- `mod_host/` — 宿主骨架，已编译（§9.1）
- `tools/arch_check.py` — 本文 §5 的机检实现，随时可跑
