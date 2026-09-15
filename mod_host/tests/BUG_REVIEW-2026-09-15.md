# 2026-09-15 复查：法语战斗像英语 / 俄语切日语后仍现俄语

范围：只做只读复现与根因定位，结论全部来自本机当前证据（游戏目录、玩家日志、
三份游戏数据库、各语言插件源码）。未做任何实机切换，未修改游戏目录。

证据来源：

- 玩家日志 `%USERPROFILE%\AppData\LocalLow\WCP\wcp\Player.log`（7,374 行，2026-09-14 15:16 退出）
- 游戏库 `E:\Steam\steamapps\common\WCP-WordGirlgriend\wcp_Data\StreamingAssets\{wcpFullEng,wcpOnlyWord,wcpFight}.db`
- 反编译源码 `Japanese\work\decompiled\`
- 插件源码 `{French,German,Russian,Contonese,Japanese}\mod_*_wordlist\*.cs`
- 复现脚本 `probes/db_probe.py`、`probes/db_meaning_probe.py`、`probes/fr_book_probe.py`

---

## 结论速览

| 现象 | 判定 | 根因 |
|---|---|---|
| 法语战斗里"都是英语" | **是 bug**（不是"法语英语相似"这么简单） | 战斗/测试词池的**补池来源是全局已学词典** `HaveLearnedDictionary`，它**不按词书隔离**；法语书与英语原库有 1,638/8,116（20.2%）拼写完全同形，于是"玩家学过的英语词"里同形的那批全部通过法语过滤留下，视觉上就是"满屏英语" |
| 俄语切日语后仍出现俄语 | **是 bug** | 5 个词表插件同时安装、同时给同一批全局游戏方法打补丁；每次切书每个插件都会"还原 + 唤醒 `FightList`"重算同一个全局词表，晚到的插件会把上一门语言的词重新灌回来。隔离是"插件互相盯防"，不是物理隔离 |

两者同源：**运行态隔离被实现成"N 个插件互相守卫的共享全局状态"，而不是每语言各自的资源命名空间。**

---

## 1. 法语战斗"都是英语"

### 1.1 战斗词表确实是法语书，不是英语书

日志（法语书激活时）：

```
2702 FRWordList: 词书状态=1 内存书名=自定义词书二 内存词表=8116词
                (内存 Profile=catbar-french-cefr-complete 槽位 Profile=catbar-french-cefr-complete)
2703 FRWordList: S7TestWordList_Para -> 120 词 (示例: collision, confusion, hamburger, exact) @fr
```

身份门通过、profile 命中法语包、队列打了 `@fr`。战斗里那 10 条 `【查单词】` 记录
（`constitution / bizarre / valve / indication / disposition / massacre / alliance / divorce /
acquisition / statue`，日志 3982-3991 行）也全部是法语词条。

### 1.2 那些"英语词"确实都在法语词书里

`probes/fr_book_probe.py` 读三张法语导入表（A1A2 2,680 + B1 2,902 + B2 2,534 = 8,116）：

```
IN collision / confusion / hamburger / exact / champion / divorce / capital / crash / miss /
   profit / module / situation / phrase / people / bus / set / dealer / gay / fan /
   dingue / sérum / aura / massacre / conversation / association / permission / imitation / science
