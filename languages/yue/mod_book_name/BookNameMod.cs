// WCP Book Name — BepInEx 5 插件
// 功能: 书单里把当前使用、且完整词表匹配猫条版签名的自定义词书显示成「日语词库(猫条版)」。
//
// 关键约束 (逆向自 Assembly-CSharp.dll, 2026-09-12):
//   1. 前缀「自定义词书一~四」是硬编码字面量, 只出现在两处显示赋值:
//        AddElementsToScrollView.AddNewElements()  (每日学习书单, 点击按下标)
//        WordChooseButtonS10                         (选书按钮标签)
//      括号里的昵称来自 SaveFile.es3 的 SelfBookName1..4 —— 玩家能改的只有这段。
//   2. WordChooseButtonS10.SonBookChoose(int) 会**读回按钮标签文字**,
//      取「（」之前那一段当作书名 (tem_ChosenBook -> ChosenBook_Para)。
//      所以改显示必须同时兜住这个回读, 否则选书会失效。
//   因此本插件: 平时只把当前正在使用、且身份匹配的自定义词书显示成「日语词库(猫条版)」, 在该方法执行前后
//   临时换回/换回显示, 保证游戏读到的仍是「自定义词书N」。
//
// 设计: 只改当前匹配完整词书签名的 TMP 显示文本与那一个方法的读入时机, 不碰任何数据;
//   日语音频界面改造也只在玩家实际使用该词书时启用。签名不绑定槽位，也不以语言猜测身份。
using System;
using System.Collections.Generic;
using System.Text;
using BepInEx;
using BepInEx.Configuration;
using BepInEx.Logging;
using HarmonyLib;
using TMPro;
using UnityEngine;
using UnityEngine.UI;
using WcpBookProfiles;

namespace WcpBookName
{
    internal static class Names
    {
        internal static readonly string[] Canon =
        {
            "自定义词书一", "自定义词书二", "自定义词书三", "自定义词书四"
        };

        internal const string Cosmetic = "日语词库(猫条版)";
        private const string LegacyCosmetic = "日语词书一";

        internal static int SlotOfCanonicalText(string s)
        {
            if (string.IsNullOrEmpty(s)) return -1;
            for (int i = 0; i < Canon.Length; i++)
                if (s.StartsWith(Canon[i], StringComparison.Ordinal)) return i;
            return -1;
        }

        internal static string ToCanonical(string s, int slot)
        {
            if (string.IsNullOrEmpty(s)) return s;
            if (BookProfiles.IsManagedDisplayName(s) ||
                s.StartsWith(LegacyCosmetic, StringComparison.Ordinal))
            {
                if (slot >= 0 && slot < Canon.Length) return Canon[slot];
            }
            return s;
        }

        // 「自定义词书N…」= 选书按钮标签(游戏会回读), 未打上补丁时不动它。
        internal static bool LooksLikeSlotLabel(string s)
        {
            return SlotOfCanonicalText(s) >= 0;
        }
    }

    // ── 选项 B（2026-09-18）：只在「自定义」分类页美化书名 ─────────────────
    // 背景（已实机核对）：游戏把自定义槽 4 渲染进每个官方分类页 Son 列表尾部，
    // 出厂态那行显示「自定义词书四」（游戏原生行为）；BookNameMod 把它美化成
    // 「德语词库(猫条版)」后，四级页/考研页…都顶着这个名字 → 用户报的违和。
    //
    // 页签判据：WordChooseButtonS10.clickNum 就是当前 Father(分类) 索引 ——
    // 反编译 case 20 = 自定义（OnBookButtonClicked(num) 末尾 clickNum = num;）。
    // 兜底/校准：游戏在自定义页写的行带全角括注「自定义词书N（SelfBookNameN）」，
    // 看到这种原生行就说明当前分类是自定义页 → 顺手把索引记准（游戏改类别顺序
    // 也能自适应）。判据全不可用时一律按「不是自定义页」处理 = 显示游戏原生名：
    // fail-safe，绝不会把规范名写进美化名位置造成跨页错乱。
    internal static class LabelPageGate
    {
        internal const int CustomCategoryDefault = 20;

        // canon[i] = 槽 i+1 的规范名；cosmetic = 本项目各语言包的显示名
        internal static int SlotFromCanon(string s, IList<string> canon)
        {
            if (string.IsNullOrEmpty(s) || canon == null) return 0;
            for (int i = 0; i < canon.Count; i++)
            {
                if (string.IsNullOrEmpty(canon[i])) continue;
                if (s.StartsWith(canon[i], StringComparison.Ordinal)) return i + 1;
            }
            return 0;
        }

        internal static bool IsCustomSlotLabel(string s, IList<string> canon,
                                               IList<string> cosmetic)
        {
            if (string.IsNullOrEmpty(s)) return false;
            if (SlotFromCanon(s, canon) > 0) return true;
            for (int i = 0; cosmetic != null && i < cosmetic.Count; i++)
                if (!string.IsNullOrEmpty(cosmetic[i]) &&
                    s.StartsWith(cosmetic[i], StringComparison.Ordinal)) return true;
            return false;
        }

