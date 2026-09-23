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
using System.Text;
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
        // 第十五轮（2026-09-18）：标签还原分帧。text.text 的 setter 会触发 TMP
        // 网格重建（单个数毫秒），一次全量还原几十个标签就是切书帧上的
        // 160~190ms（实机两轮采样复现：装载:离开 161.0 / 190.5ms，内部大头是
        // 标签还原）。改为把还原项排队，每帧按时间预算（8ms）分批执行。
        // 正确性守卫与原实现相同：只还原「仍显示旧写入值」的标签 —— 新语言包
        // 的扫描已经改写过的标签不会被旧备份覆盖。
        private sealed class RestoreItem
        {
            internal TMP_Text Text;
            internal string Backup;
            internal string Written;
        }
        private readonly List<RestoreItem> _pendingRestore = new List<RestoreItem>();
        private const long LabelRestoreBudgetMs = 8;
        private SentenceAudioService _sentenceAudio;
        private SentenceTable _sentenceTable;
        private LanguageManifest _sentenceTableManifest;
        private bool _sentenceTableReported;
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
        // 第十七轮（2026-09-21）：Enforce 节流。稳态每帧都调一次代价在 30ms/s 量级，
        // 词表字段在 Harmony 回调之间本来就不会被游戏改动，节流到 1s 无语义差异。
        // EnforceNow()（由 Harmony patch 触发）立即执行并重置计时器。
        private float _nextEnforce;
        private const float EnforceInterval = 1.0f;

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
                // 第七轮（2026-09-18）：这里原来还有一次 `_scope.Enforce()`
                // （标签"身份:同名校正"），删掉了 —— 它是纯重复。
                //
                // 等价性证明：SetIdentity 只有两个调用场景，两个场景里紧接着都会
                // 再走一次同一个 Enforce：
                //   · Host.Update:      Evaluate() → … → _runtime.Tick() → _scope.Enforce()
                //   · Host.EnforceNowForScene: Evaluate() → _runtime.EnforceNow() → _scope.Enforce()
                // 两次调用之间没有让出主线程（都在同一个 Update / 同一个回调里），
                // 游戏侧不可能改动队列，所以第二次执行看到的状态与第一次执行之后
                // 完全相同 —— 而 Enforce 是幂等的（干净且够长的列表一律不重写）。
                // 也就是说这一行**只增加一倍工作量，不改变任何结果**。
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
                using (PerfProbe.Begin("身份:接管语言包"))
                {
                    // 第十一轮（2026-09-18）：这段在实机切书帧单次 197.7ms，此前是
                    // 一个黑盒（只知道"接管语言包慢"）。Enter 里除了一次整档读
                    // （RecoverStale 读索引键）之外全是内存操作，所以要先把
                    // 「范围进入 / 服务就绪」拆开，再决定往里看哪一层。
                    using (PerfProbe.Begin("装载:范围进入")) _scope.Enter(manifest, _activeWords);
                    using (PerfProbe.Begin("装载:服务就绪")) EnsureServices();
                }
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
            using (PerfProbe.Begin("运行态:Tick"))
            {
                EnsureServices();
                TryBeginWordAudioMirror();
                if (Time.unscaledTime >= _nextEnforce)
                {
                    _nextEnforce = Time.unscaledTime + EnforceInterval;
                    try { using (PerfProbe.Begin("运行态:队列校正")) _scope.Enforce(); }
                    catch (Exception e) { Warn("运行态队列校正失败: " + e.Message); }
                }
                try { using (PerfProbe.Begin("运行态:书名扫描")) ScanBookLabelsThrottled(); }
                catch (Exception e) { Warn("书名/UI 扫描失败: " + e.Message); }
                try { using (PerfProbe.Begin("运行态:例句按钮")) _sentenceAudio.Tick(); }
                catch (Exception e) { Warn("例句按钮扫描失败: " + e.Message); }
            }
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

        // 小游戏（打怪听音选词、切水果等）的 AI 发音统一走 USgs 英语 ONNX
        // TTS。受管语言下按词形路由 pack 音频: 命中则宿主播放并拦截英语
        // TTS（返回 true = 已拦截），未命中放行保持游戏原生行为。
        internal bool BlockEnglishWordTts(object instance, string text)
        {
            if (!IsActive || ActiveStrategy == null || instance == null) return false;
            string displayed = string.IsNullOrEmpty(text) ? null : text.Trim();
            if (string.IsNullOrEmpty(displayed)) return false;
            string canonical = CurrentWord(displayed);
            string lookup;
            try { lookup = ActiveStrategy.AudioLookupForm(displayed, canonical); }
            catch (Exception e)
            {
                Warn("策略音频词形失败: " + e.Message);
                return false;
            }
            if (string.IsNullOrEmpty(lookup)) lookup = canonical;
            string path = ResolveWordAudio(lookup);
            if (string.IsNullOrEmpty(path))
            {
                ReportAudioMiss(displayed, lookup, canonical);
                return false;
            }
            EnsureServices();
            _audio.Play(path);
            return true;
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
        // 单词音频兼容层：主线程只做「O(1) 判据 + 投递」，真正的枚举与复制全在
        // MirrorWorker 的后台线程上跑。主线程在这里的耗时是一次 DirectoryInfo.stat
        // 加一次几行的标记文件读取，与包大小无关。
        //
        // 主线程为什么不能省掉这一趟：Application.persistentDataPath 是 Unity API，
        // 只能主线程取；路径算好再传进线程，线程里不碰任何 Unity API。
        private void TryBeginWordAudioMirror()
        {
            if (_mirrorAttempted) return;
            _mirrorAttempted = true;
            if (WcpHostPlugin.Instance == null || !WcpHostPlugin.Instance.MirrorWordAudio) return;

            LanguageManifest manifest = ActiveManifest;
            if (manifest == null || string.IsNullOrEmpty(manifest.WordAudioDir)) return;

            using (PerfProbe.Begin("镜像:投递"))
            {
                string source = manifest.Resolve(manifest.WordAudioDir);
                if (string.IsNullOrEmpty(source) || !Directory.Exists(source)) return;

                string parent = Path.GetDirectoryName(Application.persistentDataPath);
                if (string.IsNullOrEmpty(parent)) return;
                string targetDir = Path.Combine(parent, "vocabulary");

                try
                {
                    // 跳过判据 O(1)：pack 身份 + 源目录 mtime（各一次系统调用），
                    // 完全不枚举目录。标记文件按 pack 分行累积，所以"切回已经镜像过
                    // 的语言"也是 O(1) 跳过 —— 旧实现只存一行，切一次库就全量重扫
                    // 一遍 7.8 万个目录项，这是切词库卡顿的直接来源之一。
                    string stampPrefix = WordAudioCompat.StampPrefix(manifest.Profile.Id, source);
                    if (WordAudioCompat.StampMatches(
                            WordAudioCompat.StampPath(targetDir), stampPrefix))
                        return;
                    if (WcpHostPlugin.Log != null)
                        WcpHostPlugin.Log.LogInfo("WcpHost: 单词音频兼容层安排（" +
                            manifest.Profile.Language + " → " + targetDir +
                            "，后台线程执行，不占帧）");
                    MirrorWorker.Request(manifest.Profile.Id, source, targetDir);
                }
                catch (Exception e)
                {
                    Warn("单词音频兼容层启动失败: " + e.Message);
                }
            }
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
                    // 空选项兜底（2026-09-22）: 游戏生成非英语四选一时，
                    // GetMeaning_S7 在共享英语库里查不到就写**空串**，空串会在
                    // OptionDisplay 里被一路透传成 null，选项栏就是空的（小蜜蜂
                    // 截图症状）。空显示时退回「选项词本身」—— 判定链用的是
                    // wordNText，显示层怎么改都不影响对错，保证四行永远可读。
                    if (string.IsNullOrEmpty(display) && string.IsNullOrEmpty(options[i].text))
                        display = words[i].text;
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
                string targetMeaning = null;

                for (int i = 0; i < options.Count && i < optionWords.Length; i++)
                {
                    TMP_Text text = options[i] as TMP_Text;
                    if (text == null || string.IsNullOrEmpty(optionWords[i])) continue;
                    string def, phonic;
                    string optDisplay = null;
                    if (ActiveStrategy.ProvideMeaning(optionWords[i], out def, out phonic) && !string.IsNullOrEmpty(def))
                    {
                        optDisplay = def;
                    }
                    else
                    {
                        optDisplay = ActiveStrategy.OptionDisplay(optionWords[i], text.text);
                    }
                    // 同 S7: 游戏写空的选项（共享英语库查不到非英语词）不能留空，
                    // 用选项词本身占位，判定链读的是 S9OptionN_Para 不受影响。
                    if (string.IsNullOrEmpty(optDisplay) && string.IsNullOrEmpty(text.text))
                        optDisplay = optionWords[i];
                    if (optDisplay != null)
                    {
                        text.text = optDisplay;
                        GameAdapter.SetInstanceField(instance, "meaning" + (i + 1), optDisplay);
                    }
                    if (optionWords[i] == target) targetMeaning = text.text;
                }
                if (!string.IsNullOrEmpty(target))
                    SetQuestionStem(target, ActiveStrategy.StemDisplay(target, targetMeaning));
            }
            catch (Exception e) { Warn("自学词测试题面改写失败: " + e.Message); }
        }

        internal void PostShowWordAndMeaningS9(object instance)
        {
            if (!IsActive || ActiveStrategy == null || instance == null) return;
            try
            {
                IList options = ToObjectList(GameAdapter.InstanceField(instance, "optionText"));
                if (options == null) return;
                string[] optionWords = new string[] {
                    StaticString("S9Option1_Para"), StaticString("S9Option2_Para"),
                    StaticString("S9Option3_Para"), StaticString("S9Option4_Para") };
                for (int i = 0; i < options.Count && i < optionWords.Length; i++)
                {
                    TMP_Text text = options[i] as TMP_Text;
                    if (text == null || string.IsNullOrEmpty(optionWords[i])) continue;
                    string def, phonic;
                    if (ActiveStrategy.ProvideMeaning(optionWords[i], out def, out phonic) && !string.IsNullOrEmpty(def))
                    {
                        text.text = optionWords[i] + "\n" + def;
                    }
                }
            }
            catch (Exception e) { Warn("自学词测试答案展示覆写失败: " + e.Message); }
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
                if (ActiveStrategy.ProvideMeaning(word, out meaning, out phonic))
                {
                    TMP_Text meaningText = GameAdapter.InstanceField(instance, "meaningText") as TMP_Text;
                    TMP_Text us = GameAdapter.InstanceField(instance, "usPhoneticText") as TMP_Text;
                    TMP_Text uk = GameAdapter.InstanceField(instance, "ukPhoneticText") as TMP_Text;
                    if (meaningText != null && !string.IsNullOrEmpty(meaning))
                        meaningText.text = meaning + Environment.NewLine;
                    if (us != null && !string.IsNullOrEmpty(phonic)) us.text = phonic;
                    if (uk != null && !string.IsNullOrEmpty(phonic)) uk.text = string.Empty;
                }
                // 【例句】区只认 wcpFullEng.db 的 sentence2。资源隔离落地后语言包默认不再
                // 写共享库（AllowSharedDatabaseWrites=false），库里只剩英语 → 受管词书的
                // 该区永远空白（日志「没有例句」）。这里由 pack 例句表兜住，不再依赖游戏 DB。
                ApplySentenceTable(instance, word);
            }
            catch (Exception e) { Warn("查词面板改写失败: " + e.Message); }
        }

        // 例句文本自服务。参数与渲染格式严格对齐游戏原本的写库路径:
        //   库里存的是 "例句：<原文>（<译文>）"，游戏做三段 Replace 后拼进 outputText:
        //     例句：    → <color=#FFBE31>例句N：</color>
        //     （        → "\n\n释义："
        //     ）        → ""
        //   每个句子后再接 "\n\n"。SentenceReplyManager 解析的就是这个形态。
        private void ApplySentenceTable(object instance, string word)
        {
            // 只有 S8 查词面板有例句区；S8checkWordMeaning / ButtonTextTransfer 没有该字段。
            TMP_Text output = GameAdapter.InstanceField(instance, "outputText") as TMP_Text;
            if (output == null) return;

            SentenceTable table = SentenceTableFor(ActiveManifest);
            if (table == null) return;
            List<string> raw;
            if (!table.TryGet(word, out raw) || raw.Count == 0)
            {
                ReportSentenceTable(table, 0);
                return;
            }

            // 与游戏一致: 受 outputCount 与例句槽位数双重限制，越界会打穿 exmplesentences 数组。
            int cap = raw.Count;
            object configured = GameAdapter.InstanceField(instance, "outputCount");
            if (configured is int && (int)configured > 0 && (int)configured < cap) cap = (int)configured;
            Array slots = GameAdapter.InstanceField(instance, "exmplesentences") as Array;
            if (slots != null && slots.Length > 0 && slots.Length < cap) cap = slots.Length;

            StringBuilder text = new StringBuilder();
            List<string> filled = new List<string>(cap);
            for (int i = 0; i < cap; i++)
            {
                string s = raw[i];
                if (string.IsNullOrEmpty(s)) continue;
                s = s.Replace("例句：", "<color=#FFBE31>例句" + (i + 1) + "：</color>");
                s = s.Replace("（", "\n\n释义：");
                s = s.Replace("）", "");
                text.Append(s).Append("\n\n");
                filled.Add(s);
            }
            if (filled.Count == 0) return;

            output.text = text.ToString();
            ReportSentenceTable(table, filled.Count);

            // ▶ 例句按钮读的是 exmplesentences[i].text，由游戏自己的 ReserveExampleSentences 写。
            // 把它当可选增强: 反射不到只影响音频按钮，不影响已经生效的例句文本。
            MethodInfo reserve = null;
            try
            {
                reserve = instance.GetType().GetMethod("ReserveExampleSentences",
                    BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
            }
            catch (Exception) { reserve = null; }
            if (reserve == null) return;
            try
            {
                IList<string> shared =
                    GameAdapter.StaticField(GameAdapter.ParametersType, "exaple_sentences") as IList<string>;
                if (shared != null) shared.Clear();
                for (int i = 0; i < filled.Count; i++)
                    reserve.Invoke(instance, new object[] { filled[i] });
            }
            catch (Exception e)
            {
                Warn("例句槽填充失败（▶ 例句按钮可能不响）: " + e.Message);
            }
        }

        private SentenceTable SentenceTableFor(LanguageManifest manifest)
        {
            if (manifest == null) return null;
            if (_sentenceTable != null && ReferenceEquals(_sentenceTableManifest, manifest))
                return _sentenceTable;
            string path = null;
            try { path = _router.Resolve(ResourceKind.SentenceTable, null); }
            catch (Exception) { path = null; }
            _sentenceTable = new SentenceTable(path);
            _sentenceTableManifest = manifest;
            _sentenceTableReported = false;
            return _sentenceTable;
        }

        // 例句表首用即整表解析（ru 约 4 MB）。只报一次，避免每个词刷一行。
        private void ReportSentenceTable(SentenceTable table, int used)
        {
            if (_sentenceTableReported) return;
            _sentenceTableReported = true;
            if (table.LastError != null)
            {
                Warn("例句表不可用（例句区将保持游戏原状）: " + table.LastError);
                return;
            }
            Info("例句表已装载: " + table.RowCount + " 词 / " + table.LoadMs.ToString("F0") + " ms → " +
                 table.Path + "（本次注入 " + used + " 句）");
        }

        private static void Info(string message)
        {
            if (WcpHostPlugin.Log != null) WcpHostPlugin.Log.LogInfo("WcpHost: " + message);
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
            // 第十轮加标签：原来这里是裸调用，于是"被 Harmony 补丁触发的场景校正"
            // 与"每秒 Tick 里的队列校正"在日志里无法区分（后者有 运行态:队列校正）。
            // 分开之后才能回答"切书后那几秒的校正到底是谁在跑、跑了几次"。
            // 第十七轮：顺带重置节流计时器，让 Tick 的 1s 窗口从这次校正起算。
            if (IsActive && ActiveStrategy != null)
            {
                _nextEnforce = Time.unscaledTime + EnforceInterval;
                using (PerfProbe.Begin("运行态:场景校正")) _scope.Enforce();
            }
        }

        // ── 战斗词池接管 ──
        // 快速测试的六种排序入口共用这一条选词边界。游戏原方法从全局
        // HaveLearnedDictionary 取词，法英同形词即使通过本书过滤仍会扎堆。
        // 返回 false 后游戏仍负责保存列表、检查题数和进入原有场景。
        internal bool PrefixQuickTest(int requested, string method, ref List<string> result)
        {
            if (!IsActive || ActiveStrategy == null) return true;
            try
            {
                PoolOrder order = new PoolOrder();
                order.Mode = method.IndexOf("Ran", StringComparison.Ordinal) >= 0 ? "随机" :
                    method.IndexOf("Neg", StringComparison.Ordinal) >= 0 ? "倒序" : "正序";
                order.PriorityOn = !method.EndsWith("Off", StringComparison.Ordinal);
                result = BookPool.QuickTest(_activeWords, GameLearnedStats.FromGame(),
                    order, requested, null);
                return false;
            }
            catch (Exception e)
            {
                Warn("快速测试本书选词失败: " + e.Message);
                result = new List<string>();
                return false; // 受管词书失败时交给游戏的题数不足提示，绝不回退全局英语词。
            }
        }

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
                // 这条路上有两处 ES3 写（RebuildPool 里的 CaptureList，以及下面的
                // 游戏字段）。用一个批量作用域包住整段 = 一次整档读写而不是两次；
                // RebuildPool 自己那层作用域会识别到已在批量中，不再嵌套。
                using (GameAdapter.Es3BatchScope())
                {
                    List<string> rebuilt = _scope.RebuildPool("S7TestWordList_Para", list, requested);
                    if (rebuilt == null)
                        rebuilt = BookPool.FailClosedFightPool(list, _activeWords, requested);
                    if (rebuilt != null && !SameWords(list, rebuilt))
                    {
                        list = rebuilt;
                        GameAdapter.SetStaticField(GameAdapter.ParametersType, "S7TestWordList_Para", rebuilt);
                        GameAdapter.Es3Save("S7TestWordList_Para", rebuilt);
                    }
                }
                // 受管词书下补池一律由宿主负责: 即使本次没有变化，也不能让游戏
                // 回退到全局词典或 one..five 占位词。
                return false;
            }
            catch (Exception e)
            {
                List<string> safe;
                try { safe = BookPool.FailClosedFightPool(list, _activeWords, requested); }
                catch (Exception fallbackError)
                {
                    safe = new List<string>();
                    Warn("战斗词池本书兜底也失败，已阻止全局补词: " + fallbackError.Message);
                }
                list = safe;
                try
                {
                    using (GameAdapter.Es3BatchScope())
                    {
                        GameAdapter.SetStaticField(GameAdapter.ParametersType, "S7TestWordList_Para", safe);
                        GameAdapter.Es3Save("S7TestWordList_Para", safe);
                    }
                }
                catch (Exception saveError)
                {
                    Warn("战斗词池兜底仅保存在内存，未能写回存档: " + saveError.Message);
                }
                Warn("战斗词池重建失败，已用当前词书兜底并阻止全局补词（" +
                    (_activeProfileId ?? "unknown") + "): " + e.Message);
                return false;
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
                    GameAdapter.StaticField(GameAdapter.ParametersType, "S7TestWordList_Para"));
                if (pool == null || pool.Count == 0) return;
                IList<string> withInfo = GameAdapter.ToWordList(
                    GameAdapter.StaticField(GameAdapter.ParametersType, "S7TestWordList_WithInfo"));
                if (withInfo != null && withInfo.Count == pool.Count) return;

                List<string> rebuilt = new List<string>(pool.Count);
                for (int i = 0; i < pool.Count; i++) rebuilt.Add(pool[i] + "##0");
                GameAdapter.SetStaticField(GameAdapter.ParametersType, "S7TestWordList_WithInfo", rebuilt);
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
            // 第十一轮（2026-09-18）：`身份:装载` 在实机切书帧是 404.6ms，而它内部的
            // `身份:接管语言包` 只占 197.7ms —— 剩下约 207ms 一直没有归属。这一段
            // （LeaveCurrent）就是那个差额的头号嫌疑：RestoreLabels 是一次全场景
            // 文本扫描，_scope.Leave 里还要读两个 owned 键（各一次整档解析）。
            // 拆开，让差额落地。
            using (PerfProbe.Begin("装载:离开"))
            {
                if (_sentenceAudio != null) _sentenceAudio.Leave();
                using (PerfProbe.Begin("装载:离开·标签还原")) RestoreLabels();
                _scope.Leave();
            }
            // 离开当前语言范围后音频缓存不再有用，及时释放避免长会话内存增长。
            if (_audio != null) _audio.ClearCache();
            _labelScanIdleCount = 0;
            _nextLabelScan = 0f;
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

        // UI 标签扫描节流（性能收敛 2026-09-16）：FindObjectsOfTypeAll 全场
        // 扫描有固定成本，标签变化本来就慢。活跃期 1s（与身份轮询同拍，切书
        // 时立即跟进）；连续 5 次无任何改写视为空闲，放慢到 5s；一旦发生
        // 改写立即回到活跃期。
        private const int LabelScanIdleAfter = 5;
        private const float LabelScanIdleInterval = 5f;
        private float _nextLabelScan;
        private int _labelScanIdleCount;

        private void ScanBookLabelsThrottled()
        {
            if (Time.unscaledTime < _nextLabelScan) return;
            int writtenBefore = _labelWritten.Count;
            ScanBookLabels();
            if (_labelWritten.Count != writtenBefore)
                _labelScanIdleCount = 0;
            else if (_labelScanIdleCount < LabelScanIdleAfter)
                _labelScanIdleCount++;
            _nextLabelScan = Time.unscaledTime +
                (_labelScanIdleCount >= LabelScanIdleAfter
                    ? LabelScanIdleInterval : 1f);
        }

        // 选项 B（2026-09-18）：选书页的行按分类页定显示名 —— 自定义分类页美化，
        // 官方分类页（尾部会渲染自定义槽那行，原生显示「自定义词书N」）保持游戏
        // 原生名。判据 = 游戏自己的 clickNum（GameAdapter.IsCustomPage），
        // 判据缺失时按「不是自定义页」处理 = 显示原生名（fail-safe）。
        private void ScanBookLabels()
        {
            object chooser = GameAdapter.ChooserInstance();
            List<TMP_Text> rows = ChooserRows(chooser);
            bool onCustom = false;
            string[] canon = GameAdapter.CanonicalNames();
            string[] cosmetic = DisplayNames();
            if (chooser != null && rows.Count > 0)
            {
                List<string> texts = new List<string>();
                List<bool> visible = new List<bool>();
                for (int r = 0; r < rows.Count; r++)
                {
                    TMP_Text row = rows[r];
                    texts.Add(row == null ? null : row.text);
                    visible.Add(row != null && row.gameObject != null &&
                                row.gameObject.activeInHierarchy);
                }
                onCustom = GameAdapter.IsCustomPage(chooser, texts, visible, canon, cosmetic);
            }
            UnityEngine.Object[] all = Resources.FindObjectsOfTypeAll(typeof(TMP_Text));
            for (int i = 0; i < all.Length; i++)
            {
                TMP_Text text = all[i] as TMP_Text;
                if (text == null || string.IsNullOrEmpty(text.text)) continue;
                int slot = GameAdapter.SlotOfBookName(text.text);
                bool isRow = rows.Contains(text);
                if (slot > 0)
                {
                    if (isRow)
                    {
                        LanguageManifest rowManifest = ManifestForSlot(slot);
                        string rowDesired = rowManifest == null
                            ? null : rowManifest.Profile.DisplayName;
                        WriteLabel(text, GameAdapter.LabelPageGate.TargetRowText(
                            text.text, slot, rowDesired, onCustom, canon, cosmetic));
                        continue;
                    }
                    LanguageManifest m = ManifestForSlot(slot);
                    if (m != null && text.text != m.Profile.DisplayName)
                    {
                        if (!_labelBackup.ContainsKey(text)) _labelBackup[text] = text.text;
                        text.text = m.Profile.DisplayName;
                        _labelWritten[text] = m.Profile.DisplayName;
                    }
                    continue;
                }
                // 已经是美化名的选书页行：非自定义分类页下还原游戏原生名
                if (isRow && !onCustom)
                {
                    WriteLabel(text, GameAdapter.LabelPageGate.TargetRowText(
                        text.text, SlotByDisplayName(text.text), null, false, canon, cosmetic));
                    continue;
                }
                if (!IsAccentLabel(text.text) || !HasButtonAncestor(text)) continue;
                if (!_labelBackup.ContainsKey(text)) _labelBackup[text] = text.text;
                string value = ActiveManifest.Profile.Language.ToUpperInvariant();
                text.text = value;
                _labelWritten[text] = value;
            }
        }

        // 选项 B 用的辅助：选书页行枚举 / 项目语言包显示名 / 美化名→槽位
        private List<TMP_Text> ChooserRows(object chooser)
        {
            List<TMP_Text> rows = new List<TMP_Text>();
            if (chooser == null) return rows;
            Array arr = GameAdapter.InstanceField(chooser, "BookNameText") as Array;
            if (arr == null) return rows;
            for (int k = 0; k < arr.Length; k++)
            {
                TMP_Text row = arr.GetValue(k) as TMP_Text;
                if (row != null) rows.Add(row);
            }
            return rows;
        }

        private string[] DisplayNames()
        {
            IList<LanguageManifest> all = _registry.Manifests;
            string[] names = new string[all.Count];
            for (int i = 0; i < all.Count; i++)
                names[i] = all[i] == null || all[i].Profile == null
                    ? null : all[i].Profile.DisplayName;
            return names;
        }

        // 美化名 → 槽位（词表指纹认槽）。
        //
        // 第七轮（2026-09-18）：删掉了原来的 `_displaySlot` + 10 秒整体清空缓存。
        // 那个缓存是个陷阱 —— 它不是"按槽缓存"，而是"按显示文本缓存"，每 10 秒被
        // `_displaySlot.Clear()` 整体作废一次（`_displaySlotAt` 只在清空那一刻更新），
        // 于是每 10 秒就要把每一行 × 每个槽重新问一遍；而每次问又要走
        // SlotWords（ES3 全文档解析）+ 两次 Match（词表指纹）。
        // 现在 ManifestForSlot 本身已经是 O(1)（按槽号 + 词表实例缓存），这一层
        // 缓存没有存在价值了，留着只会引入"文本变了但缓存没失效"的陈旧读取。
        private int SlotByDisplayName(string text)
        {
            if (string.IsNullOrEmpty(text)) return 0;
            int count = GameAdapter.NativeSlotCount();
            for (int slot = 1; slot <= count; slot++)
            {
                LanguageManifest m = ManifestForSlot(slot);
                if (m == null || m.Profile == null ||
                    string.IsNullOrEmpty(m.Profile.DisplayName)) continue;
                if (text.StartsWith(m.Profile.DisplayName, StringComparison.Ordinal))
                    return slot;
            }
            return 0;
        }

        private void WriteLabel(TMP_Text text, string value)
        {
            if (text == null || string.IsNullOrEmpty(value)) return;
            if (text.text == value) return;
            if (!_labelBackup.ContainsKey(text)) _labelBackup[text] = text.text;
            text.text = value;
            _labelWritten[text] = value;
        }

        private void RestoreLabels()
        {
            // 第十五轮：不再当场还原（TMP setter 的网格重建是切书帧 160~190ms 的
            // 大头），把还原项移入队列，由 DrainLabelRestores 分帧消化。
            // 判据不变：text.text == written 才还原；已经不显示旧写入值的标签
            //（被新扫描改写 / 被游戏改写）直接丢弃，不还原 —— 与原实现一致。
            foreach (KeyValuePair<TMP_Text, string> pair in _labelBackup)
            {
                TMP_Text text = pair.Key;
                string written;
                if (text != null && _labelWritten.TryGetValue(text, out written))
                {
                    RestoreItem item = new RestoreItem();
                    item.Text = text;
                    item.Backup = pair.Value;
                    item.Written = written;
                    _pendingRestore.Add(item);
                }
            }
            _labelBackup.Clear();
            _labelWritten.Clear();
        }

        /// <summary>每帧调用：按时间预算分批还原旧标签（Host.Update 挂钩）。</summary>
        internal void DrainLabelRestores()
        {
            if (_pendingRestore.Count == 0) return;
            System.Diagnostics.Stopwatch sw = System.Diagnostics.Stopwatch.StartNew();
            using (PerfProbe.Begin("还原:分帧"))
            {
                for (int i = _pendingRestore.Count - 1; i >= 0; i--)
                {
                    RestoreItem item = _pendingRestore[i];
                    TMP_Text text = item.Text;
                    if (text != null && text.text == item.Written)
                    {
                        text.text = item.Backup;
                        if (sw.ElapsedMilliseconds >= LabelRestoreBudgetMs)
                        {
                            _pendingRestore.RemoveAt(i);
                            break;    // 预算用完，剩余项留到下一帧
                        }
                        _pendingRestore.RemoveAt(i);
                        continue;
                    }
                    _pendingRestore.RemoveAt(i);   // 已失效（被改写/销毁）：丢弃
                }
            }
        }

        // 槽位 → 语言包。第七轮（2026-09-18）改了两处，两处都是纯冗余消除：
        //
        //  1) 原实现把 `_registry.Match(words)` **调用了两次**（同一份词表、同一个
        //     确定性函数），第二次的结果与第一次逐字节相同，属于纯重复劳动。
        //     实测单价（probes/csbench/bench2_report.txt，同代 BCL）：
        //       7922 词 1.26ms / 8116 词 1.96ms / 8451 词 3.75ms
        //  2) 原来没有任何缓存。而 SlotByDisplayName 会对每一行 × 每个槽问一次，
        //     一次 UI 扫描就能问几十次 —— 每次都重算指纹。
        //
        // 缓存键用**词表实例本身**（引用相等）：GameAdapter.SlotWords 在 MyBook.es3
        // 的 (mtime,size) 未变时返回同一个实例，实例一变说明词表内容确实变了。
        // 也就是说"引用相同 ⇒ 输入相同 ⇒ 指纹相同"，判据是这个函数的强等价条件，
        // 不存在读旧值的可能。
        private sealed class SlotManifestEntry
        {
            internal IList<string> Words;
            internal LanguageManifest Manifest;
        }

        private readonly Dictionary<int, SlotManifestEntry> _slotManifest =
            new Dictionary<int, SlotManifestEntry>();

        private LanguageManifest ManifestForSlot(int slot)
        {
            IList<string> words = GameAdapter.SlotWords(slot);
            if (words == null)
            {
                _slotManifest.Remove(slot);
                return null;
            }
            SlotManifestEntry cached;
            if (_slotManifest.TryGetValue(slot, out cached) &&
                ReferenceEquals(cached.Words, words))
                return cached.Manifest;

            BookProfile profile = _registry.Match(words);
            LanguageManifest manifest = profile == null
                ? null : _registry.ByProfileId(profile.Id);
            cached = new SlotManifestEntry();
            cached.Words = words;
            cached.Manifest = manifest;
            _slotManifest[slot] = cached;
            return manifest;
        }

        private string StaticString(string field)
        {
            object value = GameAdapter.StaticField(GameAdapter.ParametersType, field);
            return value as string;
        }

        private string CurrentFightWord()
        {
            IList<string> values = GameAdapter.ToWordList(
                GameAdapter.StaticField(GameAdapter.ParametersType, "S7TestWordList_Para"));
            int index = StaticInt("S7Progress_Para");
            return At(values, index);
        }

        private string CurrentTestWord()
        {
            IList<string> values = GameAdapter.ToWordList(
                GameAdapter.StaticField(GameAdapter.ParametersType, "allTestWordsS10_Para"));
            int index = StaticInt("S8Progress_Para");
            return At(values, index);
        }

        private int StaticInt(string field)
        {
            object value = GameAdapter.StaticField(GameAdapter.ParametersType, field);
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
