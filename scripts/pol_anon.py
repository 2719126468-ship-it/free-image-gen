#!/usr/bin/env python3
"""Pollinations 匿名档（无 key）：image.pollinations.ai GET，45s/IP 限流。
用法: pol_anon.py <out.jpg> "<prompt>" [model] [width] [height] [seed]
model: flux|turbo|sana (kontext/nanobanana/seedream 需 pollen key，匿名 403)
"""
import sys, time, urllib.parse, urllib.request, os

def gen(out, prompt, model="flux", w=1024, h=1024, seed=None, retries=6):
    q = {"width": w, "height": h, "model": model, "nologo": "true"}
    if seed is not None: q["seed"] = seed
    url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}?{urllib.parse.urlencode(q)}"
    print(f"[.] {model} {w}x{h} seed={seed}")
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=180) as r:
                data = r.read()
            if data[:2] == b"\xff\xd8" or data[:8].startswith(b"\x89PNG"):
                open(out, "wb").write(data)
                print(f"[+] saved {out} ({len(data)}B)")
                return True
            body = data[:200].decode("utf-8", "replace")
            print(f"[!] non-image ({len(data)}B): {body}")
            if "FREE_LIMIT" in body or "402" in body:
                wait = 50
                print(f"[.] free limit, wait {wait}s (try {i+1}/{retries})")
                time.sleep(wait)
                continue
            return False
        except urllib.error.HTTPError as e:
            body = e.read()[:200].decode("utf-8", "replace")
            print(f"[!] HTTP {e.code}: {body}")
            if e.code == 402:
                time.sleep(50); continue
            return False
        except Exception as e:
            print(f"[!] {type(e).__name__}: {e}")
            time.sleep(10)
    return False

if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) < 2:
        print(__doc__); sys.exit(1)
    gen(a[0], a[1], a[2] if len(a) > 2 else "flux",
        int(a[3]) if len(a) > 3 else 1024,
        int(a[4]) if len(a) > 4 else 1024,
        int(a[5]) if len(a) > 5 else None)
