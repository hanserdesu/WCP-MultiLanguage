// WCP Host — 例句音频接入
//
// 例句文本来自游戏当前界面，文件路径只由当前 pack 的路由器解析。
// 宿主只给能命中当前 pack 音频的按钮加自己的监听；切书时逐个移除，
// 从不清空游戏原有的 onClick 监听。
using System;
using System.Collections;
using System.Collections.Generic;
using System.Reflection;
using System.IO;
using HarmonyLib;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

namespace WcpHost
{
    internal sealed class SentenceAudioService
    {
        private readonly HostRuntime _runtime;
        private readonly HostAudioPlayer _audio;
        private readonly Dictionary<Button, ReadState> _states =
            new Dictionary<Button, ReadState>();
        private readonly Dictionary<TMP_Text, string> _labels =
            new Dictionary<TMP_Text, string>();
        private Type _showReadType;
        private FieldInfo _readButtons;
        private Type _t8;
        private Type _t17;
        private FieldInfo _f8;
        private FieldInfo _f17;
        private object _s8;
        private object _s17;
        private float _nextScan;
        private bool _scanBusy;
        // 性能收敛 2026-09-18 第二轮：
        //  _nextFind — 管理器查找闸门。改成 IsAlive 判存活后（见 Tick 注释），
        //              页面不在场时每轮扫描都会重查两次 FindObjectOfType，而
        //              那是全场景遍历。查不到就退避，别再空跑。
        //  ScanIdleInterval — 无变化时的扫描间隔。原实现只要扫到按钮就把间隔
        //              压到 0.3s 并永远保持，等于对一个内容不再变化的批次每秒
        //              做 3.33 次全量对象遍历。
        private float _nextFind;
        private const float FindRetryInterval = 2f;
        private const float ScanBusyInterval = 0.3f;
        private const float ScanIdleInterval = 1f;

        internal SentenceAudioService(HostRuntime runtime, HostAudioPlayer audio)
        {
            _runtime = runtime;
            _audio = audio;
        }

        internal void Tick()
        {
            if (Time.unscaledTime < _nextScan) return;
            // 性能收敛 2026-09-16：0.3s → 1s（按钮出现/消失滞后于人眼无感）；
            // 发生过挂载/移除的扫描后短暂回 0.3s 加速连续出现的响应。
            //
            // 性能收敛 2026-09-18 第二轮：原来的 _scanBusy 只要「扫到按钮」就置
            // true，于是进了 S8/S17 页面后间隔永远钉在 0.3s —— 而按钮一旦挂好，
            // 再扫同一批得到的还是同一批，每次却都要付一次全量对象遍历
            // （Resources.FindObjectsOfTypeAll 的成本与已加载对象数成正比，该
            // 游戏峰值 5.5 万+）。改成只在本轮真的新增/移除了按钮时才加速，
            // 稳定后回到 ScanIdleInterval。
            float interval = _scanBusy ? ScanBusyInterval : ScanIdleInterval;
            _nextScan = Time.unscaledTime + interval;
            if (!_runtime.IsActive || _runtime.ActiveStrategy == null)
            {
                Leave();
                return;
            }
            EnsureTypes();
            if (_showReadType == null || _readButtons == null) return;
            EnsureManagers();
            // ShowReadButtons 只挂在 S8/S17 两个页面上，两者都不在场时直接跳过
            // 全量扫描：扫出来必然为空，跳过不改变任何判定。
            if (!IsAlive(_s8) && !IsAlive(_s17))
            {
                if (_states.Count == 0 && _labels.Count == 0) return;
                Leave();
                return;
            }

            UnityEngine.Object[] objects = Resources.FindObjectsOfTypeAll(_showReadType);
            _scanBusy = false;
            HashSet<Button> seen = new HashSet<Button>();
            for (int i = 0; i < objects.Length; i++)
            {
                Component component = objects[i] as Component;
                if (component == null) continue;
                Button[] buttons = _readButtons.GetValue(component) as Button[];
                if (buttons == null) continue;
                for (int j = 0; j < buttons.Length; j++)
                {
                    Button button = buttons[j];
                    if (button == null) continue;
                    seen.Add(button);
                    bool known = _states.ContainsKey(button);
                    string file = ResolveFile(j);
                    if (string.IsNullOrEmpty(file) || !File.Exists(file))
                    {
                        if (known) _scanBusy = true;
                        Remove(button);
                        continue;
                    }
                    Attach(button, file, j);
                    if (!known) _scanBusy = true;
                }
            }
            if (RemoveUnseen(seen) > 0) _scanBusy = true;
        }

