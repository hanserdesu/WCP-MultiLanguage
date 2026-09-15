# PATCH 作业执行细则（补第 3 条例句）

配套 `AGENT_SPEC.md`（硬性规则原文）。本文件是**子代理直接照做**的操作手册。

## 环境（本机特殊，必须照做）

- bash 的 PATH 缺 coreutils，`ls` / `head` / `sed` / `dirname` 全部 command not found。
  **每条 bash 命令开头都加**：
  ```
  export PATH="/c/Users/hanserdesu/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH";
  ```
- `python` 已在 PATH（3.13.12 托管版），直接敲 `python`。
- **不要用 PowerShell**：本会话 PowerShell 的 stdout 捕获是坏的，只会拿到空输出。
- 命令前先 `cd /d/Japanese/wcp_wordbooks`。

## 单批次循环（逐批做完再下一批）

1. 看词表与缺口：
   `python tools/gen_dispatch.py batch NN Y`
   输出 `词<TAB>读音<TAB>释义<TAB>级别<TAB>已有N条`，缺口词带 `<<< 需补M条`。
2. 读 `work/gen_out_NN_Y.json`，看清每个词**已有的 ja 原句**（新写的 ja 绝不能撞车）。
3. 为每个有缺口的词写 1 条新的 `{ja, zh}`。
4. 写补丁 `work/patch_NN_Y.json`：`{"词": [{"ja":"...","zh":"..."}]}`，只放新增，`ensure_ascii=False`。
5. 合并：`python tools/gen_helper.py merge NN Y work/patch_NN_Y.json`
6. 自检：`python tools/gen_pipeline.py check-one NN Y` → 必须 `PASS`。
   FAIL 就按提示重写补丁 → 重 merge → 重 check，循环到 PASS。

## 硬性规则（脚本逐条查，违反即 FAIL）

1. 每词**恰好 3 条**（含原有）
2. `ja` 以 `。` / `！` / `？` 结尾
3. `ja` 每个字符必须在 JMDict 日语用字白名单内 —— **绝不写简体中文专用字**：
   选→選、绩→績、晚→晩、灾→災、气→気、处→処、议→議、单→単
4. `zh` 必须是中文，**绝不含假名**（は/が/を/れる/けれども 一律不许）
5. 同词多条 ja 不得重复
6. **词形必须字面出现**（原形，或去掉末尾假名的词干）。活用词最易踩：
   `遮る` ≠ 「遮った」、`果たす` ≠ 「果たした」、`化する` ≠ 「化した」
   → 用带出原形的接续：`〜ために / 〜べきだ / 〜つもりだ / 〜ことができる / 〜必要がある / 〜のは難しい`
7. JSON 合法 UTF-8，`ensure_ascii=False`

## 质量红线（脚本查不到，但必须守）

- 不写**整词英文**（crew / thirty / suddenly 这类模型漂移产物）。
  例外允许：日语里的标准缩写与记号 —— `IT` / `JR` / `ATM` / `BGM` / `ビタミンC` / `H2O`。
  能自然避开就避开。
- 三条句子各不相同：不同场景 / 不同搭配 / 不同语体，不要只换主语。
- 长度 10~40 字；自然地道，不写翻译腔。`zh` 通顺，不逐字硬译。

## 报告格式（一句话）

```
NN_Y PASS（补N条）/ NN_Y PASS（补N条）/ ...
```

修不好就如实说卡在哪条规则、哪个词。**不许谎报 PASS。**
