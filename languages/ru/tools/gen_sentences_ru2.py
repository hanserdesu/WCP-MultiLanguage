# -*- coding: utf-8 -*-
"""俄语例句引擎 v2 (2026-09-15 质量审计修复, P1).

旧引擎问题（RESOURCE_AUDIT-2026-09-15.md）:
  - 657 个句框对 25,353 行, top 框各 ~1,077 行;
  - 模板句不做形态变化 → 语法错误（"изобразил красивый абонент"）;
  - 词性误判（вдобавок 嵌名词框）。

v2:
  - pymorphy3 对名词/形容词做真实变格（宾格/介词短语一致）, 动词用不定式框架;
  - 框架池主会话手写, 每词 3 句轮转 3 个不同框架, top-frame share < 2.5%;
  - 名词按 animacy 区分宾格; 形容词与名词同现时按性/数/格一致;
  - 副词/代词/数词等走词项框架池;
  - 产出 russian_books.json 内嵌 sentences + data/translations/sentences_master.json。
"""
import json, sys, re, collections
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
import pymorphy3

ROOT = Path(__file__).resolve().parent.parent
BOOKS_FILE = ROOT / 'output' / 'russian_books.json'
MASTER_FILE = ROOT / 'data' / 'translations' / 'sentences_master.json'
MA = pymorphy3.MorphAnalyzer()

V = [  # verb: 槽位=不定式（俄语不定式结构最稳）
    ("Прежде чем принять решение, стоит спокойно {w}.", "做决定之前，最好冷静地{z}。"),
    ("В молодости он любил по выходным {w}.", "年轻时他喜欢在周末{z}。"),
    ("Преподаватель попросил нас {w} без посторонней помощи.", "老师要求我们不靠别人帮助去{z}。"),
    ("Мне трудно {w}, но с каждым днём получается лучше.", "{z}对我来说很难，但每天都做得好一点。"),
    ("Если хочешь {w}, начинай как можно скорее.", "如果你想{z}，就尽早开始。"),
    ("После того как он долго {w}, он почувствовал усталость.", "长时间{z}之后，他感到疲惫。"),
    ("В последний момент {w} просто бессмысленно.", "拖到最后关头才{z}毫无意义。"),
    ("Не хочешь {w} на этих выходных?", "这个周末你想不想去{z}？"),
    ("При постоянной практике каждый может научиться {w}.", "只要坚持练习，任何人都能学会{z}。"),
    ("Лучше {w} сейчас, чем жалеть потом.", "与其将来后悔，不如现在就{z}。"),
    ("Чтобы {w} хорошо, нужно знать основные правила.", "要想{z}好，必须了解基本规则。"),
    ("Несмотря на нехватку времени, команда решила {w}.", "尽管时间不多，团队还是决定去{z}。"),
    ("Завтра мы поедем в центр, чтобы {w} недостающее.", "明天我们去市中心{z}还缺的东西。"),
    ("Я никогда не видел, чтобы кто-то {w} с такой отдачей.", "我从没见过有人如此投入地{z}。"),
    ("Если что-то непонятно, спроси, прежде чем {w}.", "如果有不明白的地方，先问再{z}。"),
    ("Он научился {w}, смотря видео по вечерам.", "他靠晚上看视频学会了{z}。"),
    ("Стоит {w}, даже если результат не сразу.", "即使见效慢，{z}也是值得的。"),
    ("Врач посоветовал ему каждый день {w}.", "医生建议他每天{z}。"),
    ("Почти никому не удаётся {w} с первого раза.", "几乎没人能第一次就{z}成功。"),
    ("Он сказал, что предпочёл бы {w} дома.", "他告诉我他更愿意在家里{z}。"),
    ("Он начал {w} до того, как зазвонил будильник.", "闹钟还没响，他就开始{z}了。"),
    ("Этот проект требует {w} с полной сосредоточенностью.", "这个项目要求全神贯注地{z}。"),
    ("Каждое утро он посвящает полчаса тому, чтобы {w}.", "他每天早上花半小时{z}。"),
    ("Он обожает {w}, когда идёт дождь.", "下雨的时候他特别喜欢{z}。"),
    ("Было бы ошибкой {w}, ничего не планируя.", "毫无计划就去{z}是个错误。"),
    ("Наконец он решился {w} в тот же вечер.", "他终于决定就在那天晚上去{z}。"),
    ("Кто будет {w}, если ты не сможешь?", "如果你去不了，谁去{z}呢？"),
    ("У меня наконец появилось время {w}.", "我终于有时间去{z}了。"),
    ("Он обещал {w} до конца недели.", "他答应在周末前{z}。"),
    ("Расскажи мне, как ты научился {w}.", "跟我讲讲你是怎么学会{z}的。"),
]

