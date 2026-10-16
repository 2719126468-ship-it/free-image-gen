#!/data/data/com.termux/files/usr/bin/bash
# AI Horde (stablehorde.net) image generator - anonymous, unlimited, unfiltered.
#
# usage: horde_gen.sh "prompt" [outdir] [seed] [model]
#
# Verified facts:
# - Anonymous apikey "0000000000" is accepted; POST /api/v2/generate/async
#   returns {"id":..., "kudos":N}. No registration needed.
# - Quota is by kudos (negative balance still works, just lowest priority).
# - Queue is long: 512x768/20 steps took ~13 min from a residential IP with
#   ~200 requests ahead. Priority rises with a registered key.
# - NSFW models exist and run: WAI-NSFW-illustrious-SDXL, WAI-ANI-NSFW-PONYXL,
#   Pony Diffusion XL, Hentai Diffusion, Grapefruit Hentai, Nova Furry XL...
# - The /status/models?type=image nsfw field is null for every model, so NSFW
#   is not filterable via that flag - pass "nsfw":true, "censor_nsfw":false.
# - Result images are returned as presigned R2 webp URLs; download within minutes.
set -u

PROMPT="${1:-}"
OUTDIR="${2:-/sdcard/Download}"
SEED="${3:-$RANDOM}"
MODEL="${4:-WAI-NSFW-illustrious-SDXL}"

[ -z "$PROMPT" ] && {
  echo "usage: horde_gen.sh <prompt> [outdir] [seed] [model]"
  echo "  models: WAI-NSFW-illustrious-SDXL | WAI-ANI-NSFW-PONYXL | Pony Diffusion XL"
  echo "          Hentai Diffusion | Grapefruit Hentai | Dreamshaper | stable_diffusion"
  exit 2
}

W="${HORDE_W:-512}"; H="${HORDE_H:-768}"; STEPS="${HORDE_STEPS:-20}"
APIKEY="${HORDE_APIKEY:-0000000000}"
# Rotate models when a worker returns a censored blank: NSFW-capable models
# first, then SFW fallbacks so a run still produces something.
if [ -n "${HORDE_MODELS:-}" ]; then
  MODELS="$HORDE_MODELS"
else
  MODELS="$MODEL
WAI-ANI-NSFW-PONYXL
Pony Diffusion XL
Dreamshaper
stable_diffusion"
fi
MAX_TRIES="${HORDE_TRIES:-4}"
mkdir -p "$OUTDIR"

# -u: under nohup python block-buffers stdout, so progress lines never appear.
exec python3 -u - "$PROMPT" "$OUTDIR" "$SEED" "$MODELS" "$W" "$H" "$STEPS" "$APIKEY" "$MAX_TRIES" <<'PY'
import sys, json, time, os, re, subprocess
from curl_cffi import requests as cr

prompt, outdir, seed, models, w, h, steps, apikey, max_tries = sys.argv[1:10]
models = [m for m in models.splitlines() if m.strip()]
max_tries = int(max_tries)
API = 'https://stablehorde.net/api/v2'
H = {'Content-Type': 'application/json', 'apikey': apikey, 'Client-Agent': 'termux-gen:1.0:dsh'}
UA = 'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36'


def blank_png(path):
    """True if the frame is a censored/black placeholder (mean Y below 6)."""
    st = subprocess.run(['ffmpeg', '-i', path, '-vf', 'signalstats', '-f', 'null', '-'],
                        capture_output=True, text=True)
    m = re.search(r'YAVG:([0-9.]+)', st.stderr)
    return (float(m.group(1)) < 6.0) if m else False


def run_one(model, seed):
    payload = {
        'prompt': prompt,
        'params': {'width': int(w), 'height': int(h), 'steps': int(steps),
                   'cfg_scale': 7, 'sampler_name': 'k_euler', 'seed': str(seed)},
        'models': [model],
        'nsfw': True, 'censor_nsfw': False,
        'trusted_workers': False, 'slow_workers': True, 'workers': [], 'r2': True,
    }
    r = cr.post(f'{API}/generate/async', headers=H, data=json.dumps(payload),
                impersonate='chrome120', timeout=90)
    if r.status_code != 202:
        return False, None, f'submit {r.status_code} {r.text[:120]}'
    jid = r.json().get('id')
    t0 = time.time(); last = ''
    deadline = time.time() + 3600
    while time.time() < deadline:
        time.sleep(12)
        try:
            s = cr.get(f'{API}/generate/status/{jid}', headers=H,
                       impersonate='chrome120', timeout=60).json()
        except Exception as e:
            continue
        if s.get('done'):
            gens = s.get('generations') or []
            if not gens:
                return False, None, 'no generations'
            g0 = gens[0]
            url = g0.get('img')
            print(f'[+] {model}: finished {time.time()-t0:.0f}s '
                  f'(state={g0.get("state")} censored={g0.get("censored")})')
            # Presigned R2 URLs die within minutes - download right away.
            out = os.path.join(outdir, f'horde_{seed}_{w}x{h}')
            subprocess.run(['curl', '-sS', '-m', '120', '-H', f'User-Agent: {UA}',
                            '-o', out + '.webp', url])
            wp = out + '.webp'
            if not (os.path.exists(wp) and os.path.getsize(wp) > 1000):
                return False, None, 'download failed (url expired?)'
            subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', wp, out + '.png'])
            final = out + '.png'
            if os.path.exists(final) and os.path.getsize(final) > 1000:
                if blank_png(final):
                    os.remove(final); os.remove(wp)
                    return False, None, 'worker returned a censored blank frame'
                os.remove(wp)
                return True, final, None
            return False, None, 'webp->png failed'
        if s.get('faulted'):
            return False, None, 'job faulted'
        cur = f"queue={s.get('queue_position')} wait={s.get('wait_time')}s"
        if cur != last:
            print(f'[.] {model} {cur} ({time.time()-t0:.0f}s)')
            last = cur
    return False, None, 'timed out after 1h'


print(f'[*] prompt : {prompt[:100]}')
print(f'[*] size   : {w}x{h} steps={steps} seed={seed}')
for i, model in enumerate(models[:max_tries]):
    print(f'[*] trying model {i+1}/{min(len(models), max_tries)}: {model}')
    ok, path, err = run_one(model, int(seed) + i)
    if ok:
        print(f'[+] {path} ({os.path.getsize(path)} bytes)')
        sys.exit(0)
    print(f'[-] {model}: {err}')
print('[!] all models failed')
sys.exit(1)
PY
