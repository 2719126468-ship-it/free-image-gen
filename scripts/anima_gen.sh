#!/data/data/com.termux/files/usr/bin/bash
# Anima (日系二次元写实) generator via HuggingFace ZeroGPU Spaces.
#
# usage: anima_gen.sh "prompt" [outdir] [seed] [w] [h] [steps] [lora] [lora_str]
#        ANIMA_SPACE=mrfakename/anima-v1-fast anima_gen.sh ...
#
# Spaces (all verified working, all Anima-2.9B-preview, all declare 45s/call):
#   mrfakename/anima-v1-fast  9 params, webp out, 1-10s
#   Menyudadas/anima-v1-fast  9 params, png out
#   mrfakename/anima-v1       9 params (same schema as -fast)
#   baka999/Anima-v1-lora     13 params, adds lora_repo/lora_file/use_lora/strength
#
# Auth : X-HF-Authorization: Bearer <HF_TOKEN>  (gradio_client's own header;
#        x-api-key and Authorization are both ignored by ZeroGPU quota).
#
# Quota: ACCOUNT-LEVEL, shared across all Spaces. Verified 2025-10: after using
#        mrfakename/anima-v1-fast to exhaustion, Menyudadas/anima-v1-fast returned
#        "You have exceeded your free ZeroGPU quota (45s requested vs. 0s left)".
#        Free = 300s/day -> 6-7 images at 832x1216/25 steps.
set -u

PROMPT="${1:-}"
OUTDIR="${2:-/sdcard/Download}"
SEED="${3:-$RANDOM}"
W="${4:-832}"; H="${5:-1216}"
STEPS="${6:-25}"
LORA="${7:-real_skin.safetensors}"
LORA_STR="${8:-0.7}"
MODEL="${ANIMA_MODEL:-}"
SPACE="${ANIMA_SPACE:-mrfakename/anima-v1-fast}"

[ -z "$PROMPT" ] && {
  echo "usage: anima_gen.sh <prompt> [outdir] [seed] [w] [h] [steps] [lora] [lora_str]"
  echo "  env: ANIMA_SPACE (default mrfakename/anima-v1-fast)"
  echo "       ANIMA_MODEL (default: whatever the Space ships)"
  echo "  loras (baka999 space): real_skin | - for none"
  exit 2
}

TOKEN_FILE="$HOME/.dsh/.hf-token"
[ -r "$TOKEN_FILE" ] || { echo "[!] missing $TOKEN_FILE"; exit 1; }
TOKEN=$(sed -n 's/^HF_TOKEN=//p' "$TOKEN_FILE" | tr -d '\r\n')
[ -n "$TOKEN" ] || { echo "[!] HF_TOKEN empty in $TOKEN_FILE"; exit 1; }

mkdir -p "$OUTDIR"
exec python3 -u - "$PROMPT" "$OUTDIR" "$SEED" "$W" "$H" "$STEPS" "$LORA" "$LORA_STR" "$MODEL" "$TOKEN" "$SPACE" <<'PY'
import sys, json, time, re, os, subprocess
from curl_cffi import requests as cr

prompt, outdir, seed, w, h, steps, lora, lora_str, model, token, space = sys.argv[1:12]
SPACE_HOST = space.replace('/', '-')
BASE = f'https://{SPACE_HOST}.hf.space'
H = {'Content-Type': 'application/json',
     'X-HF-Authorization': f'Bearer {token}'}
UA = ('Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36')

# Anima reads both Danbooru tags and natural language; this pair is the
# space-recommended quality prefix/suffix.
POS_PREFIX = 'masterpiece, best quality, score_7, safe, '
NEG = ('worst quality, low quality, score_1, score_2, score_3, '
       'artist name, blurry, jpeg artifacts, chromatic aberration')
full_prompt = prompt if prompt.startswith('masterpiece') else POS_PREFIX + prompt

# 13-param schema (baka999/Anima-v1-lora) needs LoRA fields; 9-param spaces
# take prompt/neg/w/h/steps/cfg/sigma_shift/seed/prefix only.
if 'lora' in space:
    data = [full_prompt, NEG, float(w), float(h), int(steps), 5.0, 3.0, int(seed), True,
            '', 'main', '', False, 0.8]
    if lora and lora != '-':
        data[9:13] = ['ptrgu/real_skin', 'main', 'real_skin.safetensors', True, float(lora_str)]
        data = data[:9] + data[9:13]
else:
    data = [full_prompt, NEG, float(w), float(h), int(steps), 5.0, 3.0, int(seed), True]

print(f'[*] space  : {space}')
print(f'[*] size   : {w}x{h}  steps={steps}  seed={seed}')
print(f'[*] prompt : {full_prompt[:100]}')

r = cr.post(BASE + '/gradio_api/call/generate', headers=H,
            data=json.dumps({'data': data}), impersonate='chrome120', timeout=180)
if r.status_code != 200:
    print('[!] submit failed', r.status_code, r.text[:300]); sys.exit(1)
ev = r.json().get('event_id')
if not ev:
    print('[!] no event_id:', r.text[:200]); sys.exit(1)
print(f'[*] event  : {ev}')

deadline = time.time() + 600
last = ''
while time.time() < deadline:
    time.sleep(4)
    try:
        t = cr.get(f'{BASE}/gradio_api/call/generate/{ev}', headers=H,
                   impersonate='chrome120', timeout=120).text
    except Exception as e:
        print(f'[!] poll {type(e).__name__}'); continue

    if t.startswith('event: complete'):
        d = json.loads(t.split('data: ', 1)[1])
        img = d[0][0] if isinstance(d[0], list) else d[0]
        url = img.get('url') if isinstance(img, dict) else img
        if not url:
            print('[!] no url in payload:', json.dumps(img)[:200]); sys.exit(1)
        if url.startswith('/'):
            url = BASE + url
        out = os.path.join(outdir, f'anima_{seed}_{w}x{h}.png')
        subprocess.run(['curl', '-sS', '-m', '240', '-H', f'User-Agent: {UA}', '-o', out, url])
        if os.path.exists(out) and os.path.getsize(out) > 1000:
            # gradio often returns webp; normalise to png so ffmpeg/viewers agree
            if open(out, 'rb').read(12).find(b'WEBP') != -1:
                subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', out, out + '.tmp.png'])
                if os.path.exists(out + '.tmp.png'):
                    os.replace(out + '.tmp.png', out)
            print(f'[+] {out} ({os.path.getsize(out)} bytes)')
            sys.exit(0)
        print('[!] download failed:', url[:120]); sys.exit(1)

    if t.startswith('event: error'):
        body = t[:400]
        m = re.search(r'\((\d+)s requested vs\. (\d+)s left\)', body)
        if m:
            print(f'[!] ZeroGPU quota: {m.group(1)}s requested, {m.group(2)}s left')
        elif 'runs limit' in body:
            print('[!] ZeroGPU runs limit (daily run count cap)')
        else:
            print('[!] space error:', body)
        sys.exit(1)

    cur = t.split('data:')[0][:40].strip()
    if cur and cur != last:
        print(f'[.] {cur}')
        last = cur
print('[!] timed out')
sys.exit(1)
PY
