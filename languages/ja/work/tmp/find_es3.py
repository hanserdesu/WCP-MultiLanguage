import io
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

s = io.open(r'D:\Japanese\work\decompiled\Assembly-CSharp.csproj', encoding='utf-8', errors='replace').read()

for m in sorted(set(re.findall(r'<Reference Include="([^"]+)"', s))):
    print(m)

print("---- hint paths with ES3/Save/Sqlite ----")
for m in sorted(set(re.findall(r'<HintPath>([^<]+)</HintPath>', s))):
    if re.search(r'ES3|Save|Sqlite|Mono', m, re.I):
        print(m)
