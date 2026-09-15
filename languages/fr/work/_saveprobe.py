# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')
s = open('C:/Users/hanserdesu/AppData/LocalLow/WCP/wcp/SaveFile.es3',
         encoding='utf-8', errors='replace').read()
for k in ['SelfBookName1', 'SelfBookName2', 'ChosenBook_Para',
          'SelfBookMeaningConnectIf', 'OutDatabaseConnectIf',
          'SelfBookMeaningDictionary']:
    i = s.find('"' + k + '"')
    if i < 0:
        print(k, '-> MISSING')
        continue
    print(k, '->', s[i:i+170].replace(chr(10), ' '))
