// WCP Host — 统一接入宿主（阶段 2，v0.3.0）
//
// 职责边界（这是整个重构的核心约定）:
//   宿主负责机制: 读语言包清单 / 认身份 / 作用域门 / 资源路由 / 日后接管-还原。
//   语言包负责数据: packs/<lang>/{manifest.json, books, db, audio}。
//   语言策略负责行为: ILanguageStrategy（每语言一个 ~150 行的类）。
//
// 当前版本在身份门通过后接管固定的游戏补丁点；语言差异只来自
// ILanguageStrategy，队列和 UI 状态由宿主统一还原。
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using BepInEx;
using BepInEx.Configuration;
using BepInEx.Logging;
using HarmonyLib;
using UnityEngine;

namespace WcpHost
{
    [BepInPlugin("dev.hanserdesu.wcphost", "WCP Host", "0.5.2")]
    public class WcpHostPlugin : BaseUnityPlugin
    {
        internal static ManualLogSource Log;
        private static WcpHostPlugin _instance;

        private ConfigEntry<bool> _enabled;
        private ConfigEntry<string> _packsRootOverride;
        private ConfigEntry<bool> _mirrorWordAudio;
        private ConfigEntry<bool> _requireSlotOwnership;
        private SlotOwnership _slotOwnership;

        private ResourceRouter _router;
        private BookRegistry _registry;
        private StrategyRegistry _strategies;
        private HostRuntime _runtime;
        private Harmony _featureHarmony;
        private bool _featuresInstalled;
        private float _nextProbe;
        private string _lastReported = "";
        // 词表内容守卫（第十二轮）：见 Host.cs 末尾 WordListMemo 的注释。
        private readonly WordListMemo _memMemo = new WordListMemo();
        private string _markerLangs = null;
        private const float ProbeInterval = 1.0f;

        // ---------------- 性能哨兵 ----------------
        // 目的: 把"游戏卡不卡"从主观感受变成 PLAYER.log 里可对账的数字。
        // 只累加 Time.unscaledDeltaTime (常数成本, 无分配), 每 PerfWindow 秒一行。
        // 口径: fps = 帧数 / 墙钟窗口; 最差帧 = 窗口内最大单帧耗时;
        // 卡顿帧 = 单帧 >= 50ms (即瞬时低于 20fps)。
        // 为什么要分开看: 平均 fps 正常但最差帧很大, 就是"顿挫"而不是"整体慢",
        // 两者的修法完全不同 —— 前者找固定周期的重活, 后者找稳态占用。
        //
        // 2026-09-18 第六轮补充：每一行后面再挂一段归因（mod 主线程占用 / 最慢
        // 单个操作 / 长帧次数），并在长帧（>=150ms）发生时单独打一行。口径见
        // PerfProbe.cs 顶部注释 —— 判读的关键是"mod 占用占整帧的百分比"。
        private const float PerfWindow = 10f;
        private const float HitchThreshold = 0.05f;
        private float _perfStart;
        private int _perfFrames;
        private int _perfHitches;
        private float _perfWorst;
        // 镜像线程的日志排队区（每帧 drain，见 DrainBackgroundLogs）。
        private readonly List<string> _bgLogs = new List<string>();

        private void FrameSentinel()
        {
            float now = Time.unscaledTime;
            float dt = Time.unscaledDeltaTime;
            if (_perfStart <= 0f)
            {
                _perfStart = now;
                _perfFrames = 0;
                _perfHitches = 0;
                _perfWorst = 0f;
                return;
            }
            _perfFrames++;
            if (dt > _perfWorst) _perfWorst = dt;
            if (dt >= HitchThreshold) _perfHitches++;
            // 长帧单独一行：写明这一帧里 mod 自己花了多少、最深走到哪个阶段。
            string longFrame = PerfProbe.Tick(dt * 1000f);
            if (longFrame != null) Log.LogInfo("WcpHost: " + longFrame);
            float span = now - _perfStart;
            if (span < PerfWindow) return;
            float fps = span > 0f ? _perfFrames / span : 0f;
            Log.LogInfo(string.Format(
                "WcpHost: 性能哨兵 fps={0:F1} 帧={1} 最差帧={2:F0}ms 卡顿帧(>={3:F0}ms)={4} 窗口={5:F1}s | {6}",
                fps, _perfFrames, _perfWorst * 1000f, HitchThreshold * 1000f,
                _perfHitches, span, PerfProbe.TakeWindowSummary()));
            _perfStart = now;
            _perfFrames = 0;
            _perfHitches = 0;
            _perfWorst = 0f;
        }

