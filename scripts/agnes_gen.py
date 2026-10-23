#!/usr/bin/env python3
"""Agnes AI 生图（free/non-billing 平台）—— OpenAI 兼容 images/generations，支持 img2img。

端点（实测定位，非文档抄来）：
  base  https://apihub.agnes-ai.com/v1        ← 从 ComfyUI-Agnes-AI 插件源码 API_BASE 取到
  POST  {base}/images/generations             Bearer key
  无 key 实测：HTTP 401 {"error":{"message":"Token not provided (request id: ...)",
               "type":"AgnesAI_error"}}
  POST  https://apihub.agnes-ai.com/v1/models → 404 {"error":{"message":"Invalid URL
               (POST /v1/models)","type":"invalid_request_error"}} ← 说明是 openai 风格但没有 /models

免费性质：官方/插件 README 原文「Free | No token billing, no credit system — get a key and use it」
+ 「Get a free API key: platform.agnes-ai.com」。**本脚本不代注册**；key 放
~/.dsh/.agnes-key（AGNES_API_KEY=...）。

请求体（对齐插件 generate_image()）：
  {"model":"agnes-image-2.5-flash","prompt":...,"size":"1024x1024", "seed":n,
   "extra_body":{"image":[b64,...],"response_format":"b64_json"}}   # img2img/融合时才带 extra_body

用法:
  agnes_gen.py <out.png> "<prompt>" [--size 1024x1024] [--model M] [--seed N] [--ref a.jpg,b.jpg]
  agnes_gen.py --probe
"""
import argparse, base64, json, os, sys, time, urllib.error, urllib.request

BASE = 'https://apihub.agnes-ai.com/v1'
KEY_FILE = os.path.expanduser('~/.dsh/.agnes-key')
DEFAULT_MODEL = 'agnes-image-2.5-flash'


def key():
    k = os.environ.get('AGNES_API_KEY')
    if k:
        return k.strip()
    if os.path.isfile(KEY_FILE):
        for line in open(KEY_FILE):
            line = line.strip()
            if line.startswith('AGNES_API_KEY='):
                return line.split('=', 1)[1].strip()
    return ''


def _post(path, body, k, timeout=300):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(),
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


def _b64_file(p):
    with open(p, 'rb') as f:
        return base64.b64encode(f.read()).decode()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out', nargs='?')
    ap.add_argument('prompt', nargs='?')
    ap.add_argument('--size', default='1024x1024')
    ap.add_argument('--model', default=DEFAULT_MODEL)
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--ref', default='', help='img2img 参考图，逗号分隔，最多 4 张')
    ap.add_argument('--probe', action='store_true')
    a = ap.parse_args()

    k = key()
    if a.probe:
        body = {'model': a.model, 'prompt': 'a red apple', 'size': '1024x1024'}
        t0 = time.time()
        code, b = _post('/images/generations', body, k)
        print('[probe] HTTP=%s %dB %.1fs %s' % (code, len(b), time.time() - t0,
              b[:200].decode('utf-8', 'replace')))
        print('[i] key: %s' % ('有' if k else '缺（放 ~/.dsh/.agnes-key，platform.agnes-ai.com 免费领）'))
        return 0 if k else 2

    if not (a.out and a.prompt):
        ap.error('需要 <out> 与 <prompt>（或 --probe）')
    if not k:
        print('[!] 缺 key：~/.dsh/.agnes-key 里写 AGNES_API_KEY=...（platform.agnes-ai.com 免费）')
        return 2

    body = {'model': a.model, 'prompt': a.prompt, 'size': a.size}
    if a.seed:
        body['seed'] = a.seed % 1000
    refs = [r for r in a.ref.split(',') if r.strip()]
    if refs:
        body['extra_body'] = {'image': [_b64_file(r.strip()) for r in refs[:4]],
                              'response_format': 'b64_json'}
    print('[.] Agnes %s %s refs=%d' % (a.model, a.size, len(refs)))
    t0 = time.time()
    code, b = _post('/images/generations', body, k)
    if code != 200:
        print('[!] HTTP %s: %s' % (code, b[:400].decode('utf-8', 'replace')))
        return 1
    j = json.loads(b.decode('utf-8', 'replace'))
    items = j.get('data') or []
    if not items:
        print('[!] no data: %s' % json.dumps(j)[:300]); return 1
    it = items[0]
    d = os.path.dirname(os.path.abspath(a.out))
    os.makedirs(d or '.', exist_ok=True)
    if it.get('b64_json'):
        blob = base64.b64decode(it['b64_json'])
        open(a.out, 'wb').write(blob)
    elif it.get('url'):
        with urllib.request.urlopen(it['url'], timeout=180) as r:
            blob = r.read()
        open(a.out, 'wb').write(blob)
    else:
        print('[!] unexpected item: %s' % json.dumps(it)[:200]); return 1
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
