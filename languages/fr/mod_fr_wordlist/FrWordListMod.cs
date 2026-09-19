// WCP FR Word List — BepInEx 5 插件 (C# 5 语法) v1.1.0
//
// 目的:
//   A) 法语词书 (自定义词书一~四，匹配 catbar-french-cefr-complete 指纹) 与其它词书彻底互不干扰。
//   B) 解决快速测试 / 已学词测试题干与选项严重错位（题干与选项出现旧英语词 / 英语题干配法语选项）核心问题。
//   C) 词表绝不回写成空表 / 过短表，设置安全兜底红线。
//   D) 自选测试(自由选择)的选词界面 (MyParameters.S9CurrentArray_Para, S9extraStudy_Para) 严格过滤非法语词。
//   E) 跨词书启动守卫与基线还原 (FrWL_*)：记录接管字段与原始基线，切换词书时安全还原，绝不污染英语或其它词书。
//   F) 查词面板与音标对齐 (DatabaseManagerS8 / S8checkWordMeaning / ButtonTextTransfer / showTheAnswerS8)。
//   G) 单词发音优先走本地 mp3，防回退内置英文 TTS。
//   H) 离线自愈机制：官方更新覆盖 StreamingAssets 下的 .db 后，后台自动检测探测词并从 fr_db_payload 重灌还原。
//   I) 每日学习/复习队列与日语复刻版同样覆盖原生 Reset/刷新入口；检测总表、剩余表、已完成表
//      不一致时自动恢复，避免只剩少量残留词就被 CompleteIf 标记为完成。

using System;
using System.Collections;
using System.Collections.Generic;
using System.Reflection;
using BepInEx;
using BepInEx.Configuration;
using BepInEx.Logging;
using HarmonyLib;
using Mono.Data.Sqlite;
using TMPro;
using UnityEngine;
using UnityEngine.Networking;
using WcpBookProfiles;

namespace FrWordList
{
    [BepInPlugin("dev.hanserdesu.frwordlist", "WCP FR Word List", "1.2.0")]
    public class FrWordListPlugin : BaseUnityPlugin
    {
        internal const string ReviewRangeType = "复习范围词";

        internal static ManualLogSource Log;
        internal static FrWordListPlugin Instance;

        private static ConfigEntry<bool> _enabled;
        private static ConfigEntry<bool> _topUp;
        private static ConfigEntry<bool> _guardOtherLists;
        private static ConfigEntry<bool> _healDb;
        private static ConfigEntry<bool> _allowLegacySharedDbWrites;
        private static readonly HashSet<string> Warned = new HashSet<string>();
        private static ConfigEntry<bool> _wordAudioFallback;
        private static ConfigEntry<bool> _yieldToHost;
        private static readonly Dictionary<string, string> LastSig = new Dictionary<string, string>();

        // 存档里的词书名缓存 (判断游戏是否已经读档)
        private static string _diskBook;
        private static float _diskBookAt = -1E9f;

        // 本书释义字典 (MyBook.es3 wordDictionaryN) 缓存 + 出题时攒下的词条缓存
        private static Dictionary<string, string> _bookDict;
        private static int _bookDictIdx = -1;
        private static readonly Dictionary<string, string> Harvested = new Dictionary<string, string>();

        // 当前内存词表与各槽词表的身份缓存
        private static int _slotProfileIdx = -1;
        private static BookProfile _slotProfile;
        private static List<string> _memoryProfileSnapshot;
        private static string[] _slotProfileSnapshot;
        private static string _memoryProfileBookName;
        private static BookProfile _memoryProfile;
        private static string _stateMem = "<none>";
        private static string _stateSlot = "<none>";

        // 插件只临时接管已登记词书的共享队列，修改时同步落盘；离开词书时再还原
        private static readonly HashSet<string> TouchedListFields = new HashSet<string>();
        private static readonly HashSet<string> TouchedArrayFields = new HashSet<string>();
        private static readonly HashSet<string> TouchedIntFields = new HashSet<string>();
        private static readonly HashSet<string> TouchedBoolFields = new HashSet<string>();

        // 插件动过的存档键在修改前的原始值
        private static readonly Dictionary<string, List<string>> BaselineLists =
            new Dictionary<string, List<string>>();
        private static readonly Dictionary<string, string[]> BaselineArrays =
            new Dictionary<string, string[]>();
        private static readonly Dictionary<string, bool> BaselineBools =
            new Dictionary<string, bool>();

        // 插件自有的存档键 (FrWL_*)
        private const string OwnedListKey = "FrWL_owned_lists";
        private const string OwnedArrayKey = "FrWL_owned_arrays";
        private const string OwnedBoolKey = "FrWL_owned_bools";
        private const string BakPrefix = "FrWL_bak_";
        private const string OwnedSourceSlotKey = "FrWL_owned_source_slot";

        // 跨词书启动守卫
        private static bool _crossBookGuardDone;
        private static bool _disabledCleanupDone;
        // 已让位宿主 WcpHost 的标志。注意 Awake 里的 return 只跳过了 PatchAll,
        // 挡不住 Update 的三个每秒轮询 —— 详见 Update() 顶部说明。
        private static bool _yieldedToHost;
        // 其它受管语言词书正在激活时暂缓还原 (跨插件写序竞争守卫)。
        // 根因: 切到另一本受管词书的瞬间, 对方插件可能已经重建了共享队列;
        // 本插件随后的切书还原会把旧基线盖回去, 再触发 FightList 时
        // 游戏用全局已学词典补池, 队列里就混入其它语言的词。
        // 队列基线是易失的会话边界, 晚一秒还原是安全的; 对方书的内容
        // 一旦被盖掉就找不回来了。互斥判定由全语言注册表 (BookProfiles.All) 保证。
        private static bool _deferredRestoreLogged;

        // 换行
        private static readonly string NL = ((char)10).ToString();
        private static readonly string ESC_NL = new string(new char[] { (char)92, (char)92, 'n' });

        private float _nextPoll;

        // 场景加载时先把词表摆正 (prefix)
        internal static readonly string[] SceneTypes = new string[] {
            "InitializeManagerS2", "WordListManagerS7", "S3ScoreShow",
            "LifeAndScoreManagerS15", "showWordS17", "RandomButtonInvoker",
            "MultipleChoiceGenerator", "MultipleChoiceGeneratorS9", "SetS8Data"
        };

        // 游戏算完 / 读完词表之后再校正 (postfix)
        internal static readonly string[] PostTypes = new string[] {
            "ChooseWordManager", "InitializeManagerS2", "updateNewLearnWord",
            "WordListManagerS7", "SetS8Data", "ButtonEquivalence", "S7NumberAdd",
            "ColorInputFieldS17", "MultipleChoiceGenerator", "RandomButtonInvoker",
            "clickChangeImageSource"
        };

        internal static readonly string[] PostMethods = new string[] {
            "Awake", "Start", "FightList", "setFightWord", "setAsFightWord",
            "setAsNewLearnWord", "setAsNewReviewWord", "SwitchSelfChosenMode",
            "UpdateThis", "ResetTestListQuick", "ResetTestListQuick_FreeChoose",
            "ResetExtraReviewList", "ResetExtraReviewList_FreeChoose",
            "ResetExtraStudyList", "ResetExtraStudyList_FreeChoose",
            "ResetDailyStudyList", "ResetDailyReviewList",
            "Get_TodayNewLearnWordForFight", "Get_TodayNewReviewWordForFight",
            "GetNewWord", "InvokeRandomButton", "Randomize",
            "SetReviewCount", "ClickChangeImageSource", "StartQuickTest"
        };

        internal static readonly string[] SceneMethods = new string[] {
            "Awake", "Start", "OnEnable", "GenerateOptions"
        };

        void Awake()
        {
            Log = Logger;
            Instance = this;

            _enabled = Config.Bind("General", "Enabled", true,
                "启用法语词书绝对隔离、已学词测试修复与跨词书基线还原。");
            _topUp = Config.Bind("General", "FightListTopUp", true,
                "战斗词表不满 5 词时自动补满。");
            _guardOtherLists = Config.Bind("General", "GuardOtherLists", true,
                "接管测试与复习队列，过滤跨词书残留词条。");
            _healDb = Config.Bind("General", "HealExampleDatabase", true,
                "旧版兼容开关；只有同时启用 Legacy/AllowSharedDatabaseWrites 才会生效。");
            _allowLegacySharedDbWrites = Config.Bind("Legacy", "AllowSharedDatabaseWrites", false,
                "允许旧版法语插件写入共享 wcpFullEng.db/wcpOnlyWord.db。默认关闭以保持语言资源隔离。");

            _yieldToHost = Config.Bind("Legacy", "YieldToHost", true,
                "宿主 WcpHost 接管本语言后, 旧词表插件自动让位(只保留语言资源)。设 false 强制以旧模式运行。");
            _wordAudioFallback = Config.Bind("Legacy", "WordAudioFallback", false,
                "旧版兼容开关（默认关）。true 时单词音频在 pack 缺失时回退读 legacy 目录 "
                + "<persistentDataPath>/fr_word_audio（迁移期行为，只读）。");
            if (HostTakesOver())
            {
                _yieldedToHost = true;
                Log.LogWarning("FRWordList: WcpHost 已接管法语, 旧词表插件不再打补丁, 轮询 Enforce 一并停用 (Legacy/YieldToHost=false 可强制旧模式)。");
                return;
            }
            PatchAll();
        }

        // 语言资源隔离: 宿主 (WcpHost) 成功接管本语言后, 运行时补丁只能有一个所有者。
        // 两个插件争抢同一批补丁时"后写者胜", 上一本书的词会串进新书 —— 这就是
        // "俄语切日语后还出俄语"的成因。判定看宿主落盘的受管语言登记
        // (<BepInEx>/config/WcpHost.managed.txt), 而不是"文件是否存在":
        // 宿主没装或没接管本语言时, 本插件照旧按旧模式工作。
        private static bool HostTakesOver()
        {
            try
            {
                if (_yieldToHost == null || !_yieldToHost.Value) return false;
                string dir = Paths.ConfigPath;
                if (string.IsNullOrEmpty(dir)) return false;
                string marker = System.IO.Path.Combine(dir, "WcpHost.managed.txt");
                if (!System.IO.File.Exists(marker)) return false;
                string[] codes = System.IO.File.ReadAllLines(marker);
                for (int i = 0; i < codes.Length; i++)
                    if (string.Equals(codes[i].Trim(), PackLangCode, StringComparison.OrdinalIgnoreCase))
                        return true;
                return false;
            }
            catch (Exception e)
            {
                // 判定失败保持旧行为: 宿主不存在才是常态, 不能因为读不到文件就停摆。
                Log.LogWarning("fr FRWordList: 宿主接管判定失败, 按旧模式继续打补丁: " + e.Message);
                return false;
            }
        }
        private void PatchAll()
        {
            Harmony harmony = new Harmony("dev.hanserdesu.frwordlist");
            MethodInfo pre = AccessTools.Method(typeof(FrWordListPlugin), "Pre");
            MethodInfo post = AccessTools.Method(typeof(FrWordListPlugin), "Post");
            MethodInfo postRef = AccessTools.Method(typeof(FrWordListPlugin), "PostRef");
            MethodInfo postBook = AccessTools.Method(typeof(FrWordListPlugin), "PostBookChange");
            MethodInfo postS8 = AccessTools.Method(typeof(FrWordListPlugin), "PostSetAsLearnedTest");
            MethodInfo preS9 = AccessTools.Method(typeof(FrWordListPlugin), "PreMcGenS9");

            int preCount = PatchSet(harmony, SceneTypes, SceneMethods, pre);
            int postCount = PatchSet(harmony, PostTypes, PostMethods, post);

            int refCount = PatchOne(harmony, "ChooseWordManager", "AddWordsToSelfChosenList", postRef);
            int bookCount = PatchOne(harmony, "WordChooseButtonS10", "MakeCertainChange", postBook);
            int healCount = PatchOne(harmony, "SetS8Data", "SetAsLearnedTest", postS8);
            int s9Count = PatchPre(harmony, "MultipleChoiceGeneratorS9", "Start", preS9);
            s9Count += PatchPre(harmony, "MultipleChoiceGeneratorS9", "GenerateOptions", preS9);

            // 选词界面 (MyParameters.S9CurrentArray_Para, S9extraStudy_Para)
            MethodInfo preSel = AccessTools.Method(typeof(FrWordListPlugin), "PreFixSelection");
            MethodInfo postSel = AccessTools.Method(typeof(FrWordListPlugin), "PostFixSelection");
            int selCount = 0;
            selCount += PatchPre(harmony, "PageController", "SetThis", preSel);
            selCount += PatchOne(harmony, "GoToAllS9", "ArrayToAll", postSel);
            selCount += PatchOne(harmony, "SwitchCurrentArrayS9", "SwitchThis", postSel);

            // 题干与选项保证
            int stemCount = 0;
            stemCount += PatchOne(harmony, "MultipleChoiceGenerator", "GenerateOptions",
                AccessTools.Method(typeof(FrWordListPlugin), "PostMcGen"));
            stemCount += PatchOne(harmony, "MultipleChoiceGeneratorS9", "GenerateOptions",
                AccessTools.Method(typeof(FrWordListPlugin), "PostMcGenS9"));
            // 题面取 need[0]，在游戏读取之前将题干队列摆正
            stemCount += PatchPre(harmony, "SetInputFieldValueS8", "ShowTheWord",
                AccessTools.Method(typeof(FrWordListPlugin), "PreShowTheWord"));
            // 快速测试按钮：重新采样只取本书已学词
            stemCount += PatchOne(harmony, "clickChangeImageSource", "StartQuickTest",
                AccessTools.Method(typeof(FrWordListPlugin), "PostStartQuickTest"));

            // 查词面板
            int dictCount = 0;
            dictCount += PatchOne(harmony, "DatabaseManagerS8", "OnSearchButtonClick",
                AccessTools.Method(typeof(FrWordListPlugin), "PostSearchDictS8"));
            dictCount += PatchOne(harmony, "S8checkWordMeaning", "OnSearchButtonClick",
                AccessTools.Method(typeof(FrWordListPlugin), "PostSearchDictCheck"));
            dictCount += PatchOne(harmony, "ButtonTextTransfer", "OnSearchButtonClick",
                AccessTools.Method(typeof(FrWordListPlugin), "PostSearchDictTransfer"));

            MethodInfo postPhonetic = AccessTools.Method(typeof(FrWordListPlugin), "PostAnswerPhonetic");
            int answerCount = 0;
            answerCount += PatchOne(harmony, "showTheAnswerS8", "ShowAnswer", postPhonetic);
            answerCount += PatchOne(harmony, "showTheAnswerS8", "ShowAnswerForStudy", postPhonetic);
            answerCount += PatchOne(harmony, "showTheAnswerS8", "ShowAnswerNoAutoVoice", postPhonetic);

            int classifyCount = PatchOne(harmony, "SetInputFieldValueS8", "changeKnownFuzzUnknownTimes",
                AccessTools.Method(typeof(FrWordListPlugin), "PostS8Classification"));

            int audioCount = PatchPre(harmony, "VocabularyAudioPlayer", "PlayWordAudio",
                AccessTools.Method(typeof(FrWordListPlugin), "PrePlayWordAudio"));


            Log.LogInfo("FRWordList: Harmony patches OK: scene=" + preCount + " post=" + postCount +
                        " addref=" + refCount + " bookchange=" + bookCount +
                        " heal=" + healCount + " s9pre=" + s9Count + " sel=" + selCount +
                        " stem=" + stemCount + " dict=" + dictCount + " answer=" + answerCount +
                        " classify=" + classifyCount + " audio=" + audioCount);
        }

