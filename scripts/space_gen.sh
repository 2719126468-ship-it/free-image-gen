#!/usr/bin/env bash
# 非 ZeroGPU 的 HF Space 生图入口（不消耗你的 ZeroGPU 日配额）
#
# 实测前提（2026-10-17，本机 ZeroGPU 额度=0 的情况下验证）：
#   - zero-a10g 的 Space 立即返回 `event: error`（配额被用尽）
#   - cpu-basic 的 Space 返回 `event: complete` 并出图  -> 不占配额，假设成立
#
# 关键约束：cpu-basic 只有 2 vCPU，**只能跑蒸馏模型 + 步数 <= 5**。
#   25 步的 SDXL/Illustrious 会 heartbeat 十几分钟后 `event: error`（实测三个都这样）。
#
# 用法:
#   space_gen.sh real  "prompt" [输出] [输入图(可选,img2img)] [strength]
#   space_gen.sh anime "prompt" [输出]
#   space_gen.sh raw <space_id> <endpoint> <输出> <参数...>     # 任意 Space
#     参数中 file:/path 会先上传再作为 gradio FileData 传入
#
# 已验证的两个 Space:
#   real  -> Manjushri/SDXL-Turbo-Img2Img-CPU  /predict
#            [source_img, prompt, steps(1-5), seed, strength(0.1-1)]  ~60s  写实/真人风
#   anime -> ClickyGPT/NSFW_Z-Image-Turbo      /infer
#            [prompt, neg, seed, randomize, w, h, guidance, steps]    ~90s  二次元插画风
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$SCRIPT_DIR/gradio_space_gen.py"
[ -f ~/.dsh/.hf-token ] && export HF_TOKEN="${HF_TOKEN:-$(cut -d= -f2 ~/.dsh/.hf-token)}"

MODE="${1:-}"; PROMPT="${2:-}"; OUT="${3:-$HOME/th-img/space_$(date +%s).webp}"
[ -z "$MODE" ] || [ -z "$PROMPT" ] && {
  sed -n '1,30p' "$0" | sed 's/^# \{0,1\}//'; exit 2; }

SEED="${SEED:-$((RANDOM % 99999))}"
STEPS="${STEPS:-4}"          # cpu-basic 上限，别超 5
NEG="${NEG:-lowres, bad anatomy, extra limbs, bad hands}"

case "$MODE" in
  real)
    IN_IMG="${4:-}"; STRENGTH="${5:-0.55}"
    if [ -n "$IN_IMG" ] && [ -f "$IN_IMG" ]; then
      echo "[*] 图生图（写实）strength=$STRENGTH steps=$STEPS 输入=$IN_IMG"
      GRADIO_WAIT="${GRADIO_WAIT:-420}" python3 -u "$PY" \
        "Manjushri/SDXL-Turbo-Img2Img-CPU" "/predict" "$OUT" \
        "file:$IN_IMG" "$PROMPT" "$STEPS" "$SEED" "$STRENGTH"
    else
      echo "[!] real 模式需要输入图（该 Space 是 img2img）：space_gen.sh real \"prompt\" [out] <输入图> [strength]"
      exit 2
    fi
    ;;
  anime)
    W="${WIDTH:-512}"; H="${HEIGHT:-768}"; G="${GUIDANCE:-2.5}"
    echo "[*] 文生图（二次元）${W}x${H} guidance=$G steps=$STEPS"
    GRADIO_WAIT="${GRADIO_WAIT:-420}" python3 -u "$PY" \
      "ClickyGPT/NSFW_Z-Image-Turbo" "/infer" "$OUT" \
      "$PROMPT" "$NEG" "$SEED" "False" "$W" "$H" "$G" "$STEPS"
    ;;
  *)
    # raw 模式：space_gen.sh raw <space_id> <endpoint> <输出> <参数...>
    if [ "$MODE" = "raw" ]; then
      SID="$PROMPT"; EP="$OUT"; NEWOUT="${4:-$HOME/th-img/space_$(date +%s).webp}"
      shift 4
      GRADIO_WAIT="${GRADIO_WAIT:-600}" python3 -u "$PY" "$SID" "$EP" "$NEWOUT" "$@"
    else
      echo "[!] 未知模式: $MODE （real | anime | raw）"; exit 2
    fi
    ;;
esac