        // 后台镜像线程的日志统一在这里落到主线程日志（线程只入队，不直接写）。
        private void DrainBackgroundLogs()
        {
            if (MirrorWorker.DrainInto(_bgLogs) == 0) return;
            for (int i = 0; i < _bgLogs.Count; i++)
                Log.LogInfo("WcpHost: " + _bgLogs[i]);
            _bgLogs.Clear();
        }

        internal static WcpHostPlugin Instance { get { return _instance; } }
        internal ResourceRouter Router { get { return _router; } }
        internal BookRegistry Registry { get { return _registry; } }
        internal HostRuntime Runtime { get { return _runtime; } }
        // 补丁协调器从这里取得当前策略；身份层未激活时始终为 null。
        internal ILanguageStrategy ActiveStrategy
        {
            get
            {
                return _runtime == null ? null : _runtime.ActiveStrategy;
            }
        }

        // 兼容层开关：把 pack 单词音频补进游戏原生目录（配置缺失时视为开启）。
        internal bool MirrorWordAudio
        {
            get { return _mirrorWordAudio == null || _mirrorWordAudio.Value; }
        }

        private void Awake()
        {
            _instance = this;
            Log = Logger;

            _enabled = Config.Bind("General", "Enabled", true,
                "总开关。关闭时宿主只加载注册表、不做任何判定（补丁接入后=完全停用）。");
            _packsRootOverride = Config.Bind("General", "PacksRoot", "",
                "语言包根目录。留空 = <persistentDataPath 的父目录>/packs，" +
                "即 %USERPROFILE%\\AppData\\LocalLow\\WCP\\packs");
            _mirrorWordAudio = Config.Bind("Compatibility", "MirrorWordAudio", true,
                "把当前语言包的单词音频补进游戏原生目录（…\\LocalLow\\WCP\\vocabulary）。" +
                "游戏的播放器只认那个目录：宿主未接管（读档中/未激活）时，若该目录为空，" +
                "发音会静默回退成游戏的英语 AI 语音。只补缺、分批复制、可在装好后关闭。");
            _requireSlotOwnership = Config.Bind("Compatibility", "RequireSlotOwnership", true,
                "服务边界强约束：词书必须在 20 槽存档（WcpCustomSlots.json）里登记为" +
                "托管行或原生镜像行，宿主才提供服务。存档缺失（未装自定义槽位插件）时按" +
                "兼容回退放行；遇到问题可设为 false 回退到纯指纹语义。");

            try
            {
                string root = ResolvePacksRoot();
                _registry = BookRegistry.Load(root);
                _router = new ResourceRouter(_registry);
                _strategies = StrategyRegistry.Load(_registry);
                _runtime = new HostRuntime(this, _registry, _router, _strategies);
                // P1-4 服务边界：与 CustomSlotsMod 共用同一份数据目录约定
                // （persistentDataPath = <LocalLow>\WCP\wcp，store 在其下）。
                HostLog.InfoSink = m => Log.LogInfo(m);
                HostLog.WarnSink = m => Log.LogWarning(m);
                _slotOwnership = new SlotOwnership(
                    Path.Combine(Application.persistentDataPath, "WcpCustomSlots.json"));
                ReportRegistry(root);
                _featureHarmony = new Harmony("dev.hanserdesu.wcphost.features");
                // 第十三轮（2026-09-18）：接线从"首次接管帧"搬到 Awake。
                //
                // 依据是第十二轮实机普查：Awake 期 59/59 个目标类型/方法全部可解析
                // （解析失败 0，日志 L81）。此前不搬的唯一原因就是"没证据"——
                // 现在有了。收益：首次接管帧不再付 ~2000ms（补丁:Sync 占那帧 mod
                // 成本的 55%），改成在游戏加载期一次性付掉。
                //
                // 安全依据（本轮逐点核过 HostPatches 全部处理器）：
                //   · 59 个点的处理器全部经 WcpHostPlugin.Instance → Runtime；
                //   · Runtime 每个 Post*/Prefix* 第一行都是 `if (!IsActive …) return`，
                //     IsActive = 身份门通过（受管词书 + 策略在场）；
                //   · 无策略的 identity-only 语言包原来根本不接线，现在接了也不
                //     会动作 —— 处理器同样 gate 在 `ActiveStrategy == null` 上。
                // 所以"未接管时补丁在场"与"未接管时补丁不在场"的行为差异为零，
                // 只有 trampoline 的纳秒级开销。SyncFeaturePatches 的
                // 失活即移除分支随之删除 —— 它正是"切书瞬态失活 → 下一帧重装
                // 再付 2 秒"的抖动来源。
                if (_enabled.Value)
                {
                    HostPatches.InstallFeatures(_featureHarmony);
                    _featuresInstalled = true;
                    Log.LogInfo("WcpHost: 行为 Harmony 接线已在加载期安装" +
                                "（身份门通过前所有处理器空转）");
                }
                Log.LogInfo("WcpHost: 身份轮询已启用（兼容旧选书补丁）");
            }
            catch (Exception e)
            {
                Log.LogError("WcpHost: 加载语言包失败，宿主进入禁用状态: " + e);
                _enabled.Value = false;
            }
        }

