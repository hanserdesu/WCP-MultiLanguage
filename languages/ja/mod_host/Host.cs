// WCP Host — 统一接入宿主（阶段 2，v0.3.0）
//
// 职责边界（这是整个重构的核心约定）:
//   宿主负责机制: 读语言包清单 / 认身份 / 作用域门 / 资源路由 / 日后接管-还原。
//   语言包负责数据: packs/<lang>/{manifest.json, books, db, audio}。
//   语言策略负责行为: ILanguageStrategy（每语言一个 ~150 行的类）。
//
// 当前版本在身份门通过后接管固定的游戏补丁点；语言差异只来自
// ILanguageStrategy，队列和 UI 状态由宿主统一还原。
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using BepInEx;
using BepInEx.Configuration;
using BepInEx.Logging;
using HarmonyLib;
using UnityEngine;

namespace WcpHost
{
    [BepInPlugin("dev.hanserdesu.wcphost", "WCP Host", "0.3.0")]
    public class WcpHostPlugin : BaseUnityPlugin
    {
        internal static ManualLogSource Log;
        private static WcpHostPlugin _instance;

        private ConfigEntry<bool> _enabled;
        private ConfigEntry<string> _packsRootOverride;

        private ResourceRouter _router;
        private BookRegistry _registry;
        private StrategyRegistry _strategies;
        private HostRuntime _runtime;
        private Harmony _featureHarmony;
        private bool _featuresInstalled;
        private float _nextProbe;
        private string _lastReported = "";
        private string _markerLangs = null;
        private const float ProbeInterval = 1.0f;

        internal static WcpHostPlugin Instance { get { return _instance; } }
        internal ResourceRouter Router { get { return _router; } }
        internal BookRegistry Registry { get { return _registry; } }
        internal HostRuntime Runtime { get { return _runtime; } }
        // 补丁协调器从这里取得当前策略；身份层未激活时始终为 null。
        internal ILanguageStrategy ActiveStrategy
        {
            get
            {
                return _runtime == null ? null : _runtime.ActiveStrategy;
            }
        }

        private void Awake()
        {
            _instance = this;
            Log = Logger;

            _enabled = Config.Bind("General", "Enabled", true,
                "总开关。关闭时宿主只加载注册表、不做任何判定（补丁接入后=完全停用）。");
            _packsRootOverride = Config.Bind("General", "PacksRoot", "",
                "语言包根目录。留空 = <persistentDataPath 的父目录>/packs，" +
                "即 %USERPROFILE%\\AppData\\LocalLow\\WCP\\packs");

            try
            {
                string root = ResolvePacksRoot();
                _registry = BookRegistry.Load(root);
                _router = new ResourceRouter(_registry);
                _strategies = StrategyRegistry.Load(_registry);
                _runtime = new HostRuntime(this, _registry, _router, _strategies);
                ReportRegistry(root);
                _featureHarmony = new Harmony("dev.hanserdesu.wcphost.features");
                Log.LogInfo("WcpHost: 身份轮询已启用（兼容旧选书补丁），行为接线等待身份门通过");
            }
            catch (Exception e)
            {
                Log.LogError("WcpHost: 加载语言包失败，宿主进入禁用状态: " + e);
                _enabled.Value = false;
            }
        }

        private string ResolvePacksRoot()
        {
            string custom = _packsRootOverride.Value;
            if (!string.IsNullOrEmpty(custom)) return custom;
            string pdp = Application.persistentDataPath;      // ...\AppData\LocalLow\WCP\wcp
            string parent = Path.GetDirectoryName(pdp);       // ...\AppData\LocalLow\WCP
            return Path.Combine(parent, "packs");
        }

