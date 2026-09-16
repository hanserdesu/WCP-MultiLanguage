// WCP Sentence Audio FR — BepInEx 5 插件 (法语变体, 基于 mod_sentence_audio 日语版)
// 功能: 在 每日学习(DatabaseManagerS8) 与 词典查询(DatabaseManagerS17) 的
// 例句旁挂 ▶ 按钮, 点击播放 packs/fr/audio/sentence/<md5(fr)>.mp3 (由
// D:/ATooManyLanguage/French/tools/gen_sentence_audio_fr.py 生成, 文件名规则两端一致)。
//
// 与日语版 (SentenceAudioMod) 的互斥设计:
//   - ExtractFr 只接受「含拉丁字母 且 不含 CJK/假名」的文本 —— 日语例句由
//     SentenceAudioMod 接管, 法语例句由本插件接管, 英语例句两边都没有本地音频,
//     按钮自然不出现; 三种情况互不重叠, 不会互相抢按钮。
//   - 独立插件 GUID / 独立类名 (Fr 前缀), 可与日语版共存。
// 设计: 每 0.3s 反射扫描 exmplesentences 数组, 游戏更新导致类型变化时自动
//   降级为不显示。与日语版相同, 所有接管都受词书指纹闸门保护 (WcpBookProfiles,
//   French Profile = 法语词库(猫条版), 8116 词): 只在当前词书就是登记过的法语
//   书时才显示按钮/接管朗读, 切到其它任何词书立即无损还原游戏原 UI。
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using BepInEx;
using BepInEx.Configuration;
using BepInEx.Logging;
using HarmonyLib;
using TMPro;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.UI;
using WcpBookProfiles;

namespace SentenceAudioFr
{
    [BepInPlugin("dev.hanserdesu.sentaudio.fr", "WCP Sentence Audio FR", "1.0.0")]
    public class FrSentenceAudioPlugin : BaseUnityPlugin
    {
        internal static ManualLogSource Log;
        private static FrSentenceAudioPlugin Instance;
        private const float ScanInterval = 0.3f;
        // 资源命名空间化: 只读 pack (packs/<lang>/audio/sentence)。
        // legacy 目录 (<lang>_sentence_audio) 回退已移除（迁移期结束，2026-09-16）。
        private const string PackLangCode = "fr";

        private AudioSource _audio;
        private ConfigEntry<bool> _enabled;
        private float _nextScan;
        private string _packAudioDir;
        // 旧版兼容开关（默认关）：true 时恢复 pack→legacy(<lang>_sentence_audio)
        // 的迁移期回退链。B 类改造后默认只读 pack；只有 pack 缺音频且用户明确
        // 打开本开关时才碰 legacy 目录（只读，绝不写/删）。
        private ConfigEntry<bool> _audioFallback;
        private string _legacyAudioDir;
        private readonly Dictionary<Button, FrReadBtnState> _readStates =
            new Dictionary<Button, FrReadBtnState>();
        private bool _gameButtonsActive;
        private static FieldInfo _fSentences;
        // 访问序记录: 播放/预载命中时移到末尾, 超 _ClipCacheCap 时淘汰最旧,
        // 防止长会话无限增长占用内存。
        private readonly Dictionary<string, AudioClip> _clips =
            new Dictionary<string, AudioClip>();
        private readonly List<string> _clipOrder = new List<string>();
        private const int _ClipCacheCap = 64;
        private readonly Dictionary<string, string> _audioLookup =
            new Dictionary<string, string>();
        private readonly HashSet<string> _loading = new HashSet<string>();
        private Type _t8, _t17;
        private FieldInfo _f8, _f17;
        private object _s8, _s17;
        private readonly Dictionary<TMP_Text, GameObject> _buttons =
            new Dictionary<TMP_Text, GameObject>();