        internal static string CanonicalAt(IList<string> canon, int slot)
        {
            if (canon == null || slot < 1 || slot > canon.Count) return null;
            return canon[slot - 1];
        }

        // 游戏原生「自定义页」行格式：自定义词书N（SelfBookNameN）
        internal static bool HasWrapperMark(string s)
        {
            return !string.IsNullOrEmpty(s) && s.IndexOf('（') >= 0;
        }

        internal static bool WrappedCustomRow(IList<string> texts, IList<bool> visible,
                                              IList<string> canon, IList<string> cosmetic)
        {
            if (texts == null) return false;
            for (int i = 0; i < texts.Count; i++)
            {
                if (visible != null && i < visible.Count && !visible[i]) continue;
                if (!HasWrapperMark(texts[i])) continue;
                if (IsCustomSlotLabel(texts[i], canon, cosmetic)) return true;
            }
            return false;
        }

        // 该行应当显示什么；null = 不动（与自定义槽无关的文字一律不碰）
        internal static string TargetRowText(string current, int slot, string desired,
                                             bool onCustomPage, IList<string> canon,
                                             IList<string> cosmetic)
        {
            if (slot < 1 || string.IsNullOrEmpty(current)) return null;
            if (!IsCustomSlotLabel(current, canon, cosmetic)) return null;
            string target = onCustomPage ? desired : CanonicalAt(canon, slot);
            if (string.IsNullOrEmpty(target) || target == current) return null;
            return target;
        }
    }

    // Unity 侧：页签判定 + 选书页行枚举
    internal static class LabelGate
    {
        internal static string[] Canon() { return Names.Canon; }

        internal static string[] Cosmetic()
        {
            var list = new List<string>();
            for (int i = 0; i < BookProfiles.All.Length; i++)
                list.Add(BookProfiles.All[i].DisplayName);
            return list.ToArray();
        }

        // 场景里可见的那个选书页实例（同一组件可能有多份实例挂在不同 Canvas 上）
        internal static WordChooseButtonS10 VisibleChooser()
        {
            try
            {
                var all = Resources.FindObjectsOfTypeAll(typeof(WordChooseButtonS10));
                for (int i = 0; i < all.Length; i++)
                {
                    var c = all[i] as WordChooseButtonS10;
                    if (c == null || c.BookNameText == null) continue;
                    if (c.gameObject != null && c.gameObject.activeInHierarchy) return c;
                }
            }
            catch (Exception) { }
            return null;
        }

        internal static bool IsRow(WordChooseButtonS10 inst, TMP_Text row)
        {
            if (inst == null || inst.BookNameText == null || row == null) return false;
            for (int i = 0; i < inst.BookNameText.Length; i++)
                if (inst.BookNameText[i] == row) return true;
            return false;
        }

        // 游戏自己存的当前 Father(分类) 索引；读不到返回 -1
        internal static int CurrentCategory(WordChooseButtonS10 inst)
        {
            if (inst == null) return -1;
            try
            {
                var fi = AccessTools.Field(typeof(WordChooseButtonS10), "clickNum");
                if (fi == null) return -1;
                object raw = fi.GetValue(inst);
                return raw == null ? -1 : Convert.ToInt32(raw);
            }
            catch (Exception) { return -1; }
        }

        private static int _customCategory = LabelPageGate.CustomCategoryDefault;

        internal static int CustomCategory { get { return _customCategory; } }

        // 当前是不是「自定义」分类页。fail-safe：判据缺失 → false（显示原生名）
        internal static bool OnCustomPage(WordChooseButtonS10 inst)
        {
            try
            {
                if (inst == null || inst.BookNameText == null) return false;
                var canon = Canon();
                var cosmetic = Cosmetic();
                var texts = new List<string>();
                var visible = new List<bool>();
                for (int i = 0; i < inst.BookNameText.Length; i++)
                {
                    var t = inst.BookNameText[i];
                    texts.Add(t == null ? null : t.text);
                    visible.Add(t != null && t.gameObject != null &&
                                t.gameObject.activeInHierarchy);
                }
                bool wrapped = LabelPageGate.WrappedCustomRow(texts, visible, canon, cosmetic);
                int cur = CurrentCategory(inst);
                if (cur < 0) return wrapped;
                // 原生括注行 = 此刻就在自定义页 → 校准索引
                if (wrapped && cur != _customCategory)
                {
                    _customCategory = cur;
                    if (BookNamePlugin.Log != null)
                        BookNamePlugin.Log.LogInfo(
                            "BookName: 自定义分类索引 = " + cur + "（来自原生括注行）");
                }
                return cur == _customCategory;
            }
            catch (Exception) { return false; }
        }
    }

    // 让 SonBookChoose 读到的仍是游戏认识的书名
    [HarmonyPatch(typeof(WordChooseButtonS10), "SonBookChoose")]
    internal static class SonBookChoosePatch
    {
        private static void Prefix(WordChooseButtonS10 __instance, int num)
        {
            Apply(__instance, num, true);
        }

