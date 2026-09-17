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
