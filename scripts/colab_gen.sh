#!/data/data/com.termux/files/usr/bin/bash
# Client for the Anima/Wan Colab notebook (examples/anima_colab.ipynb).
#
# The notebook runs a Flask service on port 7860 behind a cloudflared quick
# tunnel, so it is reachable without port forwarding. This script submits
# jobs, polls status, and downloads results.
#
# usage:
#   colab_gen.sh "prompt"                      # single image, url from cache
#   colab_gen.sh "prompt" https://x.trycloudflare.com
#   colab_gen.sh --health                      # 查档位/GPU/队列
#   colab_gen.sh --batch prompts.txt           # 批量出图
#   colab_gen.sh --flush                       # 把产出搬进 Drive
#
# env:
#   COLAB_URL   覆盖 url（优先于位置参数与缓存文件）
#   OUTDIR      输出目录（默认 /sdcard/Download）
#
# The url file is written once per Colab session (tunnel URL changes on
# restart). Keep it updated after re-running notebook cell 4.
set -u

URLFILE="$HOME/.dsh/.colab-url"
OUTDIR="${OUTDIR:-/sdcard/Download}"
NEG='worst quality, low quality, score_1, score_2, score_3, artist name, blurry, jpeg artifacts, chromatic aberration'

# tunables (override via env)
W="${W:-832}"; H="${H:-1216}"; STEPS="${STEPS:-25}"
VW="${VW:-1280}"; VH="${VH:-704}"; VSTEPS="${VSTEPS:-50}"; FRAMES="${FRAMES:-121}"; VFPS="${VFPS:-24}"

usage() {
  cat <<EOF
usage: colab_gen.sh "prompt" [url] [outdir] [seed] [w] [h] [steps]
       colab_gen.sh --health
       colab_gen.sh --batch prompts.txt
       colab_gen.sh --video "prompt" [url] [outdir] [ref_image]
       colab_gen.sh --flush

url: https://xxxx.trycloudflare.com  (printed by notebook cell 4)
     or stored in $URLFILE

env: W H STEPS (图, 默认 832x1216/25)
     VW VH VSTEPS FRAMES VFPS (视频, 默认 1280x704/50/121帧/24fps)
     COLAB_URL OUTDIR
     CPU_PRESET  CPU 档模型: sana06(默认) | sdxl_lightning | sdxl_anime(2.06GB 动漫SDXL)
                 | animagine(6.18GB 重) | sd15_lcm(0.90GB 最快)

video: 首次会触发 Colab 端下载 Wan2.2 权重(~10-20GB)；ref_image 走图生视频(I2V)
EOF
  exit 2
}

resolve_url() {
  if [ -n "${COLAB_URL:-}" ]; then URL="$COLAB_URL"
  elif [ -n "${1:-}" ]; then URL="$1"
  elif [ -r "$URLFILE" ]; then URL=$(tr -d '\r\n' < "$URLFILE")
  else URL=""; fi
  URL="${URL%/}"
}

require_url() {
  [ -z "$URL" ] && { echo "[!] no url: pass one, set COLAB_URL, or write $URLFILE"; exit 1; }
}

# Termux/Android 上 /tmp 可能不存在，健康检查的临时文件必须落在可写目录
HEALTH_TMP="${TMPDIR:-$HOME}/.cghealth"
[ -d "$(dirname "$HEALTH_TMP")" ] || HEALTH_TMP="$HOME/.cghealth"

# health check: dead tunnel and CPU-only sessions are the two common traps
check() {
  local code
  code=$(curl -s -m 25 -o "$HEALTH_TMP" -w '%{http_code}' "$URL/health" 2>/dev/null)
  [ -z "$code" ] && code=000
  if [ "$code" != "200" ]; then
    echo "[!] tunnel unreachable (HTTP $code) - re-run notebook cell 4, update $URLFILE"
    return 1
  fi
  return 0
}

