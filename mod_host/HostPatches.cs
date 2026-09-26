// WCP Host — 固定 Harmony 接线
//
// 补丁表只描述游戏机制，不包含语言名称。所有补丁入口都先经过当前
// identity gate；策略缺失时只让该功能降级，不让游戏方法被拦截。
using System;
using System.Collections.Generic;
using System.Reflection;
using HarmonyLib;

namespace WcpHost
{
    internal static class HostPatches
    {
        // Behavior hooks are installed only after a manifest and strategy
        // have both passed the runtime gate; identity itself is polled from
        // MyParameters during the migration period.  This avoids competing
        // with the legacy BookNameMod SonBookChoose patch.
        internal static void InstallFeatures(Harmony harmony)
        {
            if (harmony == null) return;
            // 第十一轮（2026-09-18）新增计数：`补丁:Sync` 实机 1827~1890ms 已归因到
            // harmony.Patch 本身（probe6：52 个 patch 点、均价 63ms/点，TypeByName 只占
            // 3%）。但「52」这个数字是离线复现出来的，实机到底命中几个从来没核过。
            // 接线成本 = 命中数 × 单点成本，所以必须把命中数写进日志，否则
            // 「1890ms」永远无法判断是"点太多"还是"单点太贵"。
            //
            // 第十二轮实机答案：**59 个**（0 个类型解析失败），单点 ~35.4ms
            // （2086.8 / 59）。所以它是"点太多"而不是"单点太贵" —— 搬走它（挪到
            // 加载期）比优化单点更值，前提是 Awake 期类型可解析，见 CensusAtAwake。
            _applied = 0; _attempted = 0; _typeMissing = 0;
            // 第十轮加探针：按组切段，下一次实机日志就能回答哪一组最贵。
            using (PerfProbe.Begin("补丁:场景钩子")) PatchGenericSceneHooks(harmony);
            using (PerfProbe.Begin("补丁:显示")) PatchDisplay(harmony);
            using (PerfProbe.Begin("补丁:词典")) PatchDictionary(harmony);
            using (PerfProbe.Begin("补丁:音频")) PatchAudio(harmony);
            using (PerfProbe.Begin("补丁:选词与刷新")) PatchSelectionAndRefresh(harmony);
            if (WcpHostPlugin.Log != null)
                WcpHostPlugin.Log.LogInfo("WcpHost: Harmony 接线完成 — 命中目标方法 " + _applied +
                    " 个（harmony.Patch 调用 " + _attempted + " 次，类型解析失败 " + _typeMissing +
                    " 个；单点失败已按 warn 逐条打印）");
        }

        // 干跑普查（第十二轮）已删除：第十三轮把接线直接搬到了 Awake，
        // InstallFeatures 自己的汇总行（命中 N 个 / 解析失败 K 个）就是诊断，
        // 普查成了纯开销。保留 _applied/_attempted/_typeMissing 记账 ——
        // 汇总行还在用。
        // 接线记账（第十一轮）：只用于日志，不参与任何判定。
        private static int _applied;
        private static int _attempted;
        private static int _typeMissing;