        private static void Postfix(WordChooseButtonS10 __instance, int num)
        {
            Apply(__instance, num, false);
        }

        private static void Apply(WordChooseButtonS10 inst, int num,
                                  bool toCanonical)
        {
            try
            {
                if (inst == null || inst.BookNameText == null) return;
                if (num < 0 || num >= inst.BookNameText.Length) return;
                var label = inst.BookNameText[num];
                if (label == null) return;
                var s = label.text;
                if (string.IsNullOrEmpty(s)) return;
                var n = toCanonical
                    ? Names.ToCanonical(s, num)
                    : (LabelGate.OnCustomPage(inst)
                        ? BookNamePlugin.ToCosmeticIfManaged(s)
                        : LabelPageGate.TargetRowText(s, num + 1, null, false,
                              Names.Canon, LabelGate.Cosmetic()));
                if (string.IsNullOrEmpty(n) || n == s) return;
                label.text = n;
            }
            catch (Exception e)
            {
                if (BookNamePlugin.Log != null)
                    BookNamePlugin.Log.LogError("BookName patch: " + e.Message);
            }
        }
    }

    [BepInPlugin("dev.hanserdesu.bookname", "WCP Book Name", "1.3.1")]
    public class BookNamePlugin : BaseUnityPlugin
    {
        internal static ManualLogSource Log;
        private static bool _patched;
        internal static BookNamePlugin Instance;

        // 游戏里这些组件会在 Start / 切换时把标签写回 美/英/UK/US,
        // 打补丁强制显示 JP。
        // 只在日语词书里做, 且写入前先记账, 离开日语词书时由
        // RestoreWordSide() 原样还回去 —— 否则英语词书的发音设置面板
        // 会被一起改成 JP(这就是跨词书冲突的来源)。
        private readonly Dictionary<TMP_Text, string> _labelWritten =
            new Dictionary<TMP_Text, string>();
        private string _lastVoiceLabel;

        internal void ForceJpLabels(Component c)
        {
            if (c == null) return;
            // Harmony 补丁在 Enabled=false 时仍会被游戏调用。若不在这里再次
            // 检查配置，运行中关闭插件后新的界面仍会被写成 JP。
            if (_enabled == null || !_enabled.Value ||
                _jpLabels == null || !_jpLabels.Value) return;
            BookProfile managed = SelectedManagedBook();
            if (managed == null) return;
            string vLabel = VoiceLabelFor(managed);
            var texts = c.GetComponentsInChildren<TMP_Text>(true);
            for (int i = 0; i < texts.Length; i++)
            {
                var s = texts[i].text;
                if (string.IsNullOrEmpty(s)) continue;
                if (!BookNamePlugin.IsAccentLabelPublic(s)) continue;
                if (!HasButtonAncestorPublic(texts[i])) continue;
                if (!_labelBackup.ContainsKey(texts[i]))
                    _labelBackup[texts[i]] = s;
                texts[i].text = vLabel;
                _labelWritten[texts[i]] = vLabel;
            }
        }

        internal static bool IsAccentLabelPublic(string s)
        {
            s = (s ?? string.Empty).Trim();
            return s == "US" || s == "UK" || s == "美" || s == "英";
        }

        internal static bool HasButtonAncestorPublic(TMP_Text t)
        {
            var tr = t.transform;
            for (int d = 0; d < 4 && tr != null; d++)
            {
                if (tr.GetComponent<Button>() != null) return true;
                tr = tr.parent;
            }
            return false;
        }

        // 发音按钮的标签节点可能不是 Button 的直接子级(例如
        // Canvas-.../Button-soundUS-otherPart (1)/Text (TMP) us),
        // 因此再用节点名兜一层。
        internal static bool LooksLikeAccentNode(TMP_Text t)
        {
            if (HasButtonAncestorPublic(t)) return true;
            var p = t.transform.parent;
            string n = ((t.name ?? "") + "|" + (p == null ? "" : p.name))
                .ToLowerInvariant();
            return n.Contains("sound") || n.Contains("voice")
                || n.Contains("uk") || n.Contains("us");
        }

        private const float ScanInterval = 1f;
        private ConfigEntry<bool> _enabled;
        private ConfigEntry<bool> _jpLabels;
        private ConfigEntry<bool> _singleJp;
        private ConfigEntry<bool> _hideSwitch;
        private readonly Dictionary<TMP_Text, string> _labelBackup =
            new Dictionary<TMP_Text, string>();
        private readonly List<GameObject> _hiddenNodes = new List<GameObject>();
        private readonly List<GameObject> _hiddenSwitch = new List<GameObject>();
        private readonly float[] _slotProfileAt = new float[4];
        private readonly BookProfile[] _slotProfiles = new BookProfile[4];
        private bool _lastJpBook;
        private bool _groupLogged;
        private float _nextSwitchScan;

