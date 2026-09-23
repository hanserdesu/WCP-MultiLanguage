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
        // 与真实 GameAdapter.ParametersType 同值。缺了这个常量，这个 harness 自
        // TakeoverScope 引入 ParametersType 起就**编译不过**（第七轮复查发现：
        // git HEAD 版同样编译失败，说明它不是本轮改动引起的回归，而是这个门禁
        // 已经死了一段时间 —— 期间 TakeoverScope 的改动没有任何行为测试在守着）。
        internal const string ParametersType = "MyParameters";
        internal static Dictionary<string, object> Fields = new Dictionary<string, object>();
        internal static Dictionary<string, object> Saved = new Dictionary<string, object>();
        internal static string FailKey;
        internal static bool FailSet;
        internal static int Writes;
        // 第七轮新增：ES3 读计数。一次 Es3Load 在真实环境里是一次**整文件解析**
        // （默认存档 SaveFile.es3 实测 6.0MB），所以"每轮读了几次"本身就是指标。
        internal static int Reads;

        // 第八轮新增：整档写计数。真实 GameAdapter 的 Es3BatchScope 把作用域内
        // 所有 Es3Save 合并成一次整档读写（离线实测 45 次逻辑写 5084ms → 110ms，
        // 见 probes/es3bench/probe3.cs）。这里用同样的记账方式建模：
        //   Writes          = 逻辑写次数（真实实现同样一次不少）
        //   WholeFileWrites = 真正落盘的整档写次数
        // 门禁同时守两条：批量必须把 N 次收成 ≤1 次，且**不许靠"少写"变快**。
        internal static int WholeFileWrites;
        private static int _batchOpen;
        private static bool _batchDirty;

        internal static IDisposable Es3BatchScope()
        {
            if (_batchOpen > 0) return null;   // 已在批量中：不嵌套（真实实现同样返回 null）
            _batchOpen = 1;
            _batchDirty = false;
            return new BatchScope();
        }

        private sealed class BatchScope : IDisposable
        {
            private bool _closed;
            public void Dispose()
            {
                if (_closed) return;
                _closed = true;
                if (_batchDirty) WholeFileWrites++;   // 惰性：一次都没写就不落盘
                _batchDirty = false;
                _batchOpen = 0;
            }
        }

        internal static object StaticField(string type, string key) { object v; return Fields.TryGetValue(key, out v) ? v : null; }
        internal static bool SetStaticField(string type, string key, object value)
        { if (FailSet) return false; Fields[key] = value; return true; }
        internal static IList<string> ToWordList(object value) { return value as IList<string>; }
        internal static object Es3Load(string key, Type type, object fallback, string file)
        { Reads++; object v; return Saved.TryGetValue(key, out v) ? v : fallback; }
        internal static bool Es3Save(string key, object value)
        {
            Writes++;
            if (key == FailKey) return false;      // 失败的写不进批量（与真实实现一致）
            if (_batchOpen > 0) _batchDirty = true;
            else WholeFileWrites++;
            Saved[key] = value;
            return true;
        }
    }
}

internal static class TakeoverScopeTest
{
    private const string Field = "S9extraStudy_Para";
    private static int failures;
    private static void Check(bool value, string label)
    { Console.WriteLine((value ? "PASS " : "FAIL ") + label); if (!value) failures++; }

    // 第十四轮：逐词比较两条词池（Plan 等价性门禁用）。null 与空都算"无影响"。
    private static bool SameWords(IList<string> a, IList<string> b)
    {
        if (a == null || b == null) return a == null && b == null;
        if (a.Count != b.Count) return false;
        for (int i = 0; i < a.Count; i++)
            if (!string.Equals(a[i], b[i], StringComparison.Ordinal)) return false;
        return true;
    }

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
        // 第七轮（2026-09-18）：所有权索引（wcp_owned_prefixes）是新增的 mod 自有键，
        // 只在"索引键缺失"这一次迁移里写一次；之后稳态必须完全不写。
        // 原来那条「inactive unowned leave is read-only」在这里被拆成三条更精确的断言：
        //   ① 首次（索引缺失）最多只允许写一次索引键，不许碰任何游戏字段；
        //   ② 索引已就位且为空 → RecoverStale 既不写、也不逐个语言包去读标记；
        //   ③ 索引缺失（旧装）→ 回退全扫一遍（语义不放松，只是慢一次）。
        // ②③ 这一对是第七轮那 698.5ms 的来源与消失的证明：Reads 从"2 × 语言包数"
        // 降到 1。
        scope = Setup(); scope.Leave();
        int migrateWrites = GameAdapter.Writes;
        bool wroteOnlyIndex = migrateWrites == 0 ||
            (migrateWrites == 1 && GameAdapter.Saved.ContainsKey("wcp_owned_prefixes"));
        Check(wroteOnlyIndex, "unowned leave 首次最多只写一次所有权索引迁移");

