// WCP Host — 主线程归因探针
//
// 目的（2026-09-18 第六轮立项 / 第七轮重写）：把"卡顿"拆成"mod 占了多少 / 剩下是谁的"。
//
// ─────────────────────────────────────────────────────────────────────────────
// 第七轮为什么要把这个文件重写（这是一次自我纠错，记在这里避免下次再犯）：
//
// 第六轮的实现只保留「本帧单个最慢操作」= max(所有 scope 的耗时)。而 scope 是
// **嵌套**的：外层 span 恒 ≥ 它内部任何一段，于是那个字段在数学上永远等于
// **最外层**那个标签。实机日志印证了这一点：
//
//   长帧 16224ms — mod 本帧占用 26165.5ms（161.3%） 最深阶段=运行态:Tick
//                                        本帧最慢操作=运行态:Tick 7727.1ms
//   长帧 6720ms  — mod 本帧占用 737.4ms（11.0%）   本帧最慢操作=身份:Evaluate 698.5ms
//
// `运行态:Tick` / `身份:Evaluate` 都是最外层作用域的名字，**没有一次点名到真正的
// 热点**。所谓"最慢操作"其实是"最外层操作"，这个字段在结构上就不可能给出信息。
//
// 第七轮口径改成「按标签聚合」：
//   - 每个标签单独累计 count / totalMs / maxMs（同名标签跨调用累加）；
//   - 窗口行按 **totalMs 降序**输出 Top-N —— 这才是"谁在吃主线程"的答案；
//   - 同时保留单次最大值用于识别偶发尖峰，并显式给出调用次数，因为
//     "1 次 700ms" 和 "350 次 2ms" 要修的地方完全不同，输出里的 `xN` 就是给
//     判读的人分辨这两类用的。
//
// 另一个同类缺陷：原来的"最深阶段"取的是"最后一个 Dispose 的标签"，也就是最外层，
// 同样没有信息量。删掉，不再输出。
// ─────────────────────────────────────────────────────────────────────────────
//
// 成本：Begin 只有一次 GetTimestamp + 一次字典取用；Scope 是 struct，using 不装箱。
// 标签必须是常量字面量 —— 探针绝不成为新的分配源。
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Text;

namespace WcpHost
{
    internal static class PerfProbe
    {
        // 单个 mod 操作超过这个毫秒数才算"值得点名"。
        internal const double SlowOpMs = 8.0;
        // 整帧超过这个毫秒数（≈6.7fps）才算"长帧"，值得单独打一行。
        internal const double LongFrameMs = 150.0;
        // 窗口行最多点名几个标签（按累计耗时降序）。
        //
        // 第九轮（2026-09-18）：4 → 8。4 太小了 —— 第九轮判读实机日志时，Top4 之外
        // 还有 6~7 个标签看不见，而「ES3 批量写(装载)/(提交) 到底有没有跑」正好落在
        // 被截断的那一段，直接把归因堵死了。截断自己的输出等于自废探针。
        //
        // 第十轮（2026-09-18）：8 → 12。给身份判定加细分标签之后，单帧标签数从
        // 10~11 涨到 18+，8 又不够用了 —— 同一个错误（截断自己的输出）不该犯第三次。
        internal const int TopN = 12;

        // ── GC 记账（第十轮新增）────────────────────────────────────────────
        //
        // 「身份:Evaluate 单次 2712ms」这类尖峰，最可能的解释不是"这段代码慢"，而是
        // **span 期间撞上一次 full GC**：PerfProbe 用 Stopwatch 计时，而 GC 的
        // stop-the-world 停顿会 1:1 计进当时活跃的那个 span —— 谁在计时就把账算给谁。
        // 分辨"真慢"与"被 GC 砸中"只有一个办法：把 GC 计数打在同一行。
        //   · 长帧行报「本帧 GC 增量」：若那 2712ms 伴随 gen2+1，它就不是宿主的代码成本。
        //   · 窗口行报「窗口 GC 增量 + 托管堆净变化」：用来判断稳态是否在持续制造垃圾。
        // 成本：三次 GC.CollectionCount 是 O(1)（Mono/IL2CPP 都只是读计数器），
        // 每秒一次；GetTotalMemory 只在窗口行调用。都不进热路径。
        private static int _lastGc0, _lastGc1, _lastGc2;
        private static bool _frameBaseSet;
        private static long _lastMem;
        private static int _winBaseGc0, _winBaseGc1, _winBaseGc2;
        private static long _winBaseMem;
        private static bool _winBaseSet;

        private struct Stat
        {
            internal int Count;
            internal double Total;
            internal double Max;
        }

        private const int MaxDepth = 12;
        private static readonly string[] Stack = new string[MaxDepth];

        private static int _depth;
        private static double _busyMs;
        // 本帧 + 本窗口的按标签聚合。两层都要：长帧行要报"本帧"的分布，
        // 哨兵行要报"这一整个窗口"的分布。
        private static readonly Dictionary<string, Stat> Frame =
            new Dictionary<string, Stat>(StringComparer.Ordinal);
        private static readonly Dictionary<string, Stat> Window =
            new Dictionary<string, Stat>(StringComparer.Ordinal);
        private static int _longFrames;
        private static double _windowBusyMs;