        // 宿主是否已激活受管词书：从 BepInEx 链对象里读 WcpHost 的 Router
        // ActiveProfileId。任何一步失败都返回 false（回退到本插件自扫）。
        private static bool HostTakesOver()
        {
            try
            {
                var plugin = Instance;
                if (plugin == null) return false;
                var hostType = AccessTools.TypeByName("WcpHost.WcpHostPlugin");
                if (hostType == null) return false;
                var inst = AccessTools.PropertyGetter(hostType, "Instance") != null
                    ? hostType.GetProperty("Instance").GetValue(null) : null;
                if (inst == null) return false;
                var runtime = inst.GetType().GetProperty("Runtime") != null
                    ? inst.GetType().GetProperty("Runtime").GetValue(inst) : null;
                if (runtime == null) return false;
                var pid = runtime.GetType().GetProperty("ActiveProfileId");
                return pid != null && pid.GetValue(runtime) != null;
            }
            catch (Exception) { return false; }
        }

        internal static BookProfile SelectedManagedBook()
        {
            try
            {
                var s = MyParameters.ChosenBook_Para;
                if (string.IsNullOrEmpty(s)) return null;
                int slot = Names.SlotOfCanonicalText(s);
                if (slot < 0) return null;
                string disk = ES3.Load<string>("ChosenBook_Para", defaultValue: null);
                if (string.IsNullOrEmpty(disk) || disk != s) return null;
                var list = MyParameters.ChosenBook_List;
                if (list == null || list.Count < 5) return null;
                BookProfile memory = BookProfiles.Match(list);
                if (memory == null) return null;
                var plugin = Instance;
                if (plugin == null) return null;
                BookProfile stored = plugin.SlotProfile(slot);
                return (stored != null && stored.Id == memory.Id) ? memory : null;
            }
            catch (Exception) { return null; }
        }

        internal static string VoiceLabelFor(BookProfile profile)
        {
            if (profile == null) return null;
            if (profile.Language == BookProfiles.Japanese) return "JP";
            if (profile.Language == BookProfiles.French) return "FR";
            return profile.Language.ToUpperInvariant();
        }

        // 只有当前在学「完整词表匹配猫条版日语 Profile」时才改造单词旁发音按钮。
        // 槽位不固定；其它任何自定义书和全部原版书里 UK/US 都保持游戏原样。
        internal static bool JapaneseBookSelected()
        {
            return SelectedManagedBook() != null;
        }

        // 书名单独显示时没有 ChosenBook_List 可用，因此从 MyBook.es3 读这个槽自己的完整词表。
        // 完整签名不关心用户把词书导到了第几格；5 秒缓存避免每帧计算 SHA-256。
        internal static string ToCosmeticIfManaged(string label)
        {
            var plugin = Instance;
            // Harmony 的选书钩子在配置关闭后仍会运行；关闭插件时必须连
            // 这条静态显示路径也停掉，否则点击选书会再次写入装饰名。
            if (plugin == null || !plugin.isActiveAndEnabled ||
                plugin._enabled == null || !plugin._enabled.Value) return label;
            int slot = Names.SlotOfCanonicalText(label);
            if (slot < 0 || !plugin.CurrentSlotIs(slot)) return label;
            BookProfile profile = plugin.SlotProfile(slot);
            if (profile == null) return label;
            return profile.DisplayName;
        }

        private bool CurrentSlotIs(int slot)
        {
            try
            {
                return Names.SlotOfCanonicalText(MyParameters.ChosenBook_Para) == slot;
            }
            catch (Exception) { return false; }
        }

        private BookProfile SlotProfile(int slot)
        {
            if (slot < 0 || slot >= _slotProfiles.Length) return null;
            float now = Time.realtimeSinceStartup;
            if (_slotProfileAt[slot] > -1E8f && now - _slotProfileAt[slot] < 5f)
                return _slotProfiles[slot];
            _slotProfileAt[slot] = now;
            _slotProfiles[slot] = null;
            try
            {
                string path = System.IO.Path.Combine(Application.persistentDataPath, "MyBook.es3");
                string[] words = ES3.Load<string[]>("SelfBookList" + (slot + 1), path);
                if (words == null || words.Length < 5) return null;
                _slotProfiles[slot] = BookProfiles.Match(words);
            }
            catch (Exception e)
            {
                if (Log != null) Log.LogWarning("BookName: 读取槽位 " + (slot + 1) + " 词表失败: " + e.Message);
            }
            return _slotProfiles[slot];
        }
        private float _nextScan;
        private float _diagAt2;
        private int _rewrites;

