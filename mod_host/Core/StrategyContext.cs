// WCP Host Core — 策略资源上下文
using System;
using System.Collections.Generic;

namespace WcpHost
{
    /// <summary>
    /// 当前语言包的、已经过 manifest 越界校验的资源路径。
    /// 公开给 pack 策略使用，但只能由宿主从 LanguageManifest 构造。
    /// </summary>
    public sealed class StrategyContext
    {
        public string ProfileId { get; private set; }
        public string Language { get; private set; }
        public string PackRoot { get; private set; }
        public string MeaningDbPath { get; private set; }
        public string SentenceTablePath { get; private set; }
        public string RepairPath { get; private set; }
        public string WordAudioDir { get; private set; }
        public string SentenceAudioDir { get; private set; }
        public IList<string> RepairProbes { get; private set; }

        internal StrategyContext(LanguageManifest manifest)
        {
            if (manifest == null) throw new ArgumentNullException("manifest");
            ProfileId = manifest.Profile.Id;
            Language = manifest.Profile.Language;
            PackRoot = manifest.PackRoot;
            MeaningDbPath = manifest.Resolve(manifest.MeaningDb);
            SentenceTablePath = manifest.Resolve(manifest.SentenceTable);
            RepairPath = manifest.Resolve(manifest.Repair);
            WordAudioDir = manifest.Resolve(manifest.WordAudioDir);
            SentenceAudioDir = manifest.Resolve(manifest.SentenceAudioDir);
            RepairProbes = manifest.RepairProbes == null
                ? new List<string>().AsReadOnly()
                : new List<string>(manifest.RepairProbes).AsReadOnly();
        }
    }
}