        // ── 快路径命中计数（第十二轮新增）────────────────────────────────────
        //
        // 为什么不能只用 span 记：一条"跳过昂贵计算"的快路径，它**正确时的表现就是
        // 耗时为 0**。而 0ms 的 span 在 Top-N 里没有信息量 —— "命中了快路径"和
        // "这段压根没跑"在耗时上完全一样，但两者要采取的行动相反：前者说明优化生效，
        // 后者说明守卫的判据在真实游戏里从不成立（那要改的是判据，不是算法）。
        //
        // 这条规则的代价是第八轮付过的：那一轮的 ES3 批量写因为一个反射取错接收者而
        // **静默退化成逐键写**，门禁 34 项全绿（它用的是桩 ES3），实机白卡了两轮才被
        // 探针抓到。所以本项目的规矩是：**任何"应该生效"的快路径都必须自己出声。**
        private static readonly Dictionary<string, int> HitCount =
            new Dictionary<string, int>(StringComparer.Ordinal);
        private static readonly Dictionary<string, int> MissCount =
            new Dictionary<string, int>(StringComparer.Ordinal);

        internal static void Hit(string tag) { Bump(HitCount, tag); }
        internal static void Miss(string tag) { Bump(MissCount, tag); }

        private static void Bump(Dictionary<string, int> table, string tag)
        {
            int n;
            table.TryGetValue(tag, out n);
            table[tag] = n + 1;
        }

        // 窗口行摘要：`命中a/共b`。命中率 0% 与缺字段是两回事，缺字段说明这个快路径
        // 一次都没被调用（标签打错了 / 代码没接上），比 0% 更严重。
        private static string HitSummary()
        {
            if (HitCount.Count == 0 && MissCount.Count == 0) return "";
            // 并集排序（StringComparer.Ordinal 保证同一份日志的标签顺序稳定可 diff）。
            List<string> tags = new List<string>();
            foreach (string k in HitCount.Keys) if (!tags.Contains(k)) tags.Add(k);
            foreach (string k in MissCount.Keys) if (!tags.Contains(k)) tags.Add(k);
            tags.Sort(StringComparer.Ordinal);
            StringBuilder sb = new StringBuilder(" | 快路径命中=");
            for (int i = 0; i < tags.Count; i++)
            {
                int h, m;
                HitCount.TryGetValue(tags[i], out h);
                MissCount.TryGetValue(tags[i], out m);
                if (i > 0) sb.Append(" ; ");
                sb.Append(tags[i]).Append(' ');
                if (h + m == 0) sb.Append("未触发");
                else sb.Append(h).Append('/').Append(h + m);
            }
            return sb.ToString();
        }

        private static void ClearCounters()
        {
            HitCount.Clear();
            MissCount.Clear();
        }

        private static double Ms(long deltaTicks)
        {
            return deltaTicks * 1000.0 / Stopwatch.Frequency;
        }

        // 用 using 包住一段 mod 操作：using (PerfProbe.Begin("标签")) { ... }
        internal static Scope Begin(string tag)
        {
            return new Scope(tag);
        }

        internal struct Scope : IDisposable
        {
            private readonly long _start;
            private readonly int _slot;
            private readonly string _tag;

            internal Scope(string tag)
            {
                _tag = tag;
                _start = Stopwatch.GetTimestamp();
                _slot = _depth < MaxDepth ? _depth : MaxDepth - 1;
                if (_depth < MaxDepth)
                {
                    Stack[_slot] = tag;
                    _depth++;
                }
            }

            public void Dispose()
            {
                double ms = Ms(Stopwatch.GetTimestamp() - _start);
                // 弹栈：正常 LIFO 时 _depth == _slot + 1；乱序/溢出时钳到 _slot 兜底。
                if (_depth > _slot) _depth = _slot;
                if (_tag == null) return;
                // 「本帧 mod 占用」只累加**最外层** span，不能把嵌套 span 重复计入。
                // 旧实现对每个 scope 都 += ，于是外层 span 恒 ≥ 内层，叠加后占比可以
                // 超过 100% —— 第九轮实机日志里出现的就是 `152.4%` / `243.9%` 这种
                // 物理上不可能的数字，而那个字段正是用来判断"这帧到底是谁的锅"的。
                // 按标签聚合（Top-N）照旧按每个 span 计，不受影响。
                if (_slot == 0) _busyMs += ms;
                Accumulate(Frame, _tag, ms);
                Accumulate(Window, _tag, ms);
            }
        }

        private static void Accumulate(Dictionary<string, Stat> table, string tag, double ms)
        {
            Stat s;
            if (!table.TryGetValue(tag, out s))
            {
                s = new Stat();
            }
            s.Count++;
            s.Total += ms;
            if (ms > s.Max) s.Max = ms;
            table[tag] = s;
        }

