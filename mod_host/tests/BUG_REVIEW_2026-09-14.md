# 2026-09-14 bug 复查

## 本轮语言切换修复（追加）

日志确认日语启动时，旧版法语插件会在非自身词书状态下把共享
`wcpFullEng.db` / `wcpOnlyWord.db` 写回英语态；德语插件同时存在
`DEOM` SQL 拼写错误，并可能与法语插件争抢同一组共享库。两者会造成
语言标签、词义/例句和共享数据库状态短暂不一致。

- `D:\ATooManyLanguage\French\mod_fr_wordlist\FrWordListMod.cs`：德语词书激活时法语侧只读，避免覆盖德语共享库；其它非德语受管词书仍恢复英语基线。
- `D:\ATooManyLanguage\German\mod_de_wordlist\DeWordListMod.cs`：只有德语词书激活时才拥有共享库，避免覆盖法语、日语和俄语状态。
- `D:\ATooManyLanguage\German\tools\build_all_mods_de.py`：固定生成器，防止后续重新生成时恢复 `DEOM` 或旧的共享库守卫。
- 已重新构建并部署法语、德语插件，以及 `D:\ATooManyLanguage\Japanese\mod_host\WcpHost.dll`；旧 DLL 均已在插件目录保留 `.before_fix_20260914_*.bak` 备份。

本轮检查统一宿主的队列接管/恢复、身份与资源路由、既有日语测试脚本、数据库自愈载荷和安装脚本语法，并结合新日志复核了日语启动及后续语言切换。未完成完整安装矩阵或全部方向的界面切换，不能据此断言项目不存在其他 bug。

## 已修复

生产源码 `../TakeoverScope.cs`：

- 首次接管先成功保存基线，再成功保存所有权标记；任一步失败时不修改游戏队列。旧实现先写标记，且忽略保存失败。
- 恢复合并本次会话与磁盘所有权，优先使用内存基线。旧实现完全依赖磁盘，记录丢失会导致漏恢复或清空原队列。
- 恢复只接受预定义的队列字段；缺失备份时不生成空队列，保留待恢复标记。恢复保存失败也保留标记供后续重试。
- 重启后进入同一 profile 时先恢复旧基线，防止把上次过滤后的队列当作原始基线。
- 仅恢复测试词池时检查测试完成标记；恢复其他数组不修改测试状态。

## 验证

`TakeoverScopeTest.cs` 直接编译生产 `TakeoverScope.cs`，仅替换游戏字段和 ES3 存储边界；不复制接管算法，不读写用户存档。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File mod_host/tests/run_takeover_test.ps1
$env:WCP_NO_DEPLOY = '1'
& .\mod_host\build.cmd
& .\mod_host\tests\run_registry_test.cmd
```

- 修改前首批 8 项断言中 6 项失败；修改后扩展为 14 项，全部通过。
- 最终宿主构建和 RegistryTest 通过；四语言身份、资源边界和日语策略实际加载通过。构建保留一个既有 Unity API 弃用警告。
- `portable_scope_test.py`、`quicktest_logic_test.py`、`s9_stale_pool_test.py`、`kana_render_test.py`、`order_setting_test.py`、`word_audio_test.py` 全部报告通过。这些既有脚本含模拟/静态验证，不等同于 Unity 运行时测试。
- `db_payload_roundtrip_test.py` 在临时数据库副本恢复成功：FullEng pron 7,922 条、sentence2 30,894 条、OnlyWord pron 7,922 条，三个探针各一条。
- 安装目录下 5 个 PowerShell 脚本 AST 解析通过；修改路径 `git diff --check` 通过。
- 法语完整校验、每日队列校验、运行时范围校验全部通过；法语词库 8,116 条，其中与英语完全同形 1,638 条（20.18%），法语独有 6,478 条。
- 德语完整校验通过；`DEOM` 全仓扫描无结果。法语、德语和宿主重新构建通过。
- `arch_check.py` 当前为 0 FAIL / 1 WARN：宿主 DLL 已部署且哈希一致；唯一警告是宿主资源包目录没有部署德语 manifest，该资源目前不由宿主策略接管。
- 新 `Player.log` 已加载 `WCP Host 0.2.0`；日语启动为 7,922 词，随后法语激活为 8,116 词并成功切换“共享库 -> 法语”，俄语切换后成功恢复英语态；未再出现 `near "pron"`、SQLite 异常或法语在日语启动后的抢写记录。

## 尚未验证与现存限制

- `arch_check.py` 的唯一剩余警告是德语 manifest 未部署；本地宿主 DLL 与部署版本已一致。德语宿主策略未接管，因此该 manifest 不影响当前语言插件切换，但仍是后续发布完整度事项。
- RegistryTest 只加载了日语策略，其他三种语言没有可用策略；身份/路由通过不代表这些语言已完成宿主功能迁移。
- 旧 `kana_logic_test.py` 虽返回 0，但读到 8,451 个俄语词、汉字词覆盖为 0；该脚本结果不计入日语功能通过证据。
- 已验证日语启动以及日志中的日语 → 法语/俄语路径；尚未由自动化工具完成一次法语 → 日语的鼠标界面复现，也未完成插件停用和退出再启动矩阵。原生游戏窗口当前不在可用的 UI 自动化 surface 中，因此这部分应由下一次人工切换确认。
- `DrunkDemo.OnDestroy`、缺少字体字符、`SaveButton` 脚本缺失等仍出现在游戏原始日志中，和本次语言插件 SQL/共享库问题无直接关联。


## 2026-09-14 晚间追加：跨语言队列窜写根因修复（RU -> JP）

`Player.log` 显示俄语 -> 日语切换时：JP 插件先重建日语队列，RU 插件的
`PostBookChange` 随后执行 `RestoreSharedFields`，把旧基线写回共享队列并触发
`FightList`；游戏按全局已学词典补池，战斗词表混入俄语词。五个词表插件
(JP/FR/RU/DE/YUE) 均存在同一竞争窗口，且接管基线可能把上一本受管词书的
残留内容记为自己的基线（污染复活路径）。

- 五插件统一加入 OtherManagedBookActive / OtherRestoreDeferred / DeferredRestoreCheck：对方受管词书指纹活跃时暂缓一切还原写入，场景补丁 + 每秒轮询 + CrossBookGuard 三条路在窗口关闭后重试。
- 基线记录/还原加入 BaselineFromOtherManagedBook（指纹前缀归属判定）：属于其它受管词书的基线一律按空处理，不再复活上一本书的内容。
- FR 为模板源（RU/DE/YUE 由生成器适配），JP 为独立实现，语义一致。
- Contonese 生成器写 BookProfiles.Cantonese 而常量名是 Yue，在两份 BookProfiles 副本补等价别名常量使构建通过。
- packs/yue 与实装德语书同占 observed_slot 4 导致注册表唯一性冲突：yue 包自 JP 仓库移除（Contonese 项目持有正本），注册表恢复 4 包全 PASS。

验证：五插件全部 BUILD OK 并部署；JP takeover 15 断言、RegistryTest 全部通过；JP 四个离线回归 ALL PASS；FR verify_all_fr ALL PASS；DE verify_all_de ALL PASS（共享库当前德语态，符合 book-scoped 设计，RU/FR 校验中的共享库断言因此预期不适用）；RU verify_all_ru 其余项通过。运行时五语言切换矩阵仍需实机确认。
