// WCP Custom Slots — 游戏兼容层。
//
// 目的：把所有对游戏内部的依赖（类型名、方法签名、字段名、页签魔数、节点路径）集中到
// 这一层，用反射 + 多候选 + 状态判定来解析。游戏更新后：
//   - 改名/挪页签索引 → 状态判定仍然命中，功能不受影响；
//   - 签名变化 → 明确报出"哪个成员没找到"，并降级到手动热键入口，而不是整个插件加载失败；
//   - 类型消失 → 只影响依赖它的功能块，其余照常。
//
// 设计原则：绝不因为解析失败而抛异常到插件加载路径；所有解析都返回 null/默认值 + 诊断说明。
using System;
using System.Collections.Generic;
using System.Reflection;
using UnityEngine;

namespace WcpCustomSlots
{
    internal static class GameCompat
    {
        // ── 候选名（按优先级）──
        private static readonly string[] ChooserTypeCandidates =
        {
            "WordChooseButtonS10", "WordChooseButtonS11", "WordChooseButtonS9", "WordChooseButton"
        };
        private const string EntryMethodName = "OnBookButtonClicked";
        // 页签索引仅作兜底：主判据是"页面状态看起来是不是自定义页"（见 IsCustomPageShowing）。
        private const int FallbackCustomPageIndex = 20;

        // 字段名（同样做成候选，游戏改名时可扩展）
        private static readonly string[] FatherFieldCandidates = { "BookButtonFather" };
        private static readonly string[] SonFieldCandidates = { "BookButtonSon" };
        private static readonly string[] NameTextFieldCandidates = { "BookNameText" };
        private static readonly string[] LearnedFieldCandidates = { "LearnedNumInBook" };
        private const string CustomBookLabel = "自定义词书";
        // BookNameMod 会把自定义书名行改写成美化名「…词库(猫条版)」，改写后
        // CustomBookLabel 在页面上不存在 —— 判据必须同时认美化形态，否则
        // 在学受管书时面板会被自己的轮询立即藏掉（2026-09-16 实机踩过）。
        private const string CosmeticMarker = "猫条版";

        private static bool _resolved;
        private static Type _chooserType;
        private static MethodInfo _entryMethod;
        private static string _notes = "(未解析)";
        private static int _cachedCustomPageIndex = int.MinValue;

        internal static Type ChooserType { get { EnsureResolved(); return _chooserType; } }
        internal static MethodInfo EntryMethod { get { EnsureResolved(); return _entryMethod; } }
        internal static string Notes { get { EnsureResolved(); return _notes; } }

        // ── 解析 ──

        private static void EnsureResolved()
        {
            if (_resolved) return;
            _resolved = true;
            List<string> notes = new List<string>();

            _chooserType = FindType(ChooserTypeCandidates, notes);
            if (_chooserType == null)
            {
                _notes = "找不到词书页类型（候选：" + string.Join("/", ChooserTypeCandidates) + "）";
                return;
            }
            notes.Add("类型=" + _chooserType.Name);

            _entryMethod = FindEntryMethod(_chooserType);
            notes.Add(_entryMethod != null
                ? "入口=" + _entryMethod.Name + "(" + DescribeParams(_entryMethod) + ")"
                : "入口方法未找到（将只提供手动热键入口）");

            _notes = string.Join("; ", notes.ToArray());
        }

        private static Type FindType(string[] candidates, List<string> notes)
        {
            Assembly[] assemblies;
            try { assemblies = AppDomain.CurrentDomain.GetAssemblies(); }
            catch (Exception) { return null; }

            // 先按候选顺序精确匹配 Name
            foreach (string want in candidates)
            {
                foreach (Assembly asm in assemblies)
                {
                    Type[] types;
                    try { types = asm.GetTypes(); }
                    catch (Exception) { continue; }
                    foreach (Type t in types)
                        if (t != null && t.Name == want && LooksLikeChooser(t)) return t;
                }
            }
            // 再放宽：任何带 OnBookButtonClicked(int) 且有词书按钮数组字段的类型
            foreach (Assembly asm in assemblies)
            {
                Type[] types;
                try { types = asm.GetTypes(); }
                catch (Exception) { continue; }
                foreach (Type t in types)
                    if (t != null && LooksLikeChooser(t) && FindEntryMethod(t) != null) return t;
            }
            return null;
        }

