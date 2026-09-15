// WCP Custom Slots — twenty logical wordbook slots on one scrollable page.
//
// The game exposes only four native SelfBookList fields.  This plugin does not
// enlarge or rewrite those game internals.  It keeps twenty rows in its own
// JSON store, imports existing native books as external rows, and materializes
// a selected row only when a free native slot exists.  A non-mod native book is
// never overwritten and is never marked as managed.
using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using BepInEx;
using BepInEx.Logging;
using HarmonyLib;
using UnityEngine;
using UnityEngine.Events;
using UnityEngine.UI;

namespace WcpCustomSlots
{
    internal static class CustomCategoryPatch
    {
        [HarmonyPatch(typeof(WordChooseButtonS10), "OnBookButtonClicked")]
        [HarmonyPostfix]
        private static void Postfix(WordChooseButtonS10 __instance, int num)
        {
            CustomSlotsPlugin plugin = CustomSlotsPlugin.Instance;
            if (plugin == null) return;
            if (num == 20) plugin.Show(__instance);
            else plugin.Hide();
        }
    }

    [BepInPlugin("dev.hanserdesu.customslots", "WCP Custom Slots", "1.0.0")]
    public sealed class CustomSlotsPlugin : BaseUnityPlugin
    {
        internal static CustomSlotsPlugin Instance;
        internal static ManualLogSource Log;

        private const string StoreFile = "WcpCustomSlots.json";
        private const string SeedFile = "WcpCustomSlots.seed.json";
        private const int SelectedNativeSlotFallback = 0;

        private SlotState _state;
        private string _storePath;
        private GameObject _overlay;
        private RectTransform _content;
        private WordChooseButtonS10 _bookChooser;

        private string MyBookPath
        {
            get { return Path.Combine(Application.persistentDataPath, "MyBook.es3"); }
        }

        private string SeedPath
        {
            get { return Path.Combine(Application.persistentDataPath, SeedFile); }
        }

        void Awake()
        {
            Instance = this;
            Log = Logger;
            _storePath = Path.Combine(Application.persistentDataPath, StoreFile);
            _state = LoadState();
            MergeSeed();
            SaveState();
            try
            {
                new Harmony("dev.hanserdesu.customslots").PatchAll(typeof(CustomSlotsPlugin).Assembly);
                Log.LogInfo("CustomSlots: Harmony patch OK; logical slots=" + SlotRules.MaxSlots);
            }
            catch (Exception e) { Log.LogError("CustomSlots: Harmony patch failed: " + e.Message); }
        }

        void OnDestroy()
        {
            Hide();
            if (Instance == this) Instance = null;
        }

