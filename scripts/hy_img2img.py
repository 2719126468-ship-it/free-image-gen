#!/usr/bin/env python3
"""hy_img2img.py — AI Horde img2img（无审查、匿名、无限量），专为 9:16 竖构图 + 角色一致性设计。

与 horde_img2img.py 的区别：
  * 尺寸可配（--size 9:16 / 3:4 / 自定义 WxH）
  * 模型可配（--model），默认挑队列最短的 NSFW anime 模型
  * 自动把参考图缩放到目标尺寸比例再上传（避免 horde 二次裁切破坏构图）
  * 支持 --list 查可用模型与实时队列
  * 支持 --seed 固定种子、--poll 调整轮询

usage:
  hy_img2img.py --list
  hy_img2img.py ref.png out.webp "prompt" "negative" --size 9:16 --denoise 0.7
  hy_img2img.py ref.png out.webp "prompt" "negative" --model "WAI-NSFW-illustrious-SDXL"
"""
import argparse
import base64
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request

B = "https://stablehorde.net/api/v2"
HDR = {
    "Content-Type": "application/json",
    "apikey": os.environ.get("HORDE_KEY", "0000000000"),
    "Client-Agent": "termux-gen:1.1:dsh",
}
RATIOS = {"9:16": (768, 1344), "3:4": (832, 1088), "2:3": (832, 1216),
          "1:1": (1024, 1024), "16:9": (1344, 768), "4:3": (1088, 832)}
NSFW_HINTS = ("nsfw", "illustrious", "pony", "hentai", "anime", "realism")


def list_models():
    d = json.load(urllib.request.urlopen(B + "/status/models?type=image", timeout=40))
    rows = []
    for m in d:
        if m["count"] <= 0:
            continue
        n = m["name"].lower()
        if any(k in n for k in NSFW_HINTS):
            rows.append((m["queued"], m["jobs"], m["eta"], m["count"], m["name"]))
    rows.sort(key=lambda r: (r[0], r[2]))
    print(f"{'queued':>14} {'jobs':>5} {'eta':>5} {'w':>3}  model")
    for q, j, e, c, n in rows:
        print(f"{q:>14.0f} {j:>5.0f} {e:>5} {c:>3}  {n}")
    return rows


def prepare_ref(path, w, h):
    """把参考图缩放到目标比例，避免 horde 端裁切改变构图。"""
    from PIL import Image
    im = Image.open(path).convert("RGB")
    tr = w / h
    sr = im.width / im.height
    if sr > tr:                                   # 太宽 -> 裁两边
        nw = int(im.height * tr)
        im = im.crop(((im.width - nw) // 2, 0, (im.width + nw) // 2, im.height))
    elif sr < tr:                                 # 太高 -> 裁上下
        nh = int(im.width / tr)
        im = im.crop((0, (im.height - nh) // 2, im.width, (im.height + nh) // 2))
    im = im.resize((w, h), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=92)
    return buf.getvalue(), im.size


def submit(args):
    w, h = RATIOS.get(args.size, (768, 1344)) if args.size in RATIOS else (
        tuple(int(x) for x in args.size.lower().split("x")) if "x" in args.size else (768, 1344))

    if args.denoise > 0 and args.ref:
        raw, sz = prepare_ref(args.ref, w, h)
        print(f"[.] ref {args.ref} -> {sz[0]}x{sz[1]}  {len(raw)}B")
    else:
        raw, sz = None, (w, h)

    body = {
        "prompt": args.prompt,
        "negative_prompt": args.negative or "",
        "models": [args.model] if args.model else [],
        "params": {
            "width": w, "height": h, "steps": args.steps,
            "cfg_scale": args.cfg, "sampler_name": "k_euler_a" if "pony" in (args.model or "").lower() else "DPM++ 2M Karras",
            "karras": True, "clip_skip": 2,
        },
        "nsfw": True, "censor_nsfw": False, "trusted_workers": False,
        "r2": True, "shared": False, "slow_workers": True,
    }
    if args.seed and args.seed != "-1":
        body["params"]["seed"] = str(args.seed)
    if raw:
        body["source_image"] = base64.b64encode(raw).decode()
        body["source_processing"] = "img2img"
        body["params"]["denoising_strength"] = args.denoise

    req = urllib.request.Request(B + "/generate/async", data=json.dumps(body).encode(), headers=HDR)
    try:
        d = json.load(urllib.request.urlopen(req, timeout=90))
    except urllib.error.HTTPError as e:
        print(f"[!] submit HTTP {e.code}: {e.read().decode()[:400]}")
        return None
    jid = d.get("id")
    print(f"[+] job {jid}  model={args.model or 'auto'}  {w}x{h}  denoise={args.denoise}")
    return jid


def poll(jid, out, args):
    t0 = time.time()
    while time.time() - t0 < args.timeout:
        try:
            s = json.load(urllib.request.urlopen(f"{B}/generate/check/{jid}", timeout=40))
        except Exception as e:
            print(f"[!] check: {e}")
            time.sleep(args.poll)
            continue
        wait = s.get("wait_time", 0)
        q = s.get("queue_position", -1)
        print(f"[.] {int(time.time()-t0):>4}s  queue={q}  wait={wait}s  done={s.get('done')}")
        if s.get("done"):
            break
        if s.get("faulted"):
            print(f"[!] faulted: {s}")
            return None
        time.sleep(args.poll)
    else:
        print(f"[!] 超时 {args.timeout}s，job 仍可稍后用 --jid {jid} 取回")
        return None

    st = json.load(urllib.request.urlopen(f"{B}/generate/status/{jid}", timeout=60))
    gens = st.get("generations") or []
    if not gens:
        print(f"[!] 无产出：{json.dumps(st)[:400]}")
        return None
    g = gens[0]
    if g.get("censored"):
        print("[!] 该图被 worker 端标记 censored（换模型重试）")
    url = g.get("img")
    data = urllib.request.urlopen(url, timeout=120).read()
    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
    with open(out, "wb") as f:
        f.write(data)
    print(f"[+] {out}  {len(data)}B  seed={g.get('seed')}  model={g.get('model')}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ref", nargs="?", help="参考图（img2img）")
    ap.add_argument("out", nargs="?", help="输出路径")
    ap.add_argument("prompt", nargs="?", help="正向提示词")
    ap.add_argument("negative", nargs="?", default="", help="负面提示词")
    ap.add_argument("--list", action="store_true", help="列出可用模型")
    ap.add_argument("--model", default="WAI-ANI-NSFW-PONYXL")
    ap.add_argument("--size", default="9:16", help="9:16 / 3:4 / 832x1216")
    ap.add_argument("--denoise", type=float, default=0.7)
    ap.add_argument("--steps", type=int, default=28)
    ap.add_argument("--cfg", type=float, default=6.0)
    ap.add_argument("--seed", default=None)
    ap.add_argument("--poll", type=int, default=12)
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--jid", default=None, help="取回已有 job")
    a = ap.parse_args()

    if a.list:
        list_models()
        return
    if a.jid:
        poll(a.jid, a.out or "horde_out.webp", a)
        return
    if not (a.ref and a.out and a.prompt):
        ap.error("需要 ref / out / prompt（或用 --list）")
    jid = submit(a)
    if jid:
        poll(jid, a.out, a)


if __name__ == "__main__":
    main()