        void Awake()
        {
            Log = Logger;
            Instance = this;
            PatchSoundTheWord();
            var go = new GameObject("SentenceAudioFrPlayer");
            UnityEngine.Object.DontDestroyOnLoad(go);
            _audio = go.AddComponent<AudioSource>();
            _audio.playOnAwake = false;
            _audio.volume = 1f;
            _audio.spatialBlend = 0f;
            _enabled = Config.Bind("General", "Enabled", true,
                "显示法语例句旁的 ▶ 朗读按钮。");
            string packsRoot = Path.Combine(
                Path.GetDirectoryName(Application.persistentDataPath), "packs");
            _packAudioDir = Path.Combine(packsRoot, PackLangCode, "audio", "sentence");
            _legacyAudioDir = Path.Combine(Application.persistentDataPath,
                PackLangCode + "_sentence_audio");
            _audioFallback = Config.Bind("Legacy", "AudioFallback", false,
                "旧版兼容开关（默认关）。true 时例句音频在 pack 缺失时回退读 legacy 目录 " +
                "<persistentDataPath>/" + PackLangCode + "_sentence_audio（迁移期行为，只读）。");

            Log.LogInfo(string.Format(
                "WCP Sentence Audio 1.1.0 loaded, pack dir = {0} (存在={1}), legacy fallback = {2}",
                _packAudioDir, Directory.Exists(_packAudioDir),
                _audioFallback != null && _audioFallback.Value));
        }

        void Update()
        {
            if (_enabled != null && !_enabled.Value)
            {
                // 运行中关闭配置也必须立即撤销自己的监听、标签和动态按钮;
                // 否则切到其它词书后会留下法语 UI 状态。
                if (Time.unscaledTime >= _nextScan)
                {
                    _nextScan = Time.unscaledTime + ScanInterval;
                    RestoreOtherBookUi();
                }
                return;
            }
            if (Time.unscaledTime < _nextScan) return;
            _nextScan = Time.unscaledTime + ScanInterval;
            try { ScanAll(); }
            catch (Exception e)
            {
                Log.LogWarning("scan failed: " + e.Message);
                _nextScan = Time.unscaledTime + 3f;
            }
        }

        private void ScanAll()
        {
            if (_t8 == null)
            {
                _t8 = FindGameType("DatabaseManagerS8");
                if (_t8 != null)
                    _f8 = _t8.GetField("exmplesentences",
                        BindingFlags.Public | BindingFlags.NonPublic |
                        BindingFlags.Instance);
            }
            if (_t17 == null)
            {
                _t17 = FindGameType("DatabaseManagerS17");
                if (_t17 != null)
                    _f17 = _t17.GetField("exmplesentences",
                        BindingFlags.Public | BindingFlags.NonPublic |
                        BindingFlags.Instance);
            }
            if (_s8 == null && _t8 != null) _s8 = FindObjectOfType(_t8);
            if (_s17 == null && _t17 != null) _s17 = FindObjectOfType(_t17);
            // Unity 假 null: 场景切换销毁旧管理器后 C# 引用仍在, 必须用
            // Unity 重载的 == 检查并重新查找, 否则新场景永远扫描不到。
            var c8 = _s8 as Component;
            if (c8 == null) _s8 = (_t8 != null) ? FindObjectOfType(_t8) : null;
            var c17 = _s17 as Component;
            if (c17 == null) _s17 = (_t17 != null) ? FindObjectOfType(_t17) : null;
            // 词书级别闸门: 只有当前内存词表 / 槽位序号 / 已落盘书名三者一致
            // 且词表指纹等于已登记法语书时, 才允许扫描或接管任何 UI。
            // 其它词书(含英语/日语/用户自建)在源头直接失败关闭。
            if (!ManagedBookSelected())
            {
                RestoreOtherBookUi();
                return;
            }
            if (_s8 == null && _s17 == null) return;
            if (_f8 == null && _f17 == null) return;

            TakeOverGameReadButtons();
            var texts = new List<TMP_Text>();
            if (_s8 != null && _f8 != null)
            {
                var arr = _f8.GetValue(_s8) as TMP_Text[];
                if (arr != null) texts.AddRange(arr);
            }
            if (_s17 != null && _f17 != null)
            {
                var arr = _f17.GetValue(_s17) as TMP_Text[];
                if (arr != null) texts.AddRange(arr);
            }
            Scan(texts.ToArray());
            CleanupDestroyed();
        }