        private int PatchSet(Harmony harmony, string[] typeNames, string[] methodNames, MethodInfo patch)
        {
            int n = 0;
            for (int i = 0; i < typeNames.Length; i++)
            {
                Type t = AccessTools.TypeByName(typeNames[i]);
                if (t == null)
                {
                    WarnOnce("type:" + typeNames[i], "找不到目标类型 " + typeNames[i]);
                    continue;
                }
                List<MethodInfo> all = AccessTools.GetDeclaredMethods(t);
                for (int j = 0; j < all.Count; j++)
                {
                    MethodInfo m = all[j];
                    if (!NameIn(m.Name, methodNames)) continue;
                    if (m.IsAbstract || m.ContainsGenericParameters) continue;
                    try { harmony.Patch(m, null, new HarmonyMethod(patch)); n++; }
                    catch (Exception e) { WarnOnce("patch:" + t.Name + "." + m.Name, "patch 失败 " + t.Name + "." + m.Name + ": " + e.Message); }
                }
            }
            return n;
        }

        private static bool NameIn(string name, string[] names)
        {
            for (int i = 0; i < names.Length; i++)
                if (names[i] == name) return true;
            return false;
        }

        private static int PatchOne(Harmony harmony, string typeName, string methodName, MethodInfo patch)
        {
            Type t = AccessTools.TypeByName(typeName);
            if (t == null) { WarnOnce("type:" + typeName, "找不到目标类型 " + typeName); return 0; }
            MethodInfo m = AccessTools.Method(t, methodName);
            if (m == null) { WarnOnce("method:" + typeName + "." + methodName, "找不到目标方法 " + typeName + "." + methodName); return 0; }
            try { harmony.Patch(m, null, new HarmonyMethod(patch)); return 1; }
            catch (Exception e) { Warn("patch " + typeName + "." + methodName + " 失败: " + e.Message); return 0; }
        }

        private static int PatchPre(Harmony harmony, string typeName, string methodName, MethodInfo prefix)
        {
            Type t = AccessTools.TypeByName(typeName);
            if (t == null) { WarnOnce("type:" + typeName, "找不到目标类型 " + typeName); return 0; }
            MethodInfo m = AccessTools.Method(t, methodName);
            if (m == null) { WarnOnce("method:" + typeName + "." + methodName, "找不到目标方法 " + typeName + "." + methodName); return 0; }
            try { harmony.Patch(m, new HarmonyMethod(prefix), null); return 1; }
            catch (Exception e) { Warn("patch(pre) " + typeName + "." + methodName + " 失败: " + e.Message); return 0; }
        }

        private static void Pre()
        {
            if (!IsEnabled()) return;
            DeferredRestoreCheck();
            try { CrossBookGuard(); }
            catch (Exception e) { Warn("跨词书守卫异常: " + e.Message); }
            try { Enforce(); }
            catch (Exception e) { Warn("prefix 异常: " + e.Message); }
        }

        private static void Post()
        {
            if (!IsEnabled()) return;
            DeferredRestoreCheck();
            try { CrossBookGuard(); }
            catch (Exception e) { Warn("跨词书守卫异常: " + e.Message); }
            try { Enforce(); }
            catch (Exception e) { Warn("postfix 异常: " + e.Message); }
        }

        private static void PostRef(ref List<string> S7TestWordList_Para)
        {
            if (!IsEnabled()) return;
            if (BookState() != 1) return;
            try
            {
                List<string> fixedList = Filter(S7TestWordList_Para, 5, true);
                if (fixedList == null) return;
                S7TestWordList_Para = fixedList;
                MyParameters.S7TestWordList_Para = fixedList;
                SaveField("S7TestWordList_Para", fixedList);
            }
            catch (Exception e) { Warn("postfix(ref) 异常: " + e.Message); }
        }

        private static void PostBookChange()
        {
            if (Instance != null) Instance.StopWordAudio();
            if (!IsEnabled())
            {
                CleanupDisabledState();
                return;
            }
            try
            {
                _memoryProfileSnapshot = null;
                _slotProfileSnapshot = null;
                if (BookState() == 1)
                {
                    Enforce();
                }
                else if (OtherRestoreDeferred())
                {
                    // 对方受管词书已激活: 此时把我们的旧基线写回去只会
                    // 覆盖对方刚建好的队列。轮询会在窗口关闭后继续还原。
                }
                else
                {
                    RestoreSharedFields();
                    RegenerateByGame();
                }
            }
            catch (Exception e) { Warn("切书异常: " + e.Message); }
        }

        private void Update()
        {
            if (_wordAudio != null && _wordAudio.clip != null &&
                (!IsEnabled() || BookState() != 1)) StopWordAudio();
            // 已让位宿主: 受管字段的唯一写者必须是宿主 TakeoverScope。
            // Awake 里的 return 只跳过了 PatchAll —— Update 照旧每 1s 跑一次
            // Enforce() / TickDbHeal() / TickSharedDbSwitch(), 三者都在写游戏
            // 共享库或共享队列, 与宿主争同一批受管字段。让位后必须零字段写入。
            // 实证: RU 加此门控后 PLAYER.log 里恒为 100 的
            // 「队列与完成状态不一致」重建计数降到 0。
            if (_yieldedToHost) return;
            if (!IsEnabled())
            {
                CleanupDisabledState();
                return;
            }
            _disabledCleanupDone = false;
            if (Time.unscaledTime < _nextPoll) return;
            _nextPoll = Time.unscaledTime + 1f;
            DeferredRestoreCheck();
            try { CrossBookGuard(); }
            catch (Exception e) { Warn("跨词书守卫异常: " + e.Message); }
            try { Enforce(); }
            catch (Exception e) { Warn("轮询异常: " + e.Message); }
            try { TickDbHeal(); }
            catch (Exception e) { Warn("离线自愈异常: " + e.Message); }
            try { TickSharedDbSwitch(); }
            catch (Exception e) { Warn("共享库切换轮询异常: " + e.Message); }
        }

        // ---------------- 已学词测试的队列与题干 ----------------

        private static void PostSetAsLearnedTest()
        {
            if (!IsEnabled()) return;
            if (BookState() != 1) return;
            try { HealTestList(); }
            catch (Exception e) { Warn("已学词测试队列自愈异常: " + e.Message); }
        }

        private static void PreMcGenS9()
        {
            if (!IsEnabled()) return;
            if (BookState() != 1) return;
            try { HealTestList(); }
            catch (Exception e) { Warn("S9 前置自愈异常: " + e.Message); }
        }

        private static void PreFixSelection()
        {
            if (BookState() != 1) return;
            try { FixSelectionLists(); }
            catch (Exception e) { Warn("选词表校验异常: " + e.Message); }
        }

        private static void PostFixSelection()
        {
            if (BookState() != 1) return;
            try { FixSelectionLists(); }
            catch (Exception e) { Warn("选词表校验异常: " + e.Message); }
        }

        private static void HealTestList()
        {
            if (MyParameters.S8ThisMode_Para != "已学词测试") return;
            List<string> cur = MyParameters.allTestWordsS10_Para;

            if (cur == null || cur.Count < 5)
            {
                int target = MyParameters.TestWordsNum_Para;
                if (target < 30) target = 30;
                List<string> rebuilt = RebuildWithFallback(cur, 5, target, true);
                if (rebuilt == null) return;

                SetTestLists(rebuilt);
                Warn("已学词测试词表为空/过短, 重新自愈重建 " + rebuilt.Count + " 词");
                return;
            }

            // 检查是否有非法语词条（如旧英语词）混入
            List<string> bookFixed = Filter(cur, 5, true);
            if (bookFixed != null)
            {
                SetTestLists(bookFixed);
                Warn("测试词池混入非法语词条, 已按法语词表重建 " + bookFixed.Count + " 词");
                return;
            }

            int progress = LoadInt("S8Progress_Para", MyParameters.S8Progress_Para);
            if (progress < 0 || progress >= cur.Count)
            {
                ResetProgress();
                Warn("测试进度越界(" + progress + "/" + cur.Count + "), 重置到第 1 题");
                return;
            }

            // 题干队列 = allTestWordsS10_Para 的 progress 及其后部分
            List<string> need = MyParameters.S8needToLearnWordList_Para;
            if (need == null || need.Count == 0 || need[0] != cur[progress])
            {
                Warn("题干队列与当前测试题目错位, 立即同步题干队列 " + (cur.Count - progress) + " 词");
                SyncStemQueue(progress, cur);
            }
        }

        private static void PreShowTheWord()
        {
            if (!IsEnabled()) return;
            if (BookState() != 1) return;
            try { HealTestList(); }
            catch (Exception e) { Warn("题面显示前自愈异常: " + e.Message); }
        }

        // 快速测试按钮重采样：严格只从当前法语书的已学词中重抽
        private static void PostStartQuickTest()
        {
            if (!IsEnabled()) return;
            try
            {
                if (BookState() != 1) return;
                if (MyParameters.S8ThisMode_Para != "已学词测试") return;
                int target = MyParameters.TestWordsNum_Para;
                if (target < 5) target = 5;
                List<string> pool = SampleBookLearned(target);
                if (pool == null || pool.Count < 5)
                    pool = RebuildWithFallback(MyParameters.allTestWordsS10_Para, 5, target, true);
                if (pool == null || pool.Count < 5) return;
                SetTestLists(pool);
                Warn("快速测试词池已按法语书重采样 " + pool.Count + " 词");
            }
            catch (Exception e) { Warn("快速测试重采样异常: " + e.Message); }
        }

        private static List<string> SampleBookLearned(int target)
        {
            Dictionary<string, WordInfo> learned = MyParameters.HaveLearnedDictionary;
            List<string> book = MyParameters.ChosenBook_List;
            if (learned == null || learned.Count == 0 || book == null || book.Count == 0) return null;
            HashSet<string> bookSet = new HashSet<string>(book);
            List<string> cand = new List<string>();
            foreach (KeyValuePair<string, WordInfo> kv in learned)
            {
                if (kv.Value == null) continue;
                if (!bookSet.Contains(kv.Key)) continue; // 必须是当前法语书中的词
                if (!LevelOn(kv.Value.masteryLevel)) continue;
                cand.Add(kv.Key);
            }
            if (cand.Count == 0) return null;
            OrderByTestSetting(cand, learned);
            if (target > 0 && cand.Count > target) cand.RemoveRange(target, cand.Count - target);
            return cand;
        }

        private static bool LevelOn(int level)
        {
            switch (level)
            {
                case 0: return MyParameters.level0If;
                case 1: return MyParameters.level1If;
                case 2: return MyParameters.level2If;
                case 3: return MyParameters.level3If;
                case 4: return MyParameters.level4If;
                case 5: return MyParameters.level5If;
            }
            return false;
        }

