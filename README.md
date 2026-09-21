# WCP 多语言集成项目（WCP-MultiLanguage）

《万词破 · 单词女友》多语言词书的统一接入层：一套宿主 + 资源包契约 + 一键安装器。
语言资源物理隔离、互不读写；只有被选中的词书才由宿主激活。新增语言原则上只提供资源包
（manifest + 词库 + 数据库 + 音频），复用宿主通用策略；只有行为特殊的语言才需要自己的策略程序集。

当前状态：统一接入架构全部交付落地。
统一宿主（WcpHost）、20 个逻辑槽位（CustomSlotsMod）、语言物理隔离、Jev 全量双轴审计（9 语 100% 通过）与一键安装器（v0.1.5）已全量落地验证。
注册表 / 槽位规则 / 接管范围 / 磁盘健康 / mod 物理自愈 / 自更新链 / 双击入口窗口保留 / 安装器测试 113/113 项全部通过；9 语部署包运行时与仓库逐字节一致。
本仓库为所有语言唯一的单一事实源；集成版安装包与资源包统一由本仓库发布。

## 仓库结构

| 路径 | 内容 |
|---|---|
| `mod_host/` | 统一宿主 `WcpHost.dll`：资源路由、包清单、通用语言策略、接管范围（含 `tests/`） |
| `mod_custom_slots/` | 20 个逻辑槽位 `CustomSlotsMod.dll`：同页滚轮选择管理，外部词书不被接管（含 `tests/`） |
| `mod_book_name/` | 书名 / 身份层 `BookNameMod.dll`（`BookProfiles` + 诊断） |
| `packs/` | 语言资源包契约：9 门语言（ja / fr / ru / de / es / pt / ko / ar / yue）全量 `manifest.json`、词库、SQLite 释义库与例句表 |
| `tools/` | 迁移、构建与校验工具：`check_sentence_contract.py`、`sync_packs.py`、`gen_bookprofiles.py` 等 |
| `tools/release/` | 资源包发布流水线：`build_installer.py`（安装器打包、自更新索引与仓库根索引同步）、发布清单与 catalog 维护脚本 |
| `tools/integrate_languages.py`、`tools/verify_integration.py` | 语言工程集成与一致性校验工具 |
| `languages/<code>/` | 9 个语言工程的源码树（ja / fr / ru / de / es / pt / ko / ar / yue） |
| `Install-WCP-Wordbooks.ps1`、`WordbookHub.psm1`、`catalog.json` | 一键安装器核心：GitHub 发现词书、选择安装、峰值磁盘检查、P1-9 词书磁盘健康核对、mod 物理健康自愈（`Test-ModDiskHealth`）、SHA-256 差异更新 |
| `run-installer.ps1` | 安装器启动器：自更新版本注入、异常展开排查、预填 GitHub 反馈 |
| `一键安装词书.cmd`、`更新词书资源.cmd` | 给玩家的双击免配置入口 |
| `ARCHITECTURE-UNIFIED.md` | 统一接入架构设计（Host / Pack / Strategy） |
| `INSTALLER.md` | 安装器与资源契约完整说明 |

## 快速使用（玩家）

- `一键安装词书.cmd`：列出全部词书，输入编号（可逗号分隔或 `all`）选择安装。
- `更新词书资源.cmd`：等价 `-Update`，默认选中已安装词书，回车即更新。
- 窗口不会自己消失：两个双击入口都用 `--keep-open` 自重启一个常驻 CMD 会话，安装流程结束后窗口留在原地，由你点击右上角 X 关闭，中途状态、错误链与最终结果都看得到。
- 智能差异比对：安装前按 `hub-state.json` 记录的 SHA-256 逐项比对，只重新下载内容变化的资源。
- 磁盘健康自愈（词书层）：更新时自动通过 `Test-WordbookDiskHealth` 核验本地文件完整度，若音频丢失或词表损坏自动摘除记录并全量重下修复。
- 磁盘健康自愈（mod 层）：安装前通过 `Test-ModDiskHealth` 核验 `BepInEx/plugins` 下的核心三件套（`WcpHost.dll` / `CustomSlotsMod.dll` / `BookNameMod.dll`）。发现被改名禁用的 `.disabled` / `.off` / `.bak` 副本自动改名回正、发现 0 字节损坏强制重新物化 mods 载荷，即使 `hub-state.json` 记录为最新也不会跳过。
- 自更新机制：经 `run-installer.ps1` 启动时自动检查更新，若有新版安装器提示确认后平滑切换，失败不阻断本次安装。版本索引按三条通道依次取用：仓库根 `release-index.json` 的 raw 地址（不消耗 GitHub API 配额、不受资产 CDN 缓存影响）、`wcp-mods-*` release 的资产接口（显式声明 `Accept: application/octet-stream`）、以及同一资产的下载地址。

