# Colab T4 跑 modular pipeline：四个报错逐个修

> 症状来源：`AssertionError: Torch not compiled with CUDA enabled`（`pipe.to('cuda')` 处）
> 环境：Google Colab / T4 16GB（可用约 13.6GB）、Python 3.13、`/tmp/ipykernel_*`、会话约 6 小时

---

## 报错 1：`Torch not compiled with CUDA enabled` —— 装的是 CPU 版 torch

**不是 T4 的问题，也不是 diffusers 的问题。** 栈底原文：

```
torch/cuda/__init__.py in _lazy_init()
    471  raise AssertionError("Torch not compiled with CUDA enabled")
```

`_lazy_init` 在第一次真正碰 CUDA 时才跑，所以前面 `from_pretrained` / `load_components` 全都"成功"了 ——
它们只在 CPU 上搬权重。**决定性旁证**：日志第一行的

```
WARNING:torchao.kernel.intmm:Warning: Detected no triton
```

CUDA 版 torch **必然捆绑 triton**，没有 triton = 这是 CPU wheel。多半是某次 `pip install torch`
（没带 `--index-url`）把 Colab 预装的 cu12x 版覆盖成了 PyPI 默认的 CPU 版。

**修（会话内执行一次，然后必须重启 runtime）**：

```python
# 先确认现状
import torch
print('torch:', torch.__version__)          # 期望带 +cu1xx 后缀
print('cuda build:', torch.version.cuda)    # 期望 cu126 / cu128，是 None 就是 CPU 版
print('available:', torch.cuda.is_available())
```

```bash
# T4 = sm75，cu126 就够；Python 3.13 的 linux wheel 官方有
pip uninstall -y torch torchvision torchaudio
pip install torch==2.9.1+cu126 torchvision==0.29.1+cu126 torchaudio==2.9.1+cu126 \
    --index-url https://download.pytorch.org/whl/cu126
```

装完 **Runtime → Restart session**，再验：

```python
import torch
assert torch.cuda.is_available(), 'CUDA 还是不可用'
print(torch.cuda.get_device_name(0), torch.cuda.get_device_properties(0).total_memory / 1024**3, 'GB')
```

> 实测过的 wheel 组合（2026-10-17 核对 download.pytorch.org 目录）：
> `torch-2.9.1+cu126-cp313-cp313-manylinux_2_28_x86_64.whl`（832,884,369 B）
> `torchvision-0.29.1+cu126-cp313-cp313-manylinux_2_28_x86_64.whl`
> `torchaudio-2.9.1+cu126-cp313-cp313-manylinux_2_28_x86_64.whl`
> cu128 也有同版本，但 T4 用 cu126 更稳。

---

## 报错 2：`Unexpected input 'dict_keys(['torch_dtype'])'` —— dtype 传错位置

`ModularPipeline.from_pretrained()` **不接受** `torch_dtype`。签名是：

```python
from_pretrained(cls, pretrained_model_name_or_path, trust_remote_code=None,
                components_manager=None, collection=None, workflow=None, **kwargs)
```

多出来的 kwargs 会走到 `modular_pipeline.py:1855`：

```python
if len(kwargs) > 0:
    logger.warning(f"Unexpected input '{kwargs.keys()}' provided. This input will be ignored.")
```

**所以你那次 `torch_dtype=torch.bfloat16` 被整个丢掉了** —— 权重其实是 fp32 加载的，白占一倍显存。

**正确位置是 `load_components()`**（它把 kwargs 逐个转给 `ComponentSpec.load`，
后者会 `kwargs.pop("torch_dtype")` 再映射成 `dtype`）：

```python
pipe.load_components(torch_dtype=torch.float16)          # 全局
pipe.load_components(torch_dtype={'default': torch.float16, 'vae': torch.float32})  # 分组件
```

---

## 报错 3（还没报，但必踩）：T4 不支持 bfloat16

T4 是 **compute capability 7.5**，没有原生 bf16。`torch_dtype=torch.bfloat16` 在 T4 上要么走模拟
（慢到不可用），要么在个别 kernel 里直接出 NaN。

**T4 一律用 `torch.float16`**，但 **VAE 单独留 float32** —— fp16 的 VAE decode 在 sm75 上是
经典黑图/NaN 来源：

```python
torch_dtype={'default': torch.float16, 'vae': torch.float32}
```

---

## 报错 4（还没报，但 13.6GB 必踩）：`ModularPipeline` 没有 `enable_model_cpu_offload`

