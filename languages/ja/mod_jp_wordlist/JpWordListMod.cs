// WCP JP Word List — BepInEx 5 插件 (C# 5 语法)  v1.7.6
//
// 目的:
//   A) 日语词书(游戏里就是 自定义词书一~四)与其它词书彻底互不干扰。
//   B) 日语词书下: 题目给假名读音, 选项给「汉字写法 + 中文释义」。
//   C) 词表绝不回写成空表/过短表 —— 这是 v1.2.0 的恶性 bug:
//        已学词测试(MultipleChoiceGeneratorS9)取 allTestWordsS10_Para[S8Progress_Para],
//        词表被剔空后第一时间 ArgumentOutOfRangeException 崩溃; 空表还被写回 ES3 存档,
//        每次启动重写一遍, 游戏无法自愈。
//   D) 自选测试(自由选择)的选词界面(截图里那份「已学词汇」)渲染 MyParameters.S9CurrentArray_Para,
//      勾选写 S9extraStudy_Para; 开始测试 = ChooseWordManager.ResetTestListQuick_FreeChoose
//      把 allTestWordsS10_Para 设成 S9extraStudy_Para。所以这两张表也必须只含本书词,
//      否则用户只能从一串英语词里选, 测试里也还是英语。
//   E) 已学词测试与自选测试都跑 MultipleChoiceGeneratorS9: 题目取 allTestWordsS10_Para[progress],
//      题干取 S8needToLearnWordList_Para[0]。两者错位会答非所问, 越界会直接崩; 每次进入前都要摆正。
//   F) 读档之前 MyParameters 全是编译期默认值(默认书「四级大纲词汇」), 那时按内存剔词并写回 ES3
//      会把存档写坏(实测: 默认的 69313 词全词表被当成"别的词书"筛过一遍写回存档)。
//      所以 BookState() 先用存档里的词书名和内存对比, 确认读过档才动手。
//   G) 「已学词测试 → 快速测试」不是只换词池:
//      · 游戏 clickChangeImageSource.StartQuickTest 用**全局**已学词典(别的词书学过的英语词也在里面)
//        按等级筛选 + lastStudyTime 倒序重采样 allTestWordsS10_Para = TestWordsNum_Para 个。
//      · 题面显示的词却是 SetInputFieldValueS8.ShowTheWord 里的 S8needToLearnWordList_Para[0],
//        而这张队列 StartQuickTest 完全不碰, 还是上一轮遗留的内容。
//      两张表不同源 → 题面出现「superiority + 猪肉/全部/停/破碎」这种英语题干配日语选项, 谁都不可能答对。
//      所以: 词池一换, 题干队列/剩余/进度必须一起换(SetTestLists / SyncStemQueue), 且要在游戏读 need[0] 之前。
//   H) 假名题干 / 汉字选项原先依赖 MyParameters.SelfBookMeaningDictionary, 而这张表只有
//      SelfBookMeaningConnectIf 为真时游戏才从 MyBook.es3 载入(GetSelfBookMeaningAfterSet/SelfBookDictionaryGet)。
//      实测该开关是 false(存档里没这个键), 日志里也没有「【自定义书籍字典加载】」, 于是内存字典是空的,
//      KanaOf/KanjiOption 全部返回 null → 题干照旧显示汉字, 选项照旧带【假名】, 功能等于没生效。
//      现在释义来源改成三级: 游戏内存字典 → 自己读 MyBook.es3 的 wordDictionaryN → 出题时顺手攒下的词条;
//      而且题干读音优先直接从**游戏已经渲染出来的选项释义**(它就是「【假名】释义」)里取, 不依赖那张字典。
//   I) 作用域按「词书身份」而不是按槽位或语言判断: 内存词表和 MyBook.es3 槽位词表都必须
//      匹配猫条版的完整 SHA-256 指纹，且是同一册，才会写队列/改题面。其它任何词书即使也是
//      日语，也一律不写；两份记录不一致(通常正在换书)也一律不写。
//   J) 可移植性: 指纹和语言策略是独立 BookProfile。导入到一至四任意槽都能匹配；未来增加
//      法语/俄语词书只需增加 Profile 和对应策略，不会令日语插件接管它们。
//   K) 跨词书启动守卫 (v1.7.2): 状态只在受管日语词书内落盘, 所以「在日语词书里关掉游戏,
//      之后用别的词书继续那个未完成测试」会读到日语队列。插件落盘时同时记下
//      「接管了哪些字段」和「接管前的原值」(自己的 JpWL_* 键), 启动时若当前不是本词书,
//      就把队列还原; 原值不可用(读不到 / 本身就是日语)时清空队列并把本轮测试标记为已完成
//      —— 绝不能留少于 5 个词的词池给 game 的 GenerateOptions, 那会越界崩。
//      v1.7.3 补两条同类漏点: ① 游戏内切书也走同一套「接管记录」还原 —— 只靠本次会话的
//      内存标记会漏掉「重启后仍停在日语词书, 再在游戏内切到别的词书」这条路(该进程可能
//      一次都没写过, 存档里却还留着上一次的日语队列); ② 基线读不到时 ES3 会返回空表,
//      之前会被当成「可用基线」静默回填, 于是空词池配一个未完成的测试留给别的词书 ->
//      点「继续」时 GenerateOptions 越界崩。现在统一按「清空过 or 还原后词池 < 5」结束本轮。
//   M) 周边修正 (v1.7.4): ① 查词面板(DatabaseManagerS8 / S8checkWordMeaning /
//      ButtonTextTransfer.OnSearchButtonClick)只查英语库, 日语词会显示「本地暂未收录」
//      且音标行为空 —— 受管词书下改用本书释义, 音标位填假名读音;
//      ② 本地单词音频按「汉字形」命名(全部.mp3), 而题干已改成假名(ぜんぶ), 点喇叭会查
//      <假名>.mp3 落空并回退 AI —— 发音时临时换回汉字形取音, 播完立即还原;
//      ③ 重建/重采样测试词池时按面板上的「正序/倒序/随机 + 未测词优先」排序, 与游戏的
//      ChooseWordManager.TestWordPos/Neg/Ran(含 Off) 一致, 免得重修过的词池顺序与设置不符。
//      v1.7.5: 上面②覆盖到所有小游戏 —— 实测 VocabularyAudioPlayer 出现在
//      Scene7_Fight / Scene8_Review / Scene9_ChooseWords / Scene13_FruitInjaChoosing /
//      Scene15_Bat / Scene16_FreeReview / Scene17_SpellingGame 等每个显示单词的场景,
//      所以「发音前把假名换回汉字形」一处即可覆盖战斗机/水果/拼写等全部小游戏;
//      再加一道兜底(当前题目的假名读音 -> 当前题目的词)与一行诊断日志便于核对。
//   L) 版本兼容: ① 题库/题干/选项/发音/查词面板这些核心功能从不碰游戏数据库
//      (wcpOnlyWord.db / wcpFullEng.db) —— 全靠内存反射 + 自己存的字符串键, 只读游戏
//      已在用的 ES3 存档; ② 新增逻辑对 MyParameters 一律走反射 (SetParameterField / GetField),
//      字段改名或消失时只记一条日志, 不抛异常; ③ 自己存的数据只用字符串键, 不依赖任何
//      游戏内部类型。所以游戏更新后最坏是「本插件这部分失效并记日志」, 不会崩、不会写坏存档。
//   N) 例句库自愈 (v1.7.6): 官方更新会覆盖 StreamingAssets 下的 .db, 把日文词条的
//      释义(pron)与例句(sentence2)冲掉。词书本体在 LocalLow\WCP\wcp\MyBook.es3 (用户数据,
//      不在安装目录), 更新不会动它, 所以插件照常工作, 唯一会丢的是「例句/查词释义」。
//      补丁包已导出到 LocalLow\WCP\wcp\jp_db_payload (更新同样不碰), 插件启动后空闲时
//      若探针词缺失, 就用它重灌一次: 写前把 .db 备份到 jp_db_payload\backup, 幂等,
//      全程 try/catch, 失败只记日志(下次启动再试)。这是唯一一处会写游戏数据库的代码,
//      默认开启 (配置 HealExampleDatabase), 可关; 后台线程执行, 不卡主线程。
//
// 逆向依据 (Assembly-CSharp, 2026-09-12):
//   · 战斗/复习四选一 = MultipleChoiceGenerator: 题干 = testWordText,
//     选项 = option1..4Text = GetMeaning_S7(词); 判对用 wordXText.text(汉字形),
//     另一条判对分支比较 optionText 之间的文本 —— 所以改写题干与选项显示文本是安全的,
//     但绝不能动 wordXText / matchingWordText。
//   · 已学词测试(S9) = MultipleChoiceGeneratorS9 + SetInputFieldValueS8:
//     题干 = 输入框文本, 选项 = GetMeaning_S7(词), 判对用 rightOption_S9 索引。
//     v1.7.1 补充(真因): 题干取 need[0] (ShowTheWord 里 ES3.Load), 选项取
//     allTestWordsS10_Para[progress] (GenerateOptions). 插件此前只改内存、从不落盘,
//     而游戏在这两处都会**从 ES3 重新读一遍**。于是「插件已改正的内存值」被存档里
//     残留的旧队列顶掉: 选项是新算的日语词, 题干却是存档里上一轮(英语书)留下的
//     superiority —— 就是截图里那个英语题干配日语选项的错题。
//     修法: ① 插件写队列时同步 ES3.Save, 并记下改动前的存档基线用于换书回填
//     (SaveField / RestoreSharedFields); ② HealTestList 增加「词池必须全在本书内」
//     的校验 —— 旧逻辑只看 need 与词池是否错位, 而坏存档里两者「自洽地」都是英语,
//     永远诊断不出来, 于是坏存档不会自愈。
//   · 选词界面(截图里那份「已学词汇」)= PageController 渲染 MyParameters.S9CurrentArray_Para,
//     勾选写入 S9extraStudy_Para(string[])。
//   · 词书释义字典 MyParameters.SelfBookMeaningDictionary: 汉字词 = 「【假名】中文〈词性〉」,
//     假名词 = 「中文」。这是本书自有释义, 与游戏本地库无关。
//   · 硬性规模要求: S9 需要 allTestWordsS10_Para.Count >= 5, 战斗需要 S7TestWordList_Para >= 4。
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
using WcpBookProfiles;

