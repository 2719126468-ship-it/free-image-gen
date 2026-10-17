# Colab 免费 CPU 档：SD1.5 vs SDXL 蒸馏模型实测矩阵

> 结论先行：**2 vCPU 的 Colab 免费 CPU 档，SD1.5 和 SDXL 的差距不在「模型多大」，在「像素数 × 步数」**。
> 权重体积只决定能不能塞进 12.6GB 内存，速度由 UNet 计算量 × 分辨率 × 步数决定。
> 本文所有体积取自 HF repo 内 `openvino_model.bin` 实测加总，所有跑分取自各 repo 官方 benchmark（均在 **192 vCPU Xeon 8559C** 上测），
> 2 vCPU 换算见第三节。**未实测的估算一律标注「估」。**

---

## 一、预设矩阵（notebook 第 4 格 `CPU_PRESETS`，2026-10-18 已落地）

| key | 权重实测 | 架构 / 蒸馏 | steps | guidance | 上限边长 | 负向词 | 512px 耗时（192vCPU 官方） | 1024px 耗时（192vCPU 官方） |
|---|---|---|---|---|---|---|---|---|
| `sd15_lcm` | **0.90 GB** | SD1.5 + LCM（animemix v10） | 8 | 1.5 | 512 | ✅ | **5.51 s** | 33.87 s（SD1.5 超原生分辨率，不推荐） |
| `sdxl_lightning` | **2.06 GB** | SDXL + Lightning（dreamshaper-xl-lightning） | 4 | 2.0 | 768 | ✅ | 4.76 s | 15.25 s |
| `sdxl_anime` | **2.06 GB** | SDXL + LCM（nova_xl_lcm，动漫向） | 8 | 1.5 | 1024 | ✅ | — | **30.6 s** |
| `sana06`（默认） | **2.45 GB** | SANA Sprint 0.6B **DiT**（非 UNet） | 4 | 4.5 | 1024 | ❌（不吃 CFG） | 4.61 s（steps4） | **7.10 s**（steps4）/ 12.73 s（steps20） |
| `animagine` | **6.18 GB** | Animagine-XL-4.0 + Lightning-4step | 4 | **0.0** | 1024 | ❌（guidance=0 负向词无效） | — | **10.26 s**（平均 9.2–12.2） |

**两个坑（已写进 notebook 注释）**

1. `HelloSun/animagine-xl-4.0-Lightning-OpenVINO-INT4` **名字骗人**：repo 名叫 INT4，实际只有 UNet 是 INT8（2.58 GB），
   其余 FP32（3.61 GB），合计 6.18 GB。想省内存它是最差选择。
2. `rupeshs/SDXL-Lightning-2steps-openvino-int8` 实测 **4.41 GB**（unet 3.34 + te2 0.65 + vae 0.30），
   `rupeshs/sdxl-turbo-openvino-int8` / `hyper-sd-sdxl-1-step` 都是 **4.75 GB**。用户口中的「SDXL 选 2.7GB」这一档
   **在 OpenVINO 生态里不存在**；最接近的是 `mzwing/SDXL-Lightning-GGUF` 的 `q5_0`（2.76 GB）——那是 **llama.cpp/ggml** 路线，
   要配 sd.cpp 用，不是 OpenVINO。

---

## 二、SD1.5 与 SDXL 本身的能力差距（与 CPU 无关的部分）

| 维度 | SD1.5 | SDXL 1.0 |
|---|---|---|
| 原生分辨率 | 512×512（latent 64²） | 1024×1024（latent 128²） |
| UNet 参数 | ~865 M | ~2.6 B |
| 文本编码 | 单 CLIP-L（77 token） | CLIP-L + OpenCLIP-G，双塔 + size/prompt 元条件 |
| 语义理解 | 弱，长 prompt 到第 4 条概念就糊 | 明显强，能同时守住多个主体/属性/关系 |
| 手部 / 肢体 / 文字 | 高翻车率 | 好一档，但仍需负面词 / refiner |
| 构图与光影 | 平、灰，靠模型微调（如 animemix）撑 | 原生对比度、材质、光照层次更足 |
| 高分辨率外推 | 612+ 容易重复肢体 | 1216–1536 可直出（本项目 Anima 832×1216 就是这个道理） |
| 生态 | LoRA / ControlNet / img2img 最厚 | LoRA / IP-Adapter / ControlNet 也齐（本项目 animagine 走这条） |
| 蒸馏后最低可用步数 | LCM 4–8 步 | Lightning 1–4 步 / LCM 8 步 / Turbo 1–4 步 |