        private static void SetTestLists(List<string> pool)
        {
            if (pool == null || pool.Count < 1) return;
            MyParameters.allTestWordsS10_Para = pool;
            SaveField("allTestWordsS10_Para", pool);
            MyParameters.S8TestWordList_Para = new List<string>(pool);
            SaveField("S8TestWordList_Para", MyParameters.S8TestWordList_Para);
            MyParameters.S8TestWordList_LearnedTest_left = new List<string>(pool);
            SaveField("S8TestWordList_LearnedTest_left", MyParameters.S8TestWordList_LearnedTest_left);
            MyParameters.S8needToLearnWordList_Para = new List<string>(pool);
            SaveField("S8needToLearnWordList_Para", MyParameters.S8needToLearnWordList_Para);

            if (MyParameters.S8ThisMode_Para == "已学词测试")
            {
                MyParameters.S8TestWordList_LearnedTest_Finished = new List<string>();
                SaveField("S8TestWordList_LearnedTest_Finished", MyParameters.S8TestWordList_LearnedTest_Finished);
                MyParameters.S8HaveLearnedWordList_Para = ClearList(MyParameters.S8HaveLearnedWordList_Para);
                SaveField("S8HaveLearnedWordList_Para", MyParameters.S8HaveLearnedWordList_Para);
                MyParameters.S8HaveLearnedStatusList_LearnedTest = ClearList(MyParameters.S8HaveLearnedStatusList_LearnedTest);
                SaveField("S8HaveLearnedStatusList_LearnedTest", MyParameters.S8HaveLearnedStatusList_LearnedTest);
                MyParameters.S8HaveLearnedStatusList_Para = ClearList(MyParameters.S8HaveLearnedStatusList_Para);
                SaveField("S8HaveLearnedStatusList_Para", MyParameters.S8HaveLearnedStatusList_Para);
                MyParameters.S8ForgetThisTimeList_LearnedTest = ClearList(MyParameters.S8ForgetThisTimeList_LearnedTest);
                SaveField("S8ForgetThisTimeList_LearnedTest", MyParameters.S8ForgetThisTimeList_LearnedTest);
                MyParameters.S8ForgetThisTimeList_Para = ClearList(MyParameters.S8ForgetThisTimeList_Para);
                SaveField("S8ForgetThisTimeList_Para", MyParameters.S8ForgetThisTimeList_Para);
                ResetProgress();
            }
        }

        private static void SyncStemQueue(int progress, List<string> pool)
        {
            if (MyParameters.S8ThisMode_Para != "已学词测试") return;
            if (pool == null || pool.Count == 0) return;
            if (progress < 0 || progress >= pool.Count) progress = 0;
            List<string> tail = pool.GetRange(progress, pool.Count - progress);
            MyParameters.S8needToLearnWordList_Para = tail;
            SaveField("S8needToLearnWordList_Para", tail);
            List<string> left = new List<string>(tail);
            MyParameters.S8TestWordList_LearnedTest_left = left;
            SaveField("S8TestWordList_LearnedTest_left", left);
        }

        private static List<string> ClearList(List<string> field)
        {
            if (field == null) return new List<string>();
            field.Clear();
            return field;
        }

        // ---------------- 核心逻辑 ----------------

        internal static void Enforce()
        {
            int state = BookState();
            if (state != 1) return;

            int fightMax = MyParameters.S7FightWordMax;
            if (fightMax < 5) fightMax = 5;
            bool topUp = Instance != null && _topUp.Value;
            FixField("S7TestWordList_Para", ref MyParameters.S7TestWordList_Para,
                     topUp ? fightMax : 5, true);

            if (!_guardOtherLists.Value) return;

            List<string> testFixed = Filter(MyParameters.allTestWordsS10_Para, 5, true);
            if (testFixed == null && (MyParameters.allTestWordsS10_Para == null ||
                                      MyParameters.allTestWordsS10_Para.Count < 5))
            {
                testFixed = RebuildWithFallback(MyParameters.allTestWordsS10_Para, 5, 30, true);
            }
            if (testFixed != null)
            {
                MyParameters.allTestWordsS10_Para = testFixed;
                SaveField("allTestWordsS10_Para", testFixed);
                List<string> left = new List<string>(testFixed);
                MyParameters.S8TestWordList_LearnedTest_left = left;
                SaveField("S8TestWordList_LearnedTest_left", left);
                if (MyParameters.S8TestWordList_LearnedTest_Finished != null)
                {
                    MyParameters.S8TestWordList_LearnedTest_Finished.Clear();
                    SaveField("S8TestWordList_LearnedTest_Finished", MyParameters.S8TestWordList_LearnedTest_Finished);
                }
                ResetProgress();
                SyncStemQueue(0, testFixed);
            }
            else
            {
                FixField("S8TestWordList_LearnedTest_left", ref MyParameters.S8TestWordList_LearnedTest_left, 5, true);
            }

            FixField("S8TestWordList_DailyReview", ref MyParameters.S8TestWordList_DailyReview, 1, true);
            FixField("S8TestWordList_DailyReview_left", ref MyParameters.S8TestWordList_DailyReview_left, 1, true);
            FixField("S8TestWordList_ExtraReview", ref MyParameters.S8TestWordList_ExtraReview, 1, true);
            FixField("S8TestWordList_ExtraReview_left", ref MyParameters.S8TestWordList_ExtraReview_left, 1, true);
            FixField("S8TestWordList_DailyStudy", ref MyParameters.S8TestWordList_DailyStudy, 1, false);
            FixField("S8TestWordList_DailyStudy_left", ref MyParameters.S8TestWordList_DailyStudy_left, 1, false);
            FixField("S8TestWordList_ExtraStudy", ref MyParameters.S8TestWordList_ExtraStudy, 1, false);
            FixField("S8TestWordList_ExtraStudy_left", ref MyParameters.S8TestWordList_ExtraStudy_left, 1, false);

            // 原生完成条件只检查当前 need 队列是否为空，不能发现“总表 100、left 为空、Finished 只有 2”
            // 这种跨会话残留。若不先重建，玩家完成残留的两个词后就会被标记为每日学习完成。
            RepairDailyQueues();

            FixSelectionLists();
        }

        private static void RepairDailyQueues()
        {
            if (_guardOtherLists == null || !_guardOtherLists.Value) return;
            RepairDailyQueue("S8TestWordList_DailyStudy", "S8TestWordList_DailyStudy_left",
                "S8TestWordList_DailyStudy_Finished", "CompleteIf_DailyStudy", "每日学习");
            RepairDailyQueue("S8TestWordList_DailyReview", "S8TestWordList_DailyReview_left",
                "S8TestWordList_DailyReview_Finished", "CompleteIf_DailyReview", "每日复习");
        }

        private static void RepairDailyQueue(string totalKey, string leftKey, string finishedKey,
            string completeKey, string mode)
        {
            List<string> total = ReadListField(totalKey);
            if (total == null || total.Count == 0) return;

            List<string> finished = ReadListField(finishedKey);
            if (finished == null) finished = new List<string>();
            HashSet<string> totalSet = new HashSet<string>();
            for (int i = 0; i < total.Count; i++)
            {
                string word = total[i];
                if (!string.IsNullOrEmpty(word)) totalSet.Add(word);
            }

            HashSet<string> finishedSet = new HashSet<string>();
            for (int i = 0; i < finished.Count; i++)
            {
                string word = finished[i];
                if (!string.IsNullOrEmpty(word) && totalSet.Contains(word)) finishedSet.Add(word);
            }

            List<string> left = ReadListField(leftKey);
            if (left == null) left = new List<string>();
            List<string> expected = new List<string>();
            HashSet<string> expectedSeen = new HashSet<string>();
            for (int i = 0; i < total.Count; i++)
            {
                string word = total[i];
                if (string.IsNullOrEmpty(word) || finishedSet.Contains(word)) continue;
                if (expectedSeen.Add(word)) expected.Add(word);
            }
            bool complete = ReadBoolField(completeKey, false);
            bool changed = false;

            // 关键不变量：left 必须精确等于总表 - Finished，而不只是“非空”。
            // 旧版本只修复 left 为空的情况，少量残留词、已完成词回流和
            // 跨词书词混入仍会被原生完成逻辑误认为合法。
            if (!SameWords(left, expected))
            {
                SetListField(leftKey, expected);
                left = expected;
                changed = true;
            }

            // 完成标志必须与 left/Finished 一致；这是截图中“2/100 + 已完成”的直接修复。
            if (left.Count > 0 && complete)
            {
                SaveBoolField(completeKey, false);
                complete = false;
                changed = true;
            }
            else if (left.Count == 0 && finishedSet.Count >= totalSet.Count && !complete)
            {
                SaveBoolField(completeKey, true);
                complete = true;
                changed = true;
            }

            // 当前正在该模式时，SetS8Data/ShowTheWord 还会读取共享 need 队列；
            // 它必须与修复后的 left 完全一致，避免题干继续读取另一份残留队列。
            if (MyParameters.S8ThisMode_Para == mode)
            {
                List<string> need = MyParameters.S8needToLearnWordList_Para;
                if (!SameWords(need, left))
                {
                    SetListField("S8needToLearnWordList_Para", left);
                    changed = true;
                }
                if (MyParameters.S8TestWordList_Para == null ||
                    MyParameters.S8TestWordList_Para.Count == 0)
                    SetListField("S8TestWordList_Para", total);
            }

            if (changed)
            {
                Warn(mode + "队列与完成状态不一致，已按总表 - 已完成重建剩余 " + left.Count + " 词");
            }
        }

        private static void SetListField(string key, List<string> value)
        {
            List<string> copy = new List<string>(value ?? new List<string>());
            SaveField(key, copy);
            SetParameterField(key, copy);
        }

        private static bool SameWords(IList<string> a, IList<string> b)
        {
            if (a == null || b == null) return a == null && b == null;
            if (a.Count != b.Count) return false;
            for (int i = 0; i < a.Count; i++)
                if (!string.Equals(a[i], b[i], StringComparison.Ordinal)) return false;
            return true;
        }

        private static void FixField(string key, ref List<string> field, int minKeep, bool preferLearned)
        {
            List<string> fixedList = Filter(field, minKeep, preferLearned);
            if (fixedList == null) return;
            field = fixedList;
            SaveField(key, fixedList);
        }

        private static void FixArray(string key, ref string[] field, int minKeep, bool preferLearned)
        {
            if (field == null) return;
            List<string> fixedList = Filter(new List<string>(field), minKeep, preferLearned);
            if (fixedList == null) return;
            field = fixedList.ToArray();
            SaveField(key, field);
        }

        internal static void FixSelectionLists()
        {
            if (!IsEnabled()) return;
            if (BookState() != 1) return;
            if (_guardOtherLists == null || !_guardOtherLists.Value) return;
            FixArray("S9CurrentArray_Para", ref MyParameters.S9CurrentArray_Para, 1, true);
            string[] extra = FilterDropArray(MyParameters.S9extraStudy_Para);
            if (extra == null) return;
            MyParameters.S9extraStudy_Para = extra;
            SaveField("S9extraStudy_Para", extra);
            Warn("自选测试已剔除跨词书词, 剩 " + extra.Length + " 词");
        }

        private static string[] FilterDropArray(string[] cur)
        {
            if (cur == null || cur.Length == 0) return null;
            int state = BookState();
            if (state == 0) return null;
            List<string> book = MyParameters.ChosenBook_List;
            HashSet<string> bookSet = (state == 1 && book != null) ? new HashSet<string>(book) : null;
            HashSet<string> seen = new HashSet<string>();
            List<string> keep = new List<string>();
            bool changed = false;
            for (int i = 0; i < cur.Length; i++)
            {
                string w = cur[i];
                if (string.IsNullOrEmpty(w) || !Allowed(w, state == 1, bookSet) || !seen.Add(w))
                {
                    changed = true;
                    continue;
                }
                keep.Add(w);
            }
            return changed ? keep.ToArray() : null;
        }

        private static void ResetProgress()
        {
            if (BookState() != 1) return;
            TouchedIntFields.Add("S8Progress_Para");
            TouchedIntFields.Add("S8LookBack_Para");
            MyParameters.S8Progress_Para = 0;
            MyParameters.S8LookBack_Para = 0;
        }

        private static int LoadInt(string key, int fallback)
        {
            try { return ES3.Load<int>(key, fallback); }
            catch (Exception e)
            {
                WarnOnce("ld:" + key, "读取 " + key + " 失败: " + e.Message);
                return fallback;
            }
        }

        private static List<string> Filter(List<string> cur, int minKeep, bool preferLearned)
        {
            if (cur == null || cur.Count == 0) return null;
            int state = BookState();
            if (state == 0) return null;
            bool fr = (state == 1);
            List<string> book = MyParameters.ChosenBook_List;
            HashSet<string> bookSet = fr ? new HashSet<string>(book) : null;

            HashSet<string> seen = new HashSet<string>();
            List<string> keep = new List<string>();
            int dropped = 0;
            for (int i = 0; i < cur.Count; i++)
            {
                string w = cur[i];
                if (string.IsNullOrEmpty(w)) continue;
                if (!Allowed(w, fr, bookSet)) { dropped++; continue; }
                if (seen.Add(w)) keep.Add(w);
            }
            if (dropped == 0 && keep.Count == cur.Count) return null;

            if (minKeep < 1) minKeep = 1;
            if (keep.Count < minKeep)
            {
                int target = cur.Count;
                if (target < minKeep) target = minKeep;
                keep.Clear();
                seen.Clear();
                Rebuild(keep, seen, fr, bookSet, preferLearned, target);
                if (keep.Count < minKeep) return null;
            }
            return keep;
        }

        private static List<string> RebuildKeeping(List<string> cur, int minKeep, int target, bool preferLearned)
        {
            int state = BookState();
            if (state == 0) return null;
            bool fr = (state == 1);
            List<string> book = MyParameters.ChosenBook_List;
            HashSet<string> bookSet = fr ? new HashSet<string>(book) : null;
            List<string> dest = new List<string>();
            HashSet<string> seen = new HashSet<string>();
            if (cur != null)
            {
                for (int i = 0; i < cur.Count; i++)
                {
                    string w = cur[i];
                    if (string.IsNullOrEmpty(w) || !Allowed(w, fr, bookSet)) continue;
                    if (seen.Add(w)) dest.Add(w);
                }
            }
            if (target < minKeep) target = minKeep;
            if (dest.Count > target) target = dest.Count;
            Rebuild(dest, seen, fr, bookSet, preferLearned, target);
            if (dest.Count < minKeep) return null;
            return dest;
        }

