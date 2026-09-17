# WCP 多语言词书 — 跨会话任务清单



> 生成时间：2026-09-15（状态快照基于本机只读复核）

> 唯一提交目标：`hanserdesu/WCP-MultiLanguage`（`D:\ATooManyLanguage\MultiLanguage`）

> 本文件是**唯一的待办真相**：每完成一项就把该项改成 ✅ 并附验收命令的实际输出。



> **2026-09-15 13:40 远端实测**：GitHub `hanserdesu` 名下现仅存 `japanese`、`WCP-MultiLanguage`、`-invalid-name-`

> 三个仓库；本地 French / German / Contonese / hub 四仓的远端（`WCP-*-Wordbook` / `WCP-Wordbook-Hub`）已被删除

> （push 返回 404，已用存储凭据查 API 确认非凭据问题）。四仓 2026-09-15 下午的本地提交已保留

> （French `87624ff`、German `bde55cf`、Contonese `65f6eac`、hub `cf661b3`）。

> 后续对外分发只走 `WCP-MultiLanguage`；这四个本地仓视作工作副本/历史归档。



---



## 0. 原始需求 → 当前完成度



| # | 用户需求 | 状态 | 一句话结论 |

|---|---|---|---|

| R1 | 法语战斗里都是英语：是 bug 还是语言相似 | 根因已定，**修复未生效** | 确认是 bug（全局 `HaveLearnedDictionary` 补池 + 20.2% 同形词）；宿主修复路径因为 fr 资源包不完整而没被激活，仍在跑旧插件兜底 |

| R2 | 俄语切日语后仍出现俄语 | 根因已定，**部分修复** | 5 个插件同时写同一份全局词池；`YieldToHost` + `managed.txt` 已把 ja/yue 收敛到宿主，fr/ru/de 仍在旧插件竞争 |

| R3 | 各语言资源解耦，只向下提供资源接口 | **9/9 资源包落地** | `LocalLow\WCP\packs\` 现有 9 个语言包，各自含 manifest+db+books+audio，全部走宿主通用策略（ja/yue 自带策略 DLL） |

| R4 | 以后加语言只提供资源，不反复跑测试 | **契约已落实并被机械验证** | `pack.build.json` + `$host` + 自动发现（probe 不再硬编码语言名）；es/pt/ko/ar 正是用这套流程加进来的，未改 probe 与宿主语言分支 |

| R5 | 自定义槽位 4 → 20 条，同页滚轮选择和管理 | ✅ 功能实现（实机待验）｜**UI 形态未收敛** | 20 行模型 + 滚轮滚动页 + 行内改名/移除/刷新 + 原生 4 本镜像行（P1-1/P1-2 已修）。但呈现方式是**自绘深色覆盖层**（自建 Canvas/字体/按钮/Toast），不是"原生一模一样、只多一个滚动条"——见 P1-15 |

| R6 | 20 条也可给其它自定义词书用，本 mod 只服务自己范围 | ✅ 代码+离线测试（实机待验） | 服务边界落进宿主：指纹命中之外还必须在 20 槽 store 有登记行（托管播种行/原生镜像行）才服务；未登记/已移除 fail-closed，store 缺失按兼容回退。见 P1-4 |

| R7 | 安装时从我的 GitHub 仓库自动判断可用词书 | **已实现且测试通过** | 在线发现 + `-List` + 编号选择；9 本词书 catalog 全 available |

| R8 | 一键安装器：可选安装哪几本 | **已实现且测试通过** | `-Books fr,ja` / 交互编号 / `all`；51 项离线测试全过 |

| R9 | 按所选词书判断峰值磁盘与兼容性 | ✅ 已实现并验证 | `-Plan` 峰值 = 下载 + 解压 + 预留 512MB；`catalog.json` 与 hub 副本（installer 包内）9 行 `disk.extract_mb` 完全一致（P1-8 已完成：hub 改为 ML catalog 生成副本）；fr 端到端实测"下载 589.9MB / 解压 582MB"与 catalog 数字一致 |

| R10 | 更新资源：比对同仓库差异、只下有差异的 | ✅ 已实现并端到端验证 | -Update 按 sha256 精准差异下载；新增磁盘健康核对：state 与磁盘背离（删文件/损坏）时摘除记录全量重下自愈，真实 GitHub 下载端到端验证。见 P1-9 |



---



## 1. 本轮**已验证通过**的东西（不要重做，别当 bug 修）



命令与实测输出：



| 断言 | 命令 | 结果 |

|---|---|---|

| 安装器离线单测 | `powershell -File tests\test_hub.ps1` | 51 通过 / 0 失败 |

| 宿主目录单测（用仓库自身 packs） | `mod_host\tests\run_registry_test.cmd D:\ATooManyLanguage\MultiLanguage\packs` | 全部通过：4 槽指纹 ja/fr/ru/de 全中、唯一性矩阵 4×1、pack 内路由、越界拒绝 |

| 接管范围单测 | `powershell -File mod_host\tests\run_takeover_test.ps1` | Failures: 0 |

| 20 槽行为规则 | `powershell -File mod_custom_slots\tests\run_custom_slots_test.ps1`（`test_custom_slots.ps1`） | 8 通过 / 0 失败 |

| 语言工程集成一致性 | `python tools\verify_integration.py` | PASS (9 languages) 无缺无差 |

| pack 物化一致性 | `python Japanese\tools\build_pack.py --check-all D:/ATooManyLanguage`（**需 openpyxl**） | PASS：ja 7922 / fr 8116 / ru 8451 / de 8062，指纹逐字节吻合 |

| 音频资源发布 | `MultiLanguage\tools\release\published-releases.json` | 9 语言全部 `published: true`，每项带 size+sha256 |

| 已部署 DLL = 仓库构建 | `sha256sum` 对比 | `WcpHost.dll 7baf8bc1…`、`CustomSlotsMod.dll 557fc271…` 与 BepInEx\plugins 完全一致 |

| 20 槽模型确实是 20 行 | 反射读已部署 DLL | `SlotRules.MaxSlots=20 NativeSlots=4 MinimumPlayableWords=5` |

| 旧插件已让位 + 词池根因修复已编进 DLL | `python` 扫 `FillFromBookProgress` | 已部署的 FR/RU/DE/YUE 词表 DLL 均含该修复 |



**已知假失败（别浪费时间追）**：`probes\test_isolation_contract.ps1` 的 `pack_data_matches_specs` 只有在 PATH 上的 python 装了 openpyxl 时才真跑；hermes venv 里没装，会报 FAIL。用系统 Python 3.12（`C:\Users\hanserdesu\AppData\Local\Programs\Python\Python312\python.exe`）跑就只剩真 FAIL。



---



## 2. P0 — 阻塞"资源隔离"这条主线的任务



### P0-1 让 fr / ru / de 真正进入宿主受管模式（R1 的关键） — ✅ 数据半场已完成（2026-09-15）

**当时证据**（`BepInEx\LogOutput.log` 09:12 场次）：

```

WcpHost: 受管语言登记 = [ja,yue]

WcpHost: 语言包资源未就绪, 本次不接管（旧插件继续兜底）: fr 缺 db/meaning.sqlite; ru 缺 db/meaning.sqlite

```

游戏目录 `%USERPROFILE%\AppData\LocalLow\WCP\packs\fr` 与 `packs\ru` **只有 manifest.json**。



**已做**：

1. `tools/sync_packs.py`（新）把 9 个语言工程的 `packs/<lang>` 逐字节同步进仓库；`--check` 作门禁，已进 probe。

2. 仓库 fr/ru/de manifest 的策略从**不存在的** `WcpPack.Fr/Ru/De.dll` 统一回 `$host`。

3. **es/pt/ko/ar 四个语言包全新物化**（此前完全没有）：es 8600 / pt 8600 / ko 3123 / ar 8118，

   `build_pack.py --check-all` PASS（词书并集、指纹、释义数、例句数逐项吻合）。

4. 游戏 `LocalLow\WCP\packs\` 现有 **9 个语言包**，每个都有 `manifest.json` + `db/{meaning.sqlite,sentences.json,repair.tsv}` + `books/` + `audio/{word,sentence}`。

5. 例句音频（9 语言 228,683 个文件）与单词音频（7 语言 52,000 个）已私有化到 `packs/<lang>/audio/`。

6. 注册表扩到 9 语言（13 份 `BookProfiles.cs` 副本 sha 一致）；宿主日志实测 **加载到 9 个语言包，0 告警**。



**✅ 安装器 → packs 布局已接通（2026-09-15 下午，P1-3/P1-6 联动）**：统一安装器新增 core zip（`pack` 资产，pack 布局去 audio）与 `slot_manifest` seed 资产，发布进各语言资源 release（ja 在 `japanese` 仓 `wcp-jp-resources-v1.0.0`，其余在 ML 仓 `wcp-<lang>-resources-v1.0.0`），catalog 九行同步补齐。干净沙箱 `-Books fr` 实跑：`packs/fr` 完整布局（manifest+db+books）+ 音频 8,116/24,328 + `BepInEx\plugins` 三 DLL，`WcpHost.managed.txt` 登记 `fr`。**剩余仅**：实机游戏内切换验收（fr/ru 进受管、法语战斗不再出英语、`WCP Host 0.3.0` 启动日志）。



### P0-2 例句/单词音频在非日语语言也改读 pack — ✅ 代码+数据均已完成（2026-09-15）

**已做**：

1. FR/DE/RU/YUE 四份例句音频插件加 **pack 优先 + legacy 回退**（与日语版同款）：

   Awake 里解析 `packs/<lang>/audio/sentence`，`_packAudioDir` 优先、`_audioDir` 兜底；

   `LocalAudio` 与扫描分支都先查 pack。四语言全部 BUILD OK，新 DLL 已部署到 `BepInEx\plugins`。

2. `tools/migrate_legacy_audio.py`（新，`--kind word|sentence|both`）把 legacy 目录按语言

   私有化到 `packs/<lang>/audio/{word,sentence}`：例句 9 语言 228,683 文件、单词 7 语言 52,000 文件，

   幂等（重跑"待拷=0"），只 copy 不 move（旧插件回退路径继续可用）。

3. probe 新增 4 条 `<lang> sentence_mod_language_clean` 断言。



**P0-2 语言仓侧已入库（2026-09-15）**：French `87624ff` / German `bde55cf` / Contonese `65f6eac`

（例句音频 pack 优先 + BookProfiles 扩 9 语言 + packs/fr|de 入库；probes 41/0 在该状态下复验）。



**剩余**：`packs/<lang>/audio/word` 目前只有宿主会读（`ResourceRouter`）；日语单词音频仍走游戏原生

`vocabulary/`（旧插件路径），单词音频的 pack 化归宿主接管（属阶段 2/3）。



### P0-3 清掉派生链里的法语字面量 — ✅ 已完成（2026-09-15）

**已做**：FR/DE/YUE 三份 `SentenceAudio*Mod.cs` 的 `ManagedFrenchBookSelected()` 全部改名 `ManagedBookSelected()`（12 处），日志 `(FR)` 移除；DE/YUE 补 `build.cmd`（模板生成）；三语言重新构建 BUILD OK，新 DLL 已确认不含旧标识符。probe 新增 `<lang> sentence_mod_language_clean` 断言。

**验收**：`probes\test_isolation_contract.ps1` → **40 passed, 0 failed**。已提交：ML 仓库 `d1c892f`、probes 仓库 `97f81fa`、French/German/Contonese 仓库各 1 commit。



### P0-4 修 `pack_specs_present` FAIL（R4 的验证图）— ✅ 已完成（2026-09-15）

**已做**：probe 项目列表改为目录自动发现（根目录下带 `packs\` 且无顶层 `Install-WCP-Wordbooks.ps1` 的目录；hub/ML 分发仓库自动排除）；manifest 按 `strategy.assembly` 分类——资源包（`$host`）必须有 `pack.build.json`，策略包（ja/yue，自带 DLL）免 spec；新增双向校验（非策略语言带 DLL / 策略语言缺 DLL 都报 `pack_strategy_resource_only` FAIL）。

**验收**：有 openpyxl 环境 → **40 passed, 0 failed**；无 openpyxl 环境 → `pack_data_matches_specs` 显式 SKIP（不再是假 FAIL）。



### P0-5 切断游戏 DB 依赖（阶段 3，风险最高）

**现状证据**：`wcpFullEng.db` 里仍有注入内容 —— `pron` 表 `歯医者`=1、`être`=1；`sentence2` 表 `歯医者`=4（`pron` 99,748 行 / `sentence2` 312,570 行）。`HealExampleDatabase` 未退役。

**要做**：宿主自服务查词/例句 → 退役自愈写库 → 用原版 DB 覆盖验证。**完成判定**：干净 DB 下日语查词/例句/音频全正常，且 DB 无任何非英语词条。



---



## 3. P1 — 20 槽位（用户要"选择 + 管理 + 给别的词书用"）



### P1-1 20 行现在**全是空**，原生 4 本书没被导入 — ✅ 代码+测试已完成（2026-09-15 晚）；✅ 真实根因修复（2026-09-16 凌晨，v1.2.0）

**证据**：`%USERPROFILE%\AppData\LocalLow\WCP\wcp\WcpCustomSlots.json` 内容仅

```json

{ "schema": 1, "selected": 0 }

