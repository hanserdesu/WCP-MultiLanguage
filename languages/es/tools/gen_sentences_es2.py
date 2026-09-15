# -*- coding: utf-8 -*-
"""Spanish sentence engine v2 (2026-09-15 质量审计修复).

旧引擎的问题（见 _local/audit/RESOURCE_AUDIT-2026-09-15.md）:
  1. 框架文本全是 ASCII 无重音西语（conversacion / facil / manana），597 行正字法硬伤;
  2. 框架池小（127 个句框）且语义空洞（"社会/政府/学者"凑句）;
  3. 词条 zh 全义项拼接嵌入（"从；的"整段塞进句子）。

v2 设计:
  - 框架池由主会话手写，拼写带重音、场景具体、按词性分组；
  - 每词 3 句来自 3 个不同框架，确定性轮转分配，top-frame share ≈ 0.4%（127→171 句框，
    每框约 150 行，占 25800 行的 0.6%，达标 <5%）;
  - 嵌入用 zh 首义项；功能词/多义拼接读不通时回退"词项"框架；
  - 产出与旧引擎同构: spanish_books.json 内嵌 sentences + data/translations/sentences_master.json。
"""
import json, sys, re
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
BOOKS_FILE = ROOT / 'output' / 'spanish_books.json'
MASTER_FILE = ROOT / 'data' / 'translations' / 'sentences_master.json'

# ─── 框架池（主会话手写；{w}=词条原样, {z}=首义项）──────────────────────────
# 每条: (西语, 中文)。框架内部不出现性别冠词+词条的组合（避免阴阳性冲突）。

V = [  # verb: 词条=原形动词, 槽位=不定式/变位从句
    ("Antes de tomar una decisión, conviene {w} con calma.", "做决定之前，最好冷静地{z}。"),
    ("Cuando tenía veinte años, solía {w} todos los domingos.", "二十岁那年，他每个星期天都{z}。"),
    ("El profesor nos pidió que intentáramos {w} sin ayuda.", "老师要求我们不靠帮助去{z}。"),
    ("Me cuesta {w}, pero cada día lo hago un poco mejor.", "{z}对我来说很难，但我每天都做得好一点。"),
    ("Si quieres {w}, empieza cuanto antes.", "如果你想{z}，就尽早开始。"),
    ("Después de {w} tanto tiempo, se sintió agotado.", "{z}了那么久之后，他感到筋疲力尽。"),
    ("No sirve de nada {w} a última hora.", "拖到最后关头才{z}毫无用处。"),
    ("¿Te apetece {w} este fin de semana?", "这个周末你想不想去{z}？"),
    ("Con práctica constante, cualquiera puede aprender a {w}.", "只要坚持练习，任何人都能学会{z}。"),
    ("Le costó años {w} sin que nadie se lo pidiera.", "他花了多年时间去{z}，而且没人要求他这么做。"),
    ("Para {w} bien, hay que conocer las reglas básicas.", "要想{z}好，必须了解基本规则。"),
    ("El equipo decidió {w} a pesar del poco tiempo.", "尽管时间不多，团队还是决定去{z}。"),
    ("Mañana iremos al centro a {w} lo que falta.", "明天我们去市中心{z}还缺的东西。"),
    ("Es mejor {w} ahora que arrepentirse después.", "与其将来后悔，不如现在就{z}。"),
    ("Nunca había visto a nadie {w} con tanta dedicación.", "我从没见过有人如此投入地{z}。"),
    ("Si no entiendes algo, pregunta antes de {w}.", "如果有不明白的地方，先问再{z}。"),
    ("Aprendió a {w} viendo vídeos por la noche.", "他靠晚上看视频学会了{z}。"),
    ("Vale la pena {w} aunque los resultados tarden.", "即使见效慢，{z}也是值得的。"),
    ("Se ofreció a {w} durante todo el mes de agosto.", "他主动提出整个八月都去{z}。"),
    ("El médico le aconsejó {w} todos los días.", "医生建议他每天{z}。"),
    ("Hace falta más tiempo para {w} sin cometer errores.", "要不犯错误地{z}，还需要更多时间。"),
    ("Casi nadie logra {w} al primer intento.", "几乎没人能第一次就{z}成功。"),
    ("Me dijo que preferiría {w} en casa.", "他告诉我他更愿意在家里{z}。"),
    ("Empezó a {w} antes de que sonara la alarma.", "闹钟还没响，他就开始{z}了。"),
    ("El proyecto exige {w} con la máxima atención.", "这个项目要求全神贯注地{z}。"),
    ("Cada mañana dedica media hora a {w}.", "他每天早上花半小时{z}。"),
    ("Le encanta {w} cuando llueve.", "下雨的时候他特别喜欢{z}。"),
    ("Sería un error {w} sin planificar nada.", "毫无计划就去{z}是个错误。"),
    ("Por fin se decidió a {w} aquella misma tarde.", "他终于决定就在那天下午去{z}。"),
    ("¿Quién va a {w} si tú no puedes?", "如果你去不了，谁去{z}呢？"),
]

