// WCP Host — 语言无关的运行时服务
//
// 这里承载固定的游戏接线：词书身份确认后，宿主把队列、题面、查词、
// 单词音频和例句按钮交给当前 ILanguageStrategy。代码不包含任何语言
// 专属路径或语言分支；语言资源只从当前 manifest 的 ResourceRouter 取得。
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using BepInEx.Logging;
using HarmonyLib;
using TMPro;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.UI;

namespace WcpHost
{
    internal sealed class HostRuntime
    {
        private readonly WcpHostPlugin _plugin;
        private readonly BookRegistry _registry;
        private readonly ResourceRouter _router;
        private readonly StrategyRegistry _strategies;
        private readonly TakeoverScope _scope = new TakeoverScope();
        private readonly Dictionary<TMP_Text, string> _labelBackup =
            new Dictionary<TMP_Text, string>();
        private readonly Dictionary<TMP_Text, string> _labelWritten =
            new Dictionary<TMP_Text, string>();
        private SentenceAudioService _sentenceAudio;
        private HostAudioPlayer _audio;
        private IList<string> _activeWords;
        private string _activeProfileId;
        private bool _leftOnce;
        private bool _staleRecoveryAttempted;

        internal HostRuntime(WcpHostPlugin plugin, BookRegistry registry,
                             ResourceRouter router, StrategyRegistry strategies)
        {
            _plugin = plugin;
            _registry = registry;
            _router = router;
            _strategies = strategies;
            // 学习进度来源: 只用于"本书已学"优先排序，词池本身永远只从本书构造。
            TakeoverScope.StatsProvider = GameLearnedStats.FromGame;
            TakeoverScope.WarnSink = Warn;
        }

        internal string ActiveProfileId { get { return _activeProfileId; } }
        internal LanguageManifest ActiveManifest { get { return _router == null ? null : _router.Active; } }
        internal ILanguageStrategy ActiveStrategy
        {
            get
            {
                if (_activeProfileId == null || _strategies == null) return null;
                return _strategies.ForProfile(_activeProfileId);
            }
        }
        internal bool IsActive { get { return _activeProfileId != null && ActiveManifest != null; } }
        internal IList<string> ActiveWords { get { return _activeWords; } }

        internal void SetIdentity(LanguageManifest manifest, IList<string> words)
        {
            string next = manifest == null ? null : manifest.Profile.Id;
            if (string.Equals(_activeProfileId, next, StringComparison.Ordinal))
            {
                _activeWords = words;
                if (IsActive && ActiveStrategy != null) _scope.Enforce();
                return;
            }

            LeaveCurrent();
            _activeProfileId = next;
            _activeWords = words == null ? null : new List<string>(words);
            if (manifest == null || words == null || words.Count == 0)
            {
                _router.SetActive(null);
                _staleRecoveryAttempted = true;
                return;
            }

            _router.SetActive(manifest.Profile.Id);
            if (ActiveStrategy == null)
                WcpHostPlugin.Log.LogWarning("WcpHost: 当前语言包没有可用策略，保留身份但不接管行为: " +
                    manifest.Profile.Id);
            else
            {
                _scope.Enter(manifest, _activeWords);
                EnsureServices();
                WcpHostPlugin.Log.LogInfo("WcpHost: 接管语言包 " + manifest.Profile.Language +
                    " / " + manifest.Profile.Id);
            }
            _leftOnce = false;
        }

        internal void SetInactive()
        {
            if (_activeProfileId == null)
            {
                if (!_staleRecoveryAttempted)
                {
                    _scope.RecoverStale(_registry, null);
                    _staleRecoveryAttempted = true;
                }
                return;
            }
            LeaveCurrent();
            _activeProfileId = null;
            _activeWords = null;
            _router.SetActive(null);
            _staleRecoveryAttempted = true;
        }

        internal void Tick()
        {
            if (!IsActive || ActiveStrategy == null) return;
            EnsureServices();
            try { _scope.Enforce(); }
            catch (Exception e) { Warn("运行态队列校正失败: " + e.Message); }
            try { ScanBookLabels(); }
            catch (Exception e) { Warn("书名/UI 扫描失败: " + e.Message); }
            try
            {
                _sentenceAudio.Tick();
            }
            catch (Exception e) { Warn("例句按钮扫描失败: " + e.Message); }
        }

        internal void OnDisabled()
        {
            SetInactive();
            if (_sentenceAudio != null) _sentenceAudio.Leave();
        }