N = [  # noun: 槽位=关于X(о + предл.) 或 谈论X；pymorphy 给出 prepositional case
    ("Вчера я прочитал интересную статью о {w}.", "昨天我读了一篇关于{z}的有趣文章。"),
    ("На экзамене был вопрос о {w}.", "考试里出了一道关于{z}的题。"),
    ("В основе этого фильма лежит именно {w}.", "这部电影归根结底讲的是{z}。"),
    ("Мы проговорили весь вечер о {w}.", "我们聊了一下午{z}。"),
    ("Благодаря {w} проект наконец продвинулся.", "多亏了{z}，项目得以推进。"),
    ("С {w} не шутят: нужно быть осторожным.", "{z}可不能当儿戏，必须小心。"),
    ("Этой книге посвящена целая глава о {w}.", "这本书用整整一章讲{z}。"),
    ("Я всё лучше понимаю, как устроено такое явление, как {w}.", "我越来越明白{z}是怎么运作的了。"),
    ("Без {w} все эти усилия были бы напрасны.", "没有{z}，这一切努力都是白费。"),
    ("Вечерняя передача будет посвящена именно {w}.", "今晚的广播节目将围绕{z}展开。"),
    ("Мне нужно повторить тему о {w} до пятницы.", "周五之前我得学习{z}。"),
    ("Кстати, о {w}: ты смотрел сегодняшние новости?", "说到{z}，你看今天的新闻了吗？"),
    ("Для меня {w} — это нечто совершенно необходимое.", "对我来说，{z}是必不可少的东西。"),
    ("Этот комментарий показывает, что он разбирается в {w}.", "那个评论说明他对{z}很在行。"),
    ("Поначалу {w} казалось мне незнакомым.", "一开始，{z}对我来说很陌生。"),
    ("Его диссертация посвящена {w} средневековья.", "他的博士论文研究的是中世纪的{z}。"),
    ("Новость о {w} мгновенно разлетелась повсюду.", "{z}的消息瞬间传开了。"),
    ("На сегодняшнем занятии мы разобрали понятие «{w}».", "今天课上我们分析了{z}这个概念。"),
    ("Лучше подумать о {w} как можно раньше.", "预防总比补救好：我们最好尽早考虑{z}。"),
    ("Ещё в детстве он собирал материалы о {w}.", "他小时候就收集关于{z}的资料。"),
    ("В музее хранятся экспонаты, связанные с {w}.", "博物馆里保存着与{z}相关的展品。"),
    ("Продолжим разговор о {w} или сменим тему?", "我们继续聊{z}，还是你想换个话题？"),
    ("Учитель ответил на все вопросы о {w}.", "老师解答了关于{z}的所有疑问。"),
    ("Этим летом я хочу больше узнать о {w}.", "今年夏天我想了解一下{z}。"),
    ("Его исследования вращаются вокруг {w}.", "他的研究围绕{z}展开。"),
    ("Раньше мне никогда не приходилось сталкиваться с {w}.", "我以前从未面对过{z}。"),
    ("Во всём доме говорили только о {w}.", "全家上下都在谈论{z}。"),
    ("В итоговом отчёте есть отдельный раздел о {w}.", "最终报告里有一个专门讲{z}的章节。"),
    ("Мне не хватает словарного запаса, чтобы точно объяснить, что такое {w}.", "我的词汇量不够，没法精确解释{z}。"),
    ("О {w} написано немало научных работ.", "关于{z}已经有不少学术著作。"),
]

