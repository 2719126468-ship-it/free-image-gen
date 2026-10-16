#!/data/data/com.termux/files/usr/bin/bash
# Client for the Anima Colab notebook (anima_colab.ipynb).
#
# The notebook runs a Flask service on port 7860 behind a cloudflared quick
# tunnel, so it is reachable without port forwarding. This script submits a
# job, polls status, and downloads the PNG.
#
# usage: colab_gen.sh "prompt" [url] [outdir] [seed] [w] [h] [steps]
#        colab_gen.sh "prompt"            # reads url from ~/.dsh/.colab-url
#
# The url file is written once per Colab session (tunnel URL changes on
# restart). Keep it updated after re-running cell 3.
set -u

PROMPT="${1:-}"
URL="${2:-}"
OUTDIR="${3:-/sdcard/Download}"
SEED="${4:-$RANDOM}"
W="${5:-832}"; H="${6:-1216}"; STEPS="${7:-25}"
URLFILE="$HOME/.dsh/.colab-url"

if [ -z "$URL" ] && [ -r "$URLFILE" ]; then
  URL=$(tr -d '\r\n' < "$URLFILE")
fi

[ -z "$PROMPT" ] && {
  cat <<EOF
usage: colab_gen.sh "prompt" [url] [outdir] [seed] [w] [h] [steps]

url: https://xxxx.trycloudflare.com  (printed by notebook cell 3)
     or stored in $URLFILE
EOF
  exit 2
}

[ -z "$URL" ] && { echo "[!] no url given and $URLFILE missing"; exit 1; }
URL="${URL%/}"

NEG='worst quality, low quality, score_1, score_2, score_3, artist name, blurry, jpeg artifacts, chromatic aberration'

echo "[*] url    : $URL"
echo "[*] size   : ${W}x${H} steps=$STEPS seed=$SEED"

# health check first: a dead tunnel is the most common failure
CODE=$(curl -s -m 20 -o /dev/null -w '%{http_code}' "$URL/health" || echo 000)
if [ "$CODE" != "200" ]; then
  echo "[!] tunnel unreachable (HTTP $CODE) - re-run notebook cell 3 and update $URLFILE"
  exit 1
fi

mkdir -p "$OUTDIR"
TMPDIR="${TMPDIR:-/tmp}"
mkdir -p "$TMPDIR" 2>/dev/null || TMPDIR="$HOME"
QF=$(mktemp "$TMPDIR/cg.XXXXXX")
python3 - "$QF" "$PROMPT" "$NEG" "$W" "$H" "$STEPS" "$SEED" <<'PY'
import sys, json
path, prompt, neg, w, h, steps, seed = sys.argv[1:8]
open(path, 'w').write(json.dumps({
    'prompt': prompt, 'negative': neg,
    'width': int(w), 'height': int(h),
    'steps': int(steps), 'seed': int(seed),
}))
PY

curl -s -m 60 -X POST "$URL/generate" -H 'Content-Type: application/json' \
  --data-binary "@$QF" -o "$QF.out"
JID=$(python3 -c 'import sys,json;print(json.load(open(sys.argv[1])).get("id",""))' "$QF.out" 2>/dev/null)
if [ -z "$JID" ]; then
  echo "[!] submit failed: $(head -c 200 "$QF.out")"
  rm -f "$QF" "$QF.out"; exit 1
fi
echo "[*] job    : $JID"

t0=$(date +%s)
while :; do
  sleep 12
  S=$(curl -s -m 30 "$URL/status/$JID")
  ST=$(echo "$S" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("status",""))' 2>/dev/null || echo "?")
  EL=$(( $(date +%s) - t0 ))
  case "$ST" in
    done)
      OUT="$OUTDIR/colab_${SEED}_${W}x${H}.png"
      curl -s -m 180 -o "$OUT" "$URL/image/$JID"
      if [ -s "$OUT" ] && [ "$(stat -c%s "$OUT")" -gt 1000 ]; then
        echo "[+] $OUT ($(stat -c%s "$OUT") bytes) in ${EL}s"
        rm -f "$QF" "$QF.out"; exit 0
      fi
      echo "[!] image download failed"; rm -f "$QF" "$QF.out"; exit 1
      ;;
    error)
      echo "[!] job error: $(echo "$S" | head -c 300)"
      rm -f "$QF" "$QF.out"; exit 1
      ;;
    *)
      if [ $(( EL % 60 )) -lt 12 ]; then echo "[.] $ST (${EL}s)"; fi
      ;;
  esac
  # Colab sessions die at 12h; a job stuck >30min means the tunnel is gone
  if [ "$EL" -gt 1800 ]; then
    echo "[!] still not done after 30min - check the Colab session is alive"
    rm -f "$QF" "$QF.out"; exit 1
  fi
done
