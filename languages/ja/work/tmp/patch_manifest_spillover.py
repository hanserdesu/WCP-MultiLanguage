"""Patch release-manifest: sentences parts 023-032 live in the words repo (quota spill-over).
Then verify every URL in the manifest with HEAD (both gitee and github routes)."""
import json, sys, urllib.request, concurrent.futures as cf

mpath = 'wcp_wordbooks/output/release/release-manifest.json'
d = json.load(open(mpath, encoding='utf-8'))
WORDS_TPL = 'https://gitee.com/cat-stripe/wcp-jp-audio-words/releases/download/wcp-jp-resources-v1.1.0/{name}'
patched = 0
for a in d['assets']:
    if a['kind'] != 'sentence_audio':
        continue
    for p in a.get('parts', []):
        n = p['name'].rsplit('.', 1)[1]
        if n.isdigit() and int(n) >= 23:
            p['url_template'] = WORDS_TPL
            patched += 1
print('patched part templates:', patched)
with open(mpath, 'w', encoding='utf-8', newline='\n') as f:
    f.write(json.dumps(d, ensure_ascii=False, indent=2) + '\n')
# keep the installer_pkg copy in sync
import shutil
shutil.copy2(mpath, 'wcp_wordbooks/output/installer_pkg/WCP日语词书安装包/support/release-manifest.json')

# collect every URL
urls = []
for a in d['assets']:
    for p in a.get('parts', []):
        urls.append(p['url_template'].replace('{name}', p['name']))
    for r in d['download_routes']:
        if r['id'] == 'github':
            urls.append(r['url_template'].replace('{name}', a['name']))

def check(u):
    try:
        req = urllib.request.Request(u, method='HEAD', headers={'User-Agent': 'WCP-Check/1.0'})
        with urllib.request.urlopen(req, timeout=40) as r:
            return (r.status, u)
    except Exception as e:
        return (getattr(e, 'code', type(e).__name__), u)

with cf.ThreadPoolExecutor(8) as ex:
    results = list(ex.map(check, urls))
ok = [r for r in results if r[0] == 200]
bad = [r for r in results if r[0] != 200]
print(f'TOTAL {len(results)} | OK {len(ok)} | BAD {len(bad)}')
for s, u in bad[:10]:
    print(' BAD', s, u.rsplit('/', 2)[-2] + '/' + u.rsplit('/', 1)[-1])
sys.exit(1 if bad else 0)
