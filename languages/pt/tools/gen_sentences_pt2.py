import collections
# -*- coding: utf-8 -*-
"""Portuguese sentence engine v2 (2026-09-15 质量审计修复, P0).

旧引擎问题: 模板整套是西班牙语（Debemos/decidio/abajo…），8,600 词的例句
全部是"西语框架+葡语词条"，审计判定 12.3% 西语污染、整体语种错误。

v2: 主会话手写欧洲葡萄牙语框架池（带正确重音符号与变位），
    结构与 Spanish/tools/gen_sentences_es2.py 相同:
      - 词性分组轮转取 3 个不同框架, top-frame share ~2.5%;
      - 功能词/词组/超长词走词项框架池;
      - 产出 portuguese_books.json 内嵌 sentences + sentences_master.json。
"""
import json, sys, re
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
BOOKS_FILE = ROOT / 'output' / 'portuguese_books.json'
MASTER_FILE = ROOT / 'data' / 'translations' / 'sentences_master.json'
LEMMA_FILE = ROOT / 'data' / 'lemma_pt.json'

V = [  # verb: 槽位=不定式
    ("Antes de tomar uma decisão, convém {w} com calma.", "做决定之前，最好冷静地{z}。"),
    ("Quando tinha vinte anos, costumava {w} aos domingos.", "二十岁那年，他每个星期天都{z}。"),
    ("O professor pediu-nos que tentássemos {w} sem ajuda.", "老师要求我们不靠帮助去{z}。"),
    ("Tenho dificuldade em {w}, mas melhora todos os dias.", "{z}对我来说很难，但每天都在进步。"),
    ("Se queres {w}, começa o quanto antes.", "如果你想{z}，就尽早开始。"),
    ("Depois de {w} tanto tempo, sentiu-se esgotado.", "{z}了那么久之后，他感到筋疲力尽。"),
    ("Não adianta nada {w} à última da hora.", "拖到最后关头才{z}毫无用处。"),
    ("Apetece-te {w} este fim de semana?", "这个周末你想不想去{z}？"),
    ("Com prática constante, qualquer pessoa consegue aprender a {w}.", "只要坚持练习，任何人都能学会{z}。"),
    ("Levou anos a {w} sem que ninguém lho pedisse.", "他花了多年时间去{z}，而且没人要求他这么做。"),
    ("Para {w} bem, é preciso conhecer as regras básicas.", "要想{z}好，必须了解基本规则。"),
    ("A equipa decidiu {w} apesar do pouco tempo.", "尽管时间不多，团队还是决定去{z}。"),
    ("Amanhã vamos ao centro para {w} o que falta.", "明天我们去市中心{z}还缺的东西。"),
    ("É melhor {w} agora do que arrepender-se depois.", "与其将来后悔，不如现在就{z}。"),
    ("Nunca tinha visto ninguém {w} com tanta dedicação.", "我从没见过有人如此投入地{z}。"),
    ("Se não percebes algo, pergunta antes de {w}.", "如果有不明白的地方，先问再{z}。"),
    ("Aprendeu a {w} vendo vídeos à noite.", "他靠晚上看视频学会了{z}。"),
    ("Vale a pena {w}, mesmo que os resultados demorem.", "即使见效慢，{z}也是值得的。"),
    ("Ofereceu-se para {w} durante todo o mês de agosto.", "他主动提出整个八月都去{z}。"),
    ("O médico aconselhou-o a {w} todos os dias.", "医生建议他每天{z}。"),
    ("É preciso mais tempo para {w} sem cometer erros.", "要不犯错误地{z}，还需要更多时间。"),
    ("Quase ninguém consegue {w} à primeira tentativa.", "几乎没人能第一次就{z}成功。"),
    ("Disse-me que preferiria {w} em casa.", "他告诉我他更愿意在家里{z}。"),
    ("Começou a {w} antes de o despertador tocar.", "闹钟还没响，他就开始{z}了。"),
    ("O projeto exige {w} com a máxima atenção.", "这个项目要求全神贯注地{z}。"),
    ("Todas as manhãs dedica meia hora a {w}.", "他每天早上花半小时{z}。"),
    ("Adora {w} quando chove.", "下雨的时候他特别喜欢{z}。"),
    ("Seria um erro {w} sem planear nada.", "毫无计划就去{z}是个错误。"),
    ("Por fim decidiu-se a {w} nessa mesma tarde.", "他终于决定就在那天下午去{z}。"),
    ("Quem vai {w} se tu não podes?", "如果你去不了，谁去{z}呢？"),
]