        internal bool BlockEnglishSentenceTts(object instance)
        {
            if (!IsActive || _sentenceAudio == null) return false;
            return _sentenceAudio.IsOwnedReadButton(instance);
        }

        internal bool PrefixWordAudio(object instance)
        {
            if (!IsActive || ActiveStrategy == null || instance == null) return true;
            TMP_Text text = GameAdapter.InstanceField(instance, "text1") as TMP_Text;
            if (text == null || string.IsNullOrEmpty(text.text)) return true;
            string displayed = text.text.Trim();
            string canonical = CurrentWord(displayed);
            string lookup;
            try { lookup = ActiveStrategy.AudioLookupForm(displayed, canonical); }
            catch (Exception e)
            {
                Warn("策略音频词形失败: " + e.Message);
                return true;
            }
            if (string.IsNullOrEmpty(lookup)) lookup = canonical;
            string path = _router.Resolve(ResourceKind.WordAudio, lookup);
            if (string.IsNullOrEmpty(path) || !File.Exists(path)) return true;
            EnsureServices();
            _audio.Play(path);
            return false;
        }

        internal void PostMultipleChoice(object instance)
        {
            if (!IsActive || ActiveStrategy == null || instance == null) return;
            try
            {
                string target = CurrentFightWord();
                TMP_Text[] options = new TMP_Text[] {
                    FieldText(instance, "option1Text"), FieldText(instance, "option2Text"),
                    FieldText(instance, "option3Text"), FieldText(instance, "option4Text") };
                TMP_Text[] small = new TMP_Text[] {
                    FieldText(instance, "option1Text_SM"), FieldText(instance, "option2Text_SM"),
                    FieldText(instance, "option3Text_SM"), FieldText(instance, "option4Text_SM") };
                TMP_Text[] words = new TMP_Text[] {
                    FieldText(instance, "word1Text"), FieldText(instance, "word2Text"),
                    FieldText(instance, "word3Text"), FieldText(instance, "word4Text") };
                string targetMeaning = null;
                for (int i = 0; i < options.Length; i++)
                {
                    if (options[i] == null || words[i] == null) continue;
                    string word = words[i].text;
                    if (word == target) targetMeaning = options[i].text;
                }
                for (int i = 0; i < options.Length; i++)
                {
                    if (options[i] == null || words[i] == null) continue;
                    string display = ActiveStrategy.OptionDisplay(words[i].text, options[i].text);
                    if (display == null) continue;
                    options[i].text = display;
                    if (small[i] != null) small[i].text = display;
                }
                if (!string.IsNullOrEmpty(target))
                {
                    string stem = ActiveStrategy.StemDisplay(target, targetMeaning);
                    if (!string.IsNullOrEmpty(stem)) SetQuestionStem(target, stem);
                }
            }
            catch (Exception e) { Warn("四选一题面改写失败: " + e.Message); }
        }

        internal void PostMultipleChoiceS9(object instance)
        {
            if (!IsActive || ActiveStrategy == null || instance == null) return;
            try
            {
                IList options = ToObjectList(GameAdapter.InstanceField(instance, "optionText"));
                if (options == null) return;
                string[] optionWords = new string[] {
                    StaticString("S9Option1_Para"), StaticString("S9Option2_Para"),
                    StaticString("S9Option3_Para"), StaticString("S9Option4_Para") };
                string target = CurrentTestWord();
                string meaning = null;
                for (int i = 0; i < options.Count && i < optionWords.Length; i++)
                {
                    TMP_Text text = options[i] as TMP_Text;
                    if (text != null && optionWords[i] == target) meaning = text.text;
                }
                for (int i = 0; i < options.Count && i < optionWords.Length; i++)
                {
                    TMP_Text text = options[i] as TMP_Text;
                    if (text == null || string.IsNullOrEmpty(optionWords[i])) continue;
                    text.text = ActiveStrategy.OptionDisplay(optionWords[i], text.text);
                }
                if (!string.IsNullOrEmpty(target))
                    SetQuestionStem(target, ActiveStrategy.StemDisplay(target, meaning));
            }
            catch (Exception e) { Warn("已学词测试题面改写失败: " + e.Message); }
        }

        internal void PostShowTheWord(object instance)
        {
            if (!IsActive || ActiveStrategy == null || instance == null) return;
            if (!string.Equals(StaticString("S8ThisMode_Para"), "已学词测试",
                               StringComparison.Ordinal)) return;
            TMP_InputField input = GameAdapter.InstanceField(instance, "inputField") as TMP_InputField;
            if (input == null || string.IsNullOrEmpty(input.text)) return;
            string display = ActiveStrategy.StemDisplay(input.text, null);
            if (!string.IsNullOrEmpty(display)) SetQuestionStem(input.text, display);
        }

