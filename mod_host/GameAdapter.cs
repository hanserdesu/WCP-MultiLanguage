// WCP Host — 游戏适配层（反射封装）
//
// 为什么全走反射: 游戏更新会改字段名 / 类型。现有插件（JpWordListMod.cs 的 L 段）
// 已经把这条做对了 —— 字段消失时只记一条日志，不抛异常、不崩、不写坏存档。
// 宿主把这条约定提升为通用规则: **任何对游戏内部的访问都必须能"优雅失效"**。
//
// 所有类型/方法都按名字查，查不到返回 null / 空，由调用方按 fail-closed 处理。
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using HarmonyLib;
using UnityEngine;

namespace WcpHost
{
    internal static class GameAdapter
    {
        // 游戏参数类型名单点：作者改类型名（MyParameters → …）时只改这里。
        // 30+ 个静态字段访问都引用此常量；类型缺失时各调用方按 fail-closed 降级。
        internal const string ParametersType = "MyParameters";
        private static readonly Dictionary<string, FieldInfo> _fields =
            new Dictionary<string, FieldInfo>();
        private static readonly Dictionary<string, FieldInfo> _instanceFields =
            new Dictionary<string, FieldInfo>();
        private static MethodInfo _es3LoadString;
        private static MethodInfo _es3LoadDefault;
        private static MethodInfo _es3LoadFile;
        private static MethodInfo _es3Save;
        private static bool _es3Probed;

        internal static object StaticField(string typeName, string fieldName)
        {
            string cacheKey = typeName + "." + fieldName;
            FieldInfo fi;
            if (!_fields.TryGetValue(cacheKey, out fi))
            {
                try
                {
                    Type t = AccessTools.TypeByName(typeName);
                    fi = (t == null) ? null : AccessTools.Field(t, fieldName);
                }
                catch (Exception) { fi = null; }
                _fields[cacheKey] = fi;
                if (fi == null && WcpHostPlugin.Log != null)
                    WcpHostPlugin.Log.LogWarning("WcpHost: 游戏字段不可用 " + cacheKey +
                        "（游戏更新导致？本项功能降级，其余不受影响）");
            }
            if (fi == null) return null;
            try { return fi.GetValue(null); }
            catch (Exception) { return null; }
        }

        internal static bool SetStaticField(string typeName, string fieldName, object value)
        {
            FieldInfo fi = FindField(typeName, fieldName, false);
            if (fi == null || !fi.IsStatic) return false;
            try
            {
                fi.SetValue(null, value);
                return true;
            }
            catch (Exception e)
            {
                Warn("写入游戏静态字段失败 " + typeName + "." + fieldName + ": " + e.Message);
                return false;
            }
        }

        internal static object InstanceField(object instance, string fieldName)
        {
            if (instance == null || string.IsNullOrEmpty(fieldName)) return null;
            FieldInfo fi = FindField(instance.GetType(), fieldName);
            if (fi == null) return null;
            try { return fi.GetValue(instance); }
            catch (Exception) { return null; }
        }

        internal static bool SetInstanceField(object instance, string fieldName, object value)
        {
            if (instance == null || string.IsNullOrEmpty(fieldName)) return false;
            FieldInfo fi = FindField(instance.GetType(), fieldName);
            if (fi == null) return false;
            try
            {
                fi.SetValue(instance, value);
                return true;
            }
            catch (Exception e)
            {
                Warn("写入游戏实例字段失败 " + instance.GetType().Name + "." + fieldName +
                     ": " + e.Message);
                return false;
            }
        }

        internal static IList<string> ToWordList(object raw)
        {
            if (raw == null) return null;
            if (raw is string) return null;                 // 别把 IEnumerable<char> 当词表
            IList<string> typed = raw as IList<string>;
            if (typed != null) return typed;
            IEnumerable seq = raw as IEnumerable;
            if (seq == null) return null;
            List<string> list = new List<string>();
            try
            {
                foreach (object o in seq) list.Add(o == null ? null : o.ToString());
            }
            catch (Exception) { return null; }
            return list;
        }

        // 原生槽位数量：从存档连续探测（作者加槽自动跟随），下限 4。探测一次并缓存。
        private static int _nativeSlotCount;
        internal static int NativeSlotCount()
        {
            if (_nativeSlotCount > 0) return _nativeSlotCount;
            int count = 0;
            for (int i = 1; i <= 64; i++)
            {
                object probe = Es3Load("SelfBookList" + i, typeof(string[]), null,
                                       PersistentBookPath());
                if (probe == null) break;
                count = i;
            }
            _nativeSlotCount = count >= 4 ? count : 4;
            return _nativeSlotCount;
        }