        void Awake()
        {
            Log = Logger;
            Instance = this;
            for (int i = 0; i < _slotProfileAt.Length; i++) _slotProfileAt[i] = -1E9f;
            _enabled = Config.Bind("General", "Enabled", true,
                "只把完整词表匹配猫条版签名的词书显示成「日语词库(猫条版)」；不绑定固定槽位。");
            _jpLabels = Config.Bind("General", "JpSoundLabels", true,
                "把单词发音按钮的英式/美式标记(UK/US)显示成 JP。");
            _singleJp = Config.Bind("General", "SingleJpBesideWord", true,
                "单词旁原本成对的英/美发音按钮只保留一个, 显示为 JP。");
            _hideSwitch = Config.Bind("General", "HideRedundantSwitchButton", true,
                "日语词书时隐藏例句区右下那个多余的圆形切换按钮。");
            try
            {
                new Harmony("dev.hanserdesu.bookname")
                    .PatchAll(typeof(BookNamePlugin).Assembly);
                _patched = true;
                Log.LogInfo("BookName: Harmony patch OK (SonBookChoose guarded)");
            }
            catch (Exception e)
            {
                _patched = false;
                Log.LogError("BookName: Harmony patch failed, "
                    + "本次只改非选书标签: " + e.Message);
            }
        }

        void Update()
        {
            if (!_enabled.Value)
            {
                // 配置可以在运行中改动。撤销只涉及本插件记账过的 UI，不能让
                // 已关闭的插件把 JP 标签或隐藏节点带到其它词书。
                RestoreWordSide();
                return;
            }
            if (Time.unscaledTime < _nextScan) return;
            _nextScan = Time.unscaledTime + ScanInterval;
            // 诊断: 只要 BepInEx/diag.on 存在, 每 12s 导一次现场
            // (用户删掉该文件即停)。只在抓到界面实例时才写, 覆盖旧内容。
            if (Time.unscaledTime >= _diagAt2)
            {
                _diagAt2 = Time.unscaledTime + 12f;
                var don = System.IO.Path.Combine(Paths.BepInExRootPath, "diag.on");
                if (System.IO.File.Exists(don))
                {
                    Diag.Dump();
                }
            }
            try { Scan(); }
            catch (Exception e) { Log.LogError("BookName scan: " + e.Message); }
        }

        private void Scan()
        {
            BookProfile managedBook = SelectedManagedBook();
            bool isManaged = managedBook != null;
            // 性能收敛 2026-09-16：宿主接管受管词书时，书名（DisplayName）与
            // 口音标签都由 WcpHost 的 Tick 写入，本插件的全场 TMP_Text 扫描
            // 是重复劳动——直接跳过。离开受管书（isManaged=false）走原路径
            // 负责还原。Legacy/YieldToHost=false 强制旧模式时不受影响。
            if (isManaged && HostTakesOver())
                return;
            // 选项 B（2026-09-18）：行按分类页定显示名 —— 自定义分类页才美化；
            // 官方分类页尾部那行（槽 4 原生显示「自定义词书四」）保持游戏原生名。
            // 判据 = 游戏自己的 clickNum，见 LabelGate.OnCustomPage。
            var chooser = LabelGate.VisibleChooser();
            bool onCustomPage = LabelGate.OnCustomPage(chooser);
            string vLabel = isManaged ? VoiceLabelFor(managedBook) : null;
            if (_lastVoiceLabel != vLabel) RestoreWordSide();
            _lastVoiceLabel = vLabel;
            _lastJpBook = isManaged;
            var all = Resources.FindObjectsOfTypeAll(typeof(TMP_Text));
            for (int i = 0; i < all.Length; i++)
            {
                var t = all[i] as TMP_Text;
                if (t == null) continue;
                var s = t.text;
                if (string.IsNullOrEmpty(s)) continue;
                if (s.IndexOf("自定义词书", StringComparison.Ordinal) >= 0)
                {
                    if (!_patched && Names.LooksLikeSlotLabel(s)) continue;
                    if (!onCustomPage && LabelGate.IsRow(chooser, t))
                    {
                        // 官方分类页：这行是自定义槽 → 保持/还原游戏原生名
                        var page = LabelPageGate.TargetRowText(s, SlotOfRowText(t, s),
                            null, false, Names.Canon, LabelGate.Cosmetic());
                        if (page != null && page != s)
                        {
                            t.text = page;
                            Log.LogInfo("BookName(分类页): " + s + " -> " + page);
                        }
                        continue;
                    }
                    var n = ToCosmeticIfManaged(s);
                    if (n == s) continue;
                    t.text = n;
                    _rewrites++;
                    if (_rewrites <= 10)
                        Log.LogInfo("BookName: " + s + " -> " + n);
                    continue;
                }
                // 单词旁的发音按钮: 本游戏词条已全部改用本地日语发音,
                // 英文的 UK/US 标记没有意义 -> 显示成 JP
                if (_jpLabels.Value && isManaged && IsAccentLabel(s)
                    && LooksLikeAccentNode(t))
                {
                    if (!_labelBackup.ContainsKey(t))
                        _labelBackup[t] = s;
                    t.text = vLabel;
                    _labelWritten[t] = vLabel;
                    Log.LogInfo("Label: " + s + " -> " + vLabel);
                }
            }
            // 选项 B：离开自定义分类页后，把已经美化的选书页行还原成游戏原生名
            RestoreRowNamesOffCustomPage(chooser);
            if (isManaged)
            {
                if (_singleJp.Value) EnforceSingleWordJp();
                else RestoreHiddenNodes();
                if (_hideSwitch.Value) HideRedundantSwitchButton();
                else RestoreHiddenSwitch();
                if (!_jpLabels.Value) RestoreLabels();
            }
            else RestoreWordSide();
        }