        GameAdapter.Saved.Clear();
        GameAdapter.Saved["wcp_owned_prefixes"] = new string[0];
        GameAdapter.Writes = 0; GameAdapter.Reads = 0;
        scope.RecoverStale(WcpHostPlugin.Instance.Registry, null);
        Check(GameAdapter.Writes == 0 && GameAdapter.Reads == 1,
            "索引就位且无残留 → RecoverStale 只读 1 次索引，不逐个语言包读标记");

        GameAdapter.Saved.Clear();
        GameAdapter.Writes = 0; GameAdapter.Reads = 0;
        scope.RecoverStale(WcpHostPlugin.Instance.Registry, null);
        Check(GameAdapter.Reads > 1, "索引缺失（旧装）→ 回退全扫，语义不放松");
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
        string[] fallbackBook = { "bonjour", "salut", "merci", "case", "livre" };
        var fallbackPool = BookPool.FailClosedFightPool(
            new List<string> { "english", "bonjour" }, fallbackBook, 5);
        Check(fallbackPool.Count == 5 && NoForeign(fallbackPool, fallbackBook),
            "战斗重建异常时仅从当前词书过滤并补池");
        Check(BookPool.FailClosedFightPool(new List<string> { "english" }, null, 5).Count == 0,
            "当前词书不可用时清空战斗池且不回退全局词典");
        Check(scope.RebuildPool("S8HaveLearnedWordList_Para",
            new List<string> { "english" }, 5) == null, "进度字段不参与补池");

        // 实机法语 20 词快速测试曾由全局英语已学词产生：大多数恰好是
        // version/public 等法英同形词，事后按本书过滤仍能全部通过。
        var quickBook = new string[] { "version", "public", "aller", "manger",
            "bonjour", "chaise", "maison", "parler", "rouge", "livre" };
        var quickStats = new StatsStub();
        quickStats.Learned.Add("version"); quickStats.Learned.Add("public");
        var quick = BookPool.QuickTest(quickBook, quickStats,
            new PoolOrder { Mode = "正序", PriorityOn = true }, 5, new Random(7));
        Check(quick.Count == 5 && NoForeign(quick, quickBook) &&
              !quick.Contains("english") && quick.Exists(delegate(string w)
                  { return w != "version" && w != "public"; }),
            "快速测试从本书供词，不被全局已学同形词垄断");
        var shortQuick = BookPool.QuickTest(new string[] { "aller", "manger" },
            null, new PoolOrder(), 20, new Random(7));
        Check(shortQuick.Count == 2, "短词书快速测试不注入外语词或占位词");

        scope = SetupBook();
        GameAdapter.Fields["S9extraStudy_Para"] = new string[] { "b1", "english" };
        scope.Enforce();
        var selected = GameAdapter.Fields["S9extraStudy_Para"] as string[];
        Check(selected != null && selected.Length == 1 && selected[0] == "b1",
            "手选词只过滤书外词，不自动增加未勾选词");

        // ── 第十四轮（2026-09-18）：BookPool.Plan（单次 Enforce 共享分区+排序）──
        // 门禁一：Plan.Rebuild 与逐规则 BookPool.Rebuild 在 4 种排序设置 × 双向
        // preferLearned × 多个 target 上逐项等价（这是把 706ms 收敛成 2 次排序的
        // 前提：结果必须一个词都不差）。
        var planStats = new StatsStub();
        planStats.Learned.Add("b1"); planStats.Learned.Add("b3"); planStats.Learned.Add("b5");
        planStats.Times["tb1"] = 3; planStats.Times["tb3"] = 1; planStats.Times["tb5"] = 2;
        planStats.Times["sb1"] = 9; planStats.Times["sb3"] = 4; planStats.Times["sb5"] = 7;
        var bigBook = new List<string>();
        for (int i = 0; i < 40; i++) bigBook.Add("w" + i.ToString("D2"));
        bigBook.Add("b1"); bigBook.Add("b3"); bigBook.Add("b5");