        private static List<string> RebuildWithFallback(List<string> cur, int minKeep, int target, bool preferLearned)
        {
            List<string> rebuilt = RebuildKeeping(cur, minKeep, target, preferLearned);
            if (rebuilt != null) return rebuilt;

            List<string> book = MyParameters.ChosenBook_List;
            if (book == null || book.Count < minKeep) return null;
            if (target < minKeep) target = minKeep;
            List<string> dest = new List<string>();
            HashSet<string> seen = new HashSet<string>();
            if (cur != null)
            {
                for (int i = 0; i < cur.Count && dest.Count < target; i++)
                {
                    string w = cur[i];
                    if (string.IsNullOrEmpty(w)) continue;
                    if (seen.Add(w)) dest.Add(w);
                }
            }
            FillFromList(dest, seen, book, target);
            if (dest.Count < minKeep) return null;
            return dest;
        }

        private static void Rebuild(List<string> dest, HashSet<string> seen, bool fr, HashSet<string> bookSet, bool preferLearned, int target)
        {
            List<string> book = MyParameters.ChosenBook_List;
            if (fr && book != null)
            {
                // 词池只能从当前词书补齐。HaveLearnedDictionary 是游戏全局表，
                // 不能作为跨词书的候选源；否则英语书的已学同形词会偏置法语战斗。
                FillFromBookProgress(dest, seen, book, preferLearned, target);
            }
            else
            {
                FillFromList(dest, seen, book, target);
            }
        }

        private static void FillFromBookProgress(List<string> dest, HashSet<string> seen,
            List<string> book, bool preferLearned, int target)
        {
            if (book == null) return;
            Dictionary<string, WordInfo> learned = MyParameters.HaveLearnedDictionary;
            List<string> learnedBook = new List<string>();
            List<string> unlearnedBook = new List<string>();
            for (int i = 0; i < book.Count; i++)
            {
                string w = book[i];
                if (string.IsNullOrEmpty(w) || seen.Contains(w)) continue;
                bool isLearned = learned != null && learned.ContainsKey(w);
                if (isLearned) learnedBook.Add(w); else unlearnedBook.Add(w);
            }
            if (preferLearned)
            {
                OrderByTestSetting(learnedBook, learned);
                FillFromList(dest, seen, learnedBook, target);
                FillFromList(dest, seen, unlearnedBook, target);
            }
            else
            {
                FillFromList(dest, seen, unlearnedBook, target);
                FillFromList(dest, seen, learnedBook, target);
            }
        }

        private static void FillFromLearned(List<string> dest, HashSet<string> seen, bool fr, HashSet<string> bookSet, int target)
        {
            Dictionary<string, WordInfo> learned = MyParameters.HaveLearnedDictionary;
            if (learned == null) return;
            List<string> cand = new List<string>();
            foreach (KeyValuePair<string, WordInfo> kv in learned)
            {
                string w = kv.Key;
                if (string.IsNullOrEmpty(w)) continue;
                if (!Allowed(w, fr, bookSet)) continue;
                cand.Add(w);
            }
            OrderByTestSetting(cand, learned);
            for (int i = 0; i < cand.Count && dest.Count < target; i++)
                if (seen.Add(cand[i])) dest.Add(cand[i]);
        }

        private static void OrderByTestSetting(List<string> cand, Dictionary<string, WordInfo> learned)
        {
            if (cand == null || cand.Count < 2) return;
            string mode = MyParameters.testNegOrPos;
            if (string.IsNullOrEmpty(mode)) mode = "正序";
            if (mode == "随机")
            {
                System.Random rng = new System.Random();
                for (int i = cand.Count - 1; i > 0; i--)
                {
                    int j = rng.Next(i + 1);
                    string t = cand[i]; cand[i] = cand[j]; cand[j] = t;
                }
                return;
            }
            bool desc = (mode == "倒序");
            if (MyParameters.testPriorityOn)
            {
                cand.Sort(delegate(string a, string b)
                {
                    int c = Times(a, learned).CompareTo(Times(b, learned));
                    if (c != 0) return c;
                    int sa = Study(a, learned);
                    int sb = Study(b, learned);
                    return desc ? sb.CompareTo(sa) : sa.CompareTo(sb);
                });
            }
            else if (desc)
            {
                cand.Sort(delegate(string a, string b)
                { return Times(b, learned).CompareTo(Times(a, learned)); });
            }
            else
            {
                cand.Sort(delegate(string a, string b)
                { return Study(a, learned).CompareTo(Study(b, learned)); });
            }
        }

        private static int Times(string w, Dictionary<string, WordInfo> d)
        {
            WordInfo i;
            return (d != null && d.TryGetValue(w, out i) && i != null) ? i.testTimes : 0;
        }

        private static int Study(string w, Dictionary<string, WordInfo> d)
        {
            WordInfo i;
            return (d != null && d.TryGetValue(w, out i) && i != null) ? i.lastStudyTime : 0;
        }

        private static void FillFromList(List<string> dest, HashSet<string> seen, List<string> src, int target)
        {
            if (src == null) return;
            for (int i = 0; i < src.Count && dest.Count < target; i++)
            {
                string w = src[i];
                if (string.IsNullOrEmpty(w)) continue;
                if (seen.Add(w)) dest.Add(w);
            }
        }

        private static bool Allowed(string w, bool fr, HashSet<string> bookSet)
        {
            if (string.IsNullOrEmpty(w)) return false;
            return fr ? (bookSet != null && bookSet.Contains(w)) : true;
        }

        internal static int BookState()
        {
            int state = BookStateRaw();
            LogBookState(state);
            return state;
        }

        private static int BookStateRaw()
        {
            _stateMem = "<none>";
            _stateSlot = "<none>";
            if (!BookReady()) return 0;
            string name = MyParameters.ChosenBook_Para;
            if (string.IsNullOrEmpty(name)) return 0;
            List<string> book = MyParameters.ChosenBook_List;
            if (book == null || book.Count < 5) return 0;

            int idx = SelfBookIndexOf(name);
            if (idx <= 0) return 0;
            BookProfile memoryProfile = ProfileOfCurrentList(book);
            BookProfile slotProfile = SlotProfile(idx);
            _stateMem = ProfileId(memoryProfile);
            _stateSlot = ProfileId(slotProfile);
            if (memoryProfile == null || memoryProfile.Language != BookProfiles.French) return 0;
            if (slotProfile == null || slotProfile.Id != memoryProfile.Id) return 0;
            return 1;
        }

        private static string ProfileId(BookProfile profile)
        {
            return profile == null ? "<none>" : profile.Id;
        }

        // 共享数据库只有一个当前语言态。德语插件也会维护同一组
        // wcpFullEng/wcpOnlyWord 文件；法语插件不能在德语书激活时把它
        // 抢回英语，否则两个插件会互相覆盖同形词释义和例句。
        private static string CurrentManagedLanguage()
        {
            try
            {
                if (!BookReady()) return null;
                BookProfile profile = ProfileOfCurrentList(MyParameters.ChosenBook_List);
                return profile == null ? null : profile.Language;
            }
            catch (Exception) { return null; }
        }

        private static BookProfile ProfileOfCurrentList(List<string> list)
        {
            string bookName = MyParameters.ChosenBook_Para;
            if (list != null && bookName == _memoryProfileBookName &&
                SameWords(list, _memoryProfileSnapshot))
                return _memoryProfile;
            _memoryProfileSnapshot = list == null ? null : new List<string>(list);
            _memoryProfileBookName = bookName;
            _memoryProfile = BookProfiles.Match(list);
            return _memoryProfile;
        }

        private static BookProfile SlotProfile(int idx)
        {
            if (idx <= 0) return null;
            int previousIdx = _slotProfileIdx;
            string[] current = null;
            try
            {
                string path = System.IO.Path.Combine(Application.persistentDataPath, "MyBook.es3");
                try
                {
                    string[] arr = ES3.Load<string[]>("SelfBookList" + idx, path);
                    if (arr != null && arr.Length > 0) current = arr;
                }
                catch (Exception) { }
                if (current == null || current.Length < 5)
                {
                    try
                    {
                        Dictionary<string, string> d = ES3.Load<Dictionary<string, string>>("wordDictionary" + idx, path);
                        if (d != null && d.Count > 0)
                        {
                            current = new string[d.Count];
                            int n = 0;
                            foreach (KeyValuePair<string, string> kv in d) current[n++] = kv.Key;
                        }
                    }
                    catch (Exception) { }
                }
                if (idx == previousIdx && SameWords(current, _slotProfileSnapshot))
                    return _slotProfile;
                _slotProfileIdx = idx;
                _slotProfileSnapshot = current == null ? null : (string[])current.Clone();
                _slotProfile = current == null ? null : BookProfiles.Match(current);
            }
            catch (Exception e) { WarnOnce("slotprofile:" + idx, "读取槽位 " + idx + " 词表失败: " + e.Message); }
            return _slotProfile;
        }

        private static void LogBookState(int state)
        {
            List<string> book = MyParameters.ChosenBook_List;
            int n = (book == null) ? -1 : book.Count;
            string sig = state + "|" + MyParameters.ChosenBook_Para + "|" + n + "|" + _stateMem + "|" + _stateSlot;
            string prev;
            if (LastSig.TryGetValue("bookstate", out prev) && prev == sig) return;
            LastSig["bookstate"] = sig;
            Log.LogInfo("FRWordList: 词书状态=" + state + " 内存书名=" + MyParameters.ChosenBook_Para +
                        " 内存词表=" + n + "词(内存 Profile=" + _stateMem + " 槽位 Profile=" + _stateSlot +
                        ") 存档书名=" + (DiskBookName() ?? "<未读档>"));
        }

        private static void RegenerateByGame()
        {
            string type = MyParameters.S7FightWordType;
            if (!string.IsNullOrEmpty(type) && type != ReviewRangeType) return;
            ChooseWordManager mgr = UnityEngine.Object.FindObjectOfType<ChooseWordManager>();
            if (mgr == null) return;
            mgr.FightList();
            Log.LogInfo("FRWordList: 换出受管词书, 唤醒游戏重新生成当前战斗词表");
        }

        // ---------------- 题干 / 选项保障 ----------------

        private static string CurrentFightWord()
        {
            List<string> l = MyParameters.S7TestWordList_Para;
            int i = MyParameters.S7Progress_Para;
            if (l == null || i < 0 || i >= l.Count) return null;
            return l[i];
        }

        private static string CurrentTestWordS9()
        {
            List<string> l = MyParameters.allTestWordsS10_Para;
            int i = MyParameters.S8Progress_Para;
            if (l == null || i < 0 || i >= l.Count) return null;
            return l[i];
        }

        // 战斗/复习四选一
        private static void PostMcGen(MultipleChoiceGenerator __instance)
        {
            if (BookState() != 1 || __instance == null) return;
            try
            {
                string word = CurrentFightWord();
                TextMeshProUGUI[] opts = new TextMeshProUGUI[] {
                    __instance.option1Text, __instance.option2Text,
                    __instance.option3Text, __instance.option4Text };
                TextMeshProUGUI[] optsSM = new TextMeshProUGUI[] {
                    __instance.option1Text_SM, __instance.option2Text_SM,
                    __instance.option3Text_SM, __instance.option4Text_SM };
                TextMeshProUGUI[] words = new TextMeshProUGUI[] {
                    __instance.word1Text, __instance.word2Text,
                    __instance.word3Text, __instance.word4Text };

                for (int i = 0; i < opts.Length; i++)
                {
                    if (opts[i] == null) continue;
                    string w = (words[i] != null) ? words[i].text : null;
                    if (string.IsNullOrEmpty(opts[i].text) && !string.IsNullOrEmpty(w))
                    {
                        string entry = EntryOf(w);
                        if (entry != null)
                        {
                            opts[i].text = MeaningOf(entry);
                            if (optsSM[i] != null) optsSM[i].text = opts[i].text;
                        }
                    }
                    Harvest(w, opts[i].text);
                }
            }
            catch (Exception e) { Warn("四选一选项保障(战斗)异常: " + e.Message); }
        }

        // 已学词测试 (S9)
        private static void PostMcGenS9(MultipleChoiceGeneratorS9 __instance)
        {
            if (BookState() != 1 || __instance == null) return;
            try
            {
                string[] optWords = new string[] {
                    MyParameters.S9Option1_Para, MyParameters.S9Option2_Para,
                    MyParameters.S9Option3_Para, MyParameters.S9Option4_Para };

                if (__instance.optionText != null)
                {
                    for (int i = 0; i < __instance.optionText.Length && i < optWords.Length; i++)
                    {
                        if (__instance.optionText[i] == null) continue;
                        if (string.IsNullOrEmpty(__instance.optionText[i].text) && !string.IsNullOrEmpty(optWords[i]))
                        {
                            string entry = EntryOf(optWords[i]);
                            if (entry != null)
                                __instance.optionText[i].text = MeaningOf(entry);
                        }
                        Harvest(optWords[i], __instance.optionText[i].text);
                    }
                }
            }
            catch (Exception e) { Warn("四选一选项保障(S9)异常: " + e.Message); }
        }

        // ---------------- 查词面板 / 音标 ----------------

        private static void PostSearchDictS8(DatabaseManagerS8 __instance)
        {
            if (__instance == null) return;
            FixDictPanel(__instance.meaningText, __instance.usPhoneticText, __instance.ukPhoneticText);
        }

        private static void PostSearchDictCheck(S8checkWordMeaning __instance)
        {
            if (__instance == null) return;
            FixDictPanel(__instance.meaningText, null, null);
        }

        private static void PostSearchDictTransfer(ButtonTextTransfer __instance)
        {
            if (__instance == null) return;
            FixDictPanel(__instance.meaningText, null, null);
        }

