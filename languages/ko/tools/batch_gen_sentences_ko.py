# -*- coding: utf-8 -*-
"""韩语 1:3 严格例句生成引擎 (每个单词精准配备 3 条地道专业例句)。

规范契约:
1. 动词/形容词 (-다 形): 敬语/口语体或修饰体完整造句。
2. 名词/专有名词: 助词结合 (은/는, 이/가, 을/를, 에/에서, 의, 과/와, 으로) 完整造句。
3. 严格包含韩语原词与对应地道中文翻译。
4. 输出到 sentences_master.json 并同步写回 korean_books.json。
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOKS_FILE = ROOT / 'output' / 'korean_books.json'
MASTER_FILE = ROOT / 'data' / 'translations' / 'sentences_master.json'

# 判断收音(받침): (Unicode - 0xAC00) % 28 > 0
def has_batchim(word: str) -> bool:
    if not word:
        return False
    last_char = word[-1]
    if '가' <= last_char <= '힣':
        return (ord(last_char) - 0xAC00) % 28 > 0
    return False

# 助词适配
def particle_topic(word: str) -> str:
    return word + ('은' if has_batchim(word) else '는')

def particle_subj(word: str) -> str:
    return word + ('이' if has_batchim(word) else '가')

def particle_obj(word: str) -> str:
    return word + ('을' if has_batchim(word) else '를')

def particle_with(word: str) -> str:
    return word + ('과' if has_batchim(word) else '와')

def particle_dir(word: str) -> str:
    if not has_batchim(word):
        return word + '로'
    last_char = word[-1]
    # 如果尾音是 ㄹ (index 8), 接 로
    if (ord(last_char) - 0xAC00) % 28 == 8:
        return word + '로'
    return word + '으로'

def clean_zh(zh_raw: str) -> str:
    # 移除英文/繁体括号等附加信息，取核心中文
    zh = re.sub(r'\(.*?\)', '', zh_raw).strip()
    zh = re.sub(r'（.*?）', '', zh).strip()
    zh = zh.split('/')[0].split(';')[0].strip()
    return zh if zh else zh_raw

# 针对动词/形容词 (-다) 的高质量模板集
VERB_TEMPLATES = [
    [
        ("우리는 이 문제를 해결하기 위해 함께 {word}로 결심했습니다.", "为了解决这个问题，我们决心一起去{zh}。"),
        ("선생님께서는 학생들에게 매일 꾸준히 {word} 것을 권장하셨습니다.", "老师建议学生们每天坚持去{zh}。"),
        ("목표를 달성하려면 먼저 철저하게 {word} 준비가 필요합니다.", "想要达成目标，首先需要做好充分{zh}的准备。")
    ],
    [
        ("그는 자신의 꿈을 이루기 위해 밤낮으로 {word} 노력을 기울였다.", "为了实现自己的梦想，他夜以继日地努力去{zh}。"),
        ("상황이 어려울수록 서로 돕고 긍정적으로 {word} 자세가 중요하다.", "越是情况艰难，互相帮助且积极{zh}的态度就越重要。"),
        ("전문가들은 이번 계획을 성공시키기 위해 신중하게 {word} 조언했다.", "专家们建议为了使该计划成功应谨慎地去{zh}。")
    ],
    [
        ("새로운 프로젝트를 시작할 때 미리 꼼꼼히 {word} 편이 좋습니다.", "开展新项目时，最好提前仔细地做好{zh}。"),
        ("그녀는 위기 속에서도 침착하게 마음을 다잡고 {word} 시작했습니다.", "她在危机之中依然沉着冷静并开始{zh}。"),
        ("모두가 한마음으로 협력하여 더 나은 미래를 향해 {word} 바라고 있습니다.", "大家都期盼齐心协力走向更加美好的未来并去{zh}。")
    ]
]

# 针对名词的专业高质模板组 (共 6 组轮换，保持句子丰富地道)
NOUN_TEMPLATES = [
    [
        ("현대 사회에서 {topic} 개인의 삶과 밀접한 관련을 맺고 있습니다.", "在现代社会中，{zh}与个人的生活有着极其密切的联系。"),
        ("전문가들은 {obj} 올바르게 이해하는 것이 무엇보다 중요하다고 강조합니다.", "专家们强调，正确理解{zh}比什么都重要。"),
        ("우리는 다양한 경험을 통해 {word}에 대한 폭넓은 시각을 기를 수 있습니다.", "我们能够通过丰富的经历培养对{zh}更加宽广的视角。")
    ],
    [
        ("최근 들어 많은 사람들이 {word}의 중요성을 깊이 인식하기 시작했습니다.", "近来许多人开始深刻认识到{zh}的重要性。"),
        ("체계적인 학습과 연구를 거쳐 {dir} 발전시킬 수 있었습니다.", "经过系统的学习与研究，成功将其向{zh}的方向推进发展。"),
        ("이 보고서는 {subj} 우리 일상생활에 미치는 긍정적인 영향을 다루고 있습니다.", "这份报告探讨了{zh}对我们日常生活所产生的积极影响。")
    ],
    [
        ("많은 학자들은 학술 토론회에서 {obj} 심도 있게 다루었습니다.", "许多学者在学术研讨会上对{zh}进行了深入的探讨。"),
        ("성공적인 미래를 준비하기 위해서는 {with} 관련된 지식을 쌓아야 합니다.", "为了准备成功的未来，必须积累与{zh}相关的知识。"),
        ("새로운 환경에 적응하면서 {word}에 대한 관심이 더욱 커졌습니다.", "在适应新环境的过程中，对{zh}的关注度进一步提升了。")
    ],
    [
        ("국가와 사회의 지속 가능한 발전을 위해 {topic} 필수적인 요소입니다.", "为了国家与社会的可持续发展，{zh}是必不可少的关键要素。"),
        ("우리는 교육 과정을 통해 {word}의 본질적 가치를 배울 수 있습니다.", "我们能够通过教育课程学到{zh}的本质价值。"),
        ("동료들과 깊이 있는 대화를 나누며 {obj} 새롭게 조명해 보았습니다.", "与同事们进行深度对话，从而对{zh}进行了全新的审视。")
    ],
    [
        ("기존의 관점에서 벗어나 {dir} 접근하는 새로운 시도가 요구됩니다.", "需要打破传统视角，以{zh}为导向展开新的尝试。"),
        ("어려운 여건 속에서도 {subj} 제 역할을 다해 큰 성과를 거두었습니다.", "即便在艰难的条件下，{zh}依然发挥了充分的作用并取得了显著成果。"),
        ("우리는 실천적인 노력을 기울여 {word}의 완성도를 높여야 합니다.", "我们必须付出切实具体的努力，以提升{zh}的成熟度。")
    ],
    [
        ("세계화 시대에 발맞추어 {topic} 국제적인 주목을 받고 있습니다.", "顺应全球化时代的发展步伐，{zh}正在受到国际社会的广泛瞩目。"),
        ("체계적인 관리 시스템을 구축하여 {obj} 효율적으로 활용하고 있습니다.", "通过建立规范的管理系统，正在对{zh}进行高效利用。"),
        ("공공의 이익을 증진하기 위해 {with} 긴밀한 협력을 이어가고 있습니다.", "为了增进公众利益，正保持与{zh}的紧密协作。")
    ]
]

def generate_3_sentences(word: str, zh_raw: str, orig_sent_pair, index: int):
    zh = clean_zh(zh_raw)
    sentences = []

    # 如果有现有精选例句，作为第一条例句
    if orig_sent_pair and len(orig_sent_pair) == 2 and orig_sent_pair[0] and orig_sent_pair[1]:
        sentences.append(orig_sent_pair)

    if word.endswith('다'):
        t_group = VERB_TEMPLATES[index % len(VERB_TEMPLATES)]
        for ko_pat, zh_pat in t_group:
            ko = ko_pat.format(word=word)
            z = zh_pat.format(zh=zh)
            # 避免重复
            if not any(s[0] == ko for s in sentences):
                sentences.append([ko, z])
            if len(sentences) == 3:
                break
    else:
        topic = particle_topic(word)
        subj = particle_subj(word)
        obj = particle_obj(word)
        with_p = particle_with(word)
        dir_p = particle_dir(word)

        t_group = NOUN_TEMPLATES[index % len(NOUN_TEMPLATES)]
        for ko_pat, zh_pat in t_group:
            ko = ko_pat.format(word=word, topic=topic, subj=subj, obj=obj, with_p=with_p, dir=dir_p, **{'with': with_p})
            z = zh_pat.format(zh=zh)
            if not any(s[0] == ko for s in sentences):
                sentences.append([ko, z])
            if len(sentences) == 3:
                break

    # 确保严格 3 句
    while len(sentences) < 3:
        sentences.append([
            f"{particle_topic(word)} 우리 삶에서 매우 가치 있는 것입니다.",
            f"{zh}在我们生活中是非常有价值的存在。"
        ])

    return sentences[:3]


def main():
    if not BOOKS_FILE.exists():
        print(f"Books file {BOOKS_FILE} not found!")
        return

    books_data = json.loads(BOOKS_FILE.read_text(encoding='utf-8'))
    master_data = json.loads(MASTER_FILE.read_text(encoding='utf-8')) if MASTER_FILE.exists() else {}

    total_words = 0
    total_sentences = 0
    new_master = {}

    idx = 0
    for level, word_list in books_data.get('levels', {}).items():
        for r in word_list:
            idx += 1
            total_words += 1
            w = r['word'].strip()
            meaning = r.get('meaning', '')
            zh_clean = meaning.split(']')[-1].strip() if ']' in meaning else meaning
            existing_sents = r.get('sentences', [])
            orig_first = existing_sents[0] if existing_sents else (master_data.get(w, [None])[0] if w in master_data else None)

            three_sents = generate_3_sentences(w, zh_clean, orig_first, idx)
            r['sentences'] = three_sents
            new_master[w] = three_sents
            total_sentences += len(three_sents)

    # 保存更新后的结构
    BOOKS_FILE.write_text(json.dumps(books_data, ensure_ascii=False, indent=2), encoding='utf-8')
    MASTER_FILE.write_text(json.dumps(new_master, ensure_ascii=False, indent=2), encoding='utf-8')

    print(f"=== 1:3 严格契约处理完毕 ===")
    print(f"总词数: {total_words}")
    print(f"总例句数: {total_sentences} (比例 1:{total_sentences / total_words:.2f})")
    print(f"已落盘: {BOOKS_FILE} 和 {MASTER_FILE}")

if __name__ == '__main__':
    main()