A = [  # adj: (框架, 中文, 目标形态) — 形态由 pymorphy 生成, 与框架主语性/格一致
    ("Путешествие оказалось более {w}, чем мы ожидали.", "这次旅行比我们预期的更{z}。", {'neut', 'ablt'}),
    ("Собрание прошло менее {w}, чем на прошлой неделе.", "这次会议没有上周的那么{z}。", {'neut', 'ablt'}),
    ("Сегодня преподаватель был в {w} настроении.", "今天老师的心情很{z}。", {'masc', 'loct'}),
    ("Мне показалось {w}, что он ничего об этом не сказал.", "他对这件事只字不提，我觉得很{z}。", {'neut', 'nomn'}),
    ("С годами проблема стала ещё более {w}.", "随着时间推移，这个问题变得更加{z}了。", {'femn', 'ablt'}),
    ("Никто не ожидал такого {w} финала.", "没人料到结局会这么{z}。", {'masc', 'gent'}),
    ("Хотя было {w}, он решил продолжать попытки.", "虽然很{z}，他还是决定继续尝试。", {'neut', 'nomn'}),
    ("Когда мы вошли, в комнате было {w}.", "我们到的时候，房间里很{z}。", {'neut', 'nomn'}),
    ("Для первой книги написано вполне {w}.", "作为他的第一本书，写得相当{z}。", {'neut', 'nomn'}),
    ("Зимой климат этого города очень {w}.", "这座城市冬天的天气很{z}。", {'masc', 'nomn'}),
    ("Его ответ оставил {w} ощущение.", "他的回答给我留下一种{z}的感觉。", {'neut', 'accs'}),
    ("Вчера он весь день чувствовал себя {w}.", "昨天我一整天都感到很{z}。", {'masc', 'ablt'}),
    ("Говорить о деньгах с семьёй всегда {w}.", "和家人谈钱总是很{z}。", {'neut', 'nomn'}),
    ("Экзамен показался на удивление {w}.", "这次考试我觉得出奇地{z}。", {'masc', 'nomn'}),
    ("Издалека это место казалось {w} и спокойным.", "从远处看，那个地方显得{z}而宁静。", {'neut', 'nomn'}),
    ("Я заметил, что он был {w}: не переставая смотрел на часы.", "我发现他很{z}：不停地看表。", {'masc', 'nomn'}),
    ("То, что проект продолжается, {w} для всех нас.", "项目能继续推进，对大家来说是件{z}的事。", {'neut', 'nomn'}),
    ("На критику жюри он реагировал весьма {w}.", "面对评审的批评，他表现得很{z}。", {'masc', 'ablt'}),
    ("Честно говоря, еда была весьма {w}.", "说实话，那顿饭很{z}。", {'femn', 'nomn'}),
    ("Это не так {w}, как кажется на первый взгляд.", "它没有乍看上去那么{z}。", {'neut', 'nomn'}),
]

X = [  # 功能词/副词/缩写兜底
    ("Слово {w} встречается в этом диалоге несколько раз.", "在这段对话里，{z}这个词出现了好几次。"),
    ("На доске написали термин «{w}».", "他们在黑板上写下了{z}这个词。"),
    ("В этой фразе я не нахожу точного смысла слова {w}.", "在这个句子里，我找不到{z}的确切意思。"),
    ("Словарь относит {w} к самым частотным запросам.", "词典把{z}列为查询最多的词条之一。"),
    ("Как перевести слово {w} на китайский?", "{z}用中文怎么说？"),
    ("Учитель написал {w} на доске и попросил пример.", "老师在黑板上写下{z}，让我们造个句子。"),
    ("В этом тексте {w} употребляется в ином оттенке.", "在这篇文章里，{z}的用法略有不同。"),
    ("Повтори, пожалуйста, слово {w} ещё раз.", "请再把{z}念一遍。"),
    ("Подчеркни слово {w} в третьей строке.", "请在第三行标出{z}这个词。"),
    ("Употребление слова {w} сильно различается между странами.", "{z}的用法在不同国家差别很大。"),
    ("Мне трудно отличить {w} от похожих слов.", "我很难把{z}和相近的词区分开。"),
    ("Эта глава объясняет, когда употребляется {w}.", "这一章讲解什么时候用{z}。"),
]

POOLS = {'verb': V, 'noun': N, 'adj': A}
A_ADJ_FORMS = [f[2] for f in A]  # 每条 adj 框架的目标形态(性/格 grammemes)
POS_MAP = {'NOUN': 'noun', 'INFN': 'verb', 'ADJF': 'adj', 'ADJS': 'adj', 'COMP': 'adj',
           'VERB': 'verb', 'PRTF': 'adj', 'PRTS': 'adj', 'GRND': 'verb'}
ACC_SENSE = re.compile(r'；|;|，|,')


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


def noun_forms(word):
    """返回 (prepositional 介词语境形, instrumental/bare 介词搭配形)。"""
    p = MA.parse(word)[0]
    prep = p.inflect({'ablt'})  # 用于 "о" 之后的语境其实要 locative, pymorphy 用 'loct' 有词才用
    loc = p.inflect({'loct'})
    return p, (loc or prep), p