        internal void PostDictionary(object instance)
        {
            if (!IsActive || ActiveStrategy == null || instance == null) return;
            try
            {
                string word = StaticString("checkWordInDictionary");
                if (string.IsNullOrEmpty(word)) return;
                string meaning, phonic;
                if (!ActiveStrategy.ProvideMeaning(word, out meaning, out phonic)) return;
                TMP_Text meaningText = GameAdapter.InstanceField(instance, "meaningText") as TMP_Text;
                TMP_Text us = GameAdapter.InstanceField(instance, "usPhoneticText") as TMP_Text;
                TMP_Text uk = GameAdapter.InstanceField(instance, "ukPhoneticText") as TMP_Text;
                if (meaningText != null && !string.IsNullOrEmpty(meaning))
                    meaningText.text = meaning + Environment.NewLine;
                if (us != null && !string.IsNullOrEmpty(phonic)) us.text = phonic;
                if (uk != null && !string.IsNullOrEmpty(phonic)) uk.text = string.Empty;
            }
            catch (Exception e) { Warn("查词面板改写失败: " + e.Message); }
        }

        internal void PostAnswer(object instance)
        {
            if (!IsActive || instance == null) return;
            TMP_Text dst = GameAdapter.InstanceField(instance, "phonicsText") as TMP_Text;
            if (dst == null) return;
            TMP_Text us = GameAdapter.InstanceField(instance, "Target_phonicsUSText") as TMP_Text;
            TMP_Text uk = GameAdapter.InstanceField(instance, "Target_phonicsUKText") as TMP_Text;
            string value = us == null ? null : us.text;
            if (string.IsNullOrEmpty(value) && uk != null) value = uk.text;
            if (!string.IsNullOrEmpty(value)) dst.text = value.Trim();
        }

        internal void EnforceNow()
        {
            if (IsActive && ActiveStrategy != null) _scope.Enforce();
        }

        // ── 战斗词池接管 ──
        //
        // ChooseWordManager.AddWordsToSelfChosenList 是游戏唯一的补池入口:
        // 它从**全局** HaveLearnedDictionary 取词，补不满再塞 one..five 占位词。
        // 受管词书下这条路必须被换掉: 由宿主用本书词池替代，并跳过原方法。
        // 返回值 = true 表示交回游戏处理。
        internal bool PrefixPool(ref List<string> list, int requested)
        {
            if (!IsActive || ActiveStrategy == null) return true;
            try
            {
                List<string> rebuilt = _scope.RebuildPool("S7TestWordList_Para", list, requested);
                if (rebuilt != null && !SameWords(list, rebuilt))
                {
                    list = rebuilt;
                    GameAdapter.SetStaticField("MyParameters", "S7TestWordList_Para", rebuilt);
                    GameAdapter.Es3Save("S7TestWordList_Para", rebuilt);
                }
                // 受管词书下补池一律由宿主负责: 即使本次没有变化，也不能让游戏
                // 回退到全局词典或 one..five 占位词。
                return false;
            }
            catch (Exception e)
            {
                Warn("战斗词池接管失败: " + e.Message);
                return true;
            }
        }

        // WordListManagerS7.Start 会从存档重新读一遍战斗词表（并在地毯式兜底里
        // 塞 one..five）。宿主在场景边界再校正一次；若场景缓存已经是旧表，
        // 就地刷新它，避免玩家在切书后的第一场战斗里看到上一门语言的词。
        internal void PostFightListScene(object instance)
        {
            EnforceNow();
            if (!IsActive || instance == null) return;
            try
            {
                IList<string> pool = GameAdapter.ToWordList(
                    GameAdapter.StaticField("MyParameters", "S7TestWordList_Para"));
                if (pool == null || pool.Count == 0) return;
                IList<string> withInfo = GameAdapter.ToWordList(
                    GameAdapter.StaticField("MyParameters", "S7TestWordList_WithInfo"));
                if (withInfo != null && withInfo.Count == pool.Count) return;

                List<string> rebuilt = new List<string>(pool.Count);
                for (int i = 0; i < pool.Count; i++) rebuilt.Add(pool[i] + "##0");
                GameAdapter.SetStaticField("MyParameters", "S7TestWordList_WithInfo", rebuilt);
                GameAdapter.SetInstanceField(instance, "maxPage", (pool.Count + 11) / 12);
                InvokeNoArg(instance, "ShowWordList");
            }
            catch (Exception e)
            {
                Warn("战斗场景词表刷新失败: " + e.Message);
            }
        }