```

法语项目自己的同形词表 `French\work\english_overlap_words.json` 记 1,638 条，
起始就是 `abandon, abdomen, abdominal, abject, abominable, about, absence, absent, absorber, abuser…`。
所以法语书里"看起来像英语"的词是真实的法语（借词/同形词），A1A2 段尤其密集。

### 1.3 真正的问题：补池来源不按词书隔离

战斗词表由 `ChooseWordManager.FightList()` 生成，再由
`ChooseWordManager.AddWordsToSelfChosenList(ref S7TestWordList_Para, n)` 补满；
补池数据源写死在反编译源码里（`ChooseWordManager.cs` 1586-1605 行）：

```csharp
List<KeyValuePair<string, WordInfo>> list = (from entry in MyParameters.HaveLearnedDictionary ...
```

`MyParameters.HaveLearnedDictionary` 是**全局单例、与词书无关**。日志实测：

```
576/620/742/849    在日语书下  HaveLearnedDictionary.Count ---> 830
2548/2667/2697     切法语过程中 ---> 830
2865/2984          法语书下     ---> 832
4948/4979/5117     俄语书下     ---> 832
6810/6845/6991     切回日语后   ---> 832
```

同一份 830-832 词的"已学词典"横跨日语→法语→俄语→日语全程不变。
于是法语战斗的补池 = 「全局已学词 ∩ 法语书」，而全局已学词正是玩家在**英语/其它书**里学的；
同形的那批（20.2%）全部存活，非同形的被法语过滤丢掉 —— 结果就是补池严重偏向同形词，
看起来"都是英语"。

补充缺陷（游戏硬编码，需宿主兜底）：词池不足 5 条时游戏会塞入英语占位词
`one/two/three/four/five`（`ChooseWordManager.cs` 1623-1642 行）。

**为什么"每次抽 4 个示例全是同形词"几乎不可能是巧合**：若均匀取自全书，
4 个示例全同形的概率约 `0.202^4 ≈ 0.17%`；日志里连续三次（2703/2718/2726）全同形，
说明补池**确实被全局已学词偏置**了，而不只是"法语和英语像"。

---

## 2. 俄语切日语后仍出现俄语

### 2.1 五个插件同时在场，各自重算同一个全局词表

启动日志（第 33-39 行）显示五套插件全部装上：

```
DEWordList / FRWordList / JPWordList / RUWordList / YueWordList  Harmony patches OK
```

俄语 → 日语那一次切换（6780-6870 行区间）里，同一次切换触发了**三个插件**去重算战斗词表：

```
6850 DEWordList: 换出受管词书, 唤醒游戏重新生成当前战斗词表
6852 FRWordList: 换出受管词书, 唤醒游戏重新生成当前战斗词表
6857 RUWordList: 换出受管词书, 唤醒游戏重新生成当前战斗词表
6853 RUWordList: 已还原共享队列 (残留队列被清空并结束未完成测试) -> 其它词书恢复原样
```

`WordListManagerS7` / `ChooseWordManager` 操作的是**同一份** `MyParameters.S7TestWordList_Para`、
`allTestWordsS10_Para`、`HaveLearnedDictionary`。谁最后写谁生效，于是晚到的还原/唤醒
会把上一门语言的词重新灌回全局词池。2026-09-14 那轮加的
`OtherManagedBookActive / OtherRestoreDeferred` 只是把竞争窗口缩小，没有消除竞争。

### 2.2 同一根因的第二处证据：生成器把法语字面量留在了别的语言里

`RuWordListMod.cs` 打印自己"激活"时用的是法语标签：

```csharp
// Russian\mod_ru_wordlist\RuWordListMod.cs:2080
Log.LogInfo("RUWordList: " + key + " -> " + count + " 词 (示例: " + sample + ") @" +
    (RussianBookSelected() ? "fr" : "other"));
```

日志实测（俄语书激活）：`RUWordList: allTestWordsS10_Para -> 20 词 (示例: с, они, это, мы) @fr`。

同样的法语残留还有：

```
German\mod_de_wordlist\DeWordListMod.cs:2074     (FrenchBookSelected() ? "fr" : "other")
Contonese\mod_yue_wordlist\YueWordListMod.cs:2074 (FrenchBookSelected() ? "fr" : "other")
Contonese\mod_yue_wordlist\YueWordListMod.cs:1282 PlayFrenchWord(...)
Contonese\mod_yue_wordlist\YueWordListMod.cs:2238 FrenchProbeOk(...)
```

这说明 RU/DE/YUE 是从法语模板批量派生的（`German\tools\build_all_mods_de.py`、
`Contonese\tools\build_all_mods_yue.py`；俄语目前是手抄维护），
**"加一种语言要改 N 处代码"的结构性代价**仍然存在，正是统一宿主方案要消掉的东西。

### 2.3 第三个叠加因素

日志 6868-6870 行显示统一宿主已经在日语书下接管并接线：

```
WcpHost: 接管语言包 ja / catbar-jlpt-complete
WcpHost: 语言策略已确认，行为 Harmony 接线已安装
WcpHost: 已激活 · ja / catbar-jlpt-complete（7922 词，槽 1，策略已载入）
```

也就是说此刻 `JPWordListMod` 和 `WcpHost(ja 策略)` **同时**在管同一份状态 —— 同一套状态两个所有者，
是新旧架构并行期的直接风险，必须尽快让旧插件退役。

---

## 3. 修复方向（按依赖排序）

1. **词池按书隔离（先做，改动小、可离线验证）**
   受管词书激活时，战斗/每日/自选词池一律只从【本书 ∩ 本书进度】构造，
   补池不再读全局 `HaveLearnedDictionary`；池不足 5 条时由宿主用本书词补，
   不再让游戏塞入 `one..five`。
2. **资源命名空间物理化（阶段 1）**
   单词/例句音频、释义/例句库全部落到 `packs/<lang>/`；
   A 语言代码路径里不出现 B 语言路径串（`ResourceRouter` 已具备，差部署与迁移）。
3. **单宿主接管（阶段 2）**
   补丁点合并进 `WcpHost`，语言差异只留在 `ILanguageStrategy`；旧 5 套插件退役，
   消除"多插件抢同一全局状态"。这一步做完，"俄语切日语残留"才有结构性解法。
4. **20 槽位 + 安装器**
   游戏原生只有 4 槽（`SelfBookList1..4`，且 `自定义词书一~四` 字面量散布在 15+ 个反编译文件里）。
   不能改游戏数据模型，只能由宿主持有 20 条逻辑槽位登记表，
   把"当前选中"的一条物化进任一原生槽（运行态本来就是串行的），
   并在同一个滚轮页面里做选择/管理。
5. **派生链收敛**
   消除 RU/DE/YUE 里的法语字面量与 `FrenchBookSelected` 之类标识符，
   让"新增语言"只 = `packs/<lang>/manifest.json` + 资源 + 一个策略类。

---

## 4. 本轮未验证

- 未做任何实机切换；结论均来自日志、数据库与源码，不含游戏内复现。
- 未验证"补池偏置"在其它语言（西班牙语等与英语同形率高的语言）上的同形比例。
- 20 槽位方案的可行性只做了源码侧确认（`SelfBookList1..4`、`_slotProfiles[4]`、
  `自定义词书一~四` 字面量统计），未做"导入第 5 本书"的实机验证。

---

## 5. 2026-09-15 续查：实机日志证据与两项遗留

实机日志（`BepInEx/LogOutput.log`，09:12 启动的进程加载 08:49 部署的 `WcpHost.dll`）已证实接管链路按设计工作：

- `WcpHost: 受管语言登记 = [ja,yue]`
- `YueWordList: WcpHost 已接管粤语, 旧词表插件不再打补丁`（跨语言串词的根因修复在实机生效）
- `WcpHost: 语言包资源未就绪, 本次不接管（旧插件继续兜底）: fr 缺 db/meaning.sqlite; ru 缺 db/meaning.sqlite`

**遗留 1（法语的根因修复尚未生效）**：宿主只接管 `packs/<language>` 资源齐备的语言，本机
`packs/fr`、`packs/ru` 只有 `manifest.json`，所以法语仍由旧插件兜底，战斗里仍可能出现英语。
各语言安装器的落盘布局也不一致：日语安装器写 `packs/ja`，粤语安装器写 `packs/yue`，而
`Install-WCP-French.ps1` / `Install-WCP-Russian.ps1` 完全不引用 `packs`（`rg -n packs` 无命中），
因此产不出 `packs/<lang>/db/*`。修好法语需要：按同一 pack 布局落盘 fr（以及 ru/de）的
`db/meaning.sqlite`、`db/sentences.json`、`db/repair.tsv` 与 `books/*`——日语 payload 直接内置
预构建 db 文件，可作模板——再让各语言安装器写这个布局并重新登记受管语言。

**遗留 2（编码类静默失效）**：无 BOM 的 UTF-8 `.ps1` 在 Windows PowerShell 5.1 下按 ANSI 解码。
`mod_custom_slots/tests/test_custom_slots.ps1` 的中文注释因此吞掉了下一行调用，测试套件把
“子进程根本没启动”当成结果。实测证据（5.1 下 `Parser::ParseFile`）：无 BOM 时 `errors=1`、
中文串变成 `7039 590E E5CA` 之类乱码代码点；加 BOM 后 `errors=0`、首串代码点
`5B89 88C5 6CA1 6709`（即“安装没有”）。已修复：该测试与日/粤 `run-installer.ps1`。
防回归：`hub/tests/test_hub.ps1` 断言 hub 脚本“非 ASCII 必须带 BOM”、两个双击 `.cmd` 必须纯 ASCII；
批处理还必须 CRLF（apply_patch 会写成 LF，cmd 会误读并报 `'Shell' 不是内部或外部命令`）。