```

（38 字节，09:12 写入），没有 `slots` 数组，也没有 `native-1..4` 行。

**根因（代码级）**：`CustomSlotsMod.LoadState()` 只有在**读档失败/无文件**时才走"新建 + 导入原生 4 本书"分支（`fresh` + `ReadNativeWords`）；store 文件一旦存在就 `return loaded`，**原生 4 本书永远不会被导入**。



**✅ 已做（2026-09-15 晚）**：

1. **每次加载都导入**：新增 `SlotRules.ImportNativeBooks`（纯模型），`Awake → ImportNativeBooksNow()` 把原生 4 槽词书导入/刷新为外部镜像行（`native-<槽>` 行，owner=external，内容=落盘快照）；镜像行随游戏数据原位更新、首选槽位号落行、被占则落第一空行、20 行全满不挤掉任何词书、托管行占用的原生槽不导入。旧"新建分支导入一次"逻辑已删。

2. **逐出规则（解锁死锁）**：原 `CanUseNativeSlot` 对"非 mod 原生书占用的物理槽"一律拒绝 → 用户装满 4 本原生书时托管书**首次物化必失败**，被逐出的原生书也永远点不回来。新增 `SlotRules.NativeContentTracked`：物理槽实时词表若已被任一行持有（镜像快照/托管词表）→ 内容可恢复，允许接管；从未见过的内容仍 fail-closed。语义从"从不覆盖"精确化为"从不丢失"。

3. **观测日志（解 38 字节之谜）**：`LoadState` 记录 store bytes/rows/selected、存在与否；`SaveState` 记录 bytes/filledRows/selected。下次实机会话即可确认 JsonUtility 序列化是否生效。

4. **store 自愈**已在（`Normalize` 补齐/重建 20 行）。



**✅ 实机诊断定出真根因（2026-09-16 凌晨）**：上面第 3 条的观测日志在实机上直接给出答案，

而且推翻了我原先"只是没导入"的判断——**20 行数据从来没被写进过磁盘**：



| 版本 | 实机日志 | store 文件 |

|---|---|---|

| 1.0.0（当时在跑） | `logical slots=20`（无存档日志，该版本还没有观测代码） | 38 字节空档 |

| 1.1.0（首轮部署） | `store loaded; rows=20` / `store saved; bytes=38; filledRows=4` | 38 字节空档 |

| 1.2.0（加往返自检后） | `serializer round-trip bytes=38; rows=20 -> 0 (LOSS! slots 未落盘)` | 38 字节空档 |

| 1.2.0（改自建序列化后） | `round-trip bytes=306268; rows=20 -> 20 (OK)` | **412,806 字节 / 20 行** |



**真根因（两条，互相独立，均为实机验证而非推测）**：

1. **`JsonUtility.ToJson` 静默丢弃 `SlotRecord[] slots`**。`SaveState` 的 `filledRows=4` 证明内存里

   4 行有词，但它写出的 JSON 只有 `{"schema":1,"selected":0}` —— Unity 的序列化器不支持该形状的

   嵌套数组字段，且不报错。所以哪怕 P1-1 把镜像行导进内存，重启后一样什么都没有。

   修复：序列化搬进不依赖 Unity 的 `SlotRules.Serialize/Deserialize`（自建 JSON 读写、转义、

   未知字段跳过、解析失败返回 `null` 的 fail-closed），`LoadState`/`SaveState`/`MergeSeed` 三处

   全部改走它。这同时把"能不能存住"变成**离线可单测**的事（原先只有实机才能暴露）。

2. **版本没部署**：游戏里跑的是 `CustomSlotsMod 1.0.0`（09-15 08:49），而 P1-1/P1-2 做出来的

   是 1.1.0（09-15 19:43）—— 1.0.0 完全没有原生书导入与改名/移除功能，所以用户看到的本来就该是旧行为。



**另修两个会让 20 行"看不见"的渲染缺陷（同期）**：

3. **覆盖层层级**：原先只 `SetParent` 到游戏 Canvas 下，没有自建 Canvas、没有 `overrideSorting`，

   会被原生 UI 盖住 → 改为自建 Canvas + `sortingOrder 32760` + `SetAsLastSibling`，

   并优先使用入口按钮自身的 Canvas。

4. **字体**：`GetBuiltinResource<Font>("Arial.ttf")` —— Unity 2022.2+ 起内建字体改名，

   该名字在部分运行时抛异常或返回 null，会让整个覆盖层文字不可见（面板在、字没有）。

   改为 `LegacyRuntime.ttf` → `Arial.ttf` → 系统字库逐级回退，取不到时记警告。

5. 原生镜像行显示名回退到游戏规范名（原先会显示成 `native-1`）；新增 `Show` 路径日志，

   使"覆盖层是否被创建"在实机可观测。



**验收**：`powershell -File mod_custom_slots\tests\test_custom_slots.ps1` → **8 通过 / 0 失败**

（静态契约 7 + 行为 harness；`SlotRulesTest.cs` 行为断言 `Failures: 0`，新增 13 条持久化断言：

往返保 20 行 / selected / 托管行 / 原生镜像词表快照、引号反斜杠换行中文转义、截断与非 JSON → null、

未知字段兼容）。`tests\test_hub.ps1` **55/0**。`build.cmd` BUILD OK，

部署到 `BepInEx\plugins` 后 sha256 `e0444370…` 与仓内构建一致；实机 1.2.0 启动日志

`store bytes=306268` / `rows=20 -> 20 (OK)` / `native mirror rows imported=4`，store 412,806 字节含

4 行原生书快照（ja 7922 / fr 8116 / ru 8451 / de 8062，均 `owner=external`）。

**剩余**：实机 UI 目视确认（进"自定义词书"页应看到 20 槽覆盖层面板、第 1–4 行为 4 本原生书

`[外部词书]`、行内有改名/移除按钮）—— 用户选择自行操作，我负责读日志/截图确认。



**2026-09-16 实机复验（1.2.0）发现新缺陷并已修复（1.2.1，MultiLanguage `db2e256`）**：

用户进页后仍只见原生 4 行。日志证明面板**构建成功**（`Show → 新建覆盖层; canvas=CanvasWordCount`）

但 ≤0.25s 被 `轮询 → 离开自定义页，隐藏面板` 藏掉。根因：在学受管书（ja）时 BookNameMod 把

「自定义词书N」行全部改写成「…词库(猫条版)」，`IsCustomPageShowing` 只认「自定义词书」字样 →

判据恒 false。修复：①判据兼容美化名「猫条版」；②UGUI 点击栈（Press/OnPointerClick/Invoke）

记录最后用户点击页签作兜底信号（`CalledFromGameInitialization` 会把真实点击也判成初始化，

不能用来过滤——Unity 事件系统深处有同名 Initialize 帧）；③轮询改 `FindVisibleChooserInstance`

（场景多 chooser 实例）+ `_userDismissed` 防手动关闭后被弹回。离线门禁 11/0 +

harness `Failures: 0`，部署 sha `6b9d1f14…` 与仓内一致。**实机目视确认仍待用户操作。**





### P1-2 缺"管理"（用户明确要）— ✅ 代码+测试已完成（2026-09-15 晚）

**现状**：`CustomSlotsMod` 的公开方法只有 `Show / Hide / RebuildRows / Select / ChooseNativeSlot / Materialize / LoadState / MergeSeed / SaveState`——**只有选择**。



**✅ 已做（2026-09-15 晚）**：同一滚动页每行行内操作 + 面板级工具：

1. **改名**：托管行/空行有 `改名` 钮 → 底部改名栏（InputField，Enter 确认 / Esc 或取消钮关闭）→ `SlotRules.TryRenameSlot`（trim、空名拒绝；**只动本 mod 显示名，绝不写 `SelfBookNameN`**，不切断 `SelfBookMeaningDictionary` 精确匹配）；原生镜像行拒绝改名并 toast 说明（名称跟随游戏数据）。

2. **移除**：`移除` 钮（红色）→ `SlotRules.TryClearSlot`（mod 行清空并复位选中态；托管物化行上报应释放的原生槽，插件把该槽 `SelfBookListN` 清空——内容归本 mod 可安全清；镜像行拒绝移除并 toast 引导去原生界面管理）。

3. **刷新**：面板头部 `刷新` 钮 → 从游戏落盘重读原生 4 槽、刷新镜像行（不动 mod 行）、toast 报告变化行数。

4. **EventSystem 兜底**：无 EventSystem 时自动补建（`EnsureEventSystem`），解决纯 UI 点击无响应风险。



**验收**：同 P1-1（`test_custom_slots.ps1` 8/0，行为断言 54 条 `Failures: 0`，覆盖改名 trim/空名/越界拒绝、镜像行拒绝改名/移除、托管行移除上报释放槽、空行移除不释放）。构建 BUILD OK，部署 sha 一致。

**剩余**：实机 UI 验收（点得动、改名栏输入正常、toast 显示）。



### P1-3 安装器 → 20 槽的种子链路从未接通

**证据**：`Install-WCP-Wordbooks.ps1` 的 `Merge-SlotSeed` 读 `WcpCustomSlots.seed.json`；但 9 本词书的 catalog `assets` 集合只有 `{word_audio, sentence_audio}`（**没有 `slot_manifest`**），游戏目录也没有该 seed 文件。

**要做**：发布 `wcp-wordbook.json` / `slot_manifest` 资产并接进 catalog；安装后 seed → 20 行。**完成判定**：装完 fr 后 20 行里出现 `fr` 行且 `managed: true`。



**✅ 链路与数据已完成（2026-09-15 下午）**：每语言 release 新增 `slot_manifest` 资产（`wcp-<lang>-slot-seed.json`，单 managed 行，词表从 pack db `pron` 复算并**经 manifest 指纹逐字节校验**后生成，见 `tools\release\make_core_assets.py`）；catalog 九行补 `pack`+`slot_manifest` 资产并同步进各 release 的 `release-manifest.json`（在线发现以 manifest 为准）。沙箱 `-Books fr` 实跑：`WcpCustomSlots.seed.json` 落盘且含 managed fr 行（`catbar-french-cefr-complete`，8,116 词，id 与 pack manifest 一致）。**剩余**：seed→20 行 UI 显示依赖游戏内 `MergeSeed()`，归实机验收轮（与 P1-1 原生书导入一并验证）。



### P1-4 "只服务本 mod 范围内词书"缺强约束

**现状**：`Host.Evaluate()` 只做「内存词表指纹 == 落盘槽位指纹」+ 指纹命中注册表；**不看** 20 行表里的 `managed` 标志。隔离目前靠指纹，不靠槽位归属。

**要做**：若语义要求"槽位表标 `external` 的词书不得被服务"，就在 `Evaluate()` 里加一条 managed 归属检查（fail-closed）。**完成判定**：新增单测覆盖"指纹命中但 managed=false → 不接管"。



**✅ 服务边界强约束已完成（2026-09-17，代码+离线测试）**：新增 `mod_host/Core/SlotOwnership.cs`，

`Host.Evaluate()` 在指纹命中注册表之后追加一道**槽位归属门**——词书必须在 20 槽 store

（`WcpCustomSlots.json`）里登记为**托管播种行**（owner=mod, managed=true，来自安装器 seed）

或**原生镜像行**（owner=external, nativeSlot>0，存量用户兼容）才提供服务；行被用户"移除"

或从未登记 → fail-closed 不接管，拒因写进日志（`未激活 · 词书不在 20 槽服务范围…`）。

store 文件不存在（未装 CustomSlotsMod 的老部署）按兼容回退放行，保持旧指纹语义；

store 损坏 → fail-closed，等 CustomSlotsMod 重写后按 mtime 缓存自愈（离线验证）。

指纹对 store 行的 words 快照现算（与 BookRegistry.FingerprintOf 同源），mtime 缓存避免轮询重读 400KB。

配置开关 `Compatibility/RequireSlotOwnership`（默认 true）可一键回退旧行为。

**离线验收**：`mod_host\tests\run_slot_ownership_test.cmd`（新）→ 15/0（缺失放行/托管行/镜像行/

未登记拒绝/移除拒绝/短行忽略/混合表/损坏自愈/空表/缓存）；宿主重编译 BUILD OK 并部署，

sha `aa634786…` 仓内=游戏一致；takeover/registry/custom-slots 全量回归通过。

**剩余**：实机验证（进游戏选 fr → 受管激活；在面板里移除 fr 行 → 宿主日志出现"不在 20 槽服务范围"拒因）。



### P1-5 4 原生槽的硬边界要实测

**现状**：20 行里同一时刻只能有 4 行物化进 `SelfBookList1..4`（运行态串行）；文档自认"未做导入第 5 本书的实机验证"。

**要做**：实测导入第 5 本是否被游戏拒绝/被 mod 正确 fail-closed，并把结论写回 `ARCHITECTURE-UNIFIED.md §8`。



---



## 4. P1 — 安装器（R7–R10）



### P1-6 安装器不装 mod 本体

**证据**：`MultiLanguage\Install-WCP-Wordbooks.ps1` 与 `hub\Install-WCP-Wordbooks.ps1` 里 `dll` 命中 **0**；`WcpHost.dll / CustomSlotsMod.dll / BookNameMod.dll` 只有日语一键包携带（`Japanese\wcp_wordbooks\output\installer_pkg\…\support\payload\plugins\`）。另外 `Install-WCP-Wordbooks.ps1` 的 `$data` 指向 `LocalLow\WCP\wcp`、`$packsRoot` 指向 `LocalLow\WCP\packs`，和游戏实际落盘位置一致——这部分没问题。

**要做**：给统一安装器加 `kind: mod`（或 `plugins`）资产，装宿主 + 20 槽插件；这样"装完 mod 后槽位扩到 20 条"对任何语言都成立。**完成判定**：干净游戏目录只跑统一安装器，`BepInEx\plugins` 出现 WcpHost/CustomSlotsMod，且日志 `WCP Host 0.3.0` 起得来。



**✅ 已完成（2026-09-15 下午）**：catalog 新增顶层 `mods` 块（mod 本体全局，不挂词书行），载荷已发布为 `WCP-MultiLanguage` 的 `wcp-mods-v1.0.0` release（asset `wcp-mods-payload.zip` sha256 `49f3d0f0…`，含 WcpHost/CustomSlotsMod/BookNameMod 三 DLL，BepInEx 相对布局）。安装器新增 `Install-HubMods`：装词书前先把 mod 解到 `<game>\BepInEx`（草稿发布→回读哈希校验→发布，与资源 release 同流程），`hub-state.json` 顶层 `mods` 键记账，`-Update` 仅在版本/哈希变化时重下；在线目录刷新保留 mods 块。顺带修掉存量真 bug：`Expand-HubZip` 的 `ExtractToDirectory($zip,$dest,$true)` 在 PS 5.1（.NET Framework）下第三参是 Encoding 而非 overwrite → **此前在线安装路径从未成功过**（与 P1-9"hub-state.json 从未产生"吻合），现改为逐条目展开 + 越界拒绝。新增 `-DataRoot` 参数（默认不变）用于沙箱端到端。**验收**：ML/hub 测试各 55/0（新增 3 条 mods 断言）；干净沙箱 `-Books yue -Yes -Offline` 实跑：`BepInEx\plugins` 三个 DLL 与仓内规范副本 sha 一致、yue 音频 384+766 文件落位、managed 标记为空（yue 资源未全就绪，语义正确）、state mods/yue 记账正确、重跑幂等全跳过。**未做**：实机 `WCP Host 0.3.0` 启动日志验证（需游戏内确认）。



**✅ v1.1.0 再发布（2026-09-15 晚，随 P1-1/P1-2）**：CustomSlotsMod 升 1.1.0 后重打 mods 载荷并发布 **`wcp-mods-v1.1.0`**（asset 名保持约定 `wcp-mods-payload.zip`，sha256 `7e642997…bf19a`，size 120706；草稿→回读校验→发布的同款流程；旧 v1.0.0 release 原样保留可回滚）。ML catalog mods 块同步 v1.1.0，hub catalog（生成副本）再生成。在线沙箱端到端复验：干净沙箱 `-Books yue`（在线）→ mod 载荷下载 + 哈希校验通过 → `CustomSlotsMod.dll` sha `e68277f8…` 与仓内构建一致 → state.mods 记账 v1.1.0 → 重跑幂等（"mod: 已是最新"）。



### P1-7 三份 catalog 互相矛盾，日语指向不存在的 tag

| 文件 | ja 指向 | fr |

|---|---|---|

| `MultiLanguage\catalog.json` | `wcp-jp-resources-v1.0.0`（存在） | available，url 指向 WCP-MultiLanguage |

| `hub\catalog.json` | `wcp-jp-resources-v1.1.0`（**只有 draft，`git ls-remote` 无此 tag**） | available |

| `tools\release\catalog-assets.json` | `wcp-ja-resources-v1.1.0` | — |

| `tools\release\ja-pin.json` | `wcp-jp-resources-v1.0.0` | — |

**实测**：`git ls-remote --tags https://github.com/hanserdesu/japanese` 只返回 `wcp-jp-resources-v1.0.0`（+ peeled），其它 8 语言的 tag 都在 WCP-MultiLanguage 上。

