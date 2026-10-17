#!/usr/bin/env bash
# Pollinations 零 key 生图（当前匿名档 = sana/flux 引擎）
# 实测限制：45 秒 / IP / 张；出图约 9 秒；右下角带 pollinations.ai 水印
# 用法: pol_gen.sh "prompt" [输出路径]
#   环境变量 WIDTH HEIGHT SEED MODEL 可覆盖默认值
set -euo pipefail

PROMPT="${1:?prompt required}"
OUT="${2:-$HOME/th-img/pol_$(date +%s).jpg}"
W="${WIDTH:-768}"
H="${HEIGHT:-1024}"
SEED="${SEED:-$((RANDOM % 99999))}"
MODEL="${MODEL:-flux}"

mkdir -p "$(dirname "$OUT")"
# URL 编码交给 python，避免 shell 转义踩坑
PE=$(python3 -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))" "$PROMPT")
URL="https://image.pollinations.ai/prompt/$PE?width=$W&height=$H&model=$MODEL&nologo=true&seed=$SEED"

# 撞 402(FREE_LIMIT) 时自动等过 45 秒窗口重试，最多 4 次
for try in 1 2 3 4; do
  code=$(curl -s -L -o "$OUT" -w "%{http_code}" --max-time 200 "$URL" || echo "000")
  if [ "$code" = "200" ] && file "$OUT" 2>/dev/null | grep -qi 'image data'; then
    echo "OK $OUT ($(wc -c <"$OUT") bytes, seed=$SEED, ${W}x${H})"
    exit 0
  fi
  echo "[.] try$try HTTP=$code -> 等 46s 越过 free-limit 窗口" >&2
  sleep 46
done
echo "FAILED after 4 tries (last HTTP=$code)" >&2
exit 1
