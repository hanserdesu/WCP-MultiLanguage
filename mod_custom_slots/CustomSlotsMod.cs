// WCP Custom Slots — twenty logical wordbook slots on one scrollable page.
//
// The game exposes only four native SelfBookList fields.  This plugin does not
// enlarge or rewrite those game internals.  It keeps twenty rows in its own
// JSON store, imports existing native books as external mirror rows on every
// load (P1-1), and materializes a selected row only when a free native slot
// exists.  A native slot whose live words are snapshotted by any row can be
// taken over safely (content is restorable from that row); unknown content is
// never overwritten (fail-closed).  Rename/remove act on mod rows only and
// never touch SelfBookNameN (P1-2).
using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Text;
using BepInEx;
using BepInEx.Logging;
using HarmonyLib;
using UnityEngine;
using UnityEngine.Events;
using UnityEngine.EventSystems;
using UnityEngine.UI;

namespace WcpCustomSlots
{
    // 入口补丁：编译期不绑定游戏类型（HarmonyPatch 属性必须给 Type，所以这里用
    // 运行时解析 + 显式 Patch，见 CustomSlotsPlugin.PatchEntryExplicitly）。
    // 补丁目标是 GameCompat.EntryMethod 解析出的方法；解析失败则只保留 F8 热键入口。
    internal static class CustomCategoryPatch
    {
        // 诊断：确认补丁是否真的被调用、以及实际收到哪些 num。
        private static int _seen;
        private static int _lastNum = int.MinValue;

        // Harmony 以 __instance/__0 按名字注入；用 object/int 接住，不绑类型。
        internal static void Postfix(object __instance, int num)
        {
            CustomSlotsPlugin plugin = CustomSlotsPlugin.Instance;
            string stack = DescribeStack();
            bool programmatic = false;
            try { programmatic = CalledFromGameInitialization(); }
            catch (Exception) { }

            // 信号 c：只有「UGUI 按钮回调栈」才算用户点击并记录页签。
            // 不能用 CalledFromGameInitialization 来过滤 —— 实测它把真实点击也判成
            // 初始化（Unity 事件系统深处有同名 Initialize 帧，见 2026-09-16 日志）。
            try { if (CalledFromUserClick()) GameCompat.NotePageClick(num); }
            catch (Exception) { }

            // 兼容层核心：不靠 num 魔数，改用"页面状态"判定。
            bool customPage = false;
            try { customPage = GameCompat.IsCustomPageShowing(__instance); }
            catch (Exception) { }

            if (_seen < 40 || num != _lastNum)
            {
                _seen++;
                _lastNum = num;
                if (CustomSlotsPlugin.Log != null)
                    CustomSlotsPlugin.Log.LogInfo("CustomSlots: postfix num=" + num +
                        "; plugin=" + (plugin != null ? "ok" : "NULL") +
                        "; 程序化=" + (programmatic ? "是(忽略)" : "否") +
                        "; 自定义页=" + (customPage ? "是" : "否") +
                        "; 栈=" + stack);
            }
            if (plugin == null) return;

            // 显示判据统一由 Update 轮询决定（见 PollCustomPage）。
            // 钩子这里只做即时响应，避免轮询间隔带来的延迟。
            plugin.ReactToPageChange(__instance);
        }

        // 打印调用栈前若干帧的方法名，用于判定"用户点击"与"游戏初始化"的真实差异。
        private static string DescribeStack()
        {
            try
            {
                System.Diagnostics.StackTrace st = new System.Diagnostics.StackTrace();
                StringBuilder sb = new StringBuilder();
                int frames = st.FrameCount;
                for (int i = 0; i < frames && i < 8; i++)
                {
                    System.Reflection.MethodBase m = st.GetFrame(i).GetMethod();
                    if (m == null) continue;
                    if (sb.Length > 0) sb.Append(" < ");
                    sb.Append(m.DeclaringType != null ? m.DeclaringType.Name + "." : "").Append(m.Name);
                }
                return sb.ToString();
            }
            catch (Exception) { return "?"; }
        }

        // 只有游戏自己的初始化路径会从 Initialize/Initialize_ResetButton 直接调用；
        // 用户点击的调用栈来自按钮回调。
        private static bool CalledFromGameInitialization()
        {
            try
            {
                System.Diagnostics.StackTrace stack = new System.Diagnostics.StackTrace();
                int frames = stack.FrameCount;
                for (int i = 1; i < frames && i < 24; i++)
                {
                    System.Reflection.MethodBase m = stack.GetFrame(i).GetMethod();
                    if (m == null) continue;
                    string name = m.Name;
                    if (name == "Initialize" || name == "Initialize_ResetButton") return true;
                }
            }
            catch (Exception) { }
            return false;
        }

        // 信号 c 的过滤器：UGUI 按钮回调栈的特征帧。实测（2026-09-16 日志）
        // 用户点击的栈含 Button.Press/OnPointerClick；游戏初始化调用不含。
        // 不用 CalledFromGameInitialization 判此题 —— 它会把真实点击也判成初始化
        // （事件系统深处存在同名 Initialize 帧）。
        private static bool CalledFromUserClick()
        {
            try
            {
                System.Diagnostics.StackTrace stack = new System.Diagnostics.StackTrace();
                int frames = stack.FrameCount;
                for (int i = 1; i < frames && i < 24; i++)
                {
                    System.Reflection.MethodBase m = stack.GetFrame(i).GetMethod();
                    if (m == null) continue;
                    string name = m.Name;
                    if (name == "Press" || name == "OnPointerClick" || name == "Invoke") return true;
                }
            }
            catch (Exception) { }
            return false;
        }
    }