        // 语言资源隔离的运行时凭证: 只登记"宿主确实成功接管"的语言。
        //
        // 旧词表插件 (JpWordListMod / FrWordListMod …) 读到自己的语言在列时整场不打补丁,
        // 运行时补丁因此只剩宿主一个所有者 —— 这是"俄语切日语后还出俄语"的根因修复:
        // 两个插件争抢同一批补丁时"后写者胜", 上一本书的词会串进新书。
        // 注册表为空/宿主停用时删除登记, 旧插件继续按旧模式工作。
        private void RefreshManagedMarker()
        {
            try
            {
                List<string> langs = new List<string>();
                List<string> notReady = new List<string>();
                if (_enabled.Value && _registry != null)
                {
                    for (int i = 0; i < _registry.Manifests.Count; i++)
                    {
                        LanguageManifest m = _registry.Manifests[i];
                        string code = m.Profile.Language;
                        string missing;
                        // 资源没装全的包不登记: 旧词表插件继续按旧模式兜底, 不会出现
                        // "宿主说接管了、实际没有释义库"的空档。
                        if (!m.ResourcesReady(out missing))
                        {
                            notReady.Add(code + " 缺 " + missing);
                            continue;
                        }
                        if (!string.IsNullOrEmpty(code) && !langs.Contains(code)) langs.Add(code);
                    }
                }
                string joined = string.Join(",", langs.ToArray()) + "|" +
                                string.Join(",", notReady.ToArray());
                if (joined == _markerLangs) return;
                string dir = Paths.ConfigPath;
                if (string.IsNullOrEmpty(dir)) return;
                string file = Path.Combine(dir, "WcpHost.managed.txt");
                if (langs.Count == 0)
                {
                    if (File.Exists(file)) File.Delete(file);
                }
                else
                {
                    File.WriteAllLines(file, langs.ToArray());
                }
                _markerLangs = joined;
                Log.LogInfo("WcpHost: 受管语言登记 = [" + string.Join(",", langs.ToArray()) +
                            "] -> " + file);
                if (notReady.Count > 0)
                    Log.LogWarning("WcpHost: 语言包资源未就绪, 本次不接管（旧插件继续兜底）: " +
                                   string.Join("; ", notReady.ToArray()));
            }
            catch (Exception e)
            {
                Log.LogWarning("WcpHost: 受管语言登记失败（旧词表插件继续按旧模式打补丁）: " + e.Message);
            }
        }

        private void ReportRegistry(string root)
        {
            Log.LogInfo("WcpHost: packs 根 = " + root);
            Log.LogInfo("WcpHost: 加载到 " + _registry.Manifests.Count + " 个语言包");
            for (int i = 0; i < _registry.Manifests.Count; i++)
            {
                LanguageManifest m = _registry.Manifests[i];
                Log.LogInfo(string.Format(
                    "WcpHost:   [{0}] {1} {2} 词={3} 槽={4} 指纹={5}",
                    m.Profile.Language, m.Profile.Id, m.Profile.DisplayName,
                    m.Profile.WordCount, m.Profile.ObservedSlot,
                    m.Profile.Fingerprint.Substring(0, 16)));
            }
            string detail;
            bool ok = _registry.SlotBudgetOk(out detail);
            Log.LogInfo("WcpHost: 槽位预算 " + detail + (ok ? " — 通过" : " — 超限（游戏硬上限 4）"));
            Log.LogInfo("WcpHost: 策略装载 " + _strategies.LoadedCount + "/" +
                        _registry.Manifests.Count + "（缺失策略时仅保留身份层）");
            for (int i = 0; i < _registry.Errors.Count; i++)
                Log.LogWarning("WcpHost: 语言包加载告警: " + _registry.Errors[i]);
            for (int i = 0; i < _registry.Warnings.Count; i++)
                Log.LogWarning("WcpHost: 语言包提示: " + _registry.Warnings[i]);
            for (int i = 0; i < _strategies.Errors.Count; i++)
                Log.LogWarning("WcpHost: 策略加载告警: " + _strategies.Errors[i]);
        }

        private void Update()
        {
            RefreshManagedMarker();
            if (!_enabled.Value || _router == null)
            {
                try
                {
                    if (_runtime != null) _runtime.OnDisabled();
                }
                finally
                {
                    RemoveFeaturePatches();
                }
                return;
            }
            if (Time.realtimeSinceStartup < _nextProbe) return;
            _nextProbe = Time.realtimeSinceStartup + ProbeInterval;

            string state;
            try
            {
                state = Evaluate();
                SyncFeaturePatches();
                if (_runtime != null) _runtime.Tick();
            }
            catch (Exception e)
            {
                // fail-closed: 判定出错一律取消激活，绝不猜测
                _router.SetActive(null);
                if (_runtime != null) _runtime.SetInactive();
                RemoveFeaturePatches();
                state = "ERR " + e.GetType().Name + ": " + e.Message;
            }
            if (state != _lastReported)
            {
                _lastReported = state;
                Log.LogInfo("WcpHost: " + state);
            }
        }

        // 场景边界的强制校正: 玩家切书后 1 秒内的场景切换（战斗/测试/学习）
        // 不能再读到上一门语言的队列，所以这里先按游戏当前状态重判身份，再执行隔离。
        internal void EnforceNowForScene()
        {
            if (_enabled == null || !_enabled.Value || _router == null) return;
            try
            {
                Evaluate();
            }
            catch (Exception e)
            {
                Log.LogWarning("WcpHost: 场景身份重判失败: " + e.Message);
            }
            if (_runtime != null) _runtime.EnforceNow();
        }