        // 离开日语词书(切到英语词书)时, 把我们改过的东西还原,
        // 避免影响其它词书里 UK/US 本身的含义。
        // 选项 B（2026-09-18）：当前不在自定义分类页时，把选书页里已经被美化的
        // 行还原成游戏原生名（官方分类页尾部那行原生显示「自定义词书四」）。
        // 只碰选书页的行，且只碰确实是自定义槽的行 —— 其余文字一律不动。
        private void RestoreRowNamesOffCustomPage(WordChooseButtonS10 chooser)
        {
            if (chooser == null || chooser.BookNameText == null) return;
            if (LabelGate.OnCustomPage(chooser)) return;
            for (int i = 0; i < chooser.BookNameText.Length; i++)
            {
                var row = chooser.BookNameText[i];
                if (row == null) continue;
                string s = row.text;
                if (string.IsNullOrEmpty(s)) continue;
                string n = LabelPageGate.TargetRowText(s, SlotOfRowText(row, s), null,
                    false, Names.Canon, LabelGate.Cosmetic());
                if (n == null || n == s) continue;
                row.text = n;
                Log.LogInfo("BookName(分类页): " + s + " -> " + n);
            }
        }

        // 这一行对应哪个槽（1 起）。先看规范名前缀；再看美化名（词表指纹认槽，
        // SlotProfile 有 5s 缓存）；都认不出就按行下标（游戏自定义页 BookNameText[i]
        // = 槽 i+1）。0 = 认不出 —— 调用方不动这一行。
        private int SlotOfRowText(TMP_Text row, string text)
        {
            int slot = Names.SlotOfCanonicalText(text) + 1;
            if (slot > 0) return slot;
            if (!BookProfiles.IsManagedDisplayName(text)) return 0;
            for (int i = 0; i < BookProfiles.All.Length; i++)
            {
                BookProfile p = SlotProfile(i);
                if (p == null || string.IsNullOrEmpty(p.DisplayName)) continue;
                if (text.StartsWith(p.DisplayName, StringComparison.Ordinal)) return i + 1;
            }
            var inst = LabelGate.VisibleChooser();
            if (inst != null && inst.BookNameText != null)
                for (int i = 0; i < inst.BookNameText.Length; i++)
                    if (inst.BookNameText[i] == row && i < Names.Canon.Length) return i + 1;
            return 0;
        }

        private void RestoreWordSide()
        {
            RestoreLabels();
            RestoreHiddenNodes();
            RestoreHiddenSwitch();
        }

        private void RestoreLabels()
        {
            if (_labelBackup.Count > 0)
            {
                var keys = new List<TMP_Text>(_labelBackup.Keys);
                for (int i = 0; i < keys.Count; i++)
                {
                    var t = keys[i];
                    string written;
                    if (t != null && _labelWritten.TryGetValue(t, out written) &&
                        t.text == written) t.text = _labelBackup[t];
                }
                _labelBackup.Clear();
            }
            _labelWritten.Clear();
        }

        private void RestoreHiddenNodes()
        {
            if (_hiddenNodes.Count > 0)
            {
                for (int i = 0; i < _hiddenNodes.Count; i++)
                {
                    var go = _hiddenNodes[i];
                    if (go != null && !go.activeSelf) go.SetActive(true);
                }
                _hiddenNodes.Clear();
            }
        }

        private void RestoreHiddenSwitch()
        {
            if (_hiddenSwitch.Count > 0)
            {
                for (int i = 0; i < _hiddenSwitch.Count; i++)
                {
                    var go = _hiddenSwitch[i];
                    if (go != null && !go.activeSelf) go.SetActive(true);
                }
                _hiddenSwitch.Clear();
            }
        }

        // 例句区右下那个圆形「切换」按钮: 英文词书里用来切换 英/美 发音(或
        // 本地音优先), 日语词书里词条全是本地日语录音, 它既没作用又占位置。
        // 只隐藏「开关型」按钮(监听方法名是 ToggleSound* / SoundLocal* /
        // ToggleLocalIf, 或名字里带 SwitchSentence) 且标签已显示成 JP 的那个;
        // 播放型按钮(底部发音)与发音设置面板一律不动, 切回英语词书即还原。
        private void HideRedundantSwitchButton()
        {
            if (Time.unscaledTime < _nextSwitchScan) return;
            _nextSwitchScan = Time.unscaledTime + 3f;
            var all = Resources.FindObjectsOfTypeAll(typeof(Button));
            for (int i = 0; i < all.Length; i++)
            {
                var b = all[i] as Button;
                if (b == null || !b.gameObject.activeSelf) continue;
                var nm = b.name ?? string.Empty;
                if (nm.IndexOf("ReadSentence",
                        StringComparison.OrdinalIgnoreCase) >= 0) continue;
                var path = PathOf(b.transform);
                if (path.IndexOf("wordSoundBut",
                        StringComparison.OrdinalIgnoreCase) >= 0) continue;
                if (path.IndexOf("mainMenuButtonBut",
                        StringComparison.OrdinalIgnoreCase) >= 0) continue;
                if (!LabelIsManaged(b)) continue;
                if (!IsSwitchLike(b, nm)) continue;
                if (_hiddenSwitch.Contains(b.gameObject))
                {
                    b.gameObject.SetActive(false);
                    continue;
                }
                b.gameObject.SetActive(false);
                _hiddenSwitch.Add(b.gameObject);
                Log.LogInfo("HideSwitch: " + path);
            }
        }