        internal void Show(WordChooseButtonS10 chooser)
        {
            _bookChooser = chooser;
            if (_overlay != null)
            {
                _overlay.SetActive(true);
                RebuildRows();
                return;
            }
            Canvas canvas = FindCanvas();
            if (canvas == null)
            {
                Log.LogWarning("CustomSlots: 找不到活动 Canvas，暂不显示 20 槽位页面");
                return;
            }

            _overlay = new GameObject("WcpCustomSlotsOverlay");
            _overlay.transform.SetParent(canvas.transform, false);
            RectTransform panel = _overlay.AddComponent<RectTransform>();
            panel.anchorMin = new Vector2(0.5f, 0.5f);
            panel.anchorMax = new Vector2(0.5f, 0.5f);
            panel.pivot = new Vector2(0.5f, 0.5f);
            panel.sizeDelta = new Vector2(760f, 660f);
            panel.anchoredPosition = Vector2.zero;

            Image panelImage = _overlay.AddComponent<Image>();
            panelImage.color = new Color(0.035f, 0.05f, 0.08f, 0.97f);

            CreateText(_overlay.transform, "WCP 自定义词书（20 槽）", 26, new Vector2(20f, -18f),
                new Vector2(600f, 42f), TextAnchor.UpperLeft, Color.white);
            CreateText(_overlay.transform,
                "滚轮选择。标记为“mod”才会启用语言资源服务；其它词书仅保留原样。",
                14, new Vector2(20f, -57f), new Vector2(680f, 30f), TextAnchor.UpperLeft,
                new Color(0.72f, 0.78f, 0.86f));

            Button close = CreateButton(_overlay.transform, "关闭", new Vector2(-18f, -18f),
                new Vector2(86f, 36f), new Color(0.24f, 0.28f, 0.35f));
            close.GetComponent<RectTransform>().anchorMin = new Vector2(1f, 1f);
            close.GetComponent<RectTransform>().anchorMax = new Vector2(1f, 1f);
            close.GetComponent<RectTransform>().pivot = new Vector2(1f, 1f);
            close.onClick.AddListener(new UnityAction(Hide));

            GameObject viewportObject = new GameObject("Viewport");
            viewportObject.transform.SetParent(_overlay.transform, false);
            RectTransform viewport = viewportObject.AddComponent<RectTransform>();
            viewport.anchorMin = new Vector2(0f, 0f);
            viewport.anchorMax = new Vector2(1f, 1f);
            viewport.offsetMin = new Vector2(18f, 18f);
            viewport.offsetMax = new Vector2(-18f, -94f);
            Image viewportImage = viewportObject.AddComponent<Image>();
            viewportImage.color = new Color(0.02f, 0.03f, 0.05f, 0.8f);
            Mask mask = viewportObject.AddComponent<Mask>();
            mask.showMaskGraphic = false;

            ScrollRect scroll = _overlay.AddComponent<ScrollRect>();
            scroll.viewport = viewport;
            scroll.horizontal = false;
            scroll.vertical = true;
            scroll.movementType = ScrollRect.MovementType.Clamped;
            scroll.scrollSensitivity = 28f;

            GameObject contentObject = new GameObject("Content");
            contentObject.transform.SetParent(viewportObject.transform, false);
            _content = contentObject.AddComponent<RectTransform>();
            _content.anchorMin = new Vector2(0f, 1f);
            _content.anchorMax = new Vector2(1f, 1f);
            _content.pivot = new Vector2(0.5f, 1f);
            _content.anchoredPosition = Vector2.zero;
            _content.sizeDelta = new Vector2(0f, 0f);
            VerticalLayoutGroup layout = contentObject.AddComponent<VerticalLayoutGroup>();
            layout.spacing = 6f;
            layout.padding = new RectOffset(8, 8, 8, 8);
            layout.childControlWidth = true;
            layout.childControlHeight = true;
            layout.childForceExpandWidth = true;
            layout.childForceExpandHeight = false;
            ContentSizeFitter fitter = contentObject.AddComponent<ContentSizeFitter>();
            fitter.verticalFit = ContentSizeFitter.FitMode.PreferredSize;
            fitter.horizontalFit = ContentSizeFitter.FitMode.Unconstrained;
            scroll.content = _content;

            RebuildRows();
        }

        internal void Hide()
        {
            if (_overlay != null) _overlay.SetActive(false);
        }

        private void RebuildRows()
        {
            if (_content == null) return;
            for (int i = _content.childCount - 1; i >= 0; i--)
                UnityEngine.Object.Destroy(_content.GetChild(i).gameObject);
            SlotRules.Normalize(_state);
            for (int i = 0; i < SlotRules.MaxSlots; i++)
            {
                SlotRecord record = _state.slots[i];
                int captured = i;
                string label = RowLabel(record, i + 1);
                Color color = captured + 1 == _state.selected
                    ? new Color(0.12f, 0.34f, 0.26f)
                    : (SlotRules.IsManaged(record)
                        ? new Color(0.10f, 0.18f, 0.29f)
                        : new Color(0.10f, 0.11f, 0.15f));
                Button row = CreateButton(_content, label, Vector2.zero,
                    new Vector2(0f, 48f), color);
                LayoutElement element = row.gameObject.AddComponent<LayoutElement>();
                element.minHeight = 48f;
                element.preferredHeight = 48f;
                row.onClick.AddListener(new UnityAction(delegate { Select(captured); }));
            }
            Canvas.ForceUpdateCanvases();
        }

