# append_r13.py — 把第十三轮台账/记忆文本追加到对应文件（bash coreutils 间歇失踪的替代）
import io
import sys

LEDGER = r"D:\ATooManyLanguage\docs\TASKS.md"
MEMORY = r"D:\ATooManyLanguage\.workbuddy\memory\2026-09-18.md"

LEDGER_TEXT = u"""
## P1-33 性能第十三轮：接线搬到 Awake（普查 59/59 给的 Go）（2026-09-18 晚）

### 实机验证（第十二轮构建 `9b0876c3`，会话 Player.log 21:02:06，96929 B）

证据归档：`probes/log_archive/round12_build_9b0876c3.txt`。

**第十二轮的三个承诺全部兑现：**

| 承诺 | 实机 |
|---|---|
| 快路径命中率 ≥9/10 | 稳态窗口 9/9、9/9、7/7、7/7（切书窗口掉到 5/6、5/7 是**应该的**——书换了就该未命中） |
| Awake 普查 N=59 → 接线可搬 | `Awake 期解析普查 — 可解析 59 个（失败 0，耗时 1554ms）`（L81）——**Go** |
| 稳态 mod 占用 ~44ms/s → ~10ms/s | 轻载窗口 L546：**25.6ms/10s**（原同类窗口 442ms/10s）。两次 Match 224ms → 2.4ms，**>90×** |

**普查同时给了接线成本的实机单价：1554ms 干跑解析 + 1981ms 实装 = 59 点的
TypeByName 解析在实机约 26ms/点**（离线实测是 2.7ms/点，差 10×，未归因但方向一致）。

### 本轮改动（部署 `ab5c5632f591…`，107520 B）

**Harmony 接线从「首次接管帧」搬到 Awake，整场不拆。** 这是上一轮自己立的规矩
——"N=59 则搬，N<59 则否"——本轮 N 出来了，执行。

- `Host.Awake`：`_enabled` 时直接 `InstallFeatures`（替换了普查调用）。
- `SyncFeaturePatches` 的**失活即移除分支删除**。它是"切书瞬态失活 → UnpatchSelf →
  下一帧重装再付 2 秒"的抖动来源（第十二轮日志 L625 的 `补丁:Sync x6` 就是它）。
  保留防御性补装分支（正常路径 no-op）。
- `CensusAtAwake` 连同 `_dryRun` 开关删除：被接线本身取代
  （`Harmony 接线完成 — 命中 N 个`汇总行就是同一个诊断）。
- 随删除的还有每点 `if (!_dryRun)` 判断。

**安全依据（本轮逐点核过，不是推断）**：59 个点的处理器全部经
`WcpHostPlugin.Instance → Runtime`，而 `HostRuntime` 里**每一个** `Post*`/`Prefix*`
的第一行都是 `if (!IsActive [|| ActiveStrategy == null] …) return`（HostRuntime.cs
146/168/174/306/345/374/385/513/540/573 共 10 处，grep 全中）。`IsActive` = 身份门
通过。所以"未接管时补丁在场"与"未接管时补丁不在场"行为差异为零。
旧设计里"identity-only 包不接线"的语义由处理器内的 `ActiveStrategy == null`
门保持，不需要靠"不接线"来实现。

### 门禁

- takeover **39 PASS / 0 FAIL**；registry **77 PASS / 0 FAIL**；slot **ALL PASS (18)**；
  wordaudio **80 PASS / 0 FAIL**。
- `probes/verify_round13.py` → **PASS**：repo==deployed 字节一致，新日志行在，
  **被取代的两行（普查 / "等待身份门通过"）已不在**——负向断言，防"假搬"。

### 诚实边界

- **收益未实测**：预期首次接管帧从 12923ms（mod 3632ms）掉到 ~9000ms 以下
  （少付 1981ms 接线 + 不再抖动重装）。游戏没跑这一版。
- **"未接管时补丁在场"的兼容性**：理论上处理器全部空转，但游戏方法现在带着
  Harmony trampoline 跑整场——如果有哪个游戏方法对 Harmony 包装敏感（反射取
  MethodInfo、调用栈检查），这是唯一的新风险面。下次日志若出现新异常，
  第一个怀疑它。
- **队列:规则 成为新的稳态冠军**：L676/L753 里 180~203ms/10s，是每秒一次的
  真实规则执行（非浪费）。它是真工作，不是 bug；要再降只能优化规则循环本身
  （17 字段 × ES3 批量内写），价格记在下一轮。
- bash 的 coreutils（grep/tr/head/dirname/cat）本轮**间歇性**失踪（同一命令里
  前用后失效），汇总与追加改用 Python（`probes/check_gates_r13.py` 等）。

### 下一次实机要看的数字

```text
① 启动日志里「行为 Harmony 接线已在加载期安装」+「Harmony 接线完成 — 命中 59 个」
   —— 接线应在游戏加载期出现，而不是首次接管帧
② 首次接管帧是否不再出现 补丁:Sync ≈2000ms（帧长应掉 ~2000ms）
③ 整场是否零「行为 Harmony 接线已移除/已安装」抖动日志
④ 未接管游玩段有无新异常（trampoline 兼容性的实机检验）
⑤ 队列:规则 稳态是否仍是 ~180ms/10s —— 下一个候选靶子
```
"""

MEMORY_TEXT = u"""
## 第十三轮（21:05 起）：接线搬到 Awake + 第十二轮守卫收益实机确认

**部署版本**：`ab5c5632f591…` / 107520 B（verify_round13 PASS：新行在、被取代两行不在、字节一致）。
实机证据归档：`probes/log_archive/round12_build_9b0876c3.txt`。

### 第十二轮构建实机验证（`9b0876c3`）

- **守卫收益兑现**：稳态窗口 mod 占用 442ms/10s → **25.6ms/10s**（L546）；两次 Match 224ms → 2.4ms。
  命中率稳态 9/9、7/7，切书窗口掉到 5/6 是应该的（书换了）。
- **Awake 普查 59/59 可解析（1554ms）** → 上一轮立的规矩"N=59 则搬"触发执行。

### 本轮改动

- `Host.Awake` 直接 `InstallFeatures`（替换普查）；`SyncFeaturePatches` 失活即移除分支删除
  （切书抖动重装 2 秒的来源）；`CensusAtAwake`/`_dryRun` 删除。
- 安全依据逐点核过：59 个处理器全经 Runtime，每个 Post*/Prefix* 首行 `if (!IsActive…) return`
  （HostRuntime.cs 10 处 grep 全中）→ 未接管时空转，行为差异为零。

### 门禁 / 校验

- takeover 39 / registry 77 / slot 18 / wac 80 全零失败；verify_round13 PASS。

### 环境坑更新

- bash coreutils（cat/grep/tr/head/dirname）**间歇性**失踪（同命令内前用后失效，退出码 127）——
  文本追加/汇总一律走 Python（`probes/append_r13.py`、`check_gates_r13.py` 是模板）。
"""


def append(path, text):
    with io.open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print("appended %d chars -> %s" % (len(text), path))


append(LEDGER, LEDGER_TEXT)
append(MEMORY, MEMORY_TEXT)
print("DONE")
