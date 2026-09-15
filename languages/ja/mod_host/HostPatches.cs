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
            PatchGenericSceneHooks(harmony);
            PatchDisplay(harmony);
            PatchDictionary(harmony);
            PatchAudio(harmony);
            PatchSelectionAndRefresh(harmony);
        }

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
            PatchOne(harmony, "MultipleChoiceGenerator", "GenerateOptions", null,
                AccessTools.Method(typeof(HostPatches), "MultipleChoicePostfix"));
            PatchOne(harmony, "MultipleChoiceGeneratorS9", "GenerateOptions", null,
                AccessTools.Method(typeof(HostPatches), "MultipleChoiceS9Postfix"));
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
        }

        private static void PatchSelectionAndRefresh(Harmony harmony)
        {
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

        private static void MultipleChoiceS9Postfix(object __instance)
        {
            WcpHostPlugin plugin = WcpHostPlugin.Instance;
            if (plugin != null && plugin.Runtime != null)
                plugin.Runtime.PostMultipleChoiceS9(__instance);
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
            if (type == null) return;
            List<MethodInfo> methods = AccessTools.GetDeclaredMethods(type);
            for (int i = 0; i < methods.Count; i++)
            {
                MethodInfo method = methods[i];
                if (!NameIn(method.Name, names) || method.IsAbstract || patch == null) continue;
                try
                {
                    HarmonyMethod hm = new HarmonyMethod(patch);
                    if (prefix) harmony.Patch(method, hm, null);
                    else harmony.Patch(method, null, hm);
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
            if (type == null) return;
            MethodInfo target = AccessTools.Method(type, methodName);
            if (target == null) return;
            try
            {
                harmony.Patch(target,
                    prefix == null ? null : new HarmonyMethod(prefix),
                    postfix == null ? null : new HarmonyMethod(postfix));
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
