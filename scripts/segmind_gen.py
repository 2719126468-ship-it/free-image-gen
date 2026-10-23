#!/usr/bin/env python3
"""Segmind 文生图 —— 标称 100 次/天免费。实测鉴权与错误原文（2026-10-23，无 key）：
  POST https://api.segmind.com/v1/sdxl1.0-txt2img → HTTP 401
  原文 {"error": "Missing Authorization or x-api-key in header"}
  → 头名 x-api-key（也接受 Authorization）。key 放 ~/.dsh/.segmind-key。

用法: segmind_gen.py <out.png> "<prompt>" [--model sdxl1.0-txt2img] [--w 1024] [--h 1024]
                     [--steps 25] [--seed N] [--probe]
"""
import argparse, json, os, sys, time, urllib.error, urllib.request

BASE = 'https://api.segmind.com/v1'
KEY_FILE = os.path.expanduser('~/.dsh/.segmind-key')


def key():
    k = os.environ.get('SEGMIND_API_KEY')
    if k:
        return k.strip()
    if os.path.isfile(KEY_FILE):
        for line in open(KEY_FILE):
            line = line.strip()
            if line.startswith('SEGMIND_API_KEY='):
                return line.split('=', 1)[1].strip()
    return ''


def _post(model, body, k, timeout=300):
    req = urllib.request.Request('%s/%s' % (BASE, model), data=json.dumps(body).encode(),
                                 headers={'User-Agent': 'Mozilla/5.0 (compatible; free-image-gen/1.0)',
                                 'Content-Type': 'application/json',
                                          **({'x-api-key': k} if k else {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(), r.headers.get('content-type', '')
    except urllib.error.HTTPError as e:
        return e.code, e.read(), e.headers.get('content-type', '')
    except Exception as e:
        return 0, ('%s: %s' % (type(e).__name__, e)).encode(), ''


def body(prompt, w, h, steps, seed):
    return {'prompt': prompt, 'negative_prompt': 'worst quality, blurry',
            'samples': 1, 'scheduler': 'DPMSolverMultistep', 'num_inference_steps': steps,
            'img_width': w, 'img_height': h, 'seed': seed, 'guidance_scale': 7.5}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out', nargs='?'); ap.add_argument('prompt', nargs='?')
    ap.add_argument('--model', default='sdxl1.0-txt2img')
    ap.add_argument('--w', type=int, default=1024); ap.add_argument('--h', type=int, default=1024)
    ap.add_argument('--steps', type=int, default=25); ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--probe', action='store_true')
    a = ap.parse_args()
    k = key()
    if a.probe:
        code, b, ct = _post(a.model, body('a red apple', 512, 512, 4, 0), k)
        print('[probe] %s HTTP=%s %dB ct=%s %s' % (a.model, code, len(b), ct,
              b[:200].decode('utf-8', 'replace')))
        print('[i] key: %s' % ('有' if k else '缺（放 ~/.dsh/.segmind-key）'))
        return 0 if k else 2
    if not (a.out and a.prompt):
        ap.error('需要 <out> 与 <prompt>（或 --probe）')
    if not k:
        print('[!] 缺 key：~/.dsh/.segmind-key 里写 SEGMIND_API_KEY=...'); return 2
    print('[.] Segmind %s %dx%d' % (a.model, a.w, a.h))
    t0 = time.time()
    code, b, ct = _post(a.model, body(a.prompt, a.w, a.h, a.steps, a.seed), k)
    if code != 200:
        print('[!] HTTP %s: %s' % (code, b[:300].decode('utf-8', 'replace'))); return 1
    open(a.out, 'wb').write(b)
    print('[+] saved %s (%dB) in %.1fs' % (a.out, len(b), time.time() - t0))
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
