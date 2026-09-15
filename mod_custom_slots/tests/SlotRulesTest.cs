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

        Console.WriteLine("Failures: " + failures);
        return failures == 0 ? 0 : 1;
    }
}