show_health() {
  require_url
  check || exit 1
  python3 - "$HEALTH_TMP" "$URL" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
gpu = d.get('gpu')
presets = '/'.join(d.get('cpu_presets', [])) or 'sana06/sdxl_lightning/sdxl_anime/animagine/sd15_lcm'
if gpu:
    print(f"档位    : GPU - {d.get('gpu_name')} {d.get('vram_gb')}GB")
else:
    print(f"档位    : CPU 档（OpenVINO 蒸馏，当前预设 {d.get('cpu_preset', '?')}"
          f" 权重 {d.get('cpu_weight_gb', '?')}GB，可用内存 {d.get('ram_free_gb', '?')}GB；可切 {presets}）")
print(f"url     : {sys.argv[2]}")
print(f"队列    : {d.get('pending', d.get('queue', '?'))} 待处理 · 已建任务 {d.get('jobs', 0)} 个")
print(f"视频模型: {'已加载' if d.get('video_loaded') else '未加载（首次请求视频时才下 ~10-20GB）'}")
print(f"输出目录: {d.get('out')}")
if d.get('cpu_error'):
    print(f"CPU 模型错误: {d.get('cpu_error')}")
if d.get('video_error'):
    print(f"视频错误: {d.get('video_error')}")
if not gpu:
    print("\n提示: CPU 档预设（权重体积为 HF repo 实测）：")
    print("      sd15_lcm 0.90GB  SD1.5 LCM 8步  ≤512px  2vCPU 约 2-5 分钟/张（最快，画质矮）")
    print("      sdxl_lightning 2.06GB SDXL 4步 cfg2.0 ≤768px 约 8-20 分钟/张（通用写实）")
    print("      sdxl_anime 2.06GB SDXL-LCM 8步 cfg1.5 ≤1024px 约 15-30 分钟/张（动漫，你要的 2.7GB 那档）")
    print("      sana06 2.45GB SANA 0.6B 4步 ≤1024px 写实最强（默认）")
    print("      animagine 6.18GB SDXL 4步 guidance0 ≤1024px（repo 名 INT4 实为 INT8+FP32，2vCPU 易触发内存闸门）")
    print("      切档: CPU_PRESET=<key>，或改 notebook 第4格 CPU_PRESET；内存不足服务端会直接报错。")
PY
}

# ---------- 单张 ----------
single() {
  local PROMPT="$1" URL="$2" OUTDIR="$3" SEED="$4" W="$5" H="$6" STEPS="$7"
  echo "[*] url  : $URL"
  echo "[*] size : ${W}x${H} steps=$STEPS seed=$SEED"
  check || exit 1

  mkdir -p "$OUTDIR"
  local TMPD="${TMPDIR:-$HOME}"
  mkdir -p "$TMPD" 2>/dev/null || TMPD="$HOME"
  local QF; QF=$(mktemp "$TMPD/cg.XXXXXX")

  python3 - "$QF" "$PROMPT" "$NEG" "$W" "$H" "$STEPS" "$SEED" "${CPU_PRESET:-}" <<'PY'
import sys, json
path, prompt, neg, w, h, steps, seed, preset = sys.argv[1:9]
d = {'prompt': prompt, 'negative': neg,
     'width': int(w), 'height': int(h),
     'steps': int(steps), 'seed': int(seed)}
if preset: d['cpu_preset'] = preset
open(path, 'w').write(json.dumps(d))
PY

  curl -s -m 60 -X POST "$URL/generate" -H 'Content-Type: application/json' \
    --data-binary "@$QF" -o "$QF.out"
  local JID
  JID=$(python3 -c 'import sys,json;print(json.load(open(sys.argv[1])).get("id",""))' "$QF.out" 2>/dev/null)
  if [ -z "$JID" ]; then
    echo "[!] submit failed: $(head -c 200 "$QF.out")"; rm -f "$QF" "$QF.out"; exit 1
  fi
  echo "[*] job  : $JID"

  local t0; t0=$(date +%s)
  while :; do
    sleep 10
    local S ST EL
    S=$(curl -s -m 30 "$URL/status/$JID")
    ST=$(echo "$S" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("status",""))' 2>/dev/null || echo "?")
    EL=$(( $(date +%s) - t0 ))
    case "$ST" in
      done)
        local OUT="$OUTDIR/colab_${SEED}_${W}x${H}.png"
        curl -s -m 180 -o "$OUT" "$URL/image/$JID"
        if [ -s "$OUT" ] && [ "$(stat -c%s "$OUT")" -gt 1000 ]; then
          echo "[+] $OUT ($(stat -c%s "$OUT") bytes) in ${EL}s"
          if [ "$EL" -gt 120 ]; then
            echo "[i] 耗时 >120s：可能已掉到 CPU 档，检查 --health"
          fi
          rm -f "$QF" "$QF.out"; exit 0
        fi
        echo "[!] image download failed"; rm -f "$QF" "$QF.out"; exit 1
        ;;
      error)
        echo "[!] job error: $(echo "$S" | head -c 300)"; rm -f "$QF" "$QF.out"; exit 1
        ;;
      *)
        if [ $(( EL % 60 )) -lt 10 ]; then echo "[.] $ST (${EL}s)"; fi
        ;;
    esac
    # 免费档会话 3.5-6h；单张卡 30 分钟说明隧道断了
    if [ "$EL" -gt 1800 ]; then
      echo "[!] still not done after 30min - check the Colab session is alive"
      echo "    注意：Colab 免费档不是 12h，实测 3.5-6h"
      rm -f "$QF" "$QF.out"; exit 1
    fi
  done
}