namespace JpWordList
{
    [BepInPlugin("dev.hanserdesu.jpwordlist", "WCP JP Word List", "1.7.7")]
    public class JpWordListPlugin : BaseUnityPlugin
    {
        internal const string ReviewRangeType = "复习范围词";

        internal static ManualLogSource Log;
        internal static JpWordListPlugin Instance;

        private static ConfigEntry<bool> _enabled;
        private static ConfigEntry<bool> _topUp;
        private static ConfigEntry<bool> _guardOtherLists;
        private static ConfigEntry<bool> _kanaStem;
        private static ConfigEntry<bool> _healDb;
        private static ConfigEntry<bool> _allowLegacySharedDbWrites;
        private static ConfigEntry<bool> _yieldToHost;
        private static readonly HashSet<string> Warned = new HashSet<string>();
        private static readonly Dictionary<string, string> LastSig = new Dictionary<string, string>();

        // 存档里的词书名缓存(判断游戏是否已经读档)
        private static string _diskBook;
        private static float _diskBookAt = -1E9f;

        // 本书释义字典(MyBook.es3 wordDictionaryN)缓存 + 出题时攒下的词条缓存
        private static Dictionary<string, string> _bookDict;
        private static int _bookDictIdx = -1;
        private static readonly Dictionary<string, string> Harvested = new Dictionary<string, string>();

        // 当前内存词表与各槽词表的身份缓存；完整指纹比语言采样更严格。
        private const float SlotProfileTtl = 5f;
        private static int _slotProfileIdx = -1;
        private static float _slotProfileAt = -1E9f;
        private static BookProfile _slotProfile;
        private static List<string> _memoryProfileList;
        private static int _memoryProfileCount = -1;
        private static string _memoryProfileBookName;
        private static BookProfile _memoryProfile;
        private static string _stateMem = "<none>";   // 本次判定信号，仅供日志
        private static string _stateSlot = "<none>";

        // 插件只临时接管已登记词书的共享队列: 改写时同步落盘(否则游戏的 ES3.Load 会顶掉内存值),
        // 同时记下接管前的基线, 离开词书(或是在别的词书里启动)时再还原, 避免残留影响其它词书。
        private static readonly HashSet<string> TouchedListFields = new HashSet<string>();
        private static readonly HashSet<string> TouchedArrayFields = new HashSet<string>();
        private static readonly HashSet<string> TouchedIntFields = new HashSet<string>();

        // 插件动过的存档键, 改动前的原始值。落盘会让游戏的 ES3.Load 读到插件值,
        // 所以换书时不能再靠「从存档重读」回填 —— 必须用这里记下的基线。
        private static readonly Dictionary<string, List<string>> BaselineLists =
            new Dictionary<string, List<string>>();
        private static readonly Dictionary<string, string[]> BaselineArrays =
            new Dictionary<string, string[]>();

        // 插件自有的存档键(不用游戏字段名, 也不碰游戏数据库):
        //   JpWL_owned_lists / JpWL_owned_arrays = 当前被插件接管并已落盘的共享字段名
        //   JpWL_bak_<字段>                      = 该字段被接管前的原始值
        // 只靠 ES3 的字符串键读写, 不引用任何游戏内部类型, 游戏改版也不会因此失效。
        private const string OwnedListKey = "JpWL_owned_lists";
        private const string OwnedArrayKey = "JpWL_owned_arrays";
        private const string BakPrefix = "JpWL_bak_";
        // 接管队列来自哪一个自定义槽。离开本书时只清掉能证明属于这个完整
        // 词书的旧基线，绝不能因为“含日文”就误伤用户的另一本日语词书。
        private const string OwnedSourceSlotKey = "JpWL_owned_source_slot";

        // 跨词书启动守卫: 每次进游戏只做一次
        private static bool _crossBookGuardDone;
        // Enabled 配置可在游戏中修改。关闭后仍需撤销此前由插件落盘的共享队列，
        // 否则切到其它词书的那个瞬间可能读到日语残留。
        private static bool _disabledCleanupDone;
        // 其它受管语言词书正在激活时暂缓还原 (跨插件写序竞争守卫)。
        // 根因: 切到另一本受管词书的瞬间, 对方插件可能已经重建了共享队列;
        // 本插件随后的切书还原会把旧基线盖回去 (RU->JP 串词的直接来源)。
        private static bool _deferredRestoreLogged;

        // 发音修正: 本地单词音频按「汉字形」命名(全部.mp3/歯医者.mp3), 而题干会被改写成假名
        // (ぜんぶ/しかいしゃ)。VocabularyAudioPlayer 用的是 text1.text, 查 <假名>.mp3 必然落空
        // 并回退 AI。这里维护 假名 -> 汉字形 的映射, 发音前临时换回原词。
        private static readonly Dictionary<string, string> KanaToSurface = new Dictionary<string, string>();
        private static int _kanaMapIdx = -1;
        private static bool _audioSwapped;
        private static string _audioOriginal;

        // 换行 / 释义里转义过的换行 (游戏写的是两个反斜杠加 n)
        private static readonly string NL = ((char)10).ToString();
        private static readonly string ESC_NL = new string(new char[] { (char)92, (char)92, 'n' });

        private float _nextPoll;

        // 场景加载时先把词表摆正, 再让游戏去读 (prefix)
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
            "GetNewWord", "InvokeRandomButton", "Randomize", "StartQuickTest"
        };

        private static readonly string[] SceneMethods = new string[] { "Awake", "Start" };

        void Awake()
        {
            Log = Logger;
            Instance = this;
            _enabled = Config.Bind("General", "Enabled", true,
                "开启词表校正: 日语词书只出日语词, 其它词书不出日语词。");
            _topUp = Config.Bind("General", "TopUpFromWholeBook", false,
                "日语词书: 战斗词表不足时, 是否用本书其它(未学)词补满到复习范围词上限。");
            _guardOtherLists = Config.Bind("General", "GuardSharedLists", true,
                "同时校正 每日/额外 学习复习表、已学词测试表与选词列表, 挡住全局已学词典的跨词书串词。");
            _kanaStem = Config.Bind("General", "KanaQuestionStem", true,
                "日语词书: 四选一题目显示假名读音, 选项显示「汉字写法 + 中文释义」。");
            _healDb = Config.Bind("General", "HealExampleDatabase", true,
                "旧版兼容开关；只有同时启用 Legacy/AllowSharedDatabaseWrites 才会生效。");
            _allowLegacySharedDbWrites = Config.Bind("Legacy", "AllowSharedDatabaseWrites", false,
                "允许旧版日语插件写入游戏共享 wcpFullEng.db/wcpOnlyWord.db。默认关闭以保持语言资源隔离。");
            _yieldToHost = Config.Bind("Legacy", "YieldToHost", true,
                "宿主 WcpHost 接管本语言后, 旧词表插件自动让位(只保留语言资源)。设 false 强制以旧模式运行。");
            if (HostTakesOver())
            {
                Log.LogWarning("JPWordList: WcpHost 已接管日语, 旧词表插件不再打补丁 (Legacy/YieldToHost=false 可强制旧模式)。");
                return;
            }
            PatchAll();
        }