```powershell
.\Install-WCP-Wordbooks.ps1 -List
.\Install-WCP-Wordbooks.ps1 -Plan -Books fr,ja -GameDir 'D:\Games\WCP'
.\Install-WCP-Wordbooks.ps1 -Books fr,ja -GameDir 'D:\Games\WCP'
.\Install-WCP-Wordbooks.ps1 -Update -GameDir 'D:\Games\WCP'
.\Install-WCP-Wordbooks.ps1 -Offline -GameDir 'D:\Games\WCP'
```

## 词书资源质量审计（Jev 与契约 100% 验证）

本项目收录的 9 门语言（ja / fr / ru / de / es / pt / ko / ar / yue）词书资源已建立完整的自动化质量把关与多维度契约测试：

- 双轴 Jev 语义决策审查：全量词表通过 TypeSafe Jev 决策模型进行语义释义与发音注音双轴审查。针对多义词串流、占位释义、英法同形词干扰等残余缺陷实施了清洗与补全，全部修改项均经 Jev 采纳裁决（Round 3 残余 283 项语义缺陷已全数闭环处理）。
- 例句与音频端到端契约：运行 `python tools/check_sentence_contract.py`，全量 215,813 条例句与对应的 Edge TTS 原生音频切片（严格基于例句原文 MD5 哈希定址）匹配率达到 100% PASS。
- 运行时部署一致性校验：运行 `python tools/sync_packs.py --check-deployed`，9 语部署包运行时 SQLite 数据库、例句表与 manifest 逐字节比对 100% PASS。
- 安装器磁盘健康防护：引入 P1-9 磁盘健康核对钩子（`Test-WordbookDiskHealth`），当本地音频目录缺失或词表被破坏时，更新流程能自动感知并摘除损坏记录，触发全量修复重下。

## 系统设计边界与局限性

在享受多语言与扩展槽位便利的同时，以下为当前工程架构的既有物理边界与运行局限性：

1. 原生物理槽位数量约束：
   受游戏底层内部数据结构限制，游戏存档（`MyBook.es3`）硬编码仅有 4 个物理 `SelfBookListN` 字段。
   本 mod 提供的 20 槽是 `CustomSlotsMod` 在前端维护的独立逻辑槽位（`WcpCustomSlots.json`），同一时刻最多只能将激活的词书物化入空闲的原生槽位，无法突破底层游戏引擎的并发物理槽位上限。

2. 实机热切换与游戏引擎缓存：
   虽然所有路由隔离、词池重构与 113 项离线单元测试均已全量通过，但游戏内部的单例状态机（`MyParameters` / `ChooseWordManager`）在跨场景时存在静态缓存。
   为杜绝极端战斗场景下底层引擎未能即时释放上一本词书的音频句柄或纹理，建议在游戏主菜单界面进行词书选择，或在完成跨语言大幅切换后重新启动游戏。

3. 语言处理策略分层：
   法语、俄语、德语、西班牙语、葡萄牙语、韩语、阿拉伯语等 7 种语言均已实现完全解耦的纯数据包，复用宿主内置的 `GenericLanguageStrategy`；
   日语因假名与振假名读音回查需加载独立策略程序集（`WcpPack.Ja.dll`），粤语包含注音解析程序集（`WcpPack.Yue.dll`）。新追加语言若无特殊拼写行为，仅需提供数据资源即可。

4. 特殊音标保守留空原则：
   音标数据严格坚持不主观推断与不臆造原则。针对第三方词典数据集中未能收录或格式不兼容的 10 处特殊注音数值，系统按规保持为空，不伪造拼音或注音，不影响正常背词与中文释义展示。

5. 外部词书服务边界：
   本 mod 仅对本 mod 托管范围内的词书提供定制释义数据库与专属音频路由服务。用户原有的外部自定义词书镜像进入 20 槽后标记为外部所有（`owner: external, managed: false`），宿主对其执行严格的 fail-closed 保守放行，不篡改其词表与数据，外部词书不享有本 mod 的多语言例句与私有音频增强。

