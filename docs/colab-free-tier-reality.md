# Colab 免费档生图：能做什么、不能做什么、怎么榨到极限

> 现状：免费档 **12.6GB RAM / ~107GB 磁盘 / 无 GPU 时段时只有 CPU**，会话最长 12h（实际常被提前回收）。
> 本文只讲实测与官方原文，不给幻想。

---

## 一、先把话说清楚：Colab 免费档的两条硬墙

### 硬墙 1：免费档 GPU 是「动态分配」，不是你想用就有

官方 FAQ 原文（research.google.com/colaboratory/faq.html）：

> In the version of Colab that is **free of charge, access to expensive resources like GPUs is heavily restricted**.
> Colab resources are **not guaranteed and not unlimited**, and usage limits sometimes fluctuate.
> notebooks can run for at most **12 hours**, depending on availability and your usage patterns.

所以「只能连到非 GPU 时段」不是你的账号问题，是免费档的常态。**抢 GPU 的正确姿势不是等，是换战场。**

### 硬墙 2：CPU 上跑 SDXL 级模型，算得出来是跑不动的

按你日志里的模型体积算（transformer 3.91GB + text_encoder 1.19GB + text_conditioner 0.269GB + vae 0.254GB）：

| 加载方式 | 权重占用 | + 1024² 激活峰值 | 合计 | 12.6GB RAM |
|---|---|---|---|---|
| fp32（你现在，因为 `torch_dtype` 被忽略） | 11.25 GB | 4–6 GB | **16.2 GB** | ❌ OOM |
| fp16（修好后） | 5.62 GB | 4–6 GB | 10.6 GB | ⚠️ 勉强 |
| fp16 + VAE tiling | 5.62 GB | 2–3 GB | ~8.6 GB | ✅ 能跑 |

**但「能跑」不等于「能用」**：SDXL 1024² 30 steps 在 Colab CPU（约 2 核）上大约 **20–60 分钟/张**。
免费档 12h 会话撑死出 12–30 张，中途还可能被回收。

---

## 二、想在 Colab 上真的要「快 + 好」，只有这三条路

### 路线 A：抢 GPU 时段（最直接，但要挑时间）

免费 T4 的可用性跟**地区、时段、账号活跃度**都有关。实测经验：

1. **北京时间 早上 6–9 点 / 凌晨 1–3 点**最容易分到 T4（北美空闲时段）
2. 分配不到 GPU 时，**不要反复重连** —— 会被判 abuse，冷却更久
3. 挂着 notebook 不动会被回收；**每隔几分钟跑一个空 cell** 保活
4. 用 `nvidia-smi` 确认真的分到了，而不是只看「已连接」

```bash
nvidia-smi
```

```python
import torch
print(torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU only')
```

分到 T4 之后，用 `docs/colab-t4-fix.md` 里那套（fp16 + VAE fp32 + ComponentsManager auto offload）。

### 路线 B：CPU 也能跑的小模型（要快就别用 SDXL）

如果你就是不想等 GPU，**换模型**比优化代码有效 10 倍：

| 模型 | 体积 | CPU 单张（估算） | 质量 | 备注 |
|---|---|---|---|---|
| `stabilityai/sdxl-turbo` | ~6.9GB | 3–8 分钟（1–4 steps） | 中高 | **步数只要 1–4**，这是 CPU 上的关键 |
| `stabilityai/sd-turbo` | ~2.5GB | 1–3 分钟 | 中 | 512²，1–4 steps |
| `segmind/tiny-sd` | ~0.5GB | 10–30 秒 | 低 | 只适合草稿 |
| `cagliostrolab/animagine-xl-4.0` | ~6.9GB | 20–50 分钟 | **高（动漫最强之一）** | CPU 上别想，留给 GPU |

**核心事实**：SDXL 慢在「30 步 × 每步全图去噪」。**turbo 系列只要 1–4 步**，同样的 CPU 直接快 10 倍。
这是 CPU 环境下唯一现实的提速手段。

