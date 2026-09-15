// 一次性诊断 (读 BepInEx/diag.flag): 把「读例句按钮挂载了什么」和
// 「UK/US 标签由谁写」导出到 BepInEx/diag.txt。定位完成后可删除本文件。
using System;
using System.Reflection;
using System.Text;
using BepInEx;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

namespace WcpBookName
{
    internal static class Diag
    {
        private static readonly string[] Accents = { "UK", "US", "美", "英" };
        private static string _path;
        internal static bool Enabled;

        // 只有在真正抓到界面实例时才写文件, 且每次覆盖
        internal static int LastCount = -1;

        internal static void Dump()
        {
            try
            {
                _path = System.IO.Path.Combine(Paths.BepInExRootPath, "diag.txt");
                System.IO.File.Delete(_path);
                Line("=== dump " + DateTime.Now.ToString("HH:mm:ss") + " ===");
                DumpBookState();
                DumpAccentLabels();
                DumpJpButtons();
                DumpToggleButtons();
                DumpWordSideIcons();
                int n = DumpReadButtons();
                DumpSentenceSources();
                Line("=== end ===\n");
                LastCount = n;
            }
            catch (Exception e)
            {
                try { Line("dump error: " + e); } catch (Exception) { }
            }
        }

        private static void Line(string s)
        {
            System.IO.File.AppendAllText(_path, s + "\n");
        }

        private static string PathOf(Transform t)
        {
            var sb = new StringBuilder();
            int guard = 0;
            while (t != null && guard++ < 12)
            {
                sb.Insert(0, "/" + t.name);
                t = t.parent;
            }
            return sb.ToString();
        }

        private static bool IsAccent(string s)
        {
            if (s == null) return false;
            s = s.Trim();
            for (int i = 0; i < Accents.Length; i++)
                if (s == Accents[i]) return true;
            return false;
        }

        // 当前选中的词书 + 是否按「日语词书」处理 —— 判断跨词书冲突的关键
        private static void DumpBookState()
        {
            Line("--- book state ---");
            string cb = null;
            try { cb = MyParameters.ChosenBook_Para; } catch (Exception) { }
            Line("ChosenBook_Para='" + cb + "' jpBook="
                + BookNamePlugin.JapaneseBookSelected());
        }
        private static void DumpAccentLabels()
        {
            Line("--- accent labels ---");
            var tmps = Resources.FindObjectsOfTypeAll(typeof(TMP_Text));
            for (int i = 0; i < tmps.Length; i++)
            {
                var t = tmps[i] as TMP_Text;
                if (t == null) continue;
                var tx = (t.text ?? "").Trim();
                if (!IsAccent(tx) && tx != "JP") continue;
                Line(string.Format("TMP '{0}' active={1} btnUp={2} btnDown={3} path={4}",
                    t.text, t.gameObject.activeInHierarchy,
                    FindBtnUp(t.transform, 6), FindBtnDown(t.transform, 3),
                    PathOf(t.transform)));
            }
            var txts = Resources.FindObjectsOfTypeAll(typeof(Text));
            for (int i = 0; i < txts.Length; i++)
            {
                var t = txts[i] as Text;
                if (t == null) continue;
                var tx2 = (t.text ?? "").Trim();
                if (!IsAccent(tx2) && tx2 != "JP") continue;
                Line(string.Format("TXT '{0}' active={1} btnUp={2} btnDown={3} path={4}",
                    t.text, t.gameObject.activeInHierarchy,
                    FindBtnUp(t.transform, 6), FindBtnDown(t.transform, 3),
                    PathOf(t.transform)));
            }
        }

        // 从该节点向上/向下找 Button, 报告命名路径, 定位真正的按钮根
        private static string FindBtnUp(Transform t, int max)
        {
            int d = 0;
            while (t != null && d <= max)
            {
                if (t.GetComponent<Button>() != null)
                    return "self+" + d + ":" + t.name;
                t = t.parent;
                d++;
            }
            return "<none>";
        }

        private static string FindBtnDown(Transform t, int max)
        {
            if (t == null) return "<none>";
            var b = t.GetComponentInChildren<Button>(true);
            if (b == null) return "<none>";
            return b.name + "|" + PathOf(b.transform);
        }

