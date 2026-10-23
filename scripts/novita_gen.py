#!/usr/bin/env python3
"""Novita AI 文生图（异步接口）—— 标称 $10/90 天免费额度、SDXL、60 RPM。

实测（2026-10-23，无 key）：
  POST https://api.novita.ai/v3/async/txt2img → HTTP 400
  原文 {"code":400,"reason":"MISSING_API_KEY","message":"missing api-key","metadata":{}}
  → 主机存活，接口即 async/txt2img + task-result 轮询；key 放 ~/.dsh/.novita-key。

用法:
  novita_gen.py <out.png> "<prompt>" [--model sd_xl_base_1.0.safetensors] [--w 1024] [--h 1024]
                [--steps 25] [--seed N] [--timeout 180]
  novita_gen.py --probe
"""
import argparse, json, os, sys, time, urllib.error, urllib.request

API = 'https://api.novita.ai/v3/async'
KEY_FILE = os.path.expanduser('~/.dsh/.novita-key')


def key():
    k = os.environ.get('NOVITA_API_KEY')
    if k:
        return k.strip()
    if os.path.isfile(KEY_FILE):
        for line in open(KEY_FILE):
            line = line.strip()
            if line.startswith('NOVITA_API_KEY='):
                return line.split('=', 1)[1].strip()
    return ''


def _req(url, body, k, timeout=120):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data,
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


def body(prompt, model, w, h, steps, seed):
    return {'extra': {'response_image_type': 'png'},
            'request': {'prompt': prompt, 'model_name': model, 'image_num': 1,
                        'steps': steps, 'width': w, 'height': h,
                        'guidance_scale': 7.5, 'seed': seed}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out', nargs='?'); ap.add_argument('prompt', nargs='?')
    ap.add_argument('--model', default='sd_xl_base_1.0.safetensors')
    ap.add_argument('--w', type=int, default=1024); ap.add_argument('--h', type=int, default=1024)
    ap.add_argument('--steps', type=int, default=25); ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--timeout', type=int, default=180)
    ap.add_argument('--probe', action='store_true')
    a = ap.parse_args()
    k = key()

    if a.probe:
        code, b = _req(API + '/txt2img', body('a red apple', a.model, 512, 512, 4, 0), k)
        print('[probe] txt2img HTTP=%s %dB %s' % (code, len(b), b[:200].decode('utf-8', 'replace')))
        print('[i] key: %s' % ('有' if k else '缺（放 ~/.dsh/.novita-key）'))
        return 0 if k else 2

    if not (a.out and a.prompt):
        ap.error('需要 <out> 与 <prompt>（或 --probe）')
    if not k:
        print('[!] 缺 key：~/.dsh/.novita-key 里写 NOVITA_API_KEY=...'); return 2

    print('[.] Novita %s %dx%d steps=%d' % (a.model, a.w, a.h, a.steps))
    t0 = time.time()
    code, b = _req(API + '/txt2img', body(a.prompt, a.model, a.w, a.h, a.steps, a.seed), k)
    if code != 200:
        print('[!] submit HTTP %s: %s' % (code, b[:300].decode('utf-8', 'replace'))); return 1
    tid = json.loads(b.decode()).get('task_id')
    if not tid:
        print('[!] no task_id: %s' % b[:200]); return 1
    print('[.] task_id=%s' % tid)
    while time.time() - t0 < a.timeout:
        time.sleep(4)
        code, b = _req('%s/task-result?task_id=%s' % (API, tid), None, k)
        if code != 200:
            print('[!] poll HTTP %s: %s' % (code, b[:200].decode('utf-8', 'replace'))); return 1
        j = json.loads(b.decode('utf-8', 'replace'))
        st = (j.get('task') or {}).get('status')
        print('[.] status=%s %.0fs' % (st, time.time() - t0))
        if st in ('succeeded', 'TASK_STATUS_SUCCEED'):
            imgs = j.get('images') or []
            if not imgs:
                print('[!] succeeded but no images: %s' % json.dumps(j)[:300]); return 1
            url = imgs[0].get('image_url')
            with urllib.request.urlopen(url, timeout=180) as r:
                blob = r.read()
            os.makedirs(os.path.dirname(os.path.abspath(a.out)) or '.', exist_ok=True)
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
        if st in ('failed', 'TASK_STATUS_FAILED'):
            print('[!] task failed: %s' % json.dumps(j)[:300]); return 1
    print('[!] timeout after %ss' % a.timeout); return 1


if __name__ == '__main__':
    sys.exit(main())