        private bool _restoringUi;
        private int _playRequest;

        // 当前词书是否为已登记法语书。指纹基于排序后的完整词形集合, 与槽位
        // 无关: 用户把法语书挪到别的自定义槽位也能识别; 词数不同/词表被改动
        // 则一律不接管。日语书及其它任何词书都返回 false。
        private bool ManagedBookSelected()
        {
            try
            {
                string name = MyParameters.ChosenBook_Para;
                if (string.IsNullOrEmpty(name)) return false;
                int slot = SlotOf(name);
                if (slot <= 0) return false;
                string disk = ES3.Load<string>("ChosenBook_Para", defaultValue: null);
                if (string.IsNullOrEmpty(disk) || disk != name) return false;
                List<string> current = MyParameters.ChosenBook_List;
                // List may be edited in place without changing its count. Verify content.
                BookProfile memory = BookProfiles.Match(current);
                bool ok = false;
                if (memory != null && memory.Language == BookProfiles.French)
                {
                    string path = Path.Combine(Application.persistentDataPath, "MyBook.es3");
                    string[] slotWords = ES3.Load<string[]>("SelfBookList" + slot, path);
                    BookProfile stored = BookProfiles.Match(slotWords);
                    ok = stored != null && stored.Id == memory.Id;
                }
                return ok;
            }
            catch (Exception) { return false; }
        }

