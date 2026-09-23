// RegistryTest — 在游戏外验证身份/策略层（不启动游戏）。
//
// 覆盖范围: 与游戏相同的 WcpHost.dll 中的机制部分，以及可加载的 pack 策略
//   · packs/<lang>/manifest.json 解析（Json.cs）
//   · 注册表加载 / 去重 / 槽位预算（Manifest.cs）
//   · 指纹算法与真实存档词表的一致性（BookRegistry.FingerprintOf）
//   · 负面识别：非受管词表一律不命中（汇成一个语言包都不认）
//
// 不覆盖: Unity 侧胶水（GameAdapter 反射、Host.Update 的每秒判定）和 Harmony 补丁。那部分
// 必须在游戏里跑才作数 —— 本测试的作用是把"机制错了"排除掉，让实机只剩
// "接线对不对"这一个变量。
//
// 用法: tests\run_registry_test.cmd  [packsRoot] [MyBook.es3]
using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using WcpHost;

internal static class RegistryTest
{
    private static int _fail;

    private static void Check(bool ok, string label, string detail)
    {
        Console.WriteLine((ok ? "  PASS  " : "  FAIL  ") + label +
                          (string.IsNullOrEmpty(detail) ? "" : "   " + detail));
        if (!ok) _fail++;
    }

