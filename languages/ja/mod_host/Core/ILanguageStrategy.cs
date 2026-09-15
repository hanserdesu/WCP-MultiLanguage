// WCP Host Core — 语言策略接口
//
// 这是"做不到纯数据语言包"的诚实回应。下列 5 类逻辑是**行为**不是资源，
// 无法数据化；强行塞进配置会变成"配置里写代码"。
// 抽成接口后，每语言只需实现这一个文件级的小类（预估 ~150 行），
// 而不是 fork 整个 2,339 行的词表插件。
//
// 每一项都注明当前 fork 版本里的对应实现位置，便于逐个搬运。
using System;
using System.Collections.Generic;

namespace WcpHost
{
    /// <summary>
    /// 单个语言的行为策略。宿主负责所有与语言无关的机制
    /// （Harmony 补丁点、反射适配、队列接管-还原、作用域门、资源路由），
    /// 语言差异全部收敛到这里。
    /// </summary>
    public interface ILanguageStrategy
    {
        /// <summary>语言码，必须与 manifest.language 一致（ja / fr / ru / de …）。</summary>
        string Language { get; }

        // ── 1. 句子层：从游戏渲染文本里切出"可命名的一段" ──
        //
        // 返回值 = 例句音频文件名的输入（宿主会做 md5）。返回 null = 这句不属于本语言，
        // 宿主不得接管它的 ▶ 按钮。
        //
        // 现有实现: mod_sentence_audio/SentenceAudioMod.cs :: ExtractJa  (第 840 行)
        //           mod_sentence_audio_fr/SentenceAudioFrMod.cs :: ExtractFr (第 764 行)
        //           mod_sentence_audio_ru/SentenceAudioRuMod.cs :: ExtractRu (第 620 行)
        //
        // ⚠️ 这三个谓词就是当前"跨语言隔离"的全部依据（互斥靠文字系统碰巧不同）。
        //    移到这里之后，隔离改由 packs/<lang>/audio/sentence/ 的物理目录保证，
        //    谓词退化为纯粹的"这句该不该给按钮"判断，不再是隔离手段。
        //
        // ⚠️ 已知缺陷: ExtractJa 用 rfind('（') 取最后一个全角左括号切尾，
        //    中文译文含括号时会吃掉字符 → 386 条例句 md5 失配（音频文件在但点不响）。
        //    实现本方法时**必须**修掉，不能原样搬运。
        string ExtractSentenceKey(string renderedText);

        // ── 2. 单词层：题干 / 选项的显示形 ──
        //
        // 现有实现: JpWordListMod.cs 的假名题干 / 汉字选项（LooksJapanese +
        // KanaOf/KanjiOption 三级释义来源）；FR/RU 为原形直出。
        string StemDisplay(string canonicalWord, string meaning);
        string OptionDisplay(string canonicalWord, string meaning);

        // ── 3. 单词音频：题干被改写后，用哪个词形去查音频 ──
        //
        // 现有实现: JpWordListMod.cs :: PrePlayWordAudio / PostPlayWordAudio
        // （假名题干 → 临时换回汉字形取音，播完还原）；FR/RU 原形。
        string AudioLookupForm(string displayedForm, string canonicalWord);

        // ── 4. 查词面板：本地释义 / 注音（宿主自服务，不再查游戏 DB）──
        //
        // 现有实现: JpWordListMod.cs 的 M① （受管词书下改用本书释义，音标位填假名读音）。
        // 目标: 数据从 packs/<lang>/db/meaning.sqlite 读，不再依赖 wcpFullEng.db。
        bool ProvideMeaning(string word, out string meaning, out string phonic);

        // ── 5. 自愈探针词 ──
        //
        // 现有实现（真实值，非编造）:
        //   ja: 歯医者 / 続ける / 工業        (JpWordListMod.cs 第 2100 行)
        //   fr: être / coing / vaguement      (FrWordListMod.cs 第 1914 行)
        //   ru: стол / человек / хорошо / говорить (RuWordListMod.cs 第 1923 行)
        // 同时冗余登记在 manifest.repair_probes，供宿主在没有策略程序集时也能自检。
        IList<string> RepairProbes { get; }
    }

    /// <summary>
    /// 可选的资源绑定扩展。宿主把当前 manifest 解析后的绝对路径注入策略，
    /// 策略不得自行猜测 packs 根目录或拼接其它语言的路径。
    /// </summary>
    public interface IPackBoundStrategy
    {
        void BindPack(StrategyContext context);
    }
}