        private static void PostAnswerPhonetic(showTheAnswerS8 __instance)
        {
            if (!IsEnabled() || BookState() != 1 || __instance == null) return;
            try
            {
                if (__instance.phonicsText == null) return;
                string us = (__instance.Target_phonicsUSText == null) ? null :
                    __instance.Target_phonicsUSText.text;
                string uk = (__instance.Target_phonicsUKText == null) ? null :
                    __instance.Target_phonicsUKText.text;
                string phonetic = !string.IsNullOrEmpty(uk) ? uk.Trim() :
                    (!string.IsNullOrEmpty(us) ? us.Trim() : null);
                if (!string.IsNullOrEmpty(phonetic)) __instance.phonicsText.text = phonetic;
            }
            catch (Exception e) { WarnOnce("answerphonetic", "音标显示异常: " + e.Message); }
        }

        private static void PostS8Classification(SetInputFieldValueS8 __instance)
        {
            if (!IsEnabled() || __instance == null || Instance == null) return;
            if (BookState() != 1 || !__instance.gameObject.activeInHierarchy) return;
            Instance.StartCoroutine(RefreshS8AfterClassification(__instance));
        }

        private static IEnumerator RefreshS8AfterClassification(SetInputFieldValueS8 instance)
        {
            yield return null;
            try
            {
                if (instance == null || !instance.gameObject.activeInHierarchy) yield break;
                MyParameters.S8LookBack_Para = MyParameters.S8Progress_Para;
                List<string> left = MyParameters.S8needToLearnWordList_Para;
                if (left == null || left.Count == 0)
                {
                    if (instance.invokeButtonFinish != null) instance.invokeButtonFinish.onClick.Invoke();
                }
                else
                {
                    instance.ShowTheWord();
                }
            }
            catch (Exception e) { WarnOnce("s8refresh", "学习页推进刷新异常: " + e.Message); }
        }

        private static void FixDictPanel(TextMeshProUGUI meaning, TextMeshProUGUI us, TextMeshProUGUI uk)
        {
            if (!IsEnabled()) return;
            if (BookState() != 1) return;
            try
            {
                string word = MyParameters.checkWordInDictionary;
                if (string.IsNullOrEmpty(word)) return;
                string entry = EntryOf(word);
                if (entry == null) return;
                if (meaning != null) meaning.text = entry + NL;
                string phonetic = PhoneticOf(entry);
                if (us != null && phonetic != null) us.text = phonetic;
                if (uk != null) uk.text = "";
            }
            catch (Exception e) { WarnOnce("dict", "查词面板修正异常: " + e.Message); }
        }

        // ---------------- 单词发音优先本地音频 ----------------

        private AudioSource _wordAudio;
        private int _wordAudioRequest;

        private static bool PrePlayWordAudio(VocabularyAudioPlayer __instance)
        {
            if (!IsEnabled() || BookState() != 1) return true;
            if (Instance == null || __instance == null || __instance.text1 == null) return false;
            string word = (__instance.text1.text ?? "").Trim();
            if (word.Length == 0 || word.IndexOfAny(System.IO.Path.GetInvalidFileNameChars()) >= 0)
                return false;
            // pack 优先（与宿主 ResourceRouter 的 WordAudioDir 同一物理目录）；
            // Legacy/WordAudioFallback=true 时回退旧目录（数据保留，只读）。
            string file = System.IO.Path.Combine(Application.persistentDataPath,
                "..", "packs", "fr", "audio", "word", word + ".mp3");
            Instance.StopWordAudio();
            if (!System.IO.File.Exists(file) && _wordAudioFallback != null && _wordAudioFallback.Value)
                file = System.IO.Path.Combine(Application.persistentDataPath,
                    "fr_word_audio", word + ".mp3");
            if (!System.IO.File.Exists(file))
            {
                WarnOnce("word-audio:" + word, "法语独立单词音频缺失: " + word);
                return false;
            }
            Instance.StartCoroutine(Instance.PlayLocalWordAudio(file, Instance._wordAudioRequest));
            return false;
        }

        private void StopWordAudio()
        {
            _wordAudioRequest++;
            if (_wordAudio == null) return;
            _wordAudio.Stop();
            AudioClip clip = _wordAudio.clip;
            _wordAudio.clip = null;
            if (clip != null) UnityEngine.Object.Destroy(clip);
        }

        private IEnumerator PlayLocalWordAudio(string file, int request)
        {
            using (UnityWebRequest web = UnityWebRequestMultimedia.GetAudioClip(
                new Uri(file).AbsoluteUri, AudioType.MPEG))
            {
                yield return web.SendWebRequest();
                if (web.result != UnityWebRequest.Result.Success)
                {
                    WarnOnce("word-decode:" + file, "法语单词音频加载失败: " + web.error);
                    yield break;
                }
                AudioClip clip = DownloadHandlerAudioClip.GetContent(web);
                if (request != _wordAudioRequest || !IsEnabled() || BookState() != 1)
                {
                    if (clip != null) UnityEngine.Object.Destroy(clip);
                    yield break;
                }
                if (_wordAudio == null)
                {
                    _wordAudio = gameObject.AddComponent<AudioSource>();
                    _wordAudio.playOnAwake = false;
                    _wordAudio.spatialBlend = 0f;
                }
                _wordAudio.clip = clip;
                _wordAudio.Play();
            }
        }

        private void OnDestroy()
        {
            StopWordAudio();
            if (Instance == this) Instance = null;
        }

        // ---------------- 词书释义字典 ----------------

        private static string EntryOf(string word)
        {
            if (string.IsNullOrEmpty(word)) return null;
            string v = Lookup(MyParameters.SelfBookMeaningDictionary, word);
            if (v == null) v = Lookup(BookDict(), word);
            if (v == null) v = Lookup(Harvested, word);
            if (v == null) return null;
            return CleanEntry(v);
        }

        private static string Lookup(Dictionary<string, string> d, string word)
        {
            if (d == null || d.Count == 0) return null;
            string v;
            if (d.TryGetValue(word, out v) && !string.IsNullOrEmpty(v)) return v;
            string low = word.ToLower();
            if (low != word && d.TryGetValue(low, out v) && !string.IsNullOrEmpty(v)) return v;
            return null;
        }

        private static void Harvest(string word, string meaning)
        {
            if (string.IsNullOrEmpty(word) || string.IsNullOrEmpty(meaning)) return;
            string cur;
            if (Harvested.TryGetValue(word, out cur) && !string.IsNullOrEmpty(cur)) return;
            Harvested[word] = CleanEntry(meaning);
        }

        private static int SelfBookIndexOf(string name)
        {
            if (string.IsNullOrEmpty(name)) return 0;
            if (!name.StartsWith("自定义词书", StringComparison.Ordinal) &&
                !name.StartsWith("法语词库", StringComparison.Ordinal)) return 0;
            for (int i = 0; i < name.Length; i++)
            {
                char c = name[i];
                if (c == '一') return 1;
                if (c == '二') return 2;
                if (c == '三') return 3;
                if (c == '四') return 4;
                if (c >= '1' && c <= '4') return c - '0';
            }
            return 0;
        }

        // 当前激活的词书是否属于其它受管语言 (指纹识别, 与具体槽位无关)。
        // 判定失败一律返回 false -> 还原路径保持旧行为; 误判方向的代价
        // 是多还原一次 (无害), 而不是漏盖对方的队列。
        private static bool OtherManagedBookActive()
        {
            try
            {
                // BookReady deliberately blocks writes while the game is
                // loading.  The cross-book guard must still see the persisted
                // target during that window, otherwise the old plugin can win
                // one last write before MyParameters catches up.
                string diskName = DiskBookName();
                int diskIdx = SelfBookIndexOf(diskName);
                if (diskIdx > 0 && IsOtherManagedProfile(SlotProfile(diskIdx)))
                    return true;

                string name = MyParameters.ChosenBook_Para;
                if (string.IsNullOrEmpty(name)) return false;
                int idx = SelfBookIndexOf(name);
                if (idx <= 0) return false;
                return IsOtherManagedProfile(SlotProfile(idx));
            }
            catch (Exception) { return false; }
        }

        private static bool IsOtherManagedProfile(BookProfile profile)
        {
            return profile != null && profile.Language != BookProfiles.French;
        }

        // 其它受管词书激活期间暂缓一切还原写入; 轮询会持续重试到窗口关闭。
        private static bool OtherRestoreDeferred()
        {
            try
            {
                if (BookState() == 1) return false;
                if (!OtherManagedBookActive()) return false;
                if (!_deferredRestoreLogged)
                {
                    _deferredRestoreLogged = true;
                    Warn("检测到其它受管词书激活, 还原推迟到其重建完成后");
                }
                return true;
            }
            catch (Exception) { return false; }
        }

        // 其它受管词书离开时, 它自己的切书还原负责恢复游戏原状;
        // 这里只需在窗口关闭后让被暂缓的还原自然重试 (CrossBookGuard
        // 每会话一次 + PostBookChange 场景补丁 + 每秒轮询三条路都覆盖)。
        private static void DeferredRestoreCheck()
        {
            try
            {
                if (!IsEnabled() || !BookReady()) return;
                if (BookState() == 1) return;
                if (OtherManagedBookActive())
                {
                    if (!_deferredRestoreLogged)
                    {
                        _deferredRestoreLogged = true;
                        Warn("检测到其它受管词书激活, 暂缓共享队列还原");
                    }
                    return;
                }
                _deferredRestoreLogged = false;
            }
            catch (Exception) { }
        }

        private static Dictionary<string, string> BookDict()
        {
            int idx = SelfBookIndexOf(MyParameters.ChosenBook_Para);
            if (idx <= 0) return null;
            if (_bookDictIdx == idx) return _bookDict;
            _bookDictIdx = idx;
            _bookDict = null;
            try
            {
                string path = System.IO.Path.Combine(Application.persistentDataPath, "MyBook.es3");
                _bookDict = ES3.Load<Dictionary<string, string>>("wordDictionary" + idx, path);
                if (_bookDict != null && Log != null)
                {
                    Log.LogInfo("FRWordList: 加载法语字典 wordDictionary" + idx + " 共 " +
                                _bookDict.Count + " 词");
                }
            }
            catch (Exception e)
            {
                WarnOnce("bookdict" + idx, "读取 MyBook.es3 wordDictionary" + idx + " 失败: " + e.Message);
            }
            return _bookDict;
        }

        private static string CleanEntry(string v)
        {
            if (v.IndexOf(ESC_NL) < 0) return v;
            return v.Replace(ESC_NL, NL);
        }

        private static string PhoneticOf(string entry)
        {
            if (string.IsNullOrEmpty(entry)) return null;
            int b1 = entry.IndexOf('[');
            if (b1 >= 0)
            {
                int b2 = entry.IndexOf(']', b1);
                if (b2 > b1) return entry.Substring(b1, b2 - b1 + 1).Trim();
            }
            return null;
        }

        private static string MeaningOf(string entry)
        {
            if (string.IsNullOrEmpty(entry)) return entry;
            int b2 = entry.IndexOf(']');
            if (b2 >= 0 && b2 + 1 < entry.Length)
                return entry.Substring(b2 + 1).Trim();
            return entry.Trim();
        }

        // ---------------- ES3 ----------------

        private static bool BookReady()
        {
            string disk = DiskBookName();
            if (string.IsNullOrEmpty(disk)) return false;
            string mem = MyParameters.ChosenBook_Para;
            return !string.IsNullOrEmpty(mem) && mem == disk;
        }

        private static string DiskBookName()
        {
            float now = Time.realtimeSinceStartup;
            if (_diskBookAt > -1E8f && now - _diskBookAt < 1f) return _diskBook;
            _diskBookAt = now;
            _diskBook = null;
            try { _diskBook = ES3.Load<string>("ChosenBook_Para", defaultValue: null); }
            catch (Exception e) { WarnOnce("diskbook", "读取存档 ChosenBook_Para 失败: " + e.Message); }
            return _diskBook;
        }

        private static void SaveField(string key, List<string> list)
        {
            if (BookState() != 1) return;
            RecordBaselineList(key);
            TouchedListFields.Add(key);
            RememberOwned(OwnedListKey, key);
            RecordOwnedSlot();
            try { ES3.Save(key, list); }
            catch (Exception e) { Warn("ES3.Save " + key + " 失败: " + e.Message); }
            LogChange(key, list == null ? 0 : list.Count, list == null ? "null" : Sample(list));
        }

        private static void SaveField(string key, string[] arr)
        {
            if (BookState() != 1) return;
            RecordBaselineArray(key);
            TouchedArrayFields.Add(key);
            RememberOwned(OwnedArrayKey, key);
            RecordOwnedSlot();
            try { ES3.Save(key, arr); }
            catch (Exception e) { Warn("ES3.Save " + key + " 失败: " + e.Message); }
            LogChange(key, arr == null ? 0 : arr.Length, arr == null ? "null" : Sample(arr));
        }

        private static void SaveBoolField(string key, bool value)
        {
            if (BookState() != 1) return;
            RecordBaselineBool(key);
            TouchedBoolFields.Add(key);
            RememberOwned(OwnedBoolKey, key);
            RecordOwnedSlot();
            SetParameterField(key, value);
            try { ES3.Save(key, value); }
            catch (Exception e) { Warn("ES3.Save " + key + " 失败: " + e.Message); }
        }

        private static List<string> ReadListField(string key)
        {
            try
            {
                FieldInfo f = typeof(MyParameters).GetField(key,
                    BindingFlags.Public | BindingFlags.Static);
                if (f != null)
                {
                    List<string> current = f.GetValue(null) as List<string>;
                    if (current != null) return new List<string>(current);
                }
            }
            catch (Exception) { }
            try
            {
                List<string> disk = ES3.Load<List<string>>(key, defaultValue: null);
                return disk == null ? new List<string>() : new List<string>(disk);
            }
            catch (Exception e)
            {
                WarnOnce("readlist:" + key, "读取 " + key + " 失败: " + e.Message);
                return new List<string>();
            }
        }

