// WCP Host — 20 槽 store 的服务边界检查（P1-4）。
//
// 语义：指纹命中注册表只证明"这是本 mod 发布过的词书"，不证明"用户仍然
// 要它被服务"。服务范围以 CustomSlotsMod 落盘的 20 槽 store
// （WcpCustomSlots.json）为准：
//   - 托管播种行（安装器 slot_manifest 种子，owner=mod, managed=true）→ 在服务范围；
//   - 原生镜像行（owner=external, nativeSlot>0）→ 在服务范围（存量用户兼容）；
//   - 行被用户"移除"（清空复位）或从未登记 → 不在服务范围。
// store 文件不存在 = CustomSlotsMod 未安装/未运行过（纯安装器时代的部署）→
// 按兼容回退放行，保持旧指纹语义（不阻断存量用户）。
// store 存在但一条登记行都没有（20 行全是占位）= 尚未播种 → 同样按兼容回退
// 放行：空表表达不了"撤销服务"语义，fail-closed 只会把装好的词书一起挡掉。
// store 存在但解析失败 = 损坏 → fail-closed，等 CustomSlotsMod 下次保存自愈。
//
// 身份判定与注册表同源：对 store 行的 words 快照计算与 BookRegistry.FingerprintOf
// 相同的指纹，按 mtime 缓存解析结果，避免 1 秒轮询反复读 400KB 文件。
using System;
using System.Collections.Generic;
using System.IO;

namespace WcpHost
{
    internal sealed class SlotOwnership
    {
        private readonly string _storePath;
        private bool _loggedMissing;
        private bool _loggedCorrupt;
        private bool _loggedEmpty;

        // 解析缓存：mtime 未变时直接复用上一轮结论。
        private DateTime _cacheMtimeUtc;
        private bool _cacheValid;
        private readonly List<string> _servedFingerprints = new List<string>();
        private StoreStatus _cacheStatus = StoreStatus.NotPresent;

        private enum StoreStatus { NotPresent, Corrupt, Ok, Empty }

        internal SlotOwnership(string storePath)
        {
            _storePath = storePath;
        }

        /// <summary>
        /// 该指纹的词书是否在 20 槽服务范围内。reason 仅在返回 false 时有意义。
        /// </summary>
        internal bool IsServed(string fingerprint, out string reason)
        {
            reason = null;
            if (string.IsNullOrEmpty(fingerprint)) return false;

            RefreshCache();
            switch (_cacheStatus)
            {
                case StoreStatus.NotPresent:
                    // 兼容回退：没装 CustomSlotsMod（或它还没跑过第一次保存）的
                    // 环境没有 store。保持安装器时代的行为，不做更强约束。
                    return true;
                case StoreStatus.Empty:
                    // store 已落盘但一条登记行都没有（20 行全是占位：既非托管播种
                    // 行也非原生镜像行）。这是"还没播种"的状态，不是"用户撤销了
                    // 服务范围"——空表无法表达撤销语义，所以按兼容回退放行。
                    // （2026-09-17 实机：新装用户 store 只有占位行，fail-closed 会把
                    // 唯一装好的 ja 词书一起挡在门外 → 宿主完全不接管。）
                    return true;
                case StoreStatus.Corrupt:
                    reason = "20 槽存档不可读（损坏）— 服务边界 fail-closed，等 CustomSlotsMod 自愈";
                    return false;
            }

            for (int i = 0; i < _servedFingerprints.Count; i++)
                if (_servedFingerprints[i] == fingerprint) return true;

            reason = "词书不在 20 槽服务范围（从未登记为托管行/原生镜像行，或已被移除）";
            return false;
        }

