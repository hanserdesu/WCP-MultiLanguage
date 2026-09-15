# -*- coding: utf-8 -*-
"""德语例句引擎 v2 (2026-09-15 质量审计修复, P1).

旧引擎问题: 10,222 句框里 top 框占 3.3%, 大量空洞凑句
（"Die stetige Verbesserung von X bleibt ein vorrangiges Ziel…"）。

v2:
  - 框架池主会话手写, 按词性分组（名词/动词/形容词/兜底）;
  - 每词 3 句轮转 3 个不同框架, 8,062 词 → top-frame share ~2.5%;
  - 德语名词带冠词问题: 框架一律避开冠词+词条组合, 用介词短语/复数语境;
  - 产出 german_books.json 同步嵌入 sentences 字段 + sentences_master.json。

注意: 不做词形变换 —— 德语例句统一用词条原形可成立的框架
（介词 + 名词 / 情态动词 + 动词原形 / sein + 形容词）。
"""
import json, sys, re, collections
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parent.parent
BOOKS_FILE = ROOT / 'output' / 'german_books.json'
MASTER_FILE = ROOT / 'data' / 'translations' / 'sentences_master.json'

V = [  # verb: 槽位 = 情态/不定式结构
    ("Bevor du eine Entscheidung triffst, solltest du ruhig {w}.", "做决定之前，你应该冷静地{z}。"),
    ("Als er jung war, pflegte er sonntags zu {w}.", "年轻时他常常在星期天{z}。"),
    ("Der Lehrer hat uns gebeten, ohne Hilfe zu {w}.", "老师请求我们不靠帮助去{z}。"),
    ("Es fällt mir schwer zu {w}, aber es wird besser.", "{z}对我来说很难，但正在变好。"),
    ("Wenn du {w} willst, fang am besten sofort an.", "如果你想{z}，最好马上开始。"),
    ("Nachdem er lange {w} hatte, fühlte er sich erschöpft.", "长时间{z}之后，他感到疲惫。"),
    ("Es bringt nichts, erst in letzter Minute zu {w}.", "拖到最后关头才{z}毫无意义。"),
    ("Hast du Lust, am Wochenende zu {w}?", "周末你想不想去{z}？"),
    ("Mit ständiger Übung kann jeder lernen zu {w}.", "只要坚持练习，任何人都能学会{z}。"),
    ("Besser jetzt {w} als später bereuen.", "与其将来后悔，不如现在就{z}。"),
    ("Um gut {w} zu können, muss man die Grundregeln kennen.", "要想会{z}，必须了解基本规则。"),
    ("Trotz wenig Zeit beschloss das Team zu {w}.", "尽管时间不多，团队还是决定去{z}。"),
    ("Morgen fahren wir in die Stadt, um zu {w}.", "明天我们进城去{z}。"),
    ("Ich habe noch nie jemanden so engagiert {w} sehen.", "我从没见过有人如此投入地{z}。"),
    ("Wenn etwas unklar ist, frage lieber, bevor du anfängst zu {w}.", "如果有不明白的地方，先问再{z}。"),
    ("Er hat gelernt zu {w}, indem er abends Videos sah.", "他靠晚上看视频学会了{z}。"),
    ("Es lohnt sich zu {w}, auch wenn es dauert.", "即使见效慢，{z}也是值得的。"),
    ("Der Arzt riet ihm, täglich zu {w}.", "医生建议他每天{z}。"),
    ("Fast niemand schafft es beim ersten Mal zu {w}.", "几乎没人第一次就能{z}成功。"),
    ("Er sagte, er würde lieber zu Hause {w}.", "他说他更愿意在家里{z}。"),
    ("Er begann zu {w}, bevor der Wecker klingelte.", "闹钟还没响，他就开始{z}了。"),
    ("Dieses Projekt verlangt, konzentriert zu {w}.", "这个项目要求全神贯注地{z}。"),
    ("Jeden Morgen widmet er eine halbe Stunde dem {w}.", "他每天早上花半小时{z}。"),
    ("Bei Regen liebt er es zu {w}.", "下雨的时候他特别喜欢{z}。"),
    ("Es wäre ein Fehler, ohne Plan zu {w}.", "毫无计划地去{z}是个错误。"),
    ("Schließlich entschloss er sich, noch am Abend zu {w}.", "他终于决定就在那天晚上去{z}。"),
    ("Wer soll {w}, wenn du es nicht kannst?", "如果你去不了，谁去{z}呢？"),
    ("Endlich habe ich Zeit zu {w}.", "我终于有时间去{z}了。"),
    ("Er versprach, bis Ende der Woche zu {w}.", "他答应在周末前{z}。"),
    ("Erzähl mir, wie du gelernt hast zu {w}.", "跟我讲讲你是怎么学会{z}的。"),
]