# ---------- 批量 ----------
do_batch() {
  local FILE="$1" URL="$2" OUTDIR="$3"
  [ -r "$FILE" ] || { echo "[!] 读不到 $FILE"; exit 1; }
  local N; N=$(grep -cve '^\s*$' -e '^#' "$FILE")
  echo "[*] 批量: $N 条 prompt -> $URL"
  check || exit 1

  python3 - "$FILE" "$URL" "$W" "$H" "$STEPS" "$OUTDIR" "${CPU_PRESET:-}" <<'PY'
import sys, json, time, subprocess, os, urllib.request
path, url, w, h, steps, outdir, preset = sys.argv[1:8]
prompts = [l.strip() for l in open(path) if l.strip() and not l.startswith('#')]
body = {'prompts': prompts, 'n_per_prompt': 1,
        'width': int(w), 'height': int(h), 'steps': int(steps)}
if preset: body['cpu_preset'] = preset
req = urllib.request.Request(
    url + '/batch', data=json.dumps(body).encode(),
    headers={'Content-Type': 'application/json'})
ids = json.load(urllib.request.urlopen(req))['ids']
print(f'[+] 入队 {len(ids)} 张，预计约 {len(ids) * 30 / 60:.0f} 分钟')

os.makedirs(outdir, exist_ok=True)
t0, done = time.time(), 0
while True:
    st = [json.load(urllib.request.urlopen(url + '/status/' + i)) for i in ids]
    d = sum(1 for s in st if s['status'] == 'done')
    e = sum(1 for s in st if s['status'] == 'error')
    if d != done:
        done = d
        el = (time.time() - t0) / 60
        print(f'  {d}/{len(ids)}  已用 {el:.1f}min  剩余约 {el/max(d,1)*(len(ids)-d):.0f}min')
    if d + e >= len(ids):
        break
    if time.time() - t0 > 3600:
        print('[!] 超 60 分钟，中止轮询（Colab 会话可能已断）')
        break
    time.sleep(8)

print(f'[+] 完成 {done}/{len(ids)}  总用时 {(time.time()-t0)/60:.1f} 分钟')
for i, s in zip(ids, st):
    if s['status'] == 'done':
        out = os.path.join(outdir, f'colab_{i[:8]}.png')
        try:
            with urllib.request.urlopen(url + '/image/' + i, timeout=180) as r:
                open(out, 'wb').write(r.read())
        except Exception as ex:
            print('  [!] 下载失败', i[:8], ex)
print(f'[+] 已存到 {outdir}')
print('[!] Colab 端产出仍在 /content，记得跑 --flush 搬进 Drive')
PY
}

