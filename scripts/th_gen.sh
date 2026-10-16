#!/data/data/com.termux/files/usr/bin/bash
# TensorHub Art no-login image generator.
#
# usage: th_gen.sh "prompt" [outdir] [seed] [template_id] [negative]
#
# Anonymous: no account, no API key, no request signature. The site's own
# frontend ships a no-login task path; only the site's packageId header
# (3023 for tensorhub.art) is needed.
set -u

PROMPT="${1:-}"
OUTDIR="${2:-/sdcard/Download}"
SEED="${3:-$RANDOM}"
TID="${4:-1040803651355979666}"   # ANIME YOUR IDEA: ckpt + prompt + seed + lora + save
NEG="${5:-}"

[ -z "$PROMPT" ] && {
  echo "usage: th_gen.sh <prompt> [outdir] [seed] [template_id] [negative]"
  exit 2
}

mkdir -p "$OUTDIR"

# curl_cffi impersonates Chrome's TLS fingerprint; the site sits behind
# Cloudflare and rejects the default one (cloudscraper and chrome124 both fail).
exec python3 -u - "$PROMPT" "$OUTDIR" "$SEED" "$TID" "$NEG" <<'PY'
import sys, json, time, os, subprocess
from curl_cffi import requests as cr

prompt, outdir, seed, tid, neg = sys.argv[1:6]
API = 'https://api.tensorhub.art'
H = {'Content-Type': 'application/json',
     'Origin': 'https://tensorhub.art',
     'Referer': 'https://tensorhub.art/',
     'Authorization': '',
     'X-Request-Package-Id': '3023',
     'X-Request-Lang': 'en-US'}
UA = ('Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36')

def req(method, path, body=None):
    r = cr.request(method, API + path, headers=H, data=body,
                   impersonate='chrome120', timeout=180)
    return r.json()

print(f'[*] prompt : {prompt[:90]}')
print(f'[*] tmpl   : {tid}')

d = req('GET', f'/workflow/v1/workflow/template/detail?id={tid}')
nodes = d['data']['workflowTemplate']['modifiedFields']['tensorNodes']

attrs = []
for n in nodes:
    name = n['nodeName']
    # First PromptText is the positive prompt; a second one (if the template
    # has one) is the negative prompt.
    if name == 'TensorArt_PromptText':
        cur = str(n.get('fieldValue') or '')
        if not cur.strip():
            n['fieldValue'] = prompt
        elif neg and 'negative' in n['fieldName'].lower():
            n['fieldValue'] = neg
    if name == 'TensorArt_Seed':
        n['fieldValue'] = str(seed)
    ist = n.get('inputString')
    if isinstance(ist, str):
        try:
            w = json.loads(ist)
            for item in (w if isinstance(w, list) else []):
                if item.get('name') == n['fieldName']:
                    item['value'] = n['fieldValue']
            n['inputString'] = json.dumps(w)
        except Exception:
            pass
    n.pop('extraNodeMeta', None)
    attrs.append(n)

body = json.dumps({'workspaceType': 'WORKFLOW_TEMPLATE',
                   'workflowTemplateRequest': {
                       'workflowTemplateId': tid,
                       'field': {'fieldAttrs': attrs}}})

j = req('POST', '/works/v1/no_login/task/create', body)
if j.get('code') != '0':
    print('[!] create failed:', str(j.get('message'))[:400])
    sys.exit(1)
task = j['data']['task']['taskId']
print(f'[*] task    : {task}')

deadline = time.time() + 600
last = ''
while time.time() < deadline:
    time.sleep(10)
    r = req('POST', '/works/v1/no_login/task/mget', json.dumps({'ids': [task]}))
    t = (r.get('data') or {}).get('tasks', {}).get(task) or {}
    st = t.get('status', '')
    items = t.get('items') or []
    imgs = [i['url'] for i in items if str(i.get('mimeType', '')).startswith('image/')]
    if imgs:
        for idx, u in enumerate(imgs, 1):
            out = os.path.join(outdir, f'th_{tid}_{seed}_{idx}.png')
            subprocess.run(['curl', '-sS', '-m', '180', '-H', f'User-Agent: {UA}',
                            '-o', out, u], check=False)
            if os.path.exists(out) and os.path.getsize(out) > 0:
                print(f'[+] {out} ({os.path.getsize(out)} bytes)')
    if st != last:
        print(f'[.] {st}')
        last = st
    if st in ('FINISH', 'EXCEPTION'):
        sys.exit(0 if imgs else 1)
print('[!] timed out')
sys.exit(1)
PY