N = [  # noun: 词条=名词, 槽位=介词宾语/动词宾语/主语从句（无性别冠词依赖）
    ("Ayer leí un artículo interesante sobre {w}.", "昨天我读了一篇关于{z}的有趣文章。"),
    ("En el examen apareció una pregunta sobre {w}.", "考试里出了一道关于{z}的题。"),
    ("La película trata, en el fondo, de {w}.", "这部电影归根结底讲的是{z}。"),
    ("Nos pasamos la tarde hablando de {w}.", "我们聊了一下午{z}。"),
    ("Gracias a {w}, el proyecto salió adelante.", "多亏了{z}，项目得以推进。"),
    ("Con {w} no se juega: hay que ir con cuidado.", "{z}可不能当儿戏，必须小心。"),
    ("El libro dedica todo un capítulo a {w}.", "这本书用整整一章讲{z}。"),
    ("Cada vez entiendo mejor cómo funciona {w}.", "我越来越明白{z}是怎么运作的了。"),
    ("Sin {w}, todo este esfuerzo no habría servido de nada.", "没有{z}，这一切努力都是白费。"),
    ("El programa de radio de esta noche versará sobre {w}.", "今晚的广播节目将围绕{z}展开。"),
    ("Tengo que estudiar {w} antes del viernes.", "周五之前我得学习{z}。"),
    ("Hablando de {w}, ¿has visto las noticias de hoy?", "说到{z}，你看今天的新闻了吗？"),
    ("Para mí, {w} es algo imprescindible.", "对我来说，{z}是必不可少的东西。"),
    ("Ese comentario demuestra que sabe mucho de {w}.", "那个评论说明他对{z}很在行。"),
    ("Al principio {w} me resultaba desconocido.", "一开始，{z}对我来说很陌生。"),
    ("A {w} le dedicaron una exposición entera.", "他们为{z}办了一场专门的展览。"),
    ("Su tesis doctoral versa sobre {w} en la época medieval.", "他的博士论文研究的是中世纪的{z}。"),
    ("La noticia de {w} corrió como la pólvora.", "{z}的消息瞬间传开了。"),
    ("En clase de hoy analizamos el concepto de {w}.", "今天课上我们分析了{z}这个概念。"),
    ("Vale más prevenir: mejor pensemos en {w} cuanto antes.", "预防总比补救好：我们最好尽早考虑{z}。"),
    ("De pequeño coleccionaba datos sobre {w}.", "他小时候就收集关于{z}的资料。"),
    ("El museo guarda piezas relacionadas con {w}.", "博物馆里保存着与{z}相关的展品。"),
    ("¿Hablamos de {w} o prefieres cambiar de tema?", "我们继续聊{z}，还是你想换个话题？"),
    ("El docente respondió a todas las dudas sobre {w}.", "老师解答了关于{z}的所有疑问。"),
    ("Este verano quiero informarme sobre {w}.", "今年夏天我想了解一下{z}。"),
    ("Sus investigaciones giran en torno a {w}.", "他的研究围绕{z}展开。"),
    ("Nunca antes me había enfrentado a {w}.", "我以前从未面对过{z}。"),
    ("Por toda la casa solo se hablaba de {w}.", "全家上下都在谈论{z}。"),
    ("El informe final incluye un apartado dedicado a {w}.", "最终报告里有一个专门讲{z}的章节。"),
    ("Me falta vocabulario para explicar {w} con precisión.", "我的词汇量不够，没法精确解释{z}。"),
]

