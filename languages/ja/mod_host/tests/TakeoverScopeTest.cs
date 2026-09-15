// Compile the production scope against an in-memory game/storage boundary.
using System;
using System.Collections.Generic;
using WcpHost;

namespace WcpHost
{
    internal class BookProfile { internal string Id; internal string Es3Prefix; }
    internal class LanguageManifest { internal BookProfile Profile; }
    internal class BookRegistry { internal List<LanguageManifest> Manifests = new List<LanguageManifest>(); }
    internal class WcpHostPlugin { internal static WcpHostPlugin Instance; internal BookRegistry Registry; }
    internal static class GameAdapter
    {
        internal static Dictionary<string, object> Fields = new Dictionary<string, object>();
        internal static Dictionary<string, object> Saved = new Dictionary<string, object>();
        internal static string FailKey;
        internal static bool FailSet;
        internal static int Writes;
        internal static object StaticField(string type, string key) { object v; return Fields.TryGetValue(key, out v) ? v : null; }
        internal static bool SetStaticField(string type, string key, object value)
        { if (FailSet) return false; Fields[key] = value; return true; }
        internal static IList<string> ToWordList(object value) { return value as IList<string>; }
        internal static object Es3Load(string key, Type type, object fallback, string file)
        { object v; return Saved.TryGetValue(key, out v) ? v : fallback; }
        internal static bool Es3Save(string key, object value)
        { Writes++; if (key == FailKey) return false; Saved[key] = value; return true; }
    }
}

internal static class TakeoverScopeTest
{
    private const string Field = "S9extraStudy_Para";
    private static int failures;
    private static void Check(bool value, string label)
    { Console.WriteLine((value ? "PASS " : "FAIL ") + label); if (!value) failures++; }

    // ── 词池隔离用的桩: 六词词书 + 可控的学习进度 ──
    private sealed class StatsStub : ILearnedStats
    {
        internal readonly HashSet<string> Learned = new HashSet<string>();
        internal readonly Dictionary<string, int> Times = new Dictionary<string, int>();
        public bool IsLearned(string word) { return Learned.Contains(word); }
        public int TestTimes(string word) { int v; return Times.TryGetValue("t" + word, out v) ? v : 0; }
        public int LastStudyTime(string word) { int v; return Times.TryGetValue("s" + word, out v) ? v : 0; }
    }

    private static string[] SixBook() { return new string[] { "b1", "b2", "b3", "b4", "b5", "b6" }; }

    private static TakeoverScope SetupBook()
    {
        GameAdapter.Fields.Clear(); GameAdapter.Saved.Clear();
        GameAdapter.FailKey = null; GameAdapter.FailSet = false; GameAdapter.Writes = 0;
        var registry = new BookRegistry();
        var manifest = new LanguageManifest { Profile = new BookProfile { Id = "test", Es3Prefix = "test" } };
        registry.Manifests.Add(manifest);
        WcpHostPlugin.Instance = new WcpHostPlugin { Registry = registry };
        var scope = new TakeoverScope();
        scope.Enter(manifest, SixBook());
        return scope;
    }

    private static List<string> ReadPool(string field)
    {
        return GameAdapter.Fields[field] as List<string>;
    }

    private static bool NoForeign(IList<string> words, string[] book)
    {
        var allowed = new HashSet<string>(book);
        for (int i = 0; i < words.Count; i++)
            if (!allowed.Contains(words[i])) return false;
        return true;
    }