        // 每帧调用一次（哨兵最前面）。返回非 null 时调用方应把该行写进日志。
        internal static string Tick(double frameMs)
        {
            string report = null;
            int g0 = GC.CollectionCount(0);
            int g1 = GC.CollectionCount(1);
            int g2 = GC.CollectionCount(2);
            long mem = 0;
            // 第十二轮修一个口径瑕疵：`_lastGc*` 初值是 0，而它是**进程启动以来**的
            // 累计值 —— 于是本进程第一帧的「GC本帧」实际报的是"启动至今一共回收了
            // 多少次"，实机第一帧出现过 `GC本帧=0:128 1:128 2:128` 这种数字，读的人
            // （我自己）差点把它当成"这一帧里跑了 128 次 GC"。第一次调用只建立基线。
            if (!_frameBaseSet)
            {
                _frameBaseSet = true;
                _lastGc0 = g0; _lastGc1 = g1; _lastGc2 = g2;
                _busyMs = 0;
                Frame.Clear();
                return null;
            }
            if (frameMs >= LongFrameMs)
            {
                _longFrames++;
                mem = GC.GetTotalMemory(false);
                double share = frameMs <= 0 ? 0 : _busyMs * 100.0 / frameMs;
                report = "长帧 " + frameMs.ToString("F0") + "ms — mod 本帧占用 " +
                    _busyMs.ToString("F1") + "ms（" + share.ToString("F1") + "%）" +
                    // 本帧 GC 增量：判断这帧的长是"mod 干的"还是"被 full GC 砸的"。
                    " GC本帧=0:" + (g0 - _lastGc0) + " 1:" + (g1 - _lastGc1) +
                    " 2:" + (g2 - _lastGc2) +
                    " 本帧 Top=" + Describe(Frame, TopN);
            }
            _lastGc0 = g0; _lastGc1 = g1; _lastGc2 = g2;
            if (mem > 0) _lastMem = mem;
            _windowBusyMs += _busyMs;
            _busyMs = 0;
            Frame.Clear();
            return report;
        }

        // 哨兵出窗口行时调用：取走累计值并清零。
        internal static string TakeWindowSummary()
        {
            int g0 = GC.CollectionCount(0);
            int g1 = GC.CollectionCount(1);
            int g2 = GC.CollectionCount(2);
            long mem = GC.GetTotalMemory(false);
            if (!_winBaseSet)
            {
                _winBaseGc0 = g0; _winBaseGc1 = g1; _winBaseGc2 = g2;
                _winBaseMem = mem; _winBaseSet = true;
                ClearCounters();
                return "mod 主线程占用=" + _windowBusyMs.ToString("F1") + "ms/窗口（GC 基线建立）";
            }
            string text = "mod 主线程占用=" + _windowBusyMs.ToString("F1") + "ms/窗口" +
                (_longFrames > 0 ? "，长帧=" + _longFrames + " 次" : "") +
                " | GC窗口=0:" + (g0 - _winBaseGc0) + " 1:" + (g1 - _winBaseGc1) +
                " 2:" + (g2 - _winBaseGc2) +
                " 堆=" + ((_winBaseMem - mem) >= 0 ? "-" : "+") +
                (Math.Abs(_winBaseMem - mem) / (1024L * 1024L)) + "MB" +
                HitSummary() +
                " | 窗口 Top（累计）=" + Describe(Window, TopN);
            _winBaseGc0 = g0; _winBaseGc1 = g1; _winBaseGc2 = g2;
            _winBaseMem = mem;
            _windowBusyMs = 0;
            _longFrames = 0;
            Window.Clear();
            ClearCounters();
            return text;
        }

        // 按"累计耗时"降序取前 n 个标签，写成 `标签 xN=总ms(单次max ms)`。
        private static string Describe(Dictionary<string, Stat> table, int n)
        {
            if (table.Count == 0) return "无 mod 操作";
            List<KeyValuePair<string, Stat>> items =
                new List<KeyValuePair<string, Stat>>(table);
            items.Sort(delegate (KeyValuePair<string, Stat> a, KeyValuePair<string, Stat> b)
            {
                int byTotal = b.Value.Total.CompareTo(a.Value.Total);
                if (byTotal != 0) return byTotal;
                return string.CompareOrdinal(a.Key, b.Key);
            });
            StringBuilder sb = new StringBuilder();
            int take = items.Count < n ? items.Count : n;
            for (int i = 0; i < take; i++)
            {
                if (i > 0) sb.Append(" ; ");
                Stat s = items[i].Value;
                sb.Append(items[i].Key).Append(" x").Append(s.Count)
                  .Append('=').Append(s.Total.ToString("F1")).Append("ms(单次")
                  .Append(s.Max.ToString("F1")).Append("ms)");
            }
            if (items.Count > take) sb.Append(" ; …共").Append(items.Count).Append("个标签");
            return sb.ToString();
        }

        // 诊断：把本帧按标签聚合的结果整体导出（离线 harness 用）。
        internal static string DumpFrame()
        {
            return Describe(Frame, Frame.Count == 0 ? 1 : Frame.Count);
        }

        // 诊断：窗口内某标签出现过没有 / 调用了几次。离线 harness 用来断言
        // "某条路径不再被每秒调用"。
        internal static int WindowCount(string tag)
        {
            Stat s;
            return Window.TryGetValue(tag, out s) ? s.Count : 0;
        }
    }
}