        private string RowLabel(SlotRecord record, int number)
        {
            if (!SlotRules.HasPlayableWords(record))
                return "槽位 " + number + "    （空）";
            string owner = record.managed ? "mod" : "外部词书";
            string name = string.IsNullOrEmpty(record.name) ? record.id : record.name;
            return "槽位 " + number + "    " + name + "    " + record.words.Length + " 词    [" + owner + "]";
        }

        private void Select(int index)
        {
            if (_state == null || index < 0 || index >= _state.slots.Length) return;
            SlotRecord record = _state.slots[index];
            if (!SlotRules.HasPlayableWords(record))
            {
                Log.LogInfo("CustomSlots: 槽位 " + (index + 1) + " 为空");
                return;
            }
            int nativeSlot = ChooseNativeSlot(record);
            if (nativeSlot == 0)
            {
                Log.LogWarning("CustomSlots: 没有可安全复用的原生槽位；外部词书不会被覆盖");
                return;
            }
            try
            {
                Materialize(record, nativeSlot);
                for (int i = 0; i < _state.slots.Length; i++)
                {
                    if (i != index && _state.slots[i].nativeSlot == nativeSlot &&
                        _state.slots[i].managed)
                        _state.slots[i].nativeSlot = 0;
                }
                record.nativeSlot = nativeSlot;
                _state.selected = index + 1;
                SaveState();
                RebuildRows();
                Log.LogInfo("CustomSlots: 逻辑槽位 " + (index + 1) + " -> 原生槽位 " + nativeSlot +
                    " (" + (record.managed ? "mod" : "external") + ")");
            }
            catch (Exception e) { Log.LogError("CustomSlots: 选择槽位失败: " + e.Message); }
        }

        private int ChooseNativeSlot(SlotRecord record)
        {
            if (record.nativeSlot >= 1 && record.nativeSlot <= SlotRules.NativeSlots &&
                CanUseNativeSlot(record.nativeSlot, record)) return record.nativeSlot;
            for (int i = 1; i <= SlotRules.NativeSlots; i++)
                if (CanUseNativeSlot(i, record)) return i;
            return SelectedNativeSlotFallback;
        }

        private bool CanUseNativeSlot(int nativeSlot, SlotRecord requested)
        {
            string[] words = ReadNativeWords(nativeSlot);
            if (!SlotRules.HasPlayableWords(new SlotRecord { words = words })) return true;
            if (SlotRules.NativeSlotOwnedByManaged(_state, nativeSlot)) return true;
            return SlotRules.SameWords(words, requested.words);
        }

        private void Materialize(SlotRecord record, int nativeSlot)
        {
            string[] words = (string[])record.words.Clone();
            string name = string.IsNullOrEmpty(record.name) ? record.id : record.name;
            string listKey = "SelfBookList" + nativeSlot;
            string nameKey = "SelfBookName" + nativeSlot;
            ES3.Save(listKey, words, MyBookPath);
            ES3.Save(nameKey, name, MyBookPath);
            SetStatic(listKey, words);
            SetStatic(nameKey, name);

            string canonical = Canonical(nativeSlot);
            List<string> chosen = new List<string>(words);
            SetStatic("tem_ChosenBook", canonical);
            SetStatic("tem_ChosenBook_List", new List<string>(chosen));
            SetStatic("ChosenBook_Para", canonical);
            SetStatic("ChosenBook_List", chosen);
            ES3.Save("ChosenBook_Para", canonical);
            ES3.Save("ChosenBook_List", chosen);

            if (_bookChooser != null)
            {
                InvokeNoArg(_bookChooser, "setTemBook");
                SetStatic("tem_ChosenBook_List", new List<string>(chosen));
                SetStatic("ChosenBook_List", new List<string>(chosen));
                InvokeNoArg(_bookChooser, "SonButtonSetting");
                InvokeNoArg(_bookChooser, "InitializeValueSetting3");
                InvokeNoArg(_bookChooser, "showNeedReviewWord");
            }
        }

