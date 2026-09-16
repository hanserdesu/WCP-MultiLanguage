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
        // 兼容层状态：单词音频镜像（每语言包每会话最多安排一次）与 miss 限流。
        private bool _mirrorAttempted;
        private int _audioMissTotal;
        private readonly HashSet<string> _audioMissReported =
            new HashSet<string>(StringComparer.Ordinal);
        private readonly HashSet<string> _onceMessages =
            new HashSet<string>(StringComparer.Ordinal);

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
            _mirrorAttempted = false;
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
            TryBeginWordAudioMirror();
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
            string path = ResolveWordAudio(lookup);
            if (string.IsNullOrEmpty(path))
            {
                // 不接住这次播放：放行给游戏自己的 VocabularyAudioPlayer。
                // 兼容层（TryBeginWordAudioMirror）已把 pack 音频补进游戏原生
                // 目录，因此放行后通常仍能听到本地发音而不是英语 AI 语音。
                ReportAudioMiss(displayed, lookup, canonical);
                return true;
            }
            EnsureServices();
            _audio.Play(path);
            return false;
        }

        // 精确词形优先；未命中再按写法差异候选重试（全角/半角、大小写、
        // 空格与下划线、尾部句点）。命中候选只记一次日志，便于线上定位。
        private string ResolveWordAudio(string key)
        {
            if (string.IsNullOrEmpty(key)) return null;
            string path = _router.Resolve(ResourceKind.WordAudio, key);
            if (!string.IsNullOrEmpty(path) && File.Exists(path)) return path;

            string[] forms = WordAudioCompat.CandidateForms(key);
            for (int i = 0; i < forms.Length; i++)
            {
                string form = forms[i];
                if (string.Equals(form, key, StringComparison.Ordinal)) continue;
                path = _router.Resolve(ResourceKind.WordAudio, form);
                if (!string.IsNullOrEmpty(path) && File.Exists(path))
                {
                    InfoOnce("audioform:" + key, "单词音频按候选词形命中: " +
                        key + " → " + form);
                    return path;
                }
            }
            return null;
        }

        private void ReportAudioMiss(string displayed, string lookup, string canonical)
        {
            _audioMissTotal++;
            string shown = lookup;
            if (string.IsNullOrEmpty(shown)) shown = displayed;
            if (string.IsNullOrEmpty(shown)) shown = "<空>";
            if (_audioMissReported.Count < 20 && _audioMissReported.Add(shown))
            {
                Warn("单词音频未命中 pack（放行游戏原生目录）: 显示=" + displayed +
                     " 查词=" + shown + " 词表=" + (canonical == null ? "<无>" : canonical));
            }
            else if (_audioMissTotal == 50 || _audioMissTotal == 500 ||
                     _audioMissTotal == 5000)
            {
                Warn("单词音频未命中累计 " + _audioMissTotal + " 次（示例: " + shown + "）");
            }
        }

        private void InfoOnce(string key, string message)
        {
            if (WcpHostPlugin.Log == null) return;
            if (_onceMessages.Add(key)) WcpHostPlugin.Log.LogInfo("WcpHost: " + message);
        }

        // ── 单词音频兼容层 ──────────────────────────────────────────────
        //
        // 游戏原生 VocabularyAudioPlayer 只读 <LocalLow>\WCP\vocabulary。
        // 安装器 v1.1.0 起只写 pack（开发机有历史副本、用户机没有），导致
        // 宿主未接管时发音静默变成英语 AI 语音。这里在激活语言包时把 pack 的
        // 单词音频补进游戏原生目录：只补缺、分批做（不卡帧）、可中断可重入，
        // 失败只记日志。整段不写任何语言专属路径——目标目录由引擎约定推导。
        private void TryBeginWordAudioMirror()
        {
            if (_mirrorAttempted) return;
            _mirrorAttempted = true;
            if (WcpHostPlugin.Instance == null || !WcpHostPlugin.Instance.MirrorWordAudio) return;

            LanguageManifest manifest = ActiveManifest;
            if (manifest == null || string.IsNullOrEmpty(manifest.WordAudioDir)) return;
            string source = manifest.Resolve(manifest.WordAudioDir);
            if (string.IsNullOrEmpty(source) || !Directory.Exists(source)) return;

            string parent = Path.GetDirectoryName(Application.persistentDataPath);
            if (string.IsNullOrEmpty(parent)) return;
            string targetDir = Path.Combine(parent, "vocabulary");

            try
            {
                string[] files = WordAudioCompat.ListSourceFiles(source);
                if (files == null || files.Length == 0) return;
                string stamp = WordAudioCompat.ExpectedStamp(manifest.Profile.Id, files.Length);
                if (WordAudioCompat.StampMatches(WordAudioCompat.StampPath(targetDir), stamp))
                    return;
                if (WcpHostPlugin.Log != null)
                    WcpHostPlugin.Log.LogInfo("WcpHost: 单词音频兼容层开始（" +
                        manifest.Profile.Language + " 共 " + files.Length + " 个文件 → " +
                        targetDir + "）");
                _plugin.StartCoroutine(MirrorWordAudio(files, targetDir, stamp));
            }
            catch (Exception e)
            {
                Warn("单词音频兼容层启动失败: " + e.Message);
            }
        }

        private IEnumerator MirrorWordAudio(string[] files, string targetDir, string stamp)
        {
            int copied = 0;
            int skipped = 0;
            int failed = 0;
            int frameCount = 0;
            float frameBudget = Time.realtimeSinceStartup + WordAudioCompat.FrameBudgetSeconds;
            for (int i = 0; i < files.Length; i++)
            {
                string target = Path.Combine(targetDir, Path.GetFileName(files[i]));
                if (WordAudioCompat.AlreadyPresent(files[i], target)) skipped++;
                else if (WordAudioCompat.TryCopy(files[i], target)) copied++;
                else failed++;

                frameCount++;
                if (frameCount >= WordAudioCompat.MaxFilesPerFrame ||
                    Time.realtimeSinceStartup >= frameBudget)
                {
                    frameCount = 0;
                    frameBudget = Time.realtimeSinceStartup +
                                  WordAudioCompat.FrameBudgetSeconds;
                    yield return null;
                }
            }
            if (failed == 0)
                WordAudioCompat.WriteStamp(WordAudioCompat.StampPath(targetDir), stamp);
            if (WcpHostPlugin.Log != null)
                WcpHostPlugin.Log.LogInfo("WcpHost: 单词音频兼容层完成：复制=" + copied +
                    " 已存在=" + skipped + " 失败=" + failed +
                    (failed == 0 ? "（已记录，后续会话跳过）" : "（下次会话重试）"));
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
            // 离开当前语言范围后音频缓存不再有用，及时释放避免长会话内存增长。
            if (_audio != null) _audio.ClearCache();
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
        // 缓存上限：每个播放过的音频都被永久缓存会让长会话内存只增不减
        // （每条约 0.3-1MB 解码后 PCM）。超过上限时淘汰最旧且不在播放中的条目。
        private const int MaxCache = 160;

        private AudioSource _source;
        private readonly Dictionary<string, AudioClip> _cache =
            new Dictionary<string, AudioClip>(StringComparer.Ordinal);
        private readonly Queue<string> _cacheOrder = new Queue<string>();
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

        // 离开当前语言范围时调用：释放除正在播放外的全部缓存。
        internal void ClearCache()
        {
            foreach (KeyValuePair<string, AudioClip> pair in _cache)
            {
                AudioClip clip = pair.Value;
                if (clip != null && (_source == null || _source.clip != clip))
                    UnityEngine.Object.Destroy(clip);
            }
            _cache.Clear();
            _cacheOrder.Clear();
        }

        private void Remember(string file, AudioClip clip)
        {
            if (!_cache.ContainsKey(file)) _cacheOrder.Enqueue(file);
            _cache[file] = clip;
            while (_cacheOrder.Count > MaxCache)
            {
                string oldest = _cacheOrder.Dequeue();
                AudioClip dropped;
                if (!_cache.TryGetValue(oldest, out dropped)) continue;
                _cache.Remove(oldest);
                if (dropped != null && (_source == null || _source.clip != dropped))
                    UnityEngine.Object.Destroy(dropped);
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
                        Remember(file, clip);
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