        private static bool LooksLikeChooser(Type t)
        {
            // 用"像不像词书页"的行为特征判定，而不是只信名字。
            return FindField(t, FatherFieldCandidates) != null ||
                   FindField(t, NameTextFieldCandidates) != null;
        }

        private static MethodInfo FindEntryMethod(Type t)
        {
            if (t == null) return null;
            try
            {
                MethodInfo exact = t.GetMethod(EntryMethodName,
                    BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance,
                    null, new Type[] { typeof(int) }, null);
                if (exact != null) return exact;
                // 退一步：不限定参数表
                foreach (MethodInfo m in t.GetMethods(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance))
                    if (m.Name == EntryMethodName) return m;
            }
            catch (Exception) { }
            return null;
        }

        private static FieldInfo FindField(Type t, string[] names)
        {
            if (t == null) return null;
            foreach (string n in names)
            {
                try
                {
                    FieldInfo f = t.GetField(n, BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
                    if (f != null) return f;
                }
                catch (Exception) { }
            }
            return null;
        }

        // ── 字段读取（全部 null-safe）──

        internal static Array GetBooksArray(object chooser, string[] fieldNames)
        {
            if (chooser == null) return null;
            try
            {
                FieldInfo f = FindField(chooser.GetType(), fieldNames);
                if (f == null) return null;
                return f.GetValue(chooser) as Array;
            }
            catch (Exception) { return null; }
        }

        internal static Array GetFatherButtons(object chooser)
        {
            return GetBooksArray(chooser, FatherFieldCandidates);
        }

        internal static Array GetSonButtons(object chooser)
        {
            return GetBooksArray(chooser, SonFieldCandidates);
        }

        internal static Array GetNameTexts(object chooser)
        {
            return GetBooksArray(chooser, NameTextFieldCandidates);
        }

        internal static Array GetLearnedButtons(object chooser)
        {
            return GetBooksArray(chooser, LearnedFieldCandidates);
        }

        internal static int Count(Array a) { return a == null ? 0 : a.Length; }

        // 读 TMP/UGUI 文本：用反射读 text 属性，避免编译期绑定 TMPro。
        internal static string ReadText(object textComponent)
        {
            if (textComponent == null) return null;
            try
            {
                PropertyInfo p = textComponent.GetType().GetProperty("text",
                    BindingFlags.Public | BindingFlags.Instance);
                if (p != null) return p.GetValue(textComponent, null) as string;
            }
            catch (Exception) { }
            return null;
        }

        // ── 关键：用"页面状态"判定当前是不是自定义词书页 ──
        //
        // 不依赖页签索引魔数：任何 num 点击后，如果第一个书名标签变成「自定义词书N…」，
        // 就说明当前停在自定义页。游戏重排页签顺序也不会失效。
        internal static bool IsCustomPageShowing(object chooser)
        {
            Array names = GetNameTexts(chooser);
            if (names != null && names.Length > 0)
            {
                for (int i = 0; i < names.Length; i++)
                {
                    string text = ReadText(names.GetValue(i));
                    if (string.IsNullOrEmpty(text)) continue;
                    if (text.Contains(CustomBookLabel) || text.Contains(CosmeticMarker)) return true;
                }
            }
            // 兜底：最后一次用户点击的页签就是自定义页（书名被改成任何形态都不影响）。
            // 仅记用户点击、不记游戏初始化调用，启动阶段不会误置位。
            return LastUserPageNum == CustomPageIndex;
        }

        // 兜底：页签索引匹配（仅在状态判定不可用时使用）。索引可运行时校准。
        internal static int CustomPageIndex
        {
            get
            {
                if (_cachedCustomPageIndex != int.MinValue) return _cachedCustomPageIndex;
                return FallbackCustomPageIndex;
            }
        }

        // 信号 c 状态：最后一次「用户真实点击」的页签 num（int.MinValue = 尚无）。
        // 只在选书窗可见时有意义；窗一关 PollCustomPage 就清掉，避免旧信号跨页生效。
        private static int _lastUserPageNum = int.MinValue;
        internal static int LastUserPageNum { get { return _lastUserPageNum; } }
        internal static void NotePageClick(int num) { _lastUserPageNum = num; }
        internal static void ClearUserPageNum() { _lastUserPageNum = int.MinValue; }

        // 用标签文字校准自定义页索引（父级页签按钮的文字里找「自定义」）。
        internal static void CalibrateCustomPageIndex(object chooser)
        {
            if (_cachedCustomPageIndex != int.MinValue) return;
            try
            {
                Array fathers = GetFatherButtons(chooser);
                if (fathers == null || fathers.Length == 0) return;
                for (int i = 0; i < fathers.Length; i++)
                {
                    Component c = fathers.GetValue(i) as Component;
                    if (c == null) continue;
                    string label = ReadTextOfChildren(c);
                    if (!string.IsNullOrEmpty(label) && label.Contains("自定义"))
                    {
                        _cachedCustomPageIndex = i;
                        return;
                    }
                }
                _cachedCustomPageIndex = FallbackCustomPageIndex;
            }
            catch (Exception) { _cachedCustomPageIndex = FallbackCustomPageIndex; }
        }

        private static string ReadTextOfChildren(Component c)
        {
            try
            {
                Component[] comps = c.GetComponentsInChildren<Component>(true);
                if (comps == null) return null;
                foreach (Component child in comps)
                {
                    if (child == null) continue;
                    string n = child.GetType().Name;
                    if (n.IndexOf("Text", StringComparison.Ordinal) < 0) continue;
                    string t = ReadText(child);
                    if (!string.IsNullOrEmpty(t)) return t;
                }
            }
            catch (Exception) { }
            return null;
        }

        // ── 实例查找（不依赖编译期泛型）──

        internal static object FindChooserInstance()
        {
            Type t = ChooserType;
            if (t == null) return null;
            try
            {
                UnityEngine.Object[] all = Resources.FindObjectsOfTypeAll(t);
                if (all == null) return null;
                foreach (UnityEngine.Object o in all)
                {
                    if (o == null) continue;
                    // 只取场景内真实对象，避免选到资源模板
                    Component c = o as Component;
                    if (c != null && c.gameObject.scene.IsValid()) return o;
                }
                return all.Length > 0 ? all[0] : null;
            }
            catch (Exception) { return null; }
        }

        internal static object[] FindChooserInstances()
        {
            Type t = ChooserType;
            if (t == null) return new object[0];
            try
            {
                UnityEngine.Object[] all = Resources.FindObjectsOfTypeAll(t);
                if (all == null) return new object[0];
                List<object> kept = new List<object>();
                foreach (UnityEngine.Object o in all)
                {
                    if (o == null) continue;
                    Component c = o as Component;
                    if (c != null && c.gameObject.scene.IsValid()) kept.Add(o);
                }
                return kept.ToArray();
            }
            catch (Exception) { return new object[0]; }
        }

        internal static string Describe(object chooser)
        {
            if (chooser == null) return "null";
            Component c = chooser as Component;
            return c != null ? c.GetType().Name + "@" + NodePath(c.transform) : chooser.GetType().Name;
        }

        internal static string NodePath(Transform t)
        {
            if (t == null) return "?";
            string path = t.name;
            Transform p = t.parent;
            int guard = 0;
            while (p != null && guard++ < 24) { path = p.name + "/" + path; p = p.parent; }
            return path;
        }

        private static string DescribeParams(MethodInfo m)
        {
            ParameterInfo[] ps = m.GetParameters();
            string[] parts = new string[ps.Length];
            for (int i = 0; i < ps.Length; i++) parts[i] = ps[i].ParameterType.Name;
            return string.Join(",", parts);
        }

        // ── 原生节点解析（方案 A 克隆原生行用；多候选 + 结构校验）──
        //
        // 找不到就返回 null，由调用方降级为独立覆盖层，绝不猜测硬编码索引。
        internal static Transform FindDescendant(Transform root, string nameContains, int maxNodes)
        {
            if (root == null || string.IsNullOrEmpty(nameContains)) return null;
            try
            {
                List<Transform> queue = new List<Transform>();
                queue.Add(root);
                int visited = 0;
                int head = 0;
                while (head < queue.Count && visited < maxNodes)
                {
                    Transform cur = queue[head++];
                    visited++;
                    if (cur == null) continue;
                    if (cur != root &&
                        cur.name.IndexOf(nameContains, StringComparison.OrdinalIgnoreCase) >= 0)
                        return cur;
                    for (int i = 0; i < cur.childCount; i++) queue.Add(cur.GetChild(i));
                }
            }
            catch (Exception) { }
            return null;
        }

        // 原生列表容器：持有若干"行"的父节点。以给定行节点反推。
        internal static Transform FindRowContainer(Transform row)
        {
            return row != null ? row.parent : null;
        }

        // 场景里chooser 实例可能不止一份（不同 Canvas 各挂一份）：返回「当前可见」
        // 的那个；全不可见返回 null。判可见性用 IsChooserVisible（activeInHierarchy +
        // 祖先 CanvasGroup/Canvas 检查），避免拿隐藏实例判页面状态。
        internal static object FindVisibleChooserInstance()
        {
            object[] all = FindChooserInstances();
            if (all == null || all.Length == 0) return null;
            for (int i = 0; i < all.Length; i++)
            {
                if (all[i] == null) continue;
                try { if (IsChooserVisible(all[i])) return all[i]; }
                catch (Exception) { }
            }
            return null;
        }

        // ── 可见性判定（用于"启动不弹、进页才弹"）──
        //
        // 程序化调用 vs 用户点击无法从调用栈可靠区分（实测两次调用栈都含 Initialize）。
        // 改用页面是否真的可见：游戏启动初始化标签时词书页尚未显示；用户进入该页时才可见。
        internal static bool IsChooserVisible(object chooser)
        {
            Component c = chooser as Component;
            if (c == null) return false;
            try
            {
                if (!c.gameObject.activeInHierarchy) return false;
                // 任一祖先 CanvasGroup 关闭/透明 → 视为不可见
                Transform t = c.transform;
                int guard = 0;
                while (t != null && guard++ < 24)
                {
                    CanvasGroup cg = t.GetComponent<CanvasGroup>();
                    if (cg != null && (cg.alpha <= 0.01f || !cg.interactable)) return false;
                    Canvas canvas = t.GetComponent<Canvas>();
                    if (canvas != null && !canvas.isActiveAndEnabled) return false;
                    t = t.parent;
                }
                return true;
            }
            catch (Exception) { return false; }
        }

        // 结构校验：容器里是否真的有 >= minRows 个子节点（避免认错节点）。
        internal static bool LooksLikeRowContainer(Transform container, int minRows)
        {
            if (container == null) return false;
            try { return container.childCount >= minRows; }
            catch (Exception) { return false; }
        }

        // ── 游戏静态字段写入（候选类型名 + 候选字段名，均反射）──
        private static readonly string[] ParameterTypeCandidates =
        {
            "MyParameters", "GameParameters", "MyParam"
        };
        private static string _staticNotes = "(未解析)";
        internal static string StaticNotes { get { return _staticNotes; } }

        internal static void SetStaticField(string fieldName, object value)
        {
            if (string.IsNullOrEmpty(fieldName)) return;
            try
            {
                foreach (string typeName in ParameterTypeCandidates)
                {
                    Type t = FindTypeByName(typeName);
                    if (t == null) continue;
                    FieldInfo f = t.GetField(fieldName,
                        BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static);
                    if (f == null) continue;
                    f.SetValue(null, value);
                    _staticNotes = typeName + "." + fieldName + " ok";
                    return;
                }
                _staticNotes = "未找到类型/字段: " + fieldName;
            }
            catch (Exception e) { _staticNotes = "写入失败 " + fieldName + ": " + e.Message; }
        }

        internal static object GetStaticField(string fieldName, Type knownType)
        {
            if (string.IsNullOrEmpty(fieldName)) return null;
            try
            {
                if (knownType != null)
                {
                    FieldInfo f = knownType.GetField(fieldName,
                        BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static);
                    if (f != null) return f.GetValue(null);
                }
                foreach (string typeName in ParameterTypeCandidates)
                {
                    Type t = FindTypeByName(typeName);
                    if (t == null) continue;
                    FieldInfo f = t.GetField(fieldName,
                        BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static);
                    if (f != null) return f.GetValue(null);
                }
            }
            catch (Exception) { }
            return null;
        }

        internal static Type FindTypeByName(string name)
        {
            try
            {
                foreach (Assembly asm in AppDomain.CurrentDomain.GetAssemblies())
                {
                    Type[] types;
                    try { types = asm.GetTypes(); }
                    catch (Exception) { continue; }
                    foreach (Type t in types)
                        if (t != null && t.Name == name) return t;
                }
            }
            catch (Exception) { }
            return null;
        }

        // ── ES3 存档读写（Easy Save 3）：反射调用，避免编译期绑定 ──
        private static Type _es3Type;
        private static bool _es3Resolved;
        private static string _es3Notes = "(未解析)";
        internal static string Es3Notes { get { EnsureEs3(); return _es3Notes; } }

        private static void EnsureEs3()
        {
            if (_es3Resolved) return;
            _es3Resolved = true;
            _es3Type = FindTypeByName("ES3");
            _es3Notes = _es3Type == null ? "找不到 ES3 类型（存档读写将不可用）" : "ES3 已解析";
        }

        // path 为 null 时走默认存档（等价于不带 path 的重载）。
        internal static void Es3Save(string key, object value, string path)
        {
            EnsureEs3();
            if (_es3Type == null || string.IsNullOrEmpty(key)) return;
            try
            {
                System.Reflection.MethodInfo best = null;
                foreach (System.Reflection.MethodInfo m in _es3Type.GetMethods(
                             BindingFlags.Public | BindingFlags.Static))
                {
                    if (m.Name != "Save") continue;
                    ParameterInfo[] ps = m.GetParameters();
                    if (ps.Length < 2) continue;
                    if (!ps[0].ParameterType.IsAssignableFrom(typeof(string))) continue;
                    string second = ps[1].ParameterType.Name;
                    // 想要一个能接住 string / string[] / List<string> 的重载
                    if (second == "Object" || second == "T") { best = m; if (ps.Length == 2) break; }
                }
                if (best == null) return;

                object[] args;
                ParameterInfo[] bp = best.GetParameters();
                if (bp.Length == 2)
                    args = new object[] { key, value };
                else
                    args = new object[] { key, value, path };

                // 泛型方法需要显式闭合到值的类型
                if (best.IsGenericMethodDefinition)
                {
                    Type argType = value == null ? typeof(object) : value.GetType();
                    System.Reflection.MethodInfo closed = best.MakeGenericMethod(argType);
                    // 形参个数可能因重载不同而不同，按闭合后的签名裁剪
                    ParameterInfo[] cp = closed.GetParameters();
                    object[] final = cp.Length == 2 ? new object[] { key, value } : new object[] { key, value, path };
                    closed.Invoke(null, final);
                }
                else
                {
                    best.Invoke(null, args);
                }
            }
            catch (Exception e) { _es3Notes = "Save 失败 " + key + ": " + e.Message; }
        }

        internal static T Es3Load<T>(string key, string path)
        {
            EnsureEs3();
            if (_es3Type == null || string.IsNullOrEmpty(key)) return default(T);
            try
            {
                foreach (System.Reflection.MethodInfo m in _es3Type.GetMethods(
                             BindingFlags.Public | BindingFlags.Static))
                {
                    if (m.Name != "Load" || !m.IsGenericMethodDefinition) continue;
                    ParameterInfo[] ps = m.GetParameters();
                    if (ps.Length != 1 && ps.Length != 2) continue;
                    if (!ps[0].ParameterType.IsAssignableFrom(typeof(string))) continue;

                    System.Reflection.MethodInfo closed = m.MakeGenericMethod(typeof(T));
                    object result = ps.Length == 1
                        ? closed.Invoke(null, new object[] { key })
                        : closed.Invoke(null, new object[] { key, path });
                    if (result is T) return (T)result;
                }
            }
            catch (Exception e) { _es3Notes = "Load 失败 " + key + ": " + e.Message; }
            return default(T);
        }
    }
}
