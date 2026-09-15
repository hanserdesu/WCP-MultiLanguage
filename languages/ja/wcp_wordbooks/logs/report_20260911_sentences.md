# 例句全覆盖任务 · 完成报告

日期: 2026-09-11
起点: 达标词 4,000 / 15,812，剩余 119 批（27 PATCH + 92 NEW）
终点: **15,812 / 15,812 词全部达标，每词恰好 3 条，剩余批次 0**

## 完成内容

| 阶段 | 内容 | 结果 |
|------|------|------|
| PATCH 补句 | 词块 06–12 共 27 批，补写 2,436 条 | 全部 check-one PASS |
| NEW 生产 | 词块 12_3、17–39 共 92 批，新建 27,600 条 | 全部 check-one PASS |
| 旧句翻译 | tr_chunk 17 块中 11 块（5,771 句）缺翻译 → 补齐 | 9,071/9,071 全覆盖 |
| 落库 | `apply_sentences.py`：合并 master + 写 wcpFullEng.db | UPDATE 10,251 / master 15,812 词 |

合计新增日文例句约 **30,000+ 条**（含补丁），游戏本地库 sentence2 现在
15,812 个日文词每词 ≥3 条，旧英文例句全部带上中文翻译。

## 校验证据（全部主会话亲跑，非代理自述）

1. `gen_pipeline.py summary` → 达标词数 15812, 剩余批次 0
2. `gen_helper.py audit` → 每词条数分布 {3: 15812}
3. `apply_sentences.py` 终轮输出 → master 词数 15812, 缺翻译 0, <3条 0；
   UPDATE 10251, 抽样500词中<3条 0
4. wcpFullEng.db 逐词全查（GROUP BY word 对比 master 15,812 词）→
   **DB中<3条的词: 0**
5. 抽检 `お産` → 3 条例句全部为「例句：日本語。（中文）」格式

## 说明

- 生产方式：7 波并行子代理（每波 3–4 个），契约 = `work/AGENT_SPEC.md` +
  `work/PATCH_SPEC.md`；每波结束由主会话跑 summary 复核后才放行下一波。
- 存在少量后台 Agent 重复实例越界完成了未分配批次（29_0/37_0/37_1），
  内容均过 check_slice 全量校验 + 人工抽检（29_0 抽查质量合格），无风险。
- 首次落库曾因前台 2 分钟超时被 SIGTERM，单事务未 commit 自动回滚、无损；
  改后台重跑成功。
- master 数据源：`data/translations/sentences_master.json`（15,812 词），
  `patch_local_db.py` 的 sentence2 灌库数据源即此文件，幂等可重跑。
- 游戏每次查词现开连接，**无需重启**，下一个词立即生效。
