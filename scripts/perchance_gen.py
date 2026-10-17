#!/usr/bin/env python3
"""Perchance stable-diffusion 免费无限生图（CLI 版，真 chromium 过 Turnstile）。

数据流（逆向自 yuser00123/perchance-mcp-unlimited，2026-09-24 版）：
  1. browserId = 32hex（localStorage['generation-v2-browser']）
  2. adAccessCode = GET perchance.org/api/getAccessCodeForAdPoweredStuff（住宅 IP + UA 直过）
  3. Turnstile 过验证 → GET image-generation.perchance.org/api/verifyUser
     ?browserId=..&token=..&thread=0 → {"userKey": 64hex}（~30s 有效，IP 绑定）
  4. POST /api/generate?userKey=..&requestId=0.<rand>&adAccessCode=..&v=9b43eec2...
     body {prompt, negativePrompt, seed, resolution, guidanceScale, channel,
           subChannel:"public", userKey, adAccessCode, requestId}
  5. imageDownloadUrl=/api/downloadTemporaryImageViaProxy?t=v1...（5min 有效）

分辨率: 512x512 | 512x768 | 768x512 | 768x768
用法:
  perchance_gen.py <out.jpg> "<prompt>" [negative] [seed] [resolution] [guidance]
无 Turnstile 可解时（600010）直接失败退出，不空转。
"""
import json, os, random, secrets, subprocess, sys, time, urllib.parse, urllib.request

UA = ('Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/152.0.0.0 Mobile Safari/537.36')
V_HASH = '9b43eec2e71907610e4e9317b54c208495f6850086e92239a869811d2e2d77ee'
IG = 'https://image-generation.perchance.org'
PC = 'https://perchance.org'


def get_ad_code():
    """ad code：住宅 IP + 浏览器 UA 可直接过，无需代理。"""
    r = urllib.request.Request(
        f'{PC}/api/getAccessCodeForAdPoweredStuff?__cacheBust={time.time_ns()}',
        headers={'User-Agent': UA, 'Referer': f'{PC}/stable-diffusion-ai',
                 'Origin': PC, 'Accept': '*/*'})
    code = urllib.request.urlopen(r, timeout=30).read().decode().strip()
    if len(code) != 64 or not all(c in '0123456789abcdef' for c in code):
        raise RuntimeError(f'ad code 异常: {code[:80]}')
    return code


def turnstile_user_key():
    """真 chromium 加载 verifyUser 页面，等 Turnstile 自解（无感模式多数自动过），
    从页面返回 JSON 里拿 userKey。"""
    bid = secrets.token_hex(16)
    url = f'{IG}/api/verifyUser?browserId={bid}&thread=0'
    py = f'''
import json, time, sys
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chromium.options import ChromiumOptions
opts = ChromiumOptions()
opts.add_argument('--headless=new')
opts.add_argument('--no-sandbox')
opts.add_argument('--disable-gpu')
opts.add_argument('--disable-dev-shm-usage')
opts.add_argument('--user-agent={UA}')
d = webdriver.Chrome(service=Service('/data/data/com.termux/files/usr/bin/chromedriver'), options=opts)
d.set_page_load_timeout(90)
try:
    d.get('{url}')
    for _ in range(60):
        time.sleep(2)
        t = d.find_element('tag name', 'body').text or d.title
        if 'userKey' in t or 'success' in t:
            print(t[:2000]); sys.exit(0)
    print('TIMEOUT|' + (d.title or '') + '|' + (d.find_element('tag name','body').text[:400] if d.find_elements('tag name','body') else ''))
finally:
    d.quit()
'''
    out = subprocess.run([sys.executable, '-c', py], capture_output=True,
                         text=True, timeout=300)
    txt = (out.stdout or '') + (out.stderr or '')
    print('[.] turnstile page:', txt[:300])
    import re
    m = re.search(r'"userKey"\s*:\s*"([0-9a-f]{64})"', txt)
    if m:
        return bid, m.group(1)
    m = re.search(r'([0-9a-f]{64})', txt)
    if m:
        return bid, m.group(1)
    raise RuntimeError('Turnstile 未过（600010/timeout）：' + txt[:200])


def generate(user_key, ad_code, prompt, negative, seed, resolution, guidance):
    rid = f'0.{random.random()}'
    q = (f'userKey={user_key}&requestId={rid}&adAccessCode={ad_code}'
         f'&v={V_HASH}&__cacheBust={time.time_ns()}')
    body = {'prompt': prompt, 'negativePrompt': negative, 'seed': seed,
            'resolution': resolution, 'guidanceScale': guidance,
            'channel': 'stable-diffusion-ai', 'subChannel': 'public',
            'userKey': user_key, 'adAccessCode': ad_code, 'requestId': rid}
    r = urllib.request.Request(f'{IG}/api/generate?{q}',
        data=json.dumps(body).encode(),
        headers={'User-Agent': UA, 'Content-Type': 'application/json',
                 'Referer': f'{IG}/embed', 'Origin': IG, 'Accept': '*/*'})
    return json.loads(urllib.request.urlopen(r, timeout=120).read().decode())


def download(url_path, out):
    if url_path.startswith('/'):
        url_path = IG + url_path
    r = urllib.request.Request(url_path,
        headers={'User-Agent': UA, 'Referer': f'{IG}/embed', 'Accept': '*/*'})
    data = urllib.request.urlopen(r, timeout=90).read()
    open(os.path.expanduser(out), 'wb').write(data)
    return data


def main():
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(1)
    out, prompt = sys.argv[1], sys.argv[2]
    negative = sys.argv[3] if len(sys.argv) > 3 else ''
    seed = int(sys.argv[4]) if len(sys.argv) > 4 else random.randint(1, 10**9)
    resolution = sys.argv[5] if len(sys.argv) > 5 else '768x768'
    guidance = float(sys.argv[6]) if len(sys.argv) > 6 else 9

    print('[1] ad code ...')
    ad = get_ad_code()
    print('    ok', ad[:16] + '...')
    print('[2] Turnstile → userKey ...')
    bid, key = turnstile_user_key()
    print('    ok', key[:16] + '...  (30s 内必须用)')
    print(f'[3] generate seed={seed} {resolution} g={guidance} ...')
    t0 = time.time()
    j = generate(key, ad, prompt, negative, seed, resolution, guidance)
    print('   ', json.dumps(j)[:200])
    if j.get('status') not in (None, 'success'):
        raise SystemExit(f'[!] generate 失败: {j}')
    dl = (j.get('imageDownloadUrl') or
          (j.get('imageDataUrls') or [''])[0])
    if dl.startswith('data:'):
        import base64
        open(os.path.expanduser(out), 'wb').write(
            base64.b64decode(dl.split(',', 1)[1]))
    elif dl:
        print('[4] download ...')
        data = download(dl, out)
    else:
        raise SystemExit('[!] 响应无图: ' + json.dumps(j)[:300])
    p = os.path.expanduser(out)
    print(f'[+] saved {p} ({os.path.getsize(p)}B)  {time.time()-t0:.0f}s')


main()