**要做**：以 `MultiLanguage\catalog.json` 为唯一真相，删除/生成 `hub\catalog.json`（不要手维护两份），并把 `catalog-assets.json`、`ja-pin.json` 收敛成同一次生成的产物。



**✅ hub 侧已完成（2026-09-15 下午）**：ML `ca28468` 重写在线发现（按 `/releases` 的 tag 语言分组、`jp→ja` 映射、按词书 id 索引），8 语言 repo 统一指 `WCP-MultiLanguage`；hub `cf661b3` 把 installer/psm1/tests 与 ML 逐字节对齐、`hub\catalog.json` 改为 ML catalog 的生成副本（9 行，ja 仍指 `wcp-jp-resources-v1.0.0`）。验收：两仓 `tests\test_hub.ps1` 各 51/0，`-List -Offline` 列出 9 本、tag 与磁盘数全对齐，probes `catalog_identity_matches_pack` 41/0。**未做**：`catalog-assets.json` / `ja-pin.json` 仍是独立手写产物（低优先，无消费方冲突）。



### P1-8 `disk.extract_mb` 三处不一致（直接影响峰值磁盘判断）

实测（`zipfile` 逐条读 `file_size`，ZIP_STORED 所以压缩≈解压）：



| 语言 | 实际解压 | ML catalog | hub catalog |

|---|---|---|---|

| fr | 582 MB | 582 ✅ | 2150 ❌ |

| ru | 812 MB | 811 ✅ | 2200 ❌ |

| de | 838 MB | 838 ✅ | 2100 ❌ |

| es | 653 MB | 653 ✅ | 2600 ❌ |

| ja | 2338 MB（v1.0.0 资产） | 2338 ✅ | 1571 ❌ |



**要做**：删掉 hub 那份手写估值；`make_release_manifests.py` 已能算准，把它接进 catalog 生成即可。



**✅ 已完成（2026-09-15 下午）**：hub catalog 改为 ML catalog 生成副本，9 行 disk 数字与实测一致（ja 2338 / fr 582 / ru 811 / de 838 / es 653 / pt 685 / ko 295 / ar 286 / yue 19）。



### P1-9 更新只信 `hub-state.json`，不重算磁盘

**证据**：`Get-WordbookAssetDiff` 只比 `InstalledState` 里记的 sha256；本机 `%USERPROFILE%\AppData\LocalLow\WCP\wcp\hub-state.json` **不存在**（在线安装从未跑过）。

**要做**：`-Update` 增加"抽样/全量重算磁盘哈希"模式（大文件可抽 mp3 计数 + 尺寸），使"用户删了文件/改坏了"也能被修复。**完成判定**：手工删 3 个 mp3 → `-Update` 能补齐。



**✅ 磁盘健康核对已完成（2026-09-17，代码+测试+在线端到端）**：`WordbookHub.psm1` 新增

`Test-WordbookDiskHealth`（纯只读）：对每本**已安装**词书核对 ① pack 骨架

（manifest.json / meaning.sqlite 的 SQLite 头 / repair.tsv / sentences.json）；

② 词表自证——repair.tsv `row+TAB+pron+TAB` 行数 == manifest.counts.pron（9 语言 2026-09-17 实测全等，

漂移即内容损坏）；③ 音频抽样——catalog 带 word_audio 资产的语言检查 `audio/word` mp3 计数

≥ 词数×0.95。`-Update` 前运行：不健康词书从 hub-state.json **摘除** → 差异比对自然把它当

"未安装"全量重下修复（**不删用户文件**，重下覆盖即修复）。

**在线端到端（真实 GitHub 下载）**：构造沙箱——state 记 fr v1.0.0 全资产 sha256 一致但磁盘音频树为空

（本机真实缺陷形态）→ `-Update -Books fr`：`磁盘核对: fr 不健康（单词音频 0 个低于期望 7709…）`

→ 摘除 → 判定"需下载 589.9 MB / 峰值 1171.9 MB" → 逐资产下载+SHA 校验 → 词音频 8,116 +

例句音频 24,328 落位 + vocabulary 镜像 8,116 → state 恢复 4 资产记账 → 二次运行幂等"已是最新，跳过"。

**顺手修复两个被端到端暴露的存量缺陷**：① `Get-HubWorkPath` 现在就地保证 downloads/backups 目录存在

——e3924ad 起全新机器上无人建目录，首次下载必然全部报"未能找到路径…的一部分"（阻断所有新用户，

沙箱实锤后修复）；② 下载读循环 finally 释放 fs/stream/response + tmp 清理改 best-effort

——中途异常原先会把 tmp 文件锁死并让清理在 EAP=Stop 下终止整个安装。

**契约测试**：test_hub 76→87 条全过（健康/行数漂移/缺目录/未安装跳过/-Update 钩子/摘除/目录保证/句柄释放）。



### P1-10 双份安装器维护

`hub\WordbookHub.psm1` 与 `MultiLanguage\WordbookHub.psm1` 逐字节相同（sha `9e098ff6…`），但 `Install-WCP-Wordbooks.ps1` 有 11 行差异（缓存时间戳守卫只在 ML 那份），`tests\test_hub.ps1` 有 20 行差异（47 vs 53 项检查）。**要做**：决定单点（建议 ML 仓库为唯一源），hub 仓库改成 Release 附件或指向 ML 的薄壳。



**✅ 已完成（2026-09-15 下午，cf661b3）**：installer/psm1/tests 三份文件 ML↔hub 逐字节一致；hub 的 51 项测试对 hub 自身 catalog 跑通过。注意：远端 `WCP-Wordbook-Hub` 已删除（见卷首远端实测），hub 仓从此只是本地工作副本，对外入口只剩 ML 仓。



### P1-14 安装器质量回归（ja 实战经验移植）— ✅ 已完成（2026-09-17，ML 提交 1e0e942→e3924ad）

对照 ja 安装器（Install-WCP-Japanese.ps1）逐功能移植到 ML 安装器，全部按「失败不阻断」原则：

| 移植项 | 实现 | 提交 |
|---|---|---|
| 自更新（方案 C） | 版本由 `WCP_INSTALLER_VERSION` 注入；索引 `release-index.json` 挂最新 `wcp-mods-*` release；有新版仅提示、确认才下载；SHA-256 校验通过才解包切换；任何异常不阻断；`-Offline/-Plan/-List` 不检查 | 1e0e942 |
| 启动器 run-installer.ps1 | 版本注入 + AggregateException 内层异常链展开 + 失败预填 GitHub Issue + 窗口保持 | 1e0e942 |
| 打包发布链 | `tools/release/build_installer.py`：EOL 规范化→zip→改版本号→release-index.json→`--upload` 直传→API digest 回读校验 | 1e0e942/665853a |
| 下载临时外置 | `hub_dl_*`/`installer_update_*` 写入 `LocalLow\WCP\wcp_hub_work\downloads`（Steam 云同步范围外），旧位置自动搬出；中断残留启动时兜底清理 | e3924ad |
| 旧包备份（跳 audio） | 覆盖前备份语言包到 `wcp_hub_work\backups\<时间戳>_<lang>`，跳过 audio 子树（每语 1~2 GB 无回滚价值） | e3924ad |
| 备份卫生 | 只保留最近 3 份备份；清理失败只提示 | e3924ad |

已发布 `wcp-installer-v0.1.0`（WCP-MultiLanguage release + wcp-mods-v1.3.0 索引资产，digest 回读一致）。

**存档修复也已完成（2026-09-17 深夜，wcp-installer-v0.1.1，ML 提交 0084b22）**：用户批准后移植 ja 的 TryRepairSaveFile/TryRepairMyBook 全套判据（ES3 `__type` 元数据丢失>5 条 / 开局剧情重置 → 从合格备份恢复；MyBook 无备份时就地补 `__type`）。安全设计：健康存档零触碰（实机两文件实测判定健康、TryRepair 双 False、mtime 不变）；修复前必留 `.corrupt_before_repair.bak`；找不到合格备份不动文件；检查先行于一切写入；任何失败不阻断。C# 源在 `tools/es3_repair_source.cs`（编译验证 + 沙箱端到端：受损恢复 ✓ / 健康跳过 ✓ / in-place 补齐 ✓）。契约测试 71→76 条全过。v0.1.1 已发布（digest 回读一致，mods 索引同步指向 v0.1.1）。


### P1-11 无卸载/回滚

`grep -n "Uninstall|卸载" Install-WCP-Wordbooks.ps1` = 0 命中。**要做**：`-Uninstall -Books fr`（只删该语言 pack 目录 + 注销 managed 语言），保留用户词书本体。



### P1-12 在线发现依赖未认证 GitHub API

本轮实测触发 `API rate limit exceeded for 203.10.99.26`（60 次/小时/IP）。**要做**：支持 `GH_TOKEN`/`-Offline` 主路径、发现失败时静默降级到随包 catalog（已有降级，缺 token 支持与退避提示）。



---



## 5. P2 — 仓库卫生 / 门禁 / 文档



| ID | 问题 | 证据 | 要做 |

|---|---|---|---|

| P2-1 | Japanese 仓库 12 个提交未推、工作区 196 处改动 | `git -C Japanese status`：`master...origin/master [ahead 12]`；staged 删除 `packs/{de,fr,ru}/manifest.json`；` M data/jlpt_n*.csv` | 决定这些结构修复是否入库；否则"只改仓库内容就能扩展语言"的前提不成立 |

| P2-2 | ML 仓库缺 5 个语言的 pack — ✅ 已完成（2026-09-15） | `tools\sync_packs.py` 已入库并执行 9 个工程：仓库现有 ja/fr/ru/de/yue/es/pt/ko/ar 共 9 个 pack，`--check` PASS | ~~待生成~~ 已全部物化 |

| P2-3 | `arch_check.py` 8.3 FAIL — ⚠️ 未复验（本轮改了 packages 后未重跑） | 游戏部署件 `packs\ja\manifest.json` 缺 `book_sha256/source/counts` 三键（源是 `Japanese\packs\ja\manifest.json`） | 统一 manifest 生成器，让三处同源 |

| P2-4 | registry test 默认参数写死别的仓库路径 — ✅ 已完成（2026-09-15） | `RegistryTest.cs` 已删硬编码默认值；`run_registry_test.cmd` 默认传本仓库 `packs\`，显式参数可覆盖。不带参数直接跑 → 全部通过 | ~~默认改成 `..\..\packs` 相对路径~~ 已实现并验证 |

| P2-5 | probe 依赖 openpyxl 未声明 — ✅ 已完成（2026-09-15） | probe 现先探测 `import openpyxl`，缺失时显式 SKIP（并把 `ErrorActionPreference` 临时降到 `Continue`，绕开 PS 5.1 stderr 终止错误） | ~~依赖探测 + skip~~ 已实现并验证 |

| P2-6 | 实机切书矩阵未做 | 日志只有 ja 启动 + 一次接管；`RU→JP`、`FR→EN→JP→FR` 无证据 | 每次结构性改动后跑一次矩阵，报文存 `logs\` |

| P2-7 | 文档分散 | `docs\`（根）之前为空；架构/安装/BUG 复查分散三处 | 本文件 + 把 §8"未验证边界"随验收更新 |



---



## 6. 建议执行顺序（每步都能独立验收）



```

第1步  P0-2 + P0-3 + P0-4        # 纯代码/测试，不碰游戏目录，可离线验收

第2步  P1-6                      # 统一安装器补 mod 资产 → 才有"装完即 20 槽"的前提

第3步  P0-1 + P1-7 + P1-8        # pack 同步进仓库 + catalog 单一真相 + 磁盘数字对齐

第4步  P1-3 + P1-1 + P1-2        # seed 链路 + 20 行导入 + 管理 UI

第5步  P2-4 + P2-5 + P2-3        # 门禁清零（arch_check / probe / registry test）

第6步  P0-1 实机验收              # fr/ru 进入受管 → 验证"法语战斗不再出英语"

第7步  P0-5                      # 阶段 3：切断 DB 依赖（风险最高，需干净 DB 备份）

第8步  P1-4 + P1-5 + P1-9~12     # 语义加固与安装器补全

第9步  P2-6 全矩阵 + P2-1/P2-2 入库

```



## 7. 每个会话开工前读这四份



1. 本文件（进度真相）

2. `MultiLanguage\ARCHITECTURE-UNIFIED.md` §8「未验证边界」（别把没验的当已完成）

3. `MultiLanguage\mod_host\tests\BUG_REVIEW-2026-09-15.md`（两根因：补池来源、多插件抢全局词池）

4. `MultiLanguage\INSTALLER.md`（资源包契约，加语言的唯一入口）



**验收命令合集**（改完就跑，全绿才算完成）：



```powershell

cd D:\ATooManyLanguage\MultiLanguage

powershell -File tests\test_hub.ps1                                   # 期望 61/0

mod_host\tests\run_registry_test.cmd %CD%\packs                       # 期望 全部通过

powershell -File mod_host\tests\run_takeover_test.ps1                 # 期望 Failures: 0

