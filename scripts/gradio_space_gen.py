#!/usr/bin/env python3
"""Call a non-ZeroGPU HuggingFace Gradio Space's API and save the image.

These Spaces run on the owner's hardware (cpu-basic / paid GPU), so they do NOT
consume the caller's ZeroGPU quota. Verified 2026-10-17: with ZeroGPU quota at
0s, a zero-a10g Space returns `event: error / data: null` while a cpu-basic
Space still generates.

usage: gradio_space_gen.py <space_id> <endpoint> <out.png> <param1> [param2 ...]
  Params are auto-typed: int if integral, float if decimal, "true"/"false" -> bool,
  otherwise string. Pass "" for an unused positional slot.
"""
import json, os, re, sys, time, base64, urllib.request, urllib.error

def subdomain(sid):
    return re.sub(r'[^a-z0-9-]', '-', sid.lower().replace('/', '-'))

def coerce(v):
    s = str(v)
    if s.lower() in ('true', 'false'): return s.lower() == 'true'
    if re.fullmatch(r'-?\d+', s): return int(s)
    if re.fullmatch(r'-?\d+\.\d+', s): return float(s)
    return s

def call(url, payload, headers, method='POST', timeout=90):
    data = json.dumps(payload).encode() if payload is not None else None
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    return urllib.request.urlopen(r, timeout=timeout)

def main():
    sid, endpoint, out = sys.argv[1], sys.argv[2], sys.argv[3]
    params = [coerce(p) for p in sys.argv[4:]]
    base = f'https://{subdomain(sid)}.hf.space'
    H = {'Content-Type': 'application/json', 'User-Agent': 'lcs/1.0'}
    tok = os.environ.get('HF_TOKEN')
    if tok:  # harmless on non-zero spaces, helps if the Space is gated
        H['X-HF-Authorization'] = 'Bearer ' + tok
    path = endpoint if endpoint.startswith('/') else '/' + endpoint

    print(f'[.] {sid}  endpoint={path}  params={len(params)}')
    try:
        resp = call(f'{base}/gradio_api/call{path}', {'data': params}, H)
        eid = json.load(resp)['event_id']
    except urllib.error.HTTPError as e:
        print(f'[!] submit HTTP {e.code}: {e.read().decode()[:220]}'); sys.exit(1)
    except Exception as e:
        print(f'[!] submit failed: {str(e)[:180]}'); sys.exit(1)
    print(f'[.] event_id={eid}')

    # SSE poll. A slow CPU Space can take many minutes; keep polling.
    deadline = time.time() + float(os.environ.get('GRADIO_WAIT', '900'))
    final = None
    while time.time() < deadline:
        time.sleep(6)
        try:
            raw = call(f'{base}/gradio_api/call{path}/{eid}', None, H, 'GET').read().decode()
        except Exception as e:
            print(f'  poll err {str(e)[:70]}'); continue
        ev = [l[7:] for l in raw.splitlines() if l.startswith('event:')]
        if 'error' in ev:
            print('[!] Space returned error (worker crash or hidden quota)')
            sys.exit(2)
        if 'complete' in ev:
            for line in raw.splitlines():
                if line.startswith('data:'):
                    try: final = json.loads(line[5:].strip())
                    except Exception: pass
            break
        el = int(time.time() - (deadline - float(os.environ.get('GRADIO_WAIT', '900'))))
        print(f'  ...{el}s')
    if final is None:
        print('[!] timed out'); sys.exit(3)

    # Extract an image from the returned payload.
    blob = json.dumps(final)
    m = re.search(r'"url"\s*:\s*"(https?://[^"]+)"', blob)
    b64 = re.search(r'"b64"\s*:\s*"([A-Za-z0-9+/=]{200,})"', blob)
    if m:
        u = m.group(1).replace('\\/', '/')
        print(f'[.] downloading {u[:90]}')
        open(out, 'wb').write(urllib.request.urlopen(
            urllib.request.Request(u, headers={'User-Agent': 'lcs/1.0'}), timeout=180).read())
    elif b64:
        open(out, 'wb').write(base64.b64decode(b64.group(1)))
    else:
        print('[!] no image in response:'); print(blob[:600]); sys.exit(4)
    print(f'[+] saved {out} ({os.path.getsize(out)} bytes)')

main()