        // 管理器查找闸门（见字段注释）。两个关键点：
        //   1) 「任一在场就跳过」—— S8 与 S17 是两个互斥页面，不会同时存在。
        //      在 S8 页面里 _s17 必然是死引用，原来的实现每轮都要为它做一次
        //      全场景 FindObjectOfType，而结果必然是 null。
        //   2) 两个都不在场（主菜单/选书页等）时退避 FindRetryInterval 秒，
        //      别每轮空跑。退避不会拖慢进页面：切换到 S8/S17 之间必有一次场景
        //      加载（秒级），到时闸门早已过期。
        private void EnsureManagers()
        {
            bool alive8 = IsAlive(_s8);
            bool alive17 = IsAlive(_s17);
            if (alive8 || alive17) return;
            if (Time.unscaledTime < _nextFind) return;
            if (_t8 != null) _s8 = FindObject(_t8);
            if (_t17 != null) _s17 = FindObject(_t17);
            if (!IsAlive(_s8) && !IsAlive(_s17))
                _nextFind = Time.unscaledTime + FindRetryInterval;
        }

        internal bool IsOwnedReadButton(object soundInstance)
        {
            if (soundInstance == null) return false;
            Button button = GameAdapter.InstanceField(soundInstance, "button1") as Button;
            return button != null && _states.ContainsKey(button) &&
                   button.GetComponent<HostSentenceTag>() != null;
        }

        internal void Leave()
        {
            List<Button> buttons = new List<Button>(_states.Keys);
            for (int i = 0; i < buttons.Count; i++) Remove(buttons[i]);
            _states.Clear();
            foreach (KeyValuePair<TMP_Text, string> pair in _labels)
            {
                if (pair.Key != null && pair.Key.text == LabelWritten(pair.Key))
                    pair.Key.text = pair.Value;
            }
            _labels.Clear();
        }

        private void EnsureTypes()
        {
            if (_showReadType == null)
            {
                _showReadType = AccessTools.TypeByName("ShowReadButtons");
                if (_showReadType != null)
                    _readButtons = AccessTools.Field(_showReadType, "ReadButtons");
            }
            if (_t8 == null)
            {
                _t8 = AccessTools.TypeByName("DatabaseManagerS8");
                if (_t8 != null) _f8 = AccessTools.Field(_t8, "exmplesentences");
            }
            if (_t17 == null)
            {
                _t17 = AccessTools.TypeByName("DatabaseManagerS17");
                if (_t17 != null) _f17 = AccessTools.Field(_t17, "exmplesentences");
            }
        }

        private void Attach(Button button, string file, int index)
        {
            ReadState state;
            if (!_states.TryGetValue(button, out state) || state == null)
            {
                state = new ReadState(button, _audio, this);
                _states[button] = state;
                button.gameObject.AddComponent<HostSentenceTag>();
                state.Action = new UnityEngine.Events.UnityAction(state.Play);
                button.onClick.AddListener(state.Action);
            }
            state.File = file;
            Relabel(button, index);
        }

        private void Remove(Button button)
        {
            if (button == null) return;
            ReadState state;
            if (_states.TryGetValue(button, out state) && state != null)
            {
                if (state.Action != null) button.onClick.RemoveListener(state.Action);
                RestoreLabels(state);
                _states.Remove(button);
            }
            HostSentenceTag tag = button.GetComponent<HostSentenceTag>();
            if (tag != null) UnityEngine.Object.Destroy(tag);
        }

        private int RemoveUnseen(HashSet<Button> seen)
        {
            List<Button> dead = new List<Button>();
            foreach (KeyValuePair<Button, ReadState> pair in _states)
                if (pair.Key == null || !seen.Contains(pair.Key)) dead.Add(pair.Key);
            for (int i = 0; i < dead.Count; i++) Remove(dead[i]);
            return dead.Count;
        }