        bool planEquiv = true;
        string[] planModes = new string[] { "正序", "倒序" };
        bool[] planPrio = new bool[] { false, true };
        for (int m = 0; m < planModes.Length && planEquiv; m++)
            for (int p = 0; p < planPrio.Length && planEquiv; p++)
            {
                var order = new PoolOrder { Mode = planModes[m], PriorityOn = planPrio[p] };
                var plan = new BookPool.Plan(bigBook, planStats, order);
                for (int prefer = 0; prefer < 2 && planEquiv; prefer++)
                    for (int target = 1; target <= bigBook.Count + 3; target += 7)
                    {
                        var direct = BookPool.Rebuild(bigBook, planStats, order, prefer == 0, target);
                        var viaPlan = plan.Rebuild(prefer == 0, target);
                        if (!SameWords(direct, viaPlan)) planEquiv = false;
                    }
                // 前缀性：同方向下小 target 的结果必须是大 target 结果的前缀
                // （共享计划后各规则取的是同一份有序表的不同前缀）。
                var plan2 = new BookPool.Plan(bigBook, planStats,
                    new PoolOrder { Mode = planModes[m], PriorityOn = planPrio[p] });
                var shortList = plan2.Rebuild(true, 8);
                var longList = plan2.Rebuild(true, 24);
                if (shortList == null || longList == null || longList.Count < 8) planEquiv = false;
                else for (int i = 0; i < 8; i++)
                        if (!string.Equals(shortList[i], longList[i], StringComparison.Ordinal))
                            planEquiv = false;
            }
        Check(planEquiv, "Plan.Rebuild 与 BookPool.Rebuild 逐 target 等价（正/倒序 × 优先级开关 × 双向 × 7 个 target）");
        Check(new BookPool.Plan(null, planStats, null).Rebuild(true, 5) == null,
            "Plan 空书引用 → null（与 Rebuild 一致）");
        Check(new BookPool.Plan(new string[0], planStats, null).Rebuild(false, 5) == null,
            "Plan 空词表 → null（与 Rebuild 一致）");
        var planNoStats = new BookPool.Plan(bigBook, null, new PoolOrder());
        Check(SameWords(BookPool.Rebuild(bigBook, null, new PoolOrder(), true, 10),
                        planNoStats.Rebuild(true, 10)),
            "Plan 无学习进度 → 与 Rebuild 等价（全部视为未学）");

        // 门禁二：FilterOnly 集合重载与列表重载等价（Enforce 的 17 条规则改为
        // 共享授权集的前提）。
        var fcurrent = new List<string> { "zz", "b1", "b1", "w05", "", "  ", null, "b3" };
        var viaSet = BookPool.FilterOnly(fcurrent, BookPool.ToSet(bigBook));
        var viaList = BookPool.FilterOnly(fcurrent, bigBook);
        Check(viaSet != null && viaSet.Count == 3 && viaSet[0] == "b1" &&
              viaSet[1] == "w05" && viaSet[2] == "b3" && SameWords(viaSet, viaList),
            "FilterOnly(current, allowed 集合) 与 FilterOnly(current, book 列表) 等价");

        scope = SetupBook();
        GameAdapter.Fields["S7TestWordList_Para"] = new List<string> { "russian1", "b2" };
        scope.Enforce(); scope.Leave();
        var restored = ReadPool("S7TestWordList_Para");
        Check(restored != null && restored.Count == 2 && restored[0] == "russian1",
            "离开词书后战斗词表还原为接管前内容");

        scope = SetupBook();
        GameAdapter.Fields["ChosenBook_List"] = new List<string>(SixBook());
        GameAdapter.Fields["S7TestWordList_Para"] = new List<string> { "russian1", "b2" };
        scope.Enforce(); scope.Leave();
        restored = ReadPool("S7TestWordList_Para");
        Check(restored != null && restored.Count >= BookPool.MinPlayable &&
              NoForeign(restored, SixBook()),
            "离开词书时旧语言战斗队列按当前书修复，不重新写回俄语");