        internal static IList<string> SlotWords(int slot)
        {
            if (slot < 1 || slot > NativeSlotCount()) return null;
            object value = Es3Load("SelfBookList" + slot, typeof(string[]), null,
                                  PersistentBookPath());
            return ToWordList(value);
        }

        internal static int SlotOfBookName(string name)
        {
            if (string.IsNullOrEmpty(name) ||
                !name.StartsWith("自定义词书", StringComparison.Ordinal)) return 0;
            for (int i = 0; i < name.Length; i++)
            {
                char c = name[i];
                if (c == '一' || c == '1') return 1;
                if (c == '二' || c == '2') return 2;
                if (c == '三' || c == '3') return 3;
                if (c == '四' || c == '4') return 4;
            }
            return 0;
        }

        // 落盘书名。ES3 是游戏自带的静态类，这里只找 (string key, T default) 这个重载。
        internal static string DiskBookName()
        {
            MethodInfo m = Es3LoadString();
            if (m == null) return null;
            try { return m.Invoke(null, new object[] { "ChosenBook_Para", null }) as string; }
            catch (Exception) { return null; }
        }

        internal static object Es3Load(string key, Type valueType, object fallback,
                                       string filePath)
        {
            if (string.IsNullOrEmpty(key) || valueType == null) return fallback;
            try
            {
                MethodInfo m = string.IsNullOrEmpty(filePath)
                    ? Es3LoadDefaultMethod() : Es3LoadFileMethod();
                if (m == null) return fallback;
                object[] args = string.IsNullOrEmpty(filePath)
                    ? new object[] { key, fallback }
                    : new object[] { key, filePath };
                return m.MakeGenericMethod(valueType).Invoke(null, args);
            }
            catch (Exception e)
            {
                Exception cause = e.InnerException ?? e;
                WarnOnce("load:" + key + ":" + valueType.FullName,
                    "读取 ES3 键失败 " + key + ": " + cause.Message);
                return fallback;
            }
        }

        internal static bool Es3Save(string key, object value)
        {
            if (string.IsNullOrEmpty(key) || value == null) return false;
            try
            {
                MethodInfo m = Es3SaveMethod();
                if (m == null) return false;
                m.MakeGenericMethod(value.GetType()).Invoke(null, new object[] { key, value });
                return true;
            }
            catch (Exception e)
            {
                Exception cause = e.InnerException ?? e;
                Warn("写入 ES3 键失败 " + key + ": " + cause.Message);
                return false;
            }
        }

        internal static string PersistentBookPath()
        {
            try
            {
                return Path.Combine(Application.persistentDataPath, "MyBook.es3");
            }
            catch (Exception) { }
            return null;
        }

        private static MethodInfo Es3LoadString()
        {
            if (_es3LoadString != null) return _es3LoadString;
            _es3Probed = true;
            try
            {
                Type es3 = AccessTools.TypeByName("ES3");
                if (es3 == null) return null;
                MethodInfo[] ms = es3.GetMethods(BindingFlags.Public | BindingFlags.Static);
                for (int i = 0; i < ms.Length; i++)
                {
                    MethodInfo m = ms[i];
                    if (m.Name != "Load" || !m.IsGenericMethodDefinition) continue;
                    ParameterInfo[] ps = m.GetParameters();
                    if (ps.Length == 2 && ps[0].ParameterType == typeof(string) &&
                        ps[1].ParameterType.IsGenericParameter)
                    {
                        _es3LoadString = m.MakeGenericMethod(typeof(string));
                        break;
                    }
                }
                if (_es3LoadString == null && WcpHostPlugin.Log != null)
                    WcpHostPlugin.Log.LogWarning("WcpHost: 找不到 ES3.Load<string>(string,T) 重载，" +
                        "落盘书名这一路判定降级（宿主将保持未激活）");
            }
            catch (Exception e)
            {
                if (WcpHostPlugin.Log != null) WcpHostPlugin.Log.LogWarning("WcpHost: ES3 探测失败: " + e.Message);
            }
            return _es3LoadString;
        }

        private static MethodInfo Es3LoadDefaultMethod()
        {
            ProbeEs3();
            return _es3LoadDefault;
        }