        private void Relabel(Button button, int index)
        {
            ReadState state;
            if (!_states.TryGetValue(button, out state)) return;
            TMP_Text[] texts = button.GetComponentsInChildren<TMP_Text>(true);
            string label = _runtime.ActiveManifest.Profile.Language.ToUpperInvariant();
            for (int i = 0; i < texts.Length; i++)
            {
                TMP_Text text = texts[i];
                if (text == null || string.IsNullOrEmpty(text.text)) continue;
                if (text.text.IndexOf("读例句", StringComparison.Ordinal) < 0) continue;
                if (!_labels.ContainsKey(text)) _labels[text] = text.text;
                text.text = text.text.Replace("读例句", label);
            }
        }

        private void RestoreLabels(ReadState state)
        {
            if (state == null || state.Button == null) return;
            TMP_Text[] texts = state.Button.GetComponentsInChildren<TMP_Text>(true);
            for (int i = 0; i < texts.Length; i++)
            {
                TMP_Text text = texts[i];
                string original;
                if (text != null && _labels.TryGetValue(text, out original) &&
                    text.text == LabelWritten(text))
                {
                    text.text = original;
                    _labels.Remove(text);
                }
            }
        }

        private string LabelWritten(TMP_Text text)
        {
            if (text == null || _runtime.ActiveManifest == null) return null;
            string value = _runtime.ActiveManifest.Profile.Language.ToUpperInvariant();
            string original;
            if (!_labels.TryGetValue(text, out original)) return null;
            return original.Replace("读例句", value);
        }

        private string ResolveFile(int index)
        {
            string raw = SentenceAt(_s17, _f17, index);
            string file = Resolve(raw);
            if (file != null) return file;
            raw = SentenceAt(_s8, _f8, index);
            file = Resolve(raw);
            if (file != null) return file;
            object rawSentences = GameAdapter.StaticField(GameAdapter.ParametersType, "exaple_sentences");
            IList list = rawSentences as IList;
            if (list != null && index >= 0 && index < list.Count)
                return Resolve(list[index] as string);
            return null;
        }

        private string Resolve(string raw)
        {
            if (string.IsNullOrEmpty(raw) || _runtime.ActiveStrategy == null) return null;
            string key;
            try { key = _runtime.ActiveStrategy.ExtractSentenceKey(raw); }
            catch (Exception e)
            {
                if (WcpHostPlugin.Log != null)
                    WcpHostPlugin.Log.LogWarning("WcpHost: 例句策略解析失败: " + e.Message);
                return null;
            }
            if (string.IsNullOrEmpty(key)) return null;
            string path = _runtime.ActiveManifest == null ? null :
                WcpHostPlugin.Instance.Router.Resolve(ResourceKind.SentenceAudio, key);
            return string.IsNullOrEmpty(path) || !File.Exists(path) ? null : path;
        }

        private static string SentenceAt(object manager, FieldInfo field, int index)
        {
            if (manager == null || field == null || index < 0) return null;
            try
            {
                Component c = manager as Component;
                if (c != null && !c.gameObject.activeInHierarchy) return null;
                IList list = field.GetValue(manager) as IList;
                if (list == null || index >= list.Count) return null;
                TMP_Text text = list[index] as TMP_Text;
                return text == null ? null : text.text;
            }
            catch (Exception) { return null; }
        }

        // Unity 假 null 判存活：字段声明为 object 时 == null 是引用比较，
        // 走不到 UnityEngine.Object 的重载，已销毁对象会被误判为"还在"。
        private static bool IsAlive(object o)
        {
            return (o as Component) != null;
        }

        private static object FindObject(Type type)
        {
            try { return UnityEngine.Object.FindObjectOfType(type); }
            catch (Exception) { return null; }
        }

        private sealed class ReadState
        {
            internal readonly Button Button;
            internal readonly HostAudioPlayer Audio;
            internal readonly SentenceAudioService Owner;
            internal UnityEngine.Events.UnityAction Action;
            internal string File;

            internal ReadState(Button button, HostAudioPlayer audio, SentenceAudioService owner)
            {
                Button = button;
                Audio = audio;
                Owner = owner;
            }

            internal void Play()
            {
                if (Owner != null && Button != null &&
                    Button.GetComponent<HostSentenceTag>() != null)
                    Audio.Play(File);
            }
        }
    }
}