        // ── 第八轮：ES3 整文件写风暴的批量化（2026-09-18）─────────────────────
        //
        // 背景：ES3 每次「不带路径的 Save」都是整档读+解析+序列化+写。默认存档
        // SaveFile.es3 本机实测 6.0MB / 341 键，逐键写 45 次 = 5084ms（离线 A/B
        // probes/es3bench/probe3.cs，批量后 110ms）。这一组的目的是把"批量"钉成
        // **可回归的不变量**，含反面：不许靠"少写几个键"变快。
        scope = SetupBook();
        string[] burst = { "S7TestWordList_Para", "S8TestWordList_Para",
                           "S8TestWordList_ExtraReview", "allTestWordsS10_Para" };
        for (int i = 0; i < burst.Length; i++)
            GameAdapter.Fields[burst[i]] = new List<string> { "russian1" };
        GameAdapter.Writes = 0; GameAdapter.WholeFileWrites = 0;
        scope.Enforce();
        int burstLogical = GameAdapter.Writes, burstWhole = GameAdapter.WholeFileWrites;
        // 每个待重建字段至少两次逻辑写（bak_ + 游戏字段本身），4 个字段 → ≥8。
        // 这条是反作弊线：批量只允许减少"整档写"，不允许减少"逻辑写"。
        Check(burstLogical >= 8, "重建多字段的逻辑写次数不因批量而减少（" + burstLogical + " ≥ 8）");
        Check(burstWhole == 1, "重建多字段的整档写合并为 1 次（" + burstLogical + " 逻辑写 → " + burstWhole + " 整档写）");

        // 稳态：字段已干净，Enforce 一个键都不写 → 批量作用域不该装载/落盘。
        // 这是"用户无感知"的关键——每轮轮询的稳态成本必须是 0。
        GameAdapter.Writes = 0; GameAdapter.WholeFileWrites = 0;
        scope.Enforce(); scope.Enforce();
        Check(GameAdapter.Writes == 0 && GameAdapter.WholeFileWrites == 0,
            "稳态 Enforce（无需修正）零逻辑写、零整档写（惰性批量不装载）");

        // 离开词书：4 个待还原字段 + 2 个残留标记键，同样只落一次盘。
        GameAdapter.Writes = 0; GameAdapter.WholeFileWrites = 0;
        scope.Leave();
        int leaveLogical = GameAdapter.Writes, leaveWhole = GameAdapter.WholeFileWrites;
        Check(leaveLogical >= 4, "Leave 还原的逻辑写一次不少（" + leaveLogical + " ≥ 4）");
        Check(leaveWhole == 1, "Leave 还原合并为 1 次整档写（" + leaveLogical + " 逻辑写 → " + leaveWhole + "）");
        var afterLeave = ReadPool("S7TestWordList_Para");
        Check(afterLeave != null && afterLeave.Count == 1 && afterLeave[0] == "russian1",
            "批量提交后离开词书，字段内容仍被正确还原（不是只写了标记）");

        // 作用域不嵌套：已经开着的批量里再开一次必须拿到 null（否则内层 Dispose
        // 会把外层的未提交改动提前落盘，并清掉外层还没写完的缓存）。
        using (GameAdapter.Es3BatchScope())
        {
            Check(GameAdapter.Es3BatchScope() == null, "批量作用域不嵌套（内层返回 null）");
        }
        GameAdapter.Writes = 0; GameAdapter.WholeFileWrites = 0;
        scope.Enforce();
        Check(GameAdapter.WholeFileWrites <= 1, "嵌套保护退出后外层批量仍然可用");

        // ── 第十一轮（2026-09-18）：整帧合并成一次整档读写 ────────────────────
        //
        // 实机第九/十轮日志（20:02 那次，长帧 1561ms 的切书帧）：
        //     ES3:批量写(装载) x3 = 349.0ms   ES3:批量写(提交) x3 = 206.9ms
        // 即**同一次切书做了 3 次整档读和 3 次整档写**。原因是「还原旧书 / 播种新书 /
        // 校正队列」三步在同一帧内顺序发生，但各自开了一层 Es3BatchScope()：
        // 不嵌套的语义只挡住"作用域套作用域"，挡不住"顺序开三次"。
        // Host.Update 与 EnforceNowForScene 现在在整个帧外面套了一层外层作用域，
        // 三步自动共享同一个批次。这组门禁把该不变量钉住，含对照与反面断言。
        var frame = SetupBook();
        GameAdapter.Fields["S7TestWordList_Para"] = new List<string> { "russian1" };
        frame.Enforce();                                  // 让旧书带上待还原的改动