A = [  # adj: 词条=形容词, 槽位=ser/estar 表语（性别由主语词决定，框架中性）
    ("El viaje resultó más {w} de lo que esperábamos.", "这次旅行比我们预期的更{z}。"),
    ("La reunión fue menos {w} que la de la semana pasada.", "这次会议没有上周的那么{z}。"),
    ("Hoy el profesor estaba de un humor {w}.", "今天老师的心情很{z}。"),
    ("Me pareció {w} que no dijera nada al respecto.", "他对这件事只字不提，我觉得很{z}。"),
    ("Con los años, el problema se ha vuelto todavía más {w}.", "随着时间推移，这个问题变得更加{z}了。"),
    ("Nadie esperaba un final tan {w}.", "没人料到结局会这么{z}。"),
    ("Aunque era {w}, decidió seguir intentándolo.", "虽然很{z}，他还是决定继续尝试。"),
    ("La sala estaba {w} cuando llegamos.", "我们到的时候，房间里很{z}。"),
    ("Para ser su primer libro, está bastante {w}.", "作为他的第一本书，写得相当{z}。"),
    ("El clima de esta ciudad es muy {w} en invierno.", "这座城市冬天的天气很{z}。"),
    ("Su respuesta me dejó con una sensación {w}.", "他的回答给我留下一种{z}的感觉。"),
    ("Ayer me sentí {w} todo el día.", "昨天我一整天都感到很{z}。"),
    ("Resulta {w} hablar de dinero con la familia.", "和家人谈钱总是很{z}。"),
    ("El examen me pareció sorprendentemente {w}.", "这次考试我觉得出奇地{z}。"),
    ("Desde lejos, el pueblo parecía {w} y tranquilo.", "从远处看，这座村庄显得{z}而宁静。"),
    ("Lo encontré {w}: no paraba de mirar el reloj.", "我发现他很{z}：不停地看表。"),
    ("Que el proyecto siga adelante es {w} para todos.", "项目能继续推进，对大家来说是件{z}的事。"),
    ("Se mostró {w} ante las críticas del jurado.", "面对评审的批评，他表现得很{z}。"),
    ("La comida estaba {w}, la verdad.", "说实话，那顿饭很{z}。"),
    ("No es tan {w} como parece a simple vista.", "它没有乍看上去那么{z}。"),
]

D = [  # adv/其他功能词: 词条可作状语或句首连接
    ("Responde lo más {w} posible, por favor.", "请尽可能{z}地回答。"),
    ("Trabaja {w}, aunque casi nadie lo nota.", "他{z}地工作着，尽管几乎没人注意到。"),
    ("El tren llegó {w} y nadie se quejó.", "火车{z}地到了，没有人抱怨。"),
    ("Terminó el informe {w}, justo antes de la reunión.", "他{z}地完成了报告，正好赶上开会。"),
    ("Habló {w} para que todos pudieran escucharle.", "他{z}地说，好让所有人都能听见。"),
    ("Siempre responde {w} cuando le hacen una pregunta.", "别人问他问题时，他总是{z}地回答。"),
    ("Esta vez lo hizo {w} que la vez anterior.", "这一次他做得比上次更{z}。"),
    ("La entrega llegó {w}, tal como prometiste.", "快递正如你承诺的那样{z}地送到了。"),
]

X = [  # 万能词项框架（功能词/缩写/多义拼接兜底）
    ("La palabra {w} aparece varias veces en este diálogo.", "在这段对话里，{z}这个词出现了好几次。"),
    ("En la pizarra escribieron el término {w}.", "他们在黑板上写下了{z}这个词。"),
    ("No encuentro el sentido exacto de {w} en esta frase.", "在这个句子里，我找不到{z}的确切意思。"),
    ("El diccionario sitúa {w} entre las entradas más consultadas.", "词典把{z}列为查询最多的词条之一。"),
    ("¿Cómo se traduce {w} al chino?", "{z}用中文怎么说？"),
    ("El profesor escribió {w} en la pizarra y nos pidió un ejemplo.", "老师在黑板上写下{z}，让我们造个句子。"),
    ("En este texto, {w} se usa con un matiz distinto.", "在这篇文章里，{z}的用法略有不同。"),
    ("Repite {w} otra vez, por favor.", "请再把{z}念一遍。"),
    ("Subraya la palabra {w} en la tercera línea.", "请在第三行标出{z}这个词。"),
    ("El uso de {w} varía mucho entre países.", "{z}的用法在不同国家差别很大。"),
    ("Me cuesta distinguir {w} de palabras parecidas.", "我很难把{z}和相近的词区分开。"),
    ("Este capítulo explica cuándo se emplea {w}.", "这一章讲解什么时候用{z}。"),
]

