# WCP 多语言集成项目（WCP-MultiLanguage）

《万词破 · 单词女友》多语言词书的统一接入层：**一套宿主 + 资源包契约 + 一键安装器**。
语言资源物理隔离、互不读写；只有被选中的词书才由宿主激活。新增语言原则上只提供资源包
（manifest + 词库 + 数据库 + 音频），复用宿主通用策略；只有行为特殊的语言才需要自己的策略程序集。

> **状态：阶段 2 实施中。** 宿主、20 个逻辑槽位、资源隔离与一键安装器已落地，
> 注册表 / 槽位 / 接管 / 安装器测试全部通过；多语言实机切换矩阵尚未完成最终验收。
> **2026-09-15 起本仓库是所有语言唯一的提交目标**：9 个语言工程的工作区已集成到
> `languages/<code>/`（来源与排除项见 [languages/README.md](languages/README.md)、
> [languages/PROVENANCE.json](languages/PROVENANCE.json)），宿主、槽位、资源包契约与安装器在仓库根部。
> **发布边界：集成版安装包与资源包的 release 一律从本仓库发布**；日语词书本体与日语语音包
> 保留在 `hanserdesu/japanese`（其余语言的语音包全部由本仓库发布）。

## 仓库结构

| 路径 | 内容 |
|---|---|
| `mod_host/` | 统一宿主 `WcpHost.dll`：资源路由、包清单、通用语言策略、接管范围（含 `tests/`） |
| `mod_custom_slots/` | 20 个逻辑槽位 `CustomSlotsMod.dll`：同页滚轮选择管理，外部词书不被接管（含 `tests/`） |
| `mod_book_name/` | 书名 / 身份层 `BookNameMod.dll`（`BookProfiles` + 诊断） |
| `packs/` | 语言资源包契约：每语言一个 `manifest.json`（ja / fr / ru / de），ja 含词库与数据库负载 |
| `tools/` | 迁移与生成工具：`migrate_legacy_host_yield.py`、`gen_bookprofiles.py` |
| `tools/release/` | 资源包发布流水线：`build_all_languages.py`、`make_release_manifests.py`、`publish_release.py`、`merge_catalog_rows.py`、`build_installer.py`（安装器打包与自更新索引），以及各语言的 release 清单与发布记录 |
| `tools/integrate_languages.py`、`tools/verify_integration.py` | 语言工程集成与一致性校验工具 |
| `languages/<code>/` | 9 个语言工程的源码树（ja / fr / ru / de / es / pt / ko / ar / yue），含集成时未提交的在研改动 |
| `Install-WCP-Wordbooks.ps1`、`WordbookHub.psm1`、`catalog.json` | 一键安装器：GitHub 发现词书、选择安装、峰值磁盘检查、SHA-256 差异更新 |
| `一键安装词书.cmd`、`更新词书资源.cmd` | 给玩家的双击入口 |
| `ARCHITECTURE-UNIFIED.md` | 统一接入架构设计（Host / Pack / Strategy） |
| `INSTALLER.md` | 安装器与资源契约完整说明 |

## 快速使用（玩家）

- `一键安装词书.cmd`：列出全部词书，输入编号（可逗号分隔或 `all`）选择安装。
- `更新词书资源.cmd`：等价 `-Update`，默认选中已安装词书，回车即更新。
- 安装前按 `hub-state.json` 记录的 SHA-256 逐项比对，只重新下载内容变化的资源。
- 经 `run-installer.ps1` 启动时带版本注入：在线模式下若资源 release 上有更新的
  `release-index.json`，会提示升级（确认才切换，失败不影响本次安装）。

```powershell
.\Install-WCP-Wordbooks.ps1 -List
.\Install-WCP-Wordbooks.ps1 -Plan -Books fr,ja -GameDir 'D:\Games\WCP'
.\Install-WCP-Wordbooks.ps1 -Books fr,ja -GameDir 'D:\Games\WCP'
.\Install-WCP-Wordbooks.ps1 -Update -GameDir 'D:\Games\WCP'
.\Install-WCP-Wordbooks.ps1 -Offline -GameDir 'D:\Games\WCP'
```

## 开发与验证

