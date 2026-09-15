// WCP Sentence Audio RU — BepInEx 5 插件 (俄语变体, 基于 mod_sentence_audio_fr 法语版)
// 功能: 在 每日学习(DatabaseManagerS8) 与 词典查询(DatabaseManagerS17) 的
// 例句旁挂 ▶ 按钮, 点击播放 ru_sentence_audio/<md5(ru)>.mp3 (由
// D:/ATooManyLanguage/Russian/tools/gen_sentence_audio_ru.py 生成, 文件名规则两端一致)。
//
// 与日语版 (SentenceAudioMod) / 法语版 (SentenceAudioFrMod) 的互斥设计:
//   - ExtractRu 只接受「含西里尔字母 且 不含拉丁字母/CJK/假名」的文本 ——
//     日语例句由 SentenceAudioMod 接管, 法语/英语例句由 SentenceAudioFrMod
//     (或无本地音频) 接管, 俄语例句由本插件接管, 三种情况互不重叠,
//     不会互相抢按钮。
//   - 独立插件 GUID / 独立类名 (Ru 前缀), 可与日语/法语版共存。
// 设计: 不 Harmony 补丁游戏方法 (SoundTheWordS8 只挂前缀拦截), 每 0.3s 反射扫描
//   exmplesentences 数组, 游戏更新导致类型变化时自动降级为不显示。
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

namespace SentenceAudioRu
{
    [BepInPlugin("dev.hanserdesu.sentaudio.ru", "WCP Sentence Audio RU", "1.0.0")]
    public class RuSentenceAudioPlugin : BaseUnityPlugin
    {
        internal static ManualLogSource Log;
        internal static RuSentenceAudioPlugin Instance;
        private const float ScanInterval = 0.3f;
        // 资源命名空间化: pack 优先 (packs/ru/audio/sentence),
        // legacy 目录 (ru_sentence_audio) 仅作迁移期回退。
        private const string PackLangCode = "ru";
        private const string AudioDirName = "ru_sentence_audio";

        private AudioSource _audio;
        private ConfigEntry<bool> _enabled;
        private float _nextScan;
        private string _audioDir;
        private string _packAudioDir;
        private readonly Dictionary<Button, RuReadBtnState> _readStates =
            new Dictionary<Button, RuReadBtnState>();
        private bool _gameButtonsActive;
        private static FieldInfo _fSentences;
        private readonly Dictionary<string, AudioClip> _clips =
            new Dictionary<string, AudioClip>();
        private readonly HashSet<string> _loading = new HashSet<string>();
        private Type _t8, _t17;
        private FieldInfo _f8, _f17;
        private object _s8, _s17;
        private readonly Dictionary<TMP_Text, GameObject> _buttons =
            new Dictionary<TMP_Text, GameObject>();

        // 例句按钮是游戏所有词书共用的 UI。只有当前内存词表、当前自定义槽和
        // 已落盘的书名三者一致地指向已登记俄语 Profile 时，才允许接管它。
        // 任何读档/切书中的不一致都失败关闭，宁可暂时不显示俄语按钮，也不碰别的词书。
        private bool ManagedRussianBookSelected()
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
                BookProfile memory = BookProfiles.Match(current);
                if (memory == null || memory.Language != BookProfiles.Russian) return false;
                string path = Path.Combine(Application.persistentDataPath, "MyBook.es3");
                string[] slotWords = ES3.Load<string[]>("SelfBookList" + slot, path);
                BookProfile stored = BookProfiles.Match(slotWords);
                return stored != null && stored.Id == memory.Id;
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

        // 切到其它语言词书时, 还原之前修改过的原版"读例句"按钮
        private void RestoreOtherBookUi()
        {
            if (_readStates.Count > 0)
            {
                foreach (KeyValuePair<Button, RuReadBtnState> pair in _readStates)
                {
                    Button b = pair.Key;
                    RuReadBtnState st = pair.Value;
                    if (b == null || st == null) continue;
                    b.onClick.RemoveAllListeners();
                    st.actionAttached = false;
                    foreach (KeyValuePair<TMP_Text, string> label in st.labels)
                    {
                        if (label.Key != null) label.Key.text = label.Value;
                    }
                    RuReadTag tag = b.GetComponent<RuReadTag>();
                    if (tag != null) UnityEngine.Object.Destroy(tag);
                }
                _readStates.Clear();
            }
            _gameButtonsActive = false;
            foreach (KeyValuePair<TMP_Text, GameObject> pair in _buttons)
            {
                if (pair.Value != null && pair.Value.activeSelf) pair.Value.SetActive(false);
            }
        }

