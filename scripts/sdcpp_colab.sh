#!/usr/bin/env bash
# sdcpp_colab.sh —— 在 Google Colab 上用 stable-diffusion.cpp 跑 SDXL 动漫（CPU 可行解）
#
# 为什么走这条路（2026-10-18 查证，纠正转发摘要的"bf16 最优先"）：
#   · Colab 免费 CPU 长期是 Skylake-SP / Cascade Lake，有 avx512f 但【无 avx512_bf16】
#     → PyTorch bfloat16 在 CPU 上会软件 fallback，不比 fp32 快 → 摘要方案一在免费档大概率无效
#   · SDXL 在 PyTorch 里的两难：fp32 权重 14.7GB 装不进 12.6GB 墙；fp16 装得下但 CPU 慢一个量级
#   · sdcpp 用 ggml 的 CPU 原生 int/fp16 kernel（AVX2/AVX512），Q4_K 量化后 SDXL 只有 2.8GB
#     → 唯一"装得下 + CPU 上真能跑完"的 SDXL 路。arXiv 2412.05781 实测 M1 Pro 上 Winograd 后 4.79x
#
# 用法（Colab 单元格里）：!bash sdcpp_colab.sh "你的提示词" [输出png] [宽] [高] [步数]
#   首次会 git clone + cmake build（约 3-5 分钟）+ 下 2.8GB 模型，之后复用。
#   注意：Colab 基座是 Ubuntu 22.04/glibc 2.35，官方预编译二进制是 24.04 构建（glibc 2.39）跑不了，
#   所以这里从源码 build。若 apt/cmake 失败，看文末排错。
set -e
PROMPT="${1:-1girl, solo, blue hair, masterpiece, best quality}"
OUT="${2:-/content/sdcpp_out.png}"
W="${3:-832}"; H="${4:-1216}"; STEPS="${5:-28}"
GGUF_URL="https://huggingface.co/off-grid-ai/animagine-xl-4.0-GGUF/resolve/main/animagine-xl-4.0-Q4_K.gguf"
GGUF="/content/animagine-xl-4.0-Q4_K.gguf"   # 2.80GB，实测 ungated
SDROOT="/content/sd.cpp"

echo "[1/4] 构建依赖（cmake + 编译器）"
command -v cmake >/dev/null 2>&1 || { apt-get -qq update && apt-get -qq install -y cmake build-essential git; }

echo "[2/4] clone + build sd-cli（首次约 3-5 分钟）"
if [ ! -x "$SDROOT/build/bin/sd-cli" ] && [ ! -x "$SDROOT/build/sd-cli" ]; then
  [ -d "$SDROOT" ] || git clone --recursive https://github.com/leejet/stable-diffusion.cpp "$SDROOT"
  cd "$SDROOT" && git submodule update --init --recursive >/dev/null 2>&1 || true
  mkdir -p build && cd build
  cmake .. -DCMAKE_BUILD_TYPE=Release -DSD_WEBP=OFF -DSD_WEBM=OFF >/dev/null
  cmake --build . --config Release -j"$(nproc)" >/dev/null
fi
SDCLI="$(ls "$SDROOT/build/bin/sd-cli" "$SDROOT/build/sd-cli" 2>/dev/null | head -1)"
[ -x "$SDCLI" ] || { echo "★ sd-cli 没构建出来，看上面 cmake 报错"; exit 1; }
echo "    sd-cli = $SDCLI"

echo "[3/4] 下 animagine-xl-4.0 Q4_K（2.8GB，SDXL 动漫天花板）"
[ -f "$GGUF" ] || wget -q --show-progress -O "$GGUF" "$GGUF_URL"

echo "[4/4] 出图 ${W}x${H} @${STEPS}步"
# 参数以 "$SDCLI" -h 为准；-p prompt / -n negative / --width --height / --steps / --cfg-scale / -o
#"$SDCLI" -m "$GGUF" -p "$PROMPT" \
#  -n "censor, mosaic, (worst quality, low quality:1.4), bad anatomy, watermark, text" \
#  -W "$W" -H "$H" --steps "$STEPS" --cfg-scale 7.0 \
#  --sampling-method euler_a -s -1 -o "$OUT"
# 参数名已核对 upstream examples/common/common.cpp 的 options 表：
#   -m/--model  -p/--prompt  -n/--negative-prompt  -W/--width  -H/--height
#   --steps  --cfg-scale  --sampling-method(★不是 sample-method)  -s/--seed(<0=随机)
#   -o/--output  -t/--threads  --type(q4_0/q8_0)  -M/--mode(convert 等，生成时不用)
"$SDCLI" -m "$GGUF" -p "$PROMPT" \
  -n "censor, mosaic, (worst quality, low quality:1.4), bad anatomy, watermark, text" \
  -W "$W" -H "$H" --steps "$STEPS" --cfg-scale 7.0 --sampling-method euler_a \
  -s -1 -t "$(nproc)" -o "$OUT"
echo "[+] 完成：$OUT"

# ---- 排错 ----
# 1) cmake 报找不到编译器：!apt-get install -y build-essential
# 2) git clone --recursive 超时：submodule 多，可 !git clone https://github.com/leejet/stable-diffusion.cpp
#    再 cd 进去 !git submodule update --init --recursive
# 3) 想换 pony/其它 SDXL：把 GGUF_URL 换成 off-grid-ai/pony-diffusion-v6-xl-GGUF 的 Q4_K
# 4) 想更快：--steps 降到 20；--offload-to-cpu 降内存；--vae-tiling 省显存/内存
# 5) 想先量化再跑：sd-cli -M convert -m xxx.safetensors -o out.gguf --type q4_0