        internal string CurrentWord(string displayed)
        {
            string value = CurrentTestWord();
            if (string.Equals(value, displayed, StringComparison.Ordinal)) return value;
            value = CurrentFightWord();
            if (string.Equals(value, displayed, StringComparison.Ordinal)) return value;
            if (!string.IsNullOrEmpty(displayed) && _activeWords != null)
            {
                for (int i = 0; i < _activeWords.Count; i++)
                    if (string.Equals(_activeWords[i], displayed, StringComparison.Ordinal)) return displayed;
            }
            return value;
        }

        internal void PlayFile(string file)
        {
            EnsureServices();
            if (_audio != null) _audio.Play(file);
        }

        private static bool SameWords(IList<string> a, IList<string> b)
        {
            if (a == null || b == null || a.Count != b.Count) return false;
            for (int i = 0; i < a.Count; i++)
                if (!string.Equals(a[i], b[i], StringComparison.Ordinal)) return false;
            return true;
        }

        private static void InvokeNoArg(object instance, string method)
        {
            if (instance == null) return;
            MethodInfo info = instance.GetType().GetMethod(method,
                BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
            if (info != null && info.GetParameters().Length == 0) info.Invoke(instance, null);
        }

        private void LeaveCurrent()
        {
            if (_leftOnce) return;
            _leftOnce = true;
            if (_sentenceAudio != null) _sentenceAudio.Leave();
            RestoreLabels();
            _scope.Leave();
        }

        private void EnsureServices()
        {
            if (_audio == null)
            {
                GameObject go = new GameObject("WcpHostAudio");
                UnityEngine.Object.DontDestroyOnLoad(go);
                _audio = go.AddComponent<HostAudioPlayer>();
            }
            if (_sentenceAudio == null)
                _sentenceAudio = new SentenceAudioService(this, _audio);
        }

        private void ScanBookLabels()
        {
            UnityEngine.Object[] all = Resources.FindObjectsOfTypeAll(typeof(TMP_Text));
            for (int i = 0; i < all.Length; i++)
            {
                TMP_Text text = all[i] as TMP_Text;
                if (text == null || string.IsNullOrEmpty(text.text)) continue;
                int slot = GameAdapter.SlotOfBookName(text.text);
                if (slot > 0)
                {
                    LanguageManifest m = ManifestForSlot(slot);
                    if (m != null && text.text != m.Profile.DisplayName)
                    {
                        if (!_labelBackup.ContainsKey(text)) _labelBackup[text] = text.text;
                        text.text = m.Profile.DisplayName;
                        _labelWritten[text] = m.Profile.DisplayName;
                    }
                    continue;
                }
                if (!IsAccentLabel(text.text) || !HasButtonAncestor(text)) continue;
                if (!_labelBackup.ContainsKey(text)) _labelBackup[text] = text.text;
                string value = ActiveManifest.Profile.Language.ToUpperInvariant();
                text.text = value;
                _labelWritten[text] = value;
            }
        }

        private void RestoreLabels()
        {
            foreach (KeyValuePair<TMP_Text, string> pair in _labelBackup)
            {
                TMP_Text text = pair.Key;
                string written;
                if (text != null && _labelWritten.TryGetValue(text, out written) && text.text == written)
                    text.text = pair.Value;
            }
            _labelBackup.Clear();
            _labelWritten.Clear();
        }

        private LanguageManifest ManifestForSlot(int slot)
        {
            IList<string> words = GameAdapter.SlotWords(slot);
            return words == null ? null : _registry.ByProfileId(_registry.Match(words) == null
                ? null : _registry.Match(words).Id);
        }

        private string StaticString(string field)
        {
            object value = GameAdapter.StaticField("MyParameters", field);
            return value as string;
        }

        private string CurrentFightWord()
        {
            IList<string> values = GameAdapter.ToWordList(
                GameAdapter.StaticField("MyParameters", "S7TestWordList_Para"));
            int index = StaticInt("S7Progress_Para");
            return At(values, index);
        }

        private string CurrentTestWord()
        {
            IList<string> values = GameAdapter.ToWordList(
                GameAdapter.StaticField("MyParameters", "allTestWordsS10_Para"));
            int index = StaticInt("S8Progress_Para");
            return At(values, index);
        }

        private int StaticInt(string field)
        {
            object value = GameAdapter.StaticField("MyParameters", field);
            return value is int ? (int)value : 0;
        }

        private static string At(IList<string> values, int index)
        {
            return values == null || index < 0 || index >= values.Count ? null : values[index];
        }

        private static TMP_Text FieldText(object instance, string field)
        {
            return GameAdapter.InstanceField(instance, field) as TMP_Text;
        }

        private static IList ToObjectList(object value)
        {
            if (value == null || value is string) return null;
            IList list = value as IList;
            if (list != null) return list;
            return null;
        }

        private void SetQuestionStem(string canonical, string display)
        {
            if (string.IsNullOrEmpty(canonical) || string.IsNullOrEmpty(display)) return;
            Type sifType = AccessTools.TypeByName("SetInputFieldValueS8");
            if (sifType != null)
            {
                UnityEngine.Object[] sifs = Resources.FindObjectsOfTypeAll(sifType);
                for (int i = 0; i < sifs.Length; i++)
                {
                    TMP_InputField input = GameAdapter.InstanceField(sifs[i], "inputField") as TMP_InputField;
                    if (input != null && input.text == canonical) input.text = display;
                }
            }
            Type vapType = AccessTools.TypeByName("VocabularyAudioPlayer");
            if (vapType != null)
            {
                UnityEngine.Object[] vaps = Resources.FindObjectsOfTypeAll(vapType);
                for (int i = 0; i < vaps.Length; i++)
                {
                    TMP_Text text = GameAdapter.InstanceField(vaps[i], "text1") as TMP_Text;
                    if (text != null && text.text == canonical) text.text = display;
                }
            }
        }

        private static bool IsAccentLabel(string value)
        {
            string s = (value ?? string.Empty).Trim();
            return s == "US" || s == "UK" || s == "美" || s == "英";
        }

        private static bool HasButtonAncestor(TMP_Text text)
        {
            Transform t = text == null ? null : text.transform;
            for (int i = 0; i < 5 && t != null; i++)
            {
                if (t.GetComponent<Button>() != null) return true;
                t = t.parent;
            }
            return false;
        }

        private void Warn(string message)
        {
            if (WcpHostPlugin.Log != null) WcpHostPlugin.Log.LogWarning("WcpHost: " + message);
        }
    }