6. mod 物理健康核对的覆盖范围：
   `Test-ModDiskHealth` 只把与语言无关的核心三件套（`WcpHost.dll` / `CustomSlotsMod.dll` / `BookNameMod.dll`）当作健康判据，因此新语言接入不需要改动安装器代码；
   与之相对，某个语言的旧版词表插件被改名或删除不会被单独判为不健康，只会在安装时按载荷 SHA-256 差异重新物化。这样既保持了扩展性，也避免把语言清单硬编码进安装器。

7. 安装器自更新链的对外依赖：
   安装器升级依赖 GitHub 的 raw 与 API 通道，二者都可能被网络环境限流或阻断（2026-09-21 本机实测未认证 `api.github.com` 请求已返回 403）。任一条通道不可用时，检查只打印一行提示后安静跳过，不中断本次安装，代价是该次运行不会提示升级。
   另外 v0.1.3 及更早版本的索引下载缺少 `Accept: application/octet-stream`，拿到的是资产元数据 JSON，自更新提示从未触发过；这些版本的用户需要手动重新下载一次 v0.1.4 或更新的安装包，之后才走自更新链。

## 开发与验证

```powershell
# 宿主：身份层注册表测试（读取 packs/*/manifest.json 与存档槽位）
cmd /c mod_host\tests\run_registry_test.cmd

# 宿主：接管范围测试（战斗词池 / 还原语义）
powershell -File mod_host\tests\run_takeover_test.ps1

# 宿主：槽位所有权与服务边界测试
cmd /c mod_host\tests\run_slot_ownership_test.cmd

# 宿主：单词音频兼容层测试
cmd /c mod_host\tests\run_word_audio_compat_test.cmd

# 槽位：20 槽行为规则测试
powershell -File mod_custom_slots\tests\run_slot_rules_test.ps1

# 安装器：离线单元测试（无网络、不写游戏目录，113 项全覆盖）
powershell -File tests\test_hub.ps1

# 安装器：自更新链回归（本地假 GitHub 回放 HTTP，不碰真实网络）
powershell -File tests\test_selfupdate.ps1

# 安装器：双击入口窗口保留回归（桩包 + 反向对照，不碰游戏目录）
powershell -File tests\test_launcher.ps1

# 词书：例句音频与端到端 MD5 契约校验
python tools\check_sentence_contract.py

# 部署：本地 packs 与部署端运行时逐字节核对
python tools\sync_packs.py --check-deployed

# 集成一致性：languages/<code>/ 与原语言仓库工作区逐文件 sha256 比对
python tools\verify_integration.py
```

构建：`mod_host\build.cmd`、`mod_custom_slots\build.cmd`、`mod_book_name\build.cmd`、日语策略 `mod_host\strategies\build_ja.cmd`。

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

一键安装器最新版本为 `wcp-installer-v0.1.5`，支持自动通过 GitHub 发现资源、选择性安装、峰值空间预检、差异化更新、词书磁盘健康核对与 mod 物理健康自愈。版本索引 `release-index.json` 同时放在仓库根目录（raw 可直读）与 `wcp-mods-*` release 资产上：仓库根副本不消耗 GitHub API 配额，release 资产副本供 API 通道与自更新解耦发布使用。启动器检测到新版本时提示用户确认升级；v0.1.3 及更早版本的自更新链因缺少 `Accept: application/octet-stream` 而从未真正生效，这些用户需要手动下载一次 v0.1.4 或更新的安装包。

每条 asset 都带 `url` / `size` / `sha256`（或 GitHub 的 sha256 digest），安装器直接按 `url` 下载并逐项校验。`disk.extract_mb` 是按 zip 内实际文件大小算出的解压占用，用于峰值磁盘检查。

