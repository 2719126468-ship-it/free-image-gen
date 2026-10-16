#!/data/data/com.termux/files/usr/bin/bash
# Unified free-tier image generation scheduler.
#
# Routes (tried in order of quality, first one with remaining quota wins):
#   anima  - HuggingFace ZeroGPU, Anima-2.9B + optional LoRA. 5 min GPU/day free
#            (PRO 40 min). Best quality, no NSFW filter. ~45s GPU per 832x1216/25.
#   horde  - AI Horde (stablehorde.net), anonymous apikey 0000000000, unlimited
#            runs, no NSFW filter, but 10-20 min queue. SDXL anime models.
#   cf     - Cloudflare Workers AI, 10k neurons/day (~50 images), fast (5-15s),
#            HAS NSFW prompt filter. No general img2img.
#   poll   - Pollinations, 1 image / 45 s, low quality (sana), NSFW toggle.
#
# usage: gen.sh "prompt" [outdir] [seed] [engine]
#   engine: auto (default) | anima | horde | cf | poll | list
#
# Authoritative facts behind this script:
# - ZeroGPU quota is ACCOUNT-LEVEL and shared across every Space (verified: after
#   exhausting mrfakename/anima-v1-fast, Menyudadas/anima-v1-fast reported
#   "45s requested vs. 0s left"). Switching Spaces does NOT add quota.
# - ZeroGPU deducts the DECLARED duration, not actual runtime; a run that takes
#   12s still costs 45s if the decorator declared duration=45.
# - Anima on the -fast spaces declares 45s per call -> 300s/day / 45s = 6-7 images.
# - Two distinct limiters exist: "ZeroGPU quota exceeded" (seconds) and
#   "ZeroGPU runs limit" (run count). Both are hit at the daily ceiling.
# - gradio_client rewrites Authorization -> X-HF-Authorization; that header is
#   required for logged-in (rather than anonymous) quota.
set -u

PROMPT="${1:-}"
OUTDIR="${2:-/sdcard/Download}"
SEED="${3:-$RANDOM}"
ENGINE="${4:-auto}"

[ -z "$PROMPT" ] && {
  cat <<'EOF'
usage: gen.sh "prompt" [outdir] [seed] [engine]

engine:
  auto   pick the best engine that still has quota (default)
  anima  HuggingFace ZeroGPU Anima-2.9B - best quality, 5 min GPU/day
  horde  AI Horde SDXL - unlimited, slow (10-20 min), no filter
  cf     Cloudflare Workers AI - fast, ~50/day, HAS NSFW filter
  poll   Pollinations - 1 image/45s, lowest quality
  list   show quota status of every engine and exit
EOF
  exit 2
}

# Resolve sibling scripts from this file's own directory so the repo works
# from any checkout location, not just ~/dsh-hanime1.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$OUTDIR" "$WORK" || true

case "$ENGINE" in
  list) exec "$SCRIPT_DIR/gen_quota.sh" ;;
esac

run_anima() {
  local sp="${ANIMA_SPACE:-mrfakename/anima-v1-fast}"
  local model lora lstr w h steps
  w="${GEN_W:-832}"; h="${GEN_H:-1216}"; steps="${GEN_STEPS:-25}"
  lora="${GEN_LORA:-real_skin.safetensors}"
  lstr="${GEN_LORA_STR:-0.7}"
  [ "$lora" = "-" ] && lora=""
  if [ -n "${ANIMA_MODEL:-}" ]; then model="$ANIMA_MODEL"; else model=""; fi
  GEN_W="$w" GEN_H="$h" GEN_STEPS="$steps" GEN_LORA="$lora" GEN_LORA_STR="$lstr" \
  ANIMA_SPACE="$sp" ANIMA_MODEL="$model" \
    "$SCRIPT_DIR/anima_gen.sh" "$PROMPT" "$OUTDIR" "$SEED" "$w" "$h" "$steps" "$lora" "$lstr" 2>&1
}

run_horde() {
  "$SCRIPT_DIR/horde_gen.sh" "$PROMPT" "$OUTDIR" "$SEED" "${HORDE_MODEL:-WAI-NSFW-illustrious-SDXL}" 2>&1
}

run_cf() {
  # gen_image.sh: prompt [outdir] [w] [h] [seed] [engine] [model]
  "$SCRIPT_DIR/gen_image.sh" "$PROMPT" "$OUTDIR" \
    "${GEN_W:-1024}" "${GEN_H:-1024}" "$SEED" cf 2>&1
}

run_poll() {
  "$SCRIPT_DIR/gen_image.sh" "$PROMPT" "$OUTDIR" \
    "${GEN_W:-768}" "${GEN_H:-1024}" "$SEED" pollinations 2>&1
}

# Order matters: quality first, but never waste a run on a dead engine.
if [ "$ENGINE" = "auto" ]; then
  echo "[*] probing engines for remaining quota..."
  # Anima first: 1-10s response when quota remains, instant quota error otherwise.
  if out=$(ANIMA_SPACE="${ANIMA_SPACE:-mrfakename/anima-v1-fast}" \
           GEN_W=512 GEN_H=704 GEN_STEPS=12 \
           run_anima 2>&1); then
    echo "[+] anima: quota available, running full-size job"
    run_anima
    exit $?
  else
    echo "$out" | grep -qiE 'quota|runs limit' \
      && echo "[-] anima: daily quota exhausted" \
      || echo "[-] anima: $out"
  fi

  echo "[*] anima exhausted -> horde (unlimited, slow)"
  if run_horde; then exit 0; fi

  echo "[*] horde failed -> cloudflare (has NSFW filter)"
  if run_cf; then exit 0; fi

  echo "[*] cloudflare failed -> pollinations"
  run_poll
  exit $?
fi

case "$ENGINE" in
  anima) run_anima ;;
  horde) run_horde ;;
  cf)    run_cf ;;
  poll)  run_poll ;;
  *) echo "[!] unknown engine: $ENGINE"; exit 2 ;;
esac