        private static bool ReadBoolField(string key, bool fallback)
        {
            try
            {
                FieldInfo f = typeof(MyParameters).GetField(key,
                    BindingFlags.Public | BindingFlags.Static);
                if (f != null)
                {
                    object current = f.GetValue(null);
                    if (current is bool) return (bool)current;
                }
            }
            catch (Exception) { }
            try { return ES3.Load<bool>(key, defaultValue: fallback); }
            catch (Exception e)
            {
                WarnOnce("readbool:" + key, "读取 " + key + " 失败: " + e.Message);
                return fallback;
            }
        }

        private static void RecordOwnedSlot()
        {
            int slot = SelfBookIndexOf(MyParameters.ChosenBook_Para);
            if (slot > 0)
            {
                try { ES3.Save(OwnedSourceSlotKey, slot); }
                catch (Exception) { }
            }
        }

        private static void RecordBaselineList(string key)
        {
            if (BaselineLists.ContainsKey(key)) return;
            List<string> disk = LoadBaselineListFromDisk(key);
            if (disk != null && !BaselineBelongsToOwnedBook(disk))
            {
                if (!BaselineFromOtherManagedBook(disk))
                {
                    BaselineLists[key] = disk;
                    return;
                }
                // 基线属于其它受管词书 (上一本切换时被还原竞争盖进来的残留):
                // 记为空。它是上一本书的内容, 不属于"接管前的游戏原样"。
                BaselineLists[key] = new List<string>();
                SaveBaselineToDisk(BakPrefix + key, BaselineLists[key]);
                return;
            }
            FieldInfo f = typeof(MyParameters).GetField(key, BindingFlags.Public | BindingFlags.Static);
            List<string> cur = (f != null) ? f.GetValue(null) as List<string> : null;
            if (cur != null && !BaselineBelongsToOwnedBook(cur))
            {
                if (!BaselineFromOtherManagedBook(cur))
                {
                    List<string> clone = new List<string>(cur);
                    BaselineLists[key] = clone;
                    SaveBaselineToDisk(BakPrefix + key, clone);
                    return;
                }
                BaselineLists[key] = new List<string>();
                SaveBaselineToDisk(BakPrefix + key, BaselineLists[key]);
            }
        }

        private static void RecordBaselineArray(string key)
        {
            if (BaselineArrays.ContainsKey(key)) return;
            string[] disk = LoadBaselineArrayFromDisk(key);
            if (disk != null && !BaselineBelongsToOwnedBook(disk))
            {
                if (!BaselineFromOtherManagedBook(disk))
                {
                    BaselineArrays[key] = disk;
                    return;
                }
                BaselineArrays[key] = new string[0];
                SaveBaselineToDisk(BakPrefix + key, BaselineArrays[key]);
                return;
            }
            FieldInfo f = typeof(MyParameters).GetField(key, BindingFlags.Public | BindingFlags.Static);
            string[] cur = (f != null) ? f.GetValue(null) as string[] : null;
            if (cur != null && !BaselineBelongsToOwnedBook(cur))
            {
                if (!BaselineFromOtherManagedBook(cur))
                {
                    string[] clone = (string[])cur.Clone();
                    BaselineArrays[key] = clone;
                    SaveBaselineToDisk(BakPrefix + key, clone);
                    return;
                }
                BaselineArrays[key] = new string[0];
                SaveBaselineToDisk(BakPrefix + key, BaselineArrays[key]);
            }
        }

        private static void RecordBaselineBool(string key)
        {
            if (BaselineBools.ContainsKey(key)) return;
            bool disk;
            if (LoadBaselineBoolFromDisk(key, out disk))
            {
                BaselineBools[key] = disk;
                return;
            }
            try
            {
                FieldInfo f = typeof(MyParameters).GetField(key,
                    BindingFlags.Public | BindingFlags.Static);
                if (f == null) return;
                object current = f.GetValue(null);
                if (!(current is bool)) return;
                BaselineBools[key] = (bool)current;
                SaveBaselineToDisk(BakPrefix + key, (bool)current);
            }
            catch (Exception) { }
        }

        private static bool BaselineBelongsToOwnedBook(IEnumerable<string> words)
        {
            if (words == null) return false;
            int slot = LoadInt(OwnedSourceSlotKey, 0);
            if (slot <= 0) slot = SelfBookIndexOf(MyParameters.ChosenBook_Para);
            if (slot <= 0) return false;
            // Membership must come from the owned French slot, never the newly
            // selected English/Japanese dictionary during cross-book restoration.
            try
            {
                string path = System.IO.Path.Combine(Application.persistentDataPath, "MyBook.es3");
                string[] source = ES3.Load<string[]>("SelfBookList" + slot, path);
                BookProfile profile = BookProfiles.Match(source);
                if (profile == null || profile.Language != BookProfiles.French) return false;
                HashSet<string> owned = new HashSet<string>(source, StringComparer.Ordinal);
                bool any = false;
                foreach (string word in words)
                {
                    if (string.IsNullOrEmpty(word)) continue;
                    any = true;
                    if (!owned.Contains(word)) return false;
                }
                return any;
            }
            catch (Exception) { return false; }
        }

        // 与 BaselineBelongsToOwnedBook 相反方向: 内容能否指纹命中**其它**受管语言。
        // 命中 = 这是上一本受管词书的残留 (还原竞争盖进来的), 还原时必须当空处理,
        // 绝不能在离开本书时把它恢复出去。识别不出 -> false, 保持保守旧行为。
        private static bool BaselineFromOtherManagedBook(IEnumerable<string> words)
        {
            try
            {
                if (words == null) return false;
                List<string> list = new List<string>(words);
                if (list.Count == 0) return false;
                if (BookProfiles.Match(list) != null) return false;   // 完整命中 = 自己
                List<BookProfile> candidates = new List<BookProfile>();
                for (int i = 0; i < BookProfiles.All.Length; i++)
                {
                    BookProfile p = BookProfiles.All[i];
                    if (p.Language == BookProfiles.French) continue;
                    candidates.Add(p);
                }
                string prefix = BookProfiles.FingerprintOf(list);
                if (string.IsNullOrEmpty(prefix)) return false;
                for (int i = 0; i < candidates.Count; i++)
                {
                    string fp = candidates[i].Fingerprint;
                    if (!string.IsNullOrEmpty(fp) && fp.Length >= prefix.Length &&
                        fp.StartsWith(prefix, StringComparison.Ordinal))
                        return true;
                }
                return false;
            }
            catch (Exception) { return false; }
        }

        private static List<string> LoadBaselineListFromDisk(string key)
        {
            try
            {
                string bakKey = BakPrefix + key;
                if (!ES3.KeyExists(bakKey)) return null;
                return ES3.Load<List<string>>(bakKey, defaultValue: null);
            }
            catch (Exception) { return null; }
        }

        private static string[] LoadBaselineArrayFromDisk(string key)
        {
            try
            {
                string bakKey = BakPrefix + key;
                if (!ES3.KeyExists(bakKey)) return null;
                return ES3.Load<string[]>(bakKey, defaultValue: null);
            }
            catch (Exception) { return null; }
        }

        private static bool LoadBaselineBoolFromDisk(string key, out bool value)
        {
            value = false;
            try
            {
                string bakKey = BakPrefix + key;
                if (!ES3.KeyExists(bakKey)) return false;
                value = ES3.Load<bool>(bakKey, defaultValue: false);
                return true;
            }
            catch (Exception) { return false; }
        }

        private static void SaveBaselineToDisk(string bakKey, object value)
        {
            try { ES3.Save(bakKey, value); }
            catch (Exception e) { WarnOnce("savebak:" + bakKey, "保存基线 " + bakKey + " 失败: " + e.Message); }
        }

        private static void RememberOwned(string metaKey, string fieldKey)
        {
            try
            {
                List<string> cur = LoadStringList(metaKey);
                if (!cur.Contains(fieldKey))
                {
                    cur.Add(fieldKey);
                    ES3.Save(metaKey, cur);
                }
            }
            catch (Exception e) { WarnOnce("own:" + metaKey, "记录接管字段 " + metaKey + " 失败: " + e.Message); }
        }

        private static List<string> LoadStringList(string key)
        {
            try
            {
                if (!ES3.KeyExists(key)) return new List<string>();
                List<string> l = ES3.Load<List<string>>(key, defaultValue: null);
                return l ?? new List<string>();
            }
            catch (Exception) { return new List<string>(); }
        }

        private static void ForgetOwned()
        {
            try
            {
                List<string> lists = LoadStringList(OwnedListKey);
                for (int i = 0; i < lists.Count; i++) ES3.DeleteKey(BakPrefix + lists[i]);
                ES3.DeleteKey(OwnedListKey);
                List<string> arrs = LoadStringList(OwnedArrayKey);
                for (int i = 0; i < arrs.Count; i++) ES3.DeleteKey(BakPrefix + arrs[i]);
                ES3.DeleteKey(OwnedArrayKey);
                List<string> bools = LoadStringList(OwnedBoolKey);
                for (int i = 0; i < bools.Count; i++) ES3.DeleteKey(BakPrefix + bools[i]);
                ES3.DeleteKey(OwnedBoolKey);
                ES3.DeleteKey(OwnedSourceSlotKey);
            }
            catch (Exception e) { Warn("清除接管记录失败: " + e.Message); }
            TouchedListFields.Clear();
            TouchedArrayFields.Clear();
            TouchedIntFields.Clear();
            TouchedBoolFields.Clear();
            BaselineLists.Clear();
            BaselineArrays.Clear();
            BaselineBools.Clear();
        }

        private static bool RestoreSharedFields()
        {
            if (OtherRestoreDeferred()) return false;   // 竞争守卫
            bool acted;
            bool clearedAny = RestoreQueues(out acted);
            if (!acted) return false;

            bool ended = false;
            if (clearedAny || PoolTooShort())
            {
                MarkNoTestInProgress();
                ended = true;
            }

            ForgetOwned();
            Log.LogInfo("FRWordList: 已还原共享队列" +
                (ended ? " (残留队列被清空并结束未完成测试)" : "") +
                " -> 其它词书恢复原样");
            return ended;
        }

        private static bool RestoreQueues(out bool acted)
        {
            bool clearedAny = false;
            List<string> listKeys = new List<string>();
            foreach (string k in TouchedListFields) if (!listKeys.Contains(k)) listKeys.Add(k);
            AddMissing(listKeys, LoadStringList(OwnedListKey));
            for (int i = 0; i < listKeys.Count; i++)
            {
                string key = listKeys[i];
                List<string> value;
                if (!BaselineLists.TryGetValue(key, out value) || value == null)
                    value = LoadBaselineListFromDisk(key);
                if (value == null || BaselineBelongsToOwnedBook(value))
                {
                    RestoreList(key, new List<string>());
                    clearedAny = true;
                }
                else if (BaselineFromOtherManagedBook(value))
                {
                    RestoreList(key, new List<string>());
                    clearedAny = true;
                }
                else RestoreList(key, value);
            }

            List<string> arrKeys = new List<string>();
            foreach (string k in TouchedArrayFields) if (!arrKeys.Contains(k)) arrKeys.Add(k);
            AddMissing(arrKeys, LoadStringList(OwnedArrayKey));
            for (int i = 0; i < arrKeys.Count; i++)
            {
                string key = arrKeys[i];
                string[] value;
                if (!BaselineArrays.TryGetValue(key, out value) || value == null)
                    value = LoadBaselineArrayFromDisk(key);
                if (value == null || BaselineBelongsToOwnedBook(value))
                {
                    RestoreArray(key, new string[0]);
                    clearedAny = true;
                }
                else if (BaselineFromOtherManagedBook(value))
                {
                    RestoreArray(key, new string[0]);
                    clearedAny = true;
                }
                else RestoreArray(key, value);
            }

            foreach (string key in TouchedIntFields)
                SetParameterField(key, LoadInt(key, 0));

            List<string> boolKeys = new List<string>();
            foreach (string k in TouchedBoolFields) if (!boolKeys.Contains(k)) boolKeys.Add(k);
            AddMissing(boolKeys, LoadStringList(OwnedBoolKey));
            for (int i = 0; i < boolKeys.Count; i++)
            {
                string key = boolKeys[i];
                bool value;
                if (!BaselineBools.TryGetValue(key, out value) &&
                    !LoadBaselineBoolFromDisk(key, out value)) value = false;
                RestoreBool(key, value);
            }

            acted = listKeys.Count > 0 || arrKeys.Count > 0 ||
                TouchedIntFields.Count > 0 || boolKeys.Count > 0;
            return clearedAny;
        }

        private static void AddMissing(List<string> dest, List<string> src)
        {
            for (int i = 0; i < src.Count; i++)
                if (!dest.Contains(src[i])) dest.Add(src[i]);
        }

        private static bool PoolTooShort()
        {
            List<string> pool = MyParameters.allTestWordsS10_Para;
            return pool == null || pool.Count < 5;
        }

        // ---------------- 跨词书启动守卫 ----------------

        private static void CrossBookGuard()
        {
            if (_crossBookGuardDone) return;
            if (!IsEnabled()) return;
            if (!BookReady()) return;
            _crossBookGuardDone = true;

            if (BookState() == 1) return;

            List<string> ownedLists = LoadStringList(OwnedListKey);
            List<string> ownedArrs = LoadStringList(OwnedArrayKey);
            List<string> ownedBools = LoadStringList(OwnedBoolKey);
            if (ownedLists.Count == 0 && ownedArrs.Count == 0 && ownedBools.Count == 0) return;

            if (OtherRestoreDeferred())
            {
                _crossBookGuardDone = false;   // 下轮 Pre/Post/轮询再试
                return;
            }

            bool ended = RestoreSharedFields();
            Warn("跨词书守卫: 已还原插件接管前的测试队列" +
                 (ended ? " (残留法语队列改为清空并结束本轮测试)" : ""));
        }