        private string ResolvePacksRoot()
        {
            string custom = _packsRootOverride.Value;
            if (!string.IsNullOrEmpty(custom)) return custom;
            string pdp = Application.persistentDataPath;      // ...\AppData\LocalLow\WCP\wcp
            string parent = Path.GetDirectoryName(pdp);       // ...\AppData\LocalLow\WCP
            return Path.Combine(parent, "packs");
        }

        // 语言资源隔离的运行时凭证: 只登记"宿主确实成功接管"的语言。
        //
        // 旧词表插件 (JpWordListMod / FrWordListMod …) 读到自己的语言在列时整场不打补丁,
        // 运行时补丁因此只剩宿主一个所有者 —— 这是"俄语切日语后还出俄语"的根因修复:
        // 两个插件争抢同一批补丁时"后写者胜", 上一本书的词会串进新书。
        // 注册表为空/宿主停用时删除登记, 旧插件继续按旧模式工作。
        private void RefreshManagedMarker()
        {
            try
            {
                List<string> langs = new List<string>();
                List<string> notReady = new List<string>();
                if (_enabled.Value && _registry != null)
                {
                    for (int i = 0; i < _registry.Manifests.Count; i++)
                    {
                        LanguageManifest m = _registry.Manifests[i];
                        string code = m.Profile.Language;
                        string missing;
                        // 资源没装全的包不登记: 旧词表插件继续按旧模式兜底, 不会出现
                        // "宿主说接管了、实际没有释义库"的空档。
                        if (!m.ResourcesReady(out missing))
                        {
                            notReady.Add(code + " 缺 " + missing);
                            continue;
                        }
                        if (!string.IsNullOrEmpty(code) && !langs.Contains(code)) langs.Add(code);
                    }
                }
                string joined = string.Join(",", langs.ToArray()) + "|" +
                                string.Join(",", notReady.ToArray());
                if (joined == _markerLangs) return;
                string dir = Paths.ConfigPath;
                if (string.IsNullOrEmpty(dir)) return;
                string file = Path.Combine(dir, "WcpHost.managed.txt");
                if (langs.Count == 0)
                {
                    if (File.Exists(file)) File.Delete(file);
                }
                else
                {
                    File.WriteAllLines(file, langs.ToArray());
                }
                _markerLangs = joined;
                Log.LogInfo("WcpHost: 受管语言登记 = [" + string.Join(",", langs.ToArray()) +
                            "] -> " + file);
                if (notReady.Count > 0)
                    Log.LogWarning("WcpHost: 语言包资源未就绪, 本次不接管（旧插件继续兜底）: " +
                                   string.Join("; ", notReady.ToArray()));
            }
            catch (Exception e)
            {
                Log.LogWarning("WcpHost: 受管语言登记失败（旧词表插件继续按旧模式打补丁）: " + e.Message);
            }
        }