N = [  # noun
    ("Ontem li um artigo interessante sobre {w}.", "昨天我读了一篇关于{z}的有趣文章。"),
    ("No exame apareceu uma pergunta sobre {w}.", "考试里出了一道关于{z}的题。"),
    ("O filme trata, no fundo, de {w}.", "这部电影归根结底讲的是{z}。"),
    ("Passámos a tarde toda a falar de {w}.", "我们聊了一下午{z}。"),
    ("Graças a {w}, o projeto avançou.", "多亏了{z}，项目得以推进。"),
    ("Com {w} não se brinca: é preciso ter cuidado.", "{z}可不能当儿戏，必须小心。"),
    ("O livro dedica um capítulo inteiro a {w}.", "这本书用整整一章讲{z}。"),
    ("Cada vez percebo melhor como funciona {w}.", "我越来越明白{z}是怎么运作的了。"),
    ("Sem {w}, todo este esforço não teria servido de nada.", "没有{z}，这一切努力都是白费。"),
    ("O programa de rádio desta noite será sobre {w}.", "今晚的广播节目将围绕{z}展开。"),
    ("Tenho de estudar {w} antes de sexta-feira.", "周五之前我得学习{z}。"),
    ("A falar de {w}, viste as notícias de hoje?", "说到{z}，你看今天的新闻了吗？"),
    ("Para mim, {w} é algo indispensável.", "对我来说，{z}是必不可少的东西。"),
    ("Esse comentário mostra que percebe muito de {w}.", "那个评论说明他对{z}很在行。"),
    ("No início, {w} era-me desconhecido.", "一开始，{z}对我来说很陌生。"),
    ("A {w} dedicaram-lhe uma exposição inteira.", "他们为{z}办了一场专门的展览。"),
    ("A tese dele versa sobre {w} na época medieval.", "他的博士论文研究的是中世纪的{z}。"),
    ("A notícia de {w} espalhou-se como um incêndio.", "{z}的消息瞬间传开了。"),
    ("Na aula de hoje analisámos o conceito de {w}.", "今天课上我们分析了{z}这个概念。"),
    ("Mais vale prevenir: pensemos em {w} o quanto antes.", "预防总比补救好：我们最好尽早考虑{z}。"),
    ("Desde pequeno que colecionava dados sobre {w}.", "他小时候就收集关于{z}的资料。"),
    ("O museu guarda peças relacionadas com {w}.", "博物馆里保存着与{z}相关的展品。"),
    ("Falamos de {w} ou preferes mudar de tema?", "我们继续聊{z}，还是你想换个话题？"),
    ("O professor respondeu a todas as dúvidas sobre {w}.", "老师解答了关于{z}的所有疑问。"),
    ("Este verão quero informar-me sobre {w}.", "今年夏天我想了解一下{z}。"),
    ("As investigações dele giram em torno de {w}.", "他的研究围绕{z}展开。"),
    ("Nunca antes me tinha defrontado com {w}.", "我以前从未面对过{z}。"),
    ("Por toda a casa só se falava de {w}.", "全家上下都在谈论{z}。"),
    ("O relatório final inclui uma secção dedicada a {w}.", "最终报告里有一个专门讲{z}的章节。"),
    ("Falta-me vocabulário para explicar {w} com precisão.", "我的词汇量不够，没法精确解释{z}。"),
]