        private static int SlotOf(string name)
        {
            if (string.IsNullOrEmpty(name) || !name.StartsWith("自定义词书",
                StringComparison.Ordinal)) return 0;
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

        // 把游戏自带的"读例句"按钮改造成法语朗读 + FR 标签。
        // 只有该句有本地法语音频时才接管, 否则完整保留游戏原行为。
        private void TakeOverGameReadButtons()
        {
            try
            {
                var t = FindGameType("ShowReadButtons");
                if (t == null) return;
                var f = t.GetField("ReadButtons",
                    BindingFlags.Public | BindingFlags.NonPublic |
                    BindingFlags.Instance);
                if (f == null) return;
                if (_fSentences == null)
                {
                    var mp = FindGameType("MyParameters");
                    if (mp != null)
                        _fSentences = mp.GetField("exaple_sentences",
                            BindingFlags.Public | BindingFlags.Static);
                }
                System.Collections.IList sentences = null;
                if (_fSentences != null)
                {
                    try { sentences = _fSentences.GetValue(null) as System.Collections.IList; }
                    catch (Exception) { }
                }
                var all = Resources.FindObjectsOfTypeAll(t);
                bool any = false;
                for (int k = 0; k < all.Length; k++)
                {
                    var comp = all[k] as Component;
                    if (comp == null) continue;
                    if (!comp.gameObject.activeInHierarchy) continue;
                    var arr = f.GetValue(comp) as Button[];
                    if (arr == null) continue;
                    for (int i = 0; i < arr.Length; i++)
                    {
                        var b = arr[i];
                        if (b == null) continue;
                        any = true;
                        string file = ResolveReadButtonAudio(sentences, i);
                        if (file == null)
                        {
                            // 本句无法语本地音频: 若该按钮此前被接管(残留
                            // FR 标签/TTS 拦截/额外监听), 必须立即原样撤销,
                            // 否则法语书内翻到无音频词条时按钮会滞留 FR 状态。
                            FrReadBtnState stale;
                            if (_readStates.TryGetValue(b, out stale) && stale != null)
                            {
                                ReleaseReadState(b, stale);
                                _readStates.Remove(b);
                            }
                            continue;
                        }
                        FrReadBtnState st;
                        bool isNew = false;
                        if (!_readStates.TryGetValue(b, out st) || st == null)
                        {
                            st = new FrReadBtnState();
                            st.btn = b;
                            st.owner = this;
                            _readStates[b] = st;
                            isNew = true;
                        }
                        if (b.GetComponent<FrReadTag>() == null)
                            b.gameObject.AddComponent<FrReadTag>();
                        if (st.action == null)
                            st.action = new UnityEngine.Events.UnityAction(st.Play);
                        bool changed = isNew ||
                            !string.Equals(st.file, file, StringComparison.Ordinal);
                        st.file = file;
                        // 原游戏监听和标签都保留; Harmony 前缀只在带 FrReadTag
                        // 的法语词书按钮上抑制英文 TTS。这样离开本词书时能无损恢复。
                        if (!st.actionAttached)
                        {
                            b.onClick.AddListener(st.action);
                            st.actionAttached = true;
                        }
                        EnsurePreloaded(file);
                        if (isNew) Relabel(b, i);
                        if (changed)
                            Diag("read button " + i + " -> "
                                 + Path.GetFileName(file));
                    }
                }
                _gameButtonsActive = any;
            }
            catch (Exception e) { Diag("takeover error: " + e.Message); }
        }

        // 切出受管法语词书时撤销仅由本插件添加的东西。不清空整个 onClick,
        // 否则会删掉其它词书的运行时监听。
        private void RestoreOtherBookUi()
        {
            if (_restoringUi) return;
            _restoringUi = true;
            _playRequest++;
            if (_audio != null) _audio.Stop();
            try
            {
                if (_readStates.Count > 0)
                {
                    List<Button> released = new List<Button>();
                    foreach (KeyValuePair<Button, FrReadBtnState> pair in _readStates)
                    {
                        Button b = pair.Key;
                        FrReadBtnState st = pair.Value;
                        if (b == null || st == null) { released.Add(b); continue; }
                        ReleaseReadState(b, st);
                        released.Add(b);
                    }
                    for (int i = 0; i < released.Count; i++)
                        _readStates.Remove(released[i]);
                }
                _gameButtonsActive = false;
                foreach (KeyValuePair<TMP_Text, GameObject> pair in _buttons)
                {
                    if (pair.Value != null && pair.Value.activeSelf)
                        pair.Value.SetActive(false);
                }
            }
            catch (Exception) { }
            finally { _restoringUi = false; }
        }

        // 撤销单个按钮上的全部接管痕迹并移出登记表。只删本插件添加的
        // 监听/标签, 不清空整个 onClick, 其它词书的监听保持原样。
        private void ReleaseReadState(Button b, FrReadBtnState st)
        {
            if (b == null || st == null) return;
            if (st.actionAttached && st.action != null)
                b.onClick.RemoveListener(st.action);
            st.actionAttached = false;
            foreach (KeyValuePair<TMP_Text, string> label in st.labels)
            {
                if (label.Key == null) continue;
                string frText = label.Value.Replace("读例句", "FR");
                if (label.Key.text == frText)
                    label.Key.text = label.Value;
            }
            FrReadTag tag = b.GetComponent<FrReadTag>();
            if (tag != null) UnityEngine.Object.Destroy(tag);
        }

        void OnDisable()
        {
            RestoreOtherBookUi();
            StopAllCoroutines();
            _loading.Clear();
        }

        void OnDestroy()
        {
            RestoreOtherBookUi();
            StopAllCoroutines();
            if (_audio != null) UnityEngine.Object.Destroy(_audio.gameObject);
            foreach (AudioClip clip in _clips.Values)
                if (clip != null) UnityEngine.Object.Destroy(clip);
            _clips.Clear();
            _clipOrder.Clear();
            foreach (GameObject button in _buttons.Values)
                if (button != null) UnityEngine.Object.Destroy(button);
            _buttons.Clear();
            if (Instance == this) Instance = null;
        }

        // 该序号按钮当前应播放的本地法语音频。
        private string ResolveReadButtonAudio(System.Collections.IList sentences, int i)
        {
            string s;
            s = TmpSentenceAt(_s17, _f17, i);
            if (s != null) { string f = LocalAudio(s); if (f != null) return f; }
            s = TmpSentenceAt(_s8, _f8, i);
            if (s != null) { string f = LocalAudio(s); if (f != null) return f; }
            if (sentences != null && i < sentences.Count)
            {
                s = sentences[i] as string;
                if (!string.IsNullOrEmpty(s))
                {
                    string f = LocalAudio(s);
                    if (f != null) return f;
                }
            }
            return null;
        }

        private static string TmpSentenceAt(object mgr, FieldInfo field, int i)
        {
            if (mgr == null || field == null) return null;
            try
            {
                var comp = mgr as Component;
                if (comp != null && !comp.gameObject.activeInHierarchy) return null;
                var arr = field.GetValue(mgr) as TMP_Text[];
                if (arr == null || i >= arr.Length || arr[i] == null) return null;
                var s = arr[i].text;
                return string.IsNullOrEmpty(s) ? null : s;
            }
            catch (Exception) { return null; }
        }

        // 由例句文本(或 TMP 富文本)定位本地法语 mp3
        private string LocalAudio(string raw)
        {
            string fr = ExtractFr(raw);
            if (fr == null) return null;
            string key = Md5(fr);
            string p;
            // 扫描每 0.3s 跑一次, 缓存 md5 -> 文件路径的磁盘判定,
            // 未命中也缓存, 避免对同一句反复 File.Exists。
            if (_audioLookup.TryGetValue(key, out p)) return p;
            // 只读 pack；Legacy/AudioFallback=true 时恢复迁移期回退链。
            p = Path.Combine(_packAudioDir, key + ".mp3");
            if (!File.Exists(p) && _audioFallback != null && _audioFallback.Value)
                p = Path.Combine(_legacyAudioDir, key + ".mp3");
            p = File.Exists(p) ? p : null;
            _audioLookup[key] = p;
            return p;
        }

        // 标签 "读例句N" -> "FR", 其余文字(如快捷键号)保留; 原文先存进
        // state.labels, 恢复时还原, 其它词书看到的是原样标签。
        private void Relabel(Button b, int i)
        {
            FrReadBtnState state;
            if (!_readStates.TryGetValue(b, out state) || state == null) return;
            var texts = b.GetComponentsInChildren<TMP_Text>(true);
            for (int j = 0; j < texts.Length; j++)
            {
                var s = texts[j].text;
                if (string.IsNullOrEmpty(s)) continue;
                if (s.IndexOf("读例句", StringComparison.Ordinal) >= 0)
                {
                    if (!state.labels.ContainsKey(texts[j])) state.labels[texts[j]] = s;
                    texts[j].text = s.Replace("读例句", "FR");
                    Diag("relabel " + i + ": '" + s + "' -> '" + texts[j].text + "'");
                }
            }
        }

        // 例句按钮上挂着游戏的 SoundTheWordS8: 点一下会去触发单词的英文 TTS
        // (底部 UK/US 按钮), 和法语例句叠在一起。除保留原监听外, 按类型名动
        // 态拦一层, 保证它绝不会为我们接管的按钮发声。
        // 用反射按名字取类型 (不编译期引用游戏类)。
        private void PatchSoundTheWord()
        {
            try
            {
                var t = AccessTools.TypeByName("SoundTheWordS8");
                if (t == null)
                {
                    Log.LogWarning("SoundTheWordS8 not found; 仅靠监听接管");
                    return;
                }
                var m = AccessTools.Method(t, "OnButton1Click");
                if (m == null)
                {
                    Log.LogWarning("SoundTheWordS8.OnButton1Click not found");
                    return;
                }
                var prefix = AccessTools.Method(
                    typeof(FrSentenceAudioPlugin), "SoundTheWordPrefix");
                new Harmony("dev.hanserdesu.sentaudio.fr")
                    .Patch(m, new HarmonyMethod(prefix));
                Log.LogInfo("patched SoundTheWordS8.OnButton1Click");
            }
            catch (Exception e)
            {
                Log.LogWarning("SoundTheWordS8 patch failed: " + e.Message);
            }
        }

        private static bool SoundTheWordPrefix(object __instance)
        {
            try
            {
                if (__instance == null) return true;
                var f = __instance.GetType().GetField("button1",
                    BindingFlags.Public | BindingFlags.NonPublic |
                    BindingFlags.Instance);
                if (f == null) return true;
                var b = f.GetValue(__instance) as Button;
                var plugin = Instance;
                if (plugin != null && b != null &&
                    plugin.IsActivelyTakingOver(b) &&
                    b.GetComponent<FrReadTag>() != null)
                {
                    Diag("blocked english TTS on " + b.name);
                    return false;   // 我们接管的例句按钮: 不触发英文发音
                }
            }
            catch (Exception) { }
            return true;
        }

        // Harmony 前缀的最后一道作用域检查。FrReadTag 在 Destroy 后会等到帧末
        // 才真正消失, 所以不能只看标签; 切书或关闭插件后的这一帧也不应拦截
        // 其它词书的 TTS。
        private bool IsActivelyTakingOver(Button button)
        {
            if (button == null || !isActiveAndEnabled || _enabled == null || !_enabled.Value) return false;
            if (!ManagedBookSelected()) return false;
            FrReadBtnState state;
            return _readStates.TryGetValue(button, out state) &&
                state != null && state.actionAttached;
        }

        internal static void Diag(string msg)
        {
            if (Log != null) Log.LogInfo("[FR-AUDIO] " + msg);
        }

        private void Scan(TMP_Text[] arr)
        {
            if (arr == null) return;
            var seen = new HashSet<TMP_Text>();
            for (int i = 0; i < arr.Length; i++)
            {
                var tmp = arr[i];
                if (tmp == null) continue;
                seen.Add(tmp);
                if (_gameButtonsActive)
                {
                    GameObject owned;
                    if (_buttons.TryGetValue(tmp, out owned) && owned != null &&
                        owned.activeSelf)
                        owned.SetActive(false);
                    continue;
                }
                string fr = null;
                if (tmp.gameObject.activeInHierarchy)
                    fr = ExtractFr(tmp.text);
                string file = null;
                if (fr != null)
                {
                    string p = Path.Combine(_packAudioDir, Md5(fr) + ".mp3");
                    if (!File.Exists(p) && _audioFallback != null && _audioFallback.Value)
                        p = Path.Combine(_legacyAudioDir, Md5(fr) + ".mp3");
                    if (File.Exists(p)) file = p;
                }
                GameObject btn;
                if (!_buttons.TryGetValue(tmp, out btn) || btn == null)
                {
                    if (file == null) continue;
                    btn = CreateButton(tmp);
                    _buttons[tmp] = btn;
                }
                bool show = file != null;
                if (btn.activeSelf != show) btn.SetActive(show);
                if (show)
                {
                    var spb = btn.GetComponent<FrSentencePlayButton>();
                    if (spb.file != file) spb.file = file;
                }
            }
            foreach (var kv in _buttons)
            {
                if (kv.Key == null) continue;
                if (!seen.Contains(kv.Key) && kv.Value != null &&
                    kv.Value.activeSelf)
                    kv.Value.SetActive(false);
            }
        }

        private void CleanupDestroyed()
        {
            List<TMP_Text> dead = null;
            foreach (var kv in _buttons)
            {
                if (kv.Key == null)
                {
                    if (dead == null) dead = new List<TMP_Text>();
                    dead.Add(kv.Key);
                }
            }
            if (dead == null) return;
            for (int i = 0; i < dead.Count; i++) _buttons.Remove(dead[i]);
        }

        private GameObject CreateButton(TMP_Text tmp)
        {
            var go = new GameObject("SentenceAudioFrBtn",
                typeof(RectTransform), typeof(Image), typeof(Button));
            go.transform.SetParent(tmp.gameObject.transform, false);
            var rt = (RectTransform)go.transform;
            rt.anchorMin = new Vector2(1f, 0.5f);
            rt.anchorMax = new Vector2(1f, 0.5f);
            rt.pivot = new Vector2(0f, 0.5f);
            // pivot.x=0 且锚点在文本框右缘: 正偏移会落到文本框外, 超出
            // 父级裁剪矩形时被裁掉。负偏移把 30 宽的按钮收进框内。
            rt.anchoredPosition = new Vector2(-34f, 0f);
            rt.sizeDelta = new Vector2(30f, 30f);
            var img = go.GetComponent<Image>();
            img.color = new Color(0.16f, 0.62f, 0.32f, 0.95f);  // 绿色=法语, 区别日语版蓝
            try
            {
                var font = Resources.GetBuiltinResource<Font>(
                    "LegacyRuntime.ttf");
                var tgo = new GameObject("label", typeof(RectTransform),
                    typeof(Text));
                tgo.transform.SetParent(go.transform, false);
                var trt = (RectTransform)tgo.transform;
                trt.anchorMin = Vector2.zero;
                trt.anchorMax = Vector2.one;
                trt.offsetMin = Vector2.zero;
                trt.offsetMax = Vector2.zero;
                var t = tgo.GetComponent<Text>();
                t.text = "▶";
                t.alignment = TextAnchor.MiddleCenter;
                t.color = Color.white;
                t.fontSize = 17;
                t.font = font;
                t.raycastTarget = false;
            }
            catch (Exception e)
            {
                Log.LogWarning("button label skipped: " + e.Message);
            }
            var spb = go.AddComponent<FrSentencePlayButton>();
            spb.owner = this;
            go.GetComponent<Button>().onClick.AddListener(spb.Play);
            Log.LogInfo("FR sentence button created for: " + tmp.name);
            return go;
        }

        internal void PlayFile(string file)
        {
            if (string.IsNullOrEmpty(file) || !CanPlay()) return;
            int request = ++_playRequest;
            AudioClip cached;
            if (_clips.TryGetValue(file, out cached) && cached != null)
            {
                TouchClip(file);
                PlayClip(cached, file);
                return;
            }
            StartCoroutine(LoadAndPlay(file, request));
        }

        private bool CanPlay()
        {
            return isActiveAndEnabled && _enabled != null && _enabled.Value &&
                ManagedBookSelected();
        }

        private void TouchClip(string file)
        {
            _clipOrder.Remove(file);
            _clipOrder.Add(file);
        }

        private void RememberClip(string file, AudioClip clip)
        {
            if (clip == null || string.IsNullOrEmpty(file)) return;
            if (_clips.ContainsKey(file))
            {
                AudioClip previous = _clips[file];
                if (previous != null && previous != clip)
                    UnityEngine.Object.Destroy(previous);
                _clips[file] = clip;
                TouchClip(file);
                return;
            }
            while (_clipOrder.Count >= _ClipCacheCap)
            {
                string oldest = _clipOrder[0];
                _clipOrder.RemoveAt(0);
                AudioClip old;
                if (oldest != null && _clips.TryGetValue(oldest, out old) &&
                    old != null)
                    UnityEngine.Object.Destroy(old);
                _clips.Remove(oldest);
            }
            _clips[file] = clip;
            _clipOrder.Add(file);
        }

        private void PlayClip(AudioClip clip, string file)
        {
            if (!CanPlay() || clip == null) return;
            try
            {
                _audio.Stop();
                _audio.clip = clip;
                _audio.Play();
            }
            catch (Exception e)
            {
                Log.LogWarning("play failed: " + e.Message + " " + file);
            }
        }

        // 预解码当前词条会用到的例句音频, 避免点击时掉帧。
        private void EnsurePreloaded(string file)
        {
            if (string.IsNullOrEmpty(file)) return;
            if (_clips.ContainsKey(file) || _loading.Contains(file)) return;
            _loading.Add(file);
            StartCoroutine(Preload(file));
        }

        private IEnumerator Preload(string file)
        {
            AudioClip clip = null;
            try
            {
                yield return LoadClip(file, delegate(AudioClip c) { clip = c; });
                if (clip != null) RememberClip(file, clip);
            }
            finally { _loading.Remove(file); }
        }

        private IEnumerator LoadClip(string file, Action<AudioClip> done)
        {
            string url = "file:///" + file.Replace('\\', '/');
            UnityWebRequest www = null;
            try
            {
                www = UnityWebRequestMultimedia.GetAudioClip(url,
                    AudioType.MPEG);
            }
            catch (Exception e)
            {
                Log.LogWarning("audio request failed: " + e.Message + " " + file);
                done(null);
                yield break;
            }
            AudioClip clip = null;
            try
            {
                yield return www.SendWebRequest();
                try
                {
                    if (www.result == UnityWebRequest.Result.Success)
                        clip = DownloadHandlerAudioClip.GetContent(www);
                    else
                        Log.LogWarning("audio load failed: " + www.error + " " + file);
                }
                catch (Exception e) { Log.LogWarning("decode failed: " + e.Message); }
            }
            finally { www.Dispose(); }
            done(clip);
        }

        private IEnumerator LoadAndPlay(string file, int request)
        {
            // Share the preload request; repeated clicks must not decode duplicate clips.
            EnsurePreloaded(file);
            while (_loading.Contains(file)) yield return null;
            if (request != _playRequest || !CanPlay()) yield break;
            AudioClip clip;
            if (_clips.TryGetValue(file, out clip) && clip != null)
            {
                TouchClip(file);
                PlayClip(clip, file);
            }
        }

        // "例句：fr（zh）" / TMP 标记 / "例句：" 前缀 → 还原出纯 fr 文本。
        // 只认「含拉丁字母且不含 CJK/假名」的文本 —— 日语例句留给 SentenceAudioMod,
        // 英语例句没有本地音频, 两种情况都返回 null, 不会互相抢按钮。
        internal static string ExtractFr(string raw)
        {
            if (string.IsNullOrEmpty(raw)) return null;
            string s = Regex.Replace(raw, "<[^>]+>", "");
            s = s.Replace("例句：", "").Trim();
            if (s.Length == 0) return null;
            int nl = s.IndexOf('\n');
            if (nl >= 0) s = s.Substring(0, nl).Trim();
            if (s.EndsWith("）"))
            {
                int i = s.LastIndexOf('（');
                if (i > 0) s = s.Substring(0, i).Trim();
            }
            if (s.Length < 2) return null;
            bool hasLatin = false;
            for (int i = 0; i < s.Length; i++)
            {
                char c = s[i];
                if ((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') ||
                    (c >= 0x00C0 && c <= 0x024F) || c == 'œ' || c == 'Œ' ||
                    c == 'æ' || c == 'Æ')
                {
                    hasLatin = true;
                    break;
                }
            }
            if (!hasLatin) return null;
            // 含 CJK/假名 => 日语例句 (交给日语插件), 本插件不接管
            for (int i = 0; i < s.Length; i++)
            {
                char c = s[i];
                if ((c >= 0x3040 && c <= 0x30FF) ||
                    (c >= 0x3400 && c <= 0x9FFF) ||
                    (c >= 0xF900 && c <= 0xFAFF)) return null;
            }
            return s;
        }

        internal static string Md5(string s)
        {
            using (var md5 = MD5.Create())
            {
                var h = md5.ComputeHash(Encoding.UTF8.GetBytes(s));
                var sb = new StringBuilder(32);
                for (int i = 0; i < h.Length; i++)
                    sb.Append(h[i].ToString("x2"));
                return sb.ToString();
            }
        }

        private static Type FindGameType(string name)
        {
            var t = Type.GetType(name + ", Assembly-CSharp");
            if (t != null) return t;
            var asms = AppDomain.CurrentDomain.GetAssemblies();
            for (int i = 0; i < asms.Length; i++)
            {
                t = asms[i].GetType(name);
                if (t != null) return t;
            }
            return null;
        }
    }

    public class FrSentencePlayButton : MonoBehaviour
    {
        public string file;
        public FrSentenceAudioPlugin owner;

        public void Play()
        {
            if (!string.IsNullOrEmpty(file) && owner != null)
                owner.PlayFile(file);
        }
    }

    // 标记: 该按钮已被改造成法语朗读 (避免重复接管)
    public class FrReadTag : MonoBehaviour
    {
    }

    // 已接管按钮的当前音频映射 (换词时原地更新, 不重新挂监听)
    internal class FrReadBtnState
    {
        public Button btn;
        public FrSentenceAudioPlugin owner;
        public string file;
        public UnityEngine.Events.UnityAction action;
        public bool actionAttached;
        public readonly Dictionary<TMP_Text, string> labels =
            new Dictionary<TMP_Text, string>();

        public void Play()
        {
            if (owner != null) owner.PlayFile(file);
        }
    }
}
