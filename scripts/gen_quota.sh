#!/data/data/com.termux/files/usr/bin/bash
# Quota / availability probe for every image-gen engine.
#
# usage: gen_quota.sh
#
# What it actually measures:
# - anima : submits a minimum-cost job (512x704, 10 steps) and reads the ZeroGPU
#           quota error, which reports "(Ns requested vs. Ms left)". M>0 means
#           usable. Also detects the separate "runs limit" cap.
# - horde : reads /api/v2/status/performance and /status/models?type=image to
#           report worker counts and queue depth per model.
# - cf    : reads the neurons balance from the Cloudflare GraphQL API.
# - poll  : nothing to probe; documented rate only.
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

TOKEN_FILE="$HOME/.dsh/.hf-token"
TOKEN=""
[ -r "$TOKEN_FILE" ] && TOKEN=$(sed -n 's/^HF_TOKEN=//p' "$TOKEN_FILE" | tr -d '\r\n')

echo "================ anima (HuggingFace ZeroGPU) ================"
if [ -z "$TOKEN" ]; then
  echo "  [!] no HF token at $TOKEN_FILE"
else
python3 - "$TOKEN" <<'PY'
import sys, json, time, re
from curl_cffi import requests as cr
token = sys.argv[1]
H = {'Content-Type': 'application/json', 'X-HF-Authorization': f'Bearer {token}'}
spaces = [
    ("mrfakename/anima-v1-fast", ["1girl", "worst", 512, 704, 10, 5.0, 3.0, 1, True]),
    ("mrfakename/anima-v1",      ["1girl", "worst", 512, 704, 10, 5.0, 3.0, 1, True]),
    ("Menyudadas/anima-v1-fast", ["1girl", "worst", 512, 704, 10, 5.0, 3.0, 1, True]),
    ("baka999/Anima-v1-lora",    ["1girl", "worst", 512, 704, 10, 5.0, 3.0, 1, True, "", "main", "", False, 0.8]),
]
for sp, params in spaces:
    base = f'https://{sp.replace("/", "-")}.hf.space'
    try:
        r = cr.post(base + '/gradio_api/call/generate', headers=H,
                    data=json.dumps({'data': params}), impersonate='chrome120', timeout=60)
    except Exception as e:
        print(f'  {sp:<30} submit {type(e).__name__}'); continue
    if r.status_code != 200:
        print(f'  {sp:<30} submit HTTP {r.status_code}'); continue
    try:
        eid = r.json()['event_id']
    except Exception:
        print(f'  {sp:<30} no event_id: {r.text[:100]}'); continue
    t0 = time.time(); verdict = '?'
    while time.time() - t0 < 90:
        time.sleep(4)
        try:
            raw = cr.get(f'{base}/gradio_api/call/generate/{eid}', headers=H,
                         impersonate='chrome120', timeout=60).text
        except Exception:
            continue
        if raw.startswith('event: complete'):
            verdict = f'QUOTA OK (job finished {time.time()-t0:.0f}s)'; break
        if raw.startswith('event: error'):
            m = re.search(r'\((\d+)s requested vs\. (\d+)s left\)', raw)
            if m:
                req, left = int(m.group(1)), int(m.group(2))
                verdict = f'{left}s left (declared {req}s/call -> ~{left//req} images)'
            elif 'runs limit' in raw:
                verdict = 'RUNS LIMIT hit (daily run count cap)'
            else:
                verdict = raw[:120]
            break
    print(f'  {sp:<30} {verdict}')
PY
fi

echo
echo "================ horde (AI Horde) ================"
# Route through python/curl_cffi: plain curl output was fine, the heredoc
# quoting below was mangling the JSON, so do the parsing in one place.
python3 - <<'PY' 2>/dev/null || echo "  [!] AI Horde status unreachable"
import json
from curl_cffi import requests as cr
try:
    p = cr.get('https://stablehorde.net/api/v2/status/performance', impersonate='chrome120', timeout=30).json()
    print(f"  queued_requests      : {p.get('queued_requests')}")
    print(f"  worker_count (image) : {p.get('worker_count')} threads={p.get('thread_count')}")
    print(f"  past_minute MPS      : {p.get('past_minute_megapixelsteps')}")
    m = cr.get('https://stablehorde.net/api/v2/status/models?type=image', impersonate='chrome120', timeout=30).json()
    rows = sorted(m, key=lambda x: -(x.get('count') or 0))[:8]
    print("  top models by workers:")
    for x in rows:
        print(f"    {x.get('count'):>3}  {x.get('name'):<38} eta={x.get('eta')}s jobs={x.get('jobs')}")
except Exception as e:
    print(f"  [!] {type(e).__name__}: {str(e)[:100]}")
PY

echo
echo "================ cloudflare (Workers AI) ================"
CFENV="$HOME/.dsh/.cf-ai.env"
if [ -r "$CFENV" ]; then
  set -a; . "$CFENV"; set +a
  if [ -n "${CF_ACCOUNT_ID:-}" ] && [ -n "${CF_AI_TOKEN:-}" ]; then
    # The GraphQL neurons field is gone ("unknown field neurons" - verified
    # 2026-10), and aiInferenceAdaptiveGroups now rejects the filter shape too.
    # So probe by actually running one minimal image: flux-1-schnell with no
    # width/height costs the least and returns 400 5006 if params are wrong.
    TMPDIR="${TMPDIR:-/tmp}"
    mkdir -p "$TMPDIR" 2>/dev/null || TMPDIR="$HOME"
    QF=$(mktemp "$TMPDIR/cfq.XXXXXX")
    python3 - "$QF" <<'PY'
import sys, json
open(sys.argv[1], 'w').write(json.dumps({
    'prompt': 'a single grey circle on white background, minimal',
    'steps': 4,
}))
PY
    HTTP=$(curl -s -m 60 -o "$QF.out" -w '%{http_code}' -X POST \
      "https://api.cloudflare.com/client/v4/accounts/$CF_ACCOUNT_ID/ai/run/@cf/black-forest-labs/flux-1-schnell" \
      -H "Authorization: Bearer $CF_AI_TOKEN" -H 'Content-Type: application/json' \
      --data-binary "@$QF")
    python3 - "$HTTP" "$QF.out" <<'PY'
import sys, json, base64
code, path = sys.argv[1], sys.argv[2]
raw = open(path, 'rb').read()
print(f"  probe HTTP {code}")
if code == '200':
    print(f"  OK - account has quota ({len(raw)} bytes returned)")
    print("  note: ~189 neurons/image, 10k/day -> ~50 images/day")
else:
    try:
        d = json.loads(raw)
        errs = d.get('errors') or []
        msg = errs[0].get('message') if errs else raw[:150]
        print(f"  {code}: {str(msg)[:160]}")
    except Exception:
        print(f"  {code}: {raw[:160]!r}")
PY
    rm -f "$QF" "$QF.out"
  else
    echo "  [!] CF_ACCOUNT_ID / CF_AI_TOKEN not set in $CFENV"
  fi
else
  echo "  [!] no $CFENV"
fi

echo
echo "================ pollinations ================"
echo "  documented: 1 image / 45s, no key. Nothing to probe."

echo
echo "================ 2026-10 新增免费 API 源（无 key 也能探活）================"
for f in nvidia_nim_gen agnes_gen novita_gen segmind_gen together_gen; do
  echo "---- $f"
  timeout 90 python3 "$SCRIPT_DIR/$f.py" --probe 2>&1 | sed 's/^/  /'
done
echo
echo "  key 落点: ~/.dsh/.nim-key | .agnes-key | .novita-key | .segmind-key | .together-key"
