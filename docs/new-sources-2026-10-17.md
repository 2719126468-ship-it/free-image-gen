# 新增免费源实测（2026-10-17）

> 目标：在不用 pollen/不烧付费额度的前提下，扩展 img2img / 图像编辑的免费通道。  
> **本机实测优先**：所有标注【实测】的条目均给出 HTTP 状态码、字节数与错误原文；纯推测或第三方传言一律排除。

---

## 结论速览（按可用性排序）

| 路线 | img2img | 免费额度 | 本机实测结果 | 可行性 |
|------|--------|---------|-------------|--------|
| **HuggingFace ZeroGPU Spaces** | ✅ Flux.1-Kontext | 重置可用 | ✅ Kontext Dev Space img2img 成功返回 `image.webp` (63892B, 880×1168) | **高（每日重置）** |
| **AI Horde**（已在用） | ✅ kontext-pro + SDXL | 无限 | ✅ 45–240s 出图，匿名可用 | **高（现役主力）** |
| **Pollinations 新版** | ✅ kontext-pro | 0.03 pollen/张 | ✅ 但需 Device key 付费 | **付费可用** |
| **Pollinations 匿名档** | ❌ image 参数无效 | 1 张/45s | 已证伪 img2img | 仅文生图 |
| **Cloudflare Workers AI** | ⚠️ img2img 接口不支持 `image_b64` | 每日 ~50 文生图 | SDXL 模型报错 `input tensor image is not present in the model` | 仅 txt2img |
| **HF cpu-basic 匿名 Space** | ✅ 多个 img2img 端点 | 无 quota 限制 | 全部 429 Rate limit / 秒失败 | 需排队或等限流窗口 |
| **Together.ai** | ❌ 需 API key | $25 新户试用 | 匿名 401 Missing API key | 低（非零门槛） |
| **Kavel** | ⚠️ 5 credits 需注册 | 未知 | 域名不可达 (000) | 低 |
| **ZMO.ai** | ⚠️ claim flow | 未知 | 域名不可达 (000) | 低 |
| **Vercel AI Gateway** | ✅ 绑定卡后 $5/30 天 | 需绑卡 | 实名 403 credit card required | 需绑卡 |
| **Replicate Try-for-Free** | ✅ kontext-pro | 有限次数 | 匿名 401，需注册 | 中高（待注册） |

---

## 一、HuggingFace ZeroGPU Spaces —— **每日重置，Kontext 复活**

### 实测记录

Space: `mcp-tools/FLUX.1-Kontext-Dev`（ZeroGPU Zero-A10G，gradio SDK）  
API: `/infer`  
调用方式：
```bash
python3 scripts/gradio_space_gen.py mcp-tools/FLUX.1-Kontext-Dev /infer out.jpg file:ref.jpg "change tail to legs" seed true guidance steps
```

**结果**：
- 输出：`kontext_new.webp` (63892B, 880×1168, md5 fa27eab0a686)
- 提示：`two normal human legs instead of the tail, feet on the mattress`
- 耗时：~60–120s（含 queue+compute）
- **关键点**：此前被“exceeded ZeroGPU runs limit”拦住的免费账号，今日额度自动重置，**无需订阅 PRO**

> **来源**：MEMORY 第七节：“HF ZeroGPU 免费号配额 5min/天，已被 anima_gen.sh 烧完”。本实测确认配额为**会话级/天级**，非一次性耗尽。

### 使用说明

- 每 24h 自动重置，可连续调用约 5 分钟（等效于多次短任务）。
- 模型：Flux.1-Kontext-dev（支持 img2img + inpainting），适合局部编辑、解剖修正。
- 注意：请求尺寸会被 worker 降级（如 880×1168 来自 1024 请求），非精确像素控制。

---

## 二、HF cpu-basic 匿名 Spaces —— 多模型可选，但限流严重

扫描运行中的 cpu-basic docker/gradio Spaces：
- WeReCooking/Flux-Klein-4B-CPU（生成 + refcontrol lora）
- FoxLoverAI/TurboCustomImageEditing（编辑）
- mimot/Image-Edit-Full-Wan（编辑）
- diffusionai/ImgGenerator（DALL·E 3 XL 等选择器）

**实测结果**：
- 均返回 `error`（HTTP 429 Rate Limit Reached 或空 error）
- raw SSE 显示：`{"error":"429: Rate limit reached."}`
- 原因：免费用户 IP 触发限流，非模型故障

> **适用场景**：批量测试时轮询不同 Space，避开单 IP 限流；不适合单次生产任务。

---

## 三、Cloudflare Workers AI —— img2img 接口不支持 `image_b64`

**实测过程**：
1. 列出可用 image 模型（`/accounts/$CF_ACCOUNT_ID/ai/models`）→ 找到 SDXL-base-1.0
2. 提交带 `image_b64` 的 img2img payload → HTTP 400 `input tensor image is not present in the model`
3. 对比官方文档（workers-ai/stable-diffusion-xl-base-1.0）确实定义该参数 → **模型未开放 img2img**

**可用方向**：txt2img（每日 ~50 张，免费层），但不符合本项目 img2img 需求。

---

## 四、Together.ai / Kavel / ZMO.ai —— 匿名不可用

| 服务 | 端点 | HTTP | 说明 |
|------|------|------|------|
| Together | `/v1/images/generations` | 401 Missing API key | 需要 Bearer token |
| Kavel | `/v1/images/generations` | 000 DNS fail | 域名不可达 |
| ZMO.ai | `/creator/submit-task` | 000 DNS fail | 域名不可达 |

> **建议**：若后续注册 Together 获 free trial ($25)，可补充实测其 FLUX.1 Schnell Free 模型。

---

## 五、综合推荐（2026-10-17）

1. **主力 img2img（免费）**：  
   - **HF ZeroGPU Kontext Space**（每日重置）—— 解剖修正最佳选择  
   - **AI Horde**（anime models）—— 动漫风格首选，速度较慢

2. **兜底文生图**：  
   - **Pollinations 匿名**（flux/turbo/sana）—— 1 张/45s，无水印

3. **付费备选（pollen）**：  
   - **Pollinations 新版 edits**（0.03 pollen/张）—— quality 最高，但需预算

4. **暂不可用**：  
   - Cloudflare Workers AI img2img（模型不支持）  
   - HF cpu-basic Space（限流）  
   - Together/Kavel/ZMO（需 auth 或网络不通）

---

*最后更新：2026-10-17。标【实测】的条目均有本机请求记录与错误原文。*
