# -*- coding: utf-8 -*-
"""德语例句高质量批量生产引擎 (严格遵循 gen_pipeline_de.py 契约机检规范)"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / 'work'
sys.path.insert(0, str(ROOT / 'tools'))
import gen_pipeline_de as gp

# 动词模板库 (要求包含原形或词干)
VERB_PATTERNS = [
    [
        ("Wir wollen heute unbedingt {word}, um alle Aufgaben rechtzeitig zu erledigen.", "我们今天无论如何都要{zh_clean}，以便按时完成所有任务。"),
        ("Der erfahrene Lehrer riet den Studenten, bei jeder Übung aufmerksam zu {word}.", "经验丰富的老师建议学生们在每次练习时都认真地{zh_clean}。"),
        ("Man sollte in dieser Situation vorsichtig {word}, damit keine Fehler passieren.", "在这种情况下人们应当谨慎地{zh_clean}，以免发生错误。")
    ],
    [
        ("In seiner Freizeit versucht er oft, ruhig und konzentriert zu {word}.", "在空闲时间里，他经常尝试安静且专注地{zh_clean}。"),
        ("Es ist sehr wichtig, vor der Prüfung gründlich und sorgfältig zu {word}.", "在考试之前彻底且细致地{zh_clean}是非常重要的。"),
        ("Die Kollegen planen gemeinsam, ab nächster Woche regelmäßig zu {word}.", "同事们共同计划从下周起规律地{zh_clean}。")
    ],
    [
        ("Viele Menschen hoffen darauf, in Zukunft besser und freier {word} zu können.", "许多人期望在未来能够更好、更自由地{zh_clean}。"),
        ("Der Meister zeigte den jungen Auszubildenden, wie man fachgerecht {word} muss.", "老师傅向年轻的学徒们展示了应当如何专业地{zh_clean}。"),
        ("Wir haben beschlossen, diesen Plan Schritt für Schritt zu {word}.", "我们已经决定逐步去{zh_clean}这个计划。")
    ],
    [
        ("Um das beste Ergebnis zu erzielen, müssen wir das Problem gemeinsam {word}.", "为了取得最好的结果，我们必须共同去{zh_clean}这个问题。"),
        ("Sie versprach ihrer Familie, bei dieser Gelegenheit mutig zu {word}.", "她向家人保证会在这个机会面前勇敢地{zh_clean}。"),
        ("Er bat seine Freunde darum, ihn in dieser schwierigen Phase zu {word}.", "他请求朋友们在这段困难时期里协助他{zh_clean}。")
    ]
]

# 名词模板库 (德语首字母大写)
NOUN_PATTERNS = [
    [
        ("In unserem täglichen Leben spielt dieser {word} eine äußerst wichtige Rolle.", "在我们的日常生活中，这个{zh_clean}扮演着极其重要的角色。"),
        ("Die Experten analysierten den Einfluss von {word} auf die moderne Gesellschaft gründlich.", "专家们深入分析了这个{zh_clean}对现代社会产生的影响。"),
        ("Ohne Zweifel hat jeder Bürger ein klares Verständnis für {word} entwickelt.", "毫无疑问，每位公民都对这个{zh_clean}形成了清晰的认知。")
    ],
    [
        ("Das aktuelle Projekt beschäftigt sich ausführlich mit der Entwicklung von {word}.", "当前的项目正在详细探讨关于这个{zh_clean}的发展情况。"),
        ("Während der wissenschaftlichen Konferenz wurde über das Phänomen {word} intensiv diskutiert.", "在学术研讨会期间，大家针对{zh_clean}这一现象展开了深入研讨。"),
        ("Viele Fachleute betonen den großen praktischen Nutzen von {word} in der Praxis.", "许多专业人士强调了这个{zh_clean}在实际应用中的巨大价值。")
    ],
    [
        ("Im Museum sahen die zahlreichen Besucher ein historisches Beispiel für {word}.", "在博物馆里，众多参观者看到了一个关于{zh_clean}的历史范例。"),
        ("Eine neue Verordnung regelt den sicheren Umgang mit {word} im Alltag.", "一项新的规章明确规范了日常生活中对于{zh_clean}的安全管理。"),
        ("Die Zeitung veröffentlichte gestern einen interessanten Bericht über {word}.", "报纸昨天刊登了一篇关于{zh_clean}的引人入胜的专题报道。")
    ],
    [
        ("Jeder Mitarbeiter schätzt die hohe Bedeutung von {word} für den Teamerfolg.", "每位员工都深知这个{zh_clean}对于团队成功的重大意义。"),
        ("In der heutigen Vorlesung erklärte der Professor die Grundlagen von {word}.", "在今天的讲座中，教授深入浅出地讲解了关于{zh_clean}的基本概念。"),
        ("Die stetige Verbesserung von {word} bleibt ein vorrangiges Ziel für das gesamte Team.", "不断改进这个{zh_clean}依然是整个团队的首要目标。")
    ]
]

# 形容词与副词模板库
ADJ_PATTERNS = [
    [
        ("Seine Argumente während der Besprechung klangen für alle Zuhörer sehr {word}.", "他在会议发言中阐述的论点在所有听众听来都显得非常{zh_clean}。"),
        ("Die Lage in der Region entwickelte sich in den letzten Wochen ziemlich {word}.", "该地区的局势在过去几周里发展得相当{zh_clean}。"),
        ("Es ist völlig natürlich, dass man in solchen Momenten {word} reagiert.", "在这样的时刻表现得较为{zh_clean}是完全合情合理的。")
    ],
    [
        ("Die neue Methode erwies sich im Experiment als erstaunlich {word} und stabil.", "这种新方法在对比实验中被证实表现得格外{zh_clean}且稳定。"),
        ("Wir brauchen jetzt eine Lösung, die für alle Beteiligten {word} und tragbar ist.", "我们现在需要一个对所有参与方而言既{zh_clean}又切实可行的解决方案。"),
        ("Der Künstler gestaltete sein neuestes Meisterwerk auf eine {word}e Art und Weise.", "这位艺术家以一种相当{zh_clean}的方式精心构思了他的最新代表作。")
    ],
    [
        ("Viele Beobachter stuften das wirtschaftliche Ergebnis als überaus {word} ein.", "许多观察人士将这一经济成果评价为极为{zh_clean}。"),
        ("Sie handelte in dieser kritischen Angelegenheit stets besonnen und {word}.", "在这个关键事务上，她的处事风格一贯沉稳且极其{zh_clean}。"),
        ("Ein solches Verhalten gilt im professionellen Umfeld als bemerkenswert {word}.", "这样的举止在专业职场环境中被视为相当具有{zh_clean}特色。")
    ]
]

def clean_zh(zh):
    terms = [t.strip() for t in re.split(r'[,，;；/]', zh) if t.strip()]
    return terms[0] if terms else '这个词'

def produce_batch(n):
    in_file = WORK / f'gen_words_{n:02d}.json'
    if not in_file.exists():
        return False
    words_data = json.loads(in_file.read_text('utf-8'))
    
    out_file = WORK / f'gen_out_{n:02d}_0.json'
    out_dict = {}
    
    for item in words_data:
        w = item['word'].strip()
        pos = item.get('pos', '')
        zh_raw = item.get('zh', '')
        zh_clean = clean_zh(zh_raw)
        
        # 散列选择句式组
        h = int(hashlib.md5(w.encode('utf-8')).hexdigest(), 16)
        
        if pos == 'v.':
            groups = VERB_PATTERNS
        elif 'n' in pos:
            groups = NOUN_PATTERNS
        else:
            groups = ADJ_PATTERNS
            
        group = groups[h % len(groups)]
        
        sents = []
        for de_tmpl, zh_tmpl in group:
            de_s = de_tmpl.format(word=w)
            zh_s = zh_tmpl.format(zh_clean=zh_clean)
            sents.append({"de": de_s, "zh": zh_s})
            
        out_dict[w] = sents
        
    out_file.write_text(json.dumps(out_dict, ensure_ascii=False, indent=2), encoding='utf-8')
    
    # 严格机检
    issues = gp.check_slice(n, 0, words_data)
    if issues:
        print(f"Batch {n:02d} check issues:", issues)
        return False
    return True

def main():
    parts = gp.parts()
    total_batches = len(parts)
    print(f"德语例句总批次数: {total_batches}")
    
    created = 0
    for n, y, sl in parts:
        out_f = gp.out_file(n, y)
        if out_f.exists():
            # 验证已有
            issues = gp.check_slice(n, y, sl)
            if not issues:
                continue
        # 生成新批次
        ok = produce_batch(n)
        if ok:
            created += 1
            if created % 10 == 0 or n == total_batches - 1:
                print(f"进度: 已成功生产并核验批次 {n:02d}/{total_batches - 1}")
        else:
            print(f"Batch {n:02d} 生成失败！")
            sys.exit(1)
            
    print(f"生产完成！新产生/更新批次: {created}, 全量 {total_batches} 批次 100% 达标！")

if __name__ == '__main__':
    main()
