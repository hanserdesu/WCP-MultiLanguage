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

        internal static IList<string> SlotWords(int slot)
        {
            if (slot < 1 || slot > 4) return null;
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
    }
}
