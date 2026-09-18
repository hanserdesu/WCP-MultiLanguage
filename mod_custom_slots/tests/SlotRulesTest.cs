// 把 20 条逻辑槽的规则表拿真实模型跑一遍：不依赖 Unity，也不依赖任何语言包。
using System;
using WcpCustomSlots;

internal static class SlotRulesTest
{
    private static int failures;
    private static void Check(bool value, string label)
    {
        Console.WriteLine((value ? "PASS " : "FAIL ") + label);
        if (!value) failures++;
    }

    private static SlotRecord Managed(int nativeSlot, int wordCount)
    {
        SlotRecord record = SlotRules.Empty(1);
        record.id = "fr";
        record.name = "法语词库(猫条版)";
        record.language = "fr";
        record.owner = "mod";
        record.managed = true;
        record.nativeSlot = nativeSlot;
        string[] words = new string[wordCount];
        for (int i = 0; i < wordCount; i++) words[i] = "w" + i;
        record.words = words;
        return record;
    }

    private static int Main()
    {
        // ── 1) 新建状态就是 20 条逻辑槽 ──
        SlotState fresh = SlotRules.NewState();
        Check(fresh.slots.Length == SlotRules.MaxSlots && SlotRules.MaxSlots == 20,
            "新建状态 = 20 条逻辑槽");
        bool numbered = true;
        bool allExternal = true;
        for (int i = 0; i < fresh.slots.Length; i++)
        {
            if (fresh.slots[i].number != i + 1) numbered = false;
            if (fresh.slots[i].managed || fresh.slots[i].owner != "external") allExternal = false;
        }
        Check(numbered, "逻辑槽编号 1..20");
        Check(allExternal, "空槽默认属于外部词书，不算托管");

        // ── 2) 旧存档（3 条）补齐到 20 条且保留原数据 ──
        SlotState legacy = new SlotState();
        legacy.schema = 0;
        legacy.selected = 2;
        legacy.slots = new SlotRecord[] { Managed(1, 8), null, SlotRules.Empty(3) };
        legacy.slots[2].id = "external-book";
        legacy.slots[2].owner = "external";
        SlotRules.Normalize(legacy);
        Check(legacy.slots.Length == 20, "旧存档补齐到 20 条");
        Check(legacy.slots[0].id == "fr" && legacy.slots[0].words.Length == 8 &&
              legacy.slots[2].id == "external-book", "补齐时保留原有槽位数据");
        Check(legacy.slots[1] != null && legacy.slots[19].number == 20,
            "空位补成空记录并重新编号");

        // ── 3) selected 越界修正 ──
        SlotState bad = SlotRules.NewState();
        bad.selected = 25;
        SlotRules.Normalize(bad);
        Check(bad.selected == 0, "selected 越界（25）归零");
        bad.selected = -4;
        SlotRules.Normalize(bad);
        Check(bad.selected == 0, "selected 越界（-4）归零");
        bad.selected = 7;
        SlotRules.Normalize(bad);
        Check(bad.selected == 7, "selected 合法值保留");
        SlotRules.Normalize(null);
        Check(true, "Normalize(null) 不抛异常");

        // ── 4) 可玩门槛与托管判定 ──
        Check(!SlotRules.HasPlayableWords(Managed(1, 4)) &&
              SlotRules.HasPlayableWords(Managed(1, 5)), "少于 5 词的槽不算可玩");
        SlotRecord foreign = Managed(1, 9);
        foreign.managed = false;
        Check(!SlotRules.IsManaged(foreign), "外部词书（managed=false）不算宿主托管");
        Check(SlotRules.IsManaged(Managed(3, 9)), "托管槽 + 足量词 = 宿主托管");

        // ── 5) 原生槽边界：外部词书占用的原生槽绝不能被复用 ──
        SlotState mixed = SlotRules.NewState();
        mixed.slots[4] = Managed(2, 30);            // 第 5 条逻辑槽 -> 原生槽 2
        SlotRecord other = SlotRules.Empty(6);
        other.id = "other-mod";
        other.nativeSlot = 3;                        // 别的 mod 占着原生槽 3
        other.words = new string[100];
        mixed.slots[5] = other;
        SlotRules.Normalize(mixed);
        Check(SlotRules.NativeSlotOwnedByManaged(mixed, 2), "托管槽占用的原生槽可以被复用");
        Check(!SlotRules.NativeSlotOwnedByManaged(mixed, 3), "外部词书占用的原生槽不可复用");
        Check(!SlotRules.NativeSlotOwnedByManaged(mixed, 1), "无人占用的原生槽不算托管");
        Check(!SlotRules.NativeSlotOwnedByManaged(mixed, 5), "越界原生槽（5）一律不可复用");
        Check(!SlotRules.NativeSlotOwnedByManaged(mixed, 0), "原生槽 0 不可复用");
        Check(SlotRules.NativeSlots == 4, "游戏原生槽仍是 4 个");

        int mapped = 0;
        for (int i = 0; i < mixed.slots.Length; i++)
            if (mixed.slots[i].nativeSlot >= 1 && mixed.slots[i].nativeSlot <= SlotRules.NativeSlots)
                mapped++;
        Check(mapped <= SlotRules.NativeSlots, "同一时刻最多 4 条逻辑槽对应原生槽");

        // ── 6) 词表比较按序 ──
        Check(SlotRules.SameWords(new string[] { "a", "b" }, new string[] { "a", "b" }),
            "SameWords 相同序列");
        Check(!SlotRules.SameWords(new string[] { "a", "b" }, new string[] { "b", "a" }),
            "SameWords 顺序不同即不同");
        Check(!SlotRules.SameWords(new string[] { "a" }, null), "SameWords 空值安全");

        // ── 7) P1-1：每次加载都导入原生 4 书为镜像行 ──
        SlotState imported = SlotRules.NewState();
        imported.slots[7] = Managed(0, 12);            // 已有一条托管行，占空原生槽 0
        imported.slots[7].nativeSlot = 0;
        SlotRules.NativeBook[] books = new SlotRules.NativeBook[] {
            MakeNativeBook(1, "日语词书", 100),
            MakeNativeBook(2, "法语词库(猫条版)", 8116),
            MakeNativeBook(3, null, 3),                // 不足 5 词 → 跳过
            MakeNativeBook(4, "德语词库", 8062)
        };
        int added = SlotRules.ImportNativeBooks(imported, books);
        Check(added == 3, "导入 3 本原生书（不足 5 词的跳过）");
        Check(imported.slots[0].id == "native-1" && imported.slots[0].words.Length == 100 &&
              imported.slots[0].name == "日语词书" && !imported.slots[0].managed,
            "镜像行落在槽位号对应的行（native-1 → 行 1）");
        Check(imported.slots[1].id == "native-2" && imported.slots[1].words.Length == 8116,
            "native-2 → 行 2");
        Check(imported.slots[3].id == "native-4" && imported.slots[3].words.Length == 8062,
            "native-4 → 行 4");
        Check(imported.slots[7].id == "fr" && imported.slots[7].managed,
            "托管行不被镜像导入挤掉");

        // 幂等：原样重跑不再有变化
        Check(SlotRules.ImportNativeBooks(imported, books) == 0, "重复导入幂等");

        // 镜像行更新：同一 id 的原生书内容/名称变化 → 原位刷新
        books[0].Words = MakeWords(120);
        books[0].Name = "日语词书v2";
        Check(SlotRules.ImportNativeBooks(imported, books) == 1, "内容变化时刷新 1 行");
        Check(imported.slots[0].words.Length == 120 && imported.slots[0].name == "日语词书v2",
            "镜像行原位更新（id 不变、位置不变）");

        // 偏移落位：首选行被其它词书占用 → 重新导入时落第一个空行
        imported.slots[0] = Managed(0, 6);             // 首选行 1 被托管行占用
        imported.slots[0].nativeSlot = 0;
        imported.slots[8] = Managed(0, 7);             // 行 9 也被占用
        imported.slots[8].nativeSlot = 0;
        Check(SlotRules.ImportNativeBooks(imported, books) == 1, "缺行时补导 1 行");
        Check(imported.slots[2].id == "native-1", "首选行被占 → 落第一个空行（行 3）");

        // 托管行物化占用的原生槽不导入（内容已归托管行）
        SlotState occupied = SlotRules.NewState();
        occupied.slots[0] = Managed(2, 50);            // 托管行占用原生槽 2
        SlotRules.NativeBook[] clashing = new SlotRules.NativeBook[] { MakeNativeBook(2, "法语词库", 8116) };
        Check(SlotRules.ImportNativeBooks(occupied, clashing) == 0, "托管占用的原生槽不导入");
        Check(occupied.slots[1].id != "native-2" && occupied.slots[0].id == "fr",
            "托管行原样保留");

        // 20 行全满时不挤掉任何词书
        SlotState full = SlotRules.NewState();
        for (int i = 0; i < 20; i++) full.slots[i] = Managed(0, 5 + i);
        Check(SlotRules.ImportNativeBooks(full, books) == 0, "20 行全满时不导入新镜像");
        int managedCount = 0;
        for (int i = 0; i < 20; i++) if (full.slots[i].managed) managedCount++;
        Check(managedCount == 20, "全满导入后 20 条托管行原样保留");

        // ── 8) P1-2：改名与移除 ──
        SlotState managedState = SlotRules.NewState();
        managedState.slots[2] = Managed(1, 30);
        Check(SlotRules.TryRenameSlot(managedState, 2, "  我的法语书  "), "mod 行可改名");
        Check(managedState.slots[2].name == "我的法语书", "改名去除首尾空白");
        Check(!SlotRules.TryRenameSlot(managedState, 2, "   "), "纯空白拒绝");
        Check(!SlotRules.TryRenameSlot(managedState, 2, null), "null 拒绝");
        Check(managedState.slots[2].name == "我的法语书", "拒绝后名称不变");
        Check(!SlotRules.TryRenameSlot(managedState, 25, "x"), "越界改名拒绝");

        // 原生镜像行拒绝改名/移除（内容跟随游戏数据）
        SlotState mirrorState = SlotRules.NewState();
        mirrorState.slots[0] = Managed(0, 6);
        SlotRules.ImportNativeBooks(mirrorState, new SlotRules.NativeBook[] { MakeNativeBook(1, "日语词书", 100) });
        Check(SlotRules.IsNativeMirror(mirrorState.slots[1]), "镜像行判定成立");
        Check(!SlotRules.TryRenameSlot(mirrorState, 1, "自定义名"), "镜像行拒绝改名");
        int mirrorRelease;
        Check(!SlotRules.TryClearSlot(mirrorState, 1, out mirrorRelease), "镜像行拒绝移除");
        Check(mirrorState.slots[1].id == "native-1", "拒绝移除后镜像行原样保留");

        // mod 行移除：托管物化行要上报应释放的原生槽
        SlotState clearState = SlotRules.NewState();
        clearState.slots[4] = Managed(3, 30);
        clearState.selected = 5;
        int release;
        Check(SlotRules.TryClearSlot(clearState, 4, out release) && release == 3,
            "托管行移除上报原生槽 3");
        Check(!SlotRules.HasPlayableWords(clearState.slots[4]) && clearState.selected == 0,
            "移除后行被清空、选中态复位");
        Check(!SlotRules.NativeSlotOwnedByManaged(clearState, 3), "移除后原生槽 3 不再被托管");

        // 空/外部行移除不上报释放
        int emptyRelease;
        Check(SlotRules.TryClearSlot(clearState, 5, out emptyRelease) && emptyRelease == 0,
            "空行移除不上报释放");

        // ── 9) P1-1 逐出规则：内容已跟踪的物理槽可接管，未跟踪内容 fail-closed ──
        SlotState eviction = SlotRules.NewState();
        eviction.slots[0] = Managed(0, 9116);          // 托管行（自带词表，fr）
        SlotRules.NativeBook[] frBook = new SlotRules.NativeBook[] { MakeNativeBook(1, "法语词库", 8116) };
        SlotRules.ImportNativeBooks(eviction, frBook); // native-1 镜像 → 行 2
        string[] nativeLive = MakeWords(8116);
        Check(SlotRules.NativeContentTracked(eviction, nativeLive),
            "物理槽内容=镜像行快照 → 可接管");
        Check(!SlotRules.NativeContentTracked(eviction, MakeWords(777)),
            "物理槽内容无任何行持有 → fail-closed 拒绝");
        Check(!SlotRules.NativeContentTracked(eviction, MakeWords(4)),
            "不足可玩门槛的内容不判定可接管");
        Check(!SlotRules.NativeContentTracked(null, nativeLive), "空状态 fail-closed");

        // ── 10) 持久化往返：自建序列化必须真正保住 20 行（JsonUtility 会丢 slots）──
        SlotState persist = SlotRules.NewState();
        persist.selected = 3;
        persist.slots[0] = Managed(1, 8116);
        persist.slots[0].id = "catbar-french-cefr-complete";
        persist.slots[0].name = "法语词库(猫条版)";
        persist.slots[0].language = "fr";
        persist.slots[0].owner = "mod";
        persist.slots[0].managed = true;
        persist.slots[1] = SlotRules.Empty(2);
        persist.slots[1].id = "native-2";
        persist.slots[1].name = "俄语A1A2";
        persist.slots[1].owner = "external";
        persist.slots[1].nativeSlot = 2;
        persist.slots[1].words = MakeWords(8451);
        string blob = SlotRules.Serialize(persist);
        Check(blob.Length > 1000, "序列化输出包含全部行（不是 38 字节空档）");
        SlotState revived = SlotRules.Deserialize(blob);
        Check(revived != null, "序列化结果可解析");
        Check(revived != null && revived.slots != null && revived.slots.Length == SlotRules.MaxSlots,
            "往返后仍是 20 行");
        Check(revived != null && revived.selected == 3, "往返后 selected 保留");
        Check(revived != null && revived.slots[0].managed && revived.slots[0].words.Length == 8116 &&
            revived.slots[0].id == "catbar-french-cefr-complete",
            "往返后托管行 id/managed/词表完整");
        Check(revived != null && revived.slots[1].words.Length == 8451 &&
            revived.slots[1].nativeSlot == 2 && revived.slots[1].name == "俄语A1A2",
            "往返后原生镜像行快照完整");

        // 转义与边界：引号/反斜杠/换行/中文都不能破坏 JSON
        SlotState tricky = SlotRules.NewState();
        tricky.slots[0].name = "带\"引号\"与\\反斜杠\n换行 中文";
        tricky.slots[0].words = new string[5] { "a\"b", "c\\d", "e\nf", "日本語", "emoji? ok" };
        SlotState trickyBack = SlotRules.Deserialize(SlotRules.Serialize(tricky));
        Check(trickyBack != null && trickyBack.slots[0].name == tricky.slots[0].name,
            "往返保住特殊字符名称");
        Check(trickyBack != null && trickyBack.slots[0].words[0] == "a\"b" &&
            trickyBack.slots[0].words[1] == "c\\d" && trickyBack.slots[0].words[2] == "e\nf",
            "往返保住词表里的引号/反斜杠/换行");

        // 解析失败必须返回 null（fail-closed），不能静默变成空档
        Check(SlotRules.Deserialize("{\"schema\":1,\"selected\":0}") != null,
            "旧 38 字节文件可解析（slots 缺省 → 空行，不丢其它键）");
        Check(SlotRules.Deserialize("{\"slots\":[{\"number\":1,") == null,
            "截断 JSON → null（不静默当空档）");
        Check(SlotRules.Deserialize("not json at all") == null, "非 JSON → null");
        Check(SlotRules.Deserialize(null) == null, "null 输入 → null");
        Check(SlotRules.Deserialize("{\"schema\":2,\"unknownKey\":{\"a\":[1,2]},\"slots\":[]}") != null,
            "未知字段可跳过（向后兼容）");

        // ── P1-17：原生槽位数量可探测回填（作者加槽不失联）──
        Check(SlotRules.MinNativeSlots == 4 && SlotRules.CurrentNativeSlots == 4,
            "默认原生槽数 = 4（下限保护）");
        SlotRules.SetNativeSlotCount(6);
        Check(SlotRules.CurrentNativeSlots == 6, "SetNativeSlotCount(6) 生效");
        SlotState grown = SlotRules.NewState();
        SlotRules.NativeBook[] extra = new SlotRules.NativeBook[] {
            new SlotRules.NativeBook { Slot = 5, Name = "新槽书", Words = MakeWords(10) } };
        Check(SlotRules.ImportNativeBooks(grown, extra) == 1, "原生槽 5 能导入（加槽跟随）");
        Check(grown.slots[4].id == "native-5" && grown.slots[4].words.Length == 10,
            "导入落在 native-5 镜像行");
        SlotRules.SetNativeSlotCount(4);
        SlotState shrunk = SlotRules.NewState();
        Check(SlotRules.ImportNativeBooks(shrunk, extra) == 0,
            "回到 4 槽后槽 5 拒绝导入（越界保护）");
        Check(SlotRules.NativeSlotOwnedByManaged(grown, 5) == false, "越界原生槽不算受管");

        // ── P1-18：中文槽名生成器边界（1..10、11..99、防呆）──
        // Canonical 在 CustomSlotsMod 内（不可直接单测），这里用反射调静态私有方法。
        System.Reflection.MethodInfo canon = typeof(SlotRules).Assembly.GetType("WcpCustomSlots.CustomSlotsMod") == null
            ? null : typeof(SlotRules).Assembly.GetType("WcpCustomSlots.CustomSlotsMod")
                .GetMethod("Canonical", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Static);
        if (canon != null)
        {
            Check((string)canon.Invoke(null, new object[] { 1 }) == "自定义词书一", "槽1 → 自定义词书一");
            Check((string)canon.Invoke(null, new object[] { 4 }) == "自定义词书四", "槽4 → 自定义词书四");
            Check((string)canon.Invoke(null, new object[] { 5 }) == "自定义词书五", "槽5 → 自定义词书五（旧 switch 会错写成四）");
            Check((string)canon.Invoke(null, new object[] { 10 }) == "自定义词书十", "槽10 → 十");
            Check((string)canon.Invoke(null, new object[] { 12 }) == "自定义词书十二", "槽12 → 十二");
            Check((string)canon.Invoke(null, new object[] { 20 }) == "自定义词书二十", "槽20 → 二十");
        }
        else
        {
            Console.WriteLine("SKIP Canonical 用例（测试工程不含 CustomSlotsMod.cs，只测模型）");
        }

        // ── 地址翻译层（2026-09-18）：物理页框 ≠ 逻辑身份 ──
        // 回归的是本次实机 bug 的核心：物化把「俄语词书」放进物理槽 1 后，任何
        // 「这块页框现在是谁」的判断都必须看内容，而不是看槽号。
        {
            SlotState map = SlotRules.NewState();
            SlotRecord ru = SlotRules.Empty(3);
            ru.id = "ru";
            ru.name = "俄语词库(猫条版)";
            ru.owner = "mod";
            ru.managed = true;
            ru.nativeSlot = 1;
            string[] ruWords = MakeWords(8451);
            ru.words = ruWords;
            map.slots[2] = ru;

            // 另一个托管行先占槽 2，随后被换掉
            SlotRecord fr = SlotRules.Empty(2);
            fr.id = "fr";
            fr.name = "法语词库(猫条版)";
            fr.owner = "mod";
            fr.managed = true;
            fr.nativeSlot = 2;
            fr.words = MakeWords(8116);
            map.slots[1] = fr;

            // ① 内容指纹稳定且区分不同词表
            Check(SlotRules.ContentFingerprint(ruWords) == SlotRules.ContentFingerprint(ruWords),
                "指纹：同词表两次计算一致");
            Check(SlotRules.ContentFingerprint(ruWords) != SlotRules.ContentFingerprint(fr.words),
                "指纹：不同词表必须不同（俄语 vs 法语）");
            Check(SlotRules.ContentFingerprint(new string[0]) == "",
                "指纹：空词表返回空串");

            // ② 反查归属看内容而非槽号 —— 这正是「日语词库」显示 bug 的根因
            Check(SlotRules.OwnerOfContent(map, ruWords) == 3,
                "反查：俄语内容落在物理槽1，归属仍是逻辑行3（不看槽号）");
            Check(SlotRules.OwnerOfContent(map, fr.words) == 2, "反查：法语内容 → 逻辑行2");
            Check(SlotRules.OwnerOfContent(map, MakeWords(600)) == 0, "反查：陌生内容 → 0（无主）");
            Check(SlotRules.OwnerOfContent(map, null) == 0, "反查：null 内容 → 0");

            // ③ ContentMatches 不认「词数相同但内容不同」的近似
            string[] sameCountDifferent = MakeWords(8451);
            sameCountDifferent[0] = "Ω-不同";
            Check(!SlotRules.ContentMatches(sameCountDifferent, ru),
                "内容比对：词数相同但词不同 → 不匹配（绝不吃近似）");
            Check(SlotRules.ContentMatches(ruWords, ru), "内容比对：逐词一致 → 匹配");
            Check(!SlotRules.ContentMatches(ruWords, null), "内容比对：null 记录 → 不匹配");

            // ④ 页框归属唯一化：同一块页框不能有两行同时宣称占用
            SlotState dup = SlotRules.NewState();
            SlotRecord a = SlotRules.Empty(1);
            a.managed = true; a.nativeSlot = 1; a.words = MakeWords(100);
            SlotRecord b = SlotRules.Empty(5);
            b.managed = true; b.nativeSlot = 1; b.words = MakeWords(200);
            dup.slots[0] = a;
            dup.slots[4] = b;
            SlotRules.ReleaseFramesExcept(dup, 4, 1);
            Check(dup.slots[0].nativeSlot == 0, "页框释放：旧占用者的 nativeSlot 被清 0");
            Check(dup.slots[4].nativeSlot == 1, "页框释放：新占用者保留页框");
            bool reentrant = true;
            try { SlotRules.ReleaseFramesExcept(dup, 4, 1); }
            catch (Exception) { reentrant = false; }
            Check(reentrant, "页框释放：可重复调用不抛异常");
        }

        Console.WriteLine("Failures: " + failures);
        return failures == 0 ? 0 : 1;
    }
    private static SlotRules.NativeBook MakeNativeBook(int slot, string name, int wordCount)
    {
        return new SlotRules.NativeBook { Slot = slot, Name = name, Words = MakeWords(wordCount) };
    }

    private static string[] MakeWords(int count)
    {
        string[] words = new string[count];
        for (int i = 0; i < count; i++) words[i] = "w" + i;
        return words;
    }
}