`DiffusionPipeline` 那套 `enable_model_cpu_offload()` / `enable_sequential_cpu_offload()`
**在 ModularPipeline 上不存在**（源码里 0 处定义）。直接 `pipe.to('cuda')` 等于把
~5.6GB 权重（transformer 3.91GB + text_encoder 1.19GB + text_conditioner 269MB + vae 254MB）
一次性全塞进 13.6GB，1024×1024 的激活值一上来就 OOM。

**ModularPipeline 的正确姿势是 `ComponentsManager` + `enable_auto_cpu_offload()`**：
自己持有 manager 引用，不碰私有属性 `_components_manager`。

---

## 完整可用代码（替换你现在的第 7–11 行）

```python
import torch
from diffusers.modular_pipelines import ModularPipeline, ComponentsManager

MODEL_ID = "..."   # 保持你原来的

# 1) 自己持有 manager，后面用它的 auto offload
cm = ComponentsManager()
pipe = ModularPipeline.from_pretrained(MODEL_ID, components_manager=cm)

# 2) dtype 必须在 load_components 里给，而且 T4 用 fp16、VAE 用 fp32
pipe.load_components(torch_dtype={'default': torch.float16, 'vae': torch.float32})

# 3) 不要 pipe.to('cuda')：让 manager 按显存自动搬进搬出
cm.enable_auto_cpu_offload(device='cuda', memory_reserve_margin='2GB')

pipe.set_progress_bar_config(disable=True)
print('[+] loaded, VRAM total:',
      torch.cuda.get_device_properties(0).total_memory / 1024**3, 'GB')
```

如果 `enable_auto_cpu_offload` 也报错（老版 diffusers 没有），退一步用最朴素的手动搬运：

```python
pipe = ModularPipeline.from_pretrained(MODEL_ID)
pipe.load_components(torch_dtype={'default': torch.float16, 'vae': torch.float32})
for name, mod in pipe.components.items():
    if isinstance(mod, torch.nn.Module):
        if name == 'text_encoder':
            mod.to('cpu')      # 文本编码器用完就挪走，省 1.2GB
        else:
            mod.to('cuda')
```

> `diffusers` 版本必须够新才有 `ComponentsManager`。`pip install -U diffusers`
> （官方最新 0.41.0，`setup.py` 要求 `torch>=2.6`、`accelerate>=0.31.0`、`transformers>=4.41.2`）

---

## 6 小时会话限制怎么破

Colab 免费档会被回收，靠"一次性跑完"必然被打断。三件事：

### 1. 模型缓存放 Drive，别每次重下 5.6GB

```python
from google.colab import drive
drive.mount('/content/drive')

import os
os.environ['HF_HOME'] = '/content/drive/MyDrive/hf_cache'
os.environ['HF_HUB_ENABLE_HF_TRANSFER'] = '1'   # 加速（需 pip install hf_transfer）
```

### 2. 输出直接写 Drive

```python
OUT = '/content/drive/MyDrive/img_out'
os.makedirs(OUT, exist_ok=True)
```

### 3. 批处理做成可续跑：先读清单，跳过已存在的输出

```python
import json, os

jobs = json.load(open('/content/drive/MyDrive/jobs.json'))   # [{"id":..,"prompt":..}, ...]
done = {f[:-4] for f in os.listdir(OUT) if f.endswith('.png')}

for job in jobs:
    if job['id'] in done:
        print('skip', job['id'])
        continue
    img = pipe(prompt=job['prompt'])          # 按你的实际签名补其余参数
    img.images[0].save(f"{OUT}/{job['id']}.png")
    print('done', job['id'])
```

会话断了就重跑同一个 cell —— 已完成的自动跳过。**这才是 6 小时限制的正解**，不是抢时间。

### 4. 显存碎片：每张图之间清一次

```python
import gc, torch
gc.collect(); torch.cuda.empty_cache()
```

---

## 附：这条路的性价比提醒

T4 + 5.6GB 模型 + 6 小时会话 + 四层踩坑，产出速度大概 1–3 分钟/张，且随时被回收。

本项目刚核实过的免费 API 通道 **不需要任何 GPU**：

| 通道 | 免费额度 | 成本 | 备注 |
|---|---|---|---|
| Vercel AI Gateway | **$5 / 30 天循环** | $0 | `bfl/flux-kontext-pro` 在免费层，$0.04/张 ≈ 125 张/月 |
| Replicate Try-for-Free | 有限次数 | $0 | 含同一个 kontext-pro |
| AI Horde | 无限 | $0 | 无审查，45s–20min |

Colab 这条路的价值在于**模型自由度**（本地 LoRA / 自定义 pipeline），
不是速度或额度。如果只是要出图，走 API 更划算。