        private SlotState LoadState()
        {
            try
            {
                if (File.Exists(_storePath))
                {
                    SlotState loaded = JsonUtility.FromJson<SlotState>(File.ReadAllText(_storePath));
                    if (loaded != null)
                    {
                        SlotRules.Normalize(loaded);
                        return loaded;
                    }
                }
            }
            catch (Exception e) { Log.LogWarning("CustomSlots: 读取槽位存档失败: " + e.Message); }

            SlotState fresh = SlotRules.NewState();
            for (int i = 1; i <= SlotRules.NativeSlots; i++)
            {
                string[] words = ReadNativeWords(i);
                if (!SlotRules.HasPlayableWords(new SlotRecord { words = words })) continue;
                string name = ReadNativeName(i);
                SlotRecord external = fresh.slots[i - 1];
                external.name = name;
                external.id = "native-" + i;
                external.owner = "external";
                external.managed = false;
                external.nativeSlot = i;
                external.words = words;
            }
            return fresh;
        }

        private void MergeSeed()
        {
            try
            {
                if (!File.Exists(SeedPath)) return;
                SlotState seed = JsonUtility.FromJson<SlotState>(File.ReadAllText(SeedPath));
                if (seed == null || seed.slots == null) return;
                SlotRules.Normalize(_state);
                foreach (SlotRecord incoming in seed.slots)
                {
                    if (!SlotRules.IsManaged(incoming)) continue;
                    int target = FindLogicalSlot(incoming.id);
                    if (target < 0) target = incoming.number - 1;
                    if (target < 0 || target >= SlotRules.MaxSlots ||
                        SlotRules.HasPlayableWords(_state.slots[target]) &&
                        !string.Equals(_state.slots[target].id, incoming.id, StringComparison.Ordinal))
                        target = FindEmptyLogicalSlot();
                    if (target < 0) continue;
                    SlotRecord copy = CopyRecord(incoming, target + 1);
                    copy.owner = "mod";
                    copy.managed = true;
                    copy.nativeSlot = 0;
                    _state.slots[target] = copy;
                }
            }
            catch (Exception e) { Log.LogWarning("CustomSlots: 读取安装器槽位种子失败: " + e.Message); }
        }

        private int FindLogicalSlot(string id)
        {
            if (string.IsNullOrEmpty(id)) return -1;
            for (int i = 0; i < SlotRules.MaxSlots; i++)
                if (string.Equals(_state.slots[i].id, id, StringComparison.Ordinal)) return i;
            return -1;
        }

        private int FindEmptyLogicalSlot()
        {
            for (int i = 0; i < SlotRules.MaxSlots; i++)
                if (!SlotRules.HasPlayableWords(_state.slots[i])) return i;
            return -1;
        }

        private static SlotRecord CopyRecord(SlotRecord source, int number)
        {
            return new SlotRecord {
                number = number,
                id = source.id ?? "",
                name = source.name ?? "",
                language = source.language ?? "",
                owner = source.owner ?? "mod",
                managed = source.managed,
                nativeSlot = source.nativeSlot,
                words = source.words == null ? new string[0] : (string[])source.words.Clone()
            };
        }

        private void SaveState()
        {
            try
            {
                SlotRules.Normalize(_state);
                Directory.CreateDirectory(Path.GetDirectoryName(_storePath));
                File.WriteAllText(_storePath, JsonUtility.ToJson(_state, true));
            }
            catch (Exception e) { Log.LogWarning("CustomSlots: 保存槽位存档失败: " + e.Message); }
        }

        private string[] ReadNativeWords(int nativeSlot)
        {
            try
            {
                if (!File.Exists(MyBookPath)) return new string[0];
                string[] words = ES3.Load<string[]>("SelfBookList" + nativeSlot, MyBookPath);
                return words ?? new string[0];
            }
            catch { return new string[0]; }
        }

