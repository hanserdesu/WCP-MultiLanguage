# 法语例句生产作业规范（子代理必读）

你要为 WCP 法语词书生成 **法语例句 + 中文翻译**。

## 你的产出

写文件 `D:\French\work\gen_out_NN_Y.json`（NN=词块号, Y=批号）。格式：JSON 对象，
键=单词，值=例句数组。

```json
{
"emménager": [
{"fr": "Ils ont emménagé dans un nouvel appartement le mois dernier.", "zh": "他们上个月搬进了一套新公寓。"},
{"fr": "Nous allons emménager ensemble après le mariage.", "zh": "婚礼后我们要搬去一起住。"},
{"fr": "La famille emménage dans sa nouvelle maison demain.", "zh": "这家人明天搬进新家。"}
]
}
```

## 硬性规则（校验脚本逐条检查，违规即 FAIL）

1. **每个词必须恰好 3 条例句**（不是 2 条，不是 4 条）
2. `fr` 必须以 `.` `!` 或 `?` 结尾（句末引号/省略号不行）
3. `fr` 必须是**地道法语**——严禁出现中日韩字符，严禁出现
   下划线/花括号/{}/<> 等 JSON 模板残留
4. `zh` 必须是**中文**，且**绝对不含拉丁字母整词**（4 个以上连续拉丁字母会被拒）
   也不含全角括号（）
5. 同一个词的多条 `fr` **不得重复**
6. **词的某种自然形式必须出现在例句中** —— 见下
7. 每句 5~25 个单词，长度适中
8. JSON 必须是合法 UTF-8；输出文件只含这一个 JSON 对象

## 规则 6 详解（法语动词会变位）

校验按「原形或词干（去重音去大小写）」匹配。常见规则变位自动通过：

- 原形出现：`table` → "La table est grande." ✔
- 词干出现：`finir` → "Il faut finir le travail." / "Elle finit à six heures." ✔
  （fini/finis/finissons 都含词干 fin-）
- 名词复数：`table` → "Les tables..." ✔（tables 含 table）
- 形容词阴性：`grand` → "Une grande maison." ✔（grande 含 grand）

**不规则动词要写含原形或明显词干的句子**，否则会被拒：
être/avoir/aller/faire/dire/voir/savoir/pouvoir/vouloir/venir/tenir/devoir/
prendre/mettre/lire/boire/vivre/suivre/connaître/croire/écrire/naître/mourir/
rire/plaire/falloir/valoir/pleuvoir/envoyer 及其派生词
（devenir/revenir/apprendre/comprendre/permettre/promettre/décrire…）。
最稳妥的写法：**用原形**（infinitif），或用与原形明显同根的形式：
- aller → "Je voudrais aller à Paris." ✔（不要只写 "Elle y va."）
- faire → "Qu'est-ce que tu fais ?" ✔（fais 与 faire 同根 ✔）
- venir → "Tu peux venir avec nous ?" ✔

**特殊词形注意**：oeil（复数 yeux）、travail（复数 travaux）、monsieur（messieurs）、
madame（mesdames）、beau（belle）、nouveau（nouvelle）、vieux（vieille）——
要么用原形/规则复数，要么换一个含原形的句子。

## 例句质量要求

- **自然地道**，像法国人日常说的话，不要翻译腔
- **情境具体**，能体现该词的典型用法，不要空洞套话
- **三条各不相同**：不同场景 / 不同搭配 / 不同时态语式，不要只换主语
- 句首大写，标点规范（法语可用 ? ! : 前加空格的写法，也可不加，保持一致即可）
- 中文翻译要**通顺**，符合中文表达习惯，不要逐字硬译

## 词表查看

```
python -c "import json,sys; sys.stdout.reconfigure(encoding='utf-8'); d=json.load(open('work/gen_words_NN.json',encoding='utf-8')); [print(w['word'],'|',w['pos'],'|',w['zh'],'|',w['level']) for w in d[Y*100:(Y+1)*100]]"
```

`pos` 是词性（v./n.m./n.f./adj.…），`zh` 是中文释义，是判断用法的最重要依据。

## 自检（必做）

```
cd D:\French
python tools/gen_pipeline_fr.py check-one NN Y
```

输出 `PASS` 才算完成。若 `FAIL`，按提示逐条修正后重跑，**直到 PASS**。