        private static void PatchGenericSceneHooks(Harmony harmony)
        {
            string[] prefixTypes = new string[] {
                "InitializeManagerS2", "WordListManagerS7", "S3ScoreShow",
                "LifeAndScoreManagerS15", "showWordS17", "RandomButtonInvoker",
                "MultipleChoiceGenerator", "MultipleChoiceGeneratorS9", "SetS8Data" };
            string[] postfixTypes = new string[] {
                "ChooseWordManager", "InitializeManagerS2", "updateNewLearnWord",
                "WordListManagerS7", "SetS8Data", "ButtonEquivalence", "S7NumberAdd",
                "ColorInputFieldS17", "MultipleChoiceGenerator", "RandomButtonInvoker",
                "clickChangeImageSource" };
            string[] sceneMethods = new string[] { "Awake", "Start" };
            string[] postfixMethods = new string[] {
                "Awake", "Start", "FightList", "setFightWord", "setAsFightWord",
                "setAsNewLearnWord", "setAsNewReviewWord", "SwitchSelfChosenMode",
                "UpdateThis", "ResetTestListQuick", "ResetTestListQuick_FreeChoose",
                "ResetExtraReviewList", "ResetExtraReviewList_FreeChoose",
                "ResetExtraStudyList", "ResetExtraStudyList_FreeChoose",
                "ResetDailyStudyList", "ResetDailyReviewList",
                "Get_TodayNewLearnWordForFight", "Get_TodayNewReviewWordForFight",
                "GetNewWord", "InvokeRandomButton", "StartQuickTest" };
            for (int i = 0; i < prefixTypes.Length; i++)
                PatchSet(harmony, prefixTypes[i], sceneMethods,
                    AccessTools.Method(typeof(HostPatches), "EnforcePrefix"), true);
            for (int i = 0; i < postfixTypes.Length; i++)
                PatchSet(harmony, postfixTypes[i], postfixMethods,
                    AccessTools.Method(typeof(HostPatches), "EnforcePostfix"), false);
            PatchOne(harmony, "SetS8Data", "SetAsLearnedTest", null,
                AccessTools.Method(typeof(HostPatches), "EnforcePostfix"));
            PatchOne(harmony, "MultipleChoiceGeneratorS9", "Start",
                AccessTools.Method(typeof(HostPatches), "EnforcePrefix"), null);
            PatchOne(harmony, "MultipleChoiceGeneratorS9", "GenerateOptions",
                AccessTools.Method(typeof(HostPatches), "EnforcePrefix"), null);
        }

        private static void PatchDisplay(Harmony harmony)
        {
            PatchOne(harmony, "MultipleChoiceGenerator", "GenerateOptions",
                AccessTools.Method(typeof(HostPatches), "RecoverBookPrefix"),
                AccessTools.Method(typeof(HostPatches), "MultipleChoicePostfix"));
            PatchOne(harmony, "MultipleChoiceGeneratorS9", "GenerateOptions", null,
                AccessTools.Method(typeof(HostPatches), "MultipleChoiceS9Postfix"));
            PatchOne(harmony, "MultipleChoiceGeneratorS9", "showWordAndMeaning", null,
                AccessTools.Method(typeof(HostPatches), "ShowWordAndMeaningS9Postfix"));
            PatchOne(harmony, "SetInputFieldValueS8", "ShowTheWord", null,
                AccessTools.Method(typeof(HostPatches), "ShowTheWordPostfix"));
        }

        private static void PatchDictionary(Harmony harmony)
        {
            string[] types = new string[] { "DatabaseManagerS8", "S8checkWordMeaning",
                "ButtonTextTransfer" };
            for (int i = 0; i < types.Length; i++)
                PatchOne(harmony, types[i], "OnSearchButtonClick", null,
                    AccessTools.Method(typeof(HostPatches), "DictionaryPostfix"));
            string[] answerMethods = new string[] { "ShowAnswer", "ShowAnswerForStudy",
                "ShowAnswerNoAutoVoice" };
            for (int i = 0; i < answerMethods.Length; i++)
                PatchOne(harmony, "showTheAnswerS8", answerMethods[i], null,
                    AccessTools.Method(typeof(HostPatches), "AnswerPostfix"));
        }

        private static void PatchAudio(Harmony harmony)
        {
            PatchOne(harmony, "VocabularyAudioPlayer", "PlayWordAudio",
                AccessTools.Method(typeof(HostPatches), "WordAudioPrefix"), null);
            PatchOne(harmony, "SoundTheWordS8", "OnButton1Click",
                AccessTools.Method(typeof(HostPatches), "SentenceTtsPrefix"), null);
            // 打怪听音选词/切水果的 AI 发音触发器: USgs.ReceiveTextToSpeech
            // 是英语 ONNX TTS 的统一入口，受管语言下由宿主按词形路由 pack
            // 音频，未命中再放行（与 PlayWordAudio 的放行语义一致）。
            PatchOne(harmony, "UnityText2Speech.USgs", "ReceiveTextToSpeech",
                AccessTools.Method(typeof(HostPatches), "UsgsTtsPrefix"), null);
        }

