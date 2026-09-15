# -*- coding: utf-8 -*-
"""全面粤语词库扩充生成脚本：
包含 L6 语法量词虚词、L7 茶餐厅与粤菜美食全集、L8 性格情绪与日常表达、L9 熟语歇后语、L10 现代职场商贸
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"

# L6: 语法量词与核心虚词助词
L6_DATA = {
    "level": "L6",
    "name": "粤语特征量词与语法虚词助词",
    "description": "涵盖粤语独特量词（嚿、粒、樖、啖等）与核心时态助词、语气词体系",
    "words": [
        {
            "word": "嚿",
            "jyutping": "gau6",
            "pos": "量",
            "meaning": "块（量词，用于块状物）",
            "sentences": [
                {"sentence": "食多嚿肉啦。（sik6 do1 gau6 juk6 laa1.）", "translate": "多吃一块肉吧。"},
                {"sentence": "地下有嚿大石頭。（dei6 haa2 jau5 gau6 daai6 sek6 tau4.）", "translate": "地上有一块大石头。"}
            ]
        },
        {
            "word": "粒",
            "jyutping": "nap1",
            "pos": "量",
            "meaning": "颗，粒（量词，用于小圆物）",
            "sentences": [
                {"sentence": "呢粒糖好甜。（ni1 nap1 tong2 hou2 tim4.）", "translate": "这颗糖很甜。"},
                {"sentence": "粒掣壞咗，禁唔到。（nap1 zai3 waai6 zo2, gam6 m4 dou2.）", "translate": "那个按钮坏了，按不下去。"}
            ]
        },
        {
            "word": "樖",
            "jyutping": "po1",
            "pos": "量",
            "meaning": "棵（量词，用于树木植物）",
            "sentences": [
                {"sentence": "門口有樖大榕樹。（mun4 hau2 jau5 po1 daai6 jung4 syu6.）", "translate": "门口有一棵大榕树。"},
                {"sentence": "呢樖花開得好靚。（ni1 po1 faa1 hoi1 dak1 hou2 leng3.）", "translate": "这株花开得很漂亮。"}
            ]
        },
        {
            "word": "啖",
            "jyutping": "daam6",
            "pos": "量",
            "meaning": "口（量词，用于饮、食的一口）",
            "sentences": [
                {"sentence": "飲啖水先講啦。（jam2 daam6 seoi2 sin1 gong2 laa1.）", "translate": "喝口水再讲吧。"},
                {"sentence": "食多啖飯，唔好嘥嘢。（sik6 do1 daam6 faan6, m4 hou2 saai1 je5.）", "translate": "多吃一口饭，别浪费东西。"}
            ]
        },
        {
            "word": "樽",
            "jyutping": "zeon1",
            "pos": "量/名",
            "meaning": "瓶（量词/名词，瓶子）",
            "sentences": [
                {"sentence": "唔該買樽水返嚟。（m4 goi1 maai5 zeon1 seoi2 faan1 lai4.）", "translate": "麻烦买一瓶水回来。"},
                {"sentence": "呢個玻璃樽好精緻。（ni1 go3 bo1 lei1 zeon1 hou2 zing1 zi3.）", "translate": "这个玻璃瓶很精致。"}
            ]
        },
        {
            "word": "隻",
            "jyutping": "zek3",
            "pos": "量",
            "meaning": "只（量词，用于动物、单只鞋袜手脚等）",
            "sentences": [
                {"sentence": "呢隻狗好乖。（ni1 zek3 gau2 hou2 gwaai1.）", "translate": "这只狗很乖巧。"},
                {"sentence": "我隻手整親咗。（ngo5 zek3 sau2 zing2 can1 zo2.）", "translate": "我的手受伤弄伤了。"}
            ]
        },
        {
            "word": "餐",
            "jyutping": "caan1",
            "pos": "量",
            "meaning": "顿，番（量词，用于饮食、责骂或打斗）",
            "sentences": [
                {"sentence": "今餐我請客！（gam1 caan1 ngo5 cing2 haak3!）", "translate": "这顿饭我请客！"},
                {"sentence": "佢畀阿媽鬧咗一餐。（keoi5 bei2 aa3 maa1 naau6 zo2 jat1 caan1.）", "translate": "他被妈妈狠狠训斥了一顿。"}
            ]
        },
        {
            "word": "陣",
            "jyutping": "zan6",
            "pos": "量/名",
            "meaning": "阵，一阵子（时间或风雨等）",
            "sentences": [
                {"sentence": "過咗一陣佢就返嚟。（gwo3 zo2 jat1 zan6 keoi5 zau6 faan1 lai4.）", "translate": "过了一会儿他就回来了。"},
                {"sentence": "啱啱落咗一陣狂風暴雨。（ngaam1 ngaam1 lok6 zo2 jat1 zan6 kwong4 fung1 bou6 jyu5.）", "translate": "刚刚下了一阵狂风暴雨。"}
            ]
        },
        {
            "word": "篤",
            "jyutping": "doek1",
            "pos": "量/名",
            "meaning": "坨，滩，堆；尽头",
            "sentences": [
                {"sentence": "地下有一篤水，小心跣倒。（dei6 haa2 jau5 jat1 doek1 seoi2, siu2 sam1 sin2 dou2.）", "translate": "地上有一滩水，小心滑倒。"},
                {"sentence": "行到巷仔最篤就係。（haang4 dou3 hong6 zai2 zeoi3 doek1 zau6 hai6.）", "translate": "走到小巷最尽头就是了。"}
            ]
        },
        {
            "word": "緊",
            "jyutping": "gan2",
            "pos": "助",
            "meaning": "着，正（动态助词，表示动作正在进行）",
            "sentences": [
                {"sentence": "我食緊飯，一陣覆你。（ngo5 sik6 gan2 faan6, jat1 zan6 fuk1 nei5.）", "translate": "我正在吃饭，一会儿回复你。"},
                {"sentence": "佢睇緊電視。（keoi5 tai2 gan2 din6 si6.）", "translate": "他正在看电视。"}
            ]
        },
        {
            "word": "咗",
            "jyutping": "zo2",
            "pos": "助",
            "meaning": "了（动态助词，表示动作完成）",
            "sentences": [
                {"sentence": "我已經做完咗功課。（ngo5 ji5 ging1 zou6 jyun4 zo2 gung1 fo3.）", "translate": "我已经做完了功课。"},
                {"sentence": "佢去咗香港旅行。（keoi5 heoi3 zo2 hoeng1 gong2 leoi5 hang4.）", "translate": "他去香港旅游了。"}
            ]
        },
        {
            "word": "過",
            "jyutping": "gwo3",
            "pos": "助/动",
            "meaning": "过（表示经历；超过；重新）",
            "sentences": [
                {"sentence": "我去過廣州塔。（ngo5 heoi3 gwo3 gwong2 zau1 taap3.）", "translate": "我去过广州塔。"},
                {"sentence": "寫得唔好，重新寫過。（se2 dak1 m4 hou2, cung4 san1 se2 gwo3.）", "translate": "写得不好，重新再写一遍。"}
            ]
        },
        {
            "word": "埋",
            "jyutping": "maai4",
            "pos": "助/动",
            "meaning": "连同，全部一起；靠拢",
            "sentences": [
                {"sentence": "食埋呢啖飯就走。（sik6 maai4 ni1 daam6 faan6 zau6 zau2.）", "translate": "吃完这口饭就走。"},
                {"sentence": "行埋一邊，咪阻住條路。（haang4 maai4 jat1 bin1, mai5 zo2 zyu6 tiu4 lou6.）", "translate": "靠边走，别挡住路。"}
            ]
        },
        {
            "word": "晒",
            "jyutping": "saai3",
            "pos": "助",
            "meaning": "全部，光，完（表示完全或极度）",
            "sentences": [
                {"sentence": "啲蛋糕畀人食晒喇。（di1 daan6 gou1 bei2 jan4 sik6 saai3 laa3.）", "translate": "蛋糕被人全吃光了。"},
                {"sentence": "真係唔該晒你！（zan1 hai6 m4 goi1 saai3 nei5!）", "translate": "真是太感谢你了！"}
            ]
        },
        {
            "word": "親",
            "jyutping": "can1",
            "pos": "助",
            "meaning": "到，及（动作触及某结果，多表意外受损）",
            "sentences": [
                {"sentence": "小心整親隻手。（siu2 sam1 zing2 can1 zek3 sau2.）", "translate": "小心弄伤了手。"},
                {"sentence": "佢跌親個膝頭哥。（keoi5 dit3 can1 go3 sat1 tau4 go1.）", "translate": "他摔伤了膝盖。"}
            ]
        },
        {
            "word": "定",
            "jyutping": "ding6",
            "pos": "助/副",
            "meaning": "预先，提前",
            "sentences": [
                {"sentence": "買定聽日嘅火車飛。（maai5 ding6 ting1 jat6 ge3 fo2 ce1 fei1.）", "translate": "提前买好明天的火车票。"},
                {"sentence": "準備定資料開會。（zeon2 bei6 ding6 zi1 liu2 hoi1 wui2.）", "translate": "提前准备好资料去开会。"}
            ]
        },
        {
            "word": "返",
            "jyutping": "faan1",
            "pos": "助/动",
            "meaning": "恢复，返回，重新回到原态",
            "sentences": [
                {"sentence": "休息完個人精神返晒。（jau1 sik1 jyun4 go3 jan4 zing1 san4 faan1 saai3.）", "translate": "休息完之后整个人重新精神起来了。"},
                {"sentence": "找返廿蚊畀你。（zaau2 faan1 jaa6 man1 bei2 nei5.）", "translate": "找回二十块钱给你。"}
            ]
        },
        {
            "word": "啫",
            "jyutping": "ze1",
            "pos": "助",
            "meaning": "而已，罢了（语气助词，表不过如此）",
            "sentences": [
                {"sentence": "講下笑啫，唔好嬲啦。（gong2 haa5 siu3 ze1, m4 hou2 nau1 laa1.）", "translate": "开个玩笑罢了，别生气啦。"},
                {"sentence": "幾十蚊啫，好平。（gei2 sap6 man1 ze1, hou2 peng4.）", "translate": "几十块钱而已，很便宜。"}
            ]
        },
        {
            "word": "喎",
            "jyutping": "wo3",
            "pos": "助",
            "meaning": "啊，据说（转述或提醒语气）",
            "sentences": [
                {"sentence": "天文台話聽日會落雨喎。（tin1 man4 toi4 waa6 ting1 jat6 wui5 lok6 jyu5 wo3.）", "translate": "天文台说明天会下雨呢。"},
                {"sentence": "好似幾好食喎。（hou2 ci5 gei2 hou2 sik6 wo3.）", "translate": "好像挺好吃的样子呢。"}
            ]
        },
        {
            "word": "添",
            "jyutping": "tim1",
            "pos": "助/副",
            "meaning": "还，再，连...也（表示递进或强调）",
            "sentences": [
                {"sentence": "唔記得帶鎖匙添！（m4 gei3 dak1 daai3 so2 si4 tim1!）", "translate": "居然还把钥匙给忘了！"},
                {"sentence": "飲多杯茶添啦。（jam2 do1 bui1 caa4 tim1 laa1.）", "translate": "再多喝一杯茶吧。"}
            ]
        }
    ]
}

# L7: 茶餐厅与经典粤港美食全集
L7_DATA = {
    "level": "L7",
    "name": "港式茶餐厅与粤菜美食全集",
    "description": "涵盖经典港式茶餐厅饮品、碟头饭、经典粤菜点心及街头地道小食",
    "words": [
        {
            "word": "茶走",
            "jyutping": "caa4 zau2",
            "pos": "名",
            "meaning": "茶走（奶茶改用炼奶代替淡奶与砂糖）",
            "sentences": [
                {"sentence": "伙計，一杯熱茶走！（fo2 gei3, jat1 bui1 jit6 caa4 zau2!）", "translate": "服务员，一杯热茶走！"},
                {"sentence": "茶走味道特別香滑。（caa4 zau2 mei6 dou6 dak6 bit6 hoeng1 waat6.）", "translate": "茶走味道特别香浓丝滑。"}
            ]
        },
        {
            "word": "鴛鴦",
            "jyutping": "jin1 joeng1",
            "pos": "名",
            "meaning": "鸳鸯（咖啡混合奶茶的经典饮品）",
            "sentences": [
                {"sentence": "凍鴛鴦少冰少甜。（dung3 jin1 joeng1 siu2 bing1 siu2 tim4.）", "translate": "冰鸳鸯少冰少糖。"},
                {"sentence": "鴛鴦融合咗咖啡同奶茶嘅香味。（jin1 joeng1 jung4 hap6 zo2 gaa3 fe1 tung4 naai5 caa4 ge3 hoeng1 mei6.）", "translate": "鸳鸯融合了咖啡与奶茶的独特香气。"}
            ]
        },
        {
            "word": "菠蘿油",
            "jyutping": "bo1 lo4 jau4",
            "pos": "名",
            "meaning": "菠萝油（热菠萝面包夹厚切冰牛油）",
            "sentences": [
                {"sentence": "剛出爐嘅菠蘿油冰火交融，超好食！（gong1 ceot1 lou4 ge3 bo1 lo4 jau4 bing1 fo2 gaau1 jung4, ciu1 hou2 sik6!）", "translate": "刚出炉的菠萝油冰火交融，太好吃了！"},
                {"sentence": "食下午茶必嗌菠蘿油。（sik6 haa6 zau3 caa4 bit1 aai3 bo1 lo4 jau4.）", "translate": "吃下午茶必点菠萝油。"}
            ]
        },
        {
            "word": "乾炒牛河",
            "jyutping": "gon1 caau2 ngau4 ho2",
            "pos": "名",
            "meaning": "干炒牛河（考验粤菜厨师镬气的经典炒河粉）",
            "sentences": [
                {"sentence": "一碟合格嘅乾炒牛河必須夠鑊氣。（jat1 dip6 hap6 gak3 ge3 gon1 caau2 ngau4 ho2 bit1 seoi1 gau3 wok6 hei3.）", "translate": "一盘合格的干炒牛河必须锅气十足。"},
                {"sentence": "牛肉好嫩，河粉條條分明。（ngau4 juk6 hou2 nyun3, ho4 fan2 tiu4 tiu4 fan1 ming4.）", "translate": "牛肉鲜嫩，河粉根根分明不上色过黑。"}
            ]
        },
        {
            "word": "滑蛋牛肉",
            "jyutping": "waat6 daan2 ngau4 juk6",
            "pos": "名",
            "meaning": "滑蛋牛肉饭（经典茶餐厅碟头饭）",
            "sentences": [
                {"sentence": "滑蛋牛肉飯嘅蛋好滑好嫩。（waat6 daan2 ngau4 juk6 faan6 ge3 daan2 hou2 waat6 hou2 nyun3.）", "translate": "滑蛋牛肉饭的鸡蛋非常滑嫩鲜美。"},
                {"sentence": "今晚煮滑蛋牛肉做晚餐。（gam1 maan5 zyu2 waat6 daan2 ngau4 juk6 zou6 maan5 caan1.）", "translate": "今晚做滑蛋牛肉当晚饭。"}
            ]
        },
        {
            "word": "西多士",
            "jyutping": "sai1 do1 si2",
            "pos": "名",
            "meaning": "法兰西多士（油炸裹蛋液吐司配牛油与糖浆）",
            "sentences": [
                {"sentence": "西多士淋上糖漿同牛油，邪惡又好食。（sai1 do1 si2 lam4 soeng5 tong4 zoeng1 tung4 ngau4 jau4, ce4 ok3 jau6 hou2 sik6.）", "translate": "西多士浇上糖浆和黄油，卡路里爆棚又极美味。"},
                {"sentence": "下晝食個西多士飲杯奶茶。（haa6 zau3 sik6 go3 sai1 do1 si2 jam2 bui1 naai5 caa4.）", "translate": "下午吃个西多士喝杯奶茶。"}
            ]
        },
        {
            "word": "車仔麵",
            "jyutping": "ce1 zai2 min6",
            "pos": "名",
            "meaning": "车仔面（香港平民自选配料汤面）",
            "sentences": [
                {"sentence": "車仔麵可以自己揀餸，我揀咗牛腩同蘿蔔。（ce1 zai2 min6 ho2 ji5 zi6 gei2 gaan2 sung3, ngo5 gaan2 zo2 ngau4 naam5 tung4 lo4 baak6.）", "translate": "车仔面可以自选配菜，我选了牛腩和白萝卜。"},
                {"sentence": "車仔麵嘅咖喱汁好濃。（ce1 zai2 min6 ge3 gaa3 lei1 zap1 hou2 nung4.）", "translate": "车仔面的咖喱酱汁非常香浓。"}
            ]
        },
        {
            "word": "魚蛋",
            "jyutping": "jyu4 daan2",
            "pos": "名",
            "meaning": "鱼丸，鱼蛋",
            "sentences": [
                {"sentence": "街頭咖喱魚蛋好彈牙。（gaai1 tau4 gaa3 lei1 jyu4 daan2 hou2 daan6 ngaa4.）", "translate": "街头的咖喱鱼蛋非常有嚼劲弹牙。"},
                {"sentence": "食完一串咖喱魚蛋仲想食。（sik6 jyun4 jat1 cyun3 gaa3 lei1 jyu4 daan2 zung6 soeng2 sik6.）", "translate": "吃完一串咖喱鱼蛋还想吃。"}
            ]
        },
        {
            "word": "雞蛋仔",
            "jyutping": "gai1 daan6 zai2",
            "pos": "名",
            "meaning": "鸡蛋仔（著名香港街头烘焙小吃）",
            "sentences": [
                {"sentence": "熱辣辣嘅雞蛋仔外脆內軟。（jit6 laat6 laat6 ge3 gai1 daan6 zai2 ngoi6 ceoi3 noi6 jyun5.）", "translate": "热气腾腾的鸡蛋仔外皮酥脆内里松软。"},
                {"sentence": "買底原味雞蛋仔邊行邊食。（maai5 dai2 jyun4 mei6 gai1 daan6 zai2 bin1 haang4 bin1 sik6.）", "translate": "买一整份原味鸡蛋仔边走边吃。"}
            ]
        },
        {
            "word": "碗仔翅",
            "jyutping": "wun2 zai2 ci3",
            "pos": "名",
            "meaning": "碗仔翅（仿鱼翅街头羹汤小吃）",
            "sentences": [
                {"sentence": "碗仔翅加啲麻油同胡椒粉先好食。（wun2 zai2 ci3 gaa1 di1 maa4 jau4 tung4 wu4 ziu1 fan2 sin1 hou2 sik6.）", "translate": "碗仔翅加点芝麻油和胡椒粉才好吃。"},
                {"sentence": "冬日街頭食碗熱辣辣嘅碗仔翅。（dung1 jat6 gaai1 tau4 sik6 wun2 jit6 laat6 laat6 ge3 wun2 zai2 ci3.）", "translate": "冬天街头吃一碗热腾腾的碗仔翅。"}
            ]
        },
        {
            "word": "煎釀三寶",
            "jyutping": "zin1 joeng6 saam1 bou2",
            "pos": "名",
            "meaning": "煎酿三宝（酿鲮鱼肉馅的街头小吃）",
            "sentences": [
                {"sentence": "煎釀三寶有釀青椒、茄子同豆腐。（zin1 joeng6 saam1 bou2 jau5 joeng6 cing1 ziu1, ke2 zi2 tung4 dau6 fu6.）", "translate": "煎酿三宝有酿青椒、酿茄子和酿豆腐。"},
                {"sentence": "點甜豉油食煎釀三寶好正。（dim2 tim4 si6 jau4 sik6 zin1 joeng6 saam1 bou2 hou2 zeng3.）", "translate": "蘸着甜酱油吃煎酿三宝太赞了。"}
            ]
        },
        {
            "word": "雙皮奶",
            "jyutping": "soeng1 pei4 naai5",
            "pos": "名",
            "meaning": "双皮奶（顺德传统水牛奶甜品）",
            "sentences": [
                {"sentence": "順德大良雙皮奶奶香濃郁。（seon6 dak1 daai6 loeng4 soeng1 pei4 naai5 naai5 hoeng1 nung4 juk1.）", "translate": "顺德大良双皮奶奶香极其浓郁。"},
                {"sentence": "冷熱雙皮奶各有風味。（laang5 jit6 soeng1 pei4 naai5 gok3 jau5 fung1 mei6.）", "translate": "冰的和热的双皮奶各有千秋。"}
            ]
        },
        {
            "word": "楊枝甘露",
            "jyutping": "joeng4 zi1 gam1 lou6",
            "pos": "名",
            "meaning": "杨枝甘露（芒果西米柚子经典甜汤）",
            "sentences": [
                {"sentence": "夏天食一碗冰凍楊枝甘露好消暑。（haa6 tin1 sik6 jat1 wun2 bing1 dung3 joeng4 zi1 gam1 lou6 hou2 siu1 syu2.）", "translate": "夏天吃一碗冰镇杨枝甘露非常消暑解渴。"},
                {"sentence": "芒果好甜，西米好爽。（mong1 gwo2 hou2 tim4, sai1 mai5 hou2 song2.）", "translate": "芒果很甜，西米非常爽滑。"}
            ]
        },
        {
            "word": "燒鵝",
            "jyutping": "siu1 ngo4",
            "pos": "名",
            "meaning": "烧鹅（皮脆肉嫩的经典广式烧味）",
            "sentences": [
                {"sentence": "深井燒鵝皮脆肉嫩，肉汁好多。（sam1 zing2 siu1 ngo4 pei4 ceoi3 juk6 nyun3, juk6 zap1 hou2 do1.）", "translate": "深井烧鹅皮脆肉嫩，汁水丰盈。"},
                {"sentence": "點酸梅醬食燒鵝真係絕配。（dim2 syun1 mui4 zoeng3 sik6 siu1 ngo4 zan1 hai6 zyut6 pui3.）", "translate": "蘸着酸梅酱吃烧鹅真是绝配。"}
            ]
        },
        {
            "word": "牛腩",
            "jyutping": "ngau4 naam5",
            "pos": "名",
            "meaning": "牛腩（柱侯牛腩）",
            "sentences": [
                {"sentence": "清湯牛腩煲燉得好軟爛。（cing1 tong1 ngau4 naam5 bou1 dan6 dak1 hou2 jyun5 laan6.）", "translate": "清汤牛腩煲炖得非常软烂可口。"},
                {"sentence": "牛腩麵啲湯底好濃香。（ngau4 naam5 min6 di1 tong1 dai2 hou2 nung4 hoeng1.）", "translate": "牛腩面的汤底非常浓厚鲜香。"}
            ]
        }
    ]
}

# L8: 性格脾气与情绪心理表达
L8_DATA = {
    "level": "L8",
    "name": "地道性格气质与心理情绪表达",
    "description": "涵盖广府特色性格描摹、神态刻画与情绪反应口语词汇",
    "words": [
        {
            "word": "牙擦",
            "jyutping": "ngaa4 caat3",
            "pos": "形",
            "meaning": "嚣张，爱吹嘘，狂妄自大",
            "sentences": [
                {"sentence": "佢份人好牙擦，成日自誇。（keoi5 fan6 jan4 hou2 ngaa4 caat3, seng4 jat6 zi6 kwaa1.）", "translate": "他为人很狂妄自大，整天自我吹嘘。"},
                {"sentence": "有真本事嘅人唔會咁牙擦。（jau5 zan1 bun2 si6 ge3 jan4 m4 wui5 gam3 ngaa4 caat3.）", "translate": "有真本领的人不会这么狂妄嚣张。"}
            ]
        },
        {
            "word": "心悒",
            "jyutping": "sam1 jap1",
            "pos": "形",
            "meaning": "心里难过，酸楚，揪心心疼",
            "sentences": [
                {"sentence": "見到佢生活咁艱難，睇到人心悒。（gin3 dou2 keoi5 sang1 wut6 gam3 gaan1 naan4, tai2 dou2 jan4 sam1 jap1.）", "translate": "看到他生活这么艰辛，看得人心里阵阵酸楚。"},
                {"sentence": "唔好諗咁多令人心悒嘅事。（m4 hou2 nam2 gam3 do1 ling6 jan4 sam1 jap1 ge3 si6.）", "translate": "别想那么多让人心里难过的事情。"}
            ]
        },
        {
            "word": "生性",
            "jyutping": "saang1 sing3",
            "pos": "形",
            "meaning": "懂事，乖巧成器，体谅父母",
            "sentences": [
                {"sentence": "個仔大個咗，識得幫手好生性。（go3 zai2 daai6 go3 zo2, sik1 dak1 bong1 sau2 hou2 saang1 sing3.）", "translate": "儿子长大了，懂得帮忙非常懂事。"},
                {"sentence": "你要生性做人，唔好令父母擔心。（nei5 jiu3 saang1 sing3 zou6 jan4, m4 hou2 ling6 fu6 mou5 daam1 sam1.）", "translate": "你要做个懂事争气的人，别让父母担心。"}
            ]
        },
        {
            "word": "百厭",
            "jyutping": "baak3 jim3",
            "pos": "形",
            "meaning": "调皮，淘气捣蛋",
            "sentences": [
                {"sentence": "呢個細路仔好百厭，四圍亂跑。（ni1 go3 sai3 lou6 zai2 hou2 baak3 jim3, sei3 wai4 lyun6 paau2.）", "translate": "这个小孩子很调皮捣蛋，到处乱跑。"},
                {"sentence": "雖然百厭，但好聰明。（seoi1 jin4 baak3 jim3, daan6 hou2 cung1 ming4.）", "translate": "虽然淘气，但是很聪明。"}
            ]
        },
        {
            "word": "扭計",
            "jyutping": "nau2 gai2",
            "pos": "动",
            "meaning": "耍脾气，闹别扭（多指小孩撒娇哭闹）",
            "sentences": [
                {"sentence": "小朋友想買玩具就喺度扭計。（siu2 pang4 jau5 soeng2 maai5 wun6 geoi6 zau6 hai2 dou6 nau2 gai2.）", "translate": "小朋友想买玩具就在那里闹别扭哭闹。"},
                {"sentence": "乖啦，唔好再扭計喇。（gwaai1 laa1, m4 hou2 zoi3 nau2 gai2 laa3.）", "translate": "乖啦，不要再闹脾气了。"}
            ]
        },
        {
            "word": "發老脾",
            "jyutping": "faat3 lou5 pei4",
            "pos": "动",
            "meaning": "发脾气，大动肝火",
            "sentences": [
                {"sentence": "好好講嘢，唔好郁啲就發老脾。（hou2 hou2 gong2 je5, m4 hou2 juk1 di1 zau6 faat3 lou5 pei4.）", "translate": "好好说话，别动不动就大发雷霆。"},
                {"sentence": "老細今日唔知點解發老脾。（lou5 sai3 gam1 jat6 m4 zi1 dim2 gaai2 faat3 lou5 pei4.）", "translate": "老板今天不知为何大发脾气。"}
            ]
        },
        {
            "word": "大懵",
            "jyutping": "daai6 mung2",
            "pos": "形",
            "meaning": "粗心大意，健忘，糊里糊涂",
            "sentences": [
                {"sentence": "我真係大懵，出門又唔記得帶電話。（ngo5 zan1 hai6 daai6 mung2, ceot1 mun4 jau6 m4 gei3 dak1 daai3 din6 waa2.）", "translate": "我真是太糊涂粗心了，出门又忘了带手机。"},
                {"sentence": "佢做嘢好大懵，成日漏嘢。（keoi5 zou6 je5 hou2 daai6 mung2, seng4 jat6 lau6 je5.）", "translate": "他做事很大意，经常丢三落四。"}
            ]
        },
        {
            "word": "論盡",
            "jyutping": "leon6 zeon6",
            "pos": "形",
            "meaning": "笨手笨脚，动作不灵活，笨拙",
            "sentences": [
                {"sentence": "搬嘢小心啲，唔好咁論盡跌爛嘢。（bun1 je5 siu2 sam1 di1, m4 hou2 gam3 leon6 zeon6 dit3 laan6 je5.）", "translate": "搬东西小心点，别笨手笨脚摔烂了东西。"},
                {"sentence": "佢行步路都論論盡盡。（keoi5 haang4 bou6 lou6 dou1 leon6 leon6 zeon6 zeon6.）", "translate": "他走起路来都笨手笨脚跌跌撞撞的。"}
            ]
        },
        {
            "word": "肉緊",
            "jyutping": "juk6 gan2",
            "pos": "形",
            "meaning": "紧张心焦，极度投入，激动用力",
            "sentences": [
                {"sentence": "睇世界盃決賽睇到大家超肉緊。（tai2 sai3 gaai3 bui1 kyut3 coi3 tai2 dou3 daai6 gaa1 ciu1 juk6 gan2.）", "translate": "看世界杯决赛看得大家极度紧张投入。"},
                {"sentence": "見到得意BB忍唔住想肉緊咬一啖。（gin3 dou2 dak1 ji3 BB jan2 m4 zyu6 soeng2 juk6 gan2 ngaau5 jat1 daam6.）", "translate": "看到可爱宝宝忍不住喜欢得想咬一口。"}
            ]
        },
        {
            "word": "唔忿氣",
            "jyutping": "m4 fan5 hei3",
            "pos": "形/动",
            "meaning": "不服气，心有不甘",
            "sentences": [
                {"sentence": "明明係佢贏，輸咗比賽好唔忿氣。（ming4 ming4 hai6 keoi5 jeng4, syu1 zo2 bei2 coi3 hou2 m4 fan5 hei3.）", "translate": "明明该是他赢的，输了比赛非常不服气。"},
                {"sentence": "唔忿氣就下次再贏返！（m4 fan5 hei3 zau6 haa6 ci3 zoi3 jeng4 faan1!）", "translate": "不服气那就下次再赢回来！"}
            ]
        }
    ]
}

# L9: 经典广府熟语与民间歇后语
L9_DATA = {
    "level": "L9",
    "name": "经典广府熟语与民间歇后语",
    "description": "涵盖广府语言智慧结晶、生动形象的歇后语与民间习惯用语",
    "words": [
        {
            "word": "水過鴨背",
            "jyutping": "seoi2 gwo3 aap3 bui3",
            "pos": "熟语",
            "meaning": "像水从鸭背流过一样毫无痕迹，转眼全忘光",
            "sentences": [
                {"sentence": "教咗佢幾次都水過鴨背，轉頭就唔記得。（gaau3 zo2 keoi5 gei2 ci3 dou1 seoi2 gwo3 aap3 bui3, zyun3 tau4 zau6 m4 gei3 dak1.）", "translate": "教了他几次都像耳旁风，转眼就忘得一干二净。"},
                {"sentence": "做人要吸收教訓，唔好水過鴨背。（zou6 jan4 jiu3 kap1 sau1 gaau3 fan3, m4 hou2 seoi2 gwo3 aap3 bui3.）", "translate": "做人要吸取教训，别听过就算全不往心里去。"}
            ]
        },
        {
            "word": "扮豬食老虎",
            "jyutping": "baan6 zyu1 sik6 lou5 fu2",
            "pos": "熟语",
            "meaning": "装傻充愣，故意示弱以麻痹对手暗中取胜",
            "sentences": [
                {"sentence": "佢表面好老實，其實係扮豬食老虎。（keoi5 biu1 min6 hou2 lou5 sat6, kei4 sat6 hai6 baan6 zyu1 sik6 lou5 fu2.）", "translate": "他表面上很老实，其实是在扮猪吃老虎。"},
                {"sentence": "商場競爭對手最叻扮豬食老虎。（soeng1 coeng4 ging6 zang1 deoi3 sau2 zeoi3 lek1 baan6 zyu1 sik6 lou5 fu2.）", "translate": "商场竞争对手最擅长装弱示好暗度陈仓。"}
            ]
        },
        {
            "word": "死雞撐飯蓋",
            "jyutping": "sei2 gai1 caang1 faan6 goi3",
            "pos": "熟语",
            "meaning": "死不认错，铁证如山依然硬拗抵赖",
            "sentences": [
                {"sentence": "明明做錯咗仲喺度死雞撐飯蓋。（ming4 ming4 zou6 co3 zo2 zung6 hai2 dou6 sei2 gai1 caang1 faan6 goi3.）", "translate": "明明做错了还在那里死不认账死硬狡辩。"},
                {"sentence": "認錯道歉好過死雞撐飯蓋。（jing6 co3 dou6 hip3 hou2 gwo3 sei2 gai1 caang1 faan6 goi3.）", "translate": "认错道歉好过死鸭子嘴硬到底。"}
            ]
        },
        {
            "word": "扯貓尾",
            "jyutping": "ce2 maau1 mei5",
            "pos": "熟语",
            "meaning": "唱双簧，串通一气，暗中合谋互相掩护演戏",
            "sentences": [
                {"sentence": "佢哋兩個喺度扯貓尾呃人。（keoi5 dei6 loeng5 go3 hai2 dou6 ce2 maau1 mei5 ngaak1 jan4.）", "translate": "他们两个在那唱双簧合伙骗人。"},
                {"sentence": "咪喺我面前扯貓尾啦，我睇穿晒。（mai5 hai2 ngo5 min6 cin4 ce2 maau1 mei5 laa1, ngo5 tai2 cyun1 saai3.）", "translate": "别在我面前演双簧了，我全看穿了。"}
            ]
        },
        {
            "word": "過橋抽板",
            "jyutping": "gwo3 kiu4 cau1 baan2",
            "pos": "熟语",
            "meaning": "过河拆桥，得到好处后就背弃帮助过自己的人",
            "sentences": [
                {"sentence": "做人千祈唔好過橋抽板。（zou6 jan4 cin1 kei4 m4 hou2 gwo3 kiu4 cau1 baan2.）", "translate": "做人千万不要过河拆桥忘恩负义。"},
                {"sentence": "幫完佢之後佢即刻過橋抽板。（bong1 jyun4 keoi5 zi1 hau6 keoi5 zik1 hak1 gwo3 kiu4 cau1 baan2.）", "translate": "帮完他之后他立刻过河拆桥不认人。"}
            ]
        },
        {
            "word": "一擔擔",
            "jyutping": "jat1 daam1 daam1",
            "pos": "熟语",
            "meaning": "半斤八两，彼此差不多（多含贬义）",
            "sentences": [
                {"sentence": "佢哋兩個做嘢態度都係一擔擔。（keoi5 dei6 loeng5 go3 zou6 je5 taai3 dou6 dou1 hai6 jat1 daam1 daam1.）", "translate": "他们两个做事态度都是半斤八两一个样。"},
                {"sentence": "邊個都唔好話邊個，一擔擔。（bin1 go3 dou1 m4 hou2 waa6 bin1 go3, jat1 daam1 daam1.）", "translate": "谁也别笑话谁，彼此半斤八两。"}
            ]
        },
        {
            "word": "牛頭唔對馬嘴",
            "jyutping": "ngau4 tau4 m4 deoi3 maa5 zeoi2",
            "pos": "熟语",
            "meaning": "答非所问，前言不搭后语",
            "sentences": [
                {"sentence": "問佢東佢答西，真係牛頭唔對馬嘴。（man6 keoi5 dung1 keoi5 daap3 sai1, zan1 hai6 ngau4 tau4 m4 deoi3 maa5 zeoi2.）", "translate": "问他东他答西，真是前言不搭后语。"},
                {"sentence": "你講嘅嘢同呢件事牛頭唔對馬嘴。（nei5 gong2 ge3 je5 tung4 ni1 gin6 si6 ngau4 tau4 m4 deoi3 maa5 zeoi2.）", "translate": "你说的话跟这件事完全搭不上边。"}
            ]
        }
    ]
}

# L10: 现代职场商贸与都市金钱生活
L10_DATA = {
    "level": "L10",
    "name": "现代职场商贸与都市金融生活",
    "description": "涵盖薪资福利、求职晋升、财务账目与职场摸鱼博弈词汇",
    "words": [
        {
            "word": "出糧",
            "jyutping": "ceot1 loeng4",
            "pos": "动",
            "meaning": "发薪水，发工资",
            "sentences": [
                {"sentence": "今日出糧，今晚食餐好嘅慶祝！（gam1 jat6 ceot1 loeng4, gam1 maan5 sik6 caan1 hou2 ge3 hing3 zuk1!）", "translate": "今天发工资，今晚吃顿大餐庆祝！"},
                {"sentence": "每個月最開心就係出糧嗰日。（mui5 go3 jyut6 zeoi3 hoi1 sam1 zau6 hai6 ceot1 loeng4 go2 jat6.）", "translate": "每个月最开心的就是发工资那天。"}
            ]
        },
        {
            "word": "花紅",
            "jyutping": "faa1 hung4",
            "pos": "名",
            "meaning": "奖金，年终奖，业绩分红",
            "sentences": [
                {"sentence": "公司今年業績好，派咗幾個月花紅。（gung1 si1 gam1 nin4 jip6 zik1 hou2, paai3 zo2 gei2 go3 jyut6 faa1 hung4.）", "translate": "公司今年业绩好，发了几个月薪资的奖金分红。"},
                {"sentence": "辛苦成年，最期待就係筆花紅。（san1 fu2 seng4 nin4, zeoi3 kei4 doi6 zau6 hai6 bat1 faa1 hung4.）", "translate": "辛苦了一整年，最期待的就是那笔年终奖。"}
            ]
        },
        {
            "word": "雙糧",
            "jyutping": "soeng1 loeng4",
            "pos": "名",
            "meaning": "十三薪，年底双薪",
            "sentences": [
                {"sentence": "份合約包年底雙糧。（fan6 hap6 joek3 baau1 nin4 dai2 soeng1 loeng4.）", "translate": "这份工作合同包含年底双薪。"},
                {"sentence": "有雙糧加花紅，過個肥年。（jau5 soeng1 loeng4 gaa1 faa1 hung4, gwo3 go3 fei4 nin4.）", "translate": "有双薪加奖金分红，过个丰盛肥年。"}
            ]
        },
        {
            "word": "遞信",
            "jyutping": "dai6 seon3",
            "pos": "动",
            "meaning": "递交辞职信，辞职",
            "sentences": [
                {"sentence": "佢搵到更好嘅工，琴日遞咗信。（keoi5 wan2 dou2 gang3 hou2 ge3 gung1, kam4 jat6 dai6 zo2 seon3.）", "translate": "他找到了更好的工作，昨天递了辞职信。"},
                {"sentence": "遞信之後仲要遞一個月通知期。（dai6 seon3 zi1 hau6 zung6 jiu3 dai6 jat1 go3 jyut6 tung1 zi1 kei4.）", "translate": "辞职之后还要有一个月的交接通知期。"}
            ]
        },
        {
            "word": "炒散",
            "jyutping": "caau2 saan2",
            "pos": "动",
            "meaning": "打零工，兼职，做兼职临时工",
            "sentences": [
                {"sentence": "放假去酒店炒散賺少少外快。（fong3 gaa3 heoi3 zau2 dim3 caau2 saan2 zaan6 siu2 siu2 ngoi6 faai3.）", "translate": "放假去酒店做兼职零工赚点外快。"},
                {"sentence": "炒散時間自由，好多學生做。（caau2 saan2 si4 gaan3 zi6 jau4, hou2 do1 hok6 saang1 zou6.）", "translate": "打零工时间自由，很多学生在做。"}
            ]
        },
        {
            "word": "開OT",
            "jyutping": "hoi1 ou1 ti1",
            "pos": "动",
            "meaning": "加班（OT即Overtime）",
            "sentences": [
                {"sentence": "趕項目進度，今晚全體開OT。（gon2 hong6 muk6 zeon3 dou6, gam1 maan5 cyun4 tai2 hoi1 ou1 ti1.）", "translate": "赶项目进度，今晚全体员工加班。"},
                {"sentence": "開OT開到半夜，好想瞓覺。（hoi1 ou1 ti1 hoi1 dou3 bun3 je6, hou2 soeng2 fan3 gaau3.）", "translate": "加班加到半夜，好想睡觉。"}
            ]
        },
        {
            "word": "走數",
            "jyutping": "zau2 sou3",
            "pos": "动",
            "meaning": "欠债潜逃，赖账，爽约食言",
            "sentences": [
                {"sentence": "做人最緊要講信用，千祈咪走數。（zou6 jan4 zeoi3 gan2 jiu3 gong2 seon3 jung6, cin1 kei4 mai5 zau2 sou3.）", "translate": "做人最讲究信用，千万别赖账爽约。"},
                {"sentence": "間公司欠供應商幾百萬之後走咗數。（gaan1 gung1 si1 him3 gung1 jing3 soeng1 gei2 baak3 maan6 zi1 hau6 zau2 zo2 sou3.）", "translate": "那家公司欠供应商几百万之后潜逃赖账了。"}
            ]
        },
        {
            "word": "孭鑊",
            "jyutping": "me1 wok6",
            "pos": "动",
            "meaning": "背锅，承担责任，为过失买单",
            "sentences": [
                {"sentence": "項目搞砸咗，老細要經理出嚟孭鑊。（hong6 muk6 gaau2 zaap3 zo2, lou5 sai3 jiu3 ging1 lei5 ceot1 lai4 me1 wok6.）", "translate": "项目搞砸了，老板要经理出来背锅顶雷。"},
                {"sentence": "係我嘅責任我就敢於孭鑊。（hai6 ngo5 ge3 zaak3 jam4 ngo5 zau6 gam2 jyu1 me1 wok6.）", "translate": "是我的责任我就敢于担当承担。"}
            ]
        },
        {
            "word": "卸膊",
            "jyutping": "se3 bok3",
            "pos": "动",
            "meaning": "推卸责任，甩锅，推委责任",
            "sentences": [
                {"sentence": "一有問題佢就即刻卸膊畀下屬。（jat1 jau5 man6 tai4 keoi5 zau6 zik1 hak1 se3 bok3 bei2 haa6 suk6.）", "translate": "一出问题他就立刻把责任甩给下属。"},
                {"sentence": "做領導唔好成日諗住卸膊。（zou6 ling5 dou6 m4 hou2 seng4 jat6 nam2 zyu6 se3 bok3.）", "translate": "当领导不要老想着推卸责任。"}
            ]
        },
        {
            "word": "手頭緊",
            "jyutping": "sau2 tau4 gan2",
            "pos": "形",
            "meaning": "手头紧，资金周转拮据",
            "sentences": [
                {"sentence": "最近交完租，手頭有少少緊。（zeoi3 gan6 gaau1 jyun4 zou1, sau2 tau4 jau5 siu2 siu2 gan2.）", "translate": "最近刚交完房租，手头有点紧巴巴的。"},
                {"sentence": "如果手頭緊就同我講聲。（jyu4 gwo2 sau2 tau4 gan2 zau6 tung4 ngo5 gong2 seng1.）", "translate": "如果手头紧就跟我说一声。"}
            ]
        }
    ]
}


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for data in [L6_DATA, L7_DATA, L8_DATA, L9_DATA, L10_DATA]:
        lvl = data["level"].lower()
        file_path = DATA_DIR / f"cantonese_{lvl}_{data['name'][:4]}.json"
        file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"已写入分卷: {file_path.name} (共 {len(data['words'])} 词)")


if __name__ == '__main__':
    main()
