#!/usr/bin/env python3
"""Pollinations 匿名档 img2img（零 key、零额度）：POST /prompt/<x> + JSON body。
body: {prompt, image(data-URI 或 URL), width, height, model, nologo, seed}
匿名可用模型: flux / turbo / sana（kontext 等需 pollen key）
限流: 1 张 / 45s / IP；脚本自动等待重试。
用法: pol_anon_i2i.py <ref.jpg> <out.jpg> "<instruction>" [model] [w] [h] [seed]
"""
import base64, json, sys, time, urllib.request, os

API = "https://image.pollinations.ai/prompt/x"

def _datauri(path):
    raw = open(path, "rb").read()
    ext = os.path.splitext(path)[1].lower()
    mime = {".png": "image/png", ".webp": "image/webp"}.get(ext, "image/jpeg")
    return f"data:{mime};base64," + base64.b64encode(raw).decode()

def gen(ref, out, prompt, model="flux", w=768, h=1024, seed=None, retries=8, image=None):
    payload = {"prompt": prompt, "model": model, "nologo": True,
               "width": w, "height": h, "image": image or _datauri(ref)}
    if seed is not None: payload["seed"] = seed
    body = json.dumps(payload).encode()
    print(f"[.] {model} {w}x{h} seed={seed} body={len(body)}B")
    for i in range(retries):
        try:
            req = urllib.request.Request(API, data=body,
                headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=300) as r:
                d = r.read()
            if d[:2] == b"\xff\xd8" or d[:8].startswith(b"\x89PNG"):
                open(out, "wb").write(d)
                print(f"[+] saved {out} ({len(d)}B)")
                return True
            txt = d[:250].decode("utf-8", "replace")
            print(f"[!] non-image: {txt}")
            if "FREE_LIMIT" in txt or "402" in txt:
                print(f"[.] rate limited, wait 50s ({i+1}/{retries})")
                time.sleep(50); continue
            return False
        except urllib.error.HTTPError as e:
            t = e.read()[:250].decode("utf-8", "replace")
            print(f"[!] HTTP {e.code}: {t}")
            if e.code in (402, 429): time.sleep(50); continue
            return False
        except Exception as e:
            print(f"[!] {type(e).__name__}: {e}"); time.sleep(15)
    return False

if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) < 3:
        print(__doc__); sys.exit(1)
    gen(a[0], a[1], a[2],
        a[3] if len(a) > 3 else "flux",
        int(a[4]) if len(a) > 4 else 768,
        int(a[5]) if len(a) > 5 else 1024,
        int(a[6]) if len(a) > 6 else None)