一句话：**SD1.5 赢在「快、省、生态厚」，SDXL 赢在「懂 prompt、画面密度高、能出大图解」**。
动漫向：Animagine-XL 4.0 / Illustrious / PonyXL 是 SDXL 底子，画质天花板明显高于任何 SD1.5 mix。

---

## 三、CPU 档真实耗时换算（核心）

官方跑分环境 = Xeon 8559C，**192 vCPU**。Colab 免费档 **~2 vCPU**。

```
2vCPU 耗时 ≈ 官方耗时 × (192 / 2) × 并行效率损失(1.3~1.6)
```

即 **乘 125~150 倍**，且该模型越大越受内存带宽限制，实测不会完全线性，取 40~125 倍作区间。

| 预设 | 官方 192vCPU | 2 vCPU 估算 | 一个 3.5h 会话理论产能 |
|---|---|---|---|
| `sd15_lcm` 512px 8步 | 5.5 s | **约 3–8 分钟/张**（估） | 26–70 张 |
| `sdxl_lightning` 768px 4步 | ~9 s（512 4.76 / 1024 15.25 插值） | **约 8–20 分钟/张**（估） | 10–26 张 |
| `sdxl_anime` 1024px 8步 | 30.6 s | **约 20–50 分钟/张**（估） | 4–10 张 |
| `sana06` 1024px 4步 | 7.1 s | **约 5–15 分钟/张**（估） | 14–42 张 |
| `animagine` 1024px 4步 | 10.3 s | **约 8–25 分钟/张**（估）+ 6.18GB 权重 | 内存闸门常拦 |

**为什么 SD1.5 只快 1.8 倍而不是体积比的 3 倍**：SDXL 的算力花在 128² latent + 双文本塔；
分辨率从 512 升到 1024 是 4 倍像素，UNet 是 ~3 倍参数。
**所以「SD1.5@512」vs「SDXL@512」在 CPU 上只差 ~1.4 倍**（5.51s vs 4.76s 甚至反超，因为 SDXL 4 步 vs SD1.5 8 步）。
→ **CPU 档最优解不是 SD1.5，是「SDXL 蒸馏 + 4 步 + 512~768px」**。

---

## 四、推荐用法（按诉求）

```bash
# 1) CPU 档要「最快出草图」
./scripts/colab_gen.sh --health                       # 先看档位 + 可用内存
CPU_PRESET=sd15_lcm W=512 H=512 ./scripts/colab_gen.sh "1girl, blue hair, anime"

# 2) CPU 档要「画质可用」（首选 sana06，其次 sdxl_lightning）
CPU_PRESET=sana06 W=1024 H=1024 ./scripts/colab_gen.sh "photorealistic portrait, 85mm, soft light"
CPU_PRESET=sdxl_lightning W=768 H=768 ./scripts/colab_gen.sh "1girl, anime, detailed background"

# 3) 动漫 + 必须 SDXL 底子（你要的 2.7GB 档 = sdxl_anime，实测 2.06GB）
CPU_PRESET=sdxl_anime W=1024 H=1024 ./scripts/colab_gen.sh "1girl, animagine style, score_7"

# 4) 通过 DSH 工具（免 shell，同一份 API）
colab_gen action=generate cpu_preset=sdxl_anime prompt="..." width=1024 height=1024 steps=8 timeout_sec=2400
```

批量：`CPU_PRESET=sd15_lcm ./scripts/colab_gen.sh --batch prompts.txt`（单 worker 串行，不会 OOM）。

---

## 五、必须知道的 4 个约束（免费 CPU 档）

1. **首次请求 = 下载 + 编译**：`from_pretrained(compile=True)` 在 192vCPU 是 11.9 s，2 vCPU 编译要几分钟。
   第一张的耗时 ≠ 后续张的耗时，别据第一张判速。
2. **内存闸门（本次新增）**：加载前算 `WEIGHT_GB + 激活(512→1.5GB / 768→3.0GB / 1024→5.0GB)`，
   剩余 RAM 不够直接返回明确错误，提示换 `sd15_lcm` / 调小 `maxdim`，不再让会话被 kernel OOM 掐死。
   换档会先 `del` 旧权重 + `gc.collect()`，两份 SDXL 不会同时驻留。
3. **`/content` 会话结束即清空**：模型每次都要重下（`animagine` 6.18GB、`sdxl_anime` 2.06GB）。
   产出必须 `--flush` 进 Drive（免费 Drive 仅 15GB）或直接下载回本机。
