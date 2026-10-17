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
# API key resolution. Default stays ANONYMOUS: a fresh key has kudos=0 and gets
# no priority (verified A/B), and submitting with it drains the account to NEGATIVE
# kudos, which is WORSE than anonymous. Only set HORDE_USE_KEY=1 once the account
# has positive kudos (check: curl -H "apikey: $KEY" https://stablehorde.net/api/v2/find_user).
if [ "${HORDE_USE_KEY:-0}" = "1" ] && [ -f "$HOME/.dsh/.horde-key" ]; then
  APIKEY="$(sed -n 's/^HORDE_API_KEY=//p' "$HOME/.dsh/.horde-key" | head -1)"
  APIKEY="${APIKEY:-0000000000}"
else
  APIKEY="${HORDE_APIKEY:-0000000000}"
fi
# Rotate models when a worker returns a censored blank: NSFW-capable models
# Preference pool. Order here is only a quality tie-breaker - the script
# re-sorts by LIVE eta before submitting, because queue depth swings wildly
# (Illustrious went from 97s eta to 81 queued jobs within minutes, while
# PONYXL/Dreamshaper sat at eta=0s the whole time).
if [ -n "${HORDE_MODELS:-}" ]; then
  MODELS="$HORDE_MODELS"
  AUTO_ETA=0
else
  MODELS="$MODEL
WAI-ANI-NSFW-PONYXL
CyberRealistic Pony
Dreamshaper
Grapefruit Hentai
Hentai Diffusion
Pony Diffusion XL
SwamPonyXL
AbsoluteReality
Nova Anime XL
AlbedoBase XL (SDXL)
WAI-NSFW-illustrious-SDXL"
  AUTO_ETA=1
fi
MAX_TRIES="${HORDE_TRIES:-4}"
mkdir -p "$OUTDIR"

# -u: under nohup python block-buffers stdout, so progress lines never appear.
exec python3 -u - "$PROMPT" "$OUTDIR" "$SEED" "$MODELS" "$W" "$H" "$STEPS" "$APIKEY" "$MAX_TRIES" "$AUTO_ETA" <<'PY'
import sys, json, time, os, re, subprocess
from curl_cffi import requests as cr

prompt, outdir, seed, models, w, h, steps, apikey, max_tries, auto_eta = sys.argv[1:11]
models = [m.strip() for m in models.splitlines() if m.strip()]
max_tries = int(max_tries)
auto_eta = auto_eta == '1'
API = 'https://stablehorde.net/api/v2'
H = {'Content-Type': 'application/json', 'apikey': apikey, 'Client-Agent': 'termux-gen:1.0:dsh'}


def rank_by_eta(names):
    """Sort candidate models by live backlog, least-loaded first.

    /status/models?type=image reports per-model:
      eta     - seconds for ONE job to finish (ignores queue depth)
      queued  - megapixelsteps of backlog for that model
      jobs    - number of queued jobs
      count   - workers offering the model

    eta alone is misleading: PONYXL reported eta=0 while sitting behind 136
    queued requests. 'queued' is the real signal - 0 means idle, 31457280
    means a deep backlog. Tie-break on more workers, then original order.
    """
    try:
        st = cr.get(f'{API}/status/models?type=image', headers=H,
                    impersonate='chrome120', timeout=30).json()
    except Exception:
        return names
    by = {m.get('name'): m for m in st}
    rows = []
    for i, n in enumerate(names):
        m = by.get(n)
        if not m:
            continue
        rows.append(((m.get('queued') or 0), -(m.get('count') or 0), i, n))
    rows.sort()
    ranked = [r[3] for r in rows]
    missing = [n for n in names if n not in ranked]
    return ranked + missing


if auto_eta:
    models = rank_by_eta(models)
    print('[*] models re-sorted by live backlog:')
    for m in models[:6]:
        print(f'      {m}')


def blank_png(path):
    """True if the frame is a censored/black placeholder (mean Y below 6)."""
    st = subprocess.run(['ffmpeg', '-i', path, '-vf', 'signalstats', '-f', 'null', '-'],
                        capture_output=True, text=True)
    m = re.search(r'YAVG:([0-9.]+)', st.stderr)
    return (float(m.group(1)) < 6.0) if m else False


def download_image(url, path, tries=4):
    """Download a presigned R2 URL with retries.

    The URL is NOT reliably short-lived: one job was fetched successfully
    minutes after completion. The earlier 'download failed (url expired?)'
    was a transient network failure mislabelled as expiry, so retry and
    report the real HTTP status instead of guessing.
    """
    for attempt in range(tries):
        try:
            r = cr.get(url, impersonate='chrome120', timeout=120)
            if r.status_code == 200 and len(r.content) > 1000:
                open(path, 'wb').write(r.content)
                return True, None
            # R2 returns an XML error body with the real reason
            body = r.content[:200].decode('utf-8', 'replace')
            err = f'HTTP {r.status_code}: {body[:120]}'
        except Exception as e:
            err = f'{type(e).__name__}: {str(e)[:120]}'
        print(f'[-] download attempt {attempt + 1}/{tries} failed: {err}')
        time.sleep(3)
    return False, err


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
            # Grab the image in this same process, right after detecting done,
            # so there is no extra poll cycle between detection and download.
            out = os.path.join(outdir, f'horde_{seed}_{w}x{h}')
            ok, err = download_image(url, out + '.webp')
            if not ok:
                return False, None, f'download failed: {err}'
            subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', out + '.webp', out + '.png'])
            final = out + '.png'
            if os.path.exists(final) and os.path.getsize(final) > 1000:
                if blank_png(final):
                    os.remove(final); os.remove(out + '.webp')
                    return False, None, 'worker returned a censored blank frame'
                os.remove(out + '.webp')
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
