import json, io, sys

p = r'C:\Users\hanserdesu\AppData\LocalLow\WCP\wcp\SaveFile.es3'
d = json.load(io.open(p, encoding='utf-8'))

keys = ['S8ThisMode_Para','S8Progress_Para','S8needToLearnWordList_Para',
        'S8TestWordList_LearnedTest_left','allTestWordsS10_Para','S8TestWordList_Para',
        'checkWordInDictionary','S9Option1_Para','S9Option2_Para','S9Option3_Para',
        'S9Option4_Para','S8HaveLearnedWordList_Para','ChosenBook_Para','ChosenBook_List',
        'S8LookBack_Para','rightOption_S9','S8TestWordList_LearnedTest_Finished']
for k in keys:
    v = d.get(k)
    if isinstance(v, dict) and 'value' in v:
        v = v['value']
    if isinstance(v, list) and len(v) > 20:
        v = v[:20] + ['...(%d)' % len(v)]
    print(k, '=', v)
