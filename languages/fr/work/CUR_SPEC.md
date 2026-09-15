# 法语词表精选作业规范（子代理必读）

你要为 WCP 法语词书做 **词表精选 + CEFR 分级 + 中文释义**。
输入是按字幕词频排序的 Lexique383 词元块；你输出精选结果 JSON。

## 你的产出

写文件 `D:\French\work\cur_out_NN.json`（NN 为块号，如 `cur_05.json`）。格式：

```json
{
  "kept": [
    {"word": "table", "zh": "桌子；餐桌", "level": "a1"},
    {"word": "emménager", "zh": "搬入（新居）", "level": "b2"}
  ],
  "drop": [
    {"word": "xxxy", "reason": "乱码/非词"},
    {"word": "wagnerien", "reason": "专名派生，过于冷僻"}
  ]
}
```

## 硬性规则（校验脚本逐条检查，违规即 FAIL）

1. **输入的每个词必须恰好出现一次**：要么在 `kept`，要么在 `drop`。
   既不在 kept 也不在 drop、或两边都出现 = FAIL。顺序可以打乱。
2. `level` 必须是 `a1` / `a2` / `b1` / `b2` 之一。
3. `zh` 必须含中文（CJK），禁止拉丁字母整句（引用法语词形会被拒）；
   长度 2~30 字。禁止把 IPA 或词性写进 zh。
4. `drop.reason` 非空，10 字以内简短理由。
5. JSON 合法 UTF-8。不要输出 JSON 之外的任何内容到该文件。

## 精选规则（drop 什么）

- 专名（人名/地名/品牌/作品名/语言民族名派生如 chiraquien）
- 过于冷僻（rank > 7000 且不常用的书面/古旧/技术词：chérubin、clergé 这类若你判断普通学习者不需要就 drop）
- 纯拟声词（ono 词性基本都 drop，但 aïe 这类常用感叹词可保留）
- 乱码、非词、纯缩略
- 英语借词若在法语日常使用普遍（weekend, football, parking）则 **保留**；
  只是字幕里偶尔出现的英语原词（如 and, because）则 drop
- 冗余屈折残留（若输入里混进了明显不是词元的变体，如复数形容词形式与原词重复）drop 并注明
- drop 总数不要超过该块的 40%（校验会拒绝）

## 保留词的中文释义（zh）

- 简洁词典式：主要义项 1~3 个，用「；」分隔：`好；好的；善良的`
- 名词默认给单数词典形；动词给不定式含义；形容词给原形
- 不要写例句、不要写拼音、不要写词性、不要写 IPA
- 允许用括号补充限定：`反正（口语）`、`公司（商业）`

## CEFR 分级（按实际难度判断，不严格按 rank）

- a1：最基础生存词汇（问候、数字、家庭、日常物、常用动词）
- a2：日常扩展（描述、情绪、常见抽象词）
- b1：流利表达所需（社会、工作、观点类词汇）
- b2：高级（低频抽象词、正式书面语、精细表达）
- 你的块有 rank 提示：rank 靠前的块整体偏 a1/a2，靠后的偏 b1/b2，
  但**逐词按真实教学难度判断**（如 rank 2500 的 "merci" 也应是 a1）。

## 自检（必做）

```
cd D:\French
python tools/curate_pipeline.py check-one NN
```

输出 `PASS` 才算完成。若 `FAIL` 按提示修正后重跑，**直到 PASS**。

## 词表查看

```
python -c "import json,sys; sys.stdout.reconfigure(encoding='utf-8'); d=json.load(open('work/cur_NN.json',encoding='utf-8')); [print(w['word'],'|',w['ipa'],'|',w['pos'],'|',w['rank']) for w in d]"
```