powershell -File mod_custom_slots\tests\test_custom_slots.ps1         # 期望 11/0

powershell -File mod_host\tests\run_word_audio_compat_test.ps1        # 期望 Failures: 0

python tools\verify_integration.py                                    # 期望 PASS (9 languages)

"$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" ..\Japanese\tools\build_pack.py --check-all D:/ATooManyLanguage   # 期望 PASS

powershell -File ..\probes\test_isolation_contract.ps1                # 期望 41/0（无 openpyxl 时 pack_data 项 SKIP）

"$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" ..\Japanese\tools\arch_check.py  # 期望 0 FAIL（P2-3 后）

```



---



## 8. 新增任务 — 用户纠错双向反馈链（2026-09-15 立项）



> 设计全文：`_local\audit\FEEDBACK_LOOP_DESIGN.md`（提交格式、V1–V6 核验规则、指纹联动实锤）。

> 背景：`_local\audit\RESOURCE_AUDIT-2026-09-15.md` 资源审计已定位 pt/ar/ko 系统性内容缺陷，

> 反馈链是其长期修复通道。核心决策：**纠错 = 给 repair.tsv 流喂新行**，不发明新格式；

> 待审内容独立成仓（UGC 与主仓隔离）；主仓只吸收 approved clean diff。



| ID | 任务 | 状态 | 验收 |

|---|---|---|---|

| F-1 | 建待审仓 `WCP-Feedback`（submissions/reviewed 约定 + 提交格式 README） | ⬜ | 空仓可克隆 |

| F-2 | `tools/feedback/pipeline.py`（ingest/review/export + V1–V5 机器核验） | ⬜ | 20 条人造提交跑通，拒绝/通过路径各留日志 |

| F-3 | `apply_feedback.py` 写回语言工程 repair 流 → rebuild 联动 | ⬜ | fr 干跑 1 条释义修正：build_pack --check-all PASS |

| F-4 | manifest 增 `content_revision`；`-Update` 感知纯释义更新（指纹已实锤只覆盖词集） | ⬜ | 释义更新后 -Update 能重下 meaning 资产 |

| F-5 | 游戏端提交 UI/热键（宿主 mod 写本地 queue，格式见设计 §4） | ⬜ | 单独任务，暂只预留格式 |

| F-6 | 首跑实战：pt 西语例句 / ar 模板句众包重生 | ✅（提前完成） | 2026-09-15 修复轮已直接重生成：pt 西语残留 0.02%、ar top 框架 2.37%，审计复查通过；反馈链作为长期通道保留 |



---



## 9. 资源质量修复轮完成（2026-09-15）



> 审计全文与修复明细：`_local\audit\RESOURCE_AUDIT-2026-09-15.md`。

> 修复范围：P0 pt/ar、P1 ko/es/ru/de、P2 yue 全部落地；修复后 9 语言 verify_all + sync VERIFY 全 PASS。



| 语言 | 修复要点 | 结果 |

|---|---|---|

| pt | 例句西语化 12.3%→0.02%；ultimo 重复词清除；音频补齐 | 8,599 词 ALL PASS |

| ar | 96.4% 单模板→3 句/词（top 2.37%）；音频 8,118+24,354 | 8,118 词 ALL PASS |

| ko | 3,123→7,330 词；繁体/英文释义清零；例句 top 4.77% | 7,330 词 ALL PASS（例句音频后台收尾） |

| es | 重音批量修复；错译重译；ultimo 清除 | 8,599 词 ALL PASS |

| ru | 变格重生成 top 1.74%；972 条嵌套括注契约漂移归零 | 8,451 词 ALL PASS |

| de | 114 占位释义清零；11 条括注断裂修复 | 8,062 词 ALL PASS |

| yue | manifest counts 块补齐；审计误报（无表头 xlsx/NFC）修正 | 384 词 ALL PASS |



**✅ 修复产物已提交入库（2026-09-15 21:50，8 仓库本地提交，未 push）**：



| 仓库 | 提交 | 内容 |

|---|---|---|

| German | `3765475` | 修复轮产物 + gen_sentences_de2.py |

| Contonese | `46fdef6` | yue manifest counts 块 |

| korean | `7d59cc0`+`38f6a85` | 扩词/释义修复产物 + build_ko_v2.py；gitignore 补运行日志规则 |

| Spanish | `38bc2e2`+`e379cc9` | 修复轮产物；gitignore 补 *.log |

| Portuguese | `af17022`+`bd6e4aa` | 修复轮产物 + pt_db_payload 入库；gitignore 补 *.log |

| Arabic | `688d6f0` | 修复轮产物 + translations/payload_src/3 个新工具 |

| Russian | `fe7a955`+`.gitignore` 修正 | 修复轮产物 + packs/ru 首次入库 + 例句音频 pack 优先 DLL；installer_pkg 与 .zcode/ 排除 |

| French | `cac0ba3` | 前置轮审计报告 + 审计脚本；ildump_venv 排除 |

| MultiLanguage | `0fae03e`+`e6b0fd1`+`5e3592d` | packs 镜像 + languages/ 全量重集成 |



入库后复验：`verify_integration.py` **PASS (9 languages)**、`tests\test_hub.ps1` **55/0**、

`sync_packs.py --check` PASS、Contonese/Russian manifest 与 ML 仓逐字节一致。

遗留：ko 例句音频 14,833 条后台生成完毕后需增量入库（korean `audio_manifest_ko.json` + ML packs/ko 同步重集成）。





---



## 10. 内容质量二次审计 + 修复轮（2026-09-16）



> 审计发现上一轮指标体系覆盖不到的三类缺陷（转义残留 / 例句语法 / 音频发布链错位），全部修复并复审。

> 审计与修复脚本：`_local/audit/`（fix_ru_frames.py / fix_es_pt_v3.py / build_zips_v110.py 等）。



| 语言 | 缺陷 | 规模 | 修复 | 复审 |

|---|---|---|---|---|

| de | 释义+例句中文括注含转义残留（`\.` `\ `，源自上游 DB 导出） | 1,240 释义 + 672 例句括注 | 全链清洗（payload TSV/master/german_books/gen_words_79）→ pack 重建+同步 | pron/句/repair 转义=0 |

| ru | 8 个形容词框架主格插入词语法错误（«Мне показалось странное»） | 1,138 行 | 6 框架改工具格（pymorphy 变格）+2 框架固定地道句；Apro 词头走固定句 | 坏框架=0 |

| ru/es/pt | 形容词框架中文括注「很困难的」式叠的 | ru 2,289 / es 1,794 / pt 1,635 行 | 按框架槽位截掉释义自带的「的」 | 残留=0 |

| es/pt | 阴性主语框架阳性形容词（sala/comida/reunión/sensação） | es 459 / pt 186 处 | 阴性一致变形（-o→-a/-os→-as）；pt 坏框架 o parecia→o local parecia（147 处） | 残留=0 |

| 发布链 | 6 语言 pack 侧例句音频为陈旧哈希副本（覆盖率≈0）；ko/ar/ru 例句 zip 与当前语料错位；core zip 含修复前 db | pack 6 语言 + 6 语言 zip + 4 语言 core | pack 音频按当前语料重建（100% 覆盖）；zip 重建 v1.1.0（build_zips_v110.py）；core zip+seed 重生成 | 覆盖矩阵全 0 miss |



**部署**：LocalLow packs 的 manifest/db/books 已同步 4 语言（de/es/pt/ru）+ ko（db/manifest 补同步 7,330 新版）。



**✅ v1.1.0 发布完成（2026-09-16）**：

1. **音频 zip**：6 语言（de/es/pt/ru/ko/ar）× 2 zip 按修复后 packs 语料重建（`build_zips_v110.py`，源=LocalLow packs audio；词 zip 与 v1.0.0 逐字节同 sha 的确定性复证：de/es/pt/ru/ar 词 zip sha 不变=词集未动，es 例句 zip 25,797 条、ko 句 zip 21,990 条为新语料）。

2. **core zip + seed**：ko/ar/yue 重生成（`make_core_assets.py`；ko 由 3,123 旧版升 7,330，指纹校验通过），9 语言 core 与仓库 packs 逐条目一致。

3. **发布**：`publish_release.py` 参数化（`--version/--summary/--manifest-dir/--core-dir/--published`），6 语言 draft→API 回读校验→发布 → **公开 URL HEAD 24/24 资产 200 且大小一致**。tag：`wcp-{de,es,pt,ru,ko,ar}-resources-v1.1.0`，各 4 资产（词音频/句音频/core/seed），记录在 `published-releases-v1.1.0.json`。

4. **catalog**：六行切 v1.1.0（`apply_resource_releases.py` 扩 KINDS 接受 pack/slot_manifest）；ko 词量 3,123→7,330、es/pt 8,600→8,599（指纹同步）；`disk.extract_mb` 按 zip 条目实测复算（ja/fr/yue 保持 v1.0.0 实测值不动）。hub catalog 同步生成（CRLF 语义等价）。

5. **沙箱端到端（ko）**：`-Books ko -Offline` → packs/ko 完整（7,330 词指纹吻合、音频 7,335+21,990）、seed managed 行词集=pack 词集、state 记账 v1.1.0+sha 一致、plugins 三 DLL、重跑幂等（「已是最新」）。

6. **语言仓入库（09-16 二轮修复产物，沿用 §9 先例）**：German `2780614` / Russian `f95e1f6` / Spanish `9c001f2` / Portuguese `47f8a11` / korean `79b6cef`；ML `languages/` 重集成（`3e04a56`）+ 发布链（`a8c4e33`）+ catalog 终态（`f4e2ef4`）；hub `bf2e8b8`。

7. **门禁全绿**：ML/hub test_hub 55/0 ×2、probes 41/0（系统 Python 真跑 pack_data）、registry/takeover/custom-slots 全过、`verify_integration.py` **PASS (9 languages)**、`sync_packs.py --check` PASS、`build_pack.py --check-all` PASS、`arch_check.py` **0 FAIL**（P2-3 未复验状态就此闭环）。



**遗留（不阻塞发布）**：① LocalLow es 音频树有已清除词 ultimo.mp3 残留（v1.0.0 zip 同样携带，词表已无该词，无行为影响）；② LocalLow ar 音频树词文件 8,193 vs 词表 8,118（陈旧超集，与发布 zip 同源，覆盖矩阵 0 miss）；③ ja/fr/yue 三个未变更语言仍指 v1.0.0（fr/yue core 的 manifest 早期陈旧问题已通过 ko/ar/yue 重生成时的全量逐条目核对覆盖，fr core 核对 OK）。



---



## 11. 内容质量三轮审计 + 修复（2026-09-16 下午）



> 审计全文：`_local/audit/RESOURCE_AUDIT-2026-09-16.md`。本轮专攻指标盲区：ko 的 27 个模板形状借助词变体把 90.4% 模板化伪装成 top 4.77%；de 的 fallback 垃圾释义被重复度指标掩盖。



| 语言 | 缺陷 | 规模 | 修复 | 复审 |

|---|---|---|---|---|

| de | fallback 垃圾释义（"是；表示；在；后端"式生成器兜底直写） | 50 条 | 逐词手写重译（`fix_de_meanings_20260916.py`） | fallback=0 |

| de | 释义内部重复 sense | 770 条 | 保序去重不截断（首轮截 ≤3 误伤 562 多义词已回滚） | dupin=0 |

| de | 标签泄漏/词典错配（`<英>酒后驾驶`、`Deo→草酸二乙酯`） | 4 条 | 手写修正 | =0 |

| ko | 音标缺失 | 3,584 条 | kaikki IPA 2,672 + 规则音译 912 填充 | 100% |

| ko | 释义 `[[ipa]]` 前缀（宿主 StripReading 残留游离 ]） | 3,746 条 | 清洗为纯释义 | =0 |

| ko | 例句模板化 90.4%（27 形状）+ 副词塞名词格 587 + 名词塞动词框 ~1,050 + -니다 剥干病句 | 21,990 行重生成 | 例句 v3：词性分族 36+14+8+8 帧互素步长轮换，幂等 | top 2.94%，槽位错误全 0，每词恒 3 句 |



**链路**：korean/German 仓（ko `37fbf21`、de `79b6814`）→ build_pack_payload --write → build_pack --write --force → sync_packs（VERIFY PASS）→ ML `bbb9f85`+`49d8866`（languages 重集成）→ LocalLow de/ko 部署复测全绿。



**门禁**：test_hub 55/0、verify_integration 9/9 PASS、build_pack --check-all PASS、sync --check PASS、probes 40/0。



**遗留**：① ~~ko 例句音频 TTS~~ 已完成（21,990 句 100% 覆盖，pack 音频与语料逐文件一致）；② ~~v1.1.x 发布~~ 已完成 `wcp-ko-resources-v1.1.1`（4 资产 API 回读校验 + 公开 URL HEAD 200 ×4，catalog ko 行切 v1.1.1 + disk 675MB 复算，ML `f18ad9c`、hub `fe72f20`，test_hub 双仓 61/0）；③ de 跨词义黏连（Taube→聋的 等上游词典行错位）已量化 183 条疑似（词性-释义错配启发式，清单 `_local/audit/de_crossword_suspects_20260916.json`）挂反馈链 P2；④ ja 扩词 ~10,000 可选 P2。



---



## 12. 单词发音兼容层 — 群友反馈驱动（2026-09-16 傍晚）



> 触发：群友反馈「自动下载时明明解压了音频，但发音会说什么什么 Japanese…（英语 AI 语音），说完有时还闪退」。



**根因（实证）**：游戏的 `VocabularyAudioPlayer` 只读游戏原生目录 `<LocalLow>\WCP\vocabulary\<词>.mp3`（引擎自带路径，不是插件约定）。

v1.1.0（`3162b4e`）起安装器把单词音频只写进 `packs/<lang>/audio/word`，播放依赖宿主运行时拦截；宿主未接管

（读档中 / 装完未重启游戏 / 非受管词书）或词形未命中时，游戏读空目录并**静默回退到内置英语 AI 语音**。

开发机因 v1.0.x 时代历史安装在该目录留有全量副本（24,770 文件）而不复现——缺陷只在用户侧暴露。



| 改动 | 内容 | 验收 |

|---|---|---|

| 安装器（日语 v1.2.8 + ML 统一） | 单词音频双写 pack + `%USERPROFILE%\AppData\LocalLow\WCP\vocabulary`（只覆盖同名文件；ML 侧抽成 psm1 `Sync-WordAudioMirror`，规则对所有语言一致、无语言分支） | 沙箱端到端（yue 在线）镜像 384 文件；zip 内验证版本戳/脚本/宿主 DLL 一致 |

| WcpHost 0.4.0 | 运行时自动补缺（只补缺、每帧 32 文件或 6ms、可中断、失败仅日志、完成标记 `.wcp-mirror.txt`、配置 `Compatibility/MirrorWordAudio`）；音频词形候选重试（全角半角/大小写/空格/句点）；miss 限流日志；音频缓存上限 160 + 离开词书释放 | 离线 harness 29/0；编译 OK；部署 sha 一致 |

| 发布 | GitHub `wcp-jp-v1.2.8` → `v1.2.8.1`（说明文案修正）→ **`v1.2.8.2`**（Latest；安装器容错，公开 URL 回读 SHA-256 一致）；资源 Release 的 `release-index.json` 已覆盖（公开回读 `installer_version=wcp-jp-v1.2.8.2`，v1.2.7 用户自更新可达）；ML `wcp-mods-v1.2.0` 载荷（WcpHost 0.4.0 + CustomSlots 1.2.1 + BookName 1.3.0，公开回读 sha 一致）；catalog mods 块更新 + hub catalog 生成副本 | 全部回读校验通过 |



**门禁**：test_hub 61/0（ML+hub）、takeover Failures:0、registry 全部通过、custom-slots 11/0、WordAudioCompat 29/0、

probes 41/0、verify_integration PASS(9)、build_pack --check-all PASS、arch_check 0 FAIL。



**提交**：Japanese `05d1bdc`+`562613a`+`591896d`（未 push，仓库 ahead 25/behind 7 分叉保持现状）；ML `93ac37d`（已 push `f4e2ef4..93ac37d`）；hub `ac804aa`。



**遗留**：① **实机验证通过（2026-09-16 晚，群友反馈）**：群友更新到 v1.2.8.2 后反馈「可以了」——发音变英语 AI 语音的问题在生产环境确认修复。作者本机的兼容层日志（`WcpHost: 单词音频兼容层…`）核对仍可作对照，非必须。②「说完闪退」未证实：本机事件日志只有一次 wcp.exe 挂起（9/16 3:28，换装场景加载中）与一次 AMD 驱动崩溃（9/14），无插件因果证据；需群友 `Player.log` + `BepInEx\LogOutput.log`。③ Japanese 仓本地领先远端 25 个提交，发布 tag 指向远端 HEAD 的既有惯例未变（P2-1 范围扩大）。



**2026-09-16 追加（Steam 云同步发现 → 安装器 v1.2.8.3）**：用户反馈 Steam 库页「云状态：无法同步」。实测该游戏云同步范围是**整个** `LocalLow\WCP\wcp`（`remotecache.vdf` 5000 条上限、`cloud_log` 连续上传 `ko/ru/es/pt_sentence_audio` 音频），而该目录实际有 **53 万文件 / 约 15GB**（旧版音频目录 + `jpmod_downloads` 1.6GB + 备份 + 临时目录）→ 关键存档 `MyBook.es3` 永远排不进同步队列。



- **安装器 v1.2.8.3**：下载缓存、备份、解压临时目录、自更新下载全部改到 `LocalLow\WCP\jpmod_data`（与 packs 同级、云同步范围之外）；升级首跑用 `Move-LegacyWorkDir` 同盘搬移旧数据（瞬间、不重下 1.6GB），失败只提示不影响安装；C# 存档修复 helper 备份根参数化。

- **本机已实际执行迁移**（1.59GB 缓存 + 备份移入 `jpmod_data`，旧位置清空）。

- 验收：PSParser SYNTAX OK；提取 C# 用 csc `/langversion:5` 编译通过；离线 harness `work/tmp/move_workdir_test.ps1` 6/0；verify_integration PASS(9)；GitHub `wcp-jp-v1.2.8.3` 发布（公开 URL 200 + sha256 一致；资源 index 回读 = v1.2.8.3）。

- 提交：Japanese `d8d11f4`（未 push）；ML `3216eb2`（已 push）。

- **遗留（已决策：兼容性优先，不清理）**：旧版音频目录保留在云同步范围内（`wcp\sentence_audio` 3.4GB + `*_sentence_audio` 约 8.5GB）。已用 DLL 字符串扫描确认：其中 388,631 个文件（`sentence_audio`、`ja_sentence_audio`、`es/pt/ar/ko_*_audio`）没有任何插件引用，但用户明确选择「兼容性优先」——保留全部历史目录（含旧插件回退路径），不做改名/清理，也暂不关 Steam 云同步。因此该游戏的云同步会长期维持「无法同步」（本地数据不受影响，只是没有有效云备份；换机器时手动拷存档或重跑安装器）。若将来要改善：候选子集与判定手段（DLL UTF-16 字符串扫描）已在本节，可直接复用。



**2026-09-16 晚（B 类改造 + 双渠道发布收官）**：

- **B 类改造收敛版**：de/fr/ru/yue 例句插件只读 packs/<lang>/audio/sentence，词表插件读 packs/<lang>/audio/word；legacy 回退降级为配置开关 `Legacy/AudioFallback`、`Legacy/WordAudioFallback`（默认 **false**，与 YieldToHost 同风格）——默认路径干净，异常环境一键恢复迁移期回退。8 插件 BUILD OK + 部署 + DLL 开关字符串确认；fr/yue 旧目录与 pack 差集 0，ru pack 覆盖当前语料 100%，de 98.5%（旧目录多出的是语料更新前陈旧发音）。

- **mods 载荷 v1.3.0**（GitHub，公开回读 sha256 一致）：从 3 插件扩到 11——加入 8 个收敛版语言插件，任何渠道装完即收敛版，覆盖用户机残留的旧 legacy DLL。catalog/hub catalog 同步（test_hub 61/0 ×2）。

- **日语一键包 v1.2.9**（GitHub Latest，公开 URL 200 + sha256 一致）：载荷 5 插件未变，与 mods v1.3.0 对齐版本门面；release-index.json 已覆盖（自更新链回读 = wcp-jp-v1.2.9）；v1.2.8~v1.2.8.3 标注取代提示。

- 提交：French 9b0363a、German fe4ef8b、Russian 1815804、Contonese 2d76b24、ML 13feaeb+ec1a390（已推）、Japanese bbd9419（已推，仓库首次全量同步）。

- 门禁：verify_integration PASS(9)、probes 41/0、test_hub 61/0 ×2。

- 群友实机确认 v1.2.8.2 发音修复生效；「说完闪退」仍待日志（如复现让用户交 Player.log + LogOutput.log）。



**2026-09-16 深夜（性能收敛 A+C）**：用户反馈偶发卡顿。日志检查：无插件异常（唯一 NRE 来自游戏自带 DrunkDemo），内存健康（峰值 107MB）。真实问题是 4-5 次/秒的 `FindObjectsOfTypeAll` 全场扫描背景税（宿主 1s + 例句 0.3s + BookNameMod 1s ×2 处）。

- **A**：宿主 `ScanBookLabelsThrottled`——活跃期 1s，连续 5 次无改写升 5s，改写即回快档；例句扫描 0.3s→1s（挂载/移除后短暂回 0.3s）。

- **C**：BookNameMod 检测宿主接管（反射 `WcpHost.ActiveProfileId`）时整轮跳过全场扫描，离开受管书自动还原。

- 部署 sha：WcpHost `f19b1f8f`、BookNameMod `fa83fa61`（仓内=游戏一致）。回归：custom-slots 8/0、takeover 0、verify_integration ja/fr/de/ru/yue PASS（es/pt mismatch 归并行内容会话，已同步镜像）。

- 提交：Japanese `21ff113`、ML `8e8a4ec`（均已推）。

- 下一步（未做）：实机对比体感；若仍卡再上 B 档（自适应慢速 10s）。



## 13. 多语言词书质量与格式终验收敛（2026-09-17）



> 目标：消除跨平台换行漂移防腐、净化西葡音标嵌套括号残余、彻底清除韩语上游抓取代码碎片/未汉化词义与错配例句，完成 9 语全链路回归。



| 语言 | 缺陷类别与条目 | 修复措施 | 验证结果 |

|---|---|---|---|

| pt / es | 跨环境检出 CRLF 破坏 TSV 载荷 sha256 导致 build_pack 与 sync_packs drift | LF 归一化 + 新增 `.gitattributes` 锁定 `*.tsv text eol=lf` 与 `*.json text eol=lf` | `build_pack.py --check-all` PASS、`sync_packs.py --check` PASS |

| es | 3 处音标括号破坏游戏 `StripReading`（`inteligente`, `hormiga`, `etcétera`） | 修正 `output/pack_payload/es_pron.tsv` 与 `spanish_books.json` 为规范单层括号 `[ipa]`，重新物化 pack | bad bracket = 0，`gen_sentences_es2.py --check` PASS |

| pt | 2 处音标括号破坏游戏 `StripReading`（`perdão`, `alabama`） | 修正 `output/pack_payload/pt_pron.tsv` 与 `portuguese_books.json` 为规范单层括号 `[ipa]`，重新物化 pack | bad bracket = 0，`gen_sentences_pt2.py --check` PASS |

| ko | 125 处上游语料严重污染（代码碎片：%1$s、KRunner、slot type、executing object、data type、zodiac；完全错配：공항→【2】银行、등대→【11】蓝方基地；生硬机翻/英文未汉化：Sale、Towel、Joke、找到SAD、到SUIT 等） | 全量手写校准精确汉化释义与正规词性标签，同步修复 21 词（共 61 句）例句译文，跑通 `make_import_files` + `export_ko_db_payload` + `build_pack_payload` + `build_pack` 全链路 | 9 语 meaning.sqlite 坏括号/占位符/代码碎片全 0，`verify_all_ko.py` ALL PASS |

| pt | 词条 pt 释义 zh 错配脱污染（'中世纪的zh'→'中世纪的葡萄牙语'）+ todo-poderoso (all-powerful→全能的) + 标点规范 | 修正 portuguese_books.json，重跑 gen_sentences_pt2.py 与 build_pack 全链路 | bad meaning = 0, gen_sentences_pt2.py --check PASS |

| es | 词条 ia (人工智能)/cas/lsd/bb 汉化与例句脱污染 + sr./sra./dr./dra./s. 标点规范 | 修正 spanish_books.json，重跑 gen_sentences_es2.py 与 build_pack 全链路 | bad meaning = 0, gen_sentences_es2.py --check PASS |

| ko | 82 处生硬罗马音括注（(Gukbap)/(Kongnamul Guk)等）与破损/质疑标点（哀:、浮躁？、试衣间 ?等）彻底净化 | 修正 korean_books.json，重跑 make_import_files + export_ko_db_payload + build_pack | 坏括号=0, 括注罗马音=0, 异常标点=0, verify_all_ko PASS |



- **门禁验收**：

  - `Japanese/tools/build_pack.py --check-all D:/ATooManyLanguage`：8 语逐字节一致 PASS

  - `MultiLanguage/tools/sync_packs.py --check`：PASS

  - `MultiLanguage/tools/verify_integration.py`：PASS (9 languages)

  - `Japanese/tools/arch_check.py`：0 FAIL / 0 WARN

  - `korean/tools/verify_all_ko.py`：ALL PASS (7330 词 / 21990 句 / 独立 DB / 离线 Payload)

  - `MultiLanguage/tests/test_hub.ps1`：61/0

  - `mod_host/tests/run_takeover_test.ps1`：Failures: 0

  - `mod_custom_slots/tests/test_custom_slots.ps1`：11/0

  - `mod_host/tests/run_word_audio_compat_test.ps1`：Failures: 0





- **语言仓提交记录**：

  - Spanish: `f8576cf` (content(es): 质量收敛 — 修复3处音标破坏StripReading括号+ia/cas/lsd/bb释义与例句汉化+标点规范)

  - Portuguese: `d71d71a` (content(pt): 质量收敛 — 修复2处音标坏括号+pt释义zh错配脱污染+todo-poderoso/ia汉化+标点规范)

  - korean: `cc78c82` (content(ko): 质量收敛 — 彻底净化82处生硬罗马音与标点瑕疵+125处代码碎片与错配修正)



## Task 2026-09-17: 全语种词书资源质量深度收敛与结构闭环 (Round 4)

- **目标**: 针对全 9 大语种（German, Korean, Spanish, Portuguese, Arabic, Japanese, French, Russian, Cantonese）实施深度词义校准与例句括号消除，达成 0 缺陷全面质量收敛。

- **排查与根因**:

  1. **德语 (de)**: 历史词典源数据行位移造成 156 个高频名词（Orange, Bass, Braten, Taube, Mechaniker 等）与连词 dass 释义缺失或错位；363 句中文翻译内嵌全角括号造成 `LastIndexOf('（')` 解析截断。

  2. **韩语 (ko)**: 19 处核心词条释义（如 밥, 곰, 돈, 파이팅, 소, 뼈, 고양이, 닭, 달걀 等）因多音/派生误配为不自然短语；例句中含有多层嵌套全角括号。

  3. **西/葡语 (es/pt)**: 基础功能词（es 的 que, la, un, me, te, le, hay; pt 的 o, a, um, uma, obrigado, obrigada 等）词义包含非标准全角括号，级联污染例句生成器，产生 27 句 (es) 与 9 句 (pt) 嵌套括号。

  4. **阿/日语 (ar/ja)**: 阿拉伯语 38 句例句与日语 366 句例句中，中文翻译内带有辅助性全角括号（如 `二人ともフリーだよ。（两个人都是自由的（单身）。）`），导致 `SentenceAudioMod.cs` 中 `LastIndexOf('（')` 将句子原文截断为 `二人ともフリーだよ。（两个人都是自由的`，进而引发 MD5 计算畸变致使例句 TTS 音频寻址失败。

- **处置方案**:

  1. 源头数据修复: 在各语言源码及核心生成器（`gen_sentences_*.py`, `build_dataset_*.py`, `output/*_books.json`）中直接修正词义，并将例句中文翻译内部嵌套的全角括号系统化规范为方括号 `[...]`，保留最外层单一 `（...）` 分界符。

  2. 工具链防卫加固: 在 `MultiLanguage/tools/build_pack_payload.py` 载荷导出管道中嵌入中文嵌套括号清洗，确保未来重建具备防御机制。

  3. 全链路闭环构建与物化: 重新运行生成器与 `--check` 严格校验门禁 -> 重新导出 payload/xlsx/sqlite -> `build_pack.py` 物化 -> `sync_packs.py` 同步 -> `integrate_languages.py` 镜像同步。

- **提交与验证**:

  - German: `2f201bd`

  - korean: `e980f92`

  - Spanish: `5880255`

  - Portuguese: `59b4a25`

  - Arabic: `8868135`

  - Japanese: `bb52e8e`

  - MultiLanguage: `fd19bb9`

  - 终检结果: `deep_scan_all.py` 针对全 9 大语种 pack 扫描，Meanings 缺陷 0，Sentences 缺陷 0，全量 20/20 及全语种资源审计 100% 通过。


## Task 2026-09-17: 跨环境可复现性收敛 (Round 5) — EOL 契约与哈希链自洽
- **目标**: 消除"重新生成 ≠ 已提交产物"的漂移，使 9 语 pack/载荷在任意检出环境（autocrlf 开/关）下哈希自洽、门禁真绿。
- **排查与根因**:
  1. **生成器文本模式写盘**: `build_pack.py` 的 `db/sentences.json`、ko/ru 载荷导出器以文本模式写盘（Windows 下 CRLF），与 `.gitattributes` 的 LF 要求冲突 → 换环境或重跑即字节漂移。
  2. **陈旧哈希**: de/ko/ru 载荷清单记录的哈希对应更早版本（de_pron/de_sentences、ru_*、ko_*），与仓库内文件不符；de 实际字节因 autocrlf 检出为 CRLF，而清单按 LF 记录 → 任何 LF 环境校验必失败。
  3. **门禁盲区**: ar/ko 载荷清单缺 `files` 段，`check_payload_manifest` 因此从不校验其载荷哈希（校验静默跳过）。
  4. **ja 清单失真**: `packs/ja/manifest.json` 与 `jp_sentences.tsv` 载荷哈希不一致，`--check-all` 实际 FAIL（既有记录写"8 语 PASS"，ja 从未被覆盖）；ja 的 `jp_sentences.tsv` 与 pack json 仍是 CRLF blob。
- **处置方案**:
  1. `build_pack.py` 写 `db/sentences.json` 改 `newline='\n'`；ko/ru 导出器全链路 LF 写入；ru 载荷清单增补 `files` 段。
  2. 8 语 `.gitattributes` 增补 EOL 契约（`*.tsv`/`*.json` = LF，`*.bat`/`*.cmd` 保持 CRLF）；ja 与 ML 限定到 `packs/**`、`wcp_wordbooks/output/**`、`languages/**`，避免波及中间产物。
  3. 载荷 TSV 落盘 LF 并重算 `files` 哈希（内容零变化）；ar/ko 补 `files` 段；9 语 pack 重建刷新 `payload_files`；`sync_packs --write` → `integrate_languages --apply` → 部署侧（LocalLow）同步。
  4. ja 清单与其载荷哈希重建对齐；ja/ML 的 EOL 规则镜像同步（`languages/ja/.gitattributes`）。
- **提交与验证**:
  - German `1395158` / Contonese `5021726` / French `d5b719c` / korean `549be43` / Russian `93d4954` / Arabic `e463489` / Japanese `30635a4` / MultiLanguage `2c800f4` + 镜像刷新提交
  - 门禁: `build_pack.py --check-all` PASS；`sync_packs --check` PASS；`verify_integration` PASS(9)；`arch_check` 0 FAIL/0 WARN；`test_hub.ps1` 61/0（MultiLanguage 与 hub）；`probes/test_isolation_contract.ps1` 41/0；9 语载荷哈希 0 mismatch；**提交后字节门禁**（`git cat-file blob` 取 HEAD 字节，48 个哈希）0 mismatch；EOL 漂移判定 0。
- **遗留（本轮刻意不处置，待上游根治）**:
  1. **de 例句译文错配（上游库）**: 游戏库 `wcpFullEng.db` 当前对 Ablassen、Ablenkungsmanöver 等 329 词输出与词义不符的中文（如"皱眉的""转换注意力的的"），而仓库载荷（HEAD 版）是正确的"排放""转移注意力策略"。重跑 `export_de_db_payload.py` 会把这批劣化写入资源，故本轮保持 de 内容零变化；修好例句术语替换后再统一重跑即可收敛。
  2. **de 义项分隔符丢失**: 旧导出器未转义反斜杠，`build_pack` 反解后 Jucken/demütigend/gezielt 3 词的义项分隔符被吞（游戏库内该分隔符存在）→ 自愈灌回会合并义项；随上游重跑一并解决。
  3. **音标缺口**: es 缺 220 词（本地源仅可自动补 109）、pt 缺 136 词（仅可补 5）、ja 878 词多为假名原生、ru 127 词均为单音节（无需重音标记，豁免）——低 ROI，暂缓。

## Task 2026-09-17（续）: de 例句译文术语错配修复（上游定位 + 回填 + 重灌对齐）

- **现象**: 游戏内 de 例句译文出现别的词的释义 —— `Ablassen`→"皱眉的"、`riesige`→"暴利"、`Unschuldige`→"无罪的的"、`Ader`→"隔热的"，且带"的的"重复。
- **逐层排查（关键：先分清哪一层脏）**:
  - 源 `output/catbar_german_book.json` / 载荷 `output/de_db_payload/de_pron.tsv` / pack `packs/de/db/meaning.sqlite` 三层**全部正确**（`Ablassen=[ablasən] 排放；放气；放出；停止〈n.〉`）；`93f3383` 已修过 147 条跨词义错配。
  - 游戏库 `wcpFullEng.db` **落后**：与 pack 比对释义偏离 1,807/8,062（错配 1,691 + 转义重复残留 116），例句 8,062/8,062 属另一套（`work/gen_out_*`）。
  - ⇒ 因导出器以游戏库为源，**库未对齐前重跑导出会把库内旧错配倒灌回仓库**（本轮据此挡住了一次劣化）。
- **定位真正的上游**: 灌库脚本 `patch_local_db_de.py` 的例句取自 `data/translations/sentences_master.json`（不是 german_books.json）。该文件 327 词 / 979 句译文含错配；而**发布态 HEAD 载荷里的译文是正确版本**（`排放`/`血管`/`转移注意力策略`）—— 即 master 曾被劣化覆盖。
- **处置**:
  1. 用 HEAD 载荷按 (词, 德语原文) 精确回填，判据取严：仅当 master 译文**不含本词释义核心**且发布态译文含 ⇒ 才替换（括号风格 `（）`↔`[]`、义项选择差异一律保留，避免倒退）；实际替换 **394 句**。
  2. 重灌库（`patch_local_db_de.py`：7,837 词 / 23,511 句，跳过 225 英德同形词）→ 库内释义与例句与仓库对齐。
  3. 重跑 `export_de_db_payload.py` → 重建 de pack → sync → integrate → 部署侧同步。
- **验证**: 库内 `Ablassen` = `排放；放气；放出；停止〈n.〉`、例句"讲排放/关于排放的所有疑问/没有排放" ✓；载荷 vs HEAD 内容差异 329 → 141（剩余均为括号风格与同词不同例句选择，无错配）；`--check-all` PASS；`verify_integration` PASS(9)；`arch_check` 0 FAIL/0 WARN；提交后字节门禁 48 哈希 0 mismatch；probes 41/0；hub 61/0。
- **提交**: German `4eb55a1`、MultiLanguage `8c23bc9`。
- **遗留**:
  1. **12 句两侧都不含本词释义核心**（如 `Dirk`：master"极好的" vs 发布态"迪克[男子名]"）—— 判据无法自动裁决，需人工确认后替换。
  2. de 例句存在**同词不同例句选择**（`Dialekt` 等）与括号风格 `（）`/`[]` 两套并存，属历史多轮产物，未做统一（避免倒退）。
  3. es 缺音标 220（本地源仅可补 109）、pt 缺 136（仅 5）、ru 127 全单音节豁免、ja 878 多为假名原生。
  4. **远端**: 9 仓中仅 Japanese 有可用远端（推送成功 `a246ac1..30635a4`）；其余 8 仓 `git push` 返回 `Repository not found`，提交仅存本地。

## Task 2026-09-17（续二）: de 跨词译文错配清零（最后 9 句）

- **背景**: 续一修复 394 句后遗留 12 句「两侧都不含本词释义核心」待人工。复查发现其成因是判据用原始子串匹配（如 `迪克（男子名）` vs 旧载荷 `迪克[男子名]` 不相等）——括号风格差异掩盖了它们其实是同一修复类。
- **取证**: 对 3 词逐一核对立 dismissal 依据 —— `Dirk` 释义=`迪克（男子名）；短剑`（"极好的"属别的词）、`Foul` 释义=`犯规（体育）`单义项（"污秽的"不属于它）、`Sonnen` 首义项=`太阳（复数）`（且现值带"的的"病茬）。三词现值均为跨词错配，非义项选择差异。
- **处置**: `_local/audit/round6f_repair_final9.py`（括号归一化判据，dry-run→--apply）替换 9 句（Dirk 3 / Foul 3 / Sonnen 3），来源=发布态载荷 `1395158:de_sentences.tsv`。随后重灌库 → 重跑导出 → 重建 pack → sync → integrate → 部署侧同步 → 提交（German `d3c9903`、ML `5758103`）。
- **终验**: 库内实测 `Dirk`→`没有迪克[男子名]…`、`Foul`→`关于犯规[体育]…`、`Sonnen`→`太阳[复数]` ✓；`--check-all` PASS；`verify_integration` PASS(9)；**全库 24,186 句中「译文不含本词释义核心」= 0**（逐句复扫）。
- **de 译文错配问题至此关闭**。剩余遗留：de 例句括号风格 `（）`/`[]` 两套并存（历史产物，统一需专门一轮）；音标缺口（es 220/pt 136/ja 878/ru 127 单音节豁免，低 ROI 已定性）；8 个语言子仓远端 `Repository not found`（内容已经 ML 宿主仓 `hanserdesu/WCP-MultiLanguage` 发布，子仓仅缺独立备份）。

---

## 14. 服务边界 + 磁盘健康收敛（2026-09-17 晚）

> 目标：用户需求 R6（只服务本 mod 范围）与 R10（更新只下有差异的）从"部分实现"收敛到可验收。
> 两项都坚持兼容优先：store 缺失回退旧语义、健康核对纯只读、任何失败不阻断主安装。

| 项 | 内容 | 状态 |
|---|---|---|
| P1-4 | 宿主服务边界：指纹命中 + 20 槽登记（托管行/镜像行）双门；RequireSlotOwnership 开关 | ✅ 代码+15/0 离线，实机待验 |
| P1-9 | Test-WordbookDiskHealth（骨架/词表自证/音频抽样）+ -Update 摘除重下 | ✅ 在线端到端验证 |
| 附带修复 | Get-HubWorkPath 目录保证（新用户阻断级回归）+ 下载句柄 finally 释放 | ✅ 沙箱实锤后修复 |
| 门禁 | test_hub 87/0 · takeover 0 · custom-slots 11/0 · word-audio 0 · slot-ownership 15/0 · registry 全过 · verify_integration 9/9 · sync --check · build_pack --check-all · arch_check 0F/0W · probes 41/0 | ✅ 全绿 |
| 发布 | 新 mods 载荷已构建（含 WcpHost 0.5.1 服务边界空表放行修复 + CustomSlotsMod 1.2.2 判据信号取证，payload sha256 `13a54c2c…`）——**未发布**，待用户批准 | ⬜ |

**版本记录**：WcpHost 0.4.0 → 0.5.0（服务边界门 + RequireSlotOwnership 配置）。
mods 载荷待发布为新版本（建议 wcp-mods-v1.4.0）并同步 catalog mods 块 + hub catalog 副本；
发布流程与渠道影响面见 P1-14 的经验（发版前 clarify 渠道映射）。

---

## 15. 20 槽 UI 形态收敛（P1-15，2026-09-17）

> 用户需求原话：20 个槽位"全部用原生一模一样的方式，没有 UI 违和性，只是多了个滚动条可以往下
> 管理哪些显示不出来的槽位"。**判定：未达标** —— 功能齐备，呈现形态不是原生无缝扩展。

| 项 | 内容 | 状态 |
|---|---|---|
| P1-15a | 原生页几何/组件参数采集（自动触发，非热键） | ✅ 代码+部署（2026-09-17） |
| P1-15b | 实机采集 `WcpSlotsDiag.txt` | ⬜ 待用户进一次自定义词书页（自动写盘） |
| P1-15c | 按真实几何克隆原生行 + 原生风格滚动条容器 | ⬜ 待 P1-15b 数据 |
| P1-15d | 自绘面板降级为配置开关回退（兼容优先） | ⬜ 与 P1-15c 同批 |

**硬边界（必须先讲清）**：游戏运行态只有 4 个 `SelfBookList1..4` 字段
（`WordChooseButtonS10` 里硬编码，`BookButtonSon` 数组固定），同一时刻仍只有 4 本能真正参与学习。
"原生无缝"只能做到**视觉与管理层面**：20 行都能看、都能改名/移除，选中的那几行物化进原生 4 槽。

**P1-15a 已完成**：`DumpNativeBookPage(source)` ① 自动触发 —— `PollCustomPage` 首次发现"自定义页可见"
即写盘（挂热键的采集连续多轮拿不到文件，F9 路径实测从未产出过 `WcpSlotsDiag.txt`）；
② 采集粒度扩到可克隆：父链各级容器几何 + `Canvas`/`CanvasScaler` 参数、深度 7 节点树（每节点组件参数：
Image 颜色/sprite、Text 字体/字号/颜色/对齐、LayoutGroup 间距/内边距/子对齐、ContentSizeFitter、
LayoutElement、CanvasGroup）、`BookButtonFather/Son/NameText/LearnedNum` 四组逐项 self/parent/child 几何、
**全场景 `ScrollRect`/`Scrollbar` 模板扫描**（无缝改造要克隆原生滚动条，不是自造一个风格不同的）、
页面字体清单。写入 `%LocalLow%\WCP\wcp_diag\WcpSlotsDiag.txt`（本机 =
`%USERPROFILE%\AppData\LocalLow\WCP\...`）。

**验收**：BUILD OK + 部署，CustomSlotsMod.dll sha `3f73ef39…` 仓内 = 游戏 BepInEx\plugins 一致；
custom-slots 离线 harness 11/0 无回归。

**验证命令**：`powershell -NoProfile -ExecutionPolicy Bypass -File 'mod_custom_slots\tests\test_custom_slots.ps1'`
→ `Result: 11 passed, 0 failed`。

**待用户的一条操作**：进游戏 → 打开"自定义词书"页（停留 1 秒即可）→ 自动产出 `WcpSlotsDiag.txt`。
拿到真实几何后才能克隆原生行（猜行高/字体 = "永远差一点"）。

## 15. 2026-09-17 夜 · 实机 4 项反馈定位 + P1-16/P1-17 登记

来源：用户实机截图（4 张，本会话用 Windows OCR 读出文字）+ WcpSlotsDiag.txt(270 行)
+ LogOutput.log + LocalLow\WCP\packs 现场取证。

### P1-16 20 槽面板的"是否在自定义页"判据误判（导致面板出现在不该出现的位置）
- 现象：面板在"日语词库(猫条版)"等受管书页面、甚至非自定义页也弹出。
- 根因：`GameCompat.IsCustomPageShowing` 扫描 **BookNameText 数组（每个页签的标签）**
  找 `自定义词书` 或 `猫条版`。两个分支都是恒真的：
  ①页签 20（自定义页签）的标签永远是"自定义词书"；
  ②BookNameMod 会把受管页签改写成 `…词库(猫条版)` → `CosmeticMarker` 命中。
  于是"该页签存在"被当成"当前正停在该页"。
- 正确判据应取自**当前显示页号**（用户点击信号 LastUserPageNum 或从原生 chooser 读
  当前页），标签文本扫描只能作为辅助。
- 状态：待修（需要一条"当前页"读取路径，改前必须实机确认，避免面板整页不弹）。

### P1-17 存量部署的 8 个语言包缺 books/ 与 audio/（宿主因就绪门拒接管）
- 实测（LocalLow\WCP\packs）：ja 完整（72,760 文件，含 books/ + audio/）；
  ar/de/es/fr/ko/pt/ru/yue 只有 `db/` + `manifest.json` 4 个文件，缺 books/*.xlsx。
- 后果链：宿主就绪门 `resources.books` 缺失 → "语言包资源未就绪, 本次不接管"
  （LogOutput.log:89）→ 旧插件兜底 → 例句/发音/美化名不生效。
  俄语无例句即此链的下游表现。
- 原因：这些语言是**旧的分语言安装器**装的（wcp/ 下有 `ru_db_payload`、`rumod_install.json`
  等痕迹），只落了 db 载荷；catalog 里的 `wcp-<lang>-core.zip` 本身**含** books/（已逐个
  比对 zip 条目）。所以不是发布链漏打，是存量安装没走统一安装器。
- 修法：对该语言跑统一安装器 `Install-WCP-Wordbooks.ps1 -Books <id> -Update`，pack 会**增量补齐**
  books/（不删既有 db 与用户文件）。
- 状态：待用户执行安装（需要游戏关闭）。

### 已修 P1-4 回归（本轮已提交）
`SlotOwnership` 的"20 槽服务边界"把 **store 存在但一条登记行都没有**（20 条占位行，
`managed=false` 且 `nativeSlot=0`）判成 fail-closed → 把所有词书（含唯一装好的 ja）
一起挡在门外（LogOutput.log:90 "未激活 · 词书不在 20 槽服务范围"）。
- 改动：新增 `StoreStatus.Empty` 语义 = "存在但未播种" → 与 store 缺失同样按兼容回退放行；
  非空表中的清空行仍 fail-closed（撤销语义保留）；损坏仍 fail-closed。
- 版本：WcpHost 0.5.0 → **0.5.1**；部署 sha `836d857b611ffcfca777e43cedaa969e3760634d34108adfb72226afb72e673a`（仓内=游戏一致）。
- 用例：`mod_host/tests/SlotOwnershipTest.cs` 18 条断言 ALL PASS（新增 4 条覆盖空表/占位行/非空表撤销）。




### 已修 P1-18 StrictMode @() 摊平（本轮提交；8 语言 slot-seed 全挂的真凶）



- 现象：`Install-WCP-Wordbooks.ps1 -All -Update` 装 9 语言时，**8 个语言的 `wcp-*-slot-seed.json` 全部失败**（只有 ja 成功），报错 `在此对象上找不到属性"Count"`。

- 根因（实证，非推断）：`Merge-SlotSeed` 里 `$existingWords = if (...) { @($rows[$i].words) } else { @() }` —— PowerShell 的 if 表达式会**枚举摊平输出**：空数组变 `$null`、单元素变裸对象，于是下一行 `$existingWords.Count` 在 `Set-StrictMode -Version Latest` 下抛异常。ja 走的是"seed 不存在→直接复制"分支，所以只有第二个语言起才炸。

- 修法：使用点无条件再包一层 `@()`（`@($existingWords).Count`），只恢复数组语义、不改判定结果；同类隐患 `$defaultIds`（交互式选择）一并修。

- 顺带：安装器两处 catch 增加**出错行 + 调用栈**定位（此前只记消息，定位只能靠猜）——本次正是靠它一行定位到 398 行。

- 验证：`-Books ru -Update` → 该资产由失败转为成功，seed 合并为 20 槽（ja #1 / ru #2）；`-All -Update` → 其余 7 语言 seed 全部写入；store 20 槽含 9 行登记：ja 7922 / ru 8451 / fr 8116 / de 8062 / yue 384 / ko 7330 / ar 8118 / es 8599 / pt 8599。

- 回归：`tests/test_hub.ps1` 89 通过 0 失败。



### 已判定 P1-19 单词音频镜像：硬链接优化**否决**（保留复制）



- 测量：镜像目录 69918 个文件，与 pack 源同内容的 66785 个，可省 **669.1 MB**（9 语言）。

- 试验：`Sync-WordAudioMirror` 改为同卷硬链接（PS 5.1 `New-Item -ItemType HardLink`，跨卷自动退回复制），先删后建避免就地覆写。

- 否决理由（实测）：该目录**同时是游戏官方语音包自己的读写目录**（`已经下载【官方语音包】（请勿删除此文件）0720.txt` 就在其中）。镜像侧与 pack 源共享同一份数据后，游戏对同名文件的就地覆写会**反向污染 pack 源文件**——测试当场复现：往镜像侧写 4 字节 → 源文件由 3 字节变 4 字节，同一用例同时 FAIL。

- 结论：按"兼容优先 / 不损失最终使用效果"回退为复制，669 MB 冗余保留。

- 守卫：新增用例「镜像：写镜像侧不影响 pack 源文件」「镜像：重跑可把镜像侧改回与源一致」，实现改成链接即失败。

- 附带发现：镜像目录是**扁平的**，跨语言同名文件（`Abu.mp3` / `adoption.mp3` / `agent.mp3` 等）互相覆盖，现存 345 个"无同大小源"的历史残渣（约 3 MB）——保留不删（兼容优先）。



### 已知 P1-20 安装器会覆盖开发版插件（本轮实测）



- 现象：hub 安装的 mod 步骤把 `BepInEx\plugins` 下的 `WcpHost.dll` / `CustomSlotsMod.dll` / `BookNameMod.dll` 整包替换为**已发布载荷 v1.3.0**，仓库开发版（含 0.5.1 与采集改动）被覆盖。

- 对策：每次跑完安装器都要重新 `mod_*/build.cmd` 部署开发版（本轮已重新部署，三件 sha 与仓库一致）；发版前必须让载荷包含最新插件，否则用户装到的是旧版。



### 进行中 P1-16 面板判据：改为"信号取证"落地（待一次实机）



- 已实现：`GameCompat.CollectSignals`（候选信号打平成一行）+ `CustomSlotsMod.LogSignalsIfChanged`（仅在变化时追加）→ `wcp_diag\WcpSlotsSignals.txt`。

- 记录：chooser 可见性、旧标签判据结果、LastUserPageNum、CustomPageIndex、页签标签全文、`AllCanvas/SettingPart`、`CanvasSetting1`、`CanvasWordCount`、`Canvas-Hider` 的 active 状态（含 inactiveInHierarchy）。

- 目的：判据不再靠猜——一次实机在「自定义页 / 主界面 / 词数统计」之间切换，即可看出哪个信号真正跟着屏幕走。

- 已知线索：面板父节点是 `AllCanvas/SettingPart/CanvasWordCount/WcpCustomSlotsOverlay`（与词数统计界面**共用**同一 canvas），而旧判据只扫标签文字、`BookChooseManager` 在非选书界面仍 activeInHierarchy=True → 离开页面后判据恒真。



### 资源侧 P1-4（俄语无例句）已闭环



- `-All -Update` 后 9 语言 pack 全部含 `books/` + `audio/word` + `audio/sentence`；ru = books 3 / word 8451 / sentence 25048（此前只有 db/）。

- 未做：宿主 20 槽 UI（P1-15/P1-16）实机验证仍待一次游戏运行（信号取证已埋好）。





### 已实现 P1-15 20 槽原生外观（路线 A）



- 依据（截图 724678 + WcpSlotsDiag 实测差异）：行 = 原生 `Button-showWord` 160x30 `sprite=UISprite type=Sliced`，我们 708x48 纯色；原生页**没有**深色面板底/大标题；原生有 `Scrollbar Vertical`，我们 `vScrollbar=(none)`；字体 = 原生 `SourceHanSerifCN-Heavy SDF`（TMP），我们用 `LegacyRuntime.ttf`（传统 Text）。

- 改动：

  - `CollectNativeSprites()` —— 取原生行 sprite（`AllCanvas/Canvas-Hider/ShowWordNum-Group(book)/Button-showWord`）与原生滚动条背景/handle sprite（`Canvas-Gift/SellBox/InventoryList/Scrollbar Vertical`、手机聊天兜底）。

  - `EnsureVScrollbar()` —— 结构照原生克隆（背景 + Sliding Area + Handle），`direction=TopToBottom`、`Permanent`，美术用原生 sprite。

  - `ApplyNativeLook()` —— 隐藏面板底（`Image.enabled=false` + 关 raycast，不挡下层原生点击）与标题/说明文字；关闭/刷新按钮改右下角、底图换原生 sprite；内容间距改为 6。

  - 行体：高 48→**30**（照原生），底图换原生行 sprite（选中/受管仍用同 sprite 只改色调）。

  - `ResolveNativeFont()` —— 场景内原生 `Text.font` → TMP 资产 `sourceFontFile`（反射取，避免程序集依赖）→ 内置字体逐级回退，保证取不到也不会文字消失。

- 兼容性：任一原生资源取不到就退回自绘，并写 `CustomSlots: 路线A 原生外观 → ...` 日志（含每个资源的实际来源），机型差异可据此定位。

- **未验证**：实机外观（需要一次游戏运行）；判据修复后进自定义页才显示。



### 已修 P1-16 面板判据（实机证据，推翻旧判据）



- 证据（`wcp_diag\WcpSlotsSignals.txt` 4 行）：

  - 普通页 → `labels=日语词库(猫条版)|法语词库(猫条版)|俄语词库(猫条版)|德语词库(猫条版)|考博精选词`

  - 自定义页 → `labels=自定义词书一（日语词库(猫条版))|自定义词书二（…）|俄语词库(猫条版)|…`

  - 即 `GetNameTexts` 返回的就是**当前页 5 行文字**；旧判据的 `猫条版` 分支让**每一页**都命中（受管书页签名永远带这三个字）→ 离开页面后判据恒真，面板浮在词数统计/选择词汇书页上（截图 1db190、724678 两次）。

- 四个候选屏幕容器（`SettingPart` / `CanvasSetting1` / `CanvasWordCount` / `Canvas-Hider`）全程 `activeSelf=on` → **没有任何可用的切屏信号**，判据只能靠标签文字。

- 修法：标签扫描只认 `自定义词书`（删掉 `猫条版` 分支），保留"用户点击过第 20 页签"兜底。





### 已改 P1-15 路线 B：取消悬浮窗，原生行内嵌续接（用户裁定）



- 用户原话：『我不是要独立窗口，原生的窗口不是有4个槽位吗，我想在下面多实现16条』。

- 原生结构（WcpSlotsDiag.txt 实测）：自定义页 4 槽 = CanvasSetting1/bookNameBar (1..4)，

  431.61x25，sprite=XQ56_button_list_long（选中=_choose 变体），Button(SpriteSwap)+ButtonSound，

  左 TMP `_LeftN`（书名, fontSize=11）+ 右 TMP `_RightN`（已学统计, fontSize=9.5），

  绝对定位 y 步进 81.57；bookNameBar (5)（考博行）默认隐藏 = 现成克隆模板。

- 实现：

  - EnsureRowTemplate：取隐藏的 bookNameBar (5) 当模板（缺则 (1)），顺带从

    interactable=False 的行读选中态 sprite。

  - RebuildRowsNative：Instantiate 模板成 20 行；克隆体 Button 带原型序列化 onClick

    （会拿错索引调原生逻辑）→ DestroyImmediate 换新 Button 再挂 Select(i)。

    左文本写 RowLabel，可管理行右侧放 改名/移除 小按钮，空槽右侧写"（空）"。

  - AlignToNativeBookList：用 bar(1)/bar(5) 世界角算列表区域，换算 lossyScale 后

    把覆盖层精确贴上去（不再居中悬浮）。

  - HideNativeBars/RestoreNativeBars：本 mod 20 行接管期间收起原生 5 条，Hide 恢复。

  - GameCompat.WriteText：反射写 TMP text（无编译期 TMPro 依赖）。

  - 滚动：Content spacing=56.5（=81.57 步进 - 25 行高），行宽高交给克隆体自带尺寸。

- 回退链：模板取不到 → 老自绘行；bar 几何取不到 → 居中几何。

- 回归：hub 89/0、slot_rules 0 失败、registry 全部通过、slot_ownership ALL PASS。

- 待实机确认：克隆行外观/点击/改名移除按钮位置、离开页面原生 4 行恢复。





### 已加固 P1-17 兼容层：作者更新（加槽/改键/改节点）后长期稳定



原则：兼容层所有"数量、键名、节点路径、方法名"都不再写死——探测 + 候选 + 特征扫描，

失败一律回退当前行为并写日志，绝不阻断加载。



1. 原生槽位数量探测（作者 4→5/6/… 自动跟随）：

   - 信号 = ES3 键 SelfBookListN 存在（ES3.KeyExists 反射）或 Parameters 静态字段

     SelfBookListN 已声明，从 1 连续数到第一个缺口；下限 4（首次启动键未建时保底）。

   - GameCompat.DetectListSlotCount(path) 在 Awake 里、ImportNativeBooksNow **之前**

     跑（顺序错了首次启动会漏导入新槽的原生书）；结果回填

     SlotRules.SetNativeSlotCount / CurrentNativeSlots（MinNativeSlots=4 下限保护，

     MaxNativeSlotsProbe=64 上限防呆）。规则函数全部改用 CurrentNativeSlots；

     NativeSlots 常量保留为历史下限，旧调用/旧测试不受影响。

   - mod_host/GameAdapter.SlotWords 同样探测回填（self-contained，缓存一次）。

   - 键名走 GameCompat.ListKeyFor/NameKeyFor（候选格式表，作者改键名补一处即可）。

2. 入口方法候选化：OnBookButtonClicked / OnBookButtonClick / OnClickBookButton，

   全不中再在已确认的 chooser 类型内做模糊匹配（void + 单 int + 名字含 Book&Click/Choose）；

   通配类型扫描不用模糊匹配，防误配。类型候选补 S12/S13。

3. 原生列表根与行枚举去写死：

   - 列表根：精确候选（CanvasSetting1/2）→ 按"子节点有 bookNameBar 行"特征扫描

     SettingPart 全域（作者改页名/挪层级不失联），命中即缓存路径并写日志。

   - 原生行：按 "bookNameBar" 前缀枚举全部行（模板=隐藏行优先，选中态 sprite 从

     interactable=False 的行取），不再假设 5 行——作者加行自动跟随。

   - 行文本节点名候选化（Text _Left/_Right 前缀表）+ 位置兜底（左=首子/右=末子）。

4. 测试：SlotRulesTest 新增 6 条（默认下限、回填生效、槽 5 导入、落位 native-5、

   回到 4 槽拒绝越界导入、越界槽不算受管）。

5. 回归：slot_rules 74 PASS/0 FAIL；registry 全部通过；slot_ownership ALL PASS；

   takeover 0 失败；word_audio 0 失败；test_hub 89/0；mod 构建零告警并已部署。

6. 边界说明：探测键名候选当前只有 SelfBookList{0}/SelfBookName{0}（与游戏现状一致）；

   作者若改键名格式，补 ListKeyFormatCandidates/NameKeyFormatCandidates 一行即可。

   languages/ja 快照与主源已漂移（独立事项，未混入本次）。





### 已收敛 P1-18 兼容层第二轮（三个残余写死簇 + 探针抓出一个引入 bug）



1. Canonical/NativeCanonical 中文槽名生成化：

   - 旧 switch 写死 1..4，**槽 5+ 会错写成"自定义词书四"并落进存档**（P1-17 加槽跟随

     路径上的真 bug）。改为 CnDigits 生成器：1..9 直接映射、10..99 十位组合、>99 防呆

     回"原生槽位N"。NativeCanonical 与 Canonical 合并为同一生成器。

   - 离线探针（源码同文编译）12 用例全过：1/2/4/5/9/10/11/12/20/48/99/100。

   - 探针首跑抓到第一版生成器 `<=10` 分支 CnDigits[10] 越界（IndexOutOfRange），

     已修为 `<=9` + `>=10` 双分支后复跑全过 —— 这就是"源码同文探针"的价值。

2. InvokeNoArg 失败可见化 + 缓存：

   - 以前 GetMethod 找不到就静默 return（游戏改刷新方法名 → UI 不更新且无日志）。

     现在找不到方法记警告（含类型名+方法名，唯一定位点），调用异常也记警告。

   - (类型,方法) 解析结果缓存（含负缓存），Materialize 高频路径不再反复全量扫描。

3. mod_host 类型名单点化：30 处裸 "MyParameters" 字符串收敛到

   GameAdapter.ParametersType 常量（Host/HostRuntime/TakeoverScope/SentenceAudioService

   全部替换；作者改类型名只改一处）。键名/字段名不动（那是字段候选表的职责）。

4. GameCompat.FindTypeByName 加 Dictionary 缓存（负结果也缓存）——

   StaticFieldExists 每槽每键都会走它，不缓存就是全程序集 GetTypes() × N。

5. 回归：mod/mod_host 构建零 error（CS0618 为 SentenceAudioService 既有过期 API 警告，

   与本次无关）；slot_rules 74/0；registry 全部通过；ownership ALL PASS；

   takeover 0；word_audio 0；hub 89/0；payload 重建 71a1b2d9ff1ee26f。

6. 说明：Canonical 用例在离线套件 SKIP（测试工程只编译模型），以源码同文探针为准；

   探针脚本 _local/audit/_canon_probe.cs 保留，改生成器后重跑即可。





### 已收敛 P1-19 兼容层第三轮（ES3 缓存 + ja 快照归一）



1. ES3 重载解析缓存（Save/Load/KeyExists 三处）：以前每次落盘/读档/探测都全量

   GetMethods 扫描，现在各解析一次并缓存（含负缓存 + 找不到重载时的警告文案）。

   Es3Save 现在还会在重载缺失时显式报"写档不可用"（以前静默 return）。

2. languages/ja/mod_custom_slots 快照归一（消除伪权威源）：

   - 三源（CustomSlotsMod/CustomSlotModel/GameCompat.cs）与 SlotRulesTest.cs 已从

     主源复制同步；ja 快照此前是旧架构（无 GameCompat、兼容函数内嵌、P1-17/18 缺失）。

   - ja build.cmd 修两处：源清单补 GameCompat.cs；REFS 补

     UnityEngine.InputLegacyModule.dll（F8 键）与 Unity.TextMeshPro.dll（TMP 反射

     类型解析），与主源 build.cmd 一致。修正后 ja 快照独立构建可编译、可部署。

   - ja 快照测试 74 PASS/0 FAIL（与主源同套用例）。

   - 产物哈希说明：主源 DLL（游戏内部署版）与 ja 快照 DLL 哈希不同属正常 ——

     csc 引用程序集集不同（主源带 TMP 引用、ja 现 TMP/UI 引用顺序一致但

     csc 时间戳不同），源码同文即可；构建部署以主源 mod_custom_slots/build.cmd 为准。

3. 回归：slot_rules 74/0（主源与 ja 快照各跑一遍）、registry 全部通过、

   ownership ALL PASS、takeover 0、word_audio 0、hub 89/0、mod/mod_host 构建 0 error、

   payload 重建 e6edb875d531add5。

4. 教训记录：快照目录的 build.cmd 与主源 build.cmd 的源清单/引用集必须同步维护，

   否则快照可编译性是假的（旧清单连 InputLegacyModule 都没有，F8 热键都编不过）。





### 已修 P1-15b 路线B实机三连（截图 6c6ddc + OCR 坐标对比定位）



症状（3494px 截图，≈1.87px/单位）：20 行都在渲染但行距 58px（=31 单位，应为 81.57）、

行整体偏移 (-173,+168)、左栏只剩"条版）…7922 词 [mod]"尾部碎片、原生右栏"已学"消失。



根因（三个都是"只在首次创建配置、复用全跳过"）：

1. spacing=56.5 与对位只写在 Show() 新建分支；覆盖层复用时（_overlay != null）直接

   RebuildRows —— 上个会话建层时原生行还没找到（走了老布局 6px + 居中），之后永远老几何。

2. RowLabel 是自绘时代长格式（槽位 N + 名 + 词数 + [mod]），原生左栏 247.85 宽/框高 18px，

   换行即裁 → 只剩尾巴。

3. 原生右栏"已学"消失是**符合预期**（克隆行接管、右栏被我们改写）。



修法：

- 新增 EnsureNativePresentation()（幂等）：spacing=56.5 + childControl×4 + 对位 +

  HideNativeBars，复用路径 Show() 也调用；新建路径不再重复写。

- RowLabel 改原生短格式 "N. 书名"（>16 字符截断防换行），词数/来源移到 RowRightLabel

  写右栏（原生右栏本来就放统计）；可管理行右栏也写词数，按钮浮其上不冲突。

- 回归：构建零告警已部署；slot_rules 74/0；ownership ALL PASS。

- 待实机确认：行距/对位/左栏完整书名、右栏词数。





### 已查明 P1-20：自定义书出现在官方分类页（不是 mod 写坏数据）



现象：大学四级列表第 4 行 = 「德语词库(猫条版) 8:8062」（用户截图 45606d）。



证据链：

1. 313c87（用户标注"原生"的同机截图）四级页第 4 行同样 = 8:8062 —— mod 前后一致。

2. MyBook_CopyOriginal（游戏出厂词库存档）：SelfBookList4 = red/green/blue...

   颜色示例词 11 个 —— 出厂时这个槽就有内容且会被显示。

3. Assembly-CSharp.dll：SonButtonSetting/SonBookChoose 渲染逻辑 +

   "自定义词书一/二/三/四"规范名表 —— 4 个自定义槽是全局槽。

4. 行 4 进度 8:8062 与自定义页槽 4（德语 8062 词）完全一致 = 同一数据源 SelfBookList4。



机制：游戏把「自定义词书四」渲染进每个分类页 Son 列表尾部（出厂态显示

"自定义词书四 0:11"颜色示例词）；BookNameMod 把该槽显示名美化成

"德语词库(猫条版)"，于是在四级页也顶着这个名字 —— 游戏行为 + 美化叠加，

非数据串写。mod 从未写过任何官方分类词表（四级官方 3 本 2359/4079/5200 不变）。



待用户决策：A) 接受现状（游戏原生行为，槽4内容本来就会出现在各分类页）；

B) BookNameMod 只在自定义页美化、官方分类页恢复显示"自定义词书四"

（按页签判定，有实现成本与回退风险）；C) 清空槽 4（放弃德语，腾出全局槽）。




### 已落地 P1-20-B：BookNameMod 只在自定义分类页美化（2026-09-18）

决策：采纳 **B**（用户 2026-09-18 拍板）。保留游戏原生行为 —— 槽 4 仍会出现在每个
官方分类页尾部，但那行恢复显示游戏规范名「自定义词书四」，不再顶着「德语词库(猫条版)」；
只有「自定义」分类页继续显示美化名。

页签判据（这次不猜了，改用游戏自己的状态）：
- `WordChooseButtonS10.clickNum` = 当前 Father(分类) 索引。反编译核对
  （`Japanese/work/decompiled/WordChooseButtonS10.cs`）：`OnBookButtonClicked(num)`
  末尾 `clickNum = num;`，**case 20 = 自定义**；`clickThisButtonAgain()` 复用 clickNum 重绘。
- 兜底/校准：游戏在自定义页写的行带全角括注「自定义词书N（SelfBookNameN）」（case 20 源码）
  → 看到这种原生行就说明此刻在自定义页，顺手把索引记准（游戏以后改类别顺序也能自适应）。
- 判据全不可用（游戏改掉字段名）→ 一律按「不是自定义页」处理 = 显示游戏原生名。
  fail-safe：绝不会把规范名写进美化名位置，不会跨页错乱。

改动（4 文件，纯显示层，不碰存档数据）：
- `mod_book_name/BookNameMod.cs`（1.3.0 → 1.3.1）：新增 `LabelPageGate`（纯逻辑）+
  `LabelGate`（页签判定 / 选书页行枚举）；`Scan` 与 `SonBookChoose` 的 Postfix 都改成
  「按分类页定名」；新增 `RestoreRowNamesOffCustomPage`（离开自定义页时把美化过的行还原成原生名）。
- `mod_host/GameAdapter.cs`：同一套 `LabelPageGate` + `ChooserType()/ChooserInstance()/
  CurrentCategory()/IsCustomPage()/CanonicalNames()`（宿主侧判据同源）。
- `mod_host/HostRuntime.cs`：`ScanBookLabels` 按分类页定名（自定义槽行在官方页写原生名）。
- `mod_host/Host.cs`（0.5.1 → 0.5.2）。

验证（离线，已完成）：
- `mod_book_name/build.cmd`、`mod_host/build.cmd` 均 BUILD OK（只有原有告警），已部署到
  `BepInEx/plugins/`；部署产物 SHA256 与仓库产物一致（BookNameMod `7d41b496…`、WcpHost `b9b76241…`）。
- 源码同文探针 `_local/audit/gate_probe.py`：从 `BookNameMod.cs` 原样抽取 `LabelPageGate`
  编译运行，**16/16 PASS**（含最关键的「官方页裸名不动」「官方页还原美化名」「括注行识别」
  「括注里的半角括号不误判」「空判据不崩不改写」）。

待实机确认（用户，游戏重启后）：
1. 大学四级页 → 第 4 行应显示「自定义词书四 8:8062」（原生名 + 词数），不再是「德语词库(猫条版)」。
2. 切到自定义页 → 4 行仍显示美化名（日语/法语/俄语/德语词库(猫条版)）。
3. 来回切几个官方分类页 → 第 4 行保持原生名；回自定义页仍美化（无残留、无抖动）。
4. `BepInEx/LogOutput.log` 里应出现一次「BookName: 自定义分类索引 = 20（来自原生括注行）」——
   出现即说明判据确实被原生括注行校准过。
5. 回归：点选书行、学习/复习入口、20 槽面板显示不受影响。

回退：`git checkout` 这 4 个文件 + 重新 build 部署即可（纯显示层，无数据迁移）。

未做（待用户决定）：5 个语言子仓（French/German/Japanese/Russian/Contonese）与
`MultiLanguage/languages/*/mod_book_name/` 的同源副本未同步此改动 —— 发布链只打包
`MultiLanguage/mod_book_name/BookNameMod.dll`（`tools/release/build_mods_payload.py` 第 27 行），
其余副本既不打包也不部署；如需保持源码一致，要逐份 diff 后同步。

### P1-20-B 全量子仓与同源副本对齐（方案 2，2026-09-18）

- 范围：全盘 11 处 `BookNameMod.cs` 与 `BookProfiles.cs` 完成 SHA256 逐字节归一对齐（版本全部升至 1.3.1，Option B 逻辑到位，9 语言完整指纹登记）。
- 提交对齐：
  * MultiLanguage: `686fa83`（languages/*/mod_book_name 副本 + BookProfiles 补齐 9 语）+ `4d9a21c`（最终一致部署 DLL）
  * German: `8691e4e`
  * Contonese: `368298a`
  * French: `288fdf5`
  * Russian: `671c808`
  * Japanese: `7103645`
- 构建回归：
  * `gate_probe.py` 16/16 PASS
  * `test_custom_slots.ps1` 11/11 PASS
  * `test_hub.ps1` 89/89 PASS
  * `build_mods_payload.py` 产出匹配最新部署 DLL（sha256: `874d04c0…`）
  * 游戏本体 `BepInEx/plugins/BookNameMod.dll` 已更新并断言逐字节一致
