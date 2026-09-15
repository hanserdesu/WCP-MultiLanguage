// WCP Host — manifest 驱动的语言策略装载
//
// 策略是阶段 2 的代码边界：宿主只按 manifest 指定的 pack 内程序集加载，
// 不在宿主里写任何语言名称或语言专属分支。程序集缺失、类型不匹配、语言码
// 不一致时只拒绝该 pack 的策略，不影响其它 pack，也不猜测身份。
using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;

namespace WcpHost
{
    internal sealed class StrategyRegistry
    {
        private readonly Dictionary<string, ILanguageStrategy> _byProfileId =
            new Dictionary<string, ILanguageStrategy>(StringComparer.Ordinal);
        private readonly List<string> _errors = new List<string>();

        internal IList<string> Errors { get { return _errors; } }
        internal int LoadedCount { get { return _byProfileId.Count; } }

        internal static StrategyRegistry Load(BookRegistry registry)
        {
            if (registry == null) throw new ArgumentNullException("registry");
            StrategyRegistry result = new StrategyRegistry();
            for (int i = 0; i < registry.Manifests.Count; i++)
            {
                LanguageManifest manifest = registry.Manifests[i];
                result.LoadOne(manifest);
            }
            return result;
        }

        internal ILanguageStrategy ForProfile(string profileId)
        {
            if (string.IsNullOrEmpty(profileId)) return null;
            ILanguageStrategy value;
            return _byProfileId.TryGetValue(profileId, out value) ? value : null;
        }

        private void LoadOne(LanguageManifest manifest)
        {
            string id = manifest.Profile.Id;
            Assembly assembly = null;
            string path = manifest.Resolve(manifest.StrategyAssembly);
            if (string.Equals(manifest.StrategyAssembly, "$host", StringComparison.Ordinal))
            {
                assembly = typeof(StrategyRegistry).Assembly;
            }
            else if (string.IsNullOrEmpty(path) || !File.Exists(path))
            {
                _errors.Add(id + ": 策略程序集不存在（当前仍可使用身份层）: " +
                            manifest.StrategyAssembly);
                return;
            }

            try
            {
                if (assembly == null) assembly = Assembly.LoadFrom(path);
                Type type = assembly.GetType(manifest.StrategyType, false, false);
                if (type == null)
                {
                    _errors.Add(id + ": 找不到策略类型 " + manifest.StrategyType);
                    return;
                }
                if (!typeof(ILanguageStrategy).IsAssignableFrom(type))
                {
                    _errors.Add(id + ": 策略类型未实现 ILanguageStrategy: " + manifest.StrategyType);
                    return;
                }
                ILanguageStrategy strategy = Activator.CreateInstance(type) as ILanguageStrategy;
                if (strategy == null)
                {
                    _errors.Add(id + ": 策略实例化失败: " + manifest.StrategyType);
                    return;
                }
                IPackBoundStrategy bound = strategy as IPackBoundStrategy;
                if (bound != null)
                    bound.BindPack(new StrategyContext(manifest));
                if (!string.Equals(strategy.Language, manifest.Profile.Language,
                                   StringComparison.Ordinal))
                {
                    _errors.Add(id + ": 策略语言码不一致（manifest=" +
                                manifest.Profile.Language + ", strategy=" +
                                strategy.Language + ")");
                    return;
                }
                _byProfileId[id] = strategy;
            }
            catch (Exception e)
            {
                _errors.Add(id + ": 策略加载失败 " + e.GetType().Name + ": " + e.Message);
            }
        }
    }
}