        private static MethodInfo Es3LoadFileMethod()
        {
            ProbeEs3();
            return _es3LoadFile;
        }

        private static MethodInfo Es3SaveMethod()
        {
            ProbeEs3();
            return _es3Save;
        }

        private static void ProbeEs3()
        {
            if (_es3Probed && (_es3LoadDefault != null || _es3LoadFile != null || _es3Save != null))
                return;
            _es3Probed = true;
            try
            {
                Type es3 = AccessTools.TypeByName("ES3");
                if (es3 == null) return;
                MethodInfo[] ms = es3.GetMethods(BindingFlags.Public | BindingFlags.Static);
                for (int i = 0; i < ms.Length; i++)
                {
                    MethodInfo m = ms[i];
                    if (!m.IsGenericMethodDefinition) continue;
                    ParameterInfo[] ps = m.GetParameters();
                    if (m.Name == "Load" && ps.Length == 2 &&
                        ps[0].ParameterType == typeof(string))
                    {
                        if (ps[1].ParameterType == typeof(string)) _es3LoadFile = m;
                        else if (ps[1].ParameterType.IsGenericParameter && _es3LoadDefault == null)
                            _es3LoadDefault = m;
                    }
                    else if (m.Name == "Save" && ps.Length == 2 &&
                             ps[0].ParameterType == typeof(string) &&
                             ps[1].ParameterType.IsGenericParameter && _es3Save == null)
                    {
                        _es3Save = m;
                    }
                }
            }
            catch (Exception e)
            {
                Warn("ES3 方法探测失败: " + e.Message);
            }
        }

        private static FieldInfo FindField(string typeName, string fieldName, bool instance)
        {
            if (instance) return null;
            string cacheKey = typeName + "." + fieldName;
            FieldInfo fi;
            if (_fields.TryGetValue(cacheKey, out fi)) return fi;
            try
            {
                Type t = AccessTools.TypeByName(typeName);
                fi = t == null ? null : FindField(t, fieldName);
            }
            catch (Exception) { fi = null; }
            _fields[cacheKey] = fi;
            if (fi == null) WarnMissing(cacheKey);
            return fi;
        }

        private static FieldInfo FindField(Type type, string fieldName)
        {
            string cacheKey = type.FullName + "." + fieldName;
            FieldInfo fi;
            if (_instanceFields.TryGetValue(cacheKey, out fi)) return fi;
            try
            {
                fi = AccessTools.Field(type, fieldName);
            }
            catch (Exception) { fi = null; }
            _instanceFields[cacheKey] = fi;
            if (fi == null) WarnMissing(cacheKey);
            return fi;
        }

        private static void WarnMissing(string key)
        {
            if (WcpHostPlugin.Log != null)
                WcpHostPlugin.Log.LogWarning("WcpHost: 游戏字段不可用 " + key +
                    "（游戏更新导致？本项功能降级，其余不受影响）");
        }

        private static void WarnOnce(string key, string message)
        {
            if (WcpHostPlugin.Log != null)
                WcpHostPlugin.Log.LogWarning("WcpHost: " + message);
        }

        private static void Warn(string message)
        {
            if (WcpHostPlugin.Log != null)
                WcpHostPlugin.Log.LogWarning("WcpHost: " + message);
        }
        // ── 选项 B（2026-09-18）：只在「自定义」分类页美化书名 ────────────────
        // 游戏把自定义槽 4 渲染进每个官方分类页 Son 列表尾部（出厂态那行显示
        // 「自定义词书四」）；宿主/插件的美化只该发生在自定义分类页。
        // 页签判据 = WordChooseButtonS10.clickNum（当前 Father 索引，反编译核对
        // case 20 = 自定义）；兜底/校准 = 游戏原生自定义页行带全角括注「（…）」。
        // 判据缺失一律按「不是自定义页」处理 = 显示游戏原生名（fail-safe）。
        // 纯逻辑部分不引用 Unity 类型（配 _local/audit 的源码同文探针离线验证）。
        internal static class LabelPageGate
        {
            internal const int CustomCategoryDefault = 20;

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