    internal sealed class HostAudioPlayer : MonoBehaviour
    {
        private AudioSource _source;
        private readonly Dictionary<string, AudioClip> _cache =
            new Dictionary<string, AudioClip>(StringComparer.Ordinal);
        private readonly HashSet<string> _loading =
            new HashSet<string>(StringComparer.Ordinal);

        private void Awake()
        {
            _source = gameObject.AddComponent<AudioSource>();
            _source.playOnAwake = false;
            _source.spatialBlend = 0f;
            _source.volume = 1f;
        }

        internal void Play(string file)
        {
            if (string.IsNullOrEmpty(file) || !File.Exists(file)) return;
            AudioClip clip;
            if (_cache.TryGetValue(file, out clip) && clip != null)
            {
                _source.Stop();
                _source.clip = clip;
                _source.Play();
                return;
            }
            if (!_loading.Contains(file))
            {
                _loading.Add(file);
                StartCoroutine(LoadAndPlay(file));
            }
        }

        private IEnumerator LoadAndPlay(string file)
        {
            UnityWebRequest request = null;
            try
            {
                request = UnityWebRequestMultimedia.GetAudioClip(
                    "file:///" + file.Replace('\\', '/'), AudioType.MPEG);
            }
            catch (Exception e)
            {
                _loading.Remove(file);
                if (WcpHostPlugin.Log != null)
                    WcpHostPlugin.Log.LogWarning("WcpHost: 音频请求失败: " + e.Message);
                yield break;
            }
            yield return request.SendWebRequest();
            try
            {
                if (request.result == UnityWebRequest.Result.Success)
                {
                    AudioClip clip = DownloadHandlerAudioClip.GetContent(request);
                    if (clip != null)
                    {
                        _cache[file] = clip;
                        _source.Stop();
                        _source.clip = clip;
                        _source.Play();
                    }
                }
                else if (WcpHostPlugin.Log != null)
                    WcpHostPlugin.Log.LogWarning("WcpHost: 音频载入失败: " + request.error);
            }
            catch (Exception e)
            {
                if (WcpHostPlugin.Log != null)
                    WcpHostPlugin.Log.LogWarning("WcpHost: 音频解码失败: " + e.Message);
            }
            _loading.Remove(file);
            request.Dispose();
        }
    }

    internal sealed class HostSentenceTag : MonoBehaviour
    {
    }
}