        // ---------------- 打补丁 ----------------

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
                Log.LogWarning("ja JPWordList: 宿主接管判定失败, 按旧模式继续打补丁: " + e.Message);
                return false;
            }
        }
        private void PatchAll()
        {
            Harmony harmony = new Harmony("dev.hanserdesu.jpwordlist");
            MethodInfo pre = AccessTools.Method(typeof(JpWordListPlugin), "Pre");
            MethodInfo post = AccessTools.Method(typeof(JpWordListPlugin), "Post");
            MethodInfo postRef = AccessTools.Method(typeof(JpWordListPlugin), "PostRef");
            MethodInfo postBook = AccessTools.Method(typeof(JpWordListPlugin), "PostBookChange");
            MethodInfo postS8 = AccessTools.Method(typeof(JpWordListPlugin), "PostSetAsLearnedTest");
            MethodInfo preS9 = AccessTools.Method(typeof(JpWordListPlugin), "PreMcGenS9");

            int preCount = PatchSet(harmony, SceneTypes, SceneMethods, pre);
            int postCount = PatchSet(harmony, PostTypes, PostMethods, post);

            int refCount = PatchOne(harmony, "ChooseWordManager", "AddWordsToSelfChosenList", postRef);
            int bookCount = PatchOne(harmony, "WordChooseButtonS10", "MakeCertainChange", postBook);
            int healCount = PatchOne(harmony, "SetS8Data", "SetAsLearnedTest", postS8);
            int s9Count = PatchPre(harmony, "MultipleChoiceGeneratorS9", "Start", preS9);
            s9Count += PatchPre(harmony, "MultipleChoiceGeneratorS9", "GenerateOptions", preS9);

            // 选词界面(截图里那份「已学词汇」)渲染前 / 词组重建后立刻摆正候选表
            MethodInfo preSel = AccessTools.Method(typeof(JpWordListPlugin), "PreFixSelection");
            MethodInfo postSel = AccessTools.Method(typeof(JpWordListPlugin), "PostFixSelection");
            int selCount = 0;
            selCount += PatchPre(harmony, "PageController", "SetThis", preSel);
            selCount += PatchOne(harmony, "GoToAllS9", "ArrayToAll", postSel);
            selCount += PatchOne(harmony, "SwitchCurrentArrayS9", "SwitchThis", postSel);

            int stemCount = 0;
            stemCount += PatchOne(harmony, "MultipleChoiceGenerator", "GenerateOptions",
                AccessTools.Method(typeof(JpWordListPlugin), "PostMcGen"));
            stemCount += PatchOne(harmony, "MultipleChoiceGeneratorS9", "GenerateOptions",
                AccessTools.Method(typeof(JpWordListPlugin), "PostMcGenS9"));
            stemCount += PatchOne(harmony, "SetInputFieldValueS8", "ShowTheWord",
                AccessTools.Method(typeof(JpWordListPlugin), "PostShowTheWord"));
            // 题面取 need[0], 必须在游戏读它之前把这些表对齐
            stemCount += PatchPre(harmony, "SetInputFieldValueS8", "ShowTheWord",
                AccessTools.Method(typeof(JpWordListPlugin), "PreShowTheWord"));
            // 「快速测试」按钮: 游戏刚用全局已学词典重建了词池, 立刻按本书重采样并同步题干队列
            stemCount += PatchOne(harmony, "clickChangeImageSource", "StartQuickTest",
                AccessTools.Method(typeof(JpWordListPlugin), "PostStartQuickTest"));

            // 查词面板: 日语词在英语词库里查不到 -> 用本书释义 / 假名读音补上
            int dictCount = 0;
            dictCount += PatchOne(harmony, "DatabaseManagerS8", "OnSearchButtonClick",
                AccessTools.Method(typeof(JpWordListPlugin), "PostSearchDictS8"));
            dictCount += PatchOne(harmony, "S8checkWordMeaning", "OnSearchButtonClick",
                AccessTools.Method(typeof(JpWordListPlugin), "PostSearchDictCheck"));
            dictCount += PatchOne(harmony, "ButtonTextTransfer", "OnSearchButtonClick",
                AccessTools.Method(typeof(JpWordListPlugin), "PostSearchDictTransfer"));
            // 原界面把两套英语音标硬拼成「美音 , 英音」。日语只有一个读音，
            // 因此会留下孤立的逗号；在答案区重新按非空读音显示。
            MethodInfo postPhonetic = AccessTools.Method(typeof(JpWordListPlugin), "PostAnswerPhonetic");
            int answerCount = 0;
            answerCount += PatchOne(harmony, "showTheAnswerS8", "ShowAnswer", postPhonetic);
            answerCount += PatchOne(harmony, "showTheAnswerS8", "ShowAnswerForStudy", postPhonetic);
            answerCount += PatchOne(harmony, "showTheAnswerS8", "ShowAnswerNoAutoVoice", postPhonetic);

            // SetInputFieldValueS8 的新版重选流程只更新存档，漏了刷新下一词/结束页。
            // 剩余 0 时点击「认识该词」便会看似毫无反应。
            int classifyCount = PatchOne(harmony, "SetInputFieldValueS8", "changeKnownFuzzUnknownTimes",
                AccessTools.Method(typeof(JpWordListPlugin), "PostS8Classification"));
            // 发音: 题干改成假名后, 本地音频(按汉字形命名)会查不到, 发音前换回原词再查
            int audioCount = PatchPre(harmony, "VocabularyAudioPlayer", "PlayWordAudio",
                AccessTools.Method(typeof(JpWordListPlugin), "PrePlayWordAudio"));
            audioCount += PatchOne(harmony, "VocabularyAudioPlayer", "PlayWordAudio",
                AccessTools.Method(typeof(JpWordListPlugin), "PostPlayWordAudio"));

            Log.LogInfo("JPWordList: 补丁完成 scene=" + preCount + " post=" + postCount +
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
                    WarnOnce("type:" + typeNames[i], "找不到类型 " + typeNames[i]);
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
            {
                if (names[i] == name) return true;
            }
            return false;
        }

        private static int PatchOne(Harmony harmony, string typeName, string methodName, MethodInfo patch)
        {
            Type t = AccessTools.TypeByName(typeName);
            if (t == null) { WarnOnce("type:" + typeName, "找不到类型 " + typeName); return 0; }
            MethodInfo m = AccessTools.Method(t, methodName);
            if (m == null) { WarnOnce("method:" + typeName + "." + methodName, "找不到方法 " + typeName + "." + methodName); return 0; }
            try { harmony.Patch(m, null, new HarmonyMethod(patch)); return 1; }
            catch (Exception e) { Warn("patch " + typeName + "." + methodName + " 失败: " + e.Message); return 0; }
        }

        private static int PatchPre(Harmony harmony, string typeName, string methodName, MethodInfo prefix)
        {
            Type t = AccessTools.TypeByName(typeName);
            if (t == null) { WarnOnce("type:" + typeName, "找不到类型 " + typeName); return 0; }
            MethodInfo m = AccessTools.Method(t, methodName);
            if (m == null) { WarnOnce("method:" + typeName + "." + methodName, "找不到方法 " + typeName + "." + methodName); return 0; }
            try { harmony.Patch(m, new HarmonyMethod(prefix), null); return 1; }
            catch (Exception e) { Warn("patch(pre) " + typeName + "." + methodName + " 失败: " + e.Message); return 0; }
        }

        // ---------------- Harmony 出入口 ----------------

        private static void Pre()
        {
            if (!IsEnabled()) return;
            DeferredRestoreCheck();
            // 场景补丁比 1 秒轮询更早触发, 顺手把跨词书守卫跑掉(一次性, 见 CrossBookGuard)
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

        // AddWordsToSelfChosenList 是带 ref 形参的静态方法, 就地改列表
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

        // 词书切换确认之后: 只有当前选中的词表匹配本插件的完整身份签名才摆正。
        // 离开时先恢复进入本词书前由游戏保存的共享队列，再让游戏按当前词书重算。
        private static void PostBookChange()
        {
            if (!IsEnabled())
            {
                CleanupDisabledState();
                return;
            }
            try
            {
                _slotProfileAt = -1E9f; // 换书了, 槽位记录重读
                _memoryProfileList = null;
                _memoryProfileCount = -1;
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
                    // 离开受管词书: 不管本次会话有没有动过这些队列, 只要存档里留着接管记录就还原。
                    // 只看本次会话的内存标记会漏掉「重启后游戏仍停在日语词书, 再在游戏内切书」
                    // 这条路 —— 那个进程可能一次都没写过, 存档里却还留着上一次的日语队列。
                    RestoreSharedFields();
                    RegenerateByGame();
                }
            }
            catch (Exception e) { Warn("换书异常: " + e.Message); }
        }

        // 兜底轮询: 覆盖没有补丁可打的读取点 (选词界面/重排/换标签)
        private void Update()
        {
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
            catch (Exception e) { Warn("例句库自愈调度异常: " + e.Message); }
        }

        // ---------------- 已学词测试的兜底自愈 ----------------

        // SetS8Data.SetAsLearnedTest 之后: 测试词表若被历史 bug 剔空/过短, 整组重建。
        private static void PostSetAsLearnedTest()
        {
            if (!IsEnabled()) return;
            if (BookState() != 1) return;
            try { HealTestList(); }
            catch (Exception e) { Warn("测试词表自愈异常: " + e.Message); }
        }

        // MultipleChoiceGeneratorS9 出题之前再挡一次
        // (Start 与 completeThis 都会调 GenerateOptions, 取 allTestWordsS10_Para[进度], 空表/越界必崩)
        private static void PreMcGenS9()
        {
            if (!IsEnabled()) return;
            if (BookState() != 1) return;
            try { HealTestList(); }
            catch (Exception e) { Warn("S9 前置自愈异常: " + e.Message); }
        }

        // 选词界面渲染前 / 词组重建后: 立刻把候选表与已选表摆正
        private static void PreFixSelection()
        {
            if (BookState() != 1) return;
            try { FixSelectionLists(); }
            catch (Exception e) { Warn("选词表校正异常: " + e.Message); }
        }

        private static void PostFixSelection()
        {
            if (BookState() != 1) return;
            try { FixSelectionLists(); }
            catch (Exception e) { Warn("选词表校正异常: " + e.Message); }
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
                Warn("已学词测试词表为空/过短, 已用本书词重建 " + rebuilt.Count + " 个");
                return;
            }

            // 词池里混进了别的词书的词(最常见: 进入测试前存档里残留着上一轮英语书的队列,
            // 而 need 与它「自洽」, 错位检查看不出问题) -> 整组按本书重建。
            // 这一步不依赖游戏会不会触发 Enforce, 在出题前把词池钉死。
            List<string> bookFixed = Filter(cur, 5, true);
            if (bookFixed != null)
            {
                SetTestLists(bookFixed);
                Warn("测试词池混入书外词, 已按本书重建 " + bookFixed.Count + " 个");
                return;
            }

            int progress = LoadInt("S8Progress_Para", MyParameters.S8Progress_Para);
            if (progress < 0 || progress >= cur.Count)
            {
                ResetProgress();
                Warn("测试进度越界(" + progress + "/" + cur.Count + "), 已重置到第 1 题");
                return;
            }

            // 题干队列 = allTestWordsS10_Para 从 progress 起的尾巴; 历史 bug 会把两者弄错位
            List<string> need = MyParameters.S8needToLearnWordList_Para;
            if (need == null || need.Count == 0 || need[0] != cur[progress])
            {
                Warn("题干队列与题目错位, 已按进度重新对齐 " + (cur.Count - progress) + " 个");
                SyncStemQueue(progress, cur);
            }
        }

        // 「已学词测试」的题面 = need[0], 正确答案/选项 = allTestWordsS10_Para[S8Progress_Para]。
        // 游戏有两个入口会自作主张地重建词池(快速测试按钮 / SetAsLearnedTest 用 left 重建 need),
        // 只要 need 没跟着换, 题面就会出现别的词书或上一轮遗留的词, 与选项毫无关系。
        // 这里在游戏读 need[0] 之前把两张表对齐。
        private static void PreShowTheWord()
        {
            if (!IsEnabled()) return;
            if (BookState() != 1) return;
            try { HealTestList(); }
            catch (Exception e) { Warn("题干前置自愈异常: " + e.Message); }
        }

        // 「快速测试」按钮按下之后: 词池刚被全局已学词典重建(夹带别的词书的词), 立刻按本书重采样
        private static void PostStartQuickTest()
        {
            if (!IsEnabled()) return;
            try
            {
                if (BookState() != 1) return;       // 只在日语词书下重排, 其它词书保持游戏原样
                if (MyParameters.S8ThisMode_Para != "已学词测试") return;  // 这个按钮就在「已学词测试 → 快速测试」面板上
                int target = MyParameters.TestWordsNum_Para;
                if (target < 5) target = 5;
                List<string> pool = SampleBookLearned(target);
                if (pool == null || pool.Count < 5)
                    pool = RebuildWithFallback(MyParameters.allTestWordsS10_Para, 5, target, true);
                if (pool == null || pool.Count < 5) return;
                SetTestLists(pool);
                Warn("快速测试词池已按本书重采样 " + pool.Count + " 个");
            }
            catch (Exception e) { Warn("快速测试重采样异常: " + e.Message); }
        }

        // 复刻快速测试的「0~5 级筛选」, 但只取本书内已学词; 排序按面板上的
        // 「正序/倒序/随机 + 未测词优先」(见 OrderByTestSetting), 与游戏自己的取样一致。
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
                if (!bookSet.Contains(kv.Key)) continue;
                if (!LevelOn(kv.Value.masteryLevel)) continue;
                cand.Add(kv.Key);
            }
            if (cand.Count == 0) return null;
            OrderByTestSetting(cand, learned);
            if (target > 0 && cand.Count > target) cand.RemoveRange(target, cand.Count - target);
            return cand;
        }

        // 快速测试面板上的 0~5 级筛选开关 (判定与游戏 GenerateWordList 一致)
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

        // (pron 白名单方案作废: 实测猫条版整本书的词都在 wcpOnlyWord.db 里, 含日文词,
        //   它分不开「本书词」和「全局已学词典里的英语词」。S9 词池靠 SampleBookLearned
        //   的「本书 ∩ 已学」过滤就够了。)

        // 整套「已学词测试」状态一次写齐: 词池 / 剩余 / 题干队列 / 本轮记录 / 进度
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

            // 词池是新造的, 「本轮 已完成/状态」记录必须一起清掉, 否则进度会指向错位的词。
            // 这几张表在学习/复习模式里是共用的, 只在已学词测试下清, 别误伤别的模式。
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

        // 题干队列(need)与剩余队列(left)都必须是词池从 progress 起的尾巴: 两张表错位 = 答非所问
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

        // ---------------- 主逻辑 ----------------

        internal static void Enforce()
        {
            int state = BookState();
            if (state != 1) return;                 // 不是当前日语自定义词书 -> 一律不动
            bool jp = true;

            // 战斗词表: 至少 5 个, 否则战斗界面没词可用
            int fightMax = MyParameters.S7FightWordMax;
            if (fightMax < 5) fightMax = 5;
            bool topUp = jp && Instance != null && _topUp.Value;
            FixField("S7TestWordList_Para", ref MyParameters.S7TestWordList_Para,
                     topUp ? fightMax : 5, true);

            if (!_guardOtherLists.Value) return;

            // 测试词池: S9 取 allTestWordsS10_Para[S8Progress_Para], 既要求 >= 5, 也不能夹带别的词书的词。
            // 池子一换, 进度与「已完成」记录必须一起归零, 否则题干与正确答案会错位。
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
                // 词池换了, 题干队列(need[0] 就是题面显示的词)必须一起换, 否则「别的书/上一轮的词 + 本轮的选项」
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

            // 选词列表(截图里那份「已学词汇」)与自选测试集合
            FixSelectionLists();
        }

        private static void FixField(string key, ref List<string> field, int minKeep, bool preferLearned)
        {
            if (field == null || field.Count == 0)
            {
                // 战斗入口后续会直接按索引取词。游戏初始化/切书时若暂时给出
                // null 或空表，不能把它原样留到 GenerateOptions；其它每日/额外
                // 队列为空可能是合法的“今天没有词”，仍保持只读。
                if (key != "S7TestWordList_Para") return;
                List<string> rebuilt = RebuildWithFallback(field, minKeep, minKeep, preferLearned);
                if (rebuilt == null) return;
                field = rebuilt;
                SaveField(key, rebuilt);
                Warn("战斗词表为空/未初始化, 已用本书词补足 " + rebuilt.Count + " 个");
                return;
            }
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

        // 选词界面: 候选表(S9CurrentArray_Para)补足到本书词, 已选表(S9extraStudy_Para)只剔除书外词
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
            Warn("已选词里剔除了词书外的词, 剩 " + extra.Length + " 个");
        }

        // 只剔除词书外的词, 不补词, 允许剔空(用户选了几个就是几个, 不足 5 个游戏自己会提示)
        private static string[] FilterDropArray(string[] cur)
        {
            if (cur == null || cur.Length == 0) return null;
            int state = BookState();
            if (state == 0) return null;
            bool jp = (state == 1);
            List<string> book = MyParameters.ChosenBook_List;
            HashSet<string> bookSet = jp ? new HashSet<string>(book) : null;
            HashSet<string> seen = new HashSet<string>();
            List<string> keep = new List<string>();
            bool changed = false;
            for (int i = 0; i < cur.Length; i++)
            {
                string w = cur[i];
                if (string.IsNullOrEmpty(w) || !Allowed(w, jp, bookSet) || !seen.Add(w))
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

        // 返回校正后的词表; 无需改动时返回 null。绝不返回空表/过短表。
        private static List<string> Filter(List<string> cur, int minKeep, bool preferLearned)
        {
            if (cur == null || cur.Count == 0) return null;
            int state = BookState();
            if (state == 0) return null;
            bool jp = (state == 1);
            List<string> book = MyParameters.ChosenBook_List;
            HashSet<string> bookSet = jp ? new HashSet<string>(book) : null;

            HashSet<string> seen = new HashSet<string>();
            List<string> keep = new List<string>();
            int dropped = 0;
            for (int i = 0; i < cur.Count; i++)
            {
                string w = cur[i];
                if (string.IsNullOrEmpty(w)) continue;
                if (!Allowed(w, jp, bookSet)) { dropped++; continue; }
                if (seen.Add(w)) keep.Add(w);
            }
            if (dropped == 0 && keep.Count == cur.Count) return null;

            if (minKeep < 1) minKeep = 1;
            if (keep.Count < minKeep)
            {
                // 被剔空或过短: 用本书词重建(目标 = 原规模, 至少 minKeep)
                int target = cur.Count;
                if (target < minKeep) target = minKeep;
                keep.Clear();
                seen.Clear();
                Rebuild(keep, seen, jp, bookSet, preferLearned, target);
                if (keep.Count < minKeep) return null;   // 凑不齐就不动, 免得把词表弄坏
            }
            return keep;
        }

        // 直接造一份新表: 优先本书已学词(或本书未学词), 再退到整本书
        private static List<string> Rebuild(int minKeep, int target, bool preferLearned)
        {
            if (BookState() == 0) return null;
            bool jp = (BookState() == 1);
            List<string> book = MyParameters.ChosenBook_List;
            HashSet<string> bookSet = jp ? new HashSet<string>(book) : null;
            List<string> dest = new List<string>();
            HashSet<string> seen = new HashSet<string>();
            if (target < minKeep) target = minKeep;
            Rebuild(dest, seen, jp, bookSet, preferLearned, target);
            if (dest.Count < minKeep) return null;
            return dest;
        }

        // 保留现有词(限定本书内)再补足到 target: 用于「用户已选了几个词」或「历史表被剔空」
        private static List<string> RebuildKeeping(List<string> cur, int minKeep, int target, bool preferLearned)
        {
            int state = BookState();
            if (state == 0) return null;
            bool jp = (state == 1);
            List<string> book = MyParameters.ChosenBook_List;
            HashSet<string> bookSet = jp ? new HashSet<string>(book) : null;
            List<string> dest = new List<string>();
            HashSet<string> seen = new HashSet<string>();
            if (cur != null)
            {
                for (int i = 0; i < cur.Count; i++)
                {
                    string w = cur[i];
                    if (string.IsNullOrEmpty(w) || !Allowed(w, jp, bookSet)) continue;
                    if (seen.Add(w)) dest.Add(w);
                }
            }
            if (target < minKeep) target = minKeep;
            if (dest.Count > target) target = dest.Count;
            Rebuild(dest, seen, jp, bookSet, preferLearned, target);
            if (dest.Count < minKeep) return null;
            return dest;
        }

        // 重建词表: 优先按当前词书筛/补; 词书状态不明时退化成「用当前词书列表硬补」。
        // 崩不崩不能取决于能不能认出词书, 所以只要有 ChosenBook_List 就一定能凑够 minKeep。
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

        private static void Rebuild(List<string> dest, HashSet<string> seen, bool jp, HashSet<string> bookSet, bool preferLearned, int target)
        {
            List<string> book = MyParameters.ChosenBook_List;
            if (jp && book != null)
            {
                // 词池只能从当前词书补齐；全局 HaveLearnedDictionary 不能跨书供词。
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
                if (learned != null && learned.ContainsKey(w)) learnedBook.Add(w);
                else unlearnedBook.Add(w);
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

        private static void FillFromLearned(List<string> dest, HashSet<string> seen, bool jp, HashSet<string> bookSet, int target)
        {
            Dictionary<string, WordInfo> learned = MyParameters.HaveLearnedDictionary;
            if (learned == null) return;
            List<string> cand = new List<string>();
            foreach (KeyValuePair<string, WordInfo> kv in learned)
            {
                string w = kv.Key;
                if (string.IsNullOrEmpty(w)) continue;
                if (!Allowed(w, jp, bookSet)) continue;
                cand.Add(w);
            }
            // 重建也要按玩家的排序设置来, 不然修过的词池顺序会跟他选的正序/倒序/随机对不上
            OrderByTestSetting(cand, learned);
            for (int i = 0; i < cand.Count && dest.Count < target; i++)
                if (seen.Add(cand[i])) dest.Add(cand[i]);
        }

        // 复刻 ChooseWordManager.TestWordPos/Neg/Ran(含 Off):
        //   「未测词优先」开: 主键 testTimes 升序, 次键 lastStudyTime(正序升/倒序降);
        //   「未测词优先」关: 正序 = lastStudyTime 升序, 倒序 = testTimes 降序;
        //   随机 = 纯随机(游戏里 testTimes 那一级会被随机键打散)。
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

        private static bool Allowed(string w, bool jp, HashSet<string> bookSet)
        {
            if (string.IsNullOrEmpty(w)) return false;
            return jp ? (bookSet != null && bookSet.Contains(w)) : !LooksJapanese(w);
        }

        // 词书状态: 1 = 当前选中的、已登记的日语词书；0 = 其它任何情况(一律不动)。
        // 身份来自完整词表指纹；槽位仅用于读取当前导入位置，不参与身份判断。
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
            if (!BookReady()) return 0;      // 还没读档 -> 一律不动
            string name = MyParameters.ChosenBook_Para;
            if (string.IsNullOrEmpty(name)) return 0;
            List<string> book = MyParameters.ChosenBook_List;
            if (book == null || book.Count < 5) return 0;

            // 只读取当前选中的自定义槽。原版书不可能有可管理 Profile，绝不写队列。
            int idx = SelfBookIndexOf(name);
            if (idx <= 0) return 0;
            BookProfile memoryProfile = ProfileOfCurrentList(book);
            BookProfile slotProfile = SlotProfile(idx);
            _stateMem = ProfileId(memoryProfile); // 游戏实际拿来过滤的那份词表
            _stateSlot = ProfileId(slotProfile);  // 这个槽自己在 MyBook.es3 里记的那份
            if (memoryProfile == null || memoryProfile.Language != BookProfiles.Japanese) return 0;
            // 读不到、不是本书、或正在换书时都失败关闭；不能以语言相近为由接管。
            if (slotProfile == null || slotProfile.Id != memoryProfile.Id) return 0;
            return 1;
        }

        private static string ProfileId(BookProfile profile)
        {
            return profile == null ? "<none>" : profile.Id;
        }

        // 当前内存词表在一次切换后通常复用同一个 List；缓存避免每帧计算完整 SHA-256。
        private static BookProfile ProfileOfCurrentList(List<string> list)
        {
            string bookName = MyParameters.ChosenBook_Para;
            if (System.Object.ReferenceEquals(list, _memoryProfileList) && list != null &&
                list.Count == _memoryProfileCount && bookName == _memoryProfileBookName)
                return _memoryProfile;
            _memoryProfileList = list;
            _memoryProfileCount = list == null ? -1 : list.Count;
            _memoryProfileBookName = bookName;
            _memoryProfile = BookProfiles.Match(list);
            return _memoryProfile;
        }

        // 自定义槽位(1~4)自己的完整词表。槽位只定位导入位置，不是身份条件。
        private static BookProfile SlotProfile(int idx)
        {
            if (idx <= 0) return null;
            float now = Time.realtimeSinceStartup;
            if (idx == _slotProfileIdx && now - _slotProfileAt < SlotProfileTtl) return _slotProfile;
            _slotProfileIdx = idx;
            _slotProfileAt = now;
            _slotProfile = null;
            try
            {
                string path = System.IO.Path.Combine(Application.persistentDataPath, "MyBook.es3");
                List<string> slot = new List<string>();
                try
                {
                    string[] arr = ES3.Load<string[]>("SelfBookList" + idx, path);
                    if (arr != null && arr.Length > 0) slot.AddRange(arr);
                }
                catch (Exception) { }
                if (slot.Count < 5)
                {
                    // 有的存档只写了释义字典, 用它的键顶上
                    try
                    {
                        Dictionary<string, string> d = ES3.Load<Dictionary<string, string>>("wordDictionary" + idx, path);
                        if (d != null && d.Count > 0)
                        {
                            slot.Clear();
                            foreach (KeyValuePair<string, string> kv in d) slot.Add(kv.Key);
                        }
                    }
                    catch (Exception) { }
                }
                if (slot.Count > 0) _slotProfile = BookProfiles.Match(slot);
            }
            catch (Exception e) { WarnOnce("slotprofile:" + idx, "读取槽位 " + idx + " 词表失败: " + e.Message); }
            return _slotProfile;
        }

        // 两侧 Profile 必须相同，才允许日语策略工作。
        private static void LogBookState(int state)
        {
            List<string> book = MyParameters.ChosenBook_List;
            int n = (book == null) ? -1 : book.Count;
            string sig = state + "|" + MyParameters.ChosenBook_Para + "|" + n + "|" + _stateMem + "|" + _stateSlot;
            string prev;
            if (LastSig.TryGetValue("bookstate", out prev) && prev == sig) return;
            LastSig["bookstate"] = sig;
            Log.LogInfo("JPWordList: 词书状态=" + state + " 内存书名=" + MyParameters.ChosenBook_Para +
                        " 内存词表=" + n + "条(内存 Profile=" + _stateMem + " 槽位 Profile=" + _stateSlot +
                        ") 存档书名=" + (DiskBookName() ?? "<读不到>"));
        }

        // 单词是否像日语 (含假名 / 汉字 / 半角片假名 / 々)
        internal static bool LooksJapanese(string w)
        {
            if (string.IsNullOrEmpty(w)) return false;
            for (int i = 0; i < w.Length; i++)
            {
                char c = w[i];
                if ((c >= 0x3040 && c <= 0x30FF) ||
                    (c >= 0x3400 && c <= 0x4DBF) ||
                    (c >= 0x4E00 && c <= 0x9FFF) ||
                    (c >= 0xF900 && c <= 0xFAFF) ||
                    (c >= 0xFF66 && c <= 0xFF9D) ||
                    c == 0x3005 || c == 0x3006 || c == 0x3007)
                {
                    return true;
                }
            }
            return false;
        }

        private static void RegenerateByGame()
        {
            string type = MyParameters.S7FightWordType;
            if (!string.IsNullOrEmpty(type) && type != ReviewRangeType) return;
            ChooseWordManager mgr = UnityEngine.Object.FindObjectOfType<ChooseWordManager>();
            if (mgr == null)
            {
                WarnOnce("noMgr", "找不到 ChooseWordManager, 跳过重算");
                return;
            }
            mgr.FightList();
            Log.LogInfo("JPWordList: 已切回非日语词书, 让游戏按当前词书重算战斗词表");
        }

        // ---------------- 题干 / 选项显示改写 ----------------

        private static bool KanaOn()
        {
            if (!IsEnabled()) return false;
            if (_kanaStem == null || !_kanaStem.Value) return false;
            return BookState() == 1;     // 按内容判定: 自定义槽里装的是英语书时不改写题干/选项
        }

        // 是否处于「测试」式问答 (学习界面不改写, 免得影响背单词)
        private static bool IsTestMode()
        {
            string m = MyParameters.S8ThisMode_Para;
            if (string.IsNullOrEmpty(m)) return false;
            if (m == "已学词测试") return true;
            if ((m == "每日复习" || m == "额外复习") && MyParameters.S8ReviewModeType == 1) return true;
            return false;
        }

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

        // 战斗/复习四选一: 题干 = 假名, 选项 = 汉字 + 中文释义
        private static void PostMcGen(MultipleChoiceGenerator __instance)
        {
            if (!KanaOn() || __instance == null) return;
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

                // 趁释义原文还在, 先取正确答案的假名读音, 并把见到的词条攒下来
                string kana = null;
                for (int i = 0; i < opts.Length; i++)
                {
                    if (opts[i] == null) continue;
                    string w = (words[i] != null) ? words[i].text : null;
                    Harvest(w, opts[i].text);
                    if (kana == null && !string.IsNullOrEmpty(word) && w == word)
                        kana = ReadingOf(CleanEntry(opts[i].text));
                }
                if (kana == null) kana = KanaOf(word);      // 兜底: 释义没带【假名】时查本书字典

                for (int i = 0; i < opts.Length; i++)
                {
                    if (opts[i] == null) continue;
                    string w = (words[i] != null) ? words[i].text : null;
                    string txt = KanjiOption(w, opts[i].text);
                    opts[i].text = txt;
                    if (optsSM[i] != null) optsSM[i].text = txt;
                }
                if (kana != null && __instance.testWordText != null) __instance.testWordText.text = kana;
            }
            catch (Exception e) { Warn("题干改写(战斗)异常: " + e.Message); }
        }

        // 已学词测试: 选项 = 汉字 + 中文释义; 题干沿用 ShowTheWord 的假名
        private static void PostMcGenS9(MultipleChoiceGeneratorS9 __instance)
        {
            if (!KanaOn() || __instance == null) return;
            try
            {
                string word = CurrentTestWordS9();
                string[] optWords = new string[] {
                    MyParameters.S9Option1_Para, MyParameters.S9Option2_Para,
                    MyParameters.S9Option3_Para, MyParameters.S9Option4_Para };

                string kana = null;
                if (__instance.optionText != null)
                {
                    for (int i = 0; i < __instance.optionText.Length && i < optWords.Length; i++)
                    {
                        if (__instance.optionText[i] == null) continue;
                        Harvest(optWords[i], __instance.optionText[i].text);
                        if (kana == null && !string.IsNullOrEmpty(word) && optWords[i] == word)
                            kana = ReadingOf(CleanEntry(__instance.optionText[i].text));
                    }
                    for (int i = 0; i < __instance.optionText.Length && i < optWords.Length; i++)
                    {
                        if (__instance.optionText[i] == null) continue;
                        __instance.optionText[i].text = KanjiOption(optWords[i], __instance.optionText[i].text);
                    }
                }
                if (kana == null) kana = KanaOf(word);
                if (kana != null) SetStemText(word, kana);
            }
            catch (Exception e) { Warn("题干改写(S9)异常: " + e.Message); }
        }

        // 学习/复习/测试界面: 测试模式下把题干输入框显示成假名
        private static void PostShowTheWord(SetInputFieldValueS8 __instance)
        {
            if (!KanaOn() || __instance == null) return;
            if (!IsTestMode()) return;
            try
            {
                if (__instance.inputField == null) return;
                string word = __instance.inputField.text;
                string kana = KanaOf(word);
                if (kana != null && kana != word) __instance.inputField.text = kana;
            }
            catch (Exception e) { Warn("题干改写(S8)异常: " + e.Message); }
        }

        // 题干可能挂在输入框, 也可能挂在发音按钮旁的文本上, 两处都兜住
        private static void SetStemText(string word, string kana)
        {
            if (string.IsNullOrEmpty(word)) return;
            SetInputFieldValueS8[] sifs = UnityEngine.Object.FindObjectsOfType<SetInputFieldValueS8>();
            for (int i = 0; i < sifs.Length; i++)
            {
                if (sifs[i] == null || sifs[i].inputField == null) continue;
                if (sifs[i].inputField.text == word) sifs[i].inputField.text = kana;
            }
            VocabularyAudioPlayer[] vaps = UnityEngine.Object.FindObjectsOfType<VocabularyAudioPlayer>();
            for (int i = 0; i < vaps.Length; i++)
            {
                if (vaps[i] == null || vaps[i].text1 == null) continue;
                if (vaps[i].text1.text == word) vaps[i].text1.text = kana;
            }
            // 记下这一题的确切映射: 发音按钮会把 text1 当本地音频文件名用(按汉字形命名),
            // 而这里刚把它换成了假名, 所以发音前要用这张表换回原词。先让字典映射就位,
            // 再用本题的确切值覆盖(同音词时确切值更准)。
            if (kana != word)
            {
                BuildKanaMap(SelfBookIndexOf(MyParameters.ChosenBook_Para));
                KanaToSurface[kana] = word;
            }
        }

        // ---------------- 查词面板释义 / 音标 (日语词在英语库里查不到) ----------------

        // 这些面板的释义/音标只来自英语词库(wcpFullEng.db / wcpOnlyWord.db): 日语词既没有
        // 音标也查不到释义, 面板会显示「本地暂未收录这个单词」, 音标行留空。
        // 当前是受管日语词书时, 改用本书释义(插件本来就能读到的那份), 音标位填假名读音。
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
                string phonetic = !string.IsNullOrEmpty(us) ? us.Trim() :
                    (!string.IsNullOrEmpty(uk) ? uk.Trim() : null);
                if (!string.IsNullOrEmpty(phonetic)) __instance.phonicsText.text = phonetic;
            }
            catch (Exception e) { WarnOnce("answerphonetic", "答案区读音修正异常: " + e.Message); }
        }

        private static void PostS8Classification(SetInputFieldValueS8 __instance)
        {
            if (!IsEnabled() || __instance == null || Instance == null) return;
            if (BookState() != 1 || !__instance.gameObject.activeInHierarchy) return;
            Instance.StartCoroutine(RefreshS8AfterClassification(__instance));
        }

        private static IEnumerator RefreshS8AfterClassification(SetInputFieldValueS8 instance)
        {
            // 等本次按钮的其它 listener 把状态写完，再读取最新队列；避免被旧 UI 回调覆盖。
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
            catch (Exception e) { WarnOnce("s8refresh", "学习页推进修正异常: " + e.Message); }
        }

        private static void FixDictPanel(TextMeshProUGUI meaning, TextMeshProUGUI us, TextMeshProUGUI uk)
        {
            if (!IsEnabled()) return;
            if (BookState() != 1) return;      // 只改受管日语词书, 别的词书原样
            try
            {
                string word = MyParameters.checkWordInDictionary;
                if (string.IsNullOrEmpty(word)) return;
                string entry = EntryOf(word);
                if (entry == null) return;      // 本书释义里没有就别动, 免得把好的覆盖成空
                if (meaning != null) meaning.text = entry + NL;
                string kana = ReadingOf(entry);
                if (kana == null && IsKanaOnly(word)) kana = word;
                if (us != null && kana != null) us.text = kana;
                if (uk != null) uk.text = "";
            }
            catch (Exception e) { WarnOnce("dict", "查词面板释义修正异常: " + e.Message); }
        }

        // ---------------- 发音词形 (本地音频按汉字形命名) ----------------

        // PlayWordAudio 用 text1.text 拼 <词>.mp3。插件把题干改成了假名, 于是查 ぜんぶ.mp3
        // 落空 -> 回退 AI(英语 TTS)。发音前把它换回汉字形, 播完还原(文件名在开头就取好了)。
        // VocabularyAudioPlayer 出现在 Fight/Review/ChooseWords/FruitInja/Bat/FreeReview/
        // SpellingGame 等所有会显示单词的场景里, 所以这一处就覆盖了各个小游戏。
        private static void PrePlayWordAudio(VocabularyAudioPlayer __instance)
        {
            _audioSwapped = false;
            _audioOriginal = null;
            if (!IsEnabled()) return;
            if (__instance == null || __instance.text1 == null) return;
            try
            {
                if (BookState() != 1) return;
                BuildKanaMap(SelfBookIndexOf(MyParameters.ChosenBook_Para));
                string raw = __instance.text1.text;
                if (string.IsNullOrEmpty(raw)) return;
                string shown = raw.Trim();
                string surface = SurfaceOf(shown);
                if (surface == null) surface = SurfaceFromCurrentQuestion(shown);
                if (surface == null || surface == shown)
                {
                    // 诊断: 明明是日语词却换不回汉字形 -> 本地音频必然找不到, 会退回英语 TTS
                    if (LooksJapanese(shown))
                        WarnOnce("audionosurf:" + shown,
                            "发音: " + shown + " 找不到本地音频对应的汉字形, 将退回 AI(英语)发音");
                    return;
                }
                _audioOriginal = raw;
                __instance.text1.text = surface;
                _audioSwapped = true;
                InfoOnce("audioswap:" + shown,
                    "发音词形: " + shown + " -> " + surface + " (用本地单词音频)");
            }
            catch (Exception e) { WarnOnce("audio", "发音词形修正异常: " + e.Message); }
        }

        // 兜底: 发音文本就是当前这题的假名读音 -> 直接拿当前题目的词当作汉字形。
        // 覆盖「映射表还没建好 / 词条缺读音」但题目本身已知的情况。
        private static string SurfaceFromCurrentQuestion(string shown)
        {
            string w = CurrentTestWordS9();
            if (string.IsNullOrEmpty(w)) w = CurrentFightWord();
            if (string.IsNullOrEmpty(w) || w == shown) return null;
            string kana = KanaOf(w);
            return (kana != null && kana == shown) ? w : null;
        }

        private static void PostPlayWordAudio(VocabularyAudioPlayer __instance)
        {
            if (!_audioSwapped) return;
            _audioSwapped = false;
            try
            {
                if (__instance != null && __instance.text1 != null && _audioOriginal != null)
                    __instance.text1.text = _audioOriginal;
            }
            catch (Exception e) { WarnOnce("audio2", "发音词形还原异常: " + e.Message); }
        }

        // 假名读音 -> 本书里的汉字写法。查不到返回 null(此时按原样发音)。
        private static string SurfaceOf(string kana)
        {
            if (string.IsNullOrEmpty(kana)) return null;
            string v;
            if (KanaToSurface.TryGetValue(kana, out v) && !string.IsNullOrEmpty(v)) return v;
            return null;
        }

        // 本书释义字典里逐条取「【假名】-> 词」, 同一读音有多个写法时取最短的那个。
        // 只在换书时重算一次; SetStemText 记下的确切映射会覆盖字典推断(同音词用它更准)。
        private static void BuildKanaMap(int idx)
        {
            if (idx <= 0) return;               // 认不出词书序号: 不动现有映射
            if (_kanaMapIdx == idx) return;
            _kanaMapIdx = idx;
            KanaToSurface.Clear();
            Dictionary<string, string> d = BookDict();
            if (d == null) return;
            foreach (KeyValuePair<string, string> kv in d)
            {
                string surface = kv.Key;
                if (string.IsNullOrEmpty(surface)) continue;
                string kana = ReadingOf(CleanEntry(kv.Value));
                if (kana == null || kana == surface) continue;
                string cur;
                if (!KanaToSurface.TryGetValue(kana, out cur) || surface.Length < cur.Length)
                    KanaToSurface[kana] = surface;
            }
        }

        // ---------------- 释义字典: 取假名 / 组选项 ----------------

        // 词条里取假名读音; 汉字词才有「【假名】」, 取不到返回 null
        internal static string KanaOf(string word)
        {
            return ReadingOf(EntryOf(word));
        }

        // 从「【假名】中文释义〈词性〉」里取假名; 没有【】或括号里不是假名则返回 null
        private static string ReadingOf(string entry)
        {
            if (string.IsNullOrEmpty(entry)) return null;
            int a = entry.IndexOf('【');
            if (a < 0) return null;
            int b = entry.IndexOf('】', a + 1);
            if (b < 0 || b <= a + 1) return null;
            string kana = entry.Substring(a + 1, b - a - 1).Trim();
            if (kana.Length == 0) return null;
            if (!IsKanaOnly(kana)) return null;
            return kana;
        }

        // 去掉词条里的「【假名】」; 没有【】或去掉后为空则返回 null
        private static string StripReading(string entry)
        {
            if (string.IsNullOrEmpty(entry)) return null;
            int a = entry.IndexOf('【');
            if (a < 0) return null;
            int b = entry.IndexOf('】', a + 1);
            if (b < 0) return null;
            string rest = (entry.Substring(0, a) + entry.Substring(b + 1)).Trim();
            return (rest.Length == 0) ? null : rest;
        }

        // 选项 = 「汉字写法 + 中文释义(去掉【假名】)」; 假名词或查不到时原样返回。
        // 优先用游戏已经渲染出来的释义文本(它本身就是「【假名】释义」), 不依赖内存字典是否被填过。
        internal static string KanjiOption(string word, string orig)
        {
            if (string.IsNullOrEmpty(word) || string.IsNullOrEmpty(orig)) return orig;
            string rest = StripReading(CleanEntry(orig));
            if (rest == null)
            {
                string entry = EntryOf(word);
                if (entry == null) return orig;
                rest = StripReading(entry);
                if (rest == null) return orig;
            }
            // 释义里已经带了这个词的汉字写法(例如「全部；所有〈名〉」)就不必再接一遍
            if (rest.StartsWith(word, StringComparison.Ordinal)) return rest;
            return word + " " + rest;
        }

        // 释义来源(按可靠性): 游戏内存字典 -> 自己读的 MyBook.es3 wordDictionaryN -> 出题时攒下的词条。
        // 不能只认 MyParameters.SelfBookMeaningDictionary: 实测 SelfBookMeaningConnectIf 为 false 时它是空的。
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

        // 出题/学习界面渲染出来的释义就是「【假名】释义」, 见到就记下来, 之后题干要假名时直接查
        private static void Harvest(string word, string meaning)
        {
            if (string.IsNullOrEmpty(word) || string.IsNullOrEmpty(meaning)) return;
            if (meaning.IndexOf('【') < 0) return;
            string cur;
            if (Harvested.TryGetValue(word, out cur) && !string.IsNullOrEmpty(cur)) return;
            Harvested[word] = CleanEntry(meaning);
        }

        // 当前自定义词书序号(自定义词书一~四 / 日语词书一~四, 允许带昵称后缀); 认不出返回 0
        private static int SelfBookIndexOf(string name)
        {
            if (string.IsNullOrEmpty(name)) return 0;
            if (!name.StartsWith("自定义词书", StringComparison.Ordinal) &&
                !name.StartsWith("日语词书", StringComparison.Ordinal) &&
                !name.StartsWith("日语词库", StringComparison.Ordinal)) return 0;
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
            return profile != null && profile.Language != BookProfiles.Japanese;
        }

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
        // 这里只需在窗口关闭后让被暂缓的还原自然重试。
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

        // MyBook.es3 里那份本书释义字典。游戏只在 SelfBookMeaningConnectIf 为真时才读它,
        // 那开关实测是关的, 所以这里自己读一份(按词书序号缓存, 换书才重读)。
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
                    Log.LogInfo("JPWordList: 本书释义字典 wordDictionary" + idx + " 载入 " +
                                _bookDict.Count + " 条 (题干假名 / 汉字选项用)");
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

        // 只接受假名(含长音符/中点/浊点/全角空格), 防止把中文或汉字当读音
        private static bool IsKanaOnly(string s)
        {
            for (int i = 0; i < s.Length; i++)
            {
                char c = s[i];
                bool ok = (c >= 0x3040 && c <= 0x30FF) ||
                          c == 0x30FB || c == 0x30FC || c == 0x3099 || c == 0x309A ||
                          c == 0x309B || c == 0x309C ||
                          (c >= 0xFF66 && c <= 0xFF9F) ||
                          c == ' ' || c == '.' || c == 0x3000 || c == '-';
                if (!ok) return false;
            }
            return true;
        }

        // ---------------- ES3 ----------------

        // ES3 读 string 必须写命名参数 defaultValue:, 否则 C# 会选到 (key, filePath) 重载,
        // 把字符串默认值当文件名去找文件 (游戏自己那些 ES3.Load<string>(key, 值) 就是这么写坏的)。
        private static string LoadString(string key, string fallback)
        {
            try { return ES3.Load<string>(key, defaultValue: fallback); }
            catch (Exception e)
            {
                WarnOnce("ldstr:" + key, "读取 " + key + " 失败: " + e.Message);
                return fallback;
            }
        }

        // 存档里的词书名(1 秒缓存)
        private static string DiskBookName()
        {
            if (Time.realtimeSinceStartup - _diskBookAt < 1f) return _diskBook;
            _diskBookAt = Time.realtimeSinceStartup;
            _diskBook = LoadString("ChosenBook_Para", null);
            return _diskBook;
        }

        // 游戏还没把存档读进 MyParameters 之前, 内存里全是编译期默认值(默认书是「四级大纲词汇」),
        // 那时按内存里的词书剔词再写回 ES3 会把存档写坏。确认内存与存档一致了才动手。
        internal static bool BookReady()
        {
            string disk = DiskBookName();
            if (string.IsNullOrEmpty(disk))
            {
                WarnOnce("noready", "读不到存档里的词书名, 暂不改动词表");
                return false;
            }
            return disk == MyParameters.ChosenBook_Para;
        }

        private static void SaveField(string key, List<string> list)
        {
            if (BookState() != 1) return;
            if (!BaselineLists.ContainsKey(key))
            {
                List<string> snap = LoadBaselineList(key);
                if (BaselineFromOtherManagedBook(snap))
                {
                    // 基线属于其它受管词书 (上一本切换时被还原竞争盖进来的残留): 记为空。
                    snap = new List<string>();
                }
                BaselineLists[key] = snap;
                PersistBaselineList(key, BaselineLists[key]);
                MarkOwned(OwnedListKey, key);
            }
            TouchedListFields.Add(key);
            LogChange(key, list.Count, Sample(list));
            PersistList(key, list);
        }

        private static void SaveField(string key, string[] arr)
        {
            if (BookState() != 1) return;
            if (!BaselineArrays.ContainsKey(key))
            {
                string[] snap = LoadBaselineArray(key);
                if (BaselineFromOtherManagedBook(snap))
                {
                    snap = new string[0];
                }
                BaselineArrays[key] = snap;
                PersistBaselineArray(key, BaselineArrays[key]);
                MarkOwned(OwnedArrayKey, key);
            }
            TouchedArrayFields.Add(key);
            LogChange(key, arr.Length, Sample(arr));
            PersistArray(key, arr);
        }

        // 记下「这个字段被插件接管了」, 让下次启动(可能已经是别的词书)知道要还原。
        private static void MarkOwned(string ownedKey, string field)
        {
            try
            {
                int sourceSlot = LoadInt(OwnedSourceSlotKey, 0);
                if (sourceSlot <= 0)
                {
                    sourceSlot = SelfBookIndexOf(MyParameters.ChosenBook_Para);
                    if (sourceSlot > 0) ES3.Save(OwnedSourceSlotKey, sourceSlot);
                }
                List<string> owned = LoadStringList(ownedKey);
                if (owned.Contains(field)) return;
                owned.Add(field);
                ES3.Save(ownedKey, owned);
            }
            catch (Exception e) { WarnOnce("own:" + ownedKey, "写接管记录失败: " + e.Message); }
        }

        private static void ClearOwned()
        {
            try
            {
                ES3.Save(OwnedListKey, new List<string>());
                ES3.Save(OwnedArrayKey, new List<string>());
                ES3.Save(OwnedSourceSlotKey, 0);
            }
            catch (Exception e) { WarnOnce("own:clear", "清接管记录失败: " + e.Message); }
        }

        private static List<string> LoadStringList(string key)
        {
            try
            {
                List<string> v = ES3.Load<List<string>>(key, new List<string>());
                return (v == null) ? new List<string>() : v;
            }
            catch (Exception e)
            {
                WarnOnce("ld:" + key, "读取 " + key + " 失败: " + e.Message);
                return new List<string>();
            }
        }

        private static void PersistBaselineList(string key, List<string> value)
        {
            try { ES3.Save(BakPrefix + key, new List<string>(value ?? new List<string>())); }
            catch (Exception e) { WarnOnce("bak:" + key, "写 " + key + " 基线失败: " + e.Message); }
        }

        private static void PersistBaselineArray(string key, string[] value)
        {
            try { ES3.Save(BakPrefix + key, (string[])(value ?? new string[0]).Clone()); }
            catch (Exception e) { WarnOnce("bak:" + key, "写 " + key + " 基线失败: " + e.Message); }
        }

        private static List<string> LoadBaselineListFromDisk(string key)
        {
            try { return ES3.Load<List<string>>(BakPrefix + key, new List<string>()); }
            catch (Exception e)
            {
                WarnOnce("ldbak:" + key, "读取 " + key + " 基线失败: " + e.Message);
                return null;
            }
        }

        private static string[] LoadBaselineArrayFromDisk(string key)
        {
            try { return ES3.Load<string[]>(BakPrefix + key, new string[0]); }
            catch (Exception e)
            {
                WarnOnce("ldbak:" + key, "读取 " + key + " 基线失败: " + e.Message);
                return null;
            }
        }

        private static bool BaselineBelongsToOwnedBook(List<string> list)
        {
            if (list == null || list.Count == 0) return false;
            int slot = LoadInt(OwnedSourceSlotKey, 0);
            HashSet<string> words = OwnedBookWords(slot);
            if (words == null || words.Count == 0) return false;
            bool found = false;
            for (int i = 0; i < list.Count; i++)
            {
                string word = list[i];
                if (string.IsNullOrEmpty(word)) continue;
                found = true;
                if (!words.Contains(word)) return false;
            }
            return found;
        }

        private static bool BaselineBelongsToOwnedBook(string[] arr)
        {
            if (arr == null || arr.Length == 0) return false;
            int slot = LoadInt(OwnedSourceSlotKey, 0);
            HashSet<string> words = OwnedBookWords(slot);
            if (words == null || words.Count == 0) return false;
            bool found = false;
            for (int i = 0; i < arr.Length; i++)
            {
                string word = arr[i];
                if (string.IsNullOrEmpty(word)) continue;
                found = true;
                if (!words.Contains(word)) return false;
            }
            return found;
        }

        // 与 BaselineBelongsToOwnedBook 相反方向: 内容能否指纹命中**其它**受管语言。
        // 命中 = 这是上一本受管词书的残留 (还原竞争盖进来的), 还原时必须当空处理,
        // 绝不能在离开本书时把它恢复出去。识别不出 -> false, 保持保守旧行为。
        private static bool BaselineFromOtherManagedBook(IList<string> words)
        {
            try
            {
                if (words == null || words.Count == 0) return false;
                List<string> list = new List<string>(words);
                if (BookProfiles.Match(list) != null) return false;   // 完整命中 = 自己
                string prefix = BookProfiles.FingerprintOf(list);
                if (string.IsNullOrEmpty(prefix)) return false;
                for (int i = 0; i < BookProfiles.All.Length; i++)
                {
                    BookProfile p = BookProfiles.All[i];
                    if (p.Language == BookProfiles.Japanese) continue;
                    string fp = p.Fingerprint;
                    if (!string.IsNullOrEmpty(fp) && fp.Length >= prefix.Length &&
                        fp.StartsWith(prefix, StringComparison.Ordinal))
                        return true;
                }
                return false;
            }
            catch (Exception) { return false; }
        }

        private static HashSet<string> OwnedBookWords(int slot)
        {
            try
            {
                string path = System.IO.Path.Combine(Application.persistentDataPath, "MyBook.es3");
                if (slot > 0)
                {
                    string[] list = ES3.Load<string[]>("SelfBookList" + slot, path);
                    BookProfile profile = BookProfiles.Match(list);
                    if (profile != null && profile.Language == BookProfiles.Japanese)
                        return new HashSet<string>(list);
                    return null;
                }
                // 兼容安装这个隔离修复之前留下的接管记录：扫描已登记的完整
                // 日语槽位。找不到就不猜，保留原基线而不是误伤其它词书。
                for (int i = 1; i <= 4; i++)
                {
                    try
                    {
                        string[] list = ES3.Load<string[]>("SelfBookList" + i, path);
                        BookProfile profile = BookProfiles.Match(list);
                        if (profile != null && profile.Language == BookProfiles.Japanese)
                            return new HashSet<string>(list);
                    }
                    catch (Exception) { }
                }
                return null;
            }
            catch (Exception e)
            {
                WarnOnce("ownsource:" + slot, "读取接管词书槽位失败: " + e.Message);
                return null;
            }
        }

        // 改动前的存档值。必须在第一次 Persist 之前取, 取到的才是游戏自己的基线。
        private static List<string> LoadBaselineList(string key)
        {
            try { return ES3.Load<List<string>>(key, new List<string>()); }
            catch (Exception e)
            {
                WarnOnce("base:" + key, "读取 " + key + " 基线失败: " + e.Message);
                return new List<string>();
            }
        }

        private static string[] LoadBaselineArray(string key)
        {
            try { return ES3.Load<string[]>(key, new string[0]); }
            catch (Exception e)
            {
                WarnOnce("base:" + key, "读取 " + key + " 基线失败: " + e.Message);
                return new string[0];
            }
        }

        // 真正落盘: 游戏在多个读点会用 ES3.Load 覆盖内存, 不落盘就压不住残留的旧队列。
        private static void PersistList(string key, List<string> list)
        {
            try { ES3.Save(key, new List<string>(list)); }
            catch (Exception e) { WarnOnce("save:" + key, "写入 " + key + " 失败: " + e.Message); }
        }

        private static void PersistArray(string key, string[] arr)
        {
            try { ES3.Save(key, (string[])arr.Clone()); }
            catch (Exception e) { WarnOnce("save:" + key, "写入 " + key + " 失败: " + e.Message); }
        }

        // 插件现在会落盘, 所以不能再靠「从存档重读」回填(读到的会是插件自己的值)。
        // 用改动前记下的基线把内存和存档一起还原, 这样切到别的词书时, 别的词书看到的是
        // 游戏原本的队列, 插件也不会把自己的筛选结果带过去。
        //
        // 还原范围 = 本次会话动过的字段 ∪ 存档里的接管记录。后者不可省:
        // 「在日语词书里关掉游戏 -> 重启(游戏仍停在日语词书) -> 游戏内切到别的词书」
        // 这条路上本次进程一次都没写过, 只看内存标记会把日语队列留给别的词书。
        // 返回「本轮未完成的测试是否已被结束」。
        private static bool RestoreSharedFields()
        {
            if (OtherRestoreDeferred()) return false;   // 竞争守卫
            bool acted;
            bool cleared = RestoreQueues(out acted);
            if (!acted) return false;   // 没接管过任何队列: 别的词书原样不动, 不写它的存档
            // 只有插件真的接管过队列才动测试状态。
            // 词池 < 5 或队列被清空时必须结束本轮, 否则别的词书点「继续」会越界崩。
            bool ended = cleared || PoolTooShort();
            if (ended) MarkNoTestInProgress();
            TouchedListFields.Clear();
            TouchedArrayFields.Clear();
            TouchedIntFields.Clear();
            BaselineLists.Clear();
            BaselineArrays.Clear();
            ClearOwned();
            Log.LogInfo("JPWordList: 已恢复游戏共享队列基线，离开猫条词书后不保留插件状态");
            return ended;
        }

        // 统一还原核心: 逐字段优先用内存基线(本次会话第一次接管前的值), 没有才读存档基线
        // (上一次会话留下的)。只有基线的每个词都能严格归属到当时接管的完整词书
        // 时才清空；其它书（包括用户自己的日语书）基线照原样恢复。acted = 是否存在需要还原的字段。
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

            acted = listKeys.Count > 0 || arrKeys.Count > 0 || TouchedIntFields.Count > 0;
            return clearedAny;
        }

        private static void AddMissing(List<string> dest, List<string> src)
        {
            for (int i = 0; i < src.Count; i++)
                if (!dest.Contains(src[i])) dest.Add(src[i]);
        }

        // 词池 < 5 时游戏 MultipleChoiceGeneratorS9.GenerateOptions 会取空表越界崩。
        private static bool PoolTooShort()
        {
            List<string> pool = MyParameters.allTestWordsS10_Para;
            return pool == null || pool.Count < 5;
        }

        // ---------------- 跨词书启动守卫 ----------------

        // 场景: 在日语词书里测试到一半直接关掉游戏, 之后用**别的词书**继续那个未完成的测试。
        // 游戏只会照读存档, BookState() 又不是 1, 插件不会介入 -> 别的词书看到日语队列。
        // 插件落盘时留了「接管记录 + 接管前基线」, 这里在启动时把队列还原成接管前的样子。
        //
        // 版本兼容: 只读自己的字符串键, 不碰游戏数据库(wcpOnlyWord.db / wcpFullEng.db),
        // 也不引用游戏内部类型/方法; 对 MyParameters 字段一律走反射 + try/catch。
        // 游戏更新改了字段或库, 这里最坏是「还原失败并记一条日志」, 不会崩、不会写坏存档。
        private static void CrossBookGuard()
        {
            if (_crossBookGuardDone) return;
            if (!IsEnabled()) return;
            if (!BookReady()) return;            // 还没读档: 现在判断不了当前词书, 等下一轮
            _crossBookGuardDone = true;

            if (BookState() == 1) return;        // 当前就是日语词书: Enforce / 换书还原负责, 不动

            List<string> ownedLists = LoadStringList(OwnedListKey);
            List<string> ownedArrs = LoadStringList(OwnedArrayKey);
            if (ownedLists.Count == 0 && ownedArrs.Count == 0) return;   // 没接管过, 不动

            if (OtherRestoreDeferred())
            {
                _crossBookGuardDone = false;   // 下轮 Pre/Post/轮询再试
                return;
            }

            // 走和「游戏内切书」同一套还原逻辑, 两条路不会各自漂移。
            bool ended = RestoreSharedFields();
            Warn("跨词书守卫: 已还原插件接管前的测试队列" +
                 (ended ? " (残留日语队列改为清空并结束本轮测试)" : ""));
        }

        // 配置关闭不等于已经还原存档；Harmony 补丁会停用，但游戏仍可能在
        // 同一帧切换词书。因此这里不依赖 IsEnabled，只处理插件自己的接管记录。
        private static void CleanupDisabledState()
        {
            if (_disabledCleanupDone) return;
            if (!BookReady()) return;
            try
            {
                List<string> ownedLists = LoadStringList(OwnedListKey);
                List<string> ownedArrs = LoadStringList(OwnedArrayKey);
                if (ownedLists.Count > 0 || ownedArrs.Count > 0)
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

        // 清空队列后, 还要把「有测试没做完」的状态也清掉, 否则游戏会拿空队列去继续:
        // MultipleChoiceGeneratorS9.GenerateOptions 在词池 < 5 时会死循环取空表而崩。
        // 这里复刻游戏自己的「本轮完成」状态(SetS8Data/MultipleChoiceGeneratorS9 都这么写),
        // 「继续」按钮会自动变灰, 玩家重新开一次测试即可。
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
            Log.LogInfo("JPWordList: " + key + " -> " + count + " 词 (示例: " + sample + ") @" +
                (JapaneseBookSelected() ? "jp" : "other"));
        }

        internal static bool JapaneseBookSelected()
        {
            return BookState() == 1;
        }

// ---------------- 例句/释义 数据库自愈 (v1.7.6) ----------------
// 官方更新会覆盖 StreamingAssets 下的 .db, 把日文词条的释义(pron)和例句(sentence2)冲掉。
// 插件的工作不依赖 DB, 但「例句」只在 sentence2 里, 更新后会丢。启动后若发现探针词缺失,
// 就从 LocalLow 的补丁包(jp_db_payload)重灌一次; 写前先备份 DB, 全程 try/catch。
private const string DbPackDir = "jp_db_payload";

        // 宿主资源包的语言代码: packs/<PackLangCode>/manifest.json
        private const string PackLangCode = "ja";
private static readonly string[] DbProbes = new string[] { "歯医者", "続ける", "工業" };
private static bool _dbHealTried;
private static float _dbHealAt = -1f;

private static void TickDbHeal()
{
    if (_dbHealTried || _healDb == null || !_healDb.Value ||
        _allowLegacySharedDbWrites == null || !_allowLegacySharedDbWrites.Value) return;
    if (BookState() != 1) return;  // 只在受管日语词书实际载入后检查/写库
    if (_dbHealAt < 0f) { _dbHealAt = Time.unscaledTime + 8f; return; }   // 首次只排期, 避开加载
    if (Time.unscaledTime < _dbHealAt) return;
    string pack = System.IO.Path.Combine(Application.persistentDataPath, DbPackDir);
    if (!System.IO.Directory.Exists(pack)) { _dbHealTried = true; return; }
    string full = System.IO.Path.Combine(Application.streamingAssetsPath, "wcpFullEng.db");
    if (!System.IO.File.Exists(full)) { _dbHealTried = true; return; }
    string only = System.IO.Path.Combine(Application.streamingAssetsPath, "wcpOnlyWord.db");
    _dbHealTried = true;
    try
    {
        System.Threading.Thread t = new System.Threading.Thread(
            new System.Threading.ThreadStart(delegate { RunDbHeal(pack, full, only); }));
        t.IsBackground = true;
        t.Start();
    }
    catch (Exception e) { Warn("例句库自愈启动异常: " + e.Message); }
}

private static void RunDbHeal(string pack, string full, string only)
{
    try
    {
        if (!NeedsDbHeal(full))
        {
            InfoOnce("dbheal-skip", "例句库已是补丁状态, 不再重灌");
            return;
        }
        string fullPron = System.IO.Path.Combine(pack, "jp_pron.tsv");
        string fullSent = System.IO.Path.Combine(pack, "jp_sentences.tsv");
        string onlyPron = System.IO.Path.Combine(pack, "jp_only_pron.tsv");
        if (!System.IO.File.Exists(fullPron) || !System.IO.File.Exists(fullSent) ||
            !System.IO.File.Exists(onlyPron))
        {
            throw new System.IO.FileNotFoundException("jp_db_payload 不完整");
        }
        string stamp = DateTime.Now.ToString("yyyyMMdd_HHmmss");
        string bakDir = System.IO.Path.Combine(pack, "backup");
        System.IO.Directory.CreateDirectory(bakDir);
        System.IO.File.Copy(full, System.IO.Path.Combine(bakDir, "wcpFullEng.db.bak_" + stamp), true);
        if (System.IO.File.Exists(only))
        {
            System.IO.File.Copy(only, System.IO.Path.Combine(bakDir, "wcpOnlyWord.db.bak_" + stamp), true);
        }
        int n1 = ApplyDbPack(full, fullPron, fullSent);
        int n2 = 0;
        if (System.IO.File.Exists(only))
        {
            n2 = ApplyDbPack(only, onlyPron, null);
        }
        if (n1 == 0 || NeedsDbHeal(full))
            throw new InvalidOperationException("补丁回读校验失败");
        if (Log != null)
        {
            Log.LogInfo("JPWordList: 例句库已自动重灌 FullEng.pron+sent=" + n1 +
                        ", OnlyWord.pron=" + n2 + " (官方更新后恢复)");
        }
    }
    catch (Exception e) { Warn("例句库自愈失败(下次启动再试): " + e.Message); }
}

// 探针: 三个日文词只要有一个在 DB 里查不到, 就认为更新把补丁冲掉了
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
        }
        con.Close();
    }
    return false;
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

// 幂等: 先按词分批删旧行, 避免重复灌
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

// 反向还原导出时对 \\ / \t / 换行的转义
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
            if (Log != null) Log.LogWarning("JPWordList: " + s);
        }

        private static void WarnOnce(string key, string s)
        {
            if (!Warned.Add(key)) return;
            Warn(s);
        }

        // 同一个 key 只记一次(用于换形成功这类正常但值得留痕的事件, 不想按 Warning 刷屏)
        private static void InfoOnce(string key, string s)
        {
            if (!Warned.Add("info:" + key)) return;
            if (Log != null) Log.LogInfo("JPWordList: " + s);
        }
    }
}