        private string ReadNativeName(int nativeSlot)
        {
            try
            {
                if (!File.Exists(MyBookPath)) return "";
                return ES3.Load<string>("SelfBookName" + nativeSlot, MyBookPath);
            }
            catch { return ""; }
        }

        private static string Canonical(int nativeSlot)
        {
            switch (nativeSlot)
            {
                case 1: return "自定义词书一";
                case 2: return "自定义词书二";
                case 3: return "自定义词书三";
                default: return "自定义词书四";
            }
        }

        private static void SetStatic(string name, object value)
        {
            FieldInfo field = typeof(MyParameters).GetField(name,
                BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static);
            if (field != null) field.SetValue(null, value);
        }

        private static void InvokeNoArg(object instance, string method)
        {
            if (instance == null) return;
            MethodInfo m = instance.GetType().GetMethod(method,
                BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
            if (m != null && m.GetParameters().Length == 0) m.Invoke(instance, null);
        }

        private static Canvas FindCanvas()
        {
            Canvas[] canvases = Resources.FindObjectsOfTypeAll<Canvas>();
            for (int i = 0; i < canvases.Length; i++)
                if (canvases[i] != null && canvases[i].isActiveAndEnabled && canvases[i].gameObject.scene.IsValid())
                    return canvases[i];
            return null;
        }

        private static Text CreateText(Transform parent, string value, int size,
                                       Vector2 position, Vector2 dimensions,
                                       TextAnchor anchor, Color color)
        {
            GameObject go = new GameObject("Text");
            go.transform.SetParent(parent, false);
            RectTransform rt = go.AddComponent<RectTransform>();
            rt.anchorMin = new Vector2(0f, 1f);
            rt.anchorMax = new Vector2(0f, 1f);
            rt.pivot = new Vector2(0f, 1f);
            rt.anchoredPosition = position;
            rt.sizeDelta = dimensions;
            Text text = go.AddComponent<Text>();
            text.text = value;
            text.font = Resources.GetBuiltinResource<Font>("Arial.ttf");
            text.fontSize = size;
            text.alignment = anchor;
            text.color = color;
            text.horizontalOverflow = HorizontalWrapMode.Overflow;
            text.verticalOverflow = VerticalWrapMode.Truncate;
            return text;
        }

        private static Button CreateButton(Transform parent, string value,
                                           Vector2 position, Vector2 dimensions, Color color)
        {
            GameObject go = new GameObject("Button");
            go.transform.SetParent(parent, false);
            RectTransform rt = go.AddComponent<RectTransform>();
            rt.anchorMin = new Vector2(0f, 1f);
            rt.anchorMax = new Vector2(1f, 1f);
            rt.pivot = new Vector2(0.5f, 1f);
            rt.anchoredPosition = position;
            rt.sizeDelta = dimensions;
            Image image = go.AddComponent<Image>();
            image.color = color;
            Button button = go.AddComponent<Button>();
            button.targetGraphic = image;
            button.colors = new ColorBlock {
                normalColor = color,
                highlightedColor = new Color(Mathf.Min(1f, color.r + 0.12f), Mathf.Min(1f, color.g + 0.12f), Mathf.Min(1f, color.b + 0.12f), color.a),
                pressedColor = new Color(Mathf.Min(1f, color.r + 0.2f), Mathf.Min(1f, color.g + 0.2f), Mathf.Min(1f, color.b + 0.2f), color.a),
                selectedColor = color,
                disabledColor = color,
                colorMultiplier = 1f,
                fadeDuration = 0.05f
            };
            Text text = CreateText(go.transform, value, 16, new Vector2(12f, -6f),
                new Vector2(-24f, -12f), TextAnchor.MiddleLeft, Color.white);
            text.rectTransform.anchorMin = new Vector2(0f, 0f);
            text.rectTransform.anchorMax = new Vector2(1f, 1f);
            text.rectTransform.pivot = new Vector2(0.5f, 0.5f);
            text.rectTransform.anchoredPosition = Vector2.zero;
            return button;
        }
    }
}
