#!/usr/bin/env python3
"""Pollinations 新版 API (gen.pollinations.ai) 图像编辑/生成 —— 有 key 才是真接口。

关键发现（实测）：
  * image.pollinations.ai 的 Classic API 匿名只有 sana，没有 image 参数；
    带 model=kontext 会返回 403 "kontext isn't part of the Classic API"。
  * 真正的 img2img 在 gen.pollinations.ai/v1/images/edits，OpenAI 兼容，
    `image` 接受 URL 或 data:image base64。需要 pollen key（sk_...）。
  * /v1/models 列出 47 个图像模型，其中支持 image 输入的：
      black-forest-labs/flux.1-kontext-pro (alias kontext) 0.03 pollen/图
      microsoft/mai-image-2.6              最多 5 张参考图，指令跟随最强
      microsoft/mai-image-2.6-flash
      openai/gpt-image-1.5 / gpt-image-2 / gpt-image-1-mini
      black-forest-labs/flux.2-klein-4b    最快最便宜
      community/*/flux-2-dev-free          免费但上游有内容审查（会被 flag）
  * 计费货币是 pollen，不是 HF credits；HF Inference Providers 是另一个池子。

usage:
  pol_edit.py <ref.jpg> <out.jpg> "<edit instruction>" [model]
  pol_edit.py --gen <out.jpg> "<prompt>" [model]        # 纯文生图

env: POLLEN_KEY / POLLINATIONS_KEY（或 ~/.dsh/.pollinations-key 里的 POLLINATIONS_KEY=）
     SIZE=768x1024  QUALITY=high|medium|low  SEED=...  SAFE=...
"""
import base64, json, os, sys, urllib.request, urllib.error

API = 'https://gen.pollinations.ai'


def key():
    k = os.environ.get('POLLEN_KEY') or os.environ.get('POLLINATIONS_KEY')
    if k:
        return k.strip()
    p = os.path.expanduser('~/.dsh/.pollinations-key')
    if os.path.exists(p):
        for line in open(p):
            if line.startswith('POLLINATIONS_KEY='):
                return line.split('=', 1)[1].strip()
    print('[!] 没有 pollen key：~/.dsh/.pollinations-key 或 POLLEN_KEY'); sys.exit(1)


def data_uri(path):
    raw = open(os.path.expanduser(path), 'rb').read()
    ext = os.path.splitext(path)[1].lower().lstrip('.') or 'jpeg'
    if ext == 'jpg':
        ext = 'jpeg'
    return f'data:image/{ext};base64,' + base64.b64encode(raw).decode()


def post(ep, body):
    r = urllib.request.Request(API + ep, data=json.dumps(body).encode(),
        headers={'Authorization': 'Bearer ' + key(),
                 'Content-Type': 'application/json', 'User-Agent': 'lcs/1.0'})
    try:
        resp = urllib.request.urlopen(r, timeout=420)
        return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return 0, str(e).encode()


def save(payload, out):
    o = os.path.expanduser(out)
    os.makedirs(os.path.dirname(o) or '.', exist_ok=True)
    try:
        j = json.loads(payload)
    except Exception:
        open(o, 'wb').write(payload)          # 直接就是图片字节
        return o
    d = (j.get('data') or [{}])[0]
    b = d.get('b64_json') or j.get('b64_json')
    u = d.get('url') or j.get('url')
    if b:
        open(o, 'wb').write(base64.b64decode(b))
    elif u:
        print('[.] fetching', u[:100])
        open(o, 'wb').write(urllib.request.urlopen(
            urllib.request.Request(u, headers={'User-Agent': 'lcs/1.0'}),
            timeout=240).read())
    else:
        print('[!] 响应里没有图:', json.dumps(j)[:500]); sys.exit(2)
    return o


def main():
    args = sys.argv[1:]
    gen = False
    if args and args[0] == '--gen':
        gen, args = True, args[1:]
    if len(args) < 2:
        print(__doc__); sys.exit(1)

    if gen:
        out, prompt = args[0], args[1]
        model = args[2] if len(args) > 2 else 'microsoft/mai-image-2.6'
        body = {'model': model, 'prompt': prompt}
        ref = None
    else:
        if len(args) < 3:
            print(__doc__); sys.exit(1)
        ref, out, prompt = args[0], args[1], args[2]
        model = args[3] if len(args) > 3 else 'black-forest-labs/flux.1-kontext-pro'
        body = {'model': model, 'prompt': prompt, 'image': data_uri(ref)}

    body['size'] = os.environ.get('SIZE', '768x1024')
    body['quality'] = os.environ.get('QUALITY', 'high')
    body['response_format'] = 'b64_json'
    if os.environ.get('SEED'):
        body['seed'] = int(os.environ['SEED'])
    if os.environ.get('SAFE'):
        body['safe'] = os.environ['SAFE']

    ep = '/v1/images/generations' if gen else '/v1/images/edits'
    print(f'[.] POST {ep}  model={model}  size={body["size"]}  q={body["quality"]}')
    print(f'[.] prompt: {prompt[:140]}')
    st, payload = post(ep, body)
    if st != 200:
        txt = payload.decode('utf8', 'replace')
        print(f'[!] HTTP {st}: {txt[:600]}')
        low = txt.lower()
        if 'flagged' in low or 'content' in low and 'policy' in low:
            print('[!] 上游内容审查拦了 —— 换 model（kontext-pro / mai-image-2.6 审查松）或改措辞')
        elif 'insufficient' in low or 'balance' in low or 'pollen' in low:
            print('[!] pollen 余额不足：gen.pollinations.ai/account/balance 查看，或换便宜模型 flux.2-klein-4b')
        sys.exit(1)
    p = save(payload, out)
    print(f'[+] saved {p} ({os.path.getsize(p)}B)')


main()
