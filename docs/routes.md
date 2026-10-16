# 免费生图路线调研结论（2026-10-17 实测）

> 全部结论均来自本机实际 HTTP 请求，未实测项已标注。设备环境：Android/Termux，无 GPU，磁盘余 11G，curl + python3 + node + ffmpeg。

## 一、可用路线总览

| 路线 | 认证 | 额度 | NSFW | 速度 | 质量 | 验证方式 |
|---|---|---|---|---|---|---|
| **AI Horde** `horde_gen.sh` | 匿名 `apikey: 0000000000` | **无限量** | **无审查** | 37s-13min（波动大） | 中高（SDXL/Illustrious） | ✅ 端到端出图 |
| **HF ZeroGPU** `anima_gen.sh` | HF token + `X-HF-Authorization` | 5 min GPU/天（PRO 40 min） | 无审查 | 1-10s | **最高**（Anima-2.9B） | ✅ 出图 + 触限 |
| **Cloudflare** `gen_image.sh cf` | API token | 10k neurons/天 ≈ 50 张 | **有过滤** | 5-15s | 高（flux） | ✅ 出图 + 触限 |
| **Pollinations** `gen_image.sh pollinations` | 无 | 1 张/45s | 可关 | 10-30s | 低（sana） | ✅ 出图 |
| **TensorHub** `th_gen.sh` | 无 | 匿名 2 次 | 无审查 | 3-4min | 中 | ✅ 出图 + 触限 |
| **Google Colab** | Google 账号 | 12h/会话，T4 | 无审查 | 5-10min/张 | 任意（本地模型） | ⚠️ 文档确认，未部署 |
| ModelScope | 需手机注册 | 免费档 | 未知 | 快 | 高 | ⚠️ 仅 401 探测 |
| SiliconFlow | 需注册 | 送额度 | 未知 | 快 | 高 | ⚠️ 仅 401 探测 |
| Novita / fal / DeepInfra / Hyperbolic | 需注册+卡 | 免费额度小 | 未知 | 快 | 高 | ⚠️ 仅 401 探测 |
| Krea | 需 workspace owner | **无免费档** | 未知 | 快 | 高 | ❌ 纯付费 |

**结论：真正免费且可编程的规模化路线是 AI Horde（无限量）+ Colab（12 小时 T4）。**

---

## 二、AI Horde（本次最大发现）

### 核心事实
- 匿名 apikey 固定为 `0000000000`，无需注册即可提交任务。
- 端点：`POST https://stablehorde.net/api/v2/generate/async` → 轮询 `GET /api/v2/generate/status/{id}`。
- kudos 余额为负（`-50`）仍可跑，只是队列优先级最低。
- 167 个图像模型，NSFW 模型充足：`WAI-NSFW-illustrious-SDXL`(9 workers)、`WAI-ANI-NSFW-PONYXL`(4)、`Pony Diffusion XL`(3)、`Hentai Diffusion`(4)、`Grapefruit Hentai`(4)、`Nova Furry XL`(3)、`SwamPonyXL`(3)。
- `/status/models?type=image` 的 `nsfw` 字段对所有模型都是 `null`，**无法据此筛选**，需直接传 `"nsfw":true, "censor_nsfw":false`。

### 两个坑（已写进脚本）
1. **预签名 R2 URL 几分钟内失效** —— 拿到 `img` 字段后必须立即下载，不能延后。
2. **`censored` 元数据不可信** —— 实测一次 `state=ok censored=False` 但返回 758 字节纯黑 webp（YAVG≈0）。脚本用 `ffmpeg signalstats` 检测 YAVG<6 判定为 worker 审查，并自动切换模型重试（默认轮换 4 个模型）。

### 排队实况
- worker_count 约 16，thread_count 约 18。
- 512×768/20 steps：最快 37 秒，最慢 13 分钟（取决于模型与排队深度）。
- `WAI-NSFW-illustrious-SDXL` 的 eta 约 147s、jobs 82（最热）；`Dreamshaper` eta 10-30s（最快）。
- **调优建议**：赶时间用 `Dreamshaper`/`Deliberate`/`ICBINP`（eta 0-18s）；要质量用 `WAI-NSFW-illustrious-SDXL`。

---

## 三、HF ZeroGPU 配额机制（实测推翻两条流传说法）