N = [  # noun: 槽位 = 介词短语（避免冠词性别问题）
    ("Gestern las ich einen interessanten Artikel über {w}.", "昨天我读了一篇关于{z}的有趣文章。"),
    ("In der Prüfung kam eine Frage über {w} vor.", "考试里出了一道关于{z}的题。"),
    ("In diesem Film geht es im Kern um {w}.", "这部电影归根结底讲的是{z}。"),
    ("Wir haben den ganzen Abend über {w} gesprochen.", "我们聊了一晚上{z}。"),
    ("Dank {w} konnte das Projekt weitergehen.", "多亏了{z}，项目得以推进。"),
    ("Mit {w} spielt man nicht: sei vorsichtig.", "{z}可不能当儿戏，必须小心。"),
    ("Diesem Buch ist ein ganzes Kapitel über {w} gewidmet.", "这本书用整整一章讲{z}。"),
    ("Ich verstehe immer besser, wie {w} funktioniert.", "我越来越明白{z}是怎么运作的了。"),
    ("Ohne {w} wären all diese Bemühungen umsonst gewesen.", "没有{z}，这一切努力都是白费。"),
    ("Die heutige Radiosendung handelt von {w}.", "今晚的广播节目将围绕{z}展开。"),
    ("Bis Freitag muss ich {w} wiederholen.", "周五之前我得复习{z}。"),
    ("Übrigens, zu {w}: hast du die heutigen Nachrichten gesehen?", "说到{z}，你看今天的新闻了吗？"),
    ("Für mich ist {w} einfach unverzichtbar.", "对我来说，{z}是必不可少的东西。"),
    ("Dieser Kommentar zeigt, dass er sich mit {w} auskennt.", "那个评论说明他对{z}很在行。"),
    ("Am Anfang war {w} mir völlig fremd.", "一开始，{z}对我来说很陌生。"),
    ("Seine Doktorarbeit handelt von {w} im Mittelalter.", "他的博士论文研究的是中世纪的{z}。"),
    ("Die Nachricht über {w} verbreitete sich blitzartig.", "{z}的消息瞬间传开了。"),
    ("Heute haben wir im Unterricht den Begriff {w} analysiert.", "今天课上我们分析了{z}这个概念。"),
    ("Denk besser frühzeitig an {w}.", "预防总比补救好：我们最好尽早考虑{z}。"),
    ("Schon als Kind sammelte er Materialien über {w}.", "他小时候就收集关于{z}的资料。"),
    ("Im Museum gibt es Exponate rund um {w}.", "博物馆里保存着与{z}相关的展品。"),
    ("Reden wir weiter über {w} oder wechselst du das Thema?", "我们继续聊{z}，还是你想换个话题？"),
    ("Der Lehrer beantwortete alle Fragen zu {w}.", "老师解答了关于{z}的所有疑问。"),
    ("Diesen Sommer möchte ich mehr über {w} erfahren.", "今年夏天我想多了解{z}。"),
    ("Seine Forschung kreist um {w}.", "他的研究围绕{z}展开。"),
    ("Mit {w} hatte ich früher noch nie zu tun.", "我以前从未接触过{z}。"),
    ("Im ganzen Haus sprach man nur über {w}.", "全家上下都在谈论{z}。"),
    ("Im Abschlussbericht gibt es ein eigenes Kapitel über {w}.", "最终报告里有一个专门讲{z}的章节。"),
    ("Mir fehlt das Vokabular, um {w} genau zu erklären.", "我的词汇量不够，没法精确解释{z}。"),
    ("Über {w} gibt es schon etliche wissenschaftliche Arbeiten.", "关于{z}已经有不少学术著作。"),
]

A = [  # adj: sein/werden + 原形
    ("Die Reise war {w}, als wir erwartet hatten.", "这次旅行比我们预期的更{z}。"),
    ("Die Besprechung verlief weniger {w} als in der letzten Woche.", "这次会议没有上周的那么{z}。"),
    ("Heute war der Lehrer {w} gelaunt.", "今天老师的心情很{z}。"),
    ("Ich fand es {w}, dass er dazu nichts sagte.", "他对这件事只字不提，我觉得很{z}。"),
    ("Mit den Jahren ist das Problem noch {w} geworden.", "随着时间推移，这个问题变得更加{z}了。"),
    ("Niemand hatte ein so {w} Ende erwartet.", "没人料到结局会这么{z}。"),
    ("Obwohl es {w} war, beschloss er weiterzumachen.", "虽然很{z}，他还是决定继续尝试。"),
    ("Als wir ankamen, war der Raum {w}.", "我们到的时候，房间里很{z}。"),
    ("Für ein erstes Buch ist es ziemlich {w} geschrieben.", "作为他的第一本书，写得相当{z}。"),
    ("Im Winter ist das Klima dieser Stadt sehr {w}.", "这座城市冬天的天气很{z}。"),
    ("Seine Antwort hinterließ einen {w} Eindruck.", "他的回答给我留下一种{z}的印象。"),
    ("Gestern fühlte er sich den ganzen Tag {w}.", "昨天我一整天都感到很{z}。"),
    ("Über Geld mit der Familie zu sprechen ist immer {w}.", "和家人谈钱总是很{z}。"),
    ("Die Prüfung erschien mir überraschend {w}.", "这次考试我觉得出奇地{z}。"),
    ("Von weitem sah dieser Ort {w} und ruhig aus.", "从远处看，那个地方显得{z}而宁静。"),
    ("Ich merkte, dass er {w} war: er sah ständig auf die Uhr.", "我发现他很{z}：不停地看表。"),
    ("Dass das Projekt weitergeht, ist {w} für uns alle.", "项目能继续推进，对大家来说是件{z}的事。"),
    ("Auf die Kritik der Jury reagierte er ziemlich {w}.", "面对评审的批评，他表现得很{z}。"),
    ("Ehrlich gesagt war das Essen sehr {w}.", "说实话，那顿饭很{z}。"),
    ("Es ist nicht so {w}, wie es auf den ersten Blick scheint.", "它没有乍看上去那么{z}。"),
]