        private static void PatchSelectionAndRefresh(Harmony harmony)
        {
            // ResetTestListQuick 调用这些静态选词函数后才保存测试队列并打开场景。
            // 在选词出口替换结果，避免全局已学词的法英同形词进入本书快速测试。
            string[] quickTests = new string[] { "TestWordPos", "TestWordNeg", "TestWordRan",
                "TestWordPosOff", "TestWordNegOff", "TestWordRanOff" };
            PatchSet(harmony, "ChooseWordManager", quickTests,
                AccessTools.Method(typeof(HostPatches), "QuickTestPrefix"), true);
            PatchOne(harmony, "PageController", "SetThis",
                AccessTools.Method(typeof(HostPatches), "EnforcePrefix"), null);
            PatchOne(harmony, "GoToAllS9", "ArrayToAll", null,
                AccessTools.Method(typeof(HostPatches), "EnforcePostfix"));
            PatchOne(harmony, "SwitchCurrentArrayS9", "SwitchThis", null,
                AccessTools.Method(typeof(HostPatches), "EnforcePostfix"));
            // 补池入口: 受管词书下由宿主用本书词池接管，跳过全局已学词典与占位词。
            PatchOne(harmony, "ChooseWordManager", "AddWordsToSelfChosenList",
                AccessTools.Method(typeof(HostPatches), "PoolPrefix"), null);
            PatchOne(harmony, "SetInputFieldValueS8", "changeKnownFuzzUnknownTimes", null,
                AccessTools.Method(typeof(HostPatches), "EnforcePostfix"));
            // 战斗场景会从存档重新读一遍词表并缓存到 WithInfo; 读完之后再校正一次。
            PatchOne(harmony, "WordListManagerS7", "Start", null,
                AccessTools.Method(typeof(HostPatches), "FightListScenePostfix"));
            PatchOne(harmony, "WordListManagerS7", "Start",
                AccessTools.Method(typeof(HostPatches), "RecoverBookPrefix"), null);
            PatchOne(harmony, "S3ScoreShow", "Start",
                AccessTools.Method(typeof(HostPatches), "RecoverBookPrefix"), null);
            PatchOne(harmony, "S3ScoreShow", "Awake",
                AccessTools.Method(typeof(HostPatches), "RecoverBookPrefix"), null);
        }

        private static void EnforcePrefix()
        {
            WcpHostPlugin plugin = WcpHostPlugin.Instance;
            if (plugin != null) plugin.EnforceNowForScene();
        }

        private static void EnforcePostfix()
        {
            WcpHostPlugin plugin = WcpHostPlugin.Instance;
            if (plugin != null) plugin.EnforceNowForScene();
        }

        private static bool PoolPrefix(ref List<string> S7TestWordList_Para, int num)
        {
            WcpHostPlugin plugin = WcpHostPlugin.Instance;
            if (plugin == null || plugin.Runtime == null) return true;
            return plugin.Runtime.PrefixPool(ref S7TestWordList_Para, num);
        }

        private static bool QuickTestPrefix(int __0, ref List<string> __result,
                                            MethodBase __originalMethod)
        {
            WcpHostPlugin plugin = WcpHostPlugin.Instance;
            if (plugin == null || plugin.Runtime == null) return true;
            return plugin.Runtime.PrefixQuickTest(__0, __originalMethod.Name, ref __result);
        }

        private static void FightListScenePostfix(object __instance)
        {
            WcpHostPlugin plugin = WcpHostPlugin.Instance;
            if (plugin != null && plugin.Runtime != null)
                plugin.Runtime.PostFightListScene(__instance);
        }

        private static void MultipleChoicePostfix(object __instance)
        {
            WcpHostPlugin plugin = WcpHostPlugin.Instance;
            if (plugin != null && plugin.Runtime != null)
                plugin.Runtime.PostMultipleChoice(__instance);
        }

        private static void RecoverBookPrefix()
        {
            WcpHostPlugin plugin = WcpHostPlugin.Instance;
            if (plugin != null) plugin.RecoverBattleBookForScene();
        }

        private static void MultipleChoiceS9Postfix(object __instance)
        {
            WcpHostPlugin plugin = WcpHostPlugin.Instance;
            if (plugin != null && plugin.Runtime != null)
                plugin.Runtime.PostMultipleChoiceS9(__instance);
        }

