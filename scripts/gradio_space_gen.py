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

def upload(base, filepath, tok):
    """Multipart upload a local file to a Gradio Space; returns the remote path.

    Gradio file params must be passed as {'path': ..., 'url': ..., 'meta':
    {'_type': 'gradio.FileData'}} in the call payload, not as a raw string.
    """
    import mimetypes, uuid
    boundary = '----lcs' + uuid.uuid4().hex
    ctype = mimetypes.guess_type(filepath)[0] or 'application/octet-stream'
    name = os.path.basename(filepath)
    head = (f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="{name}"\r\n'
            f'Content-Type: {ctype}\r\n\r\n').encode()
    body = head + open(filepath, 'rb').read() + f'\r\n--{boundary}--\r\n'.encode()
    H = {'Content-Type': f'multipart/form-data; boundary={boundary}', 'User-Agent': 'lcs/1.0'}
    if tok: H['X-HF-Authorization'] = 'Bearer ' + tok
    r = urllib.request.Request(base + '/gradio_api/upload', data=body, headers=H)
    resp = json.load(urllib.request.urlopen(r, timeout=180))
    remote = resp[0] if isinstance(resp, list) else resp.get('path', '')
    return remote

def file_ref(remote):
    return {'path': remote, 'url': None, 'size': None, 'orig_name': os.path.basename(remote),
            'meta': {'_type': 'gradio.FileData'}}

def main():
    sid, endpoint, out = sys.argv[1], sys.argv[2], sys.argv[3]
    params = sys.argv[4:]
    base = f'https://{subdomain(sid)}.hf.space'
    H = {'Content-Type': 'application/json', 'User-Agent': 'lcs/1.0'}
    tok = os.environ.get('HF_TOKEN')
    if tok:  # harmless on non-zero spaces, helps if the Space is gated
        H['X-HF-Authorization'] = 'Bearer ' + tok
    path = endpoint if endpoint.startswith('/') else '/' + endpoint

    # A param of the form file:/local/path.jpg is uploaded to the Space and sent
    # as a Gradio FileData object (required by img2img endpoints).
    coerced = []
    for p in params:
        if p.startswith('file:'):
            fp = os.path.expanduser(p[5:])
            remote = upload(base, fp, tok)
            print(f'[.] uploaded {os.path.basename(fp)} -> {remote}')
            coerced.append(file_ref(remote))
        else:
            coerced.append(coerce(p))
    params = coerced

    print(f'[.] {sid}  endpoint={path}  params={len(params)}')
    try:
        resp = call(f'{base}/gradio_api/call{path}', {'data': params}, H)
        eid = json.load(resp)['event_id']
    except urllib.error.HTTPError as e:
        print(f'[!] submit HTTP {e.code}: {e.read().decode()[:220]}'); sys.exit(1)
    except Exception as e:
        print(f'[!] submit failed: {str(e)[:180]}'); sys.exit(1)
    print(f'[.] event_id={eid}')

    # SSE poll with INCREMENTAL line reads. Gradio holds the stream open and emits
    # `event: heartbeat` while the job runs, so a blocking .read() never returns
    # until the job ends and defeats socket timeouts. Read line by line instead.
    wait = float(os.environ.get('GRADIO_WAIT', '900'))
    t0 = time.time()
    try:
        stream = call(f'{base}/gradio_api/call{path}/{eid}', None, H, 'GET', timeout=120)
    except Exception as e:
        print(f'[!] stream open failed: {str(e)[:150]}'); sys.exit(1)
    final = None
    ev = None
    while time.time() - t0 < wait:
        try:
            line = stream.readline()
        except Exception as e:
            print(f'  stream err {str(e)[:70]}'); break
        if not line:
            print('[!] stream closed before completion'); break
        s = (line.decode('utf8', 'replace') if isinstance(line, bytes) else line).strip()
        if s.startswith('event:'):
            ev = s[6:].strip()
            if ev == 'error':
                print('[!] Space returned error. On cpu-basic this usually means the '
                      'model is too heavy for 2 vCPU (needs a distilled model + few steps).')
                sys.exit(2)
            if ev not in ('complete', 'data'):
                print(f'  [{ev}] {int(time.time() - t0)}s')
        elif s.startswith('data:') and ev == 'complete':
            try:
                final = json.loads(s[5:].strip())
            except Exception:
                pass
            break
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
    # Gradio often returns webp regardless of the requested name; fix the extension
    # from magic bytes so downstream viewers/ffmpeg don't get confused.
    head = open(out, 'rb').read(16)
    real = None
    if head[:4] == b'RIFF' and head[8:12] == b'WEBP': real = '.webp'
    elif head[:8] == b'\x89PNG\r\n\x1a\n': real = '.png'
    elif head[:3] == b'\xff\xd8\xff': real = '.jpg'
    if real and not out.lower().endswith(real):
        fixed = os.path.splitext(out)[0] + real
        os.replace(out, fixed); out = fixed
    print(f'[+] saved {out} ({os.path.getsize(out)} bytes)')

main()