A = [  # adj
    ("A viagem revelou-se mais {w} do que esperávamos.", "这次旅行比我们预期的更{z}。"),
    ("A reunião foi menos {w} do que a da semana passada.", "这次会议没有上周的那么{z}。"),
    ("Hoje o professor estava de um humor {w}.", "今天老师的心情很{z}。"),
    ("Pareceu-me {w} que não dissesse nada a respeito.", "他对这件事只字不提，我觉得很{z}。"),
    ("Com os anos, o problema tornou-se ainda mais {w}.", "随着时间推移，这个问题变得更加{z}了。"),
    ("Ninguém esperava um final tão {w}.", "没人料到结局会这么{z}。"),
    ("Embora fosse {w}, decidiu continuar a tentar.", "虽然很{z}，他还是决定继续尝试。"),
    ("A sala estava {w} quando chegámos.", "我们到的时候，房间里很{z}。"),
    ("Para ser o primeiro livro dele, está bastante {w}.", "作为他的第一本书，写得相当{z}。"),
    ("O clima desta cidade é muito {w} no inverno.", "这座城市冬天的天气很{z}。"),
    ("A resposta dele deixou-me uma sensação {w}.", "他的回答给我留下一种{z}的感觉。"),
    ("Ontem senti-me {w} o dia inteiro.", "昨天我一整天都感到很{z}。"),
    ("É {w} falar de dinheiro com a família.", "和家人谈钱总是很{z}。"),
    ("O exame pareceu-me surpreendentemente {w}.", "这次考试我觉得出奇地{z}。"),
    ("Visto de longe, o parecia um lugar {w} e tranquilo.", "从远处看，那个地方显得{z}而宁静。"),
    ("Encontrei-o {w}: não parava de olhar para o relógio.", "我发现他很{z}：不停地看表。"),
    ("Que o projeto continue é {w} para todos.", "项目能继续推进，对大家来说是件{z}的事。"),
    ("Mostrou-se {w} perante as críticas do júri.", "面对评审的批评，他表现得很{z}。"),
    ("A comida estava {w}, sinceramente.", "说实话，那顿饭很{z}。"),
    ("Não é tão {w} como parece à primeira vista.", "它没有乍看上去那么{z}。"),
]

X = [  # 功能词/缩写/多义拼接兜底
    ("A palavra {w} aparece várias vezes neste diálogo.", "在这段对话里，{z}这个词出现了好几次。"),
    ("No quadro escreveram o termo {w}.", "他们在黑板上写下了{z}这个词。"),
    ("Não encontro o sentido exato de {w} nesta frase.", "在这个句子里，我找不到{z}的确切意思。"),
    ("O dicionário coloca {w} entre as entradas mais consultadas.", "词典把{z}列为查询最多的词条之一。"),
    ("Como se traduz {w} para chinês?", "{z}用中文怎么说？"),
    ("O professor escreveu {w} no quadro e pediu um exemplo.", "老师在黑板上写下{z}，让我们造个句子。"),
    ("Neste texto, {w} usa-se com um matiz diferente.", "在这篇文章里，{z}的用法略有不同。"),
    ("Repete {w} outra vez, por favor.", "请再把{z}念一遍。"),
    ("Sublinha a palavra {w} na terceira linha.", "请在第三行标出{z}这个词。"),
    ("O uso de {w} varia muito entre países.", "{z}的用法在不同国家差别很大。"),
    ("Tenho dificuldade em distinguir {w} de palavras parecidas.", "我很难把{z}和相近的词区分开。"),
    ("Este capítulo explica quando se usa {w}.", "这一章讲解什么时候用{z}。"),
]

POOLS = {'verb': V, 'noun': N, 'adj': A}
BAD_HEADWORD = re.compile(r'[^A-Za-zÁÂÃÀÇÉÊÍÓÔÕÚáâãàçéêíóôõúü]')


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



ADJ_HINT = re.compile(
    r'(sensaci|sala estava|comida estaba|reunión fue|me sentí|senti-me|Resulta hablar|É falar|'
    r'bastante|estaba \S+ cuando|estava \S+ quando|vuelto|tornou-se|en invierno|no inverno|'
    r'parecía \S+ y|parecia \S+ e|resultó más|revelou-se más|fue menos|foi menos|humor|'
    r'Me pareció|Pareceu-me|esperaba tan|esperava tan|Aunque era|Embora fosse|primer libro|primeiro livro|'
    r'sorprendentemente|surpreendentemente|Lo encontré|Encontrei-o|siga adelante|continue é|'
    r'críticas del|críticas do|la verdad|sinceramente|a simple vista|primeira vista|mostró|Mostrou)'
)