        private static bool LabelIsManaged(Button b)
        {
            var tmps = b.GetComponentsInChildren<TMP_Text>(true);
            for (int i = 0; i < tmps.Length; i++)
            {
                var t = tmps[i];
                if (t == null) continue;
                string txt = (t.text ?? string.Empty).Trim();
                for (int j = 0; j < BookProfiles.All.Length; j++)
                    if (txt == VoiceLabelFor(BookProfiles.All[j])) return true;
            }
            return false;
        }

        private static bool IsSwitchLike(Button b, string nm)
        {
            if (nm.IndexOf("SwitchSentence",
                    StringComparison.OrdinalIgnoreCase) >= 0) return true;
            int n = b.onClick.GetPersistentEventCount();
            for (int i = 0; i < n; i++)
            {
                var m = b.onClick.GetPersistentMethodName(i);
                if (string.IsNullOrEmpty(m)) continue;
                if (m.IndexOf("ToggleSound", StringComparison.Ordinal) >= 0)
                    return true;
                if (m.IndexOf("SoundLocal", StringComparison.Ordinal) >= 0)
                    return true;
                if (m.IndexOf("ToggleLocalIf", StringComparison.Ordinal) >= 0)
                    return true;
            }
            return false;
        }

        internal static string PathOf(Transform t)
        {
            var sb = new StringBuilder();
            int guard = 0;
            while (t != null && guard++ < 10)
            {
                sb.Insert(0, "/" + t.name);
                t = t.parent;
            }
            return sb.ToString();
        }

        // 单词旁是「英/美」成对的两个发音按钮 (Canvas-scrollMeaningSquare/
        // all/Voice-UK|Voice-US)。词条已全部改用本地日语发音, 两个按钮放
        // 同一段音频, 留一个就够了 —— 保留第一个, 隐藏另一个。
        private void EnforceSingleWordJp()
        {
            var all = Resources.FindObjectsOfTypeAll(typeof(TMP_Text));
            Dictionary<Transform, List<TMP_Text>> groups = null;
            var order = new List<Transform>();
            for (int i = 0; i < all.Length; i++)
            {
                var t = all[i] as TMP_Text;
                if (t == null || !IsWordSideAccentNode(t)) continue;
                string txt = t.text.Trim();
                if (!IsAccentLabel(t.text) && txt != "JP" && txt != "FR") continue;
                var key = t.transform.parent == null
                    ? null : t.transform.parent.parent;
                if (key == null) continue;
                if (groups == null)
                    groups = new Dictionary<Transform, List<TMP_Text>>();
                List<TMP_Text> lst;
                if (!groups.TryGetValue(key, out lst))
                {
                    lst = new List<TMP_Text>();
                    groups[key] = lst;
                    order.Add(key);
                }
                lst.Add(t);
            }
            if (groups == null) return;
            if (!_groupLogged)
            {
                _groupLogged = true;
                for (int g = 0; g < order.Count; g++)
                {
                    var lst0 = groups[order[g]];
                    Log.LogInfo("WordAccent group " + g + " key="
                        + (order[g] == null ? "<null>" : order[g].name)
                        + " count=" + lst0.Count);
                    for (int i = 0; i < lst0.Count; i++)
                    {
                        var b0 = FindButtonUp(lst0[i].transform);
                        Log.LogInfo("   node " + lst0[i].name + " btn="
                            + (b0 == null ? "<none>" : b0.name)
                            + " active=" + (b0 != null && b0.gameObject.activeSelf));
                    }
                }
            }
            for (int g = 0; g < order.Count; g++)
            {
                var lst = groups[order[g]];
                if (lst.Count < 2) continue;
                // 按「容器节点」的层级顺序稳定排序, 保证每次都留下同一个。
                // 注意: 标签节点(t-uk/t-us)各自是父节点的独子, 用标签自己的
                // siblingIndex 比会全部相等(0), 排序结果随机 —— 必须比容器。
                lst.Sort(delegate(TMP_Text a, TMP_Text b)
                {
                    var pa = a.transform.parent;
                    var pb = b.transform.parent;
                    int ia = pa == null ? int.MaxValue : pa.GetSiblingIndex();
                    int ib = pb == null ? int.MaxValue : pb.GetSiblingIndex();
                    if (ia != ib) return ia.CompareTo(ib);
                    return string.CompareOrdinal(
                        pa == null ? string.Empty : pa.name,
                        pb == null ? string.Empty : pb.name);
                });
                // 安全网: 组内两个标签若挂在同一个父节点上, 隐藏父节点会一次
                // 关掉两个 —— 这种情况不动它。
                bool sameParent = false;
                for (int k = 1; k < lst.Count; k++)
                {
                    if (lst[k].transform.parent == lst[0].transform.parent)
                    {
                        sameParent = true;
                        break;
                    }
                }
                if (sameParent) continue;
                // 这对图标本身不是 Button(纯显示容器), 直接把多余的那个
                // 容器节点停用即可。保留第一个, 隐藏其余。
                for (int i = 0; i < lst.Count; i++)
                {
                    var node = lst[i].transform.parent;
                    if (node == null) continue;
                    bool keep = i == 0;
                    if (node.gameObject.activeSelf != keep)
                    {
                        node.gameObject.SetActive(keep);
                        Log.LogInfo("WordAccent: " + node.name
                            + (keep ? " kept" : " hidden"));
                        // 只记「我们亲手关掉」的节点, 离开日语词书时才会把它
                        // 还原成显示; 游戏自己关掉的不要碰, 否则英语词书里会
                        // 把本来该隐藏的那个图标又点亮。
                        if (!keep && !_hiddenNodes.Contains(node.gameObject))
                            _hiddenNodes.Add(node.gameObject);
                    }
                }
            }
        }