4. **视频在 CPU 档不可用**：Wan 2.2 TI2V-5B 需要 GPU，服务端已直接拒绝。

---

## 六、想真正省时间的话（同仓库其它路线）

| 诉求 | 该走 |
|---|---|
| 免费、无审查、不占本机 | `./scripts/gen.sh "<prompt>"`（auto：anima → horde → cf → poll） |
| 动漫画质第一梯队 + 无 GPU | `horde` 模型 `Animagine XL` / `WAI-ANI-NSFW-PONYXL`（免费无限，4–20 分钟/张） |
| 高画质 + 快 | Colab **抢 T4 时段**（北京 6–9 点 / 凌晨 1–3 点）→ 走 GPU 档 Anima，15–40 s/张 |
| 本机离线（Termux，无网） | sd.cpp + GGUF：`mzwing/SDXL-Lightning-GGUF` 的 `q5_0` 2.76GB / `q4_0` 2.41GB，
  `second-state/stable-diffusion-v1-5-GGUF` `Q4_0` 1.46GB。注意 sd.cpp 的 conv2d 在 CPU 上是已知的慢点
  （[arXiv 2412.05781](https://ar5iv.labs.arxiv.org/html/2412.05781) 报告其原始实现有 latency 与内存问题，
  该论文对 SDXL 20步 1024² 做了 4.x 倍加速，但那是 **F32、非蒸馏、非 Android**）。本机 2 核 7.5GB，不现实。 |

---

## 参考来源

- [HelloSun/animemixv10_lcm-OpenVINO-INT4 README/REPORT（0.90GB，8步/1.5，512px 5.51s，1024px 33.87s，192vCPU）](https://huggingface.co/HelloSun/animemixv10_lcm-OpenVINO-INT4)
- [HelloSun/dreamshaper-xl-lightning-OpenVINO-INT4 REPORT（2.06GB，4步/2.0，512px 4.76s，1024px 15.25s，compile 11.9s）](https://huggingface.co/HelloSun/dreamshaper-xl-lightning-OpenVINO-INT4)
- [HelloSun/nova_xl_lcm-OpenVINO-INT4（FP16 6.5GB → INT4 2.06GB，8步/1.5，1024px 30.6s）](https://huggingface.co/HelloSun/nova_xl_lcm-OpenVINO-INT4)
- [HelloSun/Sana_Sprint_0.6B_1024px-OpenVINO-INT4（2.45GB，1024px steps4 7.10s / steps20 12.73s）](https://huggingface.co/HelloSun/Sana_Sprint_0.6B_1024px-OpenVINO-INT4)
- [HelloSun/animagine-xl-4.0-Lightning-OpenVINO-INT4（名为 INT4 实为 INT8+FP32，6.18GB，4步/0.0，1024px 10.26s）](https://huggingface.co/HelloSun/animagine-xl-4.0-Lightning-OpenVINO-INT4)
- [rupeshs/sdxl-turbo-openvino-int8（4.75GB）](https://huggingface.co/rupeshs/sdxl-turbo-openvino-int8) · [rupeshs/SDXL-Lightning-2steps-openvino-int8（4.41GB）](https://huggingface.co/rupeshs/SDXL-Lightning-2steps-openvino-int8)
- [mzwing/SDXL-Lightning-GGUF（q5_0 2.76GB / q4_0 2.41GB / q8_0 3.82GB）](https://huggingface.co/mzwing/SDXL-Lightning-GGUF) · [second-state/stable-diffusion-v1-5-GGUF（Q4_0 1.46GB）](https://huggingface.co/second-state/stable-diffusion-v1-5-GGUF)
- [leejet/stable-diffusion.cpp 量化文档（SD1.5 txt2img 512² 内存 2.0–2.8GB）](https://github.com/leejet/stable-diffusion.cpp/blob/master/docs/quantization_and_gguf.md) · [蒸馏/小 UNet 支持说明](https://github.com/leejet/stable-diffusion.cpp/blob/master/docs/distilled_sd.md)
- [Open-Source Acceleration of Stable-Diffusion.cpp（arXiv 2412.05781，sd.cpp conv2d 慢点与 SDXL 加速比）](https://ar5iv.labs.arxiv.org/html/2412.05781)
- 本仓库既有实测：[docs/colab-free-tier-reality.md](colab-free-tier-reality.md)（免费档 12.6GB RAM / 3.5–6h / 2 vCPU）

*最后更新：2026-10-18。体积为 HF API `?blobs=true` 加总；跑分为各 repo 官方 benchmark 原文，未重测。*