# ---------- 视频 ----------
# 首次请求会触发 Colab 端下载 Wan2.2 权重(~10-20GB) + 生成，可能 15-25 分钟。
# 有 ref_image 则先上传拿 Colab 端路径走 I2V，否则纯 T2V。
video() {
  local PROMPT="$1" URL="$2" OUTDIR="$3" REF="$4"
  echo "[*] video url : $URL"
  echo "[*] ${VW}x${VH} frames=$FRAMES fps=$VFPS steps=$VSTEPS${REF:+  ref=$REF}"
  check || exit 1
  mkdir -p "$OUTDIR"

  local IMG_PATH=""
  if [ -n "$REF" ] && [ -r "$REF" ]; then
    echo "[*] 上传参考静帧 -> /upload"
    IMG_PATH=$(curl -s -m 180 -F "file=@$REF" "$URL/upload" \
      | python3 -c 'import sys,json;print(json.load(sys.stdin).get("path",""))' 2>/dev/null)
    [ -z "$IMG_PATH" ] && { echo "[!] 上传失败"; exit 1; }
    echo "[*] Colab 端路径: $IMG_PATH"
  fi

  local VF; VF=$(mktemp "${TMPDIR:-$HOME}/cv.XXXXXX")
  python3 - "$VF" "$PROMPT" "$VW" "$VH" "$VSTEPS" "$FRAMES" "$VFPS" "$IMG_PATH" <<'PY'
import sys, json
f, p, w, h, st, fr, fps, img = sys.argv[1:9]
d = {'kind': 'video', 'prompt': p, 'width': int(w), 'height': int(h),
     'steps': int(st), 'frames': int(fr), 'fps': int(fps)}
if img: d['image_path'] = img
open(f, 'w').write(json.dumps(d))
PY
  curl -s -m 60 -X POST "$URL/generate" -H 'Content-Type: application/json' \
    --data-binary "@$VF" -o "$VF.out"
  local JID
  JID=$(python3 -c 'import sys,json;print(json.load(open(sys.argv[1])).get("id",""))' "$VF.out" 2>/dev/null)
  if [ -z "$JID" ]; then
    echo "[!] submit failed: $(head -c 200 "$VF.out")"; rm -f "$VF" "$VF.out"; exit 1
  fi
  echo "[*] job : $JID（首次会先下视频权重，耐心等）"

  local t0; t0=$(date +%s)
  while :; do
    sleep 15
    local S ST EL
    S=$(curl -s -m 30 "$URL/status/$JID")
    ST=$(echo "$S" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("status",""))' 2>/dev/null || echo "?")
    EL=$(( $(date +%s) - t0 ))
    case "$ST" in
      done)
        local OUT="$OUTDIR/colab_vid_${JID:0:8}.mp4"
        curl -s -m 300 -o "$OUT" "$URL/result/$JID"
        if [ -s "$OUT" ] && [ "$(stat -c%s "$OUT")" -gt 1000 ]; then
          echo "[+] $OUT ($(stat -c%s "$OUT") bytes) in ${EL}s"
          rm -f "$VF" "$VF.out"; exit 0
        fi
        echo "[!] video download failed"; rm -f "$VF" "$VF.out"; exit 1
        ;;
      error)
        echo "[!] job error: $(echo "$S" | head -c 300)"; rm -f "$VF" "$VF.out"; exit 1
        ;;
      *)
        echo "[.] $ST (${EL}s)"
        ;;
    esac
    if [ "$EL" -gt 2400 ]; then
      echo "[!] 超 40min 仍未完成 - 检查 Colab 会话是否还活着 / 是否在下权重"
      rm -f "$VF" "$VF.out"; exit 1
    fi
  done
}

# ---------- 主入口 ----------
case "${1:-}" in
  ''|-h|--help) usage ;;
  --health)     resolve_url "${2:-}"; show_health ;;
  --flush)      resolve_url "${2:-}"; require_url; check || exit 1
                curl -s -m 120 "$URL/flush"; echo; echo "[+] 已请求搬盘" ;;
  --video)      [ -n "${2:-}" ] || usage
                resolve_url "${3:-}"; require_url
                video "$2" "$URL" "${4:-$OUTDIR}" "${5:-}" ;;
  --batch)      [ -n "${2:-}" ] || usage
                resolve_url "${4:-}"; require_url
                do_batch "$2" "$URL" "${3:-$OUTDIR}" ;;
  *)
    resolve_url "${2:-}"
    [ -z "${1:-}" ] && usage
    require_url
    single "$1" "$URL" "${3:-$OUTDIR}" "${4:-$RANDOM}" \
           "${5:-$W}" "${6:-$H}" "${7:-$STEPS}"
    ;;
esac