        private void ReportRegistry(string root)
        {
            Log.LogInfo("WcpHost: packs 根 = " + root);
            Log.LogInfo("WcpHost: 加载到 " + _registry.Manifests.Count + " 个语言包");
            for (int i = 0; i < _registry.Manifests.Count; i++)
            {
                LanguageManifest m = _registry.Manifests[i];
                Log.LogInfo(string.Format(
                    "WcpHost:   [{0}] {1} {2} 词={3} 槽={4} 指纹={5}",
                    m.Profile.Language, m.Profile.Id, m.Profile.DisplayName,
                    m.Profile.WordCount, m.Profile.ObservedSlot,
                    m.Profile.Fingerprint.Substring(0, 16)));
            }
            string detail;
            bool ok = _registry.SlotBudgetOk(out detail);
            Log.LogInfo("WcpHost: 槽位预算 " + detail + (ok ? " — 通过" : " — 超限（游戏硬上限 4）"));
            Log.LogInfo("WcpHost: 策略装载 " + _strategies.LoadedCount + "/" +
                        _registry.Manifests.Count + "（缺失策略时仅保留身份层）");
            for (int i = 0; i < _registry.Errors.Count; i++)
                Log.LogWarning("WcpHost: 语言包加载告警: " + _registry.Errors[i]);
            for (int i = 0; i < _registry.Warnings.Count; i++)
                Log.LogWarning("WcpHost: 语言包提示: " + _registry.Warnings[i]);
            for (int i = 0; i < _strategies.Errors.Count; i++)
                Log.LogWarning("WcpHost: 策略加载告警: " + _strategies.Errors[i]);
        }

