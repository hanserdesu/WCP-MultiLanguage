// WCP Host — 单词音频镜像的后台执行器
//
// 为什么要有这个文件（2026-09-18 第六轮）：
//   镜像此前是主线程协程，两个结构性缺陷都来自"跑在主线程"：
//     1. 它和游戏的加载/切场景抢同一帧。切词库本来就是"卸载 5 千个资源 +
//        重建 322 行列表 + 存档写盘"的重活，再叠上目录枚举与数千次文件复制，
//        最坏帧被推到 10 秒量级（Player.log 实测 14615ms）。
//     2. 协程生命周期绑 MonoBehaviour/场景。切库时 StopCoroutine 会让上一轮
//        "有开始没完成"，stamp 写不上 → 每次切库全量重扫 7.8 万个目录项。
//   移到后台线程后两条同时消失：不占帧、不怕场景切换、必然跑完。
//
// 设计要点：
//   - 线程只做 IO 与纯计算。所有 Unity API（Application.persistentDataPath 等）
//     都由主线程算好、以字符串传进来 —— Unity 的 API 只在主线程合法。
//   - 日志不直接写：投进队列，由主线程每帧 drain 后统一输出。这样既不赌
//     BepInEx logger 的线程安全，也不会让后台线程在 Unity 日志锁上被卡住。
//   - 线程池退化为"空则退出"：队列空时线程自己结束并把句柄置空，Request 里
//     在同一把锁下重新起线程 —— 没有"线程活着但队列空"的忙等。
//   - 优先级 BelowNormal + 启动前静默期：不跟切库的加载高峰抢磁盘。
using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Threading;

namespace WcpHost
{
    internal static class MirrorWorker
    {
        // 静默期：切词库瞬间游戏自己在猛读盘，镜像晚几秒开始，用户体感无差
        // （单词音频是"下一次查词"才用到的），但磁盘队列会干净很多。
        private const int StartDelayMs = 2000;

        private sealed class Job
        {
            internal string PackId;
            internal string Source;
            internal string Target;
        }

        private static readonly object Gate = new object();
        private static readonly List<Job> Queue = new List<Job>();
        private static readonly ConcurrentQueue<string> Pending =
            new ConcurrentQueue<string>();
        private static Thread _worker;
        private static int _completed;

        internal static int CompletedCount { get { return _completed; } }

        // 主线程调用。同一 (pack, 源目录) 已在队列里就不重复投递。
        internal static void Request(string packId, string source, string target)
        {
            if (string.IsNullOrEmpty(source) || string.IsNullOrEmpty(target)) return;
            lock (Gate)
            {
                for (int i = 0; i < Queue.Count; i++)
                    if (string.Equals(Queue[i].PackId, packId, StringComparison.Ordinal) &&
                        string.Equals(Queue[i].Source, source, StringComparison.OrdinalIgnoreCase))
                        return;

                Job job = new Job();
                job.PackId = packId;
                job.Source = source;
                job.Target = target;
                Queue.Add(job);

                if (_worker == null)
                {
                    Thread t = new Thread(Loop);
                    t.IsBackground = true;
                    t.Name = "WcpMirror";
                    try { t.Priority = ThreadPriority.BelowNormal; } catch { }
                    _worker = t;
                    t.Start();
                }
            }
        }

        private static void Loop()
        {
            // 静默期只在本线程第一次取活前生效一次：线程活着就说明刚发生过切库。
            try { Thread.Sleep(StartDelayMs); } catch { }
            while (true)
            {
                Job job;
                lock (Gate)
                {
                    if (Queue.Count == 0)
                    {
                        _worker = null;   // 句柄置空与 Request 的判空共用一把锁 → 无竞态
                        return;
                    }
                    job = Queue[0];
                    Queue.RemoveAt(0);
                }
                Run(job);
            }
        }

        private static void Run(Job job)
        {
            try
            {
                WordAudioCompat.MirrorStats stats =
                    WordAudioCompat.MirrorPack(job.Source, job.Target);
                if (stats == null)
                {
                    Pending.Enqueue("单词音频兼容层跳过：源目录为空或不可读（pack=" +
                        job.PackId + "）");
                    return;
                }
                if (stats.Failed == 0)
                    WordAudioCompat.WriteStamp(WordAudioCompat.StampPath(job.Target),
                        WordAudioCompat.StampPrefix(job.PackId, job.Source) +
                        "files=" + stats.Source);
                // 真写进去了文件 → 其它 pack 的"已完成"记录不再可信（目标目录共用）。
                if (stats.Copied > 0)
                    WordAudioCompat.DropOtherPacks(
                        WordAudioCompat.StampPath(job.Target), job.PackId);

                Pending.Enqueue("单词音频兼容层完成（后台线程）：pack=" + job.PackId +
                    " 复制=" + stats.Copied + " 已存在=" + stats.Skipped +
                    " 忽略(保留设备名)=" + stats.Ignored + " 失败=" + stats.Failed +
                    " 源=" + stats.Source + " 目标库=" + stats.Target +
                    (stats.StaleTemp > 0 ? " 清理半截临时=" + stats.StaleTemp : "") +
                    (stats.Failed == 0 ? "（已记录，后续会话跳过）" : "（下次会话重试）"));
                // 耗时口径：全部在后台线程，不占任何一帧，所以这里只报 IO 真实
                // 成本，不再有"帧数"这一列（旧口径的墙钟含等下一帧的时间）。
                Pending.Enqueue("镜像耗时（后台线程）pack=" + job.PackId +
                    " 源枚举=" + Ms(stats.SourceMs) + " 目标枚举=" + Ms(stats.TargetMs) +
                    " 比对=" + Ms(stats.CompareMs) + " 复制=" + Ms(stats.CopyMs));
            }
            catch (Exception e)
            {
                // 线程绝不能因为异常而死：死了就再也不会有人补音频，且没有任何迹象。
                Pending.Enqueue("单词音频兼容层线程异常（已吞，不影响游戏）：" +
                    e.GetType().Name + ": " + e.Message);
            }
            finally
            {
                Interlocked.Increment(ref _completed);
            }
        }

        private static string Ms(double value)
        {
            return value.ToString("F0") + "ms";
        }

        // 主线程每帧调用；返回写进 sink 的行数。
        internal static int DrainInto(List<string> sink)
        {
            if (sink == null) return 0;
            int n = 0;
            string line;
            while (Pending.TryDequeue(out line))
            {
                if (line == null) continue;
                sink.Add(line);
                n++;
            }
            return n;
        }
    }
}