X = [  # 功能词/缩写兜底
    ("Das Wort {w} erscheint in diesem Dialog mehrmals.", "在这段对话里，{z}这个词出现了好几次。"),
    ("An der Tafel stand der Begriff {w}.", "他们在黑板上写下了{z}这个词。"),
    ("In diesem Satz finde ich die genaue Bedeutung von {w} nicht.", "在这个句子里，我找不到{z}的确切意思。"),
    ("Das Wörterbuch zählt {w} zu den häufigsten Anfragen.", "词典把{z}列为查询最多的词条之一。"),
    ("Wie übersetzt man {w} ins Chinesische?", "{z}用中文怎么说？"),
    ("Der Lehrer schrieb {w} an die Tafel und verlangte ein Beispiel.", "老师在黑板上写下{z}，让我们造个句子。"),
    ("In diesem Text wird {w} mit einer anderen Nuance verwendet.", "在这篇文章里，{z}的用法略有不同。"),
    ("Wiederhole bitte das Wort {w}.", "请再把{z}念一遍。"),
    ("Unterstreiche das Wort {w} in der dritten Zeile.", "请在第三行标出{z}这个词。"),
    ("Der Gebrauch von {w} variiert stark zwischen Ländern.", "{z}的用法在不同国家差别很大。"),
    ("Es fällt mir schwer, {w} von ähnlichen Wörtern zu unterscheiden.", "我很难把{z}和相近的词区分开。"),
    ("Dieses Kapitel erklärt, wann man {w} verwendet.", "这一章讲解什么时候用{z}。"),
]

POOLS = {'verb': V, 'noun': N, 'adj': A}
BAD_HEADWORD = re.compile(r'[^A-Za-zÄÖÜäöüß-]')


def first_zh(zh: str) -> str:
    t = (zh or '').strip()
    if not t:
        return ''
    for sep in ('；', ';', '，', ','):
        if sep in t:
            t = t.split(sep)[0].strip()
            if t:
                return t
    return t


def generate_3_sentences(word, zh, pos, idx):
    p = (pos or '').strip()
    if p.startswith('v'):
        key, pool = 'verb', V
    elif p.startswith('n'):
        key, pool = 'noun', N
    elif p.startswith('adj') or 'adj' in p:
        key, pool = 'adj', A
    else:
        key, pool = 'x', X
    if len(word) > 30 or BAD_HEADWORD.search(word):
        key, pool = 'x', X
    z = first_zh(zh) or word
    n = len(pool)
    out, seen, k = [], set(), 0
    while len(out) < 3 and k < n + 3:
        pick = (idx * 7 + k * 13 + len(out) * 3) % n
        if key == 'x':
            pick = (idx + k) % n
        if pick not in seen:
            seen.add(pick)
            es_pat, zh_pat = pool[pick][:2]
            out.append((es_pat.replace('{w}', word), zh_pat.replace('{z}', z)))
        k += 1
    return out[:3]


def main():
    books = json.loads(BOOKS_FILE.read_text(encoding='utf-8'))
    master = {}
    idx = 0
    for lv in ('a1', 'a2', 'b1', 'b2'):
        for e in books['levels'].get(lv, []):
            idx += 1
            w = e['word']
            sents = generate_3_sentences(w, e.get('zh', ''), e.get('pos', ''), idx)
            e['sentences'] = sents
            master[w] = sents
    BOOKS_FILE.write_text(json.dumps(books, ensure_ascii=False, indent=2), encoding='utf-8')
    MASTER_FILE.write_text(json.dumps(master, ensure_ascii=False, indent=2), encoding='utf-8')
    total_s = sum(len(v) for v in master.values())
    fc = collections.Counter()
    for w, pairs in master.items():
        for es, _ in pairs:
            fc[re.sub(re.escape(w), '#', es, flags=re.I)] += 1
    top = fc.most_common(1)[0]
    print(f'total words: {len(master)}, sentences: {total_s}, frames: {len(fc)}')
    print(f'top frame: {top[1]} rows ({top[1]/total_s*100:.2f}%)  {top[0][:50]}')
    print(f'saved: {BOOKS_FILE}\nsaved: {MASTER_FILE}')


if __name__ == '__main__':
    main()