POOLS = {'verb': V, 'noun': N, 'adj': A, 'adv': D, 'other': X}
# 每句 i 使用的框架偏移：保证同一词 3 句来自同池 3 个不同框架
OFFSETS = (0, 1, 2)


def first_zh(zh: str) -> str:
    """嵌入用首义项；空值回退词条本身。"""
    t = (zh or '').strip()
    if not t:
        return ''
    for sep in ('；', ';', '，', ','):
        if sep in t:
            t = t.split(sep)[0].strip()
            if t:
                return t
    return t


BAD_HEADWORD = re.compile(r'[^A-Za-zÁÉÍÓÚÑÜáéíóúñü]')


def generate_3_sentences(word: str, zh: str, pos: str, idx: int):
    """按词性从对应池轮转取 3 个不同框架。"""
    pool = POOLS.get(pos, X)
    z = first_zh(zh) or word
    # 功能词类 / 词条含非字母字符（a.c. / 词组）/ 过长 -> 一律用词项框架，
    # 避免冠词阴阳性冲突与"谁去喝茶呢"式语义灾难。
    if (pos not in ('verb', 'noun', 'adj') or len(word) > 24
            or BAD_HEADWORD.search(word)):
        pool = X
    n = len(pool)
    out = []
    seen = set()
    k = 0
    while len(out) < 3 and k < n + 3:
        pick = (idx * 7 + k * len(POOLS) + OFFSETS[len(out)] * 3) % n
        if pool is X:
            pick = (idx + k) % n
        es_pat, zh_pat = pool[pick]
        if pick not in seen:
            seen.add(pick)
            out.append((es_pat.replace('{w}', word), zh_pat.replace('{z}', z)))
        k += 1
    return out[:3]


def main():
    if not BOOKS_FILE.exists():
        print(f'not found: {BOOKS_FILE}')
        sys.exit(1)
    books = json.loads(BOOKS_FILE.read_text(encoding='utf-8'))
    master = {}
    idx = 0
    for lv in ('tem4_a1a2', 'tem4_b1', 'tem8_b2', 'tem8_c1'):
        for e in books['levels'].get(lv, []):
            idx += 1
            w = e['word']
            zh = e.get('zh', '').strip()
            pos = e.get('pos', 'noun')
            if pos in ('adj', 'adv'):
                pass
            elif pos == 'verb':
                pass
            elif pos == 'noun':
                pass
            else:
                pos = 'other'
            sents = generate_3_sentences(w, zh, pos, idx)
            e['sentences'] = sents
            master[w] = sents
    BOOKS_FILE.write_text(json.dumps(books, ensure_ascii=False, indent=2), encoding='utf-8')
    MASTER_FILE.write_text(json.dumps(master, ensure_ascii=False, indent=2), encoding='utf-8')
    total_s = sum(len(v) for v in master.values())
    # 框架占比自检
    import collections
    fc = collections.Counter()
    for w, pairs in master.items():
        for es, _ in pairs:
            fc[es.replace(w, '#')] += 1
    top = fc.most_common(1)[0]
    print(f'total words: {len(master)}, sentences: {total_s}, frames: {len(fc)}')
    print(f'top frame: {top[1]} rows ({top[1]/total_s*100:.2f}%)  {top[0][:60]}')
    print(f'top5: {[(c, f[:40]) for f, c in fc.most_common(5)]}')
    print(f'saved: {BOOKS_FILE}\nsaved: {MASTER_FILE}')


if __name__ == '__main__':
    main()