        private void Update()
        {
            // 哨兵必须在所有 return 之前: 它要能在 _enabled=false 时也采集,
            // 才能拿到"关掉宿主"的基线做对比。
            FrameSentinel();
            // 后台镜像线程的日志每帧落地（线程自己只入队）。也要放在所有 return 之前：
            // 宿主未激活时镜像仍可能刚跑完，日志不能丢。
            DrainBackgroundLogs();
            // 第十五轮（2026-09-18）：标签还原分帧的消化口。必须在每秒门控之前 ——
            // 队列里积压的旧标签还原要每帧推进（时间预算 8ms/帧），不能被 1s 门控卡住。
            if (_runtime != null) _runtime.DrainLabelRestores();
            // 第十六轮（2026-09-18）：ES3 写后置的消化口。上一帧批量作用域记的账
            // 在这里提交（每帧最多一批），整文件装载+落盘离开切书帧。
            // 必须在每秒门控与 Evaluate 之前：先把上一帧的账冲掉，再开本帧的新作用域。
            GameAdapter.DrainEs3Writes();
            // 性能收敛 2026-09-18：RefreshManagedMarker 内部对每个语言包调
            // ResourcesReady()，而那是 (meaning_db + sentence_table + repair + 每本书)
            // 的 File.Exists 序列 —— 9 个包合计 44 次文件系统查询，外加每帧 2 个 List、
            // 2 次 string.Join、2 次 ToArray 的纯分配。
            //
            // 它原本挂在 1 秒门控**之前**，等于每帧都跑（60fps ≈ 2600 次 File.Exists/秒），
            // 而结果只在"哪些语言包资源齐备"变化时才需要重算 —— 那是以秒为量级的低频事件。
            //
            // 移到门控之后：语义不变（登记文件依旧会被写/删，包括 _enabled=false 的删除分支），
            // 只是粒度从每帧降到每秒。这是纯粹的重复劳动消除，不改任何判据。
            if (Time.realtimeSinceStartup < _nextProbe) return;
            _nextProbe = Time.realtimeSinceStartup + ProbeInterval;
            using (PerfProbe.Begin("身份:托管登记")) RefreshManagedMarker();
            if (!_enabled.Value || _router == null)
            {
                try
                {
                    if (_runtime != null) _runtime.OnDisabled();
                }
                finally
                {
                    RemoveFeaturePatches();
                }
                return;
            }

            string state;
            try
            {
                // 第十一轮（2026-09-18）：整帧的 ES3 写合并进**一个**批量作用域。
                //
                // 为什么：第九轮把逐键整档写（45 次）换成批量之后，第九轮的实机日志
                // （20:02）里切书帧的账变成了「ES3:批量写(装载) x3 = 349.0ms +
                // ES3:批量写(提交) x3 = 206.9ms」—— **同一次切书仍然做了 3 次整档读
                // 和 3 次整档写**。原因是恢复（Leave→RestoreOwned）、播种（Enter）与
                // 校正（Enforce）各自开了一层 `Es3BatchScope()`，三者在**同一帧内顺序
                // 发生**但互相不嵌套，于是各自装载、各自提交。
                //
                // Es3BatchScope 本来就是「外层已开则内层返回 null」的不嵌套语义，
                // 所以只要在最外层套一层，内部那三层会自动共享同一个批次：
                // 一次整档读 + 一次整档写。IsDirty 才落盘的惰性语义不变 ——
                // 系统空闲、一个字段都不用改的那些帧，成本仍然是 0。
                //
                // 为什么不会写坏：整帧的 mod 工作全部跑在 Unity 主线程的一个 Update
                // （或一个 Harmony 回调）里，游戏自己的 ES3.Save 不可能插进这段区间；
                // 而批量内部对「自己刚写过的键」的读由 Es3WriteBatch 的 _written
                // 覆盖（GameAdapter.Es3Load 里那段 WasWritten/TryGet），所以恢复→
                // 播种→校正三步之间「读回自己写的值」依旧成立。
                using (GameAdapter.Es3BatchScope())
                {
                    using (PerfProbe.Begin("身份:Evaluate")) state = Evaluate();
                    using (PerfProbe.Begin("补丁:Sync")) SyncFeaturePatches();
                    // 第九轮（2026-09-18）删掉这里原本第二层 `运行态:Tick` 包裹：
                    // HostRuntime.Tick() 自己已经打了同名标签，两层同名的结果是 counts x2、
                    // 总量翻倍，读日志的人会把它当成"Tick 一帧跑了两次"（第九轮我就先这么
                    // 误读了一次）。标签必须唯一指向一处，否则聚合就是假的。
                    if (_runtime != null) _runtime.Tick();
                }
            }
            catch (Exception e)
            {
                // fail-closed: 判定出错一律取消激活，绝不猜测
                _router.SetActive(null);
                if (_runtime != null) _runtime.SetInactive();
                RemoveFeaturePatches();
                state = "ERR " + e.GetType().Name + ": " + e.Message;
            }
            if (state != _lastReported)
            {
                _lastReported = state;
                Log.LogInfo("WcpHost: " + state);
            }
        }