        void Awake()
        {
            Log = Logger;
            Instance = this;
            PatchSoundTheWord();
            var go = new GameObject("SentenceAudioRuPlayer");
            UnityEngine.Object.DontDestroyOnLoad(go);
            _audio = go.AddComponent<AudioSource>();
            _audio.playOnAwake = false;
            _audio.volume = 1f;
            _audio.spatialBlend = 0f;
            _enabled = Config.Bind("General", "Enabled", true,
                "显示俄语例句旁的 ▶ 朗读按钮。");
            string packsRoot = Path.Combine(
                Path.GetDirectoryName(Application.persistentDataPath), "packs");
            _packAudioDir = Path.Combine(packsRoot, PackLangCode, "audio", "sentence");
            _audioDir = Path.Combine(Application.persistentDataPath,
                AudioDirName);
            Log.LogInfo(string.Format(
                "WCP Sentence Audio RU 1.1.0 loaded, pack dir = {0} (存在={1}), legacy dir = {2}",
                _packAudioDir, Directory.Exists(_packAudioDir), _audioDir));
        }

        void Update()
        {
            if (_enabled != null && !_enabled.Value) return;
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
            if (!ManagedRussianBookSelected())
            {
                RestoreOtherBookUi();
                return;
            }
            if (_s8 == null && _s17 == null) return;
            if (_f8 == null && _f17 == null) return;

            if (_s8 != null && _f8 != null)
                Scan(_f8.GetValue(_s8) as TMP_Text[]);
            if (_s17 != null && _f17 != null)
                Scan(_f17.GetValue(_s17) as TMP_Text[]);
            CleanupDestroyed();
            TakeOverGameReadButtons();
        }