        // 身份判定：内存词表 / 内存书名 / 落盘书名 / 选中槽位词表四者一致，且指纹命中注册表，才激活。
        // 任一环节读不到或对不上 → 返回"未激活"。这条门是从现有插件的 fail-closed 门搬来的。
        private string Evaluate()
        {
            object rawList = GameAdapter.StaticField("MyParameters", "ChosenBook_List");
            string memName = GameAdapter.StaticField("MyParameters", "ChosenBook_Para") as string;
            IList<string> words = GameAdapter.ToWordList(rawList);
            string diskName = GameAdapter.DiskBookName();

            if (words == null || words.Count == 0)
            {
                if (_runtime != null) _runtime.SetInactive();
                else _router.SetActive(null);
                return "未激活 · 内存词表为空";
            }
            if (string.IsNullOrEmpty(memName))
            {
                if (_runtime != null) _runtime.SetInactive();
                else _router.SetActive(null);
                return "未激活 · 内存书名为空";
            }
            if (string.IsNullOrEmpty(diskName))
            {
                if (_runtime != null) _runtime.SetInactive();
                else _router.SetActive(null);
                return "未激活 · 落盘书名读不到（读档中？）";
            }
            if (diskName != memName)
            {
                if (_runtime != null) _runtime.SetInactive();
                else _router.SetActive(null);
                return "未激活 · 内存书名(" + memName + ") ≠ 落盘书名(" + diskName + ") — 正在切书";
            }

            int slot = GameAdapter.SlotOfBookName(memName);
            if (slot <= 0)
            {
                if (_runtime != null) _runtime.SetInactive();
                else _router.SetActive(null);
                return "未激活 · 书名不是受支持的自定义槽位: " + memName;
            }

            BookProfile p = _registry.Match(words);
            if (p == null)
            {
                if (_runtime != null) _runtime.SetInactive();
                else _router.SetActive(null);
                return "未激活 · 词表 " + words.Count + " 条未命中任何语言包 — 非受管词书";
            }

            IList<string> slotWords = GameAdapter.SlotWords(slot);
            BookProfile slotProfile = _registry.Match(slotWords);
            if (slotProfile == null || slotProfile.Id != p.Id)
            {
                if (_runtime != null) _runtime.SetInactive();
                else _router.SetActive(null);
                return "未激活 · 内存词表与持久化槽位词表指纹不一致 — 正在读档/切书";
            }

            LanguageManifest manifest = _registry.ByProfileId(p.Id);
            if (manifest == null)
            {
                if (_runtime != null) _runtime.SetInactive();
                else _router.SetActive(null);
                return "未激活 · 注册表没有 profile: " + p.Id;
            }

            if (_runtime != null) _runtime.SetIdentity(manifest, words);
            else _router.SetActive(p.Id);

            if (_router.ActiveProfileId != p.Id)
            {
                _router.SetActive(p.Id);
                return "已激活 · " + p.Language + " / " + p.Id +
                       "（" + words.Count + " 词，槽 " + p.ObservedSlot + "）";
            }
            return "已激活 · " + p.Language + " / " + p.Id +
                   "（" + words.Count + " 词，槽 " + slot +
                   (ActiveStrategy == null ? "，策略缺失" : "，策略已载入") + "）";
        }

        private void SyncFeaturePatches()
        {
            // A manifest without its strategy is an identity-only pack.  Do
            // not install behavior hooks that cannot be implemented safely.
            bool shouldInstall = _runtime != null && _runtime.IsActive &&
                                 ActiveStrategy != null;
            if (shouldInstall && !_featuresInstalled)
            {
                HostPatches.InstallFeatures(_featureHarmony);
                _featuresInstalled = true;
                Log.LogInfo("WcpHost: 语言策略已确认，行为 Harmony 接线已安装");
            }
            else if (!shouldInstall && _featuresInstalled)
            {
                RemoveFeaturePatches();
            }
        }

        private void RemoveFeaturePatches()
        {
            if (!_featuresInstalled) return;
            try
            {
                if (_featureHarmony != null) _featureHarmony.UnpatchSelf();
            }
            finally
            {
                _featuresInstalled = false;
                if (Log != null) Log.LogInfo("WcpHost: 行为 Harmony 接线已移除");
            }
        }

        private void OnDestroy()
        {
            try
            {
                if (_runtime != null) _runtime.OnDisabled();
                RemoveFeaturePatches();
            }
            catch (Exception) { }
            if (_instance == this) _instance = null;
        }
    }
}