语音包的打包与发布流程见 [INSTALLER.md](INSTALLER.md#资源包发布流程)；流水线脚本已随本仓库版本化在 `tools/release/`，构建产物留在本地 `_local/release/` 不入库。

## 演进与迁移记录

1. 2026-09-15 上午（初始快照）：`hanserdesu/japanese` 提供宿主、槽位、书名层与迁移工具；`hanserdesu/WCP-Wordbook-Hub` 提供初版安装器。
2. 2026-09-15 资源包发布：8 种语言（ar / de / es / fr / ko / pt / ru / yue）语音资源包在本仓库发布，`catalog.json` 中 9 本词书全部转为 `available`。
3. 2026-09-15 日语稳定版收敛：`hanserdesu/japanese` 的 `master` 收敛回滚至稳定版 `wcp-jp-v1.2.2`。
4. 2026-09-15 全量集成与单源收敛：9 个语言工程的工作区全量集成进 `languages/<code>/`，至此各语言不再分散提交。
5. 2026-09-16 载荷升级与发音兼容（v1.2.0 / v1.3.0）：实现统一发音兼容层 `WordAudioCompat`，新增收敛版 Legacy 回退开关，音频目录私有化以隔离 Steam 云同步。
6. 2026-09-17 安装器与存档安全加固（v0.1.1）：集成 ES3 存档受损检测与合格备份自动恢复机制，下载临时目录与历史备份移出 Steam 同步范围。
7. 2026-09-20 词书全量双轴审计与部署对齐：使用 TypeSafe Jev 完成 9 语词表语义与发音全面清洗审计，例句与音频端到端 100% 契约达成；P1-9 磁盘健康自动核对钩子上线。
8. 2026-09-21 统一安装器 v0.1.2 发布与 Hub 分发对齐：独立分发仓库 `WCP-Wordbook-Hub` 与主仓库完全对齐（89/89 测试通过），正式发布 `wcp-installer-v0.1.2`。
9. 2026-09-21 仓库架构终极收敛至双仓模型：经 Jev 决策审计（p=0.97），将分发镜像 Hub 与内部探针 Probes 彻底收拢并入本大仓（本地保留完整镜像归档），GitHub 远端仅保留 `hanserdesu/japanese`（日语老牌独立仓）与 `hanserdesu/WCP-MultiLanguage`（多语言统一大仓），终结双重维护与分散碎片。
10. 2026-09-21 mod 物理健康自愈（v0.1.3）：实机定位到「`WcpHost.dll` 被改名为 `WcpHost.dll.disabled` → 旧语言插件检测到 pack 存在主动让渡 → 词典 Hook 链真空 → 查词面板对所有受管语言回退成游戏原生兜底提示」的故障链，据此上线 `Test-ModDiskHealth`：安装前核验核心三件套在位与非 0 字节、自动改名回正被禁用的插件副本、核心插件缺失时强制重新物化 mods 载荷。离线测试由 89 项扩至 99 项并全部通过，正式发布 `wcp-installer-v0.1.3`。
11. 2026-09-21 自更新链修复（v0.1.4）：实测发现索引下载走 GitHub API 资产地址却未声明 `Accept: application/octet-stream`，拿到的是资产元数据 JSON（1506 字节）而非索引本体（501 字节），`installer_version` 解析不出，自更新检查一直静默判定为「已是最新」；同时本机对 `api.github.com` 的未认证请求已返回 403，整条链不可达。修复为三条通道依次取用（仓库根 raw 索引 → release 资产接口带 Accept 头 → 资产下载地址），并新增本地假 GitHub 驱动的自更新回归测试（含复现修复前行为的反向对照）。离线测试由 99 项扩至 103 项，正式发布 `wcp-installer-v0.1.4`。
12. 2026-09-21 双击入口窗口保留修复（v0.1.5）：玩家反馈双击入口跑完自动退出、来不及看状态。定位到 `tools/release/build_installer.py` 打包时另写了一份两行 `一键安装词书.cmd`，覆盖了仓库根那份带 `--keep-open` 自重启的入口，那份既没有保持窗口的机制，包里也漏了 `更新词书资源.cmd`。改为打包直接收录仓库根两个入口（单一事实源），两个入口统一经 `run-installer.ps1` 启动（版本注入 + 错误链），`更新词书资源.cmd` 通过 `-Update` 转发；启动器只在 `WCP_KEEP_OPEN=1` 时才承诺窗口保留。新增桩包行为回归（含复现修复前闪退的反向对照）。离线测试由 103 项扩至 113 项，正式发布 `wcp-installer-v0.1.5`。

## 许可

本仓库采用分层许可：代码、内容与词典数据各自适用不同条款，范围说明与上游署名见 [ATTRIBUTION.md](ATTRIBUTION.md)。

- 代码（宿主、槽位、插件、安装器、工具）：[PolyForm Noncommercial License 1.0.0](LICENSE)。个人学习、研究与其它非商业用途可以自由使用、修改和再分发；商业用途请联系作者另行授权。
- 内容（选词分级、中文释义、例句、语音）：CC BY-NC-SA 4.0。使用时需署名，不得用于商业目的，改编作品以相同方式共享。
- 词典数据（音标、重音、汉字读音等由第三方数据集派生的逐项数值，来源见 ATTRIBUTION.md）：CC BY-SA 4.0。需保留上游署名，衍生数据以相同方式共享。