### 1. 配额是**账号级全局共享**，换 Space 不涨额度
实测：先在 `mrfakename/anima-v1-fast` 用尽额度，再访问 `Menyudadas/anima-v1-fast`，返回
`You have exceeded your free ZeroGPU quota (45s requested vs. 0s left)`。
→ 同一额度池。论坛上"quota is per space"的说法（[nroggendorff 帖子](https://huggingface.co/posts/nroggendorff/123504053518795)）与当前行为不符。

### 2. 扣的是**声明的 duration，不是实际运行时间**
参考 [multimodalart/skills 的 how-quota-works.md](https://huggingface.co/buckets/multimodalart/skills/tree/skills/huggingface-zerogpu/references/how-quota-works.md)：
`DEFAULT_SCHEDULE_DURATION = 60s`，未显式声明 `duration=` 的 Space 每次都按 60s 扣。
- Anima 的 `-fast` Space 声明 45s/call → 300s/天 ÷ 45s = **6-7 张/天**（832×1216/25 步实际只需约 12s GPU）。
- 若找到声明 `duration=15` 的 Space，同样 300s 可跑 **20 张**。
- 这是免费档唯一的免费扩容手段：**找低 duration 声明的 Space**。

### 3. 两套限制器
| 错误 | 含义 |
|---|---|
| `ZeroGPU quota exceeded (Ns requested vs. Ms left)` | 秒数额度耗尽 |
| `exceeded your ZeroGPU runs limit` | 每日**次数**上限（独立于秒数） |

实测四个 Space 中三个撞 runs limit、一个撞秒数额度，说明两者会分别触发。

### 4. 额度窗口是首次调用起 24h 固定
不是自然日重置、不是滑动窗口。14:00 用第一次 → 次日 14:00 重置。

### 5. 认证 header
`X-HF-Authorization: Bearer <token>` 必须（gradio_client 源码 `client.py:118-125` 把 `Authorization` 改写为它）。`x-api-key` 和 `Authorization` 均被忽略。

### 6. 已验证可用的 Anima Space
| Space | 参数 schema | 输出 | 备注 |
|---|---|---|---|
| `mrfakename/anima-v1-fast` | 9 参数 | webp | 1-10s 返回，实测最快 |
| `Menyudadas/anima-v1-fast` | 9 参数 | png | 同样秒回 |
| `mrfakename/anima-v1` | 9 参数 | webp | 非 fast 版 |
| `baka999/Anima-v1-lora` | 13 参数 | png | 多 LoRA 字段；`ptrgu/real_skin` 路径不存在，需换 repo |

调用格式：`POST /gradio_api/call/generate`，body `{"data":[prompt, negative, w, h, steps, cfg, sigma_shift, seed, add_prefix]}`。

---

## 四、Google Colab（突破每日上限的唯一免费方案）

- 免费档确认：**最多 12 小时/会话，T4 GPU 16GB 免费**（[Colab FAQ](https://research.google.com/colaboratory/faq.html)：`notebooks can run for at most 12 hours`）。
- Anima-2.9B-preview 模型共 **6.80 GB**（transformer 5.19 + text_encoder 1.11 + conditioner 0.25 + vae 0.24），T4 16GB 装得下。
- 现成项目：[nazdridoy/ComfyUI-On-Colab](https://github.com/nazdridoy/ComfyUI-On-Colab)（内置 cloudflared/localtunnel 公网穿透，一键取图）、[shinshin86/comfy-agent colab 脚本](https://github.com/shinshin86/comfy-agent/blob/main/scripts/colab/02_start_comfyui.py)。
- 单张预计 5-10 分钟（T4 + 25 步），12 小时约 70-140 张，**是本地免费方案的 10-20 倍产能**。
- 未部署（需 Google 账号与浏览器交互），列为下一步。

---

## 五、已排除 / 待定

### 排除（实测拒绝或无免费档）
- **Krea API**：需 workspace owner/admin 建 token，纯付费计费。网页版每天 100 免费单位但不可编程调用。
- **Hyperbolic**：`/v1/image/generation` 返回 `decommissioned`。
- **Novita / fal.ai / DeepInfra**：均 401/400 要求 API key，无免费匿名档。
- **Perchance**：`/api/getGeneratorPageDependencies` 等 POST 端点被 Cloudflare challenge 拦截（GET 页面能过），必须浏览器自动化，非纯 HTTP 可解。
- **本地部署**：磁盘余 11G、无 PyTorch、8 核 ARM 无 GPU、内存 7.7G，CPU 出图 30-90 分钟/张，已量化排除。

### 待定（需注册，未实测）
- **ModelScope 魔搭**：`POST https://api-inference.modelscope.cn/v1/images/generations`，未认证返回 401。需手机注册，免费档额度未实测。
- **SiliconFlow 硅基流动**：`POST https://api.siliconflow.cn/v1/images/generations`，401 `Token is invalid`。注册送额度，NSFW 政策未实测。
- **HF 多账号**：`/join` 返回 HTTP 202 size=0（有反自动化门槛），无法从页面判断是否需手机验证。且违反 HF ToS，账号级风险，**不建议**。
- **HF PRO**：$9/月，8× ZeroGPU 配额（40 min/天）+ 最高队列优先级。约 8-9 张 832×1216/天，是付费最优解。

---

## 六、工具清单（均在 `~/dsh-hanime1/`）

| 脚本 | 用途 |
|---|---|
| `gen.sh "prompt" [outdir] [seed] [engine]` | 统一入口，`auto` 模式按 anima→horde→cf→poll 自动降级 |
| `gen_quota.sh` | 探测四条引擎的实时额度（ZeroGPU 报剩余秒数、Horde 报排队、CF 实测发图） |
| `anima_gen.sh` | Anima 生图，支持 `ANIMA_SPACE` 切换 Space |
| `horde_gen.sh` | AI Horde，默认轮换 4 个模型，自动跳过纯黑审查图 |
| `gen_image.sh` | Cloudflare / Pollinations / HF Space 三引擎 |
| `th_gen.sh` | TensorHub 免登录（匿名 2 次已用尽） |

`gen_quota.sh` 的一个已知限制：Cloudflare GraphQL 的 `neurons` 字段已废弃（返回 `unknown field "neurons"`），`aiInferenceAdaptiveGroups` 的 filter 形状也变了，所以改为**实发一张 4 步最小图**来判定剩余额度——代价是消耗约 189 neurons。