        private static Button FindButtonUp(Transform t)
        {
            for (int d = 0; d < 4 && t != null; d++)
            {
                var b = t.GetComponent<Button>();
                if (b != null) return b;
                t = t.parent;
            }
            return null;
        }

        // 只认单词释义区(Canvas-scrollMeaningSquare)里那一对:
        // .../all/Voice-UK/t-uk 与 .../all/Voice-US/t-us。
        // 它们本身不是 Button(纯图标容器), 所以隐藏时直接停用父节点。
        private static bool IsWordSideAccentNode(TMP_Text t)
        {
            var p = t.transform.parent;
            if (p == null) return false;
            var pn = p.name.ToLowerInvariant();
            var tn = t.name.ToLowerInvariant();
            bool named = pn.StartsWith("voice", StringComparison.Ordinal)
                && (pn.EndsWith("uk", StringComparison.Ordinal)
                    || pn.EndsWith("us", StringComparison.Ordinal)
                    || tn == "t-uk" || tn == "t-us");
            if (!named) return false;
            var tr = t.transform;
            for (int d = 0; d < 6 && tr != null; d++)
            {
                if (tr.name.IndexOf("scrollMeaningSquare",
                        StringComparison.OrdinalIgnoreCase) >= 0) return true;
                tr = tr.parent;
            }
            return false;
        }

        private static bool IsAccentLabel(string s)
        {
            return IsAccentLabelPublic(s);
        }

        private static bool HasButtonAncestor(TMP_Text t)
        {
            return HasButtonAncestorPublic(t);
        }
    }

    // 游戏自带脚本会把发音按钮写成 美/英(UK/US), 打补丁强制显示 JP
    internal static class AccentLabelPatches
    {
        // 转调实例方法: 实例里才有「当前是否日语词书」和标签记账
        private static void Call(Component c)
        {
            var p = BookNamePlugin.Instance;
            if (p != null) p.ForceJpLabels(c);
        }

        [HarmonyPostfix]
        [HarmonyPatch(typeof(changePreferredSoundS8), "Start")]
        private static void A1(changePreferredSoundS8 __instance)
        { Call(__instance); }

        [HarmonyPostfix]
        [HarmonyPatch(typeof(changePreferredSoundS8), "ToggleSoundUSIf_Para")]
        private static void A2(changePreferredSoundS8 __instance)
        { Call(__instance); }

        [HarmonyPostfix]
        [HarmonyPatch(typeof(changePreferredSoundS9), "Start")]
        private static void A3(changePreferredSoundS9 __instance)
        { Call(__instance); }

        [HarmonyPostfix]
        [HarmonyPatch(typeof(changePreferredSoundS9), "ToggleSoundUSIf_Para")]
        private static void A4(changePreferredSoundS9 __instance)
        { Call(__instance); }

        [HarmonyPostfix]
        [HarmonyPatch(typeof(ChangeLocalVoiceIf), "Start")]
        private static void A5(ChangeLocalVoiceIf __instance)
        { Call(__instance); }

        [HarmonyPostfix]
        [HarmonyPatch(typeof(ChangeLocalVoiceIf), "ToggleLocalIf")]
        private static void A6(ChangeLocalVoiceIf __instance)
        { Call(__instance); }

        [HarmonyPostfix]
        [HarmonyPatch(typeof(SoundLocalManager), "Start")]
        private static void A7(SoundLocalManager __instance)
        { Call(__instance); }

        [HarmonyPostfix]
        [HarmonyPatch(typeof(SoundLocalManager), "Switch_SoundLocalIf")]
        private static void A8(SoundLocalManager __instance)
        { Call(__instance); }
    }
}