```python
# CPU 上跑 sdxl-turbo：注意 steps 必须 ≤4，guidance_scale=0.0
import torch
from diffusers import AutoPipelineForText2Image

pipe = AutoPipelineForText2Image.from_pretrained(
    'stabilityai/sdxl-turbo',
    torch_dtype=torch.float32,      # CPU 上用 fp32（fp16 在 CPU 上反而慢）
    variant='fp16',
)
pipe.to('cpu')
pipe.enable_vae_slicing()
pipe.enable_vae_tiling()

img = pipe(
    prompt='1girl, blue long hair, anime style, detailed face',
    num_inference_steps=2,          # 关键：1-4，多了没用
    guidance_scale=0.0,             # turbo 必须 0
    height=512, width=512,          # CPU 上别上 1024
).images[0]
img.save('out.png')
```

### 路线 C：Colab CPU 只做「后处理」，生图交给免费 API

这是我最推荐的组合 —— **Colab 不负责生成，负责加工**：

- 生图：Vercel AI Gateway（$5/30 天）/ Replicate Try-for-Free / AI Horde
- Colab 做：放大（`RealESRGAN`）、抠图、批量拼接对比图、LoRA 训练（CPU 上 LoRA 也不现实，跳过）

---

## 三、你要的「ami 模型那种质量」到底怎么拿

你说的「ami」如果指 **Animagine XL**（动漫生图质量第一梯队），它的现实情况是：

- 模型页：https://huggingface.co/cagliostrolab/animagine-xl-4.0（43 万下载，非 gated）
- **SDXL 架构，6.9GB**，30 steps 在 T4 上约 15–25 秒/张，在 CPU 上 20–50 分钟/张
- 也就是说：**这模型的可用性完全绑定「有没有 GPU」**

所以拿它的方式只有两个：

1. **Colab 抢到 T4** → 用上面路线 A + `docs/colab-t4-fix.md`
2. **用 API 出同等质量** → Vercel 的 `bfl/flux-kontext-pro`（$0.04/张，免费层 $5/月）质量在动漫写实向不输 Animagine，且**不用 GPU、不用等时段**

---

## 四、AI Horde 上的动漫模型（免费、无 GPU 需求、但慢）

本机 2026-10-17 实测在线 worker 数（`stablehorde.net/api/v2/status/models?type=image`）：

| 模型 | worker | 说明 |
|---|---|---|
| `WAI-NSFW-illustrious-SDXL` | 12 | **最多 worker**，但本机实测 **输出纯黑图（YAVG=0.0，526B）**，worker 端审查吞图 |
| `WAI-ANI-NSFW-PONYXL` | 9 | PonyXL 系，worker 确定性渲染（同 seed 同输出） |
| `AMPonyXL` | 7 | |
| `Animagine XL` | 4 | **就是你要的那个**，4 worker，排队较久 |
| `MeinaMix` | 3 | 经典动漫模型 |
| `Anything v5` / `Abyss OrangeMix` / `Counterfeit` / `Hassaku XL` | 4–5 | 都是老牌动漫模型 |

**实测数据**：`WAI-NSFW-illustrious-SDXL` 提交 → 253 秒出图，但**输出是纯黑 526B**（审查）。
这说明「worker 多」不等于「能出图」——**必须逐模型验证 YAVG**。

```python
# 判定纯黑图（worker 审查）
from PIL import Image, ImageStat
im = Image.open(path).convert('L')
if ImageStat.Stat(im).mean[0] < 6:
    print('黑图，worker 审查吞了，换模型')
```

**结论**：AI Horde 免费无限，但动漫模型的质量参差、审查玄学、排队 4 分钟起。适合「不着急、要免费」的场景。

---

## 五、给你的实际建议（按投入产出排序）

| 你的诉求 | 该走哪条 |
|---|---|
| **要快 + 质量好 + 不花钱** | **Vercel AI Gateway**（$5/30天，kontext-pro ≈125 张/月，20–60s/张） |
| 要 Animagine 那种动漫味 | Colab 抢 T4 + Animagine XL（15–25s/张），或 Horde 的 `Animagine XL`（4min/张） |
| 完全不想等 GPU、也不想注册 | Horde + `Animagine XL` / `MeinaMix`（免费无限，4–20min/张） |
| 只想在 Colab 里玩 | `sdxl-turbo` 2 steps + 512²（3–8min/张，质量中高） |

**Colab 免费档不是生图工具，是「有 GPU 时段时的临时算力」。**
把它当成主力，你会一直在等时段和 OOM 之间循环。

---

*最后更新：2026-10-17。Colab 规则引自官方 FAQ；Horde worker 数与出图结果为本机实测。*