```powershell
# 宿主：身份层注册表测试（读取 packs/*/manifest.json 与存档槽位）
cmd /c mod_host\tests\run_registry_test.cmd

# 宿主：接管范围测试（战斗词池 / 还原语义）
powershell -File mod_host\tests\run_takeover_test.ps1

# 槽位：20 槽行为规则测试
powershell -File mod_custom_slots\tests\run_slot_rules_test.ps1

# 安装器：离线单元测试（无网络、不写游戏目录）
powershell -File tests\test_hub.ps1

# 集成一致性：languages/<code>/ 与原语言仓库工作区逐文件 sha256 比对
python tools\verify_integration.py
```

构建：`mod_host\build.cmd`、`mod_custom_slots\build.cmd`、`mod_book_name\build.cmd`、
日语策略 `mod_host\strategies\build_ja.cmd`。

## 词书资源质量审计（Jev 与契约 100% 验证）

本项目收录的 9 门语言（ja / fr / ru / de / es / pt / ko / ar / yue）词书资源已建立完整的自动化质量把关与多维度契约测试：

- **双轴 Jev 语义决策审查**：全量词表通过 TypeSafe Jev 决策模型进行语义释义与发音注音双轴审查。针对多义词串流、占位释义、英法同形词干扰等残余缺陷实施了清洗与补全，全部修改项均经 Jev 采纳裁决（Round 3 残余 283 项语义缺陷已全数闭环处理）。
- **例句与音频端到端契约**：运行 python tools/check_sentence_contract.py，全量 215,813 条例句与对应的 Edge TTS 原生音频切片（严格基于例句原文 MD5 哈希定址）匹配率达到 100% PASS。
- **运行时部署一致性校验**：运行 python tools/sync_packs.py --check-deployed，9 语部署包运行时 SQLite 数据库、例句表与 manifest 逐字节比对 100% PASS。
- **安装器磁盘健康防护**：引入 P1-9 磁盘健康核对钩子（Test-WordbookDiskHealth），当本地音频目录缺失或词表被破坏时，更新流程能自动感知并摘除损坏记录，触发全量修复重下。

## 系统设计边界与局限性

在享受多语言与扩展槽位便利的同时，以下为当前工程架构的既有物理边界与运行局限性：

1. **原生物理槽位数量约束**：
   受游戏底层内部数据结构限制，游戏存档（MyBook.es3）硬编码仅有 4 个物理 SelfBookListN 字段。
   本 mod 提供的 20 槽是 CustomSlotsMod 在前端维护的独立逻辑槽位（WcpCustomSlots.json），同一时刻最多只能将激活的词书物化入空闲的原生槽位，无法突破底层游戏引擎的并发物理槽位上限。

2. **实机热切换与游戏引擎缓存**：
   虽然所有路由隔离、词池重构与 89 项离线单元测试均已全量通过，但游戏内部的单例状态机（MyParameters / ChooseWordManager）在跨场景时存在静态缓存。
   为杜绝极端战斗场景下底层引擎未能即时释放上一本词书的音频句柄或纹理，建议在游戏主菜单界面进行词书选择，或在完成跨语言大幅切换后重新启动游戏。

3. **语言处理策略分层**：
   法语、俄语、德语、西班牙语、葡萄牙语、韩语、阿拉伯语等 7 种语言均已实现完全解耦的纯数据包，复用宿主内置的 GenericLanguageStrategy；
   日语因假名与振假名读音回查需加载独立策略程序集（WcpPack.Ja.dll），粤语包含注音解析程序集（WcpPack.Yue.dll）。新追加语言若无特殊拼写行为，仅需提供数据资源即可。

4. **特殊音标保守留空原则**：
   音标数据严格坚持不主观推断与不臆造原则。针对第三方词典数据集中未能收录或格式不兼容的 10 处特殊注音数值，系统按规保持为空，不伪造拼音或注音，不影响正常背词与中文释义展示。

5. **外部词书服务边界**：
   本 mod 仅对本 mod 托管范围内的词书提供定制释义数据库与专属音频路由服务。用户原有的外部自定义词书镜像进入 20 槽后标记为外部所有（owner: external, managed: false），宿主对其执行严格的 fail-closed 保守放行，不篡改其词表与数据，外部词书不享有本 mod 的多语言例句与私有音频增强。


## 目录状态说明

`catalog.json` 中 9 本词书的语音资源均已发布并逐项校验（`status: available`）：

