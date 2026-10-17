#!/usr/bin/env python3
"""Replicate Try-for-Free —— 注册即可白跑有限次数，含 black-forest-labs/flux-kontext-pro。

免费集合（官方确认）：https://replicate.com/collections/try-for-free
  black-forest-labs/flux-kontext-pro   图像编辑（本项目要的）
  black-forest-labs/flux-1.1-pro       文生图
  google/imagen-4                      文生图
  ideogram-ai/ideogram-v3-turbo        文生图（带字强）
  black-forest-labs/flux-dev           文生图
  topazlabs/image-upscale / codeformer / gfpgan  修复放大
官方 FAQ：免费是「有限次数」，次数未公开；用完要绑卡充值。

准备：
  1. 注册 https://replicate.com （免费，不绑卡）
  2. https://replicate.com/account/api-tokens 建 token
  3. echo "REPLICATE_API_TOKEN=r8_..." > ~/.dsh/.replicate-token && chmod 600 ~/.dsh/.replicate-token

用法：
  replicate_edit.py <ref.jpg> <out.jpg> "<instruction>" [model]
  replicate_edit.py --gen <out.jpg> "<prompt>" [model]

env: REPLICATE_API_TOKEN 覆盖文件
"""
import json, os, sys, time, urllib.error, urllib.request, base64

API = 'https://api.replicate.com/v1'
EDIT_MODEL = 'black-forest-labs/flux-kontext-pro'
GEN_MODEL = 'black-forest-labs/flux-1.1-pro'


def token():
    t = os.environ.get('REPLICATE_API_TOKEN')
    if t:
        return t.strip()
    p = os.path.expanduser('~/.dsh/.replicate-token')
    if os.path.exists(p):
        for line in open(p):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            return line.split('=', 1)[1].strip() if '=' in line else line
    print('[!] 没有 Replicate token。一次性准备：')
    print('    1) 注册 https://replicate.com （免费，不绑卡）')
    print('    2) https://replicate.com/account/api-tokens 建 token')
    print('    3) echo "REPLICATE_API_TOKEN=r8_..." > ~/.dsh/.replicate-token && chmod 600 ~/.dsh/.replicate-token')
    sys.exit(1)


def call(method, url, body=None):
    req = urllib.request.Request(
        url, data=json.dumps(body).encode() if body is not None else None,
        headers={'Authorization': 'Bearer ' + token(), 'Content-Type': 'application/json',
                 'User-Agent': 'lcs/1.0'},
        method=method)
    try:
        return json.load(urllib.request.urlopen(req, timeout=120))
    except urllib.error.HTTPError as e:
        txt = e.read().decode('utf8', 'replace')
        print(f'[!] HTTP {e.code}: {txt[:600]}')
        low = txt.lower()
        if e.code == 401:
            print('[!] token 无效')
        elif 'payment' in low or 'billing' in low or 'credit' in low:
            print('[!] 免费次数用完：该模型不再免费，需绑卡充值（别充，换 Vercel 免费层）')
        elif 'not found' in low or 'no method' in low:
            print('[!] 模型不存在或不在 Try-for-Free 集合')
        sys.exit(1)


def data_uri(path):
    raw = open(os.path.expanduser(path), 'rb').read()
    ext = os.path.splitext(path)[1].lower().lstrip('.') or 'jpeg'
    if ext == 'jpg':
        ext = 'jpeg'
    return f'data:image/{ext};base64,' + base64.b64encode(raw).decode()


def run(model, inp, out):
    # 优先用官方 model predictions 端点（免费集合按 model 授权）
    owner, name = model.split('/', 1)
    url = f'{API}/models/{owner}/{name}/predictions'
    print(f'[.] POST {url}')
    pred = call('POST', url, {'input': inp})
    pid = pred.get('id')
    print(f'[.] prediction={pid}  status={pred.get("status")}')
    t0 = time.time()
    while time.time() - t0 < 600:
        time.sleep(3)
        pred = call('GET', f'{API}/predictions/{pid}')
        st = pred.get('status')
        if st in ('succeeded', 'failed', 'canceled'):
            break
        if int(time.time() - t0) % 30 < 3:
            print(f'    t={int(time.time()-t0)}s status={st}')
    if pred.get('status') != 'succeeded':
        print(f'[!] 失败: {pred.get("status")}  {str(pred.get("error"))[:400]}')
        sys.exit(1)
    outp = pred.get('output')
    u = outp[0] if isinstance(outp, list) else outp
    if not isinstance(u, str):
        print('[!] 输出格式异常:', str(outp)[:300]); sys.exit(1)
    o = os.path.expanduser(out)
    os.makedirs(os.path.dirname(o) or '.', exist_ok=True)
    open(o, 'wb').write(urllib.request.urlopen(u, timeout=240).read())
    print(f'[+] saved {o} ({os.path.getsize(o)}B)  in {int(time.time()-t0)}s')


def main():
    args = sys.argv[1:]
    gen = False
    if args and args[0] == '--gen':
        gen, args = True, args[1:]
    if len(args) < 2:
        print(__doc__); sys.exit(1)
    if gen:
        out, prompt = args[0], args[1]
        model = args[2] if len(args) > 2 else GEN_MODEL
        run(model, {'prompt': prompt}, out)
    else:
        ref, out, prompt = args[0], args[1], args[2]
        model = args[3] if len(args) > 3 else EDIT_MODEL
        print(f'[.] model={model}  prompt: {prompt[:140]}')
        run(model, {'prompt': prompt, 'input_image': data_uri(ref),
                    'aspect_ratio': 'match_input_image', 'output_format': 'jpg'}, out)


main()