    private static int Main(string[] args)
    {
        try { Console.OutputEncoding = Encoding.UTF8; }
        catch (Exception) { }

        // 第十六轮：GameLearnedStats 快照门禁第一次把 mod 的 BepInEx/UnityEngine
        // 引用链拖进了离线进程（JIT 告警分支需要解析这些类型的程序集令牌）。
        // 挂一个按需解析钩子：从游戏目录找 dll —— 拷贝传递依赖是无底洞。
        string gameDir = Environment.GetEnvironmentVariable("WCP_GAME_DIR");
        if (!string.IsNullOrEmpty(gameDir) && Directory.Exists(gameDir))
        {
            string coreDir = Path.Combine(gameDir, "BepInEx", "core");
            string managedDir = Path.Combine(gameDir, "wcp_Data", "Managed");
            AppDomain.CurrentDomain.AssemblyResolve += delegate(object s, ResolveEventArgs a)
            {
                string name = new System.Reflection.AssemblyName(a.Name).Name;
                foreach (string dir in new string[] { coreDir, managedDir })
                {
                    string p = Path.Combine(dir, name + ".dll");
                    if (File.Exists(p)) return System.Reflection.Assembly.LoadFrom(p);
                }
                return null;
            };
        }

        // packs 根不再写死成某台机器的绝对路径：run_registry_test.cmd 会把
        // 仓库自己的 packs 目录作为第一个参数传进来；直接运行 exe 时可用
        // 环境变量 WCP_PACKS_ROOT 指定（必须包含 <lang>/manifest.json）。
        string packsRoot = args.Length > 0 ? args[0]
            : Environment.GetEnvironmentVariable("WCP_PACKS_ROOT");
        if (string.IsNullOrEmpty(packsRoot))
            throw new InvalidOperationException(
                "未指定 packs 根：用 run_registry_test.cmd 运行（自动传入仓库 packs），" +
                "或传参数 / 设 WCP_PACKS_ROOT（包含 <lang>/manifest.json 的目录）");
        string es3 = args.Length > 1 ? args[1] : Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.UserProfile),
            @"AppData\LocalLow\WCP\wcp\MyBook.es3");

        Console.WriteLine("packs = " + packsRoot);
        Console.WriteLine("存档  = " + es3);
        Console.WriteLine();

        BookRegistry reg = BookRegistry.Load(packsRoot);
        Console.WriteLine("加载语言包 = " + reg.Manifests.Count +
                          "，加载告警 = " + reg.Errors.Count);
        for (int i = 0; i < reg.Errors.Count; i++)
            Console.WriteLine("   告警: " + reg.Errors[i]);
        Check(reg.Errors.Count == 0, "注册表加载无告警", "");
        Check(reg.Manifests.Count >= 1,
              "至少加载 1 个语言包", "实际 " + reg.Manifests.Count);
        CheckDuplicateWordCountIsAllowed();
        CheckDuplicateEs3PrefixIsRejected();
        CheckMultipleUnassignedPacksAreAllowed();
        CheckHostGenericStrategy();
        CheckWordListMemo(packsRoot);
        CheckLearnedSnapshot();

        for (int i = 0; i < reg.Manifests.Count; i++)
        {
            BookProfile p = reg.Manifests[i].Profile;
            Console.WriteLine(string.Format("   [{0}] {1} 词={2} 槽={3} 指纹={4}…",
                p.Language, p.Id, p.WordCount, p.ObservedSlot, p.Fingerprint.Substring(0, 12)));
        }

        string budgetDetail;
        bool budgetOk = reg.SlotBudgetOk(out budgetDetail);
        Check(budgetOk, "槽位预算 ≤ 4", budgetDetail);

        StrategyRegistry strategies = StrategyRegistry.Load(reg);
        foreach (string strategyError in strategies.Errors)
            Console.WriteLine("  STRATEGY-ERR  " + strategyError);
        Check(strategies.LoadedCount + strategies.Errors.Count == reg.Manifests.Count,
              "策略装载结果覆盖全部语言包",
              "已装载 " + strategies.LoadedCount + "，告警 " + strategies.Errors.Count);

        LanguageManifest jaManifest = reg.ByLanguage("ja");
        ILanguageStrategy ja = jaManifest == null ? null :
            strategies.ForProfile(jaManifest.Profile.Id);
        Check(ja != null, "日语策略从 pack 程序集实际装载", "");
        if (ja != null)
        {
            try
            {
                string nested = ja.ExtractSentenceKey(
                    "<b>例句：うちの旦那。（我家的那位（丈夫）。）</b>");
                Check(nested == "うちの旦那。", "日语例句切分拒绝嵌套译文括号", nested);

                string meaning, phonic;
                bool found = ja.ProvideMeaning("歯医者", out meaning, out phonic);
                Check(found && !string.IsNullOrEmpty(meaning) && !string.IsNullOrEmpty(phonic),
                      "日语策略读取 pack 内 pron", "meaning=" + meaning + " phonic=" + phonic +
                      " error=" + StrategyError(ja));
                if (found)
                {
                    string stem = ja.StemDisplay("歯医者", null);
                    Check(stem == phonic, "日语题干使用 pack 读音", stem);
                    Check(ja.AudioLookupForm(stem, "歯医者") == "歯医者",
                          "日语假名音频回查还原词形", stem);
                    // 自由复习浏览页: 显示词不是队列指针词, 靠读音反查索引还原词形。
                    // 長い 的读音是 ながい; 指针词故意传另一个已收录词 ずいぶん。
                    string viaIndex = ja.AudioLookupForm("ながい", "ずいぶん");
                    Check(viaIndex == "長い" || viaIndex == "永い",
                          "日语读音反查索引跨词还原词形",
                          "ながい -> " + viaIndex);
                    Check(ja.AudioLookupForm("ぜんぜんしらない", "ずいぶん") == "ぜんぜんしらない",
                          "日语读音索引对未收录假名 fail-closed",
                          ja.AudioLookupForm("ぜんぜんしらない", "ずいぶん"));
                    Check(!string.IsNullOrEmpty(ja.OptionDisplay("歯医者", meaning)),
                          "日语选项保留本地释义", "");
                }
            }
            catch (Exception e)
            {
                Check(false, "日语策略行为调用未抛异常", ExceptionSummary(e));
            }

            // ── 粤语策略（与日语同构: 显示形=拼音, 音频按词形命名）──
            ILanguageStrategy yue = null;
            LanguageManifest yueManifest = reg.ByLanguage("yue");
            if (yueManifest != null)
                yue = strategies.ForProfile(yueManifest.Profile.Id);
            if (yue != null)
            {
                try
                {
                    string ystem = yue.StemDisplay("一擔擔", null);
                    Check(ystem == "jat1 daam1 daam1",
                          "粤语题干使用 pack 拼音读音", ystem);
                    // 浏览页: 显示词的拼音 + 指针词是另一条 → 反查回显示词词形,
                    // 不允许静默用指针词的音频。
                    string yueHit = yue.AudioLookupForm(ystem, "一陣");
                    Check(yueHit == "一擔擔",
                          "粤语读音反查索引跨词还原词形",
                          "jat1 daam1 daam1 -> " + yueHit);
                    Check(yue.AudioLookupForm("ngoi1 zi6", "一陣") == "ngoi1 zi6",
                          "粤语读音索引对未收录拼音 fail-closed",
                          yue.AudioLookupForm("ngoi1 zi6", "一陣"));
                }
                catch (Exception e)
                {
                    Check(false, "粤语策略行为调用未抛异常", ExceptionSummary(e));
                }
            }
        }

        Console.WriteLine("\n== 资源路由回归（pack 内路径 + fail-closed） ==");
        ResourceRouter router = new ResourceRouter(reg);
        Check(router.Resolve(ResourceKind.MeaningDb, "probe") == null,
              "未激活时释义资源为空", "");
        Check(router.Resolve(ResourceKind.WordAudio, "probe") == null,
              "未激活时单词音频为空", "");
        for (int i = 0; i < reg.Manifests.Count; i++)
        {
            LanguageManifest m = reg.Manifests[i];
            router.SetActive(m.Profile.Id);
            string meaning = router.Resolve(ResourceKind.MeaningDb, "probe");
            string wordAudio = router.Resolve(ResourceKind.WordAudio, "gehen");
            string sentenceAudio = router.Resolve(ResourceKind.SentenceAudio, "例句 probe");
            Check(IsInside(m.PackRoot, meaning), m.Profile.Language + " 释义路由在 pack 内", meaning);
            Check(IsInside(m.PackRoot, wordAudio) && wordAudio.EndsWith("gehen.mp3", StringComparison.Ordinal),
                  m.Profile.Language + " 单词音频路由在 pack 内", wordAudio);
            Check(IsInside(m.PackRoot, sentenceAudio) && sentenceAudio.EndsWith(".mp3", StringComparison.Ordinal),
                  m.Profile.Language + " 例句音频路由在 pack 内", sentenceAudio);
            Check(m.Resolve("../outside") == null, m.Profile.Language + " 拒绝 pack 越界路径", "");
        }
        router.SetActive(null);
        Check(!router.IsActive, "取消激活后路由关闭", "");

        if (!File.Exists(es3))
        {
            Console.WriteLine("\n找不到存档，槽位回归跳过。结果: " +
                              (_fail == 0 ? "机制部分通过" : _fail + " 条 FAIL"));
            return _fail == 0 ? 0 : 1;
        }

        string text = File.ReadAllText(es3, Encoding.UTF8).TrimStart('\uFEFF');
        Dictionary<string, object> root = Json.AsDict(Json.Parse(text));

        Console.WriteLine("\n== 槽位回归（真实存档词表 -> Match） ==");
        int matched = 0, empty = 0;
        for (int slot = 1; slot <= 4; slot++)
        {
            List<string> words = Json.StrList(Json.Sub(root, "SelfBookList" + slot), "value");
            if (words.Count == 0)
            {
                empty++;
                Check(reg.Match(words) == null, "槽 " + slot + " 空 -> 不匹配受管词书", "");
                continue;
            }
            BookProfile p = reg.Match(words);
            if (p == null)
            {
                Check(false, "槽 " + slot + " 命中语言包", words.Count + " 词 -> null");
                continue;
            }
            matched++;
            string fp = BookRegistry.FingerprintOf(words);
            Check(fp == p.Fingerprint, "槽 " + slot + " 指纹与清单一致",
                p.Language + "/" + p.Id +
                "  声明=" + p.Fingerprint.Substring(0, 12) +
                " 实算=" + fp.Substring(0, 12));
        }
        Check(matched + empty == 4, "所有存档槽位完成识别",
              "非空命中 " + matched + "，空 " + empty);
        Check(empty + matched == 4, "槽位总数为 4", "空 " + empty + " + 命中 " + matched);

        Console.WriteLine("\n== 唯一性矩阵（一个槽的词表只能命中一个语言包） ==");
        for (int slot = 1; slot <= 4; slot++)
        {
            List<string> words = Json.StrList(Json.Sub(root, "SelfBookList" + slot), "value");
            if (words.Count == 0) continue;
            int hits = 0;
            string who = "";
            for (int i = 0; i < reg.Manifests.Count; i++)
                if (reg.Manifests[i].Matches(words))
                {
                    hits++;
                    who += reg.Manifests[i].Profile.Language + " ";
                }
            Check(hits == 1, "槽 " + slot + " 唯一命中",
                hits + " 个 (" + who.Trim() + ")");
        }

        Console.WriteLine();
        Console.WriteLine("结果: " + (_fail == 0 ? "全部通过" : _fail + " 条 FAIL"));
        return _fail == 0 ? 0 : 1;
    }

    private static bool IsInside(string root, string path)
    {
        if (string.IsNullOrEmpty(root) || string.IsNullOrEmpty(path)) return false;
        string fullRoot = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar,
                                                         Path.AltDirectorySeparatorChar) +
                          Path.DirectorySeparatorChar;
        string fullPath = Path.GetFullPath(path);
        return fullPath.StartsWith(fullRoot, StringComparison.OrdinalIgnoreCase);
    }

    private static void CheckDuplicateWordCountIsAllowed()
    {
        string root = Path.Combine(Path.GetTempPath(),
            "wcphost_registry_" + Guid.NewGuid().ToString("N"));
        try
        {
            Directory.CreateDirectory(Path.Combine(root, "aa"));
            Directory.CreateDirectory(Path.Combine(root, "bb"));
            File.WriteAllText(Path.Combine(root, "aa", "manifest.json"),
                SyntheticManifest("profile-aa", "aa", "1", 1));
            File.WriteAllText(Path.Combine(root, "bb", "manifest.json"),
                SyntheticManifest("profile-bb", "bb", "2", 2));

            BookRegistry synthetic = BookRegistry.Load(root);
            Check(synthetic.Errors.Count == 0 && synthetic.Manifests.Count == 2,
                  "不同指纹但同词数的语言包都能注册",
                  "清单 " + synthetic.Manifests.Count + "，告警 " + synthetic.Errors.Count);
        }
        catch (Exception e)
        {
            Check(false, "同词数注册回归未抛异常", ExceptionSummary(e));
        }
        finally
        {
            try
            {
                if (Directory.Exists(root)) Directory.Delete(root, true);
            }
            catch (Exception e)
            {
                Console.WriteLine("  WARN  清理注册表临时目录失败: " + e.Message);
            }
        }
    }

    private static void CheckDuplicateEs3PrefixIsRejected()
    {
        string root = Path.Combine(Path.GetTempPath(),
            "wcphost_registry_prefix_" + Guid.NewGuid().ToString("N"));
        try
        {
            Directory.CreateDirectory(Path.Combine(root, "aa"));
            Directory.CreateDirectory(Path.Combine(root, "bb"));
            File.WriteAllText(Path.Combine(root, "aa", "manifest.json"),
                SyntheticManifestWithPrefix("profile-aa", "aa", "3", 1, "shared"));
            File.WriteAllText(Path.Combine(root, "bb", "manifest.json"),
                SyntheticManifestWithPrefix("profile-bb", "bb", "4", 2, "shared"));

            BookRegistry synthetic = BookRegistry.Load(root);
            Check(synthetic.Manifests.Count == 1 && synthetic.Errors.Count == 1,
                  "重复 ES3 前缀的语言包被拒绝",
                  "清单 " + synthetic.Manifests.Count + "，告警 " + synthetic.Errors.Count);
        }
        catch (Exception e)
        {
            Check(false, "重复 ES3 前缀回归未抛异常", ExceptionSummary(e));
        }
        finally
        {
            try
            {
                if (Directory.Exists(root)) Directory.Delete(root, true);
            }
            catch (Exception e)
            {
                Console.WriteLine("  WARN  清理前缀临时目录失败: " + e.Message);
            }
        }
    }

    private static void CheckMultipleUnassignedPacksAreAllowed()
    {
        string root = Path.Combine(Path.GetTempPath(),
            "wcphost_registry_unassigned_" + Guid.NewGuid().ToString("N"));
        try
        {
            Directory.CreateDirectory(Path.Combine(root, "aa"));
            Directory.CreateDirectory(Path.Combine(root, "bb"));
            File.WriteAllText(Path.Combine(root, "aa", "manifest.json"),
                SyntheticManifest("profile-aa", "aa", "5", 0));
            File.WriteAllText(Path.Combine(root, "bb", "manifest.json"),
                SyntheticManifest("profile-bb", "bb", "6", 0));

            BookRegistry synthetic = BookRegistry.Load(root);
            string detail;
            Check(synthetic.Errors.Count == 0 && synthetic.Manifests.Count == 2,
                  "多个未分配槽位语言包可以注册",
                  "清单 " + synthetic.Manifests.Count + "，告警 " + synthetic.Errors.Count);
            Check(synthetic.SlotBudgetOk(out detail),
                  "未分配槽位语言包不消耗槽位预算", detail);
        }
        catch (Exception e)
        {
            Check(false, "未分配槽位注册回归未抛异常", ExceptionSummary(e));
        }
        finally
        {
            try
            {
                if (Directory.Exists(root)) Directory.Delete(root, true);
            }
            catch (Exception e)
            {
                Console.WriteLine("  WARN  清理未分配槽位临时目录失败: " + e.Message);
            }
        }
    }

    // 第十二轮（2026-09-18）：WordListMemo 是 Host.Evaluate 里
    // `身份:匹配内存词表` 的守卫 —— 词表元素引用没变就直接复用上一轮的 Match 结论。
    // 它必须被钉死，因为"守卫判错"的后果是身份判定用旧结论：多省钱可以商量，
    // 判错不行。这里钉的是它的**精确性边界**：
    //   命中 ⟺ 元素引用逐位相同（string 不可变 ⟹ 内容必然相同，结论必然成立）
    //   未命中 ⟸ 任何内容变化（某个位置换了实例，引用比对必然发现）
    private static void CheckWordListMemo(string packsRoot)
    {
        BookRegistry reg = BookRegistry.Load(packsRoot);
        BookRegistry reg2 = BookRegistry.Load(packsRoot);   // 同内容、不同实例
        BookProfile sentinel = reg.Manifests.Count > 0
            ? reg.Manifests[0].Profile : null;
        WordListMemo memo = new WordListMemo();

        List<string> a = new List<string> { "alpha", "beta", "gamma" };

        BookProfile p;
        Check(!memo.TryHit(reg, a, out p) && p == null,
              "守卫空状态必然未命中", "");
        memo.Store(reg, a, sentinel);
        Check(memo.TryHit(reg, a, out p) && ReferenceEquals(p, sentinel),
              "同一份词表（同元素引用）必然命中并复用同一 profile 对象", "");
        // 新容器、元素引用原样拷贝 → 仍必须命中（守卫看的是元素，不是容器）。
        List<string> b = new List<string>(a);
        Check(memo.TryHit(reg, b, out p) && ReferenceEquals(p, sentinel),
              "容器换新但元素引用一致仍命中", "");
        // 同内容、不同实例（new string 保证非驻留新引用）→ 必须未命中。
        // 这是"安全方向"：宁可白算一次 Match，也绝不用旧结论。
        b[0] = new string("alpha".ToCharArray());
        Check(!memo.TryHit(reg, b, out p),
              "内容相同但元素换了实例必须未命中（安全方向）", "");
        // 元素数变化 → 必须未命中；且把新状态存进去后，旧长度的词表不再命中。
        b.Add("delta");
        Check(!memo.TryHit(reg, b, out p),
              "元素数变化必须未命中", "");
        memo.Store(reg, b, null);   // 上一轮没命中（null profile）也要能被记住
        Check(memo.TryHit(reg, b, out p) && p == null,
              "上一轮未命中（null）也能被守卫复用", "");
        Check(!memo.TryHit(reg, a, out p),
              "存过长词表后旧长度的词表不再命中", "");
        // 注册表实例换了（重新 Load）→ 必须未命中：上一轮结论是旧注册表下的。
        Check(!memo.TryHit(reg2, b, out p),
              "注册表实例更换必须未命中", "");
        memo.Store(reg, null, sentinel);
        Check(!memo.TryHit(reg, a, out p),
              "存 null 词表后必然未命中（不残留旧快照）", "");
    }

    // 第十六轮：GameLearnedStats 查询快照化的精确性门禁。
    // 实机（R15 日志 23:45）场景进入 Rebuild 的 队列:规则 单次 804.6ms 来自逐词
    // Contains+反射；快照把查询变成哈希查找。这里钉死快照的语义边界：
    //   命中/数值 ⟺ 建快照那一刻字典里的内容（Enforce 期间不允许看到中途变化）；
    //   快照建立后字典再变 → 查询仍回答快照时的值（本 Enforce 内的稳定视图）。
    private sealed class FakeEntry { public int testTimes; public int lastStudyTime; }

    private static void CheckLearnedSnapshot()
    {
        Dictionary<string, object> dict = new Dictionary<string, object>();
        FakeEntry e1 = new FakeEntry(); e1.testTimes = 3; e1.lastStudyTime = 100;
        FakeEntry e2 = new FakeEntry(); e2.testTimes = 0; e2.lastStudyTime = 55;
        dict["apple"] = e1;
        dict["banana"] = e2;
        dict["cherry"] = null;              // 脏条目：必须被跳过而不是抛异常
        dict["bad\0key"] = e1;              // 非常规键：照常进快照
        GameLearnedStats stats = new GameLearnedStats(dict);

        Check(stats.IsLearned("apple"), "快照命中已学词（IsLearned）",
            "learned=" + stats.IsLearned("apple") + " err=" + GameLearnedStats.LastBuildError +
            " scanned=" + GameLearnedStats.ScannedCount);
        Check(stats.TestTimes("apple") == 3, "快照给出 testTimes 数值",
            "times=" + stats.TestTimes("apple"));
        Check(stats.LastStudyTime("apple") == 100, "快照给出 lastStudyTime 数值",
            "last=" + stats.LastStudyTime("apple"));
        Check(stats.IsLearned("banana") && stats.TestTimes("banana") == 0 &&
              stats.LastStudyTime("banana") == 55, "testTimes=0 的词照常返回 0/时间",
            "b=" + stats.IsLearned("banana") + "/" + stats.TestTimes("banana") + "/" + stats.LastStudyTime("banana"));
        Check(!stats.IsLearned("durian") && stats.TestTimes("durian") == 0 &&
              stats.LastStudyTime("durian") == 0, "未学词按未学/0 处理", "");
        Check(!stats.IsLearned(null) && !stats.IsLearned("") &&
              stats.TestTimes(null) == 0 && stats.LastStudyTime("") == 0,
              "null/空词一律按未学处理", "");

        // 快照稳定性：建快照后字典再变，本实例的查询不变。
        dict["durian"] = new FakeEntry();          // 新增
        dict.Remove("apple");                       // 删除
        e1.testTimes = 99;                          // 原地改
        Check(stats.IsLearned("apple") && stats.TestTimes("apple") == 3,
              "快照建立后字典增删改不影响本实例查询（Enforce 内稳定视图）", "");
        Check(!stats.IsLearned("durian"), "快照后新增的词本实例不可见", "");

        // 新实例 = 新快照：看到的是新内容。
        GameLearnedStats stats2 = new GameLearnedStats(dict);
        Check(stats2.IsLearned("durian") && !stats2.IsLearned("apple") &&
              stats2.TestTimes("banana") == 0,
              "新实例重建快照，反映字典现状（每次 Enforce 一个实例的语义）", "");
        Check(stats2.LastStudyTime("cherry") == 0 && !stats2.IsLearned("cherry"),
              "null 条目按未学处理，不抛异常", "");
    }

    private static void CheckHostGenericStrategy()
    {
        string root = Path.Combine(Path.GetTempPath(),
            "wcphost_registry_host_strategy_" + Guid.NewGuid().ToString("N"));
        try
        {
            Directory.CreateDirectory(Path.Combine(root, "xx"));
            string manifest = SyntheticManifest("profile-xx", "xx", "7", 0)
                .Replace("\"Pack.dll\"", "\"$host\"")
                .Replace("\"Pack.Type\"", "\"WcpHost.GenericLanguageStrategy\"");
            File.WriteAllText(Path.Combine(root, "xx", "manifest.json"), manifest);

            BookRegistry synthetic = BookRegistry.Load(root);
            StrategyRegistry strategies = StrategyRegistry.Load(synthetic);
            ILanguageStrategy strategy = strategies.ForProfile("profile-xx");
            Check(synthetic.Errors.Count == 0 && strategies.Errors.Count == 0 &&
                  strategies.LoadedCount == 1,
                  "资源包可复用宿主内置通用策略", "策略=" + strategies.LoadedCount);
            Check(strategy != null && strategy.Language == "xx",
                  "通用策略由 manifest 绑定语言码", strategy == null ? "null" : strategy.Language);
            if (strategy != null)
            {
                Check(strategy.ExtractSentenceKey("hello（你好）") == "hello",
                      "通用策略切除译文尾巴", strategy.ExtractSentenceKey("hello（你好）"));
                string meaning, phonic;
                Check(!strategy.ProvideMeaning("missing", out meaning, out phonic),
                      "通用策略缺资源时 fail-closed", "");
            }
        }
        catch (Exception e)
        {
            Check(false, "通用策略注册回归未抛异常", ExceptionSummary(e));
        }
        finally
        {
            try
            {
                if (Directory.Exists(root)) Directory.Delete(root, true);
            }
            catch (Exception e)
            {
                Console.WriteLine("  WARN  清理通用策略临时目录失败: " + e.Message);
            }
        }
    }

    private static string SyntheticManifest(string id, string language,
                                            string fingerprintTail, int slot)
    {
        return SyntheticManifestWithPrefix(id, language, fingerprintTail, slot, language);
    }

    private static string SyntheticManifestWithPrefix(string id, string language,
                                                      string fingerprintTail, int slot,
                                                      string es3Prefix)
    {
        string fingerprint = new string('0', 63) + fingerprintTail;
        return "{\n" +
            "  \"schema\": 1,\n" +
            "  \"profile_id\": \"" + id + "\",\n" +
            "  \"language\": \"" + language + "\",\n" +
            "  \"display_name\": \"synthetic\",\n" +
            "  \"word_count\": 5,\n" +
            "  \"fingerprint_sha256\": \"" + fingerprint + "\",\n" +
            "  \"observed_slot\": " + slot + ",\n" +
            "  \"es3_prefix\": \"" + es3Prefix + "\",\n" +
            "  \"strategy\": {\"assembly\": \"Pack.dll\", \"type\": \"Pack.Type\"},\n" +
            "  \"resources\": {\n" +
            "    \"books\": [\"book.xlsx\"],\n" +
            "    \"meaning_db\": \"meaning.sqlite\",\n" +
            "    \"sentence_table\": \"sentences.json\",\n" +
            "    \"repair\": \"repair.tsv\",\n" +
            "    \"word_audio\": \"audio/word/\",\n" +
            "    \"sentence_audio\": \"audio/sentence/\"\n" +
            "  }\n" +
            "}";
    }

    private static string ExceptionSummary(Exception e)
    {
        try
        {
            return e.GetType().FullName + ": " + e.Message +
                   (string.IsNullOrEmpty(e.StackTrace) ? "" : " @" + e.StackTrace);
        }
        catch (Exception)
        {
            return e.GetType().FullName;
        }
    }

    private static string StrategyError(ILanguageStrategy strategy)
    {
        try
        {
            System.Reflection.PropertyInfo property = strategy.GetType().GetProperty("LastLoadError");
            if (property == null) return "<none>";
            object value = property.GetValue(strategy, null);
            return value == null ? "<none>" : value.ToString();
        }
        catch (Exception)
        {
            return "<diagnostic-unavailable>";
        }
    }
}