        private static void CleanupDisabledState()
        {
            if (_disabledCleanupDone) return;
            if (!BookReady()) return;
            try
            {
                List<string> ownedLists = LoadStringList(OwnedListKey);
                List<string> ownedArrs = LoadStringList(OwnedArrayKey);
                List<string> ownedBools = LoadStringList(OwnedBoolKey);
                if (ownedLists.Count > 0 || ownedArrs.Count > 0 || ownedBools.Count > 0)
                {
                    if (OtherRestoreDeferred())
                    {
                        _disabledCleanupDone = false;   // 窗口关闭后重试
                        return;
                    }
                    RestoreSharedFields();
                }
                _disabledCleanupDone = true;
            }
            catch (Exception e)
            {
                Warn("禁用后还原共享队列失败: " + e.Message);
            }
        }

        private static void RestoreList(string key, List<string> value)
        {
            try
            {
                SetParameterField(key, new List<string>(value));
                ES3.Save(key, new List<string>(value));
            }
            catch (Exception e) { Warn("守卫还原 " + key + " 失败: " + e.Message); }
        }

        private static void RestoreArray(string key, string[] value)
        {
            try
            {
                SetParameterField(key, (string[])value.Clone());
                ES3.Save(key, (string[])value.Clone());
            }
            catch (Exception e) { Warn("守卫还原 " + key + " 失败: " + e.Message); }
        }

        private static void RestoreBool(string key, bool value)
        {
            try
            {
                SetParameterField(key, value);
                ES3.Save(key, value);
            }
            catch (Exception e) { Warn("守卫还原 " + key + " 失败: " + e.Message); }
        }

        private static void MarkNoTestInProgress()
        {
            try
            {
                SetParameterField("S8Progress_Para", 0);
                ES3.Save("S8Progress_Para", 0);
                SetParameterField("testingIf_Para", false);
                ES3.Save("testingIf_Para", false);
                SetParameterField("testingIf_CompleteIf", true);
                ES3.Save("testingIf_CompleteIf", true);
            }
            catch (Exception e) { Warn("清测试状态失败: " + e.Message); }
        }

        private static void SetParameterField(string key, object value)
        {
            FieldInfo field = typeof(MyParameters).GetField(key,
                BindingFlags.Public | BindingFlags.Static);
            if (field != null) field.SetValue(null, value);
            else WarnOnce("restore:" + key, "找不到 MyParameters." + key + "，无法恢复该共享字段");
        }

        private static string Sample(List<string> list)
        {
            System.Text.StringBuilder sb = new System.Text.StringBuilder();
            for (int i = 0; i < list.Count && i < 4; i++)
            {
                if (i > 0) sb.Append(", ");
                sb.Append(list[i]);
            }
            return sb.ToString();
        }

        private static string Sample(string[] arr)
        {
            System.Text.StringBuilder sb = new System.Text.StringBuilder();
            for (int i = 0; i < arr.Length && i < 4; i++)
            {
                if (i > 0) sb.Append(", ");
                sb.Append(arr[i]);
            }
            return sb.ToString();
        }

        private static void LogChange(string key, int count, string sample)
        {
            string sig = count + "|" + sample;
            string prev;
            if (LastSig.TryGetValue(key, out prev) && prev == sig) return;
            LastSig[key] = sig;
            Log.LogInfo("FRWordList: " + key + " -> " + count + " 词 (示例: " + sample + ") @" +
                (ManagedBookSelected() ? BookProfiles.French : "other"));
        }

        internal static bool ManagedBookSelected()
        {
            return BookState() == 1;
        }

        // ---------------- 数据库自愈 (fr_db_payload) ----------------

        private const string DbPackDir = "fr_db_payload";

        // 宿主资源包的语言代码: packs/<PackLangCode>/manifest.json
        private const string PackLangCode = "fr";
        // 探测词必须同时覆盖两种状态:
        //   être — 法语独有词, 只在补丁库里存在 (官方覆盖后消失)
        //   table — 英法同形词, 稳态/英语书 = 英文原版; 法语书 = 法语释义
        private static readonly string[] DbProbes = new string[] { "être", "coing", "vaguement" };
        private const string EnProbeWord = "table";
        private const string EnProbeText = "(n.) 桌子；表格；平地层";
        private static bool _dbHealTried;
        private static float _dbHealAt = -1f;

        private static void TickDbHeal()
        {
            if (_dbHealTried || _healDb == null || !_healDb.Value ||
                _allowLegacySharedDbWrites == null || !_allowLegacySharedDbWrites.Value) return;
            if (BookState() != 1) return;
            if (_dbHealAt < 0f) { _dbHealAt = Time.unscaledTime + 8f; return; }
            if (Time.unscaledTime < _dbHealAt) return;
            string pack = System.IO.Path.Combine(Application.persistentDataPath, DbPackDir);
            if (!System.IO.Directory.Exists(pack))
            {
                // 补丁包缺失: 自愈无从谈起, 但必须放行共享库切换, 否则
                // TickSharedDbSwitch 会永远停在 heal 等待, 本会话内法语
                // 同形词一直显示英文内容。
                _dbHealTried = true;
                _dbSwitchTried = true;
                return;
            }
            string full = System.IO.Path.Combine(Application.streamingAssetsPath, "wcpFullEng.db");
            if (!System.IO.File.Exists(full))
            {
                _dbHealTried = true;
                _dbSwitchTried = true;
                return;
            }
            string only = System.IO.Path.Combine(Application.streamingAssetsPath, "wcpOnlyWord.db");
            if (!System.IO.File.Exists(only))
            {
                // IMPLEMENTATION.md §1.4 的双库契约不能把 OnlyWord 缺失当成已就绪。
                // 先放行状态机，再由共享库切换逻辑按 15s 退避重试。
                _dbHealTried = true;
                _dbSwitchTried = true;
                WarnOnce("dbheal-only-missing", "wcpOnlyWord.db 缺失, 暂不标记自愈完成");
                return;
            }
            _dbHealTried = true;
            try
            {
                System.Threading.Thread t = new System.Threading.Thread(
                    new System.Threading.ThreadStart(delegate
                    {
                        lock (DbWriteLock)
                        {
                            try { RunDbHeal(pack, full, only); }
                            finally { _dbLang = 0; }
                        }
                    }));
                t.IsBackground = true;
                t.Start();
            }
            catch (Exception e)
            {
                _dbSwitchTried = true;
                Warn("例句库自愈启动异常: " + e.Message);
            }
        }

        private static void RunDbHeal(string pack, string full, string only)
        {
            try
            {
                if (!System.IO.File.Exists(full) || !System.IO.File.Exists(only))
                    throw new System.IO.FileNotFoundException("wcpFullEng.db / wcpOnlyWord.db 不完整");
                if (!NeedsDbHeal(full))
                {
                    // 法语独有词都在 = 官方库未被覆盖。同形词当前是英是法
                    // 由 TickSharedDbSwitch 按词书处理, 不属于自愈职责。
                    InfoOnce("dbheal-skip", "法语独有词补丁完整, 不再重灌");
                    _dbSwitchTried = true;
                    return;
                }
                string fullPron = System.IO.Path.Combine(pack, "fr_pron.tsv");
                string fullSent = System.IO.Path.Combine(pack, "fr_sentences.tsv");
                string onlyPron = System.IO.Path.Combine(pack, "fr_only_pron.tsv");
                if (!System.IO.File.Exists(fullPron) || !System.IO.File.Exists(fullSent) ||
                    !System.IO.File.Exists(onlyPron))
                {
                    throw new System.IO.FileNotFoundException("fr_db_payload 不完整");
                }
                string stamp = DateTime.Now.ToString("yyyyMMdd_HHmmss");
                string bakDir = System.IO.Path.Combine(pack, "backup");
                System.IO.Directory.CreateDirectory(bakDir);
                System.IO.File.Copy(full, System.IO.Path.Combine(bakDir, "wcpFullEng.db.bak_" + stamp), true);
                System.IO.File.Copy(only, System.IO.Path.Combine(bakDir, "wcpOnlyWord.db.bak_" + stamp), true);
                int n1 = ApplyDbPack(full, fullPron, fullSent);
                int n2 = ApplyDbPack(only, onlyPron, null);
                if (n1 == 0 || n2 == 0 || NeedsDbHeal(full))
                    throw new InvalidOperationException("补丁回读校验失败");
                _dbSwitchTried = true;
                if (Log != null)
                {
                    Log.LogInfo("FRWordList: 例句库已自动重灌 FullEng.pron+sent=" + n1 +
                                ", OnlyWord.pron=" + n2 + " (官方更新后恢复)");
                }
            }
            catch (Exception e)
            {
                // 自愈失败也要放行共享库切换: 切换自己会探测补丁完整性,
                // 不放行会让整个会话卡死在 heal 等待状态。
                _dbSwitchTried = true;
                Warn("例句库自愈失败(下次启动再试): " + e.Message);
            }
        }

        private static bool NeedsDbHeal(string db)
        {
            using (SqliteConnection con = new SqliteConnection("URI=file:" + db))
            {
                con.Open();
                using (SqliteCommand cmd = con.CreateCommand())
                {
                    for (int i = 0; i < DbProbes.Length; i++)
                    {
                        cmd.CommandText = "SELECT COUNT(*) FROM pron WHERE word = @w";
                        cmd.Parameters.Clear();
                        cmd.Parameters.Add(new SqliteParameter("@w", DbProbes[i]));
                        object o = cmd.ExecuteScalar();
                        if (o == null || Convert.ToInt64(o) == 0) return true;
                    }
                    cmd.CommandText = "SELECT COUNT(*) FROM sentence2 WHERE word = @w";
                    for (int i = 0; i < DbProbes.Length; i++)
                    {
                        cmd.Parameters.Clear();
                        cmd.Parameters.Add(new SqliteParameter("@w", DbProbes[i]));
                        object o = cmd.ExecuteScalar();
                        if (o == null || Convert.ToInt64(o) == 0) return true;
                    }
                }
                con.Close();
            }
            return false;
        }

        private static bool EnglishProbeOk(SqliteConnection con)
        {
            using (SqliteCommand cmd = con.CreateCommand())
            {
                cmd.CommandText = "SELECT meaning FROM pron WHERE word = @w";
                cmd.Parameters.Add(new SqliteParameter("@w", EnProbeWord));
                object o = cmd.ExecuteScalar();
                string m = (o == null) ? null : Convert.ToString(o);
                // 英文原版 meaning 以 "(n.) 桌子..." 开头; 法语补丁以 "桌子〈" 开头
                return m != null && m.StartsWith(EnProbeText, StringComparison.Ordinal);
            }
        }

        private static bool ManagedProbeOk(SqliteConnection con)
        {
            using (SqliteCommand cmd = con.CreateCommand())
            {
                cmd.CommandText = "SELECT COUNT(*) FROM pron WHERE word = @w";
                for (int i = 0; i < DbProbes.Length; i++)
                {
                    cmd.Parameters.Clear();
                    cmd.Parameters.Add(new SqliteParameter("@w", DbProbes[i]));
                    object o = cmd.ExecuteScalar();
                    if (o == null || Convert.ToInt64(o) == 0) return false;
                }
                // 仅凭“英语探针不是英语”会把半写入/损坏库误判为法语态。
                // 法语态必须同时有法语独有词，并且同形探针不能仍是英文释义。
                cmd.CommandText = "SELECT meaning FROM pron WHERE word = @w";
                cmd.Parameters.Clear();
                cmd.Parameters.Add(new SqliteParameter("@w", EnProbeWord));
                object meaning = cmd.ExecuteScalar();
                string text = meaning == null ? null : Convert.ToString(meaning);
                return !string.IsNullOrEmpty(text) &&
                    !text.StartsWith(EnProbeText, StringComparison.Ordinal);
            }
        }

        private static int ApplyDbPack(string db, string pronTsv, string sentTsv)
        {
            if (!System.IO.File.Exists(pronTsv)) return 0;
            string[][] pron = ReadTsv(pronTsv, 4);
            string[][] sent = (sentTsv != null && System.IO.File.Exists(sentTsv))
                ? ReadTsv(sentTsv, 2) : new string[0][];
            int n = 0;
            using (SqliteConnection con = new SqliteConnection("URI=file:" + db))
            {
                con.Open();
                using (SqliteCommand p = con.CreateCommand())
                {
                    p.CommandText = "PRAGMA busy_timeout=30000";
                    p.ExecuteNonQuery();
                }
                using (SqliteTransaction tx = con.BeginTransaction())
                {
                    DeleteRows(con, tx, "pron", pron);
                    if (sent.Length > 0) DeleteRows(con, tx, "sentence2", sent);
                    using (SqliteCommand ins = con.CreateCommand())
                    {
                        ins.Transaction = tx;
                        ins.CommandText =
                            "INSERT INTO pron (word, ukPhonic, usPhonic, meaning) VALUES (@w,@u,@s,@m)";
                        for (int i = 0; i < pron.Length; i++)
                        {
                            ins.Parameters.Clear();
                            ins.Parameters.Add(new SqliteParameter("@w", pron[i][0]));
                            ins.Parameters.Add(new SqliteParameter("@u", pron[i][1]));
                            ins.Parameters.Add(new SqliteParameter("@s", pron[i][2]));
                            ins.Parameters.Add(new SqliteParameter("@m", pron[i][3]));
                            n += ins.ExecuteNonQuery();
                        }
                    }
                    if (sent.Length > 0)
                    {
                        using (SqliteCommand ins2 = con.CreateCommand())
                        {
                            ins2.Transaction = tx;
                            ins2.CommandText = "INSERT INTO sentence2 (word, sentences) VALUES (@w,@s)";
                            for (int i = 0; i < sent.Length; i++)
                            {
                                ins2.Parameters.Clear();
                                ins2.Parameters.Add(new SqliteParameter("@w", sent[i][0]));
                                ins2.Parameters.Add(new SqliteParameter("@s", sent[i][1]));
                                ins2.ExecuteNonQuery();
                            }
                        }
                    }
                    tx.Commit();
                }
                con.Close();
            }
            return n;
        }

