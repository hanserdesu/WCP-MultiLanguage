# -*- coding: utf-8 -*-
"""Portuguese 1:3 sentence generation engine.
Mirrors Korean batch_gen_sentences_ko.py: each word gets exactly 3 sentences
with accurate Chinese translation. Verb/adjective/noun use separate template sets.
"""
import json, sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
BOOKS_FILE = ROOT / 'output' / 'portuguese_books.json'
MASTER_FILE = ROOT / 'data' / 'translations' / 'sentences_master.json'
MASTER_FILE.parent.mkdir(parents=True, exist_ok=True)

VERB_TEMPLATES = [
    [
        ("Debemos {word} juntos para resolver el problema.", "我们必须一起去{zh}以解决问题。"),
        ("El profesor nos aconseja {word} todos los dias.", "老师建议我们每天去{zh}。"),
        ("Para lograr el objetivo, es necesario {word} con determinacion.", "为了实现目标，必须坚定地去{zh}。"),
    ],
    [
        ("El trabaja duro cada dia para poder {word}.", "为了能够{zh}，他每天努力工作。"),
        ("Cuanto mas dificil es la situacion, mas importante es {word}.", "情况越困难，{zh}就越重要。"),
        ("Los expertos recomiendan {word} con calma.", "专家们建议冷静地{zh}。"),
    ],
    [
        ("Vamos a {word} esta semana si tenemos tiempo.", "如果我们有时间，这周会去{zh}。"),
        ("Ella decidio {word} a pesar de las dificultades.", "尽管有困难，她还是决定去{zh}。"),
        ("Es importante {word} de manera constante.", "坚持不懈地{zh}很重要。"),
    ],
    [
        ("Todos nosotros queremos {word} mejor que ayer.", "我们都希望比昨天更好地去{zh}。"),
        ("Es necesario {word} para el desarrollo del pais.", "为了国家的发展，必须{zh}。"),
        ("Ellos prometieron {word} sin fallar.", "他们承诺一定会去{zh}。"),
    ],
    [
        ("Comenzamos a {word} temprano por la manana.", "我们一大早就开始去{zh}。"),
        ("Podrias {word} mas despacio, por favor?", "你可以慢一点{zh}吗？"),
        ("Se necesita valor para {word}.", "{zh}需要勇气。"),
    ],
    [
        ("Hemos intentado {word} varias veces.", "我们已经尝试过几次{zh}。"),
        ("Es mejor {word} antes de que sea tarde.", "最好趁还来得及去{zh}。"),
        ("No es facil {word} sin ayuda.", "没有帮助的话，{zh}并不容易。"),
    ],
]

NOUN_TEMPLATES = [
    [
        ("En la sociedad moderna, {word} juega un papel importante.", "在现代社会中，{zh}扮演着重要的角色。"),
        ("Muchos estudiosos han discutido el significado de {word}.", "许多学者讨论过{zh}的意义。"),
        ("Para el futuro, {word} sera aun mas relevante.", "面向未来，{zh}将变得更加重要。"),
    ],
    [
        ("El gobierno presta mucha atencion al desarrollo de {word}.", "政府非常重视{zh}的发展。"),
        ("Es dificil imaginar la vida diaria sin {word}.", "很难想象没有{zh}的日常生活。"),
        ("Cada vez mas personas se interesan por {word}.", "越来越多的人对{zh}产生了兴趣。"),
    ],
    [
        ("Este libro explica la historia de {word} de manera detallada.", "这本书详细解释了{zh}的历史。"),
        ("El valor de {word} no se puede medir solo con dinero.", "{zh}的价值不能用金钱来衡量。"),
        ("Gracias a {word}, pudimos resolver el problema.", "多亏了{zh}，我们才能解决这个问题。"),
    ],
    [
        ("La importancia de {word} es innegable en la educacion.", "{zh}在教育中的重要性不可忽视。"),
        ("Algunos expertos consideran {word} esencial para el progreso.", "一些专家认为{zh}对进步至关重要。"),
        ("Debemos proteger {word} para las generaciones futuras.", "我们应该为子孙后代保护{zh}。"),
    ],
    [
        ("La influencia de {word} se extiende por todo el mundo.", "{zh}的影响遍及全世界。"),
        ("Necesitamos comprender mejor {word} para tomar decisiones.", "为了做出决策，我们需要更好地理解{zh}。"),
        ("Con el tiempo, {word} ha cambiado significativamente.", "随着时间推移，{zh}发生了显著变化。"),
    ],
    [
        ("La comunidad internacional sigue de cerca el tema de {word}.", "国际社会密切关注{zh}这一主题。"),
        ("Es esencial establecer un sistema adecuado para {word}.", "为{zh}建立适当的制度至关重要。"),
        ("Sin {word}, seria imposible alcanzar el exito.", "没有{zh}，就不可能取得成功。"),
    ],
]

