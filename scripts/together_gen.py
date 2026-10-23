#!/usr/bin/env python3
"""Together AI 生图 —— 关键点是 FLUX.1-schnell-Free（标称免费、3 RPM、1 张/次）。

实测（2026-10-23，无 key）：
  POST https://api.together.xyz/v1/images/generations → HTTP 401
  原文 Missing API key. You need to provide your API key in an Authorization header using Bearer auth
  → key 放 ~/.dsh/.together-key。注意 Together 的免费图像模型常改 ID，
    404/400 时先用 --list 看当前账号可用模型。

用法: together_gen.py <out.png> "<prompt>" [--model black-forest-labs/FLUX.1-schnell-Free]
                      [--w 1024] [--h 1024] [--steps 4] [--seed N] [--list] [--probe]
"""
import argparse, base64, json, os, sys, time, urllib.error, urllib.request

BASE = 'https://api.together.xyz/v1'
KEY_FILE = os.path.expanduser('~/.dsh/.together-key')


def key():
    k = os.environ.get('TOGETHER_API_KEY')
    if k:
        return k.strip()
    if os.path.isfile(KEY_FILE):
        for line in open(KEY_FILE):
            line = line.strip()
            if line.startswith('TOGETHER_API_KEY='):
                return line.split('=', 1)[1].strip()
    return ''


def _req(path, body, k, timeout=300):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data,
                                 headers={'User-Agent': 'Mozilla/5.0 (compatible; free-image-gen/1.0)',
                                 'Content-Type': 'application/json',
                                          **({'Authorization': 'Bearer ' + k} if k else {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return 0, ('%s: %s' % (type(e).__name__, e)).encode()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out', nargs='?'); ap.add_argument('prompt', nargs='?')
    ap.add_argument('--model', default='black-forest-labs/FLUX.1-schnell-Free')
    ap.add_argument('--w', type=int, default=1024); ap.add_argument('--h', type=int, default=1024)
    ap.add_argument('--steps', type=int, default=4); ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--list', action='store_true'); ap.add_argument('--probe', action='store_true')
    a = ap.parse_args()
    k = key()

    if a.list:
        code, b = _req('/models', None, k)
        print('HTTP=%s' % code)
        if code == 200:
            ids = [m.get('id') for m in json.loads(b).get('data', [])]
            print('\n'.join(i for i in ids if any(x in i.lower() for x in ('flux', 'sd', 'image'))))
        else:
            print(b[:300].decode('utf-8', 'replace'))
        return 0 if code == 200 else 1

    if a.probe:
        body = {'model': a.model, 'prompt': 'a red apple', 'n': 1, 'steps': 4,
                'width': 512, 'height': 512}
        code, b = _req('/images/generations', body, k)
        print('[probe] HTTP=%s %dB %s' % (code, len(b), b[:240].decode('utf-8', 'replace')))
        print('[i] key: %s' % ('有' if k else '缺（放 ~/.dsh/.together-key）'))
        return 0 if k else 2

    if not (a.out and a.prompt):
        ap.error('需要 <out> 与 <prompt>（或 --probe / --list）')
    if not k:
        print('[!] 缺 key：~/.dsh/.together-key 里写 TOGETHER_API_KEY=...'); return 2
    body = {'model': a.model, 'prompt': a.prompt, 'n': 1, 'steps': a.steps,
            'width': a.w, 'height': a.h, 'response_format': 'b64_json', 'seed': a.seed}
    print('[.] Together %s %dx%d steps=%d' % (a.model, a.w, a.h, a.steps))
    t0 = time.time()
    code, b = _req('/images/generations', body, k)
    if code != 200:
        print('[!] HTTP %s: %s' % (code, b[:400].decode('utf-8', 'replace'))); return 1
    j = json.loads(b.decode('utf-8', 'replace'))
    it = (j.get('data') or [{}])[0]
    if it.get('b64_json'):
        blob = base64.b64decode(it['b64_json'])
    elif it.get('url'):
        with urllib.request.urlopen(it['url'], timeout=180) as r:
            blob = r.read()
    else:
        print('[!] unexpected: %s' % json.dumps(j)[:300]); return 1
    open(a.out, 'wb').write(blob)
    print('[+] saved %s (%dB) in %.1fs' % (a.out, len(blob), time.time() - t0))
    try:
        from PIL import Image, ImageStat
        import hashlib
        im = Image.open(a.out); im.load()
        print('[+] %s %dB md5=%s luma=%.1f' % (im.size, os.path.getsize(a.out),
              hashlib.md5(open(a.out, 'rb').read()).hexdigest()[:16],
              ImageStat.Stat(im.convert('L')).mean[0]))
    except Exception as e:
        print('[i] verify skipped: %s' % e)
    return 0


if __name__ == '__main__':
    sys.exit(main())