        // 对照：不套外层，同样三步 → 多次落盘（这就是合并要消掉的那部分）。
        GameAdapter.Writes = 0; GameAdapter.WholeFileWrites = 0;
        frame.Leave();
        var noOuter = new TakeoverScope();
        noOuter.Enter(WcpHostPlugin.Instance.Registry.Manifests[0], SixBook());
        noOuter.Enforce();
        int baselineWhole = GameAdapter.WholeFileWrites;

        // 合并后：整个帧套一层外层作用域 → 只落一次盘。
        var frame2 = SetupBook();
        GameAdapter.Fields["S7TestWordList_Para"] = new List<string> { "russian1" };
        frame2.Enforce();
        GameAdapter.Writes = 0; GameAdapter.WholeFileWrites = 0;
        using (GameAdapter.Es3BatchScope())               // = Host.Update 里新加的那一层
        {
            frame2.Leave();                               // 1) 还原旧书
            var entering = new TakeoverScope();
            entering.Enter(WcpHostPlugin.Instance.Registry.Manifests[0], SixBook());  // 2) 播种
            entering.Enforce();                           // 3) 校正
        }
        int frameLogical = GameAdapter.Writes, frameWhole = GameAdapter.WholeFileWrites;

        Check(baselineWhole >= 2,
            "（对照）不套外层时 还原+播种+校正 会落 ≥2 次整档写（实际 " + baselineWhole + "）");
        Check(frameWhole == 1,
            "整帧只落 1 次整档写（" + frameLogical + " 逻辑写 → " + frameWhole + "，合并前 " + baselineWhole + "）");
        // 反作弊线：合并只允许减少"整档写"，不允许减少"逻辑写"。
        Check(frameLogical >= 6,
            "整帧的逻辑写不因合并而减少（" + frameLogical + " ≥ 6）");
        Check(ReadPool("S7TestWordList_Para") != null,
            "整帧合并后字段仍被写回（不是靠不写变快）");

        // 探针标签必须在（否则上面的账算不清，也没人会发现标签被改掉了）。
        Check(PerfProbe.WindowCount("队列:授权集") > 0 &&
              PerfProbe.WindowCount("队列:规则") > 0 &&
              PerfProbe.WindowCount("队列:对齐") > 0,
            "Enforce 三段探针标签都在（队列:授权集 / 队列:规则 / 队列:对齐）");

        CheckSortGate();