        private static void ShowWordAndMeaningS9Postfix(object __instance)
        {
            WcpHostPlugin plugin = WcpHostPlugin.Instance;
            if (plugin != null && plugin.Runtime != null)
                plugin.Runtime.PostShowWordAndMeaningS9(__instance);
        }

        private static void ShowTheWordPostfix(object __instance)
        {
            WcpHostPlugin plugin = WcpHostPlugin.Instance;
            if (plugin != null && plugin.Runtime != null)
                plugin.Runtime.PostShowTheWord(__instance);
        }

        private static void DictionaryPostfix(object __instance)
        {
            WcpHostPlugin plugin = WcpHostPlugin.Instance;
            if (plugin != null && plugin.Runtime != null)
                plugin.Runtime.PostDictionary(__instance);
        }

        private static void AnswerPostfix(object __instance)
        {
            WcpHostPlugin plugin = WcpHostPlugin.Instance;
            if (plugin != null && plugin.Runtime != null)
                plugin.Runtime.PostAnswer(__instance);
        }

        // 受管语言下拦截英语 ONNX TTS: 词形可路由到 pack 音频时返回 false
        // （跳过英语 TTS，宿主已播本地音）；未命中返回 true 放行英语 TTS。
        private static bool UsgsTtsPrefix(object __instance, string text)
        {
            WcpHostPlugin plugin = WcpHostPlugin.Instance;
            if (plugin == null || plugin.Runtime == null) return true;
            return !plugin.Runtime.BlockEnglishWordTts(__instance, text);
        }

        private static bool WordAudioPrefix(object __instance)
        {
            WcpHostPlugin plugin = WcpHostPlugin.Instance;
            return plugin == null || plugin.Runtime == null ||
                   plugin.Runtime.PrefixWordAudio(__instance);
        }

        private static bool SentenceTtsPrefix(object __instance)
        {
            WcpHostPlugin plugin = WcpHostPlugin.Instance;
            if (plugin == null || plugin.Runtime == null) return true;
            return !plugin.Runtime.BlockEnglishSentenceTts(__instance);
        }

        private static void PatchSet(Harmony harmony, string typeName, string[] names,
                                     MethodInfo patch, bool prefix)
        {
            Type type = AccessTools.TypeByName(typeName);
            if (type == null) { _typeMissing++; return; }
            List<MethodInfo> methods = AccessTools.GetDeclaredMethods(type);
            for (int i = 0; i < methods.Count; i++)
            {
                MethodInfo method = methods[i];
                if (!NameIn(method.Name, names) || method.IsAbstract || patch == null) continue;
                try
                {
                    HarmonyMethod hm = new HarmonyMethod(patch);
                    _attempted++;
                    if (prefix) harmony.Patch(method, hm, null);
                    else harmony.Patch(method, null, hm);
                    _applied++;
                }
                catch (Exception e)
                {
                    if (WcpHostPlugin.Log != null)
                        WcpHostPlugin.Log.LogWarning("WcpHost: patch 失败 " + typeName + "." +
                            method.Name + ": " + e.Message);
                }
            }
        }

        private static void PatchOne(Harmony harmony, string typeName, string methodName,
                                     MethodInfo prefix, MethodInfo postfix)
        {
            Type type = AccessTools.TypeByName(typeName);
            if (type == null) { _typeMissing++; return; }
            MethodInfo target = AccessTools.Method(type, methodName);
            if (target == null) return;
            try
            {
                _attempted++;
                harmony.Patch(target,
                    prefix == null ? null : new HarmonyMethod(prefix),
                    postfix == null ? null : new HarmonyMethod(postfix));
                _applied++;
            }
            catch (Exception e)
            {
                if (WcpHostPlugin.Log != null)
                    WcpHostPlugin.Log.LogWarning("WcpHost: patch 失败 " + typeName + "." +
                        methodName + ": " + e.Message);
            }
        }

        private static bool NameIn(string name, string[] names)
        {
            for (int i = 0; i < names.Length; i++)
                if (name == names[i]) return true;
            return false;
        }
    }
}