            internal static bool HasWrapperMark(string s)
            {
                return !string.IsNullOrEmpty(s) && s.IndexOf('\uff08') >= 0;
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

        // ── 自定义槽的规范名（生成，不写死上限；与 CustomSlotsMod 同规则）──
        private static readonly string[] CnDigits =
        {
            "\u4e00", "\u4e8c", "\u4e09", "\u56db", "\u4e94",
            "\u516d", "\u4e03", "\u516b", "\u4e5d"
        };

        internal static string CnNumber(int n)
        {
            if (n < 1 || n > 99) return null;
            if (n <= 9) return CnDigits[n - 1];
            int tens = n / 10;
            int ones = n % 10;
            string head = tens == 1 ? "\u5341" : CnDigits[tens - 1] + "\u5341";
            return ones == 0 ? head : head + CnDigits[ones - 1];
        }

        internal static string CanonicalBookName(int slot)
        {
            string digits = CnNumber(slot);
            return digits == null ? null : "\u81ea\u5b9a\u4e49\u8bcd\u4e66" + digits;
        }

        // canon[i] = 槽 i+1 的规范名，与 LabelPageGate 的约定一致
        internal static string[] CanonicalNames()
        {
            int count = NativeSlotCount();
            string[] names = new string[count];
            for (int i = 0; i < count; i++) names[i] = CanonicalBookName(i + 1);
            return names;
        }

        // ── 选书页类型（候选名；作者改名时补这里即可，缺失只让本项降级）──
        private static readonly string[] ChooserTypeCandidates =
        {
            "WordChooseButtonS10", "WordChooseButtonS11", "WordChooseButtonS12",
            "WordChooseButtonS13", "WordChooseButtonS9", "WordChooseButton"
        };
        private static bool _chooserProbed;
        private static Type _chooserType;

        internal static Type ChooserType()
        {
            if (_chooserProbed) return _chooserType;
            _chooserProbed = true;
            for (int i = 0; i < ChooserTypeCandidates.Length; i++)
            {
                Type t = null;
                try { t = AccessTools.TypeByName(ChooserTypeCandidates[i]); }
                catch (Exception) { t = null; }
                if (t == null) continue;
                _chooserType = t;
                break;
            }
            if (_chooserType == null)
                Warn("\u627e\u4e0d\u5230\u9009\u4e66\u9875\u7c7b\u578b\uff08\u5019\u9009\uff1a" +
                     string.Join("/", ChooserTypeCandidates) +
                     "\uff09\u2014\u2014 \u300c\u5206\u7c7b\u9875\u663e\u793a\u89c4\u8303\u540d\u300d\u8fd9\u4e00\u9879\u964d\u7ea7");
            return _chooserType;
        }

        // 场景里可见的选书页实例（同一组件可能多份实例；只认激活那份）
        internal static object ChooserInstance()
        {
            Type chooser = ChooserType();
            if (chooser == null) return null;
            try
            {
                UnityEngine.Object[] all = Resources.FindObjectsOfTypeAll(chooser);
                for (int i = 0; i < all.Length; i++)
                {
                    Component c = all[i] as Component;
                    if (c == null || c.gameObject == null ||
                        !c.gameObject.activeInHierarchy) continue;
                    if (InstanceField(c, "BookNameText") == null) continue;
                    return c;
                }
            }
            catch (Exception) { }
            return null;
        }

        // 当前 Father(分类) 索引 = 游戏自己存的 clickNum；读不到返回 -1
        internal static int CurrentCategory(object chooser)
        {
            object raw = InstanceField(chooser, "clickNum");
            if (raw == null) return -1;
            try { return Convert.ToInt32(raw); }
            catch (Exception) { return -1; }
        }

        private static int _customCategory = LabelPageGate.CustomCategoryDefault;

        internal static int CustomCategory { get { return _customCategory; } }

        // 当前是不是「自定义」分类页；判据缺失一律按 false（显示游戏原生名）
        internal static bool IsCustomPage(object chooser, IList<string> texts,
                                          IList<bool> visible, IList<string> canon,
                                          IList<string> cosmetic)
        {
            bool wrapped = LabelPageGate.WrappedCustomRow(texts, visible, canon, cosmetic);
            int cur = CurrentCategory(chooser);
            if (cur < 0) return wrapped;
            if (wrapped && cur != _customCategory)
            {
                _customCategory = cur;
                Warn("\u81ea\u5b9a\u4e49\u5206\u7c7b\u7d22\u5f15 = " + cur +
                     "\uff08\u6765\u81ea\u539f\u751f\u62ec\u6ce8\u884c\uff09");
            }
            return cur == _customCategory;
        }

    }
}
