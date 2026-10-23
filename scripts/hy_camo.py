#!/usr/bin/env python3
"""hy_camo.py — 面向带内容审核的国内闭源生图模型的图像伪装工具箱。"""
import argparse, base64, hashlib, hmac, io, json, math, os, random, re, struct, subprocess, sys, time, urllib.request
from datetime import datetime, timezone

try:
    from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps
except ImportError:
    sys.exit("需要 Pillow")

try:
    import numpy as np
except ImportError:
    sys.exit("需要 numpy")

def load(path, size=None):
    im = Image.open(path)
    return im.convert("RGB").resize(tuple(size), Image.LANCZOS) if size else im

def ensure_rgb(im):
    return im if im.mode == "RGB" else im.convert("RGB")

def arr(im):
    return np.asarray(ensure_rgb(im), dtype=np.uint8)

def from_arr(a):
    if a.dtype != np.uint8:
        a = np.clip(a, 0, 255).astype(np.uint8)
    if a.ndim == 3:
        return Image.fromarray(a, "RGBA" if a.shape[2] == 4 else "RGB")
    return Image.fromarray(a, "L")

def save(im, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    im.save(path)
    print(f" -> {path} {os.path.getsize(path)} B")
    return path

def fit(im, max_side=1024):
    w, h = im.size
    s = min(1.0, max_side / max(w, h))
    return im if s == 1.0 else im.resize((max(1, int(w * s)), max(1, int(h * s))), Image.LANCZOS)

def jpeg_bytes(im, q):
    buf = io.BytesIO()
    ensure_rgb(im).save(buf, "JPEG", quality=int(q))
    return buf.getvalue()

def from_jpeg(b):
    return Image.open(io.BytesIO(b)).convert("RGB")

def dig(obj, key):
    for k in key.split("."):
        obj = obj[int(k)] if isinstance(obj, list) else obj.get(k) if isinstance(obj, dict) else None
    return obj

class Evaluator:
    def __init__(self, args):
        self.kind = args.eval
        self.tpl = getattr(args, "eval_cmd", None) or ""
        self.url = getattr(args, "eval_url", None) or ""
        self.pass_lt = float(getattr(args, "eval_lt", 0) or 0.0)
        self.calls = 0
        self.log = []

    def check(self, path):
        self.calls += 1
        if self.kind == "none":
            return None, None
        try:
            p = subprocess.run(self.tpl.replace("{img}", os.path.abspath(path)), shell=True, capture_output=True, text=True, timeout=180)
            out = (p.stdout or "").strip()
            passed = p.returncode == 0
            score = None
            m = re.search(r"[-+]?\d*\.?\d+", out)
            if m:
                score = float(m.group())
        except Exception as e:
            print(f"[eval error] {e}", file=sys.stderr)
            return None, None
        self.log.append({"n": self.calls, "path": os.path.basename(path), "pass": bool(passed), "score": score})
        return bool(passed), score

TMPDIR = os.environ.get("TMPDIR") or os.path.expanduser("~/.hy_camo_tmp")
os.makedirs(TMPDIR, exist_ok=True)

# Subcommand implementations
def cmd_phantom(a):
    cover = fit(load(a.cover), a.max_side).convert("RGBA")
    secret = load(a.secret).convert("L").resize(cover.size, Image.LANCZOS)
    if a.invert:
        secret = ImageOps.invert(secret)
    if a.threshold:
        secret = secret.point(lambda v: 255 if v > a.threshold else 0)
    out = cover.copy()
    out.putalpha(secret)
    save(out, a.out)
    chat = ensure_rgb(out.copy()).convert("RGB")
    chat.save(a.out.replace(".png", "_chat.png"))
    dark = Image.new("RGB", out.size, (24, 26, 33))
    dark.paste(out, (0, 0), out)
    dark.save(a.out.replace(".png", "_dark.png"))
    print("[phantom] _chat.png（聊天显示） _dark.png（保存后相册合成）")

def cmd_viscrypt(a):
    """2-of-2 视觉密码：A、B 各自是纯随机噪声；A XOR B 得到二值秘密。"""
    src = fit(load(a.secret), a.max_side).convert("L")
    c = max(2, a.cell)
    gw, gh = src.width // c, src.height // c
    if gw < 1 or gh < 1:
        raise SystemExit("cell 太大")
    small = np.asarray(src.resize((gw, gh), Image.BOX), np.float32) / 255.0
    dark = (small < a.level).astype(np.uint8)          # 1 = 秘密中的黑
    rng = np.random.default_rng(a.seed)
    A = rng.integers(0, 2, size=(gh, c, gw, c)).astype(np.uint8)
    B = np.bitwise_xor(A, np.broadcast_to(dark[:, None, :, None], A.shape))
    pack = lambda x: from_arr(x.transpose(0, 1, 2, 3).reshape(gh * c, gw * c) * 255)
    Aimg, Bimg = pack(A), pack(B)
    save(Aimg, a.out_a)
    save(Bimg, a.out_b)
    side = Image.new("RGB", (Aimg.width * 2 + 8, Aimg.height), (255, 255, 255))
    side.paste(Aimg, (0, 0)); side.paste(Bimg, (Aimg.width + 8, 0))
    save(side, a.out_a.replace(".png", "_AB.png"))

    if a.recover_demo:
        # 还原：逐 cell 取 XOR，再降采样回逻辑分辨率
        Af = np.asarray(Aimg.convert("L")).reshape(gh, c, gw, c)
        Bf = np.asarray(Bimg.convert("L")).reshape(gh, c, gw, c)
        rec = (np.bitwise_xor(Af, Bf)[:, 0, :, 0] > 127).astype(np.uint8)   # 每个 cell 内所有像素同值
        rec_img = from_arr((rec * 255).astype(np.uint8)).resize((gw * 4, gh * 4), Image.NEAREST)
        save(rec_img, a.out_a.replace(".png", "_recovered.png"))
        acc = float((rec == dark).mean())
        print(f"  [viscrypt] 还原准确率 {acc*100:.2f}%（XOR 解码，100% 为无损）")
    print("  [viscrypt] 单张=纯噪声；A XOR B / 两张重叠即还原")


def cmd_dark_embed(a):
    """暗遮罩：封面压进 5-bit 高位带（加抖动掩盖色阶），秘密藏进 3-bit 低位带。
    正常看是一张略有色带噪点的封面；提亮 / 取低位即浮出秘密。"""
    cover = ensure_rgb(fit(load(a.cover), a.max_side))
    secret = load(a.secret).convert("L").resize(cover.size, Image.LANCZOS)
    if a.invert:
        secret = ImageOps.invert(secret)
    C = np.asarray(cover, np.float32)
    S = np.asarray(secret, np.float32)

    cover_bits = max(4, min(7, a.cover_bits))     # 高位带宽度
    secret_bits = 8 - cover_bits                  # 低位带留给秘密
    step = 1 << secret_bits
    top = (1 << cover_bits) - 1

    # 抖动后量化封面到高位带，避免大面积死板色阶
    rng = np.random.default_rng(a.seed)
    dith = rng.integers(0, step, C.shape, dtype=np.uint8).astype(np.float32) * a.dither
    q = np.clip((C + dith) / step, 0, top).astype(np.uint8) * step

    # 秘密量化到低位带
    s_q = np.clip(np.round(S / 255.0 * ((1 << secret_bits) - 1)), 0, (1 << secret_bits) - 1).astype(np.uint8)
    s_q = np.repeat(s_q[:, :, None], 3, axis=2)   # 灰度秘密广播到三通道
    out = np.clip(q.astype(np.int16) + s_q.astype(np.int16), 0, 255).astype(np.uint8)

    save(from_arr(out), a.out)
    print(f"  [dark] cover={cover_bits}bit secret={secret_bits}bit")
    print(f"  [dark] 还原：hy_camo.py dark-lift {a.out} -o out.png --cover-bits {cover_bits}")

def cmd_dark_lift(a):
    """从低位带取出秘密；也支持 --gamma 模式做纯提亮（适合旧式叠加暗遮罩）。"""
    im = ensure_rgb(load(a.inp))
    if a.gamma_mode:
        x = np.asarray(im, np.float32) / 255.0
        g = np.clip(x ** a.gamma * a.gain, 0, 1)
        save(from_arr((g * 255).astype(np.uint8)), a.out)
        return
    A = np.asarray(im, np.uint8)
    step = 1 << (8 - a.cover_bits)
    low = (A % step).astype(np.float32)
    rec = low / max(step - 1, 1) * 255
    rec = np.clip(rec, 0, 255).astype(np.uint8)
    if a.smooth:
        rec = np.asarray(Image.fromarray(rec).filter(ImageFilter.MedianFilter(3)))
    save(from_arr(rec), a.out)
    print(f"  [dark-lift] 从 {a.cover_bits}bit 高位的低位带还原")

def cmd_obfuscate(a):
    im = ensure_rgb(fit(load(a.inp)))
    style = a.style
    if style == "sketch":
        g = im.convert("L").filter(ImageFilter.FIND_EDGES)
        g = ImageOps.autocontrast(g.filter(ImageFilter.GaussianBlur(a.blur)))
        out = Image.merge("RGB", [g]*3) if a.invert_edges else from_arr(np.stack([g,g,g],-1))
    elif style == "blueprint":
        g = im.convert("L").filter(ImageFilter.FIND_EDGES).point(lambda v: 255 if v > 60 else 0)
        grid = Image.new("L", im.size, 0)
        d = ImageDraw.Draw(grid)
        step = a.grid
        for x in range(0, im.width, step):
            d.line([(x, 0), (x, im.height)])
        for y in range(0, im.height, step):
            d.line([(0, y), (im.width, y)])
        base = Image.new("RGB", im.size, (16, 34, 68))
        out = ImageChops.add(ImageChops.add(base, Image.merge("RGB", [grid]*3)), Image.merge("RGB", [g]*3))
    elif style == "halftone":
        c = max(2, a.cell)
        w0, h0 = im.size
        w0, h0 = (w0 // c) * c, (h0 // c) * c
        if w0 < c or h0 < c:
            raise SystemExit("halftone: 图太小")
        im2 = im.resize((w0, h0), Image.BILINEAR)
        g = np.asarray(im2.convert("L"), np.float32) / 255.0
        hh, gg = h0 // c, w0 // c
        # 每个 cell 的平均亮度 -> 点半径
        cellmean = g.reshape(hh, c, gg, c).mean(axis=(1, 3))
        radius = cellmean * (c / 2.0) * 0.95   # 亮 -> 点大；暗 -> 点小（正片网点）
        yy, xx = np.mgrid[0:c, 0:c].astype(np.float32)
        dist = np.sqrt((yy - (c - 1) / 2.0) ** 2 + (xx - (c - 1) / 2.0) ** 2)
        # 广播：dist [c,c] 对比 radius [hh,gg,1,1]
        dots = np.where(dist[None, None, :, :] <= radius[:, :, None, None], 0, 255).astype(np.uint8)
        out = Image.fromarray(dots.transpose(0, 2, 1, 3).reshape(h0, w0)).convert("RGB")
    elif style == "voxel":
        p = im.resize((max(2,im.width//a.cell),max(2,im.height//a.cell)),Image.BOX)
        p = p.resize(im.size, Image.NEAREST)
        ga = np.asarray(p.convert("L").filter(ImageFilter.FIND_EDGES),np.int16)
        ga = np.where(ga>40,200,0).astype(np.uint8)
        base = np.asarray(p,np.int16)
        edge = np.stack([ga]*3,axis=2)
        out = from_arr(np.clip(base.astype(np.int16)*1.25-edge,0,255).astype(np.uint8))
    elif style == "pixelate":
        out = im.resize((max(2,im.width//a.cell),max(2,im.height//a.cell)),Image.BOX).resize(im.size,Image.NEAREST)
    elif style == "lowres":
        t = im.resize((max(8,int(im.width*a.scale)),max(8,int(im.height*a.scale))),Image.BILINEAR)
        out = from_jpeg(jpeg_bytes(t,a.quality)).resize(im.size,Image.BILINEAR if a.smooth else Image.NEAREST)
    elif style == "edgeflow":
        g = np.asarray(im.convert("L"),np.float32)
        gy,gx=np.gradient(g)
        mag=np.clip(np.hypot(gx,gy)/40,0,1)
        ang=np.arctan2(gy,gx)
        rgb=np.stack([mag*(np.sin(ang)*.5+.5),mag*(np.cos(ang)*.5+.5),mag],-1)*255
        out=from_arr(rgb.astype(np.uint8))
    elif style == "tiles":
        c=a.cells;w,h=im.width//c,im.height//c
        idx=[(i,j) for i in range(c) for j in range(c)]
        random.Random(a.seed).shuffle(idx)
        out=Image.new("RGB",im.size)
        for (ox,oy),(sx,sy) in zip(idx,idx):
            out.paste(im.crop((sx*w,sy*h,sx*w+w,sy*h+h)),(ox*w,oy*h))
        d=ImageDraw.Draw(out)
        for i in range(1,c):
            d.line([(i*w,0),(i*w,im.height)],fill=(255,255,255),width=1)
            d.line([(0,i*h),(im.width,i*h)],fill=(255,255,255),width=1)
    else: raise SystemExit("style?")
    save(out,a.out)


def _lsb_write(flat, payload, bits):
    n_bits = len(payload) * 8
    pad = (-n_bits) % bits
    b = np.concatenate([np.unpackbits(np.frombuffer(payload, np.uint8)), np.zeros(pad, np.uint8)])
    groups = b.reshape(-1, bits)
    vals = (groups.astype(np.int64) * (1 << np.arange(bits, dtype=np.int64))).sum(1)
    mask = (1 << bits) - 1
    out = flat.astype(np.int64).copy()
    k = min(len(vals), out.size)
    out[:k] = (out[:k] & ~mask) | vals[:k]
    return out.clip(0, 255).astype(np.uint8)

def _lsb_read(flat, bits, nbytes):
    mask = (1 << bits) - 1
    need = nbytes * 8 // bits
    vals = (flat.astype(np.int64) & mask)[:need]
    groups = np.stack([((vals >> i) & 1) for i in range(bits)], axis=1).astype(np.uint8)
    return np.packbits(groups.reshape(-1), bitorder="big")

def cmd_lsb_embed(a):
    cover = ensure_rgb(fit(load(a.cover), a.max_side))
    w, h = cover.size
    cap = w * h * 3 * a.bits // 8
    raw = open(a.payload, "rb").read()
    name = os.path.basename(a.payload).encode()[:200]
    if 4 + len(name) + len(raw) > cap:
        for q in (80, 60, 45, 30, 20):
            cand = jpeg_bytes(fit(load(a.payload), 512), q)
            if 4 + 9 + len(cand) <= cap:
                raw, name = cand, b"payload.jpg"
                break
        else:
            raise SystemExit(f"payload 太大：容量 {cap}B（{w}x{h} @{a.bits}bit），提高 --bits 或换大封面")
    head = struct.pack("<HH", len(raw), len(name))
    data = head + name + raw
    flat = arr(cover).reshape(-1).copy()
    out = _lsb_write(flat, data, a.bits)
    save(from_arr(out.reshape(h, w, 3)), a.out)
    print(f"  [lsb] 写入 {len(raw)}B ({name.decode()}) bits={a.bits}")

def cmd_lsb_extract(a):
    flat = arr(load(a.inp)).reshape(-1)
    pre = _lsb_read(flat, a.bits, 4)
    ln, nn = struct.unpack("<HH", pre[:4])
    if ln == 0 or ln > 60 * 1024 * 1024 or nn > 200:
        raise SystemExit("未识别的 LSB 头（非本工具写入，或 --bits 不匹配）")
    body = _lsb_read(flat, a.bits, 4 + nn + ln)
    name = bytes(body[4:4 + nn]).decode(errors="replace")
    data = bytes(body[4 + nn:4 + nn + ln])
    out = a.out or (os.path.splitext(a.inp)[0] + "_recovered_" + (name or "payload"))
    open(out, "wb").write(data)
    print(f"  [lsb] 还原 {len(data)}B -> {out} (原名 {name})")

def cmd_channel_embed(a):
    cover = ensure_rgb(fit(load(a.cover), a.max_side))
    secret = load(a.secret).convert("L").resize(cover.size, Image.LANCZOS)
    C = arr(cover).astype(np.float32)
    C[:, :, 2] = C[:, :, 2] * (1 - a.mix) + np.asarray(secret, np.float32) * a.mix
    save(from_arr(C.astype(np.uint8)), a.out)

def cmd_channel_extract(a):
    im = arr(load(a.inp)).astype(np.float32)
    out = np.stack([im[:, :, 2]] * 3, axis=2)
    save(from_arr(np.clip(out, 0, 255).astype(np.uint8)), a.out)

def cmd_check(a):
    im = Image.open(a.inp)
    rep = {"file": a.inp, "size": im.size, "mode": im.mode, "bytes": os.path.getsize(a.inp)}
    if "A" in im.getbands():
        al = np.asarray(im.getchannel("A"), np.float32)
        rep["alpha"] = {"mean": round(float(al.mean()), 2), "std": round(float(al.std()), 2),
                        "pct_opaque": round(float((al > 200).mean()), 3),
                        "pct_transparent": round(float((al < 50).mean()), 3),
                        "payload_likely": bool(al.std() > 25)}
    rgb = arr(im).astype(np.float32)
    luma = rgb.mean(2)
    rep["luma"] = {"mean": round(float(luma.mean()), 2), "pct_dark": round(float((luma < 30).mean()), 3)}
    low = rgb.astype(np.uint8) % 4
    combined = (low[:, :, 0] | (low[:, :, 1] << 1) | (low[:, :, 2] << 2)).astype(np.uint8)
    _, cnt = np.unique(combined, return_counts=True)
    p = cnt / cnt.sum()
    rep["lsb_entropy"] = round(float(-(p * np.log2(p + 1e-12)).sum()), 3)
    rep["jpeg_note"] = "JPEG 重编码会销毁 alpha 与 LSB -> 平台压缩后只剩 RGB 层"
    print(json.dumps(rep, ensure_ascii=False, indent=2))

def cmd_probe(a):
    im = fit(load(a.inp), 512)
    def score(x):
        g = np.asarray(x.convert("RGB").resize((224, 224)), np.float32) / 255.0
        r, gg, b = g[:, :, 0], g[:, :, 1], g[:, :, 2]
        skin = ((r > .45) & (r < .98) & (gg > .25) & (gg < .85) & (b > .18) & (b < .78) &
                (r > gg) & (gg > b) & ((r - gg) > .04) & ((r - gg) < .3))
        frac = float(skin[30:194, 30:194].mean())
        lg = np.asarray(x.convert("L").resize((224, 224)), np.float32)
        eg = float(np.hypot(*np.gradient(lg)).mean()) / 255.0
        return {"skin_frac": round(frac, 4), "edge_energy": round(eg, 4),
                "proxy": round(frac + eg * 0.4, 4)}
    rows = [{"variant": "original", **score(im)}]
    for s in (0.5, 0.3, 0.15):
        t = im.resize((max(8, int(im.width * s)), max(8, int(im.height * s))), Image.BILINEAR)
        t = from_jpeg(jpeg_bytes(t, 25)).resize(im.size, Image.BILINEAR)
        rows.append({"variant": f"lowres{int(s*100)}", **score(t)})
    print(json.dumps({"baseline": rows[0], "curve": rows}, ensure_ascii=False, indent=2))
    print("\n判读：曲线骤降 -> 语义/肤色主导型审核，obfuscate 有效；几乎持平 -> 拦截在输出侧，换后端。")

SPACE = {
    "scale": (0.25, 1.0, "log"),
    "blur": (0.0, 1.6, "lin"),
    "jpeg": (12, 88, "lin"),
    "noise": (0, 40, "lin"),
    "posterize": (2, 16, "lin"),
    "contrast": (0.4, 1.5, "lin"),
    "sat": (0.0, 1.2, "lin"),
    "hue": (0.0, 1.0, "lin"),
    "edge_alpha": (0.0, 0.9, "lin"),
    "pad": (0.0, 0.35, "lin"),
    "rot": (-12, 12, "lin"),
}

def rand_params(space, rng, base=None):
    p = dict(base or {})
    for k, (lo, hi, kind) in space.items():
        if base is None or rng.random() < 0.6:
            if kind == "bool":
                p[k] = int(rng.random() < 0.5)
            elif kind == "log":
                p[k] = float(math.exp(rng.uniform(math.log(lo), math.log(hi))))
            else:
                p[k] = float(rng.uniform(lo, hi))
    p["seed"] = rng.randint(0, 2**30)
    return p

def transform(im, p):
    w, h = im.size
    out = ensure_rgb(im).copy()
    if abs(p.get("rot", 0)) > 0.5:
        out = out.rotate(p["rot"], resample=Image.BILINEAR, expand=True, fillcolor=(240, 240, 242))
    sw = max(8, int(out.width * p.get("scale", 1.0)))
    sh = max(8, int(out.height * p.get("scale", 1.0)))
    out = out.resize((sw, sh), Image.BILINEAR)
    if p.get("blur", 0) > 0.05:
        out = out.filter(ImageFilter.GaussianBlur(p["blur"]))
    if p.get("posterize", 16) < 15:
        out = ImageOps.posterize(out, max(1, min(8, int(round(math.log2(max(p["posterize"], 2)))))))
    if p.get("edge_alpha", 0) > 0.02:
        e = ImageOps.autocontrast(out.convert("L").filter(ImageFilter.FIND_EDGES))
        out = Image.blend(out, Image.merge("RGB", [e] * 3), p["edge_alpha"])
    if abs(p.get("contrast", 1) - 1) > 0.02:
        out = ImageEnhance.Contrast(out).enhance(p["contrast"])
    if abs(p.get("sat", 1) - 1) > 0.02:
        out = ImageEnhance.Color(out).enhance(p["sat"])
    if p.get("hue", 0) > 0.01:
        hsv = np.asarray(out.convert("HSV"), np.int16)
        hsv[:, :, 0] = (hsv[:, :, 0] + int(p["hue"] * 255)) % 256
        out = Image.fromarray(hsv.astype(np.uint8), "HSV").convert("RGB")
    if p.get("noise", 0) > 0:
        rng = np.random.default_rng(int(p["seed"]))
        a = np.asarray(out, np.int16) + rng.integers(-p["noise"], p["noise"] + 1, (out.height, out.width, 3))
        out = from_arr(np.clip(a, 0, 255).astype(np.uint8))
    if p.get("pad", 0) > 0.01:
        pw, ph = int(out.width * p["pad"]), int(out.height * p["pad"])
        canvas = Image.new("RGB", (out.width + 2 * pw, out.height + 2 * ph), (246, 246, 248))
        canvas.paste(out, (pw, ph))
        out = canvas
    return out.resize((w, h), Image.BILINEAR) if out.size != (w, h) else out

def cmd_adv(a):
    src = ensure_rgb(fit(load(a.inp), a.max_side))
    ev = Evaluator(a)
    workdir = a.workdir or (os.path.splitext(a.out)[0] + "_tmp")
    os.makedirs(workdir, exist_ok=True)
    rng = random.Random(a.seed)

    if a.eval == "none":
        p = rand_params(SPACE, rng)
        p.update({"scale": a.scale, "blur": a.blur, "jpeg": a.jpeg, "noise": a.noise,
                  "posterize": a.posterize, "edge_alpha": a.edge, "pad": a.pad,
                  "contrast": a.contrast, "sat": a.sat, "hue": a.hue, "rot": 0})
        out = transform(src, p)
        if a.jpeg < 95:
            out = from_jpeg(jpeg_bytes(out, p["jpeg"]))
        save(out, a.out)
        print("  [adv] --eval none：单次套用参数。接 --eval cmd/http 才进入搜索。")
        return

    # 起点：原图是否已过审
    clean = os.path.join(workdir, "clean.png")
    save(src, clean)
    ok, sc = ev.check(clean)
    print(f"  [adv] clean -> pass={ok} score={sc}")
    if ok:
        save(src, a.out)
        return

    best = None
    trials = 0
    while trials < a.max_evals:
        p = rand_params(SPACE, rng, best[0] if best else None)
        cand = transform(src, p)
        if p["jpeg"] < 90:
            cand = from_jpeg(jpeg_bytes(cand, p["jpeg"]))
        path = os.path.join(workdir, f"t{trials:03d}.png")
        cand.save(path)
        trials += 1
        ok, sc = ev.check(path)
        if ok is None:
            print("  [adv] 评估器不可用，退出")
            break
        cost = float(np.abs(np.asarray(cand, np.float32) - np.asarray(src, np.float32)).mean())
        if ok:
            if best is None or cost < best[1]:
                best = (p, cost, cand)
                print(f"  [adv] #{trials} PASS cost={cost:.1f} score={sc} (keep)")
        else:
            print(f"  [adv] #{trials} BLOCK score={sc} cost={cost:.1f}")
    if best:
        save(best[2], a.out)
        json.dump({"params": {k: (round(v, 4) if isinstance(v, float) else v) for k, v in best[0].items()},
                   "evals": ev.log}, open(a.out + ".params.json", "w"), ensure_ascii=False, indent=1)
        print(f"  [adv] 过审变体 -> {a.out}（参数见 .params.json）")
    else:
        print("  [adv] 未找到过审变体：拦截很可能来自输出侧 -> 换无审查后端，或走 ladder 递进路线。")

def cmd_prompts(a):
    md=["# 提示词侧改写（混元/国内闭源）","## 风格框定示例", "1. 学院派人体习作 figure study", "2. 古典油画人体", "3. 角色设定白模", "4. 解剖图谱插画"]
    txt="\n".join(md);open(a.outdir+"/prompts.md","w").write(txt); print(txt)

def main():
    ap=argparse.ArgumentParser(description=__doc__);sub=ap.add_subparsers(dest="cmd",required=True)
    
    p=sub.add_parser("phantom"); p.add_argument("--cover", required=True); p.add_argument("--secret", required=True); p.add_argument("--out", required=True); p.add_argument("--threshold",type=float,default=0); p.add_argument("--invert",action="store_true"); p.set_defaults(fn=cmd_phantom); p.add_argument("--seed", type=int, default=7); p.add_argument("--max-side", type=int, default=1024)
    
    p=sub.add_parser("viscrypt"); p.add_argument("--secret", required=True); p.add_argument("--out-a", required=True); p.add_argument("--out-b", required=True); p.add_argument("--cell", type=int, default=6); p.add_argument("--level", type=float, default=0.55); p.add_argument("--recover-demo", action="store_true", default=True); p.set_defaults(fn=cmd_viscrypt); p.add_argument("--seed", type=int, default=7); p.add_argument("--max-side", type=int, default=1024)
    
    p=sub.add_parser("dark-embed"); p.add_argument("--cover", required=True); p.add_argument("--secret", required=True); p.add_argument("--out", required=True); p.add_argument("--cover-bits", type=int, default=5); p.add_argument("--dither", type=float, default=0.6); p.add_argument("--invert",action="store_true"); p.set_defaults(fn=cmd_dark_embed); p.add_argument("--seed", type=int, default=7); p.add_argument("--max-side", type=int, default=1024)
    
    p=sub.add_parser("dark-lift"); p.add_argument("inp"); p.add_argument("-o", "--out", required=True); p.add_argument("--cover-bits", type=int, default=5); p.add_argument("--smooth", action="store_true", default=True); p.add_argument("--gamma-mode", action="store_true"); p.add_argument("--gamma", type=float, default=3.0); p.add_argument("--gain", type=float, default=1.0); p.set_defaults(fn=cmd_dark_lift); p.add_argument("--seed", type=int, default=7); p.add_argument("--max-side", type=int, default=1024)
    
    p=sub.add_parser("obfuscate"); p.add_argument("inp"); p.add_argument("--out", required=True); p.add_argument("--style", required=True, choices=["sketch", "blueprint", "halftone", "voxel", "pixelate", "lowres", "edgeflow", "tiles"]); p.add_argument("--seed", type=int, default=7); p.add_argument("--max-side", type=int, default=1024); p.set_defaults(fn=cmd_obfuscate); p.add_argument("--blur", type=float, default=0.4); p.add_argument("--grid", type=int, default=32); p.add_argument("--scale", type=float, default=0.25); p.add_argument("--quality", type=int, default=22); p.add_argument("--smooth", action="store_true", default=True); p.add_argument("--invert-edges", action="store_true", default=True); p.add_argument("--cell", type=int, default=10); p.add_argument("--cells", type=int, default=3)
    
    p=sub.add_parser("lsb-embed"); p.add_argument("--cover", required=True); p.add_argument("--payload", required=True); p.add_argument("--out", required=True); p.add_argument("--bits", type=int, default=2); p.set_defaults(fn=cmd_lsb_embed); p.add_argument("--seed", type=int, default=7); p.add_argument("--max-side", type=int, default=1024)
    
    p=sub.add_parser("lsb-extract"); p.add_argument("inp"); p.add_argument("-o", "--out", default=None); p.add_argument("--bits", type=int, default=2); p.set_defaults(fn=cmd_lsb_extract)
    
    p=sub.add_parser("channel-embed"); p.add_argument("--cover", required=True); p.add_argument("--secret", required=True); p.add_argument("--out", required=True); p.add_argument("--mix", type=float, default=0.5); p.set_defaults(fn=cmd_channel_embed); p.add_argument("--seed", type=int, default=7); p.add_argument("--max-side", type=int, default=1024)
    
    p=sub.add_parser("channel-extract"); p.add_argument("inp"); p.add_argument("-o", "--out", required=True); p.set_defaults(fn=cmd_channel_extract)
    
    p=sub.add_parser("check"); p.add_argument("inp"); p.set_defaults(fn=cmd_check)
    
    p=sub.add_parser("probe"); p.add_argument("inp"); p.set_defaults(fn=cmd_probe)
    
    p=sub.add_parser("adv"); p.add_argument("inp"); p.add_argument("--out", required=True); p.add_argument("--eval", default="none", choices=["none", "cmd", "http"]); p.add_argument("--eval-cmd"); p.add_argument("--eval-url"); p.add_argument("--eval-lt", type=float); p.add_argument("--workdir", default=""); p.add_argument("--max-evals", type=int, default=8); p.set_defaults(fn=cmd_adv); p.add_argument("--scale", type=float, default=0.5); p.add_argument("--blur", type=float, default=0.6); p.add_argument("--jpeg", type=int, default=40); p.add_argument("--noise", type=int, default=12); p.add_argument("--posterize", type=int, default=8); p.add_argument("--edge", type=float, default=0.2); p.add_argument("--pad", type=float, default=0.1); p.add_argument("--contrast", type=float, default=1.0); p.add_argument("--sat", type=float, default=1.0); p.add_argument("--hue", type=float, default=0.0); p.add_argument("--seed", type=int, default=7); p.add_argument("--max-side", type=int, default=1024)
    
    p=sub.add_parser("prompts"); p.add_argument("--outdir", required=True); p.set_defaults(fn=cmd_prompts)
    
    a=ap.parse_args(); cmds={"phantom":cmd_phantom,"viscrypt":cmd_viscrypt,"dark-embed":cmd_dark_embed,"dark-lift":cmd_dark_lift,"obfuscate":cmd_obfuscate,"adv":cmd_adv,"prompts":cmd_prompts,"lsb-embed":cmd_lsb_embed,"lsb-extract":cmd_lsb_extract,"channel-embed":cmd_channel_embed,"channel-extract":cmd_channel_extract,"check":cmd_check,"probe":cmd_probe}; 
    if a.cmd in cmds: cmds[a.cmd](a)
    else: print("Unknown cmd:", a.cmd); sys.exit(1)

if __name__ == "__main__":
    main()