        // ---------------- 共享库 book-scoped 切换 ----------------

        // 稳态共享库 = 英文原版 + 法语独有词补丁 (同形词保持英文)。
        // 法语书选中时, 1638 个同形词切成法语释义/例句; 离开时切回英文。
        private static readonly object DbWriteLock = new object();
        private static volatile int _dbLang = 0;      // 0=unknown, 1=fr, 2=en
        private static volatile bool _dbSwitchTried;
        private static volatile bool _dbSwitchBusy;
        private static bool _frPatchProbed;
        private static bool _frPatchOk;
        // 切换线程异常后的退避截止时间 (UtcNow.Ticks); 避免数据库被游戏
        // 短暂占用时每秒重试刷日志。
        private static long _dbSwitchFailUntilTicks;

        private static void TickSharedDbSwitch()
        {
            if (_allowLegacySharedDbWrites == null || !_allowLegacySharedDbWrites.Value) return;
            if (!IsEnabled()) return;
            if (!BookReady()) return;   // 未读档前不动共享库 (默认值态不可信)
            if (_dbSwitchBusy) return;
            if (DateTime.UtcNow.Ticks < _dbSwitchFailUntilTicks) return;
            int state = BookState();
            if (state != 1 && CurrentManagedLanguage() == BookProfiles.German)
                return; // 德语插件拥有共享库时，法语侧保持只读
            if (state != 1 && CurrentManagedLanguage() == BookProfiles.Russian)
                return; // 俄语插件拥有共享库时，法语侧保持只读
            int want = (state == 1) ? 1 : 2;
            if (_dbLang == want) return;
            if (want == 1 && !_dbSwitchTried)
            {
                // 自愈开启时等 TickDbHeal 先跑 (它完成后置 _dbSwitchTried);
                // 自愈关闭时自己探测一次法语独有词补丁是否完整。
                if (_healDb != null && _healDb.Value) return;
                if (!_frPatchProbed)
                {
                    _frPatchProbed = true;
                    string full0 = System.IO.Path.Combine(
                        Application.streamingAssetsPath, "wcpFullEng.db");
                    _frPatchOk = System.IO.File.Exists(full0) &&
                        !NeedsDbHeal(full0);
                }
                if (!_frPatchOk)
                {
                    WarnOnce("switch-nopatch",
                        "法语补丁不完整且 HealExampleDatabase 已关闭, 共享库保持英语态");
                    return;
                }
                _dbSwitchTried = true;
            }
            _dbSwitchBusy = true;
            string pack = System.IO.Path.Combine(Application.persistentDataPath, DbPackDir);
            string full = System.IO.Path.Combine(Application.streamingAssetsPath, "wcpFullEng.db");
            string only = System.IO.Path.Combine(Application.streamingAssetsPath, "wcpOnlyWord.db");
            System.Threading.Thread t = new System.Threading.Thread(new System.Threading.ThreadStart(delegate
            {
                try { lock (DbWriteLock) { SwitchSharedDb(pack, full, only, want); } }
                catch (Exception e)
                {
                    _dbSwitchFailUntilTicks =
                        DateTime.UtcNow.Ticks + 15 * TimeSpan.TicksPerSecond;
                    Warn("共享库切换异常(15s 后重试): " + e.Message);
                }
                finally { _dbSwitchBusy = false; }
            }));
            t.IsBackground = true;
            t.Start();
        }

        private static void SwitchSharedDb(string pack, string full, string only, int want)
        {
            string enPron = System.IO.Path.Combine(pack, "en_pron.tsv");
            string enSent = System.IO.Path.Combine(pack, "en_sentences.tsv");
            if (!System.IO.File.Exists(full) || !System.IO.File.Exists(only))
            {
                _dbSwitchFailUntilTicks =
                    DateTime.UtcNow.Ticks + 15 * TimeSpan.TicksPerSecond;
                WarnOnce("switch-db-missing",
                    "共享库切换需要 wcpFullEng.db 与 wcpOnlyWord.db, 缺失时 15s 后重试");
                return;
            }
            // 先确认当前状态, 避免无谓写入 (稳态即目标态时跳过)
            bool enOkFull;
            bool probeOkFull;
            using (SqliteConnection con = new SqliteConnection("URI=file:" + full))
            {
                con.Open();
                enOkFull = EnglishProbeOk(con);
                probeOkFull = ManagedProbeOk(con);
                con.Close();
            }
            bool enOkOnly;
            bool probeOkOnly;
            using (SqliteConnection con = new SqliteConnection("URI=file:" + only))
            {
                con.Open();
                enOkOnly = EnglishProbeOk(con);
                probeOkOnly = ManagedProbeOk(con);
                con.Close();
            }
            // 法语态 = 两个库的同形词都是法语 (英文探针都不过);
            // 英语态 = 两个库都是英文原版 (探针都过)
            bool alreadyOk = (want == 2)
                ? (enOkFull && enOkOnly)
                : (probeOkFull && probeOkOnly);
            if (alreadyOk)
            {
                _dbLang = want;
                if (Log != null)
                    Log.LogInfo("FRWordList: 共享库已是" + (want == 1 ? "法语" : "英语") + "态, 无需切换");
                return;
            }
            if (want == 1)
            {
                // 英语 -> 法语: 同形词切成法语。法语 TSV 由 export_fr_db_payload.py
                // 从仓库数据确定性生成 (fr_pron/fr_sentences/fr_only_pron 已含同形词)。
                string frPron = System.IO.Path.Combine(pack, "fr_pron.tsv");
                string frSent = System.IO.Path.Combine(pack, "fr_sentences.tsv");
                string frOnly = System.IO.Path.Combine(pack, "fr_only_pron.tsv");
                if (!System.IO.File.Exists(frPron) || !System.IO.File.Exists(frSent) ||
                    !System.IO.File.Exists(frOnly))
                {
                    _dbSwitchFailUntilTicks =
                        DateTime.UtcNow.Ticks + 60 * TimeSpan.TicksPerSecond;
                    WarnOnce("switch-fr-missing",
                        "共享库切换(法语)缺少 fr_*.tsv, 60s 后重试");
                    return;
                }
                int n1 = ApplyDbPack(full, frPron, frSent);
                int n2 = ApplyDbPack(only, frOnly, null);
                _dbLang = 1;
                if (Log != null)
                    Log.LogInfo("FRWordList: 共享库 -> 法语 (FullEng=" + n1 + ", OnlyWord=" + n2 + ")");
            }
            else
            {
                // 法语 -> 英语: 同形词恢复英文原版
                if (!System.IO.File.Exists(enPron) || !System.IO.File.Exists(enSent))
                {
                    _dbSwitchFailUntilTicks =
                        DateTime.UtcNow.Ticks + 60 * TimeSpan.TicksPerSecond;
                    WarnOnce("switch-en-missing",
                        "共享库切换(英语)缺少 en_*.tsv, 60s 后重试");
                    return;
                }
                int n1 = ApplyDbPack(full, enPron, enSent);
                int n2 = ApplyDbPack(only, enPron, null);
                CleanupOrphanSentences(full, enSent);
                _dbLang = 2;
                if (Log != null)
                    Log.LogInfo("FRWordList: 共享库 -> 英语 (FullEng=" + n1 + ", OnlyWord=" + n2 + ")");
            }
        }

        // 英文基线没有例句的同形词 (如 max/pin/respecter/sable) 在切法语时
        // 被灌入了法语例句, en_sentences.tsv 不含它们, ApplyDbPack 的 DELETE
        // 覆盖不到 — 切回英语态时需要显式删除。但差集必须先与同形词集合
        // (en_pron.tsv 词集) 求交: 法语独有词 (être/coing/…) 的例句是共享库
        // 稳态 (英文原版 + 法语独有词补丁) 的一部分, 绝不能删。差集是静态
        // 数据, 只算一次。
        private static HashSet<string> _orphanSentWords;

        private static void CleanupOrphanSentences(string full, string enSentPath)
        {
            string packFrSent = System.IO.Path.Combine(
                System.IO.Path.GetDirectoryName(enSentPath), "fr_sentences.tsv");
            if (_orphanSentWords == null)
            {
                _orphanSentWords = new HashSet<string>();
                if (!System.IO.File.Exists(enSentPath) ||
                    !System.IO.File.Exists(packFrSent))
                    return;
                string enPronPath = System.IO.Path.Combine(
                    System.IO.Path.GetDirectoryName(enSentPath), "en_pron.tsv");
                if (!System.IO.File.Exists(enPronPath))
                {
                    // 无法判定同形词集合时宁可少删 (残留少量同形词法语例句),
                    // 也绝不能把 6478 个法语独有词的稳态例句误删。
                    WarnOnce("orphan-nopron",
                        "en_pron.tsv 缺失, 跳过孤儿例句清理");
                    return;
                }
                HashSet<string> enCovered = new HashSet<string>();
                string[][] enRows = ReadTsv(enSentPath, 2);
                for (int i = 0; i < enRows.Length; i++)
                    enCovered.Add(enRows[i][0]);
                HashSet<string> overlap = new HashSet<string>();
                string[][] pronRows = ReadTsv(enPronPath, 4);
                for (int i = 0; i < pronRows.Length; i++)
                    overlap.Add(pronRows[i][0]);
                string[][] frRows = ReadTsv(packFrSent, 2);
                for (int i = 0; i < frRows.Length; i++)
                {
                    string w = frRows[i][0];
                    if (w == null || w.Length == 0 || enCovered.Contains(w))
                        continue;
                    if (!overlap.Contains(w))
                        continue;   // 法语独有词: 例句属于稳态, 保留
                    _orphanSentWords.Add(w);
                }
            }
            if (_orphanSentWords.Count == 0) return;
            List<string[]> rows = new List<string[]>(_orphanSentWords.Count);
            foreach (string w in _orphanSentWords)
                rows.Add(new string[] { w });
            using (SqliteConnection con = new SqliteConnection("URI=file:" + full))
            {
                con.Open();
                using (SqliteTransaction tx = con.BeginTransaction())
                {
                    DeleteRows(con, tx, "sentence2", rows.ToArray());
                    tx.Commit();
                }
                con.Close();
            }
        }

        private static void DeleteRows(SqliteConnection con, SqliteTransaction tx,
            string table, string[][] rows)
        {
            if (rows.Length == 0) return;
            List<string> wl = new List<string>();
            HashSet<string> seen = new HashSet<string>();
            for (int i = 0; i < rows.Length; i++)
            {
                string w = rows[i][0];
                if (w != null && w.Length > 0 && seen.Add(w)) wl.Add(w);
            }
            for (int i = 0; i < wl.Count; i += 400)
            {
                int end = Math.Min(i + 400, wl.Count);
                System.Text.StringBuilder sb = new System.Text.StringBuilder();
                sb.Append("DELETE FROM ").Append(table).Append(" WHERE word IN (");
                using (SqliteCommand cmd = con.CreateCommand())
                {
                    cmd.Transaction = tx;
                    for (int j = i; j < end; j++)
                    {
                        if (j > i) sb.Append(',');
                        string pn = "@p" + (j - i);
                        sb.Append(pn);
                        cmd.Parameters.Add(new SqliteParameter(pn, wl[j]));
                    }
                    sb.Append(')');
                    cmd.CommandText = sb.ToString();
                    cmd.ExecuteNonQuery();
                }
            }
        }

        private static string[][] ReadTsv(string path, int cols)
        {
            string[] lines = System.IO.File.ReadAllLines(path, System.Text.Encoding.UTF8);
            List<string[]> rows = new List<string[]>(lines.Length);
            for (int i = 0; i < lines.Length; i++)
            {
                if (lines[i].Length == 0) continue;
                string[] parts = lines[i].Split('\t');
                string[] vals = new string[cols];
                for (int c = 0; c < cols; c++)
                    vals[c] = (c < parts.Length) ? Unescape(parts[c]) : "";
                rows.Add(vals);
            }
            return rows.ToArray();
        }

        private static string Unescape(string s)
        {
            if (s == null || s.IndexOf('\\') < 0) return s;
            System.Text.StringBuilder sb = new System.Text.StringBuilder(s.Length);
            for (int i = 0; i < s.Length; i++)
            {
                char c = s[i];
                if (c == '\\' && i + 1 < s.Length)
                {
                    char x = s[i + 1];
                    if (x == 'n') { sb.Append('\n'); i++; continue; }
                    if (x == 't') { sb.Append('\t'); i++; continue; }
                    if (x == '\\') { sb.Append('\\'); i++; continue; }
                }
                sb.Append(c);
            }
            return sb.ToString();
        }

        private static bool IsEnabled()
        {
            return Instance != null && _enabled != null && _enabled.Value;
        }

        private static void Warn(string s)
        {
            if (Log != null) Log.LogWarning("FRWordList: " + s);
        }

        private static void WarnOnce(string key, string s)
        {
            if (!Warned.Add(key)) return;
            Warn(s);
        }

        private static void InfoOnce(string key, string s)
        {
            if (!Warned.Add("info:" + key)) return;
            if (Log != null) Log.LogInfo("FRWordList: " + s);
        }
    }
}