        // 场景边界的强制校正: 玩家切书后 1 秒内的场景切换（战斗/测试/学习）
        // 不能再读到上一门语言的队列，所以这里先按游戏当前状态重判身份，再执行隔离。
        internal void EnforceNowForScene()
        {
            if (_enabled == null || !_enabled.Value || _router == null) return;
            // 第十轮加探针（这是探针口径上的一处真实漏洞，不只是缺个标签）：
            // 这个方法由 52 个 Harmony 补丁点在**游戏方法内部**回调，每次都要跑一遍
            // 完整的 Evaluate() 加 EnforceNow()。而 PerfProbe 只把 depth==0 的 span
            // 计入「mod 本帧占用」，此前它没有任何外层标签 —— 于是这些被补丁触发的
            // 全部校正工作，既不进「mod 本帧占用」，也不进 Top-N，在日志里等于不存在。
            // 换句话说：哪怕宿主在游戏方法里干了 3 秒活，哨兵也只会报 mod 占用 0.0ms
            // （实机 line 155 / 398 / 518 / 632 / 685 等"长帧 … mod 本帧占用 0.0ms
            // 本帧 Top=无 mod 操作"就有这个嫌疑）。补上外层 span，口径才闭合。
            using (PerfProbe.Begin("场景:强制校正"))
            {
                // 第十一轮：与 Host.Update 同一处理 —— 一次场景校正里的
                // Evaluate()（可能触发恢复/播种）与 EnforceNow()（校正）共享
                // 一个批量作用域，整档读写各一次。
                using (GameAdapter.Es3BatchScope())
                {
                    try
                    {
                        Evaluate();
                    }
                    catch (Exception e)
                    {
                        Log.LogWarning("WcpHost: 场景身份重判失败: " + e.Message);
                    }
                    if (_runtime != null) _runtime.EnforceNow();
                }
            }
        }