DET_PT = re.compile(
    r'^(o |a |os |as |um |uma |uns |umas |este |esta |estes |estas |esse |essa |esses |essas |aquele |aquela |aqueles |aquelas |'
    r'meu |minha |meus |minhas |teu |tua |teus |tuas |seu |sua |seus |suas |nosso |nossa |nossos |nossas |vosso |vossa |vossos |vossas |'
    r'todo |toda |todos |todas |algum |alguma |alguns |algumas |nenhum |nenhuma |nenhuns |nenhumas |muito |muita |muitos |muitas |'
    r'pouco |pouca |poucos |poucas |tanto |tanta |tantos |tantas |outro |outra |outros |outras |vários |várias |cada |qualquer |quaisquer |'
    r'qual |quais |que |quem |quanto |quanta |quantos |quantas |'
    r'mi |tu |su |nuestro |vuestro |este |ese |aquel |esta |esa |aquella |tal |cada |mismo |'
    r'otro |otra |varios |varias |todo |toda |cuál |qué |quién |cualquier |algún |alguna |'
    r'ningún |ninguna |mucho |mucha |muchos |muchas |más |menos |poco |poca |demasiado |'
    r'my |your |his |her |its |our |their |this |that |these |those |such |each |every |same |'
    r'other |several |all |no |which |what |some |any |many |much |more |most |few |less |own )'
)

FEM_FRAMES_PT = [
    r'(A sala estava) (\S+?)( quando chegámos\.)',
    r'(uma sensação) (\S+?)([.,])',
]

TPLS = [
    (r'^(这次旅行比我们预期的更)(.+?)(?:的)?。$', r'\1\2。'),
    (r'^(这次会议没有上周的那么)(.+?)(?:的)?。$', r'\1\2。'),
    (r'^(今天老师的心情很)(.+?)(?:的)?。$', r'\1\2。'),
    (r'^(他对这件事只字不提，我觉得很)(.+?)(?:的)?。$', r'\1\2。'),
    (r'^(随着时间推移，这个问题变得更加)(.+?)(?:的)?了。$', r'\1\2了。'),
    (r'^(没人料到结局会这么)(.+?)(?:的)?。$', r'\1\2。'),
    (r'^(虽然很)(.+?)(?:的)?，他还是决定继续尝试。$', r'\1\2，他还是决定继续尝试。'),
    (r'^(我们到的时候，房间里很)(.+?)(?:的)?。$', r'\1\2。'),
    (r'^(作为他的第一本书，写得相当)(.+?)(?:的)?。$', r'\1\2。'),
    (r'^(这座城市冬天的天气很)(.+?)(?:的)?。$', r'\1\2。'),
    (r'^(他的回答给我留下一种)(.+?)(?:的)?的感觉。$', r'\1\2的感觉。'),
    (r'^(昨天我一整天都感到很)(.+?)(?:的)?。$', r'\1\2。'),
    (r'^(和家人谈钱总是很)(.+?)(?:的)?。$', r'\1\2。'),
    (r'^(这次考试我觉得出奇地)(.+?)(?:的)?。$', r'\1\2。'),
    (r'^(从远处看，.+?显得)(.+?)(?:的)?而宁静。$', r'\1\2而宁静。'),
    (r'^(我发现他很)(.+?)(?:的)?：不停地看表。$', r'\1\2：不停地看表。'),
    (r'^(项目能继续推进，对大家来说是件)(.+?)(?:的)?的事。$', r'\1\2的事。'),
    (r'^(面对评审的批评，他表现得很)(.+?)(?:的)?。$', r'\1\2。'),
    (r'^(说实话，那顿饭很)(.+?)(?:的)?。$', r'\1\2。'),
    (r'^(它没有乍看上去那么)(.+?)(?:的)?。$', r'\1\2。'),
]

BODY_FIX = ("Visto de longe, o parecia um lugar", "Visto de longe, o local parecia um lugar")


def fem_fix(body, frames):
    changed = False
    for rx in frames:
        m = re.search(rx, body)
        if m:
            w = m.group(2)
            if w.endswith('os'):
                nw = w[:-2] + 'as'
            elif w.endswith('o') and not w.endswith(('a', 'e', 'or', 'l', 'z', 'n')):
                nw = w[:-1] + 'a'
            else:
                nw = w
            if nw != w:
                body = body[:m.start(2)] + nw + body[m.end(2):]
                changed = True
    return body, changed


def generate_3_sentences(word: str, zh: str, pos: str, idx: int):
    if pos in POOLS and len(word) <= 24 and not BAD_HEADWORD.search(word):
        pool = POOLS[pos]
    else:
        pool = X
    z = first_zh(zh) or word
    n = len(pool)
    out, seen, k = [], set(), 0
    while len(out) < 3 and k < n + 3:
        pick = (idx * 7 + k * 13 + len(out) * 3) % n
        if pool is X:
            pick = (idx + k) % n
        if pick not in seen:
            seen.add(pick)
            es_pat, zh_pat = pool[pick]
            out.append([es_pat.replace('{w}', word), zh_pat.replace('{z}', z)])
        k += 1
    return out[:3]