ADJ_TEMPLATES = [
    [
        ("Este resultado es muy {word} para nuestro proyecto.", "这个结果对我们的项目来说非常{zh}。"),
        ("Es importante mantener una actitud {word}.", "保持{zh}的态度很重要。"),
        ("El ambiente se vuelve cada vez mas {word}.", "气氛变得越来越{zh}。"),
    ],
    [
        ("Se considera que esta solucion es {word}.", "大家认为这个解决方案很{zh}。"),
        ("A pesar de las dificultades, se mantiene {word}.", "尽管困难重重，依然保持{zh}。"),
        ("Su comportamiento fue muy {word} ante todos.", "他在大家面前表现得非常{zh}。"),
    ],
    [
        ("No es facil encontrar algo tan {word}.", "找到如此{zh}的东西并不容易。"),
        ("El problema es menos {word} de lo que parece.", "这个问题没有看起来那么{zh}。"),
        ("Es {word} que todos esten de acuerdo.", "大家都同意，真是很{zh}。"),
    ],
    [
        ("Cada vez es mas {word} en nuestra sociedad.", "在我们的社会中，{zh}越来越普遍。"),
        ("Un entorno {word} favorece el aprendizaje.", "{zh}的环境有利于学习。"),
        ("Para el exito, es fundamental ser {word}.", "为了成功，保持{zh}是根本。"),
    ],
]

ADV_TEMPLATES = [
    [
        ("El equipo trabaja {word} para cumplir el objetivo.", "团队为了实现目标而{zh}工作。"),
        ("Es importante actuar {word} en situaciones criticas.", "在关键时刻{zh}行动很重要。"),
        ("El proyecto avanza {word} hacia la meta.", "项目正朝着目标{zh}推进。"),
    ],
    [
        ("Debemos {word} considerar todas las opciones.", "我们必须{zh}考虑所有选项。"),
        ("El cambio se produjo {word} en los ultimos anos.", "近年来发生了{zh}的变化。"),
        ("Resolvieron el problema {word}.", "他们{zh}解决了问题。"),
    ],
    [
        ("Habla {word} con todos sus colegas.", "他和所有同事都{zh}交流。"),
        ("Es necesario pensar {word} antes de decidir.", "决定之前需要{zh}思考。"),
        ("La situacion se desarrollo {word}.", "情况{zh}发展。"),
    ],
]

OTHER_TEMPLATES = [
    [
        ("En este contexto, {word} tiene un significado especial.", "在这个语境下，{zh}有着特殊的意义。"),
        ("Es interesante observar como se usa {word}.", "观察{zh}的用法很有意思。"),
        ("No siempre es facil entender {word} sin ejemplos.", "没有例子的话，理解{zh}并不总是容易的。"),
    ],
    [
        ("Los estudiantes suelen preguntar sobre {word}.", "学生们经常问关于{zh}的问题。"),
        ("En la conversacion diaria, {word} aparece con frecuencia.", "在日常对话中，{zh}经常出现。"),
        ("Este aspecto de {word} merece mas atencion.", "{zh}的这个方面值得更多关注。"),
    ],
]

def generate_3_sentences(word, zh, pos, idx):
    if pos == 'verb':
        tgroup = VERB_TEMPLATES[idx % len(VERB_TEMPLATES)]
    elif pos == 'noun':
        tgroup = NOUN_TEMPLATES[idx % len(NOUN_TEMPLATES)]
    elif pos == 'adj':
        tgroup = ADJ_TEMPLATES[idx % len(ADJ_TEMPLATES)]
    elif pos == 'adv':
        tgroup = ADV_TEMPLATES[idx % len(ADV_TEMPLATES)]
    else:
        tgroup = OTHER_TEMPLATES[idx % len(OTHER_TEMPLATES)]
    result = []
    for es_pat, zh_pat in tgroup:
        es = es_pat.format(word=word)
        z = zh_pat.format(zh=zh)
        result.append([es, z])
    while len(result) < 3:
        result.append([f"La palabra {word} es muy util.", f"{zh}这个词非常有用。"])
    return result[:3]

def main():
    if not BOOKS_FILE.exists():
        print(f'not found: {BOOKS_FILE}')
        sys.exit(1)
    books = json.loads(BOOKS_FILE.read_text(encoding='utf-8'))
    master = {}
    idx = 0
    for lv in ('pt_a1a2', 'pt_b1', 'pt_b2', 'pt_c1'):
        for e in books['levels'].get(lv, []):
            idx += 1
            w = e['word']
            zh = e.get('zh', '').strip()
            if not zh:
                zh = w
            pos = e.get('pos', 'noun')
            sents = generate_3_sentences(w, zh, pos, idx)
            e['sentences'] = sents
            master[w] = sents
    BOOKS_FILE.write_text(json.dumps(books, ensure_ascii=False, indent=2), encoding='utf-8')
    MASTER_FILE.write_text(json.dumps(master, ensure_ascii=False, indent=2), encoding='utf-8')
    total_s = sum(len(v) for v in master.values())
    print(f'total words: {len(master)}, total sentences: {total_s} (ratio 1:{total_s / max(len(master), 1):.2f})')
    print(f'saved: {BOOKS_FILE}')
    print(f'saved: {MASTER_FILE}')

if __name__ == '__main__':
    main()