        // 身份判定：内存词表 / 内存书名 / 落盘书名 / 选中槽位词表四者一致，且指纹命中注册表，才激活。
        // 任一环节读不到或对不上 → 返回"未激活"。这条门是从现有插件的 fail-closed 门搬来的。
        private string Evaluate()
        {
            // 第十轮（2026-09-18）把身份判定切成 8 个独立标签。此前 Evaluate 只有一个
            // 外层 span，而实机出现过「身份:Evaluate 单次 2712.2ms」这样的尖峰却无从
            // 归因 —— 外层标签只能说"这一整段慢"，说不出"慢在哪一步"。切段之后切书帧
            // 的账目是直接可读的。唯一副作用是本帧标签数变多，TopN 已同步放宽到 12。
            object rawList;
            string memName;
            IList<string> words;
            using (PerfProbe.Begin("身份:读内存词表"))
            {
                rawList = GameAdapter.StaticField(GameAdapter.ParametersType, "ChosenBook_List");
                memName = GameAdapter.StaticField(GameAdapter.ParametersType, "ChosenBook_Para") as string;
                words = GameAdapter.ToWordList(rawList);
            }
            string diskName;
            using (PerfProbe.Begin("身份:读落盘书名")) diskName = GameAdapter.DiskBookName();

            if (words == null || words.Count == 0)
            {
                if (_runtime != null) _runtime.SetInactive();
                else _router.SetActive(null);
                return "未激活 · 内存词表为空";
            }
            if (string.IsNullOrEmpty(memName))
            {
                if (_runtime != null) _runtime.SetInactive();
                else _router.SetActive(null);
                return "未激活 · 内存书名为空";
            }
            if (string.IsNullOrEmpty(diskName))
            {
                if (_runtime != null) _runtime.SetInactive();
                else _router.SetActive(null);
                return "未激活 · 落盘书名读不到（读档中？）";
            }
            if (diskName != memName)
            {
                if (_runtime != null) _runtime.SetInactive();
                else _router.SetActive(null);
                return "未激活 · 内存书名(" + memName + ") ≠ 落盘书名(" + diskName + ") — 正在切书";
            }

            int slot;
            using (PerfProbe.Begin("身份:槽号")) slot = GameAdapter.SlotOfBookName(memName);
            if (slot <= 0)
            {
                if (_runtime != null) _runtime.SetInactive();
                else _router.SetActive(null);
                return "未激活 · 书名不是受支持的自定义槽位: " + memName;
            }

            BookProfile p;
            using (PerfProbe.Begin("身份:匹配内存词表"))
            {
                // 第十二轮：词表内容没变的轮次直接复用上一轮的结论（见 WordListMemo）。
                // 命中与未命中都要出声 —— 一个"应该生效的快路径"如果从不命中，
                // 要么是判据不对，要么是代码没接上，这两件事都必须能从日志里看出来。
                if (_memMemo.TryHit(_registry, words, out p)) PerfProbe.Hit("内存词表指纹");
                else
                {
                    PerfProbe.Miss("内存词表指纹");
                    p = _registry.Match(words);
                    _memMemo.Store(_registry, words, p);
                }
            }
            if (p == null)
            {
                if (_runtime != null) _runtime.SetInactive();
                else _router.SetActive(null);
                return "未激活 · 词表 " + words.Count + " 条未命中任何语言包 — 非受管词书";
            }

            IList<string> slotWords;
            using (PerfProbe.Begin("身份:读槽位词表")) slotWords = GameAdapter.SlotWords(slot);
            BookProfile slotProfile;
            // 第十二轮：槽位词表的指纹按 (slot, mtime, size) 缓存在 SlotEntry 里，
            // 稳态不再每秒重算（实机 11.7ms/s）。判据与缓存键同源，所以是精确的 ——
            // 见 GameAdapter.SlotEntry.Profile 的注释。
            bool slotCached = false;
            using (PerfProbe.Begin("身份:匹配槽位词表"))
            {
                if (slotWords == null) slotProfile = null;
                else slotProfile = GameAdapter.SlotProfile(slot, _registry, out slotCached);
            }
            if (slotWords != null)
            {
                if (slotCached) PerfProbe.Hit("槽位词表指纹");
                else PerfProbe.Miss("槽位词表指纹");
            }
            if (slotProfile == null || slotProfile.Id != p.Id)
            {
                if (_runtime != null) _runtime.SetInactive();
                else _router.SetActive(null);
                return "未激活 · 内存词表与持久化槽位词表指纹不一致 — 正在读档/切书";
            }

            LanguageManifest manifest = _registry.ByProfileId(p.Id);
            if (manifest == null)
            {
                if (_runtime != null) _runtime.SetInactive();
                else _router.SetActive(null);
                return "未激活 · 注册表没有 profile: " + p.Id;
            }

            // P1-4 服务边界：指纹命中只证明"本书是本 mod 发布的资源"，
            // 是否仍被服务以 20 槽 store 的登记为准（托管行/原生镜像行）。
            if (_requireSlotOwnership != null && _requireSlotOwnership.Value && _slotOwnership != null)
            {
                string ownershipReason;
                bool served;
                using (PerfProbe.Begin("身份:槽位归属"))
                    served = _slotOwnership.IsServed(p.Fingerprint, out ownershipReason);
                if (!served)
                {
                    if (_runtime != null) _runtime.SetInactive();
                    else _router.SetActive(null);
                    return "未激活 · " + ownershipReason;
                }
            }

            using (PerfProbe.Begin("身份:装载"))
            {
                if (_runtime != null) _runtime.SetIdentity(manifest, words);
                else _router.SetActive(p.Id);
            }

            if (_router.ActiveProfileId != p.Id)
            {
                _router.SetActive(p.Id);
                return "已激活 · " + p.Language + " / " + p.Id +
                       "（" + words.Count + " 词，槽 " + p.ObservedSlot + "）";
            }
            return "已激活 · " + p.Language + " / " + p.Id +
                   "（" + words.Count + " 词，槽 " + slot +
                   (ActiveStrategy == null ? "，策略缺失" : "，策略已载入") + "）";
        }

        private void SyncFeaturePatches()
        {
            // 第十三轮：接线已在 Awake 装好且**整场不拆**（见 Awake 注释的安全依据）。
            // 这里只剩一道防御性补装 —— 正常路径 _featuresInstalled 恒为 true，是 no-op。
            // 失活即移除的分支已删除：它造成的"切书瞬态失活 → 下一帧重装再付 2 秒"
            // 是第十一轮实机日志里 `补丁:Sync x6` 的来源之一。
            bool shouldInstall = _runtime != null && _runtime.IsActive &&
                                 ActiveStrategy != null;
            if (shouldInstall && !_featuresInstalled)
            {
                HostPatches.InstallFeatures(_featureHarmony);
                _featuresInstalled = true;
                Log.LogInfo("WcpHost: 语言策略已确认，行为 Harmony 接线已安装");
            }
        }