        Console.WriteLine("Failures: " + failures); return failures == 0 ? 0 : 1;
    }

    // ══ 第十五轮（2026-09-18）：SortBySetting 装饰-排序-脱饰 门禁 ══════════════
    // 背景：原实现每对比较都调 stats（IDictionary.Contains + 反射 GetValue），
    // 8000+ 词书首次排序实机 642~702ms。新实现键抽取一次（O(n) 次 stats 调用）、
    // 排序纯 int 比较。门禁验三件事：① 与旧比较器在键唯一时输出完全一致；
    // ② stats 调用次数从 O(n log n) 降到 O(n)（这正是优化的本体）；③ 平级输入
    // 下输出仍是合法有序序列（原排序不稳定，平级次序不作为等价条件）。
    private sealed class CountingStats : ILearnedStats
    {
        internal int TestCalls, TimeCalls;
        internal readonly Dictionary<string, int> Times = new Dictionary<string, int>();
        public bool IsLearned(string word) { return Times.ContainsKey("l" + word); }
        public int TestTimes(string word) { TestCalls++; int v; return Times.TryGetValue("t" + word, out v) ? v : 0; }
        public int LastStudyTime(string word) { TimeCalls++; int v; return Times.TryGetValue("s" + word, out v) ? v : 0; }
    }

    // 旧比较器的参考实现（语义与改动前逐条相同），等价性对照用。
    private static void RefSort(List<string> words, CountingStats stats, bool priority, bool desc)
    {
        if (priority)
            words.Sort(delegate(string a, string b)
            {
                int byTimes = stats.TestTimes(a).CompareTo(stats.TestTimes(b));
                if (byTimes != 0) return byTimes;
                int sa = stats.LastStudyTime(a), sb = stats.LastStudyTime(b);
                return desc ? sb.CompareTo(sa) : sa.CompareTo(sb);
            });
        else if (desc)
            words.Sort(delegate(string a, string b)
            { return stats.TestTimes(b).CompareTo(stats.TestTimes(a)); });
        else
            words.Sort(delegate(string a, string b)
            { return stats.LastStudyTime(a).CompareTo(stats.LastStudyTime(b)); });
    }

    private static PoolOrder Order(bool priority, bool desc)
    {
        PoolOrder o = new PoolOrder();
        o.PriorityOn = priority;
        o.Mode = desc ? "倒序" : "正序";
        return o;
    }

    private static bool SameMultiset(IList<string> a, IList<string> b)
    {
        if (a == null || b == null || a.Count != b.Count) return false;
        Dictionary<string, int> counts = new Dictionary<string, int>(StringComparer.Ordinal);
        for (int i = 0; i < a.Count; i++)
        { int v; counts.TryGetValue(a[i], out v); counts[a[i]] = v + 1; }
        for (int i = 0; i < b.Count; i++)
        {
            int v;
            if (!counts.TryGetValue(b[i], out v) || v == 0) return false;
            counts[b[i]] = v - 1;
        }
        return true;
    }

    private static void CheckSortGate()
    {
        // 数据集 A：键全唯一（tt=i, lst=999-i）→ 与旧比较器输出必须逐位一致。
        const int N = 300;
        string[] unique = new string[N];
        for (int i = 0; i < N; i++) unique[i] = "w" + i.ToString("D4");

        bool[,] configs = new bool[4, 2] { { true, false }, { true, true }, { false, false }, { false, true } };
        for (int c = 0; c < 4; c++)
        {
            bool priority = configs[c, 0], desc = configs[c, 1];
            CountingStats s1 = new CountingStats(), s2 = new CountingStats();
            for (int i = 0; i < N; i++)
            {
                s1.Times["t" + unique[i]] = i;       s1.Times["s" + unique[i]] = 999 - i;
                s2.Times["t" + unique[i]] = i;       s2.Times["s" + unique[i]] = 999 - i;
            }
            List<string> viaNew = new List<string>(unique);
            BookPool.SortBySetting(viaNew, s1, Order(priority, desc));
            List<string> viaRef = new List<string>(unique);
            RefSort(viaRef, s2, priority, desc);
            Check(SameWords(viaNew, viaRef),
                "排序等价（键唯一, priority=" + priority + ", desc=" + desc + "）");

            // 调用次数：装饰阶段每词恰好一次（priority 模式两种各一次）——
            // 这正是 O(n log n)→O(n) 的本体断言。
            if (priority)
                Check(s1.TestCalls == N && s1.TimeCalls == N,
                    "键抽取 O(n)（priority: TestTimes=" + s1.TestCalls + ", LastStudyTime=" + s1.TimeCalls + ", n=" + N + "）");
            else if (desc)
                Check(s1.TestCalls == N && s1.TimeCalls == 0,
                    "键抽取 O(n)（desc: TestTimes=" + s1.TestCalls + "==" + N + ", LastStudyTime=0）");
            else
                Check(s1.TimeCalls == N && s1.TestCalls == 0,
                    "键抽取 O(n)（asc: LastStudyTime=" + s1.TimeCalls + "==" + N + ", TestTimes=0）");
        }

        // 数据集 B：键全平级（全是 0）→ 旧排序不稳定、次序不作等价条件；
        // 只要求：① 输出是输入的一个排列；② 新输出按 (键, 词序) 确定有序。
        CountingStats s3 = new CountingStats();   // 全部 miss → 键恒 0
        List<string> flat = new List<string>(unique);
        BookPool.SortBySetting(flat, s3, Order(false, false));
        Check(SameMultiset(flat, unique), "平级输入输出仍是输入的排列（asc）");
        bool sorted = true;
        for (int i = 1; i < flat.Count && sorted; i++)
            if (string.CompareOrdinal(flat[i - 1], flat[i]) > 0) sorted = false;
        Check(sorted, "平级输入按词序确定化（原为不稳定排序）");

        // 随机模式：仍是洗牌（多集不变；次序不作断言 —— 种子取自时钟）。
        List<string> shuf = new List<string>(unique);
        PoolOrder rnd = new PoolOrder(); rnd.Mode = "随机";
        BookPool.SortBySetting(shuf, new CountingStats(), rnd);
        Check(SameMultiset(shuf, unique), "随机模式仍为洗牌（多集不变）");
    }
}