def build_all_sentences(books: dict, lemma: dict):
    master = {}
    idx = 0
    for lv in ('pt_a1a2', 'pt_b1', 'pt_b2', 'pt_c1'):
        for e in books['levels'].get(lv, []):
            idx += 1
            calc_idx = idx if idx < 5208 else idx + 1
            w = e['word']
            zh = e.get('zh', '').strip()
            pos = e.get('pos', 'noun')
            if pos not in ('adj', 'adv', 'verb', 'noun'):
                pos = 'other'
            sents = generate_3_sentences(w, zh, pos, calc_idx)

            has_adj = any(ADJ_HINT.search(x[0]) for x in sents)
            if has_adj:
                zh0 = sents[0][1] if len(sents[0]) > 1 else ""
                is_det = bool(DET_PT.match(zh0.rstrip('。') + ' '))
                lem = lemma.get(w, {})
                if is_det or ('adj' not in lem if lem else False):
                    z = first_zh(zh0) or w
                    new_s = []
                    for k in range(3):
                        tpl, ztpl = X[(len(w) * 7 + k * 5) % len(X)]
                        new_s.append([tpl.replace('{w}', w), ztpl.replace('{z}', z)])
                    sents = new_s

            if not (has_adj and (is_det or ('adj' not in lem if lem else False))):
                for x in sents:
                    if BODY_FIX[0] in x[0]:
                        x[0] = x[0].replace(BODY_FIX[0], BODY_FIX[1])
                    nb, ch = fem_fix(x[0], FEM_FRAMES_PT)
                    if ch:
                        x[0] = nb

            for x in sents:
                zh_val = x[1]
                for rx, rep in TPLS:
                    if re.match(rx, zh_val):
                        new_val = re.sub(rx, rep, zh_val).replace('的的', '的')
                        if new_val != zh_val:
                            x[1] = new_val
                        break

            for x in sents:
                x[1] = x[1].replace('（', '[').replace('）', ']')

            e['sentences'] = sents
            master[w] = sents
    return master


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Portuguese sentence generator / checker")
    parser.add_argument("--check", action="store_true", help="Check against master without modifying files")
    args = parser.parse_args()

    if not BOOKS_FILE.exists():
        print(f"not found: {BOOKS_FILE}")
        sys.exit(1)
    books = json.loads(BOOKS_FILE.read_text(encoding='utf-8'))
    lemma = {}
    if LEMMA_FILE.exists():
        lemma = json.loads(LEMMA_FILE.read_text(encoding='utf-8')).get("lemmas", {})

    master = build_all_sentences(books, lemma)

    if args.check:
        if not MASTER_FILE.exists():
            print(f"MASTER_FILE not found: {MASTER_FILE}")
            sys.exit(1)
        expected = json.loads(MASTER_FILE.read_text(encoding='utf-8'))
        mismatches = [w for w in expected if master.get(w) != expected[w]]
        if mismatches:
            print(f"CHECK FAIL: {len(mismatches)} words differ from master!")
            for w in mismatches[:5]:
                print(f"  diff at {w}: gen={master.get(w)[:1]} vs exp={expected.get(w)[:1]}")
            sys.exit(1)
        print(f"CHECK PASS: all {len(expected)} words match sentences_master.json exactly.")
        return

    BOOKS_FILE.write_text(json.dumps(books, ensure_ascii=False, indent=2), encoding='utf-8')
    MASTER_FILE.write_text(json.dumps(master, ensure_ascii=False, indent=1), encoding='utf-8')

    total_s = sum(len(v) for v in master.values())
    fc = collections.Counter()
    for w, pairs in master.items():
        for es, _ in pairs:
            fc[es.replace(w, '#')] += 1
    top = fc.most_common(1)[0]
    print(f"total words: {len(master)}, sentences: {total_s}, frames: {len(fc)}")
    print(f"top frame: {top[1]} rows ({top[1]/total_s*100:.2f}%)")
    print(f"saved: {BOOKS_FILE}\nsaved: {MASTER_FILE}")


if __name__ == '__main__':
    main()