        private void RemoveFeaturePatches()
        {
            if (!_featuresInstalled) return;
            try
            {
                if (_featureHarmony != null) _featureHarmony.UnpatchSelf();
            }
            finally
            {
                _featuresInstalled = false;
                if (Log != null) Log.LogInfo("WcpHost: 行为 Harmony 接线已移除");
            }
        }

        private void OnDestroy()
        {
            try
            {
                if (_runtime != null) _runtime.OnDisabled();
                RemoveFeaturePatches();
            }
            catch (Exception) { }
            // 第十六轮：退出前把还没落盘的写后置批次全部冲掉（丢失 = 玩家进度回退）。
            try { GameAdapter.DrainEs3WritesAll(); }
            catch (Exception) { }
            if (_instance == this) _instance = null;
        }
    }

    /// <summary>
    /// 词表内容守卫（第十二轮 2026-09-18）。
    ///
    /// 用途：让 `_registry.Match(words)` 在"词表根本没变"的轮次上不必重算。
    ///
    /// 为什么这是**精确**的、不是启发式：`string` 是不可变对象，所以
    ///     元素个数相同 且 每个元素引用逐位相同  ⟹  内容逐字节相同
    ///     ⟹  FingerprintOf 的结果必然相同  ⟹  上一轮 Match 得出的 profile 依然成立。
    /// 反向不成立也不影响正确性：任何"引用换了但其实内容相同"的情况只会让守卫
    /// 判为未命中、退回全量 Match（少省钱，但绝不会判错）。任何"内容真的变了"的
    /// 情况必然是某个位置上换了字符串实例，引用比对一定发现。
    ///
    /// 为什么需要它：Host.Evaluate 每秒跑一次，其中两次 Match 是它 97% 的成本
    /// （实机窗口 592：匹配内存词表 10 次 107.6ms + 匹配槽位词表 10 次 116.5ms
    /// ＝ 22.4ms/s，占 mod 稳态 44ms/s 的一半）。而词表真正变化的频率是"用户切书",
    /// 量级是分钟 —— 中间那些轮次里这 22ms 全是白付的。
    ///
    /// 成本：快照只在"内容变化"的那一轮里重填，且长度不变时**复用同一个数组** ——
    /// 稳态命中时是 8000 次引用比较（几十微秒）加一次遍历，零分配。
    /// </summary>
    internal sealed class WordListMemo
    {
        private string[] _snapshot;
        private BookProfile _profile;
        private BookRegistry _registry;

        /// <summary>
        /// 命中 = "与上一轮逐位相同"，profile（可能为 null，表示上一轮也没命中）直接复用。
        /// </summary>
        internal bool TryHit(BookRegistry registry, IList<string> words, out BookProfile profile)
        {
            profile = null;
            if (_snapshot == null || !ReferenceEquals(_registry, registry)) return false;
            if (words == null || words.Count != _snapshot.Length) return false;
            for (int i = 0; i < _snapshot.Length; i++)
                if (!ReferenceEquals(_snapshot[i], words[i])) return false;
            profile = _profile;
            return true;
        }

        internal void Store(BookRegistry registry, IList<string> words, BookProfile profile)
        {
            if (words == null)
            {
                _snapshot = null;
                _profile = null;
                _registry = registry;
                return;
            }
            int n = words.Count;
            // 长度不变时复用数组：否则每次未命中都要新分配 8000 个引用（≈64KB），
            // 而"守卫一直不命中"的场景下那就是每秒 64KB 的净新增垃圾 —— 一个为了
            // 省 CPU 反而制造 GC 压力的优化是负优化。
            if (_snapshot == null || _snapshot.Length != n) _snapshot = new string[n];
            for (int i = 0; i < n; i++) _snapshot[i] = words[i];
            _profile = profile;
            _registry = registry;
        }
    }
}
