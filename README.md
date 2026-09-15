# WCP 多语言集成项目（WCP-MultiLanguage）

《万词破 · 单词女友》多语言词书的统一接入层：**一套宿主 + 资源包契约 + 一键安装器**。
语言资源物理隔离、互不读写；只有被选中的词书才由宿主激活。新增语言原则上只提供资源包
（manifest + 词库 + 数据库 + 音频），复用宿主通用策略；只有行为特殊的语言才需要自己的策略程序集。

> **状态：阶段 2 实施中。** 宿主、20 个逻辑槽位、资源隔离与一键安装器已落地，
> 注册表 / 槽位 / 接管 / 安装器测试全部通过；多语言实机切换矩阵尚未完成最终验收。
> **发布边界：集成版安装包与资源包的 release 一律从本仓库发布**；
> `hanserdesu/japanese` 只保留日语词书本体。

## 仓库结构

| 路径 | 内容 |
|---|---|
| `mod_host/` | 统一宿主 `WcpHost.dll`：资源路由、包清单、通用语言策略、接管范围（含 `tests/`） |
| `mod_custom_slots/` | 20 个逻辑槽位 `CustomSlotsMod.dll`：同页滚轮选择管理，外部词书不被接管（含 `tests/`） |
| `mod_book_name/` | 书名 / 身份层 `BookNameMod.dll`（`BookProfiles` + 诊断） |
| `packs/` | 语言资源包契约：每语言一个 `manifest.json`（ja / fr / ru / de），ja 含词库与数据库负载 |
| `tools/` | 迁移与生成工具：`migrate_legacy_host_yield.py`、`gen_bookprofiles.py` |
| `Install-WCP-Wordbooks.ps1`、`WordbookHub.psm1`、`catalog.json` | 一键安装器：GitHub 发现词书、选择安装、峰值磁盘检查、SHA-256 差异更新 |
| `一键安装词书.cmd`、`更新词书资源.cmd` | 给玩家的双击入口 |
| `ARCHITECTURE-UNIFIED.md` | 统一接入架构设计（Host / Pack / Strategy） |
| `INSTALLER.md` | 安装器与资源契约完整说明 |

## 快速使用（玩家）

- `一键安装词书.cmd`：列出全部词书，输入编号（可逗号分隔或 `all`）选择安装。
- `更新词书资源.cmd`：等价 `-Update`，默认选中已安装词书，回车即更新。
- 安装前按 `hub-state.json` 记录的 SHA-256 逐项比对，只重新下载内容变化的资源。

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
```

构建：`mod_host\build.cmd`、`mod_custom_slots\build.cmd`、`mod_book_name\build.cmd`、
日语策略 `mod_host\strategies\build_ja.cmd`。

## 目录状态说明

`catalog.json` 中所有词书当前均为 `pending_release`：集成版资源包将在本仓库的发布流程中
重新发布后逐个转为 `available`。`-List` 仍会显示这些词书，但在资源可用前不可选择安装。

## 迁移说明

本仓库初始内容快照自 2026-09-15 上午的工作区：

- `hanserdesu/japanese` @ `5283a39`：宿主、槽位、书名层、packs、迁移工具、架构文档
  （含当时工作区中未提交的槽位测试与 packs 载荷文件）
- `hanserdesu/WCP-Wordbook-Hub` @ `3c6ed26`：安装器、目录、双击启动器、安装器测试

japanese 仓库中仍在收尾的集成开发迁移完成后，本仓库将成为集成项目的唯一开发与发布源。
