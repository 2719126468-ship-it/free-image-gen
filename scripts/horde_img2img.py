#!/usr/bin/env python3
"""AI Horde img2img: keep a reference composition, repaint one element.

Submits source_image (base64) + source_processing=img2img to /generate/async,
polls status, downloads the result. Reads the image from a file so we dodge
Android's 128KiB argv limit.

usage: horde_img2img.py <ref.jpg> <out.webp> <prompt> <negative> [denoise] [model]
"""
import json, os, sys, base64, time, subprocess, urllib.request, urllib.error

B = 'https://stablehorde.net/api/v2'
HDR = {'Content-Type': 'application/json', 'apikey': '0000000000',
       'Client-Agent': 'termux-gen:1.0:dsh'}

def main():
    ref, out = sys.argv[1], sys.argv[2]
    prompt, negative = sys.argv[3], sys.argv[4]
    denoise = float(sys.argv[5]) if len(sys.argv) > 5 else 0.7
    model = sys.argv[6] if len(sys.argv) > 6 else 'WAI-NSFW-illustrious-SDXL'

    raw = open(os.path.expanduser(ref), 'rb').read()
    src = base64.b64encode(raw).decode()
    print(f'[.] ref {len(raw)}B -> base64 {len(src)}B  denoise={denoise}  model={model}')

    body = {
        'prompt': prompt, 'negative_prompt': negative,
        'models': [model],
        'source_image': src, 'source_processing': 'img2img',
        'denoising_strength': denoise,
        'nsfw': True, 'censor_nsfw': False, 'special': False,
        'width': 768, 'height': 1024, 'samples': 1,
        'steps': 30, 'cfg_scale': 5, 'sampler_name': 'DPM++ 2M Karras',
        'clip_skip': 2,
    }
    r = urllib.request.Request(B + '/generate/async',
                               data=json.dumps(body).encode(), headers=HDR)
    try:
        d = json.load(urllib.request.urlopen(r, timeout=60))
    except urllib.error.HTTPError as e:
        print(f'[!] submit HTTP {e.code}: {e.read().decode()[:300]}'); sys.exit(1)
    jid = d.get('id')
    print(f'[.] job={jid}  kudos={d.get("kudos")}')

    t0 = time.time()
    while time.time() - t0 < 1800:
        time.sleep(20)
        try:
            s = json.load(urllib.request.urlopen(
                urllib.request.Request(B + f'/generate/status/{jid}',
                                       headers={'apikey': '0000000000',
                                                 'Client-Agent': 'termux-gen:1.0:dsh'}),
                timeout=30))
        except Exception as e:
            print(f'  poll-err {str(e)[:60]}'); continue
        el = int(time.time() - t0)
        print(f'  t={el}s q={s.get("queued")} wait={s.get("wait_time")} '
              f'fin={s.get("finished")} state={s.get("status")} '
              f'is_img2img={s.get("is_img2img")}')
        if s.get('faulted'):
            print('[!] faulted:', s.get('message')); sys.exit(2)
        if s.get('finished', 0) >= 1 and s.get('generations'):
            img = s['generations'][0]['img']
            url = img if img.startswith('http') else f'https://stablehorde.net/{img}'
            o = os.path.expanduser(out)
            os.makedirs(os.path.dirname(o), exist_ok=True)
            for a in range(4):
                subprocess.run(['curl', '-sL', '-o', o, '--max-time', '150', url])
                if os.path.exists(o) and os.path.getsize(o) > 20000:
                    break
                time.sleep(3)
            print(f'[+] saved {o} ({os.path.getsize(o) if os.path.exists(o) else 0}B) '
                  f'censored={s.get("censored")} at {el}s')
            return
    print('[!] timed out'); sys.exit(3)

main()