    [BepInPlugin("dev.hanserdesu.customslots", "WCP Custom Slots", "1.2.1")]
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
        private object _bookChooser;
        private GameObject _renameBar;
        private InputField _renameInput;
        private Text _renameTitle;
        private int _renameIndex = -1;
        private Text _toast;
        private float _toastUntil;
        private float _lastVisibilityCheck;
        // 用户刚通过 F8/关闭按钮手动关掉面板：本轮停在自定义页时轮询不再自动重开，
        // 否则用户想看原生 4 行时面板会每 0.25 秒弹回来。离开页面后复位。
        private bool _userDismissed;
        private bool _autoDiagDone;   // 原生页几何自动采集只做一次

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
            int imported = ImportNativeBooksNow();
            MergeSeed();
            VerifySerializerRoundTrip();
            SaveState();
            try
            {
                new Harmony("dev.hanserdesu.customslots").PatchAll(typeof(CustomSlotsPlugin).Assembly);
                Log.LogInfo("CustomSlots: Harmony patch OK; logical slots=" + SlotRules.MaxSlots +
                    "; native mirror rows imported=" + imported);
            }
            catch (Exception e) { Log.LogError("CustomSlots: Harmony patch failed: " + e.Message); }
            PatchEntryExplicitly();
        }

        // PatchAll 报 OK 也可能是"没挂上"（实机实测 postfixes=0 且无异常）。
        // 这里用显式 Patch 补挂，并把真实结果（挂上前后 postfix 数）写进日志。
        // 目标方法来自兼容层解析（不绑定编译期类型名）。
        private void PatchEntryExplicitly()
        {
            try
            {
                Log.LogInfo("CustomSlots: 兼容层解析结果 → " + GameCompat.Notes);
                System.Reflection.MethodInfo target = GameCompat.EntryMethod;
                if (target == null)
                {
                    Log.LogWarning("CustomSlots: 入口方法未解析出来；只保留 F8 热键入口（其它功能不受影响）");
                    return;
                }

                Patches before = Harmony.GetPatchInfo(target);
                int beforeCount = (before == null || before.Postfixes == null) ? 0 : before.Postfixes.Count;
                if (beforeCount == 0)
                {
                    System.Reflection.MethodInfo postfix =
                        typeof(CustomCategoryPatch).GetMethod("Postfix",
                            System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Static);
                    if (postfix == null) { Log.LogError("CustomSlots: 未找到 Postfix 方法"); return; }
                    new Harmony("dev.hanserdesu.customslots.entry")
                        .Patch(target, postfix: new HarmonyMethod(postfix));
                    Log.LogInfo("CustomSlots: 显式补挂 " + target.DeclaringType.Name + "." + target.Name);
                }

                Patches after = Harmony.GetPatchInfo(target);
                int afterCount = (after == null || after.Postfixes == null) ? -1 : after.Postfixes.Count;
                Log.LogInfo("CustomSlots: patch 状态 " + target.DeclaringType.Name + "." + target.Name +
                    " postfixes=" + afterCount +
                    (afterCount > 0 ? "（已挂上）" : "（未挂上！改用 F8 热键入口）"));
            }
            catch (Exception e) { Log.LogError("CustomSlots: 显式补挂失败: " + e); }
        }

        void OnDestroy()
        {
            Hide();
            if (Instance == this) Instance = null;
        }

        // Unity 的 JsonUtility 对嵌套/数组字段有序列化限制（历史实测：4 行有词却只写出 38 字节）。
        // 这里在启动时做一次真实往返自检，把"存档把 slots 丢掉"这类静默数据丢失暴露到日志里。
        private void VerifySerializerRoundTrip()
        {
            try
            {
                SlotRules.Normalize(_state);
                string json = SlotRules.Serialize(_state);
                SlotState back = SlotRules.Deserialize(json);
                int rowsBack = (back == null || back.slots == null) ? -1 : back.slots.Length;
                bool ok = rowsBack == _state.slots.Length;
                Log.LogInfo("CustomSlots: serializer round-trip bytes=" + json.Length +
                    "; rows=" + _state.slots.Length + " -> " + rowsBack +
                    (ok ? " (OK)" : " (LOSS! slots 未落盘)"));
            }
            catch (Exception e) { Log.LogWarning("CustomSlots: serializer round-trip 失败: " + e.Message); }
        }

        internal void Show(object chooser)
        {
            _bookChooser = chooser;
            GameCompat.CalibrateCustomPageIndex(chooser);
            if (_overlay != null)
            {
                _overlay.SetActive(true);
                Log.LogInfo("CustomSlots: Show → 复用已有覆盖层（20 行）");
                RebuildRows();
                return;
            }
            Canvas canvas = null;
            Component chooserComponent = _bookChooser as Component;
            if (chooserComponent != null) canvas = chooserComponent.GetComponentInParent<Canvas>();
            if (canvas == null) canvas = FindCanvas();
            if (canvas == null)
            {
                Log.LogWarning("CustomSlots: 找不到活动 Canvas，暂不显示 20 槽位页面");
                return;
            }
            Log.LogInfo("CustomSlots: Show → 新建覆盖层; canvas=" + canvas.name +
                "; sortingOrder=" + canvas.sortingOrder);

            _overlay = new GameObject("WcpCustomSlotsOverlay");
            _overlay.transform.SetParent(canvas.transform, false);
            // 覆盖层必须自建 Canvas + 强制排序：只挂在游戏 Canvas 下会被原生 UI 盖住。
            // 注意：Canvas 自带 [RequireComponent(RectTransform)]，AddComponent<Canvas> 会
            // 自动补上 RectTransform —— 之后不能再 AddComponent<RectTransform>()，
            // 否则报 "already added"、返回 null，随后 panel 解引用直接 NRE（实机踩过）。
            Canvas overlayCanvas = _overlay.AddComponent<Canvas>();
            overlayCanvas.overrideSorting = true;
            overlayCanvas.sortingOrder = 32760;
            _overlay.transform.SetAsLastSibling();
            RectTransform panel = _overlay.GetComponent<RectTransform>();
            if (panel == null) panel = _overlay.AddComponent<RectTransform>();
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
            close.onClick.AddListener(new UnityAction(OnCloseButton));
            EnsureEventSystem();
            CreateActionButton(_overlay.transform, "刷新", new Vector2(-112f, -18f),
                new Vector2(56f, 36f), new Color(0.16f, 0.30f, 0.38f),
                new UnityAction(RefreshFromDisk), true);

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

            EnsureInputField(_overlay.transform);
            RebuildRows();
        }

        // 关闭按钮：与 F8 同一语义 —— 手动关闭后轮询不再自动重开（本轮停留期间）。
        private void OnCloseButton()
        {
            Hide();
            _userDismissed = true;
        }

        internal void Hide()
        {
            if (_overlay != null && _overlay.activeSelf)
                Log.LogInfo("CustomSlots: Hide → 关闭覆盖层");
            if (_renameBar != null) { UnityEngine.Object.Destroy(_renameBar); _renameBar = null; }
            _renameInput = null;
            _renameTitle = null;
            _renameIndex = -1;
            if (_toast != null && _toast.gameObject.activeSelf) _toast.gameObject.SetActive(false);
            if (_overlay != null) _overlay.SetActive(false);
        }

        private void Update()
        {
            // 每帧检查"是否停在自定义词书页且页面可见"——这是唯一的显示判据，
            // 不依赖点击钩子（钩子只在页签被点击时触发，直接进入该页时不会触发）。
            if (Time.unscaledTime - _lastVisibilityCheck > 0.25f)
            {
                _lastVisibilityCheck = Time.unscaledTime;
                PollCustomPage();
            }

            // 手动入口兜底：不依赖游戏方法钩子。F8 打开/关闭 20 槽面板。
            if (Input.GetKeyDown(KeyCode.F8))
            {
                if (_overlay != null && _overlay.activeSelf)
                {
                    Hide();
                    _userDismissed = true; // 轮询不许立即弹回
                }
                else
                {
                    _userDismissed = false;
                    object chooser = GameCompat.FindChooserInstance();
                    Log.LogInfo("CustomSlots: F8 手动打开（chooser=" + GameCompat.Describe(chooser) + "）");
                    Show(chooser);
                }
            }
            // F9：手动重采原生页层级（自动采集见 PollCustomPage；写文件，不依赖日志刷新）。
            if (Input.GetKeyDown(KeyCode.F9)) DumpNativeBookPage("manual");

            if (_overlay == null || !_overlay.activeSelf) return;
            if (_toast != null && _toast.gameObject.activeSelf && Time.unscaledTime > _toastUntil)
                _toast.gameObject.SetActive(false);
            if (Input.GetKeyDown(KeyCode.Escape))
            {
                if (_renameIndex >= 0) CancelRename();
                else { Hide(); _userDismissed = true; }
            }
            else if (_renameIndex >= 0 &&
                     (Input.GetKeyDown(KeyCode.Return) || Input.GetKeyDown(KeyCode.KeypadEnter)))
                SubmitRename();
        }

        // 钩子回调入口：与轮询共用同一判据（页面可见 + 处于自定义页）。
        internal void ReactToPageChange(object chooser)
        {
            try
            {
                if (GameCompat.IsChooserVisible(chooser) && GameCompat.IsCustomPageShowing(chooser))
                {
                    if (_overlay == null || !_overlay.activeSelf)
                    {
                        Log.LogInfo("CustomSlots: 钩子 → 显示面板");
                        Show(chooser);
                    }
                }
                else if (_overlay != null && _overlay.activeSelf)
                {
                    Log.LogInfo("CustomSlots: 钩子 → 隐藏面板");
                    Hide();
                }
            }
            catch (Exception e) { Log.LogWarning("CustomSlots: 钩子响应失败: " + e.Message); }
        }

        // 轮询"是否停在自定义词书页且页面可见"，据此显示/隐藏面板。
        // 轮询而非依赖点击钩子：用户可能直接就停在该页（不点页签），钩子不会触发。
        // 场景里可能有多个 chooser 实例（实机日志见两个 canvas 各挂一份）——
        // 必须找"可见的那个"来判，拿错实例会得出"不在页"的假象。
        private void PollCustomPage()
        {
            try
            {
                object chooser = GameCompat.FindVisibleChooserInstance();
                if (chooser == null)
                {
                    // 选书窗整体不可见：清掉页签点击信号，避免旧点击跨界面生效
                    GameCompat.ClearUserPageNum();
                    _userDismissed = false;
                    if (_overlay != null && _overlay.activeSelf)
                    {
                        Log.LogInfo("CustomSlots: 轮询 → 选书窗不可见，隐藏面板");
                        Hide();
                    }
                    return;
                }
                bool want = GameCompat.IsCustomPageShowing(chooser);
                bool shown = _overlay != null && _overlay.activeSelf;
                // 原生层级几何采集自动触发：挂热键的方案连续多轮都拿不到文件。
                // 只在首次进入该页时写盘一次（F9 可手动重采）。
                if (want && !_autoDiagDone)
                {
                    _autoDiagDone = true;
                    DumpNativeBookPage("auto");
                }
                if (!want)
                {
                    _userDismissed = false;
                    GameCompat.ClearUserPageNum();
                    if (shown)
                    {
                        Log.LogInfo("CustomSlots: 轮询 → 离开自定义页，隐藏面板");
                        Hide();
                    }
                    return;
                }
                if (shown) return;
                if (_userDismissed) return; // 用户刚手动关掉：停在页上不自动重开
                Log.LogInfo("CustomSlots: 轮询 → 进入自定义页，显示面板");
                Show(chooser);
            }
            catch (Exception e) { Log.LogWarning("CustomSlots: 轮询失败: " + e.Message); }
        }

        // 诊断用：dump 原生词书页的真实层级与可克隆参数，用于"无缝扩展原生列表 + 滚动条"改造。
        // 写成 <persistentDataPath>/WcpSlotsDiag.txt（不依赖日志被刷新）。
        // source=auto：首次发现该页可见时自动采集；manual：F9 手动重采。
        private void DumpNativeBookPage(string source)
        {
            try
            {
                object chooser = GameCompat.FindVisibleChooserInstance();
                if (chooser == null) chooser = GameCompat.FindChooserInstance();
                Component chooserComponent = chooser as Component;
                if (chooserComponent == null)
                {
                    Log.LogWarning("CustomSlots: dump 找不到词书页实例（" + source + "）");
                    return;
                }

                List<string> lines = new List<string>();
                lines.Add("=== WCP native book page dump (" + source + ") " +
                          DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + " ===");
                lines.Add("compat: " + GameCompat.Notes);
                lines.Add("chooser type = " + chooser.GetType().FullName);
                lines.Add("chooser path = " + GameCompat.NodePath(chooserComponent.transform));
                lines.Add("screen = " + Screen.width + "x" + Screen.height + " dpi=" + Screen.dpi);
                lines.Add("BookButtonFather=" + GameCompat.Count(GameCompat.GetFatherButtons(chooser)) +
                          " BookButtonSon=" + GameCompat.Count(GameCompat.GetSonButtons(chooser)) +
                          " BookNameText=" + GameCompat.Count(GameCompat.GetNameTexts(chooser)) +
                          " LearnedNumInBook=" + GameCompat.Count(GameCompat.GetLearnedButtons(chooser)));
                lines.Add("isCustomPage=" + (GameCompat.IsCustomPageShowing(chooser) ? "yes" : "no") +
                          " calibratedTabIndex=" + GameCompat.CustomPageIndex);
                lines.Add("");

                // 父链：把新容器挂回原页面时要按原样对齐各级容器尺寸与锚点。
                lines.Add("--- parent chain (0 = chooser root) ---");
                Transform up = chooserComponent.transform;
                for (int depth = 0; up != null && depth < 12; depth++)
                {
                    lines.Add("[" + depth + "] " + DescribeTransform(up));
                    Canvas cv = up.GetComponent<Canvas>();
                    if (cv != null)
                        lines.Add(new string(' ', 6) + "Canvas: renderMode=" + cv.renderMode + " sortingOrder=" +
                                  cv.sortingOrder + " overrideSorting=" + cv.overrideSorting +
                                  " pixelPerfect=" + cv.pixelPerfect + " scaleFactor=" + cv.scaleFactor);
                    CanvasScaler scaler = up.GetComponent<CanvasScaler>();
                    if (scaler != null)
                        lines.Add(new string(' ', 6) + "CanvasScaler: uiScaleMode=" + scaler.uiScaleMode +
                                  " refRes=" + scaler.referenceResolution.x + "x" + scaler.referenceResolution.y +
                                  " match=" + scaler.matchWidthOrHeight + " screenMatchMode=" + scaler.screenMatchMode +
                                  " scaleFactor=" + scaler.scaleFactor);
                    up = up.parent;
                }
                lines.Add("");

                lines.Add("--- chooser subtree (depth<=7) ---");
                DumpNode(chooserComponent.transform, lines, 0, 7);
                lines.Add("");
                lines.Add("--- BookButtonFather (native 4 rows container) ---");
                DumpArray(GameCompat.GetFatherButtons(chooser), "Father", lines);
                lines.Add("--- BookButtonSon ---");
                DumpArray(GameCompat.GetSonButtons(chooser), "Son", lines);
                lines.Add("--- BookNameText ---");
                DumpArray(GameCompat.GetNameTexts(chooser), "NameText", lines);
                lines.Add("--- LearnedNumInBook ---");
                DumpArray(GameCompat.GetLearnedButtons(chooser), "LearnedNum", lines);
                lines.Add("");

                DumpScrollTemplates(lines);
                DumpFonts(chooserComponent.transform, lines);

                // 落点必须在 Steam 云同步范围（LocalLow\WCP\wcp 整目录）之外：
                // 一次性诊断文件不许进同步队列；失败退回 persistentDataPath（只记日志，不阻断）。
                string path = DiagPath();
                Directory.CreateDirectory(Path.GetDirectoryName(path));
                File.WriteAllText(path, string.Join("\n", lines.ToArray()));
                Log.LogInfo("CustomSlots: native page dumped (" + source + ") -> " + path +
                            " (" + lines.Count + " lines)");
            }
            catch (Exception e) { Log.LogError("CustomSlots: dump 原生页失败: " + e); }
        }

        // 组件可克隆参数：克隆原生行/滚动条时这些值必须照抄，靠猜必然"永远差一点"。
        private string DescribeComponent(Component c)
        {
            if (c == null) return "(null)";
            string type = c.GetType().Name;
            if (c is Image)
            {
                Image img = (Image)c;
                return "Image color=" + Fmt(img.color) + " sprite=" + (img.sprite == null ? "(none)" : img.sprite.name) +
                       " type=" + img.type + " preserveAspect=" + img.preserveAspect + " raycast=" + img.raycastTarget;
            }
            if (c is UnityEngine.UI.Text)
            {
                UnityEngine.UI.Text tx = (UnityEngine.UI.Text)c;
                return "Text text='" + Clip(tx.text) + "' fontSize=" + tx.fontSize + " font=" +
                       (tx.font == null ? "(none)" : tx.font.name) + " color=" + Fmt(tx.color) + " style=" + tx.fontStyle +
                       " align=" + tx.alignment + " bestFit=" + tx.resizeTextForBestFit + " raycast=" + tx.raycastTarget;
            }
            if (c is Button)
            {
                Button b = (Button)c;
                string target = b.targetGraphic is Image ? " targetColor=" + Fmt(((Image)b.targetGraphic).color) : "";
                return "Button interactable=" + b.interactable + " transition=" + b.transition + target;
            }
            if (c is ScrollRect)
            {
                ScrollRect sr = (ScrollRect)c;
                return "ScrollRect movement=" + sr.movementType + " h=" + sr.horizontal + " v=" + sr.vertical +
                       " inertia=" + sr.inertia + " elasticity=" + sr.elasticity + " decel=" + sr.decelerationRate +
                       " sensitivity=" + sr.scrollSensitivity + " viewport=" + PathOf(sr.viewport) +
                       " content=" + PathOf(sr.content) + " vScrollbar=" + PathOf(sr.verticalScrollbar == null ? null : sr.verticalScrollbar.transform) +
                       " vScrollbarVisibility=" + sr.verticalScrollbarVisibility;
            }
            if (c is Scrollbar)
            {
                Scrollbar sb = (Scrollbar)c;
                return "Scrollbar direction=" + sb.direction + " value=" + sb.value + " size=" + sb.size +
                       " steps=" + sb.numberOfSteps + " handle=" + PathOf(sb.handleRect) +
                       " normalColor=" + Fmt(sb.colors.normalColor);
            }
            if (c is Mask) return "Mask showMaskGraphic=" + ((Mask)c).showMaskGraphic;
            if (type.IndexOf("RectMask2D", StringComparison.Ordinal) >= 0) return "RectMask2D";
            if (c is CanvasGroup)
            {
                CanvasGroup g = (CanvasGroup)c;
                return "CanvasGroup alpha=" + g.alpha + " interactable=" + g.interactable +
                       " blocksRaycasts=" + g.blocksRaycasts + " ignoreParent=" + g.ignoreParentGroups;
            }
            if (type.IndexOf("LayoutGroup", StringComparison.Ordinal) >= 0)
                return type + " spacing=" + Refl(c, "spacing") + " padding=" + Refl(c, "padding") +
                       " align=" + Refl(c, "childAlignment") + " controlW=" + Refl(c, "childControlWidth") +
                       " controlH=" + Refl(c, "childControlHeight") + " expandW=" + Refl(c, "childForceExpandWidth") +
                       " expandH=" + Refl(c, "childForceExpandHeight") + " cellSize=" + Refl(c, "cellSize");
            if (type.IndexOf("ContentSizeFitter", StringComparison.Ordinal) >= 0)
                return "ContentSizeFitter h=" + Refl(c, "horizontalFit") + " v=" + Refl(c, "verticalFit");
            if (type.IndexOf("LayoutElement", StringComparison.Ordinal) >= 0)
                return "LayoutElement minH=" + Refl(c, "minHeight") + " prefH=" + Refl(c, "preferredHeight") +
                       " minW=" + Refl(c, "minWidth") + " prefW=" + Refl(c, "preferredWidth") +
                       " flexibleH=" + Refl(c, "flexibleHeight");
            // 文本类组件不绑 TMPro：反射读 TMP_Text 的公开属性。
            if (type.IndexOf("Text", StringComparison.Ordinal) >= 0)
                return type + " text='" + Clip(GameCompat.ReadText(c)) + "' fontSize=" + Refl(c, "fontSize") +
                       " font=" + Refl(c, "font") + " color=" + Refl(c, "color") + " style=" + Refl(c, "fontStyle") +
                       " align=" + Refl(c, "alignment") + " wrap=" + Refl(c, "enableWordWrapping");
            return type;
        }

        private string DescribeTransform(Transform t)
        {
            if (t == null) return "(null)";
            string comps = "";
            Component[] cs = t.GetComponents<Component>();
            if (cs != null)
                foreach (Component c in cs)
                {
                    if (c == null || c is Transform) continue;
                    comps += (comps.Length == 0 ? "" : " | ") + DescribeComponent(c);
                }
            return t.name + Geo(t) + (t.gameObject.activeSelf ? "" : " [INACTIVE]") + " {" + comps + "}";
        }

        private static string Geo(Transform t)
        {
            RectTransform rt = t as RectTransform;
            if (rt == null) return "";
            Vector3 wp = rt.position;
            Rect r = rt.rect;
            return " size=" + rt.sizeDelta.x.ToString("0.##") + "x" + rt.sizeDelta.y.ToString("0.##") +
                   " pos=" + rt.anchoredPosition.x.ToString("0.##") + "," + rt.anchoredPosition.y.ToString("0.##") +
                   " anchor=" + rt.anchorMin.x.ToString("0.##") + "," + rt.anchorMin.y.ToString("0.##") +
                   "->" + rt.anchorMax.x.ToString("0.##") + "," + rt.anchorMax.y.ToString("0.##") +
                   " pivot=" + rt.pivot.x.ToString("0.##") + "," + rt.pivot.y.ToString("0.##") +
                   " world=" + wp.x.ToString("0") + "," + wp.y.ToString("0") +
                   " rect=" + r.width.ToString("0.##") + "x" + r.height.ToString("0.##");
        }

        private void DumpNode(Transform t, List<string> lines, int depth, int maxDepth)
        {
            if (t == null || depth > maxDepth) return;
            lines.Add(new string(' ', depth * 2) + DescribeTransform(t));
            for (int i = 0; i < t.childCount; i++) DumpNode(t.GetChild(i), lines, depth + 1, maxDepth);
        }

        // 通过兼容层 dump 一个组件数组（按钮组 / 文本组），不绑具体类型。
        private void DumpArray(Array items, string tag, List<string> lines)
        {
            if (items == null) { lines.Add(tag + ": (field not resolved)"); return; }
            for (int i = 0; i < items.Length; i++)
            {
                Component c = items.GetValue(i) as Component;
                if (c == null) { lines.Add(tag + "[" + i + "]: (null)"); continue; }

                string label = "";
                Component[] children = c.GetComponentsInChildren<Component>(true);
                if (children != null)
                    foreach (Component child in children)
                    {
                        if (child == null) continue;
                        if (child.GetType().Name.IndexOf("Text", StringComparison.Ordinal) < 0) continue;
                        string txt = GameCompat.ReadText(child);
                        if (!string.IsNullOrEmpty(txt)) { label = txt; break; }
                    }

                lines.Add(tag + "[" + i + "] path=" + GameCompat.NodePath(c.transform) +
                          " active=" + c.gameObject.activeSelf + " label='" + label + "'");
                lines.Add(new string(' ', 4) + "self: " + DescribeTransform(c.transform));
                Transform parent = c.transform.parent;
                if (parent != null) lines.Add(new string(' ', 4) + "parent: " + DescribeTransform(parent));
                for (int k = 0; k < c.transform.childCount && k < 6; k++)
                    lines.Add(new string(' ', 4) + "child[" + k + "]: " + DescribeTransform(c.transform.GetChild(k)));
            }
        }

        // 原生滚动件模板：无缝改造要克隆原生滚动条/滚动容器，不能自己造一个风格不同的。
        private void DumpScrollTemplates(List<string> lines)
        {
            lines.Add("--- all ScrollRect in scene (clone templates) ---");
            try
            {
                ScrollRect[] rects = Resources.FindObjectsOfTypeAll<ScrollRect>();
                if (rects == null || rects.Length == 0) lines.Add("(none found)");
                else
                    foreach (ScrollRect sr in rects)
                    {
                        if (sr == null || !sr.gameObject.scene.IsValid()) continue;
                        lines.Add("* " + GameCompat.NodePath(sr.transform) + " active=" +
                                  sr.gameObject.activeInHierarchy + " " + DescribeComponent(sr));
                        if (sr.viewport != null) lines.Add("    viewport: " + DescribeTransform(sr.viewport));
                        if (sr.content != null)
                        {
                            lines.Add("    content: " + DescribeTransform(sr.content));
                            for (int k = 0; k < sr.content.childCount && k < 3; k++)
                                lines.Add("      content.child[" + k + "]: " + DescribeTransform(sr.content.GetChild(k)));
                        }
                    }

                lines.Add("--- all Scrollbar in scene (clone templates) ---");
                Scrollbar[] bars = Resources.FindObjectsOfTypeAll<Scrollbar>();
                if (bars == null || bars.Length == 0) lines.Add("(none found)");
                else
                    foreach (Scrollbar sb in bars)
                    {
                        if (sb == null || !sb.gameObject.scene.IsValid()) continue;
                        lines.Add("* " + GameCompat.NodePath(sb.transform) + " active=" +
                                  sb.gameObject.activeInHierarchy + " " + DescribeComponent(sb));
                        if (sb.handleRect != null) lines.Add("    handle: " + DescribeTransform(sb.handleRect));
                    }
            }
            catch (Exception e) { lines.Add("(template scan failed: " + e.Message + ")"); }
        }

        private void DumpFonts(Transform root, List<string> lines)
        {
            lines.Add("--- fonts used in this page (clone rows must reuse these) ---");
            try
            {
                Dictionary<string, int> seen = new Dictionary<string, int>();
                Component[] all = root.GetComponentsInChildren<Component>(true);
                if (all != null)
                    foreach (Component c in all)
                    {
                        if (c == null) continue;
                        string type = c.GetType().Name;
                        bool isText = c is UnityEngine.UI.Text || type.IndexOf("Text", StringComparison.Ordinal) >= 0;
                        if (!isText) continue;
                        string font = c is UnityEngine.UI.Text
                            ? (((UnityEngine.UI.Text)c).font == null ? "(none)" : ((UnityEngine.UI.Text)c).font.name)
                            : Refl(c, "font");
                        if (string.IsNullOrEmpty(font)) font = "(none)";
                        seen[font] = (seen.ContainsKey(font) ? seen[font] : 0) + 1;
                    }
                if (seen.Count == 0) lines.Add("(no text components)");
                foreach (KeyValuePair<string, int> kv in seen) lines.Add("* " + kv.Key + " x" + kv.Value);
            }
            catch (Exception e) { lines.Add("(font scan failed: " + e.Message + ")"); }
        }

        private static string Fmt(Color c)
        {
            return "RGBA(" + c.r.ToString("0.###") + "," + c.g.ToString("0.###") + "," + c.b.ToString("0.###") +
                   "," + c.a.ToString("0.###") + ")";
        }

        // 诊断文件落点：<LocalLow>\WCP\wcp_diag\WcpSlotsDiag.txt（云同步范围外）。
        // persistentDataPath 就是被同步的那个 wcp 目录，所以取它的上一级再拼 wcp_diag。
        private static string DiagPath()
        {
            try
            {
                DirectoryInfo parent = Directory.GetParent(Application.persistentDataPath);
                if (parent != null && !string.IsNullOrEmpty(parent.FullName))
                    return Path.Combine(Path.Combine(parent.FullName, "wcp_diag"), "WcpSlotsDiag.txt");
            }
            catch (Exception e)
            {
                Log.LogWarning("CustomSlots: 诊断目录解析失败，退回 persistentDataPath: " + e.Message);
            }
            return Path.Combine(Application.persistentDataPath, "WcpSlotsDiag.txt");
        }

        private static string Clip(string s)
        {
            if (string.IsNullOrEmpty(s)) return "";
            s = s.Replace("\r", " ").Replace("\n", " ");
            return s.Length > 40 ? s.Substring(0, 40) + "..." : s;
        }

        private static string PathOf(Transform rt)
        {
            return rt == null ? "(none)" : GameCompat.NodePath(rt);
        }

        private static string Refl(object o, string prop)
        {
            try
            {
                if (o == null) return null;
                System.Reflection.PropertyInfo pi = o.GetType().GetProperty(prop);
                if (pi == null) return null;
                object v = pi.GetValue(o, null);
                return v == null ? "(null)" : v.ToString();
            }
            catch { return null; }
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
                bool hasActions = !SlotRules.IsNativeMirror(record) && SlotRules.HasPlayableWords(record);
                Color color = captured + 1 == _state.selected
                    ? new Color(0.12f, 0.34f, 0.26f)
                    : (SlotRules.IsManaged(record)
                        ? new Color(0.10f, 0.18f, 0.29f)
                        : new Color(0.10f, 0.11f, 0.15f));
                GameObject rowObject = new GameObject("Row" + (i + 1));
                rowObject.transform.SetParent(_content, false);
                LayoutElement element = rowObject.AddComponent<LayoutElement>();
                element.minHeight = 48f;
                element.preferredHeight = 48f;
                Image rowImage = rowObject.AddComponent<Image>();
                rowImage.color = color;
                Button row = rowObject.AddComponent<Button>();
                row.targetGraphic = rowImage;
                row.colors = new ColorBlock {
                    normalColor = color,
                    highlightedColor = new Color(Mathf.Min(1f, color.r + 0.12f), Mathf.Min(1f, color.g + 0.12f), Mathf.Min(1f, color.b + 0.12f), color.a),
                    pressedColor = color,
                    selectedColor = color,
                    disabledColor = color,
                    colorMultiplier = 1f,
                    fadeDuration = 0.05f
                };
                Text label = CreateText(rowObject.transform, RowLabel(record, i + 1), 16, Vector2.zero,
                    new Vector2(-24f, -12f), TextAnchor.MiddleLeft, Color.white);
                label.rectTransform.anchorMin = new Vector2(0f, 0f);
                label.rectTransform.anchorMax = new Vector2(1f, 1f);
                label.rectTransform.offsetMin = new Vector2(12f, 4f);
                label.rectTransform.offsetMax = new Vector2(hasActions ? -130f : -12f, -4f);
                row.onClick.AddListener(new UnityAction(delegate { Select(captured); }));

                if (!hasActions) continue;
                CreateActionButton(rowObject.transform, "改名", new Vector2(-64f, -6f),
                    new Vector2(56f, 36f), new Color(0.16f, 0.30f, 0.38f),
                    new UnityAction(delegate { BeginRename(captured); }), false);
                CreateActionButton(rowObject.transform, "移除", new Vector2(-8f, -6f),
                    new Vector2(56f, 36f), new Color(0.38f, 0.16f, 0.16f),
                    new UnityAction(delegate { ClearSlot(captured); }), false);
            }
            RenderRenameBar();
            Canvas.ForceUpdateCanvases();
        }

        private string RowLabel(SlotRecord record, int number)
        {
            if (!SlotRules.HasPlayableWords(record))
                return "槽位 " + number + "    （空）";
            string owner = record.managed ? "mod" : "外部词书";
            string name = string.IsNullOrEmpty(record.name) ? record.id : record.name;
            if (SlotRules.IsNativeMirror(record))
            {
                // 原生镜像行：落盘的 SelfBookNameN 可能为空（游戏里"猫条版"是 BookNameMod 的
                // 显示层伪装，不落盘），此时回退到游戏自己的规范名，避免显示成 "native-1"。
                string canonical = NativeCanonical(record.nativeSlot);
                name = string.IsNullOrEmpty(record.name)
                    ? canonical
                    : canonical + "（" + record.name + "）";
            }
            return "槽位 " + number + "    " + name + "    " + record.words.Length + " 词    [" + owner + "]";
        }

        private static string NativeCanonical(int nativeSlot)
        {
            switch (nativeSlot)
            {
                case 1: return "自定义词书一";
                case 2: return "自定义词书二";
                case 3: return "自定义词书三";
                case 4: return "自定义词书四";
                default: return "原生槽位" + nativeSlot;
            }
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

        // 物理槽可用性：空槽 > 本 mod 托管行占用（可重新物化）> 内容已被任何行快照
        //（可从该行恢复，P1-1 逐出规则）。从未见过的原生内容绝不覆盖（fail-closed）。
        private bool CanUseNativeSlot(int nativeSlot, SlotRecord requested)
        {
            string[] words = ReadNativeWords(nativeSlot);
            if (!SlotRules.HasPlayableWords(new SlotRecord { words = words })) return true;
            if (SlotRules.NativeSlotOwnedByManaged(_state, nativeSlot)) return true;
            if (requested != null && SlotRules.SameWords(words, requested.words)) return true;
            return SlotRules.NativeContentTracked(_state, words);
        }

        // ── ES3 存档读写（通过兼容层反射，避免编译期绑定 ES3 类型）──
        private static void Es3Save(string key, object value)
        {
            GameCompat.Es3Save(key, value, null);
        }

        private static void Es3SaveTo(string key, object value, string path)
        {
            GameCompat.Es3Save(key, value, path);
        }

        private static T Es3Load<T>(string key, string path)
        {
            return GameCompat.Es3Load<T>(key, path);
        }

        private void Materialize(SlotRecord record, int nativeSlot)
        {
            string[] words = (string[])record.words.Clone();
            string name = string.IsNullOrEmpty(record.name) ? record.id : record.name;
            string listKey = "SelfBookList" + nativeSlot;
            string nameKey = "SelfBookName" + nativeSlot;
            Es3SaveTo(listKey, words, MyBookPath);
            Es3SaveTo(nameKey, name, MyBookPath);
            SetStatic(listKey, words);
            SetStatic(nameKey, name);

            string canonical = Canonical(nativeSlot);
            List<string> chosen = new List<string>(words);
            SetStatic("tem_ChosenBook", canonical);
            SetStatic("tem_ChosenBook_List", new List<string>(chosen));
            SetStatic("ChosenBook_Para", canonical);
            SetStatic("ChosenBook_List", chosen);
            Es3Save("ChosenBook_Para", canonical);
            Es3Save("ChosenBook_List", chosen);

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

        // ── P1-2 管理：改名 / 移除 / 刷新 / 提示 ──

        private void BeginRename(int index)
        {
            if (_state == null || index < 0 || index >= _state.slots.Length) return;
            if (SlotRules.IsNativeMirror(_state.slots[index]))
            {
                ShowToast("原生词书名称跟随游戏数据，不能在这里改名");
                return;
            }
            _renameIndex = index;
            if (_renameInput != null)
            {
                string current = _state.slots[index].name;
                _renameInput.text = string.IsNullOrEmpty(current) ? "" : current;
                _renameInput.ActivateInputField();
            }
            RenderRenameBar();
        }

        private void SubmitRename()
        {
            if (_renameIndex < 0 || _renameInput == null) return;
            string name = _renameInput.text;
            int index = _renameIndex;
            if (SlotRules.TryRenameSlot(_state, index, name))
            {
                _renameIndex = -1;
                SaveState();
                RebuildRows();
                Log.LogInfo("CustomSlots: 槽位 " + (index + 1) + " 已改名为 “" + name.Trim() + "”");
            }
            else ShowToast("名称不能为空");
        }

        private void CancelRename()
        {
            _renameIndex = -1;
            RenderRenameBar();
        }

        private void RenderRenameBar()
        {
            if (_renameBar == null) return;
            bool active = _renameIndex >= 0;
            _renameBar.SetActive(active);
            if (active && _renameTitle != null)
                _renameTitle.text = "重命名：槽位 " + (_renameIndex + 1);
        }

        private void ClearSlot(int index)
        {
            if (_state == null || index < 0 || index >= _state.slots.Length) return;
            int release;
            if (!SlotRules.TryClearSlot(_state, index, out release))
            {
                ShowToast("原生词书行不能移除（请在游戏原生界面管理）");
                return;
            }
            if (release >= 1)
            {
                try
                {
                    Es3SaveTo("SelfBookList" + release, new string[0], MyBookPath);
                    SetStatic("SelfBookList" + release, new string[0]);
                }
                catch (Exception e) { Log.LogWarning("CustomSlots: 清空原生槽 " + release + " 失败: " + e.Message); }
            }
            SaveState();
            RebuildRows();
            Log.LogInfo("CustomSlots: 槽位 " + (index + 1) + " 已移除" +
                (release >= 1 ? "（释放原生槽 " + release + "）" : ""));
        }

        // 从游戏落盘重新读原生 4 槽，刷新镜像行与页面（不动 mod 行）。
        private void RefreshFromDisk()
        {
            int changed = ImportNativeBooksNow();
            SaveState();
            RebuildRows();
            Log.LogInfo("CustomSlots: 刷新完成，镜像行变化 " + changed + " 行");
            ShowToast(changed > 0 ? "已从游戏数据刷新 " + changed + " 行" : "已是最新（无变化）");
        }

        private void ShowToast(string message)
        {
            if (_toast == null) return;
            _toast.text = message;
            _toast.gameObject.SetActive(true);
            _toastUntil = Time.unscaledTime + 3f;
        }

        private void EnsureInputField(Transform parent)
        {
            _renameBar = new GameObject("RenameBar");
            _renameBar.transform.SetParent(parent, false);
            RectTransform bar = _renameBar.AddComponent<RectTransform>();
            bar.anchorMin = new Vector2(0f, 1f);
            bar.anchorMax = new Vector2(1f, 1f);
            bar.pivot = new Vector2(0f, 1f);
            bar.anchoredPosition = new Vector2(20f, -92f);
            bar.sizeDelta = new Vector2(-40f, 40f);
            Image barImage = _renameBar.AddComponent<Image>();
            barImage.color = new Color(0.05f, 0.09f, 0.14f, 0.98f);
            _renameBar.SetActive(false);

            _renameTitle = CreateText(_renameBar.transform, "重命名", 14, new Vector2(12f, -10f),
                new Vector2(150f, 22f), TextAnchor.MiddleLeft, new Color(0.72f, 0.78f, 0.86f));

            GameObject inputObject = new GameObject("Input");
            inputObject.transform.SetParent(_renameBar.transform, false);
            RectTransform inputRect = inputObject.AddComponent<RectTransform>();
            inputRect.anchorMin = new Vector2(0f, 0f);
            inputRect.anchorMax = new Vector2(1f, 1f);
            inputRect.offsetMin = new Vector2(170f, 5f);
            inputRect.offsetMax = new Vector2(-130f, -5f);
            Image inputImage = inputObject.AddComponent<Image>();
            inputImage.color = new Color(0.02f, 0.04f, 0.07f, 1f);
            _renameInput = inputObject.AddComponent<InputField>();
            _renameInput.targetGraphic = inputImage;
            _renameInput.textComponent = CreateText(inputObject.transform, "", 15, Vector2.zero,
                new Vector2(-16f, -8f), TextAnchor.MiddleLeft, Color.white);
            _renameInput.textComponent.rectTransform.anchorMin = Vector2.zero;
            _renameInput.textComponent.rectTransform.anchorMax = Vector2.one;
            _renameInput.textComponent.rectTransform.offsetMin = new Vector2(8f, 2f);
            _renameInput.textComponent.rectTransform.offsetMax = new Vector2(-8f, -2f);
            _renameInput.lineType = InputField.LineType.SingleLine;

            CreateActionButton(_renameBar.transform, "确定", new Vector2(-62f, -6f),
                new Vector2(52f, 30f), new Color(0.12f, 0.34f, 0.26f),
                new UnityAction(SubmitRename), false);
            CreateActionButton(_renameBar.transform, "取消", new Vector2(-8f, -6f),
                new Vector2(52f, 30f), new Color(0.24f, 0.28f, 0.35f),
                new UnityAction(CancelRename), false);

            _toast = CreateText(parent, "", 14, new Vector2(0f, 8f),
                new Vector2(-40f, 24f), TextAnchor.LowerLeft, new Color(0.95f, 0.82f, 0.45f));
            _toast.rectTransform.anchorMin = new Vector2(0f, 0f);
            _toast.rectTransform.anchorMax = new Vector2(1f, 0f);
            _toast.rectTransform.pivot = new Vector2(0.5f, 0f);
            _toast.rectTransform.anchoredPosition = new Vector2(0f, 8f);
            _toast.gameObject.SetActive(false);
        }

        private static void EnsureEventSystem()
        {
            if (EventSystem.current != null) return;
            GameObject es = new GameObject("WcpCustomSlotsEventSystem");
            es.AddComponent<EventSystem>();
            es.AddComponent<StandaloneInputModule>();
        }

        // anchorTop=true：右上角（面板头部按钮）；false：右下角（行内 / 输入栏按钮）。
        private static void CreateActionButton(Transform parent, string label, Vector2 position,
                                               Vector2 dimensions, Color color, UnityAction action,
                                               bool anchorTop)
        {
            Button button = CreateButton(parent, label, position, dimensions, color);
            RectTransform rect = button.GetComponent<RectTransform>();
            rect.anchorMin = new Vector2(1f, anchorTop ? 1f : 0f);
            rect.anchorMax = rect.anchorMin;
            rect.pivot = rect.anchorMin;
            button.onClick.AddListener(action);
        }

        private SlotState LoadState()
        {
            try
            {
                if (File.Exists(_storePath))
                {
                    string raw = File.ReadAllText(_storePath);
                    Log.LogInfo("CustomSlots: store bytes=" + (raw == null ? 0 : raw.Length));
                    SlotState loaded = SlotRules.Deserialize(raw);
                    if (loaded != null)
                    {
                        SlotRules.Normalize(loaded);
                        Log.LogInfo("CustomSlots: store loaded; rows=" +
                            (loaded.slots == null ? 0 : loaded.slots.Length) +
                            "; selected=" + loaded.selected);
                        return loaded;
                    }
                    Log.LogWarning("CustomSlots: store 解析失败，走新建分支（旧文件不会被静默当作空档）");
                }
                else
                {
                    Log.LogInfo("CustomSlots: store 不存在，走新建分支");
                }
            }
            catch (Exception e) { Log.LogWarning("CustomSlots: 读取槽位存档失败: " + e.Message); }

            SlotState fresh = SlotRules.NewState();
            return fresh;
        }

        // P1-1：把原生 4 槽的当前词书导入/刷新为镜像行。每次加载都跑（旧版只在新建
        // 存档分支跑一次，store 文件一旦存在原生书就永远进不了 20 行）。
        private int ImportNativeBooksNow()
        {
            List<SlotRules.NativeBook> books = new List<SlotRules.NativeBook>();
            for (int i = 1; i <= SlotRules.NativeSlots; i++)
            {
                string[] words = ReadNativeWords(i);
                if (!SlotRules.HasPlayableWords(new SlotRecord { words = words })) continue;
                books.Add(new SlotRules.NativeBook { Slot = i, Name = ReadNativeName(i), Words = words });
            }
            return SlotRules.ImportNativeBooks(_state, books.ToArray());
        }

        private void MergeSeed()
        {
            try
            {
                if (!File.Exists(SeedPath)) return;
                SlotState seed = SlotRules.Deserialize(File.ReadAllText(SeedPath));
                if (seed == null || seed.slots == null)
                {
                    Log.LogWarning("CustomSlots: 安装器 seed 解析失败（格式不支持），本次不合并");
                    return;
                }
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
                string json = SlotRules.Serialize(_state);
                File.WriteAllText(_storePath, json);
                int filled = 0;
                for (int i = 0; i < _state.slots.Length; i++)
                    if (SlotRules.HasPlayableWords(_state.slots[i])) filled++;
                Log.LogInfo("CustomSlots: store saved; bytes=" + json.Length + "; filledRows=" + filled +
                    "; selected=" + _state.selected);
            }
            catch (Exception e) { Log.LogWarning("CustomSlots: 保存槽位存档失败: " + e.Message); }
        }

        private string[] ReadNativeWords(int nativeSlot)
        {
            try
            {
                if (!File.Exists(MyBookPath)) return new string[0];
                string[] words = Es3Load<string[]>("SelfBookList" + nativeSlot, MyBookPath);
                return words ?? new string[0];
            }
            catch { return new string[0]; }
        }

        private string ReadNativeName(int nativeSlot)
        {
            try
            {
                if (!File.Exists(MyBookPath)) return "";
                return Es3Load<string>("SelfBookName" + nativeSlot, MyBookPath);
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

        // 通过兼容层写游戏静态字段（不绑 MyParameters 类型名，游戏改名也走这里）。
        private static void SetStatic(string name, object value)
        {
            GameCompat.SetStaticField(name, value);
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

        // Unity 2022.2+ 起内建字体从 Arial.ttf 更名为 LegacyRuntime.ttf：
        // 旧名字在部分运行时会抛 ArgumentException 或返回 null，导致整个覆盖层文字不可见。
        // 逐级回退，最后退到系统字库，保证中文标签一定能画出来。
        private static Font ResolveFont()
        {
            Font font = null;
            try { font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf"); }
            catch (Exception) { }
            if (font == null)
            {
                try { font = Resources.GetBuiltinResource<Font>("Arial.ttf"); }
                catch (Exception) { }
            }
            if (font == null)
            {
                try { font = Font.CreateDynamicFontFromOSFont("Microsoft YaHei", 16); }
                catch (Exception) { }
            }
            if (font == null)
            {
                Font[] available = Resources.FindObjectsOfTypeAll<Font>();
                if (available != null && available.Length > 0) font = available[0];
            }
            if (font == null) Log.LogWarning("CustomSlots: 取不到可用字体，覆盖层文字将不可见");
            return font;
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
            text.font = ResolveFont();
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