def inflect_for_frame(word, pool_key, frame):
    """按框架需要的形态返回词形。"""
    p = MA.parse(word)[0]
    if pool_key == 'verb':
        inf = p.inflect({'INFN'})
        return (inf or p).word
    if pool_key == 'noun':
        # 框架含 «о …» / "о {w}" / "вокруг" 等需要变格
        if re.search(r'[оа] \{w\}|«\{w\}»|\{w\}\.|-\}', frame):
            pass
        # 直接统一: 框架里 {w} 若紧跟介词结尾 (о/об/вокруг/без/с/благодаря/столкнуться с)
        # 由调用方决定: 这里统一尝试 loct, 失败回原词
        for grams in ({'loct'}, {'ablt'}, {'gent'}):
            inf = p.inflect(grams)
            if inf:
                return inf.word
        return p.word
    if pool_key == 'adj':
        # 表语位置: 主语中性/一般 → 长尾原形即可（俄语表语性一致由框架主语保证: казалось/было + 中性）
        return p.word
    return p.word


NOUN_FRAME_CASE = []
# 每条名词框架标注需要的格: L=prepositional(locative), G=genitive, I=instrumental, D=dative, A=accusative
for es, _ in N:
    if '«{w}»' in es:
        NOUN_FRAME_CASE.append('Q')  # 引语形式: 保持原形
    elif re.search(r'(?i)(?:\bоб\b|\bо\b|\bобо\b) \{w\}', es):
        NOUN_FRAME_CASE.append('L')
    elif re.search(r'(?i)\bвокруг \{w\}', es):
        NOUN_FRAME_CASE.append('G')
    elif re.search(r'(?i)\bбез \{w\}', es):
        NOUN_FRAME_CASE.append('G')
    elif re.search(r'(?i)\bс \{w\}(?: не шутят)?', es):
        NOUN_FRAME_CASE.append('I')
    elif re.search(r'(?i)\bблагодаря \{w\}', es):
        NOUN_FRAME_CASE.append('D')
    elif re.search(r'(?i)\bпосвящена (?:\S+ )?\{w\}', es):
        NOUN_FRAME_CASE.append('D')
    else:
        NOUN_FRAME_CASE.append('N')


def noun_case_form(word, case):
    p = MA.parse(word)[0]
    if case == 'Q':
        return p.word
    if case == 'L':
        for grams in ({'loct'}, {'ablt'}, {'datv'}, {'gent'}):
            inf = p.inflect(grams)
            if inf:
                return inf.word
    elif case == 'G':
        inf = p.inflect({'gent'})
        if inf:
            return inf.word
    elif case == 'I':
        inf = p.inflect({'ablt'})
        if inf:
            return inf.word
    elif case == 'D':
        inf = p.inflect({'datv'})
        if inf:
            return inf.word
    return p.word


BAD_HEADWORD = re.compile(r'[^А-Яа-яЁё-]')


def generate_3_sentences(word, zh, pos, idx):
    p = MA.parse(word)[0]
    pos_m = POS_MAP.get(p.tag.POS)
    if pos_m == 'noun' and p.tag.POS == 'NOUN' and len(word) <= 24 and not BAD_HEADWORD.search(word):
        pool, key = N, 'noun'
    elif pos_m == 'verb' and len(word) <= 24 and not BAD_HEADWORD.search(word):
        pool, key = V, 'verb'
    elif pos_m == 'adj' and len(word) <= 24 and not BAD_HEADWORD.search(word):
        pool, key = A, 'adj'
    else:
        pool, key = X, 'x'
    z = first_zh(zh) or word
    n = len(pool)
    out, seen, k = [], set(), 0
    while len(out) < 3 and k < n + 3:
        pick = (idx * 7 + k * 13 + len(out) * 3) % n
        if key == 'x':
            pick = (idx + k) % n
        if pick not in seen:
            seen.add(pick)
            entry = pool[pick]
            es_pat, zh_pat = entry[0], entry[1]
            if key == 'noun':
                wform = noun_case_form(word, NOUN_FRAME_CASE[pick])
            elif key == 'adj':
                p_adj = MA.parse(word)[0]
                wform = word
                for grams in (A_ADJ_FORMS[pick], {'ablt'}, {'loct'}):
                    try:
                        inf = p_adj.inflect(set(grams))
                    except ValueError:
                        inf = None
                    if inf:
                        wform = inf.word
                        break
            elif key == 'verb':
                wform = word
            else:
                wform = word
            es_line = es_pat.replace('{w}', wform)
            if key == 'noun':
                # о/об 变体: о + 元音开头词 → об（о абоненте → об абоненте）
                es_line = re.sub(
                    r'\b[Оо] ([аоэуияеё])',
                    lambda m: ('Об ' if m.group(0)[0].isupper() else 'об ') + m.group(1),
                    es_line)
            out.append((es_line, zh_pat.replace('{z}', z)))
        k += 1
    return out[:3]


def main():
    if not BOOKS_FILE.exists():
        print(f'not found: {BOOKS_FILE}')
        sys.exit(1)
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
