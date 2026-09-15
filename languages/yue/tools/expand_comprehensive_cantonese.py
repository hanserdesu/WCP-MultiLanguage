# -*- coding: utf-8 -*-
"""全面粤语词库系统扩充脚本 (L11 ~ L18):
涵盖亲属称谓、居家日用品、身体健康、烹饪口味、交通设施、时间量词、情感态度、社交礼仪
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"

# L11: 亲属称谓与人际社交
L11_DATA = {
    "level": "L11",
    "name": "亲属称谓与人际社交",
    "description": "涵盖广府传统及日常亲属称谓与人际称呼",
    "words": [
        {
            "word": "老竇",
            "jyutping": "lou5 dau6",
            "pos": "名",
            "meaning": "爸爸，父亲（口语称呼）",
            "sentences": [
                {"sentence": "我老竇平時好鍾意飲早茶。（ngo5 lou5 dau6 ping4 si4 hou2 zung1 ji3 jam2 zou2 caa4.）", "translate": "我爸爸平时很喜欢喝早茶。"},
                {"sentence": "老竇教我要做個正直嘅人。（lou5 dau6 gaau3 ngo5 jiu3 zou6 go3 zing3 zik6 ge3 jan4.）", "translate": "爸爸教导我要做个正直的人。"}
            ]
        },
        {
            "word": "老母",
            "jyutping": "lou5 mou5",
            "pos": "名",
            "meaning": "妈妈，母亲（日常口语称呼）",
            "sentences": [
                {"sentence": "我老母煲嘅老火湯最好飲。（ngo5 lou5 mou5 bou1 ge3 lou5 fo2 tong1 zeoi3 hou2 jam2.）", "translate": "我妈妈煲的老火靓汤最好喝。"},
                {"sentence": "今日打電話返去問候老母。（gam1 jat6 daa2 din6 waa2 faan1 heoi3 man6 hau6 lou5 mou5.）", "translate": "今天打电话回去问候妈妈。"}
            ]
        },
        {
            "word": "阿爸",
            "jyutping": "aa3 baa1",
            "pos": "名",
            "meaning": "爸爸",
            "sentences": [
                {"sentence": "阿爸今晚煮幾味好餸。（aa3 baa1 gam1 maan5 zyu2 gei2 mei6 hou2 sung3.）", "translate": "爸爸今晚做几样好菜。"},
                {"sentence": "同阿爸一齊去散步。（tung4 aa3 baa1 jat1 cai4 heoi3 saan3 bou6.）", "translate": "和爸爸一起去散步。"}
            ]
        },
        {
            "word": "阿媽",
            "jyutping": "aa3 maa1",
            "pos": "名",
            "meaning": "妈妈",
            "sentences": [
                {"sentence": "阿媽成日叮囑我要早瞓。（aa3 maa1 seng4 jat6 ding1 zuk1 ngo5 jiu3 zou2 fan3.）", "translate": "妈妈整天叮嘱我要早点睡觉。"},
                {"sentence": "阿媽煮嘅飯最有家嘅味道。（aa3 maa1 zyu2 ge3 faan6 zeoi3 jau5 gaa1 ge3 mei6 dou6.）", "translate": "妈妈做的饭最具有家的味道。"}
            ]
        },
        {
            "word": "阿哥",
            "jyutping": "aa3 go1",
            "pos": "名",
            "meaning": "哥哥",
            "sentences": [
                {"sentence": "我阿哥讀大學電腦系。（ngo5 aa3 go1 duk6 daai6 hok6 din6 nou5 hai6.）", "translate": "我哥哥在大学念计算机系。"},
                {"sentence": "阿哥好照顧細佬妹。（aa3 go1 hou2 ziu3 gu3 sai3 lou6 mui2.）", "translate": "哥哥很照顾弟弟妹妹。"}
            ]
        },
        {
            "word": "阿嫂",
            "jyutping": "aa3 sou2",
            "pos": "名",
            "meaning": "嫂子",
            "sentences": [
                {"sentence": "阿嫂整嘅甜品好好食。（aa3 sou2 zing2 ge3 tim4 ban2 hou2 hou2 sik6.）", "translate": "嫂子做的甜品非常好吃。"},
                {"sentence": "阿哥同阿嫂感情好好。（aa3 go1 tung4 aa3 sou2 gam2 cing4 hou2 hou2.）", "translate": "哥哥和嫂子感情非常好。"}
            ]
        },
        {
            "word": "細佬",
            "jyutping": "sai3 lou2",
            "pos": "名",
            "meaning": "弟弟",
            "sentences": [
                {"sentence": "我細佬今年讀小學三年級。（ngo5 sai3 lou2 gam1 nin4 duk6 siu2 hok6 saam1 nin4 kap1.）", "translate": "我弟弟今年上小学三年级。"},
                {"sentence": "細佬好鍾意踢足球。（sai3 lou2 hou2 zung1 ji3 tek3 zuk1 kau4.）", "translate": "弟弟很喜欢踢足球。"}
            ]
        },
        {
            "word": "細妹",
            "jyutping": "sai3 mui2",
            "pos": "名",
            "meaning": "妹妹",
            "sentences": [
                {"sentence": "細妹彈鋼琴彈得好聽。（sai3 mui2 daan6 gong3 kam4 daan6 dak1 hou2 teng1.）", "translate": "妹妹钢琴弹得很好听。"},
                {"sentence": "細妹笑得好甜。（sai3 mui2 siu3 dak1 hou2 tim4.）", "translate": "妹妹笑得很甜。"}
            ]
        },
        {
            "word": "阿爺",
            "jyutping": "aa3 je4",
            "pos": "名",
            "meaning": "爷爷，祖父",
            "sentences": [
                {"sentence": "阿爺今年八十歲，身體仲好健康。（aa3 je4 gam1 nin4 baat3 sap6 seoi3, san1 tai2 zung6 hou2 gin6 hong1.）", "translate": "爷爷今年八十岁，身体还很硬朗健康。"},
                {"sentence": "阿爺每日早上去公園打太極。（aa3 je4 mui5 jat6 zou2 soeng6 heoi3 gung1 jyun2 daa2 taai3 gik6.）", "translate": "爷爷每天早上去公园打太极拳。"}
            ]
        },
        {
            "word": "阿嫲",
            "jyutping": "aa3 maa4",
            "pos": "名",
            "meaning": "奶奶，祖母",
            "sentences": [
                {"sentence": "阿嫲教我包粽。（aa3 maa4 gaau3 ngo5 baau1 zung2.）", "translate": "奶奶教我包粽子。"},
                {"sentence": "阿嫲好錫啲孫。（aa3 maa4 hou2 sek3 di1 syun1.）", "translate": "奶奶非常疼爱孙辈。"}
            ]
        },
        {
            "word": "阿公",
            "jyutping": "aa3 gung1",
            "pos": "名",
            "meaning": "外公，姥爷",
            "sentences": [
                {"sentence": "阿公以前係中學校長。（aa3 gung1 ji5 cin4 hai6 zung1 hok6 haau6 zoeng2.）", "translate": "外公以前是中学校长。"},
                {"sentence": "放假返鄉下探阿公。（fong3 gaa3 faan1 hoeng1 haa2 taam3 aa3 gung1.）", "translate": "放假回老家探望外公。"}
            ]
        },
        {
            "word": "婆婆",
            "jyutping": "po4 po2",
            "pos": "名",
            "meaning": "外婆，姥姥；老奶奶",
            "sentences": [
                {"sentence": "婆婆煮嘅餸好合我胃口。（po4 po2 zyu2 ge3 sung3 hou2 hap6 ngo5 wai6 hau2.）", "translate": "外婆做的饭菜很对我的胃口。"},
                {"sentence": "扶婆婆過馬路。（fu4 po4 po2 gwo3 maa5 lou6.）", "translate": "搀扶老奶奶过马路。"}
            ]
        }
    ]
}

# L12: 家居设施与日常用品全套
L12_DATA = {
    "level": "L12",
    "name": "家居设施与日常用品",
    "description": "涵盖现代家庭家具家电、厨卫设施与日常生活必需品",
    "words": [
        {
            "word": "梳化",
            "jyutping": "so1 faa2",
            "pos": "名",
            "meaning": "沙发",
            "sentences": [
                {"sentence": "張真皮梳化坐得好舒服。（zoeng1 zan1 pei4 so1 faa2 co5 dak1 hou2 syu1 fuk6.）", "translate": "那张真皮沙发坐着很舒服。"},
                {"sentence": "放工返屋企攤喺梳化睇電視。（fong3 gung1 faan1 uk1 kei2 taan1 hai2 so1 faa2 tai2 din6 si6.）", "translate": "下班回家瘫在沙发上看电视。"}
            ]
        },
        {
            "word": "茶几",
            "jyutping": "caa4 gei1",
            "pos": "名",
            "meaning": "茶几",
            "sentences": [
                {"sentence": "個茶几上面放咗幾盆鮮花。（go3 caa4 gei1 soeng6 min6 fong3 zo2 gei2 pun4 sin1 faa1.）", "translate": "茶几上面摆了几盆鲜花。"},
                {"sentence": "小心唔好撞到茶几角。（siu2 sam1 m4 hou2 zong6 dou2 caa4 gei1 gok3.）", "translate": "小心别撞到茶几角。"}
            ]
        },
        {
            "word": "衣櫃",
            "jyutping": "ji1 gwai6",
            "pos": "名",
            "meaning": "衣柜",
            "sentences": [
                {"sentence": "把洗乾淨嘅衫放返入衣櫃。（baa2 sai2 gon1 zeng6 ge3 saam1 fong3 faan1 jap6 ji1 gwai6.）", "translate": "把洗干净的衣服放回衣柜里。"},
                {"sentence": "衣櫃入面好多衫。（ji1 gwai6 jap6 min6 hou2 do1 saam1.）", "translate": "衣柜里面有很多衣服。"}
            ]
        },
        {
            "word": "風筒",
            "jyutping": "fung1 tung2",
            "pos": "名",
            "meaning": "吹风机，电吹风",
            "sentences": [
                {"sentence": "沖完涼用風筒吹乾頭髮。（cung1 jyun4 loeng4 jung6 fung1 tung2 ceoi1 gon1 tau4 faat3.）", "translate": "洗完澡用吹风机吹干头发。"},
                {"sentence": "呢個風筒風力好大。（ni1 go3 fung1 tung2 fung1 lik6 hou2 daai6.）", "translate": "这个吹风机风力很大。"}
            ]
        },
        {
            "word": "花灑",
            "jyutping": "faa1 saa2",
            "pos": "名",
            "meaning": "花洒，淋浴喷头",
            "sentences": [
                {"sentence": "浴室嘅花灑水壓好足。（juk6 sat1 ge3 faa1 saa2 seoi2 aat3 hou2 zuk1.）", "translate": "浴室的花洒水压很充足。"},
                {"sentence": "換個新花灑沖涼更爽。（wun6 go3 san1 faa1 saa2 cung1 loeng4 gang3 song2.）", "translate": "换个新花洒洗澡更畅快。"}
            ]
        },
        {
            "word": "電掣",
            "jyutping": "din6 zai3",
            "pos": "名",
            "meaning": "开关，电源插座",
            "sentences": [
                {"sentence": "臨出門記得熄晒所有電掣。（lam4 ceot1 mun4 gei3 dak1 sik1 saai3 so2 jau5 din6 zai3.）", "translate": "出门前记得关掉所有电源开关。"},
                {"sentence": "呢個電掣插座鬆咗。（ni1 go3 din6 zai3 caap3 zo6 sung1 zo2.）", "translate": "这个电源插座松动了。"}
            ]
        },
        {
            "word": "拖板",
            "jyutping": "to1 baan2",
            "pos": "名",
            "meaning": "接线板，插线板，排插",
            "sentences": [
                {"sentence": "插頭唔夠用，買個多功能拖板。（caap3 tau4 m4 gau3 jung6, maai5 go3 do1 gung1 nang4 to1 baan2.）", "translate": "插头不够用，买个多功能接线板。"},
                {"sentence": "唔好喺同一個拖板插太多大功率電器。（m4 hou2 hai2 tung4 jat1 go3 to1 baan2 caap3 taai3 do1 daai6 gung1 lik6 din6 hei3.）", "translate": "不要在同一个接线板插太多大功率电器。"}
            ]
        },
        {
            "word": "膠袋",
            "jyutping": "gaau1 doi2",
            "pos": "名",
            "meaning": "塑料袋",
            "sentences": [
                {"sentence": "去超市買嘢記得自備環保袋，少用膠袋。（heoi3 ciu1 si5 maai5 je5 gei3 dak1 zi6 bei6 waan4 bou2 doi2, siu2 jung6 gaau1 doi2.）", "translate": "去超市买东西记得自备环保袋，少用塑料袋。"},
                {"sentence": "攞個膠袋裝住啲垃圾。（lo2 go3 gaau1 doi2 zong1 zyu6 di1 laap6 saap3.）", "translate": "拿个塑料袋装着垃圾。"}
            ]
        },
        {
            "word": "紙巾",
            "jyutping": "zi2 gan1",
            "pos": "名",
            "meaning": "纸巾，餐巾纸",
            "sentences": [
                {"sentence": "借張紙巾抹下手唔該。（ze3 zoeng1 zi2 gan1 maat3 haa5 sau2 m4 goi1.）", "translate": "借张纸巾擦一下手麻烦。"},
                {"sentence": "隨身帶包紙巾好方便。（ceoi4 san1 daai3 baau1 zi2 gan1 hou2 fong1 bin6.）", "translate": "随身带包纸巾很方便。"}
            ]
        },
        {
            "word": "番梘",
            "jyutping": "faan1 gaan2",
            "pos": "名",
            "meaning": "肥皂，香皂",
            "sentences": [
                {"sentence": "用番梘洗手洗得好乾淨。（jung6 faan1 gaan2 sai2 sau2 sai2 dak1 hou2 gon1 zeng6.）", "translate": "用肥皂洗手洗得非常干净。"},
                {"sentence": "呢塊手工番梘有淡淡花香。（ni1 faai3 sau2 gung1 faan1 gaan2 jau5 daam6 daam6 faa1 hoeng1.）", "translate": "这块手工皂有淡淡的花香。"}
            ]
        }
    ]
}

# L13: 身体部位与就医看病健康
L13_DATA = {
    "level": "L13",
    "name": "身体部位与就医健康",
    "description": "涵盖人体生理部位称谓与生病、看诊就医粤语口语",
    "words": [
        {
            "word": "頸",
            "jyutping": "geng2",
            "pos": "名",
            "meaning": "脖子，颈部",
            "sentences": [
                {"sentence": "成日低頭睇電話，條頸好酸痛。（seng4 jat6 dai1 tau4 tai2 din6 waa2, tiu4 geng2 hou2 syun1 tung3.）", "translate": "整天低头看手机，脖子很酸痛。"},
                {"sentence": "天氣凍要圍條圍巾保暖條頸。（tin1 hei3 dung3 jiu3 wai4 tiu4 wai4 gan1 bou2 nyun5 tiu4 geng2.）", "translate": "天气冷要围围巾给脖子保暖。"}
            ]
        },
        {
            "word": "肚",
            "jyutping": "tou5",
            "pos": "名",
            "meaning": "肚子，腹部",
            "sentences": [
                {"sentence": "食錯嘢搞到肚痛。（sik6 co3 je5 gaau2 dou3 tou5 tung3.）", "translate": "吃坏东西搞得肚子痛。"},
                {"sentence": "摸下個肚，食得好飽。（mo2 haa5 go3 tou5, sik6 dak1 hou2 baau2.）", "translate": "摸一下肚子，吃得好饱。"}
            ]
        },
        {
            "word": "背脊",
            "jyutping": "bui3 zek3",
            "pos": "名",
            "meaning": "后背，背部",
            "sentences": [
                {"sentence": "做完運動成個背脊都係汗。（zou6 jyun4 wan6 dung6 seng4 go3 bui3 zek3 dou1 hai6 hon6.）", "translate": "做完运动整个后背都是汗水。"},
                {"sentence": "坐姿要端正，唔好駝住背脊。（co5 zi1 jiu3 dyun1 zing3, m4 hou2 to4 zyu6 bui3 zek3.）", "translate": "坐姿要端正，不要弓着背。"}
            ]
        },
        {
            "word": "膝頭哥",
            "jyutping": "sat1 tau4 go1",
            "pos": "名",
            "meaning": "膝盖",
            "sentences": [
                {"sentence": "跑步跌親整親個膝頭哥。（paau2 bou6 dit3 can1 zing2 can1 go3 sat1 tau4 go1.）", "translate": "跑步摔倒弄伤了膝盖。"},
                {"sentence": "落雨天膝頭哥容易風濕痛。（lok6 jyu5 tin1 sat1 tau4 go1 jung4 ji6 fung1 sap1 tung3.）", "translate": "下雨天膝盖容易风湿酸痛。"}
            ]
        },
        {
            "word": "睇醫生",
            "jyutping": "tai2 ji1 sang1",
            "pos": "动",
            "meaning": "看医生，就医门诊",
            "sentences": [
                {"sentence": "發燒成三十九度，快啲去睇醫生。（faat3 siu1 seng4 saam1 sap6 gau2 dou6, faai3 di1 heoi3 tai2 ji1 sang1.）", "translate": "发烧将近39度，快点去看医生。"},
                {"sentence": "睇完醫生記得按時食藥。（tai2 jyun4 ji1 sang1 gei3 dak1 on3 si4 sik6 joek6.）", "translate": "看完医生记得按时吃药。"}
            ]
        },
        {
            "word": "發燒",
            "jyutping": "faat3 siu1",
            "pos": "动",
            "meaning": "发烧，发热",
            "sentences": [
                {"sentence": "佢發燒出咗成身汗。（keoi5 faat3 siu1 ceot1 zo2 seng4 san1 hon6.）", "translate": "他发烧出了一身汗。"},
                {"sentence": "用探热针量下有冇發燒。（jung6 taam3 jit6 zam1 loeng4 haa5 jau5 mou5 faat3 siu1.）", "translate": "用体温计测一下有没有发烧。"}
            ]
        },
        {
            "word": "感冒",
            "jyutping": "gam2 mou6",
            "pos": "名/动",
            "meaning": "感冒，患伤风",
            "sentences": [
                {"sentence": "轉季天氣好易感冒。（zyun2 gwai3 tin1 hei3 hou2 ji3 gam2 mou6.）", "translate": "换季时节很容易感冒。"},
                {"sentence": "感冒要多飲溫水多休息。（gam2 mou6 jiu3 do1 jam2 wan1 seoi2 do1 jau1 sik1.）", "translate": "感冒要多喝温水多休息。"}
            ]
        },
        {
            "word": "肚痛",
            "jyutping": "tou5 tung3",
            "pos": "动/形",
            "meaning": "腹痛，肚子痛",
            "sentences": [
                {"sentence": "食完生冷嘢之後好肚痛。（sik6 jyun4 saang1 laang5 je5 zi1 hau6 hou2 tou5 tung3.）", "translate": "吃完生冷生鲜之后肚子很痛。"},
                {"sentence": "肚痛得好犀利要去醫院。（tou5 tung3 dak1 hou2 sai1 lei6 jiu3 heoi3 ji1 jyun2.）", "translate": "肚子痛得厉害要去医院。"}
            ]
        },
        {
            "word": "食藥",
            "jyutping": "sik6 joek6",
            "pos": "动",
            "meaning": "吃药，服药",
            "sentences": [
                {"sentence": "食完飯半個鐘先好食藥。（sik6 jyun4 faan6 bun3 go3 zung1 sin1 hou2 sik6 joek6.）", "translate": "吃完饭半小时后再吃药。"},
                {"sentence": "醫生開嘅藥好有效。（ji1 sang1 hoi1 ge3 joek6 hou2 jau5 haau6.）", "translate": "医生开的药很见效。"}
            ]
        },
        {
            "word": "保重",
            "jyutping": "bou2 zung6",
            "pos": "动",
            "meaning": "保重（多用于叮嘱病患或离别祝福）",
            "sentences": [
                {"sentence": "天氣轉凍，多着衫保重身體！（tin1 hei3 zyun2 dung3, do1 zoek3 saam1 bou2 zung6 san1 tai2!）", "translate": "天气转冷，多穿衣服保重身体！"},
                {"sentence": "祝你早日康復，多多保重。（zuk1 nei5 zou2 jat6 hong1 fuk6, do1 do1 bou2 zung6.）", "translate": "祝你早日康复，多加保重。"}
            ]
        }
    ]
}

# L14: 粤菜烹饪手法与味道口感
L14_DATA = {
    "level": "L14",
    "name": "粤菜烹饪技艺与风味口感",
    "description": "涵盖广府烹饪核心动词（煲、炖、蒸、炒、焗、灼）与味觉体验",
    "words": [
        {
            "word": "煲",
            "jyutping": "bou1",
            "pos": "动/名",
            "meaning": "煲，煮（用锅慢熬）；砂锅",
            "sentences": [
                {"sentence": "煲返煲好湯畀屋企人飲。（bou1 faan1 bou1 hou2 tong1 bei2 uk1 kei2 jan4 jam2.）", "translate": "煲一锅好靓汤给家里人喝。"},
                {"sentence": "砂煲煲飯特別香。（saa1 bou1 bou1 faan6 dak6 bit6 hoeng1.）", "translate": "砂锅煲饭特别香。"}
            ]
        },
        {
            "word": "燉",
            "jyutping": "dan6",
            "pos": "动",
            "meaning": "隔水炖（保持原汁原味的烹饪法）",
            "sentences": [
                {"sentence": "燉盅燉湯原汁原味。（dan6 zung1 dan6 tong1 jyun4 zap1 jyun4 mei6.）", "translate": "用炖盅隔水炖汤原汁原味。"},
                {"sentence": "花膠燉雞補身好正。（faa1 gaau1 dan6 gai1 bou2 san1 hou2 zeng3.）", "translate": "花胶炖鸡滋补身体太棒了。"}
            ]
        },
        {
            "word": "蒸",
            "jyutping": "zing1",
            "pos": "动",
            "meaning": "清蒸（粤菜讲究清鲜脆嫩的核心手法）",
            "sentences": [
                {"sentence": "清蒸石斑魚火候啱啱好。（cing1 zing1 sek6 baan1 jyu4 fo2 hau6 ngaam1 ngaam1 hou2.）", "translate": "清蒸石斑鱼火候掌握得刚刚好。"},
                {"sentence": "水滾先落鑊蒸魚。（seoi2 gwan2 sin1 lok6 wok6 zing1 jyu4.）", "translate": "水沸腾了再下锅蒸鱼。"}
            ]
        },
        {
            "word": "灼",
            "jyutping": "coek3",
            "pos": "动",
            "meaning": "白灼（沸水烫熟以保持食材鲜甜嫩滑）",
            "sentences": [
                {"sentence": "白灼菜心好清甜爽脆。（baak6 coek3 coi3 sam1 hou2 cing1 tim4 song2 ceoi3.）", "translate": "白灼菜心非常清甜脆爽。"},
                {"sentence": "白灼海蝦最能食出原味。（baak6 coek3 hoi2 haa1 zeoi3 nang4 sik6 ceot1 jyun4 mei6.）", "translate": "白灼海虾最能品尝出本味鲜美。"}
            ]
        },
        {
            "word": "焗",
            "jyutping": "guk6",
            "pos": "动",
            "meaning": "焗，烘焙（利用密封蒸汽或烤炉加热）",
            "sentences": [
                {"sentence": "鮮茄焗豬扒飯係茶餐廳名菜。（sin1 ke2 guk6 zyu1 paa4 faan6 hai6 caa4 caan1 teng1 meng4 coi3.）", "translate": "鲜茄焗猪排饭是茶餐厅名菜。"},
                {"sentence": "鹽焗雞皮脆肉嫩，鹹香四溢。（jim4 guk6 gai1 pei4 ceoi3 juk6 nyun3, haam4 hoeng1 sei3 jat6.）", "translate": "盐焗鸡皮脆肉嫩，咸香四溢。"}
            ]
        },
        {
            "word": "鑊氣",
            "jyutping": "wok6 hei3",
            "pos": "名",
            "meaning": "锅气（高温烈火炒菜产生的独特香气）",
            "sentences": [
                {"sentence": "呢碟牛柳鑊氣十足，超好味！（ni1 dip6 ngau4 lau5 wok6 hei3 sap6 zuk1, ciu1 hou2 mei6!）", "translate": "这盘牛柳锅气十足，超级美味！"},
                {"sentence": "大排檔炒餸最有鑊氣。（daai6 paai4 dong3 caau2 sung3 zeoi3 jau5 wok6 hei3.）", "translate": "大排档炒菜最有独特的锅气。"}
            ]
        },
        {
            "word": "爽脆",
            "jyutping": "song2 ceoi3",
            "pos": "形",
            "meaning": "爽口脆嫩，口感鲜脆",
            "sentences": [
                {"sentence": "啲蝦仁好爽脆彈牙。（di1 haa1 jan4 hou2 song2 ceoi3 daan6 ngaa4.）", "translate": "那些虾仁非常爽脆Q弹。"},
                {"sentence": "涼拌黃瓜好爽脆。（loeng4 bun6 wong4 gwaa1 hou2 song2 ceoi3.）", "translate": "凉拌黄瓜很爽脆解腻。"}
            ]
        },
        {
            "word": "入味",
            "jyutping": "jap6 mei6",
            "pos": "形",
            "meaning": "入味，调味充分渗透",
            "sentences": [
                {"sentence": "燜牛腩燜得好入味。（mun6 ngau4 naam5 mun6 dak1 hou2 jap6 mei6.）", "translate": "炖牛腩炖得非常入味可口。"},
                {"sentence": "醃返半個鐘等啲雞肉入味。（jip3 faan1 bun3 go3 zung1 dang2 di1 gai1 juk6 jap6 mei6.）", "translate": "腌制半小时让鸡肉充分入味。"}
            ]
        }
    ]
}

# L15: 城市交通与市政地标设施
L15_DATA = {
    "level": "L15",
    "name": "城市交通与市政设施",
    "description": "涵盖城际交通、公共交通设施与城市出行标志",
    "words": [
        {
            "word": "機場",
            "jyutping": "gei1 coeng4",
            "pos": "名",
            "meaning": "机场，航空港",
            "sentences": [
                {"sentence": "搭機場快綫二十分鐘就到市區。（daap3 gei1 coeng4 faai3 sin3 jaa6 fan1 zung1 zau6 dou3 si5 keoi1.）", "translate": "坐机场快线二十分钟就能到市区。"},
                {"sentence": "我去機場接朋友機。（ngo5 heoi3 gei1 coeng4 zip3 pang4 jau5 gei1.）", "translate": "我去机场接朋友下飞机。"}
            ]
        },
        {
            "word": "碼頭",
            "jyutping": "maa5 tau4",
            "pos": "名",
            "meaning": "轮渡码头",
            "sentences": [
                {"sentence": "尖沙咀天星碼頭風景好靚。（zim1 saa1 zeoi2 tin1 sing1 maa5 tau4 fung1 ging2 hou2 leng3.）", "translate": "尖沙咀天星码头风景真漂亮。"},
                {"sentence": "喺碼頭搭船過海。（hai2 maa5 tau4 daap3 syun4 gwo3 hoi2.）", "translate": "在码头坐轮渡过海。"}
            ]
        },
        {
            "word": "天星小輪",
            "jyutping": "tin1 sing1 siu2 leon4",
            "pos": "名",
            "meaning": "天星小轮（维港标志性渡轮）",
            "sentences": [
                {"sentence": "搭天星小輪睇維港夜景好浪漫。（daap3 tin1 sing1 siu2 leon4 tai2 wai4 gong2 je6 ging2 hou2 long6 maan6.）", "translate": "乘坐天星小轮欣赏维港夜景很浪漫。"},
                {"sentence": "天星小輪票價好平。（tin1 sing1 siu2 leon4 piu3 gaa3 hou2 peng4.）", "translate": "天星小轮票价非常便宜亲民。"}
            ]
        },
        {
            "word": "叮叮車",
            "jyutping": "ding1 ding1 ce1",
            "pos": "名",
            "meaning": "叮叮车（香港岛双层有轨电车）",
            "sentences": [
                {"sentence": "坐叮叮車慢悠悠遊香港島。（co5 ding1 ding1 ce1 maan6 jau1 jau1 jau4 hoeng1 gong2 dou2.）", "translate": "坐叮叮车慢悠悠畅游香港岛。"},
                {"sentence": "叮叮車係百年歷史交通工具。（ding1 ding1 ce1 hai6 baak3 nin4 lik6 si2 gaau1 tung1 gung1 geoi6.）", "translate": "叮叮车是有百年历史的交通工具。"}
            ]
        },
        {
            "word": "天橋",
            "jyutping": "tin1 kiu4",
            "pos": "名",
            "meaning": "人行天桥，过街立交桥",
            "sentences": [
                {"sentence": "行天橋過馬路好安全。（haang4 tin1 kiu4 gwo3 maa5 lou6 hou2 on1 cyun4.）", "translate": "走人行天桥过马路非常安全。"},
                {"sentence": "中環天橋網絡四通八達。（zung1 waan4 tin1 kiu4 mong5 lok3 sei3 tung1 baat3 daat6.）", "translate": "中环的人行天桥系统四通八达。"}
            ]
        },
        {
            "word": "斑馬線",
            "jyutping": "baan1 maa5 sin3",
            "pos": "名",
            "meaning": "斑马线，人行横道",
            "sentences": [
                {"sentence": "過馬路一定要行斑馬線。（gwo3 maa5 lou6 jat1 ding6 jiu3 haang4 baan1 maa5 sin3.）", "translate": "过马路一定要走斑马线。"},
                {"sentence": "司機會喺斑馬線前停車禮讓行人。（si1 gei1 wui5 hai2 baan1 maa5 sin3 cin4 ting4 ce1 lai5 joeng6 hang4 jan4.）", "translate": "司机会在斑马线前停车礼让行人。"}
            ]
        },
        {
            "word": "紅綠燈",
            "jyutping": "hung4 luk6 dang1",
            "pos": "名",
            "meaning": "交通信号灯，红绿灯",
            "sentences": [
                {"sentence": "紅燈停，綠燈行。（hung4 dang1 ting4, luk6 dang1 haang4.）", "translate": "红灯停，绿灯行。"},
                {"sentence": "等緊紅綠燈過馬路。（dang2 gan2 hung4 luk6 dang1 gwo3 maa5 lou6.）", "translate": "正在等红绿灯过马路。"}
            ]
        }
    ]
}

# L16: 数字时间度量与高频连词
L16_DATA = {
    "level": "L16",
    "name": "数字时间度量与高频连词",
    "description": "涵盖大数表述、常用时间节点及因果转折等核心连接词",
    "words": [
        {
            "word": "同埋",
            "jyutping": "tung4 maai4",
            "pos": "连",
            "meaning": "和，以及，还有",
            "sentences": [
                {"sentence": "我同埋佢一齊去。（ngo5 tung4 maai4 keoi5 jat1 cai4 heoi3.）", "translate": "我和他一起去。"},
                {"sentence": "買咗麵包同埋牛奶。（maai5 zo2 min6 baau1 tung4 maai4 ngau4 naai5.）", "translate": "买了面包和牛奶。"}
            ]
        },
        {
            "word": "但係",
            "jyutping": "daan6 hai6",
            "pos": "连",
            "meaning": "但是，可是，不过",
            "sentences": [
                {"sentence": "雖然好貴，但係物有所值。（seoi1 jin4 hou2 gwai3, daan6 hai6 mat6 jau5 so2 zik6.）", "translate": "虽然很贵，但是物有所值。"},
                {"sentence": "佢想去，但係冇時間。（keoi5 soeng2 heoi3, daan6 hai6 mou5 si4 gaan3.）", "translate": "他想去，可是没有时间。"}
            ]
        },
        {
            "word": "因為",
            "jyutping": "jan1 wai6",
            "pos": "连",
            "meaning": "因为",
            "sentences": [
                {"sentence": "因為落雨，所以取消咗活動。（jan1 wai6 lok6 jyu5, so2 ji5 ceoi2 siu1 zo2 wut6 dung6.）", "translate": "因为下雨，所以取消了户外活动。"},
                {"sentence": "佢因為努力而成功。（keoi5 jan1 wai6 nou5 lik6 ji4 sing4 gung1.）", "translate": "他因为刻苦努力而获得成功。"}
            ]
        },
        {
            "word": "所以",
            "jyutping": "so2 ji5",
            "pos": "连",
            "meaning": "所以，因此",
            "sentences": [
                {"sentence": "今日放假，所以唔使返工。（gam1 jat6 fong3 gaa3, so2 ji5 m4 sai2 faan1 gung1.）", "translate": "今天放假，所以不用上班。"},
                {"sentence": "佢好勤力，所以成績好。（keoi5 hou2 kan4 lik6, so2 ji5 sing4 zik1 hou2.）", "translate": "他很勤奋，因此成绩优异。"}
            ]
        },
        {
            "word": "如果",
            "jyutping": "jyu4 gwo2",
            "pos": "连",
            "meaning": "如果，假如",
            "sentences": [
                {"sentence": "如果得閒就過嚟坐下。（jyu4 gwo2 dak1 haan4 zau6 gwo3 lai4 co5 haa5.）", "translate": "如果有空就过来坐坐。"},
                {"sentence": "如果有問題隨時問我。（jyu4 gwo2 jau5 man6 tai4 ceoi4 si4 man6 ngo5.）", "translate": "如果有什么问题随时问我。"}
            ]
        },
        {
            "word": "其實",
            "jyutping": "kei4 sat6",
            "pos": "副",
            "meaning": "其实，实际上",
            "sentences": [
                {"sentence": "其實佢個人心地好好。（kei4 sat6 keoi5 go3 jan4 sam1 dei6 hou2 hou2.）", "translate": "其实他这个人心地很善良。"},
                {"sentence": "件事其實好簡單。（gin6 si6 kei4 sat6 hou2 gaan2 daan1.）", "translate": "事情其实非常简单。"}
            ]
        },
        {
            "word": "總之",
            "jyutping": "zung2 zi1",
            "pos": "连/副",
            "meaning": "总之，总而言之",
            "sentences": [
                {"sentence": "總之小心為上。（zung2 zi1 siu2 sam1 wai4 soeng6.）", "translate": "总之小心为上策。"},
                {"sentence": "總之大家平安就最好。（zung2 zi1 daai6 gaa1 ping4 on1 zau6 zeoi3 hou2.）", "translate": "总而言之大家平平安安就最好了。"}
            ]
        },
        {
            "word": "頭先",
            "jyutping": "tau4 sin1",
            "pos": "名/副",
            "meaning": "刚才，方才",
            "sentences": [
                {"sentence": "頭先邊個打電話嚟？（tau4 sin1 bin1 go3 daa2 din6 waa2 lai4?）", "translate": "刚才谁打电话过来了？"},
                {"sentence": "我頭先喺路上撞見佢。（ngo5 tau4 sin1 hai2 lou6 soeng6 zong6 gin3 keoi5.）", "translate": "我刚才在路上碰见他了。"}
            ]
        }
    ]
}

# L17: 情感心理与人际态度表达
L17_DATA = {
    "level": "L17",
    "name": "情感心理与人际态度",
    "description": "涵盖粤语喜爱厌恶、心理感受及态度评价词汇",
    "words": [
        {
            "word": "鍾意",
            "jyutping": "zung1 ji3",
            "pos": "动",
            "meaning": "喜欢，喜爱，中意",
            "sentences": [
                {"sentence": "我好鍾意食廣東點心。（ngo5 hou2 zung1 ji3 sik6 gwong2 dung1 dim2 sam1.）", "translate": "我很喜欢吃广式点心。"},
                {"sentence": "你鍾唔鍾意睇戲啊？（nei5 zung1 m4 zung1 ji3 tai2 hei3 aa3?）", "translate": "你喜不喜欢看电影呀？"}
            ]
        },
        {
            "word": "憎",
            "jyutping": "zang1",
            "pos": "动",
            "meaning": "讨厌，厌恶，憎恨",
            "sentences": [
                {"sentence": "我最憎人講大話。（ngo5 zeoi3 zang1 jan4 gong2 daai6 waa6.）", "translate": "我最讨厌别人撒谎说谎。"},
                {"sentence": "唔好成日憎呢個憎嗰個。（m4 hou2 seng4 jat6 zang1 ni1 go3 zang1 go2 go3.）", "translate": "不要整天讨厌这个厌烦那个。"}
            ]
        },
        {
            "word": "驚",
            "jyutping": "geng1",
            "pos": "动/形",
            "meaning": "害怕，畏惧，恐慌",
            "sentences": [
                {"sentence": "唔使驚，有大家喺度。（m4 sai2 geng1, jau5 daai6 gaa1 hai2 dou6.）", "translate": "不用怕，有大家在这里。"},
                {"sentence": "佢好驚打雷。（keoi5 hou2 geng1 daa2 leoi4.）", "translate": "他很害怕打雷。"}
            ]
        },
        {
            "word": "急",
            "jyutping": "gap1",
            "pos": "形",
            "meaning": "急，急切，着急",
            "sentences": [
                {"sentence": "慢慢嚟，唔好咁急。（maan6 maan6 lai4, m4 hou2 gam3 gap1.）", "translate": "慢慢来，别这么着急。"},
                {"sentence": "件事好急，要即刻處理。（gin6 si6 hou2 gap1, jiu3 zik1 hak1 cyu2 lei5.）", "translate": "事情非常紧急，要立刻处理。"}
            ]
        },
        {
            "word": "慳",
            "jyutping": "haan1",
            "pos": "动",
            "meaning": "省，节省，节约",
            "sentences": [
                {"sentence": "慳得一蚊得一蚊。（haan1 dak1 jat1 man1 dak1 jat1 man1.）", "translate": "能省一块钱是一块钱。"},
                {"sentence": "慳水慳電，人人有責。（haan1 seoi2 haan1 din6, jan4 jan4 jau5 zaak3.）", "translate": "节约水电，人人有责。"}
            ]
        },
        {
            "word": "嘈",
            "jyutping": "cou4",
            "pos": "形/动",
            "meaning": "吵闹，喧闹，喧哗",
            "sentences": [
                {"sentence": "出面好嘈，聽唔清講咩。（ceot1 min6 hou2 cou4, teng1 m4 cing1 gong2 me1.）", "translate": "外面很吵，听不清楚在说什么。"},
                {"sentence": "唔好喺圖書館入面咁嘈。（m4 hou2 hai2 tou4 syu1 gun2 jap6 min6 gam3 cou4.）", "translate": "不要在图书馆里面这么吵闹喧哗。"}
            ]
        },
        {
            "word": "靜",
            "jyutping": "zing6",
            "pos": "形",
            "meaning": "安静，清静，冷清",
            "sentences": [
                {"sentence": "夜晚嘅鄉村好寧靜。（je6 maan5 ge3 hoeng1 cyun1 hou2 ning4 zing6.）", "translate": "夜晚的乡村非常宁静祥和。"},
                {"sentence": "呢間咖啡館好靜好舒服。（ni1 gaan1 gaa3 fe1 gun2 hou2 zing6 hou2 syu1 fuk6.）", "translate": "这家咖啡馆很安静很舒适。"}
            ]
        }
    ]
}

# L18: 日常社交礼貌与问候应答
L18_DATA = {
    "level": "L18",
    "name": "日常社交礼貌与应答应候",
    "description": "涵盖广府社交礼貌常用客套语与日常问候回应",
    "words": [
        {
            "word": "唔該",
            "jyutping": "m4 goi1",
            "pos": "叹/副",
            "meaning": "劳驾，麻烦，谢谢（用于请托人或接受轻微帮助）",
            "sentences": [
                {"sentence": "唔該借借。（m4 goi1 ze3 ze3.）", "translate": "劳驾借过借过。"},
                {"sentence": "唔該畀杯熱水我。（m4 goi1 bei2 bui1 jit6 seoi2 ngo5.）", "translate": "麻烦给我一杯热水，谢谢。"}
            ]
        },
        {
            "word": "多謝",
            "jyutping": "do1 ze6",
            "pos": "动/叹",
            "meaning": "多谢，感谢（用于接收礼物、款待或厚意）",
            "sentences": [
                {"sentence": "多謝你嘅禮物！（do1 ze6 nei5 ge3 lai5 mat6!）", "translate": "多谢你的精美礼物！"},
                {"sentence": "多謝大家嘅支持同厚愛。（do1 ze6 daai6 gaa1 ge3 zi1 ci4 tung4 hau5 oi3.）", "translate": "非常感谢大家的支持与厚爱。"}
            ]
        },
        {
            "word": "唔好意思",
            "jyutping": "m4 hou2 ji3 si3",
            "pos": "短语",
            "meaning": "不好意思，抱歉，打扰一下",
            "sentences": [
                {"sentence": "唔好意思，我遲到咗。（m4 hou2 ji3 si3, ngo5 ci4 dou3 zo2.）", "translate": "不好意思，我迟到了。"},
                {"sentence": "唔好意思，請問地鐵站喺邊度？（m4 hou2 ji3 si3, cing2 man6 dei6 tit3 zaam6 hai2 bin1 dou6?）", "translate": "不好意思打扰一下，请问地铁站在哪里？"}
            ]
        },
        {
            "word": "唔緊要",
            "jyutping": "m4 gan2 jiu3",
            "pos": "短语",
            "meaning": "没关系，不打紧，不要紧",
            "sentences": [
                {"sentence": "唔緊要啦，小事一樁。（m4 gan2 jiu3 laa1, siu2 si6 jat1 zong1.）", "translate": "没关系啦，小事一桩。"},
                {"sentence": "跌咗就算，最緊要人冇事，唔緊要。（dit3 zo2 zau6 syun3, zeoi3 gan2 jiu3 jan4 mou5 si6, m4 gan2 jiu3.）", "translate": "掉了就算了，最重要人没事，不要紧。"}
            ]
        },
        {
            "word": "拜拜",
            "jyutping": "baai1 baai3",
            "pos": "叹",
            "meaning": "再见，拜拜",
            "sentences": [
                {"sentence": "聽日見啦，拜拜！（ting1 jat6 gin3 laa1, baai1 baai3!）", "translate": "明天见啦，拜拜！"},
                {"sentence": "大家拜拜，路上小心！（daai6 gaa1 baai1 baai3, lou6 soeng6 siu2 sam1!）", "translate": "大家再见，路上当心！"}
            ]
        },
        {
            "word": "慢慢行",
            "jyutping": "maan6 maan6 haang4",
            "pos": "短语",
            "meaning": "慢走（送客礼貌用语）",
            "sentences": [
                {"sentence": "食飽喇？慢慢行啦，得閒再嚟坐。（sik6 baau2 laa3? maan6 maan6 haang4 laa1, dak1 haan4 zoi3 lai4 co5.）", "translate": "吃饱啦？慢走啊，有空常来坐。"},
                {"sentence": "夜深路黑，慢慢行小心睇路。（je6 sam1 lou6 hak1, maan6 maan6 haang4 siu2 sam1 tai2 lou6.）", "translate": "夜深天黑，慢走小心看路。"}
            ]
        }
    ]
}


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    all_new_levels = [
        L11_DATA, L12_DATA, L13_DATA, L14_DATA,
        L15_DATA, L16_DATA, L17_DATA, L18_DATA
    ]
    for data in all_new_levels:
        lvl = data["level"].lower()
        file_path = DATA_DIR / f"cantonese_{lvl}_{data['name'][:4]}.json"
        file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"已写入分卷: {file_path.name} (共 {len(data['words'])} 词)")


if __name__ == '__main__':
    main()
