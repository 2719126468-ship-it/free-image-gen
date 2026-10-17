#!/usr/bin/env python3
"""FLUX.1-Kontext img2img via HF Inference Providers router.

Kontext is an image-to-image editing model: it keeps the reference composition
and repaints what the instruction asks. This is the right tool for
"turn the mermaid tail into two normal legs, keep everything else".

Unlike ZeroGPU Spaces, Inference Providers is a SEPARATE billing pool, so it
does not consume the daily ZeroGPU quota.

usage: kontext_edit.py <ref.jpg> <out.jpg> "edit instruction" [provider]
  provider: fal-ai (default) | replicate | wavespeed
env: HF_TOKEN (needs the "Make calls to Inference Providers" permission)
"""
import base64, json, os, sys, time, urllib.request, urllib.error

MODEL = 'black-forest-labs/FLUX.1-Kontext-dev'

def main():
    ref, out = sys.argv[1], sys.argv[2]
    instr = sys.argv[3]
    provider = sys.argv[4] if len(sys.argv) > 4 else 'fal-ai'
    tok = os.environ.get('HF_TOKEN')
    if not tok:
        print('[!] HF_TOKEN unset'); sys.exit(1)

    raw = open(os.path.expanduser(ref), 'rb').read()
    b64 = base64.b64encode(raw).decode()
    print(f'[.] ref {len(raw)}B  provider={provider}')
    print(f'[.] instruction: {instr[:120]}')

    url = f'https://router.huggingface.co/{provider}/models/{MODEL}'
    body = {'inputs': instr, 'image': b64,
            'parameters': {'guidance_scale': 3.5, 'num_inference_steps': 28}}
    r = urllib.request.Request(url, data=json.dumps(body).encode(),
        headers={'Authorization': 'Bearer ' + tok,
                 'Content-Type': 'application/json',
                 'User-Agent': 'lcs/1.0'})
    try:
        resp = urllib.request.urlopen(r, timeout=300)
    except urllib.error.HTTPError as e:
        txt = e.read().decode('utf8', 'replace')
        print(f'[!] HTTP {e.code}: {txt[:400]}')
        low = txt.lower()
        if 'permission' in low or 'sufficient' in low:
            print('[!] token 缺少 Inference Providers 权限：'
                  'huggingface.co/settings/tokens 建 fine-grained token 并勾选该权限')
        elif 'credit' in low or 'billing' in low or 'quota' in low or 'payment' in low:
            print('[!] 权限已通过，但账号无 Inference Providers 额度（需绑卡或 PRO）')
        sys.exit(1)
    except Exception as e:
        print(f'[!] request failed: {str(e)[:200]}'); sys.exit(1)

    data = resp.read()
    ct = resp.headers.get('content-type', '')
    print(f'[.] HTTP {resp.status}  {len(data)}B  {ct}')
    o = os.path.expanduser(out)
    os.makedirs(os.path.dirname(o) or '.', exist_ok=True)
    if 'image' in ct or data[:3] == b'\xff\xd8\xff' or data[:8] == b'\x89PNG\r\n\x1a\n':
        open(o, 'wb').write(data)
    else:
        # Some providers return JSON with a URL or base64 payload.
        try:
            j = json.loads(data)
        except Exception:
            print('[!] unexpected payload:', data[:300]); sys.exit(2)
        u = (j.get('image') or j.get('url') or
             (j.get('images') or [{}])[0].get('url') if j.get('images') else None)
        b = j.get('b64_json') or (j.get('images') or [{}])[0].get('b64') if j.get('images') else j.get('b64_json')
        if u:
            print('[.] fetching', u[:90])
            data = urllib.request.urlopen(urllib.request.Request(
                u, headers={'User-Agent': 'lcs/1.0'}), timeout=180).read()
            open(o, 'wb').write(data)
        elif b:
            open(o, 'wb').write(base64.b64decode(b))
        else:
            print('[!] no image in JSON:', json.dumps(j)[:400]); sys.exit(2)
    print(f'[+] saved {o} ({os.path.getsize(o)}B)')

main()