        // 所有含 "JP" 标签的按钮: 完整路径 + 组件 + onClick 目标,
        // 用来精确定位「例句区右下那个圆形切换按钮」。
        private static void DumpJpButtons()
        {
            Line("--- jp buttons ---");
            var btns = Resources.FindObjectsOfTypeAll(typeof(Button));
            for (int i = 0; i < btns.Length; i++)
            {
                var b = btns[i] as Button;
                if (b == null) continue;
                var tmps = b.GetComponentsInChildren<TMP_Text>(true);
                bool hasJp = false;
                for (int j = 0; j < tmps.Length; j++)
                {
                    var s = tmps[j] == null ? null : tmps[j].text;
                    if (s != null && s.Trim() == "JP") { hasJp = true; break; }
                }
                if (!hasJp) continue;
                var comps = b.GetComponents<Component>();
                var cs = new StringBuilder();
                for (int c = 0; c < comps.Length; c++)
                {
                    if (comps[c] == null) continue;
                    cs.Append(comps[c].GetType().Name).Append(",");
                }
                int n = b.onClick.GetPersistentEventCount();
                var ev = new StringBuilder();
                for (int e = 0; e < n; e++)
                {
                    ev.Append(" {").Append(b.onClick.GetPersistentTarget(e))
                      .Append(".").Append(b.onClick.GetPersistentMethodName(e))
                      .Append("}");
                }
                Line(string.Format("BTN '{0}' active={1} inHier={2}{3} comps={4} path={5}",
                    b.name, b.gameObject.activeSelf,
                    b.gameObject.activeInHierarchy, ev.ToString(), cs.ToString(),
                    PathOf(b.transform)));
            }
        }

        // 单词旁那对「英/美」图标: 打印每个标签节点的容器、同级序号与激活
        // 状态, 用来确认「两个 JP 同时显示」到底是哪两个节点。
        private static void DumpWordSideIcons()
        {
            Line("--- word side icons (单词旁) ---");
            var tmps = Resources.FindObjectsOfTypeAll(typeof(TMP_Text));
            for (int i = 0; i < tmps.Length; i++)
            {
                var t = tmps[i] as TMP_Text;
                if (t == null) continue;
                var tx = (t.text ?? "").Trim();
                if (!IsAccent(tx) && tx != "JP") continue;
                var tr = t.transform;
                bool near = false;
                for (int d = 0; d < 6 && tr != null; d++)
                {
                    if (tr.name.IndexOf("scrollMeaningSquare",
                            StringComparison.OrdinalIgnoreCase) >= 0)
                    { near = true; break; }
                    tr = tr.parent;
                }
                if (!near) continue;
                var par = t.transform.parent;
                var gpar = par == null ? null : par.parent;
                Line(string.Format(
                    "ICON '{0}' text='{1}' selfActive={2} inHier={3} parent='{4}' parentActive={5} parentSibling={6} grandparent='{7}' grandSibling={8}",
                    t.name, t.text, t.gameObject.activeSelf,
                    t.gameObject.activeInHierarchy,
                    par == null ? "<null>" : par.name,
                    par != null && par.gameObject.activeSelf,
                    par == null ? -1 : par.GetSiblingIndex(),
                    gpar == null ? "<null>" : gpar.name,
                    gpar == null ? -1 : gpar.GetSiblingIndex()));
            }
        }

        private static void DumpToggleButtons()
        {
            Line("--- toggle buttons (切发音口音/本地音 的开关) ---");
            var bs = Resources.FindObjectsOfTypeAll(typeof(Button));
            for (int i = 0; i < bs.Length; i++)
            {
                var b = bs[i] as Button;
                if (b == null) continue;
                int cnt = b.onClick.GetPersistentEventCount();
                bool hit = false;
                var ev = new StringBuilder();
                for (int e = 0; e < cnt; e++)
                {
                    var tgt = b.onClick.GetPersistentTarget(e);
                    var mth = b.onClick.GetPersistentMethodName(e);
                    ev.Append(" {").Append(tgt).Append(".").Append(mth).Append("}");
                    if (mth != null && (mth.IndexOf("Toggle", StringComparison.Ordinal) >= 0
                        || mth.IndexOf("Switch", StringComparison.Ordinal) >= 0))
                        hit = true;
                }
                if (b.name != null && b.name.IndexOf("Switch", StringComparison.OrdinalIgnoreCase) >= 0)
                    hit = true;
                if (!hit) continue;
                var lbl = b.GetComponentInChildren<TMP_Text>(true);
                Line(string.Format("BTN '{0}' active={1} label='{2}'{3} path={4}",
                    b.name, b.gameObject.activeInHierarchy,
                    lbl == null ? "<null>" : lbl.text, ev.ToString(),
                    PathOf(b.transform)));
            }
        }