| 词书 | 资源发布位置 | 当前 tag |
|---|---|---|
| `ja` | `hanserdesu/japanese`（日语本体保留在原仓库） | `wcp-jp-resources-v1.0.0` |
| `ar` | 本仓库 | `wcp-ar-resources-v1.1.0` |
| `de` | 本仓库 | `wcp-de-resources-v1.1.1` |
| `es` | 本仓库 | `wcp-es-resources-v1.1.0` |
| `fr` | 本仓库 | `wcp-fr-resources-v1.0.0` |
| `ko` | 本仓库 | `wcp-ko-resources-v1.1.2` |
| `pt` | 本仓库 | `wcp-pt-resources-v1.1.0` |
| `ru` | 本仓库 | `wcp-ru-resources-v1.1.0` |
| `yue` | 本仓库 | `wcp-yue-resources-v1.0.0` |

一键安装器本体自 `wcp-installer-v0.1.0` 起带**自更新**（方案 C：版本索引
`release-index.json` 挂在 `wcp-mods-*` release 上，有新版仅提示、用户确认才下载切换，
SHA-256 校验通过才启动新包，任何异常不阻断安装）。各语言版本以 `catalog.json` 为准，
逐资产 `url` / `size` / `sha256` 均与 release 实测一致。

每条 asset 都带 `url` / `size` / `sha256`（或 GitHub 的 sha256 digest），安装器直接按 `url`
下载并逐项校验。资源**不依赖** GitHub 的仓库发现流程：多语言仓库有多个 release 且每个都带
同名 `release-manifest.json`，发现流程会把别的语言资源串进来，因此以打包在目录里的固定
asset 列表为准。`disk.extract_mb` 是按 zip 内实际文件大小算出的解压占用，用于峰值磁盘检查。

条目里的 `repo` 仍是每种语言自己的词书仓库，不是资源所在的仓库：安装器的在线发现按 `repo`
建索引，两本词书共用一个仓库会被折叠成一条（`tests/test_hub.ps1` 里有对应断言）。资源到底
从哪个 release 下载，只看每条 asset 的 `url`。

语音包的打包与发布流程见 [INSTALLER.md](INSTALLER.md#资源包发布流程)；流水线脚本已随本仓库
版本化在 `tools/release/`，构建产物（音频 zip 等）仍留在本地 `_local/release/` 不入库。

## 迁移说明

1. **2026-09-15 上午（初始快照）**：`hanserdesu/japanese` @ `5283a39` 提供宿主、槽位、
   书名层、packs、迁移工具与架构文档（含当时工作区中未提交的槽位测试与 packs 载荷文件）；
   `hanserdesu/WCP-Wordbook-Hub` @ `3c6ed26` 提供安装器、目录、双击启动器与安装器测试。
2. **2026-09-15 资源包发布**：8 种语言（ar / de / es / fr / ko / pt / ru / yue）的语音资源包在本仓库发布，
   `catalog.json` 中 9 本词书全部转 `available`。
3. **2026-09-15 日语回滚**：`hanserdesu/japanese` 的 `master` 回滚到 `8e48f6a`（tag `wcp-jp-v1.2.2`），
   即群友正在使用的稳定版。回滚移除了 12 个尚未验收的提交，它们完整保存在本地分支
   `archive/pre-freeze-2026-09-15`、reflog，以及下面第 4 条的工作区集成里。
4. **2026-09-15 全量集成**：9 个语言工程的工作区（tracked 全量 + 未提交改动）复制进
   `languages/<code>/`，逐文件 sha256 记录在 `languages/PROVENANCE.json`，
   `python tools\verify_integration.py` 可随时复核。至此各语言不再分散提交，
   日语词书本体与日语语音包的 Release 保留在 `hanserdesu/japanese`。

## 许可

本仓库采用分层许可：代码、内容与词典数据各自适用不同条款，范围说明与上游署名见 [ATTRIBUTION.md](ATTRIBUTION.md)。

- 代码（宿主、槽位、插件、安装器、工具）：[PolyForm Noncommercial License 1.0.0](LICENSE)。个人学习、研究与其它非商业用途可以自由使用、修改和再分发；商业用途请联系作者另行授权。
- 内容（选词分级、中文释义、例句、语音）：CC BY-NC-SA 4.0。使用时需署名，不得用于商业目的，改编作品以相同方式共享。
- 词典数据（音标、重音、汉字读音等由第三方数据集派生的逐项数值，来源见 ATTRIBUTION.md）：CC BY-SA 4.0。需保留上游署名，衍生数据以相同方式共享。
