#!/data/data/com.termux/files/usr/bin/bash
# Multi-engine image generator.
#
# usage: gen_image.sh "prompt" [outdir] [width] [height] [seed] [engine] [model]
#
# engines (default: cf):
#   cf            Cloudflare Workers AI  - 10k neurons/day free, no rate wall, ~50 imgs/day
#   pollinations  Pollinations anonymous - 1 img/45s, silently degrades to sana
#   hf            HuggingFace Space FLUX.1-schnell - no key, no filter, cold-start 20-40s
#
# models (engine cf, all verified working):
#   @cf/black-forest-labs/flux-1-schnell        (default, 4-step, fastest)
#   @cf/black-forest-labs/flux-2-dev            (highest quality, multipart body)
#   @cf/black-forest-labs/flux-2-klein-9b       (multipart body)
#   @cf/black-forest-labs/flux-2-klein-4b       (multipart body)
#   @cf/stabilityai/stable-diffusion-xl-base-1.0
#   @cf/bytedance/stable-diffusion-xl-lightning
#   @cf/leonardo/phoenix-1.0
#   @cf/leonardo/lucid-origin
#   @cf/lykon/dreamshaper-8-lcm
set -u

PROMPT="${1:-}"
OUTDIR="${2:-/sdcard/Download}"
W="${3:-1024}"; H="${4:-1024}"
SEED="${5:-$RANDOM}"
ENGINE="${6:-cf}"
MODEL="${7:-@cf/black-forest-labs/flux-1-schnell}"

[ -z "$PROMPT" ] && {
  echo "usage: gen_image.sh <prompt> [outdir] [w] [h] [seed] [engine] [model]"
  echo "  engine: cf (default) | pollinations | hf"
  exit 2
}

ENV_FILE="$HOME/.dsh/.cf-ai.env"
# `set -a` exports every assignment so the sourced values reach the node child.
set -a
[ -r "$ENV_FILE" ] && . "$ENV_FILE"
set +a
GEN="$HOME/.cf-img/gen.mjs"

mkdir -p "$OUTDIR"
SLUG=$(printf '%s' "$PROMPT" | tr -cs 'A-Za-z0-9' '-' | sed 's/^-*//;s/-*$//' | cut -c1-40)
OUT="$OUTDIR/${SLUG:-image}_${SEED}.jpg"

echo "[*] prompt : $PROMPT"
echo "[*] engine : $ENGINE"
echo "[*] output : $OUT"

verify() {
  [ -s "$OUT" ] || return 1
  python - "$OUT" <<'PY' >/dev/null 2>&1
from PIL import Image
import sys
im = Image.open(sys.argv[1])
im.load()
PY
}

report() {
  python - "$OUT" <<'PY'
from PIL import Image
import sys
im = Image.open(sys.argv[1])
print(f"    size  : {im.size[0]}x{im.size[1]} {im.format} {im.mode}")
PY
}

# ---------------------------------------------------------------- cloudflare
gen_cf() {
  local steps="${CF_STEPS:-4}"
  [ -s "$GEN" ] || { echo "[!] missing $GEN"; return 1; }
  [ -n "${CF_ACCOUNT_ID:-}" ] || { echo "[!] CF_ACCOUNT_ID unset (source $ENV_FILE)"; return 1; }
  [ -n "${CF_AI_TOKEN:-}" ] || { echo "[!] CF_AI_TOKEN unset (source $ENV_FILE)"; return 1; }
  # gen.mjs writes fixed 1024x1024 for models that accept width/height; the
  # schnell family rejects both, so W/H only apply where the model honours them.
  node "$GEN" "$MODEL" "$PROMPT" "$OUT" "$steps" 2>&1
}

# ------------------------------------------------------------- pollinations
gen_pollinations() {
  local enc wait_s attempt
  enc=$(python -c 'import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))' "$PROMPT")
  # No model= param: the anonymous tier only serves sana and silently degrades
  # any other name, so asking for flux/nanobanana/seedream yields sana anyway.
  local url="https://image.pollinations.ai/prompt/$enc?width=$W&height=$H&nologo=true&safe=false&seed=$SEED"
  for attempt in 1 2 3 4; do
    code=$(curl -sS -m 180 -o "$OUT" -w '%{http_code}' \
      -H 'User-Agent: Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/126 Mobile' \
      "$url" 2>/dev/null || echo 000)
    if [ "$code" = "200" ] && verify; then
      # EXIF Make carries the real serving model; surface a silent downgrade.
      python - "$OUT" <<'PY'
from PIL import Image
from PIL.ExifTags import TAGS
import sys
im = Image.open(sys.argv[1])
ex = im.getexif() or {}
make = ex.get(271)
if make and str(make).lower() != 'sana':
    print(f"    served-by: {make}")
PY
      return 0
    fi
    # 402 FREE_LIMIT carries an exact retry hint in its JSON body.
    wait_s=$(python - "$OUT" <<'PY' 2>/dev/null || echo 45
import json, re, sys
try:
    raw = open(sys.argv[1], 'rb').read().decode('utf-8', 'replace')
    m = re.search(r'Retry after (\d+)s', raw)
    print(int(m.group(1)) + 2 if m else 45)
except Exception:
    print(45)
PY
)
    echo "[-] attempt $attempt failed (http=$code) waiting ${wait_s}s..."
    sleep "$wait_s"
  done
  return 1
}

# ------------------------------------------------------------------ hf space
gen_hf() {
  local ev
  ev=$(curl -sS -m 240 -X POST \
    "https://black-forest-labs-flux-1-schnell.hf.space/gradio_api/call/infer" \
    -H 'Content-Type: application/json' \
    -d "{\"data\":[\"$PROMPT\",$SEED,true,$W,$H,4]}" 2>/dev/null) || return 1
  ev=$(printf '%s' "$ev" | python -c 'import json,sys;print(json.load(sys.stdin).get("event_id",""))' 2>/dev/null)
  [ -n "$ev" ] || { echo "[-] hf submit failed"; return 1; }
  # ZeroGPU cold start plus queue can exceed two minutes on a shared space.
  for _ in 1 2 3 4 5 6 7 8; do
    sleep 20
    body=$(curl -sS -m 200 \
      "https://black-forest-labs-flux-1-schnell.hf.space/gradio_api/call/infer/$ev" 2>/dev/null)
    url=$(printf '%s' "$body" | grep -o 'https://[^"]*\.webp' | head -1)
    if [ -n "$url" ]; then
      curl -sS -m 90 -o "$OUT" "$url" 2>/dev/null && verify && return 0
    fi
  done
  return 1
}

case "$ENGINE" in
  cf)          gen_cf ;;
  pollinations) gen_pollinations ;;
  hf)          gen_hf ;;
  *)           echo "[!] unknown engine '$ENGINE' (cf|pollinations|hf)"; exit 2 ;;
esac
rc=$?

if [ "$rc" = "0" ] && verify; then
  echo "[+] ok -> $OUT"
  report
  exit 0
fi
echo "[!] engine '$ENGINE' failed; try --engine pollinations or hf"
exit 1
