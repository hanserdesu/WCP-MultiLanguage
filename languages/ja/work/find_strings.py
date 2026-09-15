import re
path = 'E:/SteamLibrary/steamapps/common/WCP-WordGirlgriend/wcp_Data/Managed/Assembly-CSharp.dll'
data = open(path,'rb').read()
print('size:', len(data))
# search for interesting strings
for pat in [b'SelfBookList', b'wordDictionary', b'MyBook', b'CopyOriginal']:
    idxs = [m.start() for m in re.finditer(re.escape(pat), data)]
    print(pat, len(idxs), idxs[:10])
