#!/usr/bin/env python3
"""NVIDIA NIM (build.nvidia.com) 文生图 —— 官方免费档，实测结论见 docs/routes.md 第十三节。

免绑卡依据：build.nvidia.com 注册只需 NVIDIA Developer 账号（社区实测与官方 FAQ 均为免费、
无需信用卡），免费档 1,000 credits/月。**本脚本不代你注册**，key 自行获取后放
~/.dsh/.nim-key（内容 NVIDIA_API_KEY=nvapi-...）。

实测（2026-10-23，无 key）：
  * https://integrate.api.nvidia.com/v1/models  → HTTP 200（84 个模型，匿名可读，但全是 LLM/embedding）
  * https://ai.api.nvidia.com/v1/genai/stabilityai/stable-diffusion-xl → 401
    原文：Header of type `authorization` was missing
  → 生图走 ai.api.nvidia.com/v1/genai/{owner}/{model}，必须 Bearer。

用法:
  nvidia_nim_gen.py <out.png> "<prompt>" [--model M] [--w 1024] [--h 1024] [--steps 30] [--seed N]
  nvidia_nim_gen.py --probe            # 只探活（不带 key 也能跑，记录状态码/原文）

模型（--model）:
  stabilityai/stable-diffusion-xl                 payload: text_prompts[]
  black-forest-labs/flux.1-dev                    payload: prompt + mode
  black-forest-labs/flux.1-schnell                payload: prompt + mode
  stabilityai/stable-diffusion-3-medium           payload: prompt
"""
import argparse, base64, json, os, sys, time, urllib.error, urllib.request

API = 'https://ai.api.nvidia.com/v1/genai'
KEY_FILE = os.path.expanduser('~/.dsh/.nim-key')


def key():
    k = os.environ.get('NVIDIA_API_KEY') or os.environ.get('NIM_API_KEY')
    if k:
        return k.strip()
    if os.path.isfile(KEY_FILE):
        for line in open(KEY_FILE):
            line = line.strip()
            if line.startswith('NVIDIA_API_KEY='):
                return line.split('=', 1)[1].strip()
            if line.startswith('nvapi-'):
                return line
    return ''


def _post(url, body, k):
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={'User-Agent': 'Mozilla/5.0 (compatible; free-image-gen/1.0)',
                                 'Content-Type': 'application/json',
                                          'Accept': 'application/json',
                                          **({'Authorization': 'Bearer ' + k} if k else {})})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return 0, ('%s: %s' % (type(e).__name__, e)).encode()


def build_body(model, prompt, w, h, steps, seed):
    if 'stable-diffusion-xl' in model:
        return {'text_prompts': [{'text': prompt, 'weight': 1}], 'cfg_scale': 7,
                'seed': seed, 'steps': steps, 'height': h, 'width': w}
    return {'prompt': prompt, 'mode': 'base', 'width': w, 'height': h,
            'seed': seed, 'steps': steps}


def save(data, out):
    """NIM 返回 {"artifacts":[{"base64":"..."}]}，也兼容直接二进制。"""
    if data[:8].startswith(b'\x89PNG') or data[:2] == b'\xff\xd8':
        blob = data
    else:
        j = json.loads(data.decode('utf-8', 'replace'))
        art = (j.get('artifacts') or [{}])[0]
        b64 = art.get('base64') or (j.get('data') or [{}])[0].get('b64_json')
        if not b64:
            raise RuntimeError('no image in response: %s' % json.dumps(j)[:300])
        blob = base64.b64decode(b64)
    os.makedirs(os.path.dirname(os.path.abspath(out)) or '.', exist_ok=True)
    open(out, 'wb').write(blob)
    return len(blob)


def verify(out):
    try:
        from PIL import Image, ImageStat
        im = Image.open(out); im.load()
        st = ImageStat.Stat(im.convert('L'))
        import hashlib
        print('[+] %s %s %dB md5=%s luma=%.1f' % (out, im.size, os.path.getsize(out),
              hashlib.md5(open(out, 'rb').read()).hexdigest()[:16], st.mean[0]))
        return im.size
    except Exception as e:
        print('[!] verify failed: %s' % e)
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out', nargs='?')
    ap.add_argument('prompt', nargs='?')
    ap.add_argument('--model', default='stabilityai/stable-diffusion-xl')
    ap.add_argument('--w', type=int, default=1024)
    ap.add_argument('--h', type=int, default=1024)
    ap.add_argument('--steps', type=int, default=30)
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--probe', action='store_true')
    a = ap.parse_args()

    k = key()
    if a.probe:
        for m in ('stabilityai/stable-diffusion-xl', 'black-forest-labs/flux.1-dev'):
            t0 = time.time()
            code, body = _post('%s/%s' % (API, m), build_body(m, 'a red apple', 512, 512, 4, 0), k)
            print('[probe] %-45s HTTP=%s %dB %.1fs %s' % (m, code, len(body), time.time() - t0,
                  '' if code == 200 else body[:160].decode('utf-8', 'replace')))
        print('[i] key: %s' % ('有' if k else '缺（放 ~/.dsh/.nim-key）'))
        return 0 if k else 2

    if not (a.out and a.prompt):
        ap.error('需要 <out> 与 <prompt>（或 --probe）')
    if not k:
        print('[!] 缺 key：~/.dsh/.nim-key 里写 NVIDIA_API_KEY=nvapi-...（build.nvidia.com 免费领取）')
        return 2
    url = '%s/%s' % (API, a.model)
    print('[.] NIM %s %dx%d steps=%d' % (a.model, a.w, a.h, a.steps))
    t0 = time.time()
    code, body = _post(url, build_body(a.model, a.prompt, a.w, a.h, a.steps, a.seed), k)
    if code != 200:
        print('[!] HTTP %s: %s' % (code, body[:300].decode('utf-8', 'replace')))
        return 1
    n = save(body, a.out)
    print('[+] saved %s (%dB) in %.1fs' % (a.out, n, time.time() - t0))
    verify(a.out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
