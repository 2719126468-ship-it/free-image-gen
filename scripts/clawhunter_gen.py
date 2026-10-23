#!/usr/bin/env python3
"""Claw Hunter 自控端点（Cloudflare Worker，OpenAI 兼容代理）—— 零密钥 fallback。

状态（2026-10-23 实测）：**Termux 端部署受阻**
  npm install -g wrangler --ignore-scripts → 成功（32 packages / 2 min）
  wrangler --version → 直接崩，原文：
      /data/data/com.termux/files/usr/lib/node_modules/wrangler/node_modules/workerd/lib/main.js:60
          throw new Error(`Unsupported platform: ${platformKey}`);
      Error: Unsupported platform: android arm64 LE
  → workerd（wrangler 的本地运行时）没有 android/arm64 构建，Termux 上跑不了
  → 结论：**待桌面端部署**（在有 x86_64/arm64 Linux 或 macOS 的机器上 `npx wrangler login && npx wrangler deploy`），
    部署完把 URL 写进 ~/.dsh/.clawhunter-url，本脚本即可用。

用法:
  clawhunter_gen.py <out.jpg> "<prompt>" [--model gpt-image-2] [--size 1024x1024] [--url URL]
  clawhunter_gen.py --probe
env: CLAWHUNTER_URL（优先于 URL 参数与 ~/.dsh/.clawhunter-url）
"""
import argparse, base64, json, os, sys, time, urllib.error, urllib.request

URL_FILE = os.path.expanduser('~/.dsh/.clawhunter-url')
UA = 'Mozilla/5.0 (compatible; free-image-gen/1.0)'


def base_url(cli=None):
    for c in (cli, os.environ.get('CLAWHUNTER_URL')):
        if c:
            return c.rstrip('/')
    if os.path.isfile(URL_FILE):
        return open(URL_FILE).read().strip().rstrip('/')
    return ''


def call(base, body, timeout=300):
    req = urllib.request.Request(base + '/v1/images/generations',
                                 data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json', 'User-Agent': UA})
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
    ap.add_argument('--model', default='gpt-image-2')
    ap.add_argument('--size', default='1024x1024')
    ap.add_argument('--url', default=None)
    ap.add_argument('--probe', action='store_true')
    a = ap.parse_args()

    base = base_url(a.url)
    if not base:
        print('[!] 没有 Worker URL：把它写进 ~/.dsh/.clawhunter-url（或设 CLAWHUNTER_URL / --url）')
        print('    部署要求：非 Termux 环境跑 `npx wrangler login && npx wrangler deploy`')
        print('    原因（实测原文）：workerd → Error: Unsupported platform: android arm64 LE')
        return 3

    body = {'model': a.model, 'prompt': a.prompt or 'a simple red cube on white background',
            'size': a.size}
    t0 = time.time()
    st, raw = call(base, body)
    if a.probe or not a.out:
        print('[probe] %s HTTP=%s %dB %.1fs %s' % (base, st, len(raw), time.time() - t0,
              raw[:240].decode('utf-8', 'replace')))
        return 0 if st == 200 else 1
    if st != 200:
        print('[!] HTTP %s: %s' % (st, raw[:300].decode('utf-8', 'replace'))); return 1
    if raw[:2] == b'\xff\xd8' or raw[:8].startswith(b'\x89PNG'):
        blob = raw
    else:
        j = json.loads(raw.decode('utf-8', 'replace'))
        it = (j.get('data') or [{}])[0]
        if it.get('b64_json'):
            blob = base64.b64decode(it['b64_json'])
        elif it.get('url'):
            blob = urllib.request.urlopen(urllib.request.Request(
                it['url'], headers={'User-Agent': UA}), timeout=180).read()
        else:
            print('[!] unexpected: %s' % json.dumps(j)[:300]); return 1
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or '.', exist_ok=True)
    open(a.out, 'wb').write(blob)
    print('[+] saved %s (%dB) in %.1fs' % (a.out, len(blob), time.time() - t0))
    try:
        import hashlib
        from PIL import Image, ImageStat
        im = Image.open(a.out); im.load()
        print('[+] %s %dB md5=%s luma=%.1f' % (im.size, os.path.getsize(a.out),
              hashlib.md5(open(a.out, 'rb').read()).hexdigest()[:16],
              ImageStat.Stat(im.convert('L')).mean[0]))
    except Exception as e:
        print('[i] verify skipped: %s' % e)
    return 0


if __name__ == '__main__':
    sys.exit(main())