        // 把游戏自带的"读例句"按钮改造成俄语朗读 + RU 标签。
        // 只有该句有本地俄语音频时才接管, 否则完整保留游戏原行为。
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
                    var arr = f.GetValue(comp) as Button[];
                    if (arr == null) continue;
                    for (int i = 0; i < arr.Length; i++)
                    {
                        var b = arr[i];
                        if (b == null) continue;
                        any = true;
                        string file = ResolveReadButtonAudio(sentences, i);
                        if (file == null) continue;   // 无俄语本地音频 -> 保留原样
                        RuReadBtnState st;
                        bool isNew = false;
                        if (!_readStates.TryGetValue(b, out st) || st == null)
                        {
                            st = new RuReadBtnState();
                            st.btn = b;
                            st.owner = this;
                            _readStates[b] = st;
                            isNew = true;
                        }
                        if (b.GetComponent<RuReadTag>() == null)
                            b.gameObject.AddComponent<RuReadTag>();
                        if (st.action == null)
                            st.action = new UnityEngine.Events.UnityAction(st.Play);
                        bool changed = isNew ||
                            !string.Equals(st.file, file, StringComparison.Ordinal);
                        st.file = file;
                        // 游戏在这些按钮上挂了 SoundTheWordS8: 点一下会转去播
                        // 单词的英文 TTS, 和例句俄语叠在一起。禁用它, 并把
                        // onClick 收口成只剩我们的监听。
                        SuppressWordTts(b);
                        b.onClick.RemoveAllListeners();
                        b.onClick.AddListener(st.action);
                        st.actionAttached = true;
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

        // 该序号按钮当前应播放的本地俄语音频。
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

        // 由例句文本(或 TMP 富文本)定位本地俄语 mp3
        private string LocalAudio(string raw)
        {
            string ru = ExtractRu(raw);
            if (ru == null) return null;
            // pack 优先, legacy 回退 (迁移期); 都没有才判缺失。
            string p = Path.Combine(_packAudioDir, Md5(ru) + ".mp3");
            if (!File.Exists(p)) p = Path.Combine(_audioDir, Md5(ru) + ".mp3");
            return File.Exists(p) ? p : null;
        }

        // 标签 "读例句N" -> "RU", 其余文字(如快捷键号)保留
        private void Relabel(Button b, int i)
        {
            RuReadBtnState state;
            if (!_readStates.TryGetValue(b, out state) || state == null) return;
            var texts = b.GetComponentsInChildren<TMP_Text>(true);
            for (int j = 0; j < texts.Length; j++)
            {
                var s = texts[j].text;
                if (string.IsNullOrEmpty(s)) continue;
                if (s.IndexOf("读例句", StringComparison.Ordinal) >= 0)
                {
                    if (!state.labels.ContainsKey(texts[j])) state.labels[texts[j]] = s;
                    texts[j].text = s.Replace("读例句", "RU");
                    Diag("relabel " + i + ": '" + s + "' -> '" + texts[j].text + "'");
                }
            }
        }

        // 例句按钮上挂着游戏的 SoundTheWordS8: 点一下会去触发单词的英文 TTS。
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
                    typeof(RuSentenceAudioPlugin), "SoundTheWordPrefix");
                new Harmony("dev.hanserdesu.sentaudio.ru")
                    .Patch(m, new HarmonyMethod(prefix));
                Log.LogInfo("patched SoundTheWordS8.OnButton1Click (RU)");
            }
            catch (Exception e)
            {
                Log.LogWarning("SoundTheWordS8 patch failed: " + e.Message);
            }
        }

        private bool IsActivelyTakingOver(Button button)
        {
            if (button == null || _enabled == null || !_enabled.Value) return false;
            if (!ManagedRussianBookSelected()) return false;
            RuReadBtnState state;
            return _readStates.TryGetValue(button, out state) &&
                state != null && state.actionAttached;
        }

        private static bool SoundTheWordPrefix(object __instance)
        {
            try
            {
                if (__instance == null) return true;
                if (Instance != null && !Instance.ManagedRussianBookSelected()) return true;
                var f = __instance.GetType().GetField("button1",
                    BindingFlags.Public | BindingFlags.NonPublic |
                    BindingFlags.Instance);
                if (f == null) return true;
                var b = f.GetValue(__instance) as Button;
                if (b != null && Instance != null && Instance.IsActivelyTakingOver(b))
                {
                    Diag("blocked english TTS on " + b.name);
                    return false;   // 我们接管的例句按钮: 不触发英文发音
                }
            }
            catch (Exception) { }
            return true;
        }

        internal static void Diag(string msg)
        {
            if (Log != null) Log.LogInfo("[RU-AUDIO] " + msg);
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
                string ru = null;
                if (tmp.gameObject.activeInHierarchy)
                    ru = ExtractRu(tmp.text);
                string file = null;
                if (ru != null)
                {
                    string p = Path.Combine(_packAudioDir, Md5(ru) + ".mp3");
                    if (!File.Exists(p))
                        p = Path.Combine(_audioDir, Md5(ru) + ".mp3");
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
                    var spb = btn.GetComponent<RuSentencePlayButton>();
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
            var go = new GameObject("SentenceAudioRuBtn",
                typeof(RectTransform), typeof(Image), typeof(Button));
            go.transform.SetParent(tmp.gameObject.transform, false);
            var rt = (RectTransform)go.transform;
            rt.anchorMin = new Vector2(1f, 0.5f);
            rt.anchorMax = new Vector2(1f, 0.5f);
            rt.pivot = new Vector2(0f, 0.5f);
            rt.anchoredPosition = new Vector2(34f, 0f);
            rt.sizeDelta = new Vector2(30f, 30f);
            var img = go.GetComponent<Image>();
            img.color = new Color(0.85f, 0.45f, 0.10f, 0.95f);  // 橙色=俄语, 区别日语版蓝/法语版绿
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
            var spb = go.AddComponent<RuSentencePlayButton>();
            spb.owner = this;
            go.GetComponent<Button>().onClick.AddListener(spb.Play);
            Log.LogInfo("RU sentence button created for: " + tmp.name);
            return go;
        }

        internal void PlayFile(string file)
        {
            if (string.IsNullOrEmpty(file)) return;
            AudioClip cached;
            if (_clips.TryGetValue(file, out cached) && cached != null)
            {
                PlayClip(cached, file);
                return;
            }
            StartCoroutine(LoadAndPlay(file));
        }

        private void PlayClip(AudioClip clip, string file)
        {
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
            yield return LoadClip(file, delegate(AudioClip c) { clip = c; });
            _loading.Remove(file);
            if (clip != null) _clips[file] = clip;
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
            yield return www.SendWebRequest();
            AudioClip clip = null;
            try
            {
                if (www.result == UnityWebRequest.Result.Success)
                    clip = DownloadHandlerAudioClip.GetContent(www);
                else
                    Log.LogWarning("audio load failed: " + www.error + " " + file);
            }
            catch (Exception e)
            {
                Log.LogWarning("decode failed: " + e.Message);
            }
            www.Dispose();
            done(clip);
        }

        private IEnumerator LoadAndPlay(string file)
        {
            AudioClip clip = null;
            yield return LoadClip(file, delegate(AudioClip c) { clip = c; });
            if (clip == null)
            {
                Log.LogWarning("audio clip null: " + file);
                yield break;
            }
            _clips[file] = clip;
            PlayClip(clip, file);
        }

        private void SuppressWordTts(Button b)
        {
            try
            {
                var comps = b.GetComponents<MonoBehaviour>();
                for (int i = 0; i < comps.Length; i++)
                {
                    var m = comps[i];
                    if (m == null) continue;
                    if (m.GetType().Name != "SoundTheWordS8") continue;
                    if (m.enabled)
                    {
                        m.enabled = false;
                        Diag("disabled SoundTheWordS8 on " + b.name);
                    }
                }
            }
            catch (Exception e) { Diag("suppress error: " + e.Message); }
        }

        // "例句：ru（zh）" / TMP 标记 / "例句：" 前缀 → 还原出纯 ru 文本。
        // 只认「含西里尔字母且不含拉丁字母/CJK/假名」的文本 —— 日语例句留给
        // SentenceAudioMod, 法语/英语例句留给 SentenceAudioFrMod 或无本地音频,
        // 这几种情况都返回 null, 不会互相抢按钮。
        internal static string ExtractRu(string raw)
        {
            if (string.IsNullOrEmpty(raw)) return null;
            string s = Regex.Replace(raw, "<[^>]+>", "");
            s = s.Replace("例句：", "").Trim();
            if (s.Length == 0) return null;
            int nl = s.IndexOf('\n');
            if (nl >= 0) s = s.Substring(0, nl).Trim();
            if (s.EndsWith("）") || s.EndsWith(")"))
            {
                int i = s.LastIndexOf('（');
                if (i < 0) i = s.LastIndexOf('(');
                if (i > 0) s = s.Substring(0, i).Trim();
            }
            s = s.TrimEnd('。', ' ');
            if (s.Length < 2) return null;
            bool hasCyr = false;
            for (int i = 0; i < s.Length; i++)
            {
                char c = s[i];
                if ((c >= 0x0400 && c <= 0x04FF) || c == 'ё' || c == 'Ё')
                {
                    hasCyr = true;
                    break;
                }
            }
            if (!hasCyr) return null;
            // 含拉丁/CJK/假名 => 别的语言例句, 本插件不接管
            for (int i = 0; i < s.Length; i++)
            {
                char c = s[i];
                if ((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') ||
                    (c >= 0x00C0 && c <= 0x024F) ||
                    (c >= 0x3040 && c <= 0x30FF) ||
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

    public class RuSentencePlayButton : MonoBehaviour
    {
        public string file;
        public RuSentenceAudioPlugin owner;

        public void Play()
        {
            if (!string.IsNullOrEmpty(file) && owner != null)
                owner.PlayFile(file);
        }
    }

    // 标记: 该按钮已被改造成俄语朗读 (避免重复接管)
    public class RuReadTag : MonoBehaviour
    {
    }

    // 已接管按钮的当前音频映射 (换词时原地更新, 不重新挂监听)
    internal class RuReadBtnState
    {
        public Button btn;
        public RuSentenceAudioPlugin owner;
        public string file;
        public UnityEngine.Events.UnityAction action;
        public bool actionAttached;
        public readonly Dictionary<TMP_Text, string> labels = new Dictionary<TMP_Text, string>();

        public void Play()
        {
            if (owner != null) owner.PlayFile(file);
        }
    }
}