    private static TakeoverScope Setup()
    {
        GameAdapter.Fields.Clear(); GameAdapter.Saved.Clear(); GameAdapter.FailKey = null; GameAdapter.FailSet = false; GameAdapter.Writes = 0;
        var registry = new BookRegistry();
        var manifest = new LanguageManifest { Profile = new BookProfile { Id = "test", Es3Prefix = "test" } };
        registry.Manifests.Add(manifest);
        WcpHostPlugin.Instance = new WcpHostPlugin { Registry = registry };
        GameAdapter.Fields[Field] = new string[] { "english" };
        var scope = new TakeoverScope(); scope.Enter(manifest, new string[] { "book" }); return scope;
    }
    private static bool Original() { return ((string[])GameAdapter.Fields[Field]).Length == 1 && ((string[])GameAdapter.Fields[Field])[0] == "english"; }
    private static int Main()
    {
        var scope = Setup(); scope.Enforce(); scope.Leave();
        Check(Original(), "normal array baseline restored");
        scope = Setup(); GameAdapter.FailKey = "test_bak_" + Field; scope.Enforce();
        Check(Original(), "backup write failure prevents takeover");
        scope.Leave(); Check(Original(), "backup failure does not erase original on leave");
        scope = Setup(); GameAdapter.FailKey = "test_owned_arrays"; scope.Enforce();
        Check(Original(), "ownership write failure prevents takeover");
        scope = Setup(); scope.Enforce(); GameAdapter.Saved.Clear(); scope.Leave();
        Check(Original(), "session baseline survives missing disk markers");
        scope = Setup(); scope.Leave();
        Check(GameAdapter.Writes == 0, "inactive unowned leave is read-only");
        scope = Setup(); scope.Leave();
        GameAdapter.Saved["test_owned_arrays"] = new string[] { "UnrelatedField" };
        GameAdapter.Saved["test_bak_UnrelatedField"] = new string[] { "corrupt" };
        GameAdapter.Fields["UnrelatedField"] = new string[] { "keep" };
        scope.RecoverStale(WcpHostPlugin.Instance.Registry, null);
        Check(((string[])GameAdapter.Fields["UnrelatedField"])[0] == "keep", "foreign field in marker is never restored");
        scope = Setup(); scope.Leave();
        GameAdapter.Saved["test_owned_arrays"] = new string[] { Field };
        scope.RecoverStale(WcpHostPlugin.Instance.Registry, null);
        Check(Original(), "missing persisted baseline does not invent empty queue");
        scope = Setup(); scope.Enforce();
        var restarted = new TakeoverScope();
        restarted.Enter(WcpHostPlugin.Instance.Registry.Manifests[0], new string[] { "book" });
        restarted.Enforce(); restarted.Leave();
        Check(Original(), "restart in same profile preserves original baseline");
        scope = Setup();
        GameAdapter.Fields["S8needToLearnWordList_Para"] = new List<string> { "english" };
        GameAdapter.FailKey = "test_bak_S8needToLearnWordList_Para"; scope.Enforce();
        Check(((IList<string>)GameAdapter.Fields["S8needToLearnWordList_Para"])[0] == "english", "list backup failure prevents takeover");
        scope = Setup();
        GameAdapter.Fields["S8needToLearnWordList_Para"] = new List<string> { "english" };
        scope.Enforce(); GameAdapter.Saved.Clear(); scope.Leave();
        Check(((IList<string>)GameAdapter.Fields["S8needToLearnWordList_Para"])[0] == "english", "list session baseline survives missing disk markers");
        scope = Setup(); scope.Enforce(); GameAdapter.FailKey = Field; scope.Leave();
        Check(((string[])GameAdapter.Saved["test_owned_arrays"]).Length == 1, "failed restore keeps retry marker");
        GameAdapter.FailKey = null; scope.RecoverStale(WcpHostPlugin.Instance.Registry, null);
        Check(((string[])GameAdapter.Saved["test_owned_arrays"]).Length == 0 && Original(), "successful recovery clears retry marker");
        scope = Setup(); GameAdapter.Fields["testingIf_Para"] = true; scope.Enforce(); scope.Leave();
        Check((bool)GameAdapter.Fields["testingIf_Para"], "array-only restore does not change test flags");
        scope = Setup(); GameAdapter.FailSet = true; scope.Enforce();
        Check(Original(), "field write failure does not persist takeover");

        // ── 词池隔离（2026-09-15 复查: 法语战斗像英语 / 俄语切日语后仍出现俄语）──
        scope = SetupBook();
        GameAdapter.Fields["S7TestWordList_Para"] = new List<string> { "russian1", "russian2", "b1" };
        scope.Enforce();
        var pool = ReadPool("S7TestWordList_Para");
        Check(pool != null && pool.Count >= 5 && NoForeign(pool, SixBook()),
            "战斗词表被重建为本书词（外部语言残留清零）");

        scope = SetupBook();
        GameAdapter.Fields["S7TestWordList_Para"] =
            new List<string> { "one", "two", "three", "four", "five" };
        scope.Enforce();
        pool = ReadPool("S7TestWordList_Para");
        Check(pool != null && pool.Count >= 5 && NoForeign(pool, SixBook()),
            "one..five 占位词被本书词替换");
        Check(pool != null && !pool.Contains("one"), "占位词不会留在战斗词表里");

        scope = SetupBook();
        GameAdapter.Fields["S8HaveLearnedWordList_Para"] = new List<string> { "english", "b3" };
        scope.Enforce();
        var progress = ReadPool("S8HaveLearnedWordList_Para");
        Check(progress != null && progress.Count == 1 && progress[0] == "b3",
            "学习进度列表只过滤、不补词");

        scope = SetupBook();
        var clean = new List<string> { "b3", "b1", "b5", "b6", "b2" };
        GameAdapter.Fields["S7TestWordList_Para"] = clean;
        scope.Enforce();
        Check(ReferenceEquals(clean, GameAdapter.Fields["S7TestWordList_Para"]),
            "已干净的词池保持原对象（轮询不抖动）");

        scope = SetupBook();
        var stub = new StatsStub();
        stub.Learned.Add("b4"); stub.Learned.Add("b6");
        stub.Times["s" + "b4"] = 5; stub.Times["s" + "b6"] = 1;
        TakeoverScope.StatsProvider = delegate { return stub; };
        GameAdapter.Fields["S7TestWordList_Para"] = new List<string> { "english" };
        scope.Enforce();
        pool = ReadPool("S7TestWordList_Para");
        Check(pool != null && pool.Count >= 5 && pool[0] == "b6" && pool[1] == "b4",
            "补池优先本书已学词并按玩家排序设置排列");
        TakeoverScope.StatsProvider = null;

        scope = SetupBook();
        var rebuilt = scope.RebuildPool("S7TestWordList_Para",
            new List<string> { "russian1" }, 5);
        Check(rebuilt != null && rebuilt.Count >= 5 && NoForeign(rebuilt, SixBook()),
            "补池入口（AddWordsToSelfChosenList）只从本书重建");
        Check(scope.RebuildPool("S8HaveLearnedWordList_Para",
            new List<string> { "english" }, 5) == null, "进度字段不参与补池");

        scope = SetupBook();
        GameAdapter.Fields["S7TestWordList_Para"] = new List<string> { "russian1", "b2" };
        scope.Enforce(); scope.Leave();
        var restored = ReadPool("S7TestWordList_Para");
        Check(restored != null && restored.Count == 2 && restored[0] == "russian1",
            "离开词书后战斗词表还原为接管前内容");

        Console.WriteLine("Failures: " + failures); return failures == 0 ? 0 : 1;
    }
}