        private static int DumpReadButtons()
        {
            Line("--- read buttons ---");
            var t = Type.GetType("ShowReadButtons, Assembly-CSharp");
            if (t == null) { Line("ShowReadButtons NOT FOUND"); return 0; }
            var f = t.GetField("ReadButtons",
                BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
            var all = Resources.FindObjectsOfTypeAll(t);
            Line("ShowReadButtons instances: " + all.Length);
            int found = 0;
            for (int k = 0; k < all.Length; k++)
            {
                var comp = all[k] as Component;
                if (comp == null) continue;
                found++;
                Line(" instance " + k + " path=" + PathOf(comp.transform)
                     + " active=" + comp.gameObject.activeInHierarchy);
                var arr = f == null ? null : f.GetValue(comp) as Button[];
                if (arr == null) { Line("  ReadButtons null"); continue; }
                for (int i = 0; i < arr.Length; i++)
                {
                    var b = arr[i];
                    if (b == null) { Line("  [" + i + "] null"); continue; }
                    var lbl = b.GetComponentInChildren<TMP_Text>(true);
                    var comps = b.GetComponents<Component>();
                    var cs = new StringBuilder();
                    for (int c = 0; c < comps.Length; c++)
                    {
                        if (comps[c] == null) continue;
                        cs.Append(comps[c].GetType().Name).Append(",");
                    }
                    int n = b.onClick.GetPersistentEventCount();
                    var ev = new StringBuilder();
                    for (int e = 0; e < n; e++)
                    {
                        ev.Append(" {").Append(b.onClick.GetPersistentTarget(e))
                          .Append(".").Append(b.onClick.GetPersistentMethodName(e))
                          .Append("}");
                    }
                    Line(string.Format(
                        "  [{0}] '{1}' active={2} label='{3}' persistent={4}{5} comps={6}",
                        i, b.name, b.gameObject.activeInHierarchy,
                        lbl == null ? "<null>" : lbl.text, n, ev.ToString(), cs.ToString()));
                }
            }
            return found;
        }

        private static void DumpSentenceSources()
        {
            Line("--- sentence sources ---");
            var mp = Type.GetType("MyParameters, Assembly-CSharp");
            if (mp != null)
            {
                var fw = mp.GetField("checkWordInDictionary",
                    BindingFlags.Public | BindingFlags.Static);
                if (fw != null) Line("checkWordInDictionary=" + fw.GetValue(null));
                var fl = mp.GetField("exaple_sentences",
                    BindingFlags.Public | BindingFlags.Static);
                var list = fl == null ? null : fl.GetValue(null) as System.Collections.IList;
                if (list != null)
                {
                    Line("exaple_sentences count=" + list.Count);
                    for (int i = 0; i < list.Count; i++)
                        Line("  [" + i + "] " + list[i]);
                }
            }
            DumpManager("DatabaseManagerS8");
            DumpManager("DatabaseManagerS17");
        }

        private static void DumpManager(string name)
        {
            var t = Type.GetType(name + ", Assembly-CSharp");
            if (t == null) { Line(name + " NOT FOUND"); return; }
            var f = t.GetField("exmplesentences",
                BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
            var all = Resources.FindObjectsOfTypeAll(t);
            Line(name + " instances: " + all.Length);
            for (int k = 0; k < all.Length; k++)
            {
                var comp = all[k] as Component;
                if (comp == null) continue;
                Line("  instance " + k + " path=" + PathOf(comp.transform)
                     + " active=" + comp.gameObject.activeInHierarchy);
                var arr = f == null ? null : f.GetValue(comp) as TMP_Text[];
                if (arr == null) { Line("    exmplesentences null"); continue; }
                for (int i = 0; i < arr.Length; i++)
                {
                    if (arr[i] == null) { Line("    [" + i + "] null"); continue; }
                    var s = arr[i].text;
                    if (s != null && s.Length > 60) s = s.Substring(0, 60);
                    Line("    [" + i + "] active=" + arr[i].gameObject.activeInHierarchy
                         + " '" + s + "'");
                }
            }
        }
    }
}