        private void RefreshCache()
        {
            DateTime mtime;
            try
            {
                if (!File.Exists(_storePath))
                {
                    if (!_loggedMissing)
                    {
                        HostLog.Info("WcpHost: 槽位存档不存在（CustomSlotsMod 未运行过）— 按兼容回退放行，不启用槽位归属约束");
                        _loggedMissing = true;
                    }
                    _cacheStatus = StoreStatus.NotPresent;
                    _cacheValid = true;
                    return;
                }
                mtime = File.GetLastWriteTimeUtc(_storePath);
            }
            catch (Exception)
            {
                // 文件系统读失败：按损坏处理（fail-closed），下一轮重试。
                _cacheStatus = StoreStatus.Corrupt;
                _cacheValid = true;
                return;
            }

            if (_cacheValid && mtime == _cacheMtimeUtc &&
                (_cacheStatus == StoreStatus.Ok || _cacheStatus == StoreStatus.Empty)) return;
            if (_cacheValid && _cacheStatus != StoreStatus.Ok && _cacheStatus != StoreStatus.NotPresent &&
                _cacheStatus != StoreStatus.Empty)
            {
                // 损坏态每个探针周期都重试读取（自愈后立即恢复）。
            }

            _cacheMtimeUtc = mtime;
            _cacheValid = true;
            _servedFingerprints.Clear();

            string raw;
            try { raw = File.ReadAllText(_storePath); }
            catch (Exception e)
            {
                LogCorruptOnce("读取失败: " + e.Message);
                _cacheStatus = StoreStatus.Corrupt;
                return;
            }

            object parsed;
            try { parsed = Json.Parse(raw); }
            catch (Exception)
            {
                LogCorruptOnce("JSON 解析失败");
                _cacheStatus = StoreStatus.Corrupt;
                return;
            }

            Dictionary<string, object> root = parsed as Dictionary<string, object>;
            List<object> rows = null;
            if (root != null)
            {
                object slots;
                if (root.TryGetValue("slots", out slots)) rows = slots as List<object>;
            }
            if (rows == null)
            {
                LogCorruptOnce("缺少 slots 数组");
                _cacheStatus = StoreStatus.Corrupt;
                return;
            }

            for (int i = 0; i < rows.Count; i++)
            {
                Dictionary<string, object> row = rows[i] as Dictionary<string, object>;
                if (row == null) continue;

                bool managed = Json.Bool(row, "managed", false);
                int nativeSlot = Json.Int(row, "nativeSlot", 0);
                if (!managed && nativeSlot <= 0) continue;

                List<string> words = Json.StrList(row, "words");
                if (words == null || words.Count < BookPool.MinPlayable) continue;

                try { _servedFingerprints.Add(BookRegistry.FingerprintOf(words)); }
                catch (Exception) { /* 单行异常不拖垮整表 */ }
            }

            if (_servedFingerprints.Count == 0)
            {
                if (!_loggedEmpty)
                {
                    HostLog.Info("WcpHost: 槽位存档存在但无登记行（尚未播种）— 按兼容回退放行，不启用槽位归属约束");
                    _loggedEmpty = true;
                }
                _cacheStatus = StoreStatus.Empty;
                return;
            }

            _cacheStatus = StoreStatus.Ok;
        }

        private void LogCorruptOnce(string detail)
        {
            if (_loggedCorrupt) return;
            _loggedCorrupt = true;
            HostLog.Warn("WcpHost: 槽位存档不可读（" + detail + "）— 槽位归属判定 fail-closed，待 CustomSlotsMod 重写后自动恢复");
        }
    }

    /// <summary>
    /// 极薄的日志门面：离线 harness 编译宿主 DLL 时没有 BepInEx Logger，
    /// 这里只走 Console，宿主进程里由 Host 在 Awake 注入真实 Logger。
    /// </summary>
    internal static class HostLog
    {
        internal static Action<string> InfoSink;
        internal static Action<string> WarnSink;

        internal static void Info(string message)
        {
            Action<string> sink = InfoSink;
            if (sink != null) sink(message); else Console.WriteLine(message);
        }

        internal static void Warn(string message)
        {
            Action<string> sink = WarnSink;
            if (sink != null) sink(message); else Console.WriteLine(message);
        }
    }
}
