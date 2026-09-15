import re, sys, codecs

sys.stdout.reconfigure(encoding='utf-8')

DLL = r'E:\SteamLibrary\steamapps\common\WCP-WordGirlgriend\wcp_Data\Managed\Assembly-CSharp.dll'
data = open(DLL, 'rb').read()

strs = re.findall(rb'[\x20-\x7e]{4,}', data)
strs = [s.decode('ascii', 'ignore') for s in strs]

keys = [s for s in strs if re.search(r'SelfBook|MyBook|wordDict|\.es3|ES3File', s, re.I)]
print("KEY STRINGS:")
for k in dict.fromkeys(keys):
    print("  ", k)

print(f"\nTotal strings: {len(strs)}")
