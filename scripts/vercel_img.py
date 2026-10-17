#!/usr/bin/env python3
"""Vercel AI Gateway 图像编辑/生成 —— 免费层 $5 / 30 天循环，含 bfl/flux-kontext-pro。

为什么用它：
  * pollen 余额只剩 0.2，kontext-pro 0.03/张 ≈ 6 张就没了
  * Vercel 免费层（**未充过款**的账号）每 30 天送 $5；kontext-pro $0.04/张 ≈ 125 张
  * 一旦充值就永久失去每月 $5 → 别充钱

端点（官方文档实测确认）：
  * 图像编辑：POST https://ai-gateway.vercel.sh/v1/images/edits   （multipart/form-data）
  * 文生图  ：POST https://ai-gateway.vercel.sh/v1/images/generations
  * 多模态 LLM（nano-banana 等）：/v1/chat/completions，图片在 choices[0].message.images[]
  支持 image 输入的模型：openai/gpt-image-2、bfl/flux-kontext-pro、bfl/flux-pro-1.0-fill、
  google/gemini-3.1-flash-image、spacexai/grok-imagine-image

准备（一次性，手动）：
  1. 注册 https://vercel.com（免费，不绑卡）
  2. Dashboard → AI Gateway → API Keys → Create（或 `vercel ai-gateway api-keys create`）
  3. echo "AI_GATEWAY_API_KEY=vck_..." > ~/.dsh/.vercel-gw-key && chmod 600 ~/.dsh/.vercel-gw-key

用法：
  vercel_img.py <ref.jpg> <out.jpg> "<instruction>" [model]     # img2img 编辑
  vercel_img.py --gen <out.jpg> "<prompt>" [model]              # 纯文生图

env: AI_GATEWAY_API_KEY / VERCEL_GW_KEY 覆盖文件；SIZE=1024x1024；N=1
"""
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.request
import uuid

BASE = 'https://ai-gateway.vercel.sh/v1'
DEFAULT_EDIT = 'bfl/flux-kontext-pro'
DEFAULT_GEN = 'bfl/flux-kontext-pro'


def key():
    k = os.environ.get('AI_GATEWAY_API_KEY') or os.environ.get('VERCEL_GW_KEY')
    if k:
        return k.strip()
    p = os.path.expanduser('~/.dsh/.vercel-gw-key')
    if os.path.exists(p):
        for line in open(p):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if line.startswith('AI_GATEWAY_API_KEY='):
                return line.split('=', 1)[1].strip()
            if '=' not in line:
                return line
    print('[!] 没有 Vercel AI Gateway key。一次性准备：')
    print('    1) 注册 https://vercel.com （免费，别绑卡 —— 绑卡/充值会永久失去每月 $5）')
    print('    2) Dashboard → AI Gateway → API Keys → Create')
    print('    3) echo "AI_GATEWAY_API_KEY=vck_..." > ~/.dsh/.vercel-gw-key && chmod 600 ~/.dsh/.vercel-gw-key')
    sys.exit(1)


def multipart(fields, files):
    """files: [(field, path)]  ->  (body_bytes, content_type)"""
    boundary = '----lcs' + uuid.uuid4().hex
    out = []
    for k, v in fields.items():
        out.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    for field, path in files:
        p = os.path.expanduser(path)
        raw = open(p, 'rb').read()
        ctype = mimetypes.guess_type(p)[0] or 'image/jpeg'
        out.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; '
            f'filename="{os.path.basename(p)}"\r\nContent-Type: {ctype}\r\n\r\n'.encode()
            + raw + b'\r\n')
    out.append(f'--{boundary}--\r\n'.encode())
    return b''.join(out), f'multipart/form-data; boundary={boundary}'


def post(path, body, ctype):
    req = urllib.request.Request(
        BASE + path, data=body,
        headers={'Authorization': 'Bearer ' + key(), 'Content-Type': ctype,
                 'User-Agent': 'lcs/1.0'})
    try:
        return urllib.request.urlopen(req, timeout=420).read()
    except urllib.error.HTTPError as e:
        txt = e.read().decode('utf8', 'replace')
        print(f'[!] HTTP {e.code}: {txt[:700]}')
        low = txt.lower()
        if e.code == 401:
            print('[!] key 无效：Dashboard → AI Gateway → API Keys 重建')
        elif e.code in (402, 403) or 'credit' in low or 'quota' in low:
            print('[!] 免费额度用完/无权限：等下个 30 天周期，或换更便宜的免费层模型 bfl/flux-2-klein-4b')
        elif e.code == 429:
            print('[!] 免费层速率限制：等 30–60s 重试')
        elif 'model' in low:
            print('[!] 模型不支持或不在免费层：查 /ai-gateway/models?freeTier=true')
        sys.exit(1)


def save(payload, out):
    j = json.loads(payload)
    d = (j.get('data') or [])
    if not d:
        raise SystemExit('[!] 响应里没有图: ' + json.dumps(j)[:600])
    item = d[0]
    o = os.path.expanduser(out)
    os.makedirs(os.path.dirname(o) or '.', exist_ok=True)
    if item.get('b64_json'):
        import base64
        img = base64.b64decode(item['b64_json'])
        open(o, 'wb').write(img)
    elif item.get('url'):
        img = urllib.request.urlopen(item['url'], timeout=240).read()
        open(o, 'wb').write(img)
    else:
        raise SystemExit('[!] 未知返回格式: ' + json.dumps(item)[:300])
    print(f'[+] saved {o} ({os.path.getsize(o)}B)')


def main():
    args = sys.argv[1:]
    gen = False
    if args and args[0] == '--gen':
        gen, args = True, args[1:]
    if len(args) < 2:
        print(__doc__)
        sys.exit(1)

    if gen:
        out, prompt = args[0], args[1]
        model = args[2] if len(args) > 2 else DEFAULT_GEN
        fields = {'model': model, 'prompt': prompt, 'n': os.environ.get('N', '1')}
        if os.environ.get('SIZE'):
            fields['size'] = os.environ['SIZE']
        print(f'[.] POST {BASE}/images/generations  model={model}')
        print(f'[.] prompt: {prompt[:140]}')
        body, ctype = multipart(fields, [])
        save(post('/images/generations', body, ctype), out)
    else:
        ref, out, prompt = args[0], args[1], args[2]
        model = args[3] if len(args) > 3 else DEFAULT_EDIT
        fields = {'model': model, 'prompt': prompt, 'n': os.environ.get('N', '1')}
        if os.environ.get('SIZE'):
            fields['size'] = os.environ['SIZE']
        print(f'[.] POST {BASE}/images/edits  model={model}')
        print(f'[.] ref={ref}  prompt: {prompt[:140]}')
        body, ctype = multipart(fields, [('image', ref)])
        save(post('/images/edits', body, ctype), out)


main()
