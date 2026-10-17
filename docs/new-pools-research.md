# 新池调研：免费 img2img 路线（2026-10-17 实测版）

> 目标：找不烧 pollen 的 img2img / 图像编辑通道。
> 本文分两档：**【本机实测】** = 在 Termux 上真的打过请求、有状态码和响应原文；**【仅核实来源】** = 官方页面确认政策，未注册未实测。
> 上一版调研由子代理产出，其中 **3 条结论被本机实测推翻**（HF Inference 免费额度、HF Spaces 免费可用、Replicate 免注册），已在本文件更正。

---

## 一、结论速览（按可用性排序）

| 路线 | img2img | 免费额度 | 本机实测结果 | 可行性 |
|---|---|---|---|---|
| **AI Horde**（已在用） | ✅ | 无限 | ✅ 45–65s 出图，匿名可用 | **高（现役主力）** |
| **Vercel AI Gateway** | ✅ | **$5 / 30 天循环** | 政策已核实，未注册 | **高（最值得接）** |
| **Replicate Try-for-Free** | ✅ kontext-pro | 有限次数 | 集合页确认含 kontext-pro；匿名 API 401 | **中高（需注册）** |
| **fal.ai Sandbox** | ✅ | **15 次/天，无需账户** | 页面原文已核实，未实测调用 | **中高（零门槛试用）** |
| **Claw Hunter Proxy** | ✅ | 声称 1K/天 | 无公共实例，必须自己部署到 CF Workers | **中（要自建）** |
| **Pollinations 匿名档** | ❌ | 1 张/45s | 已证伪 img2img | 仅文生图 |
| **Pollinations 新版** | ✅ kontext-pro | 0.03 pollen/张 | ✅ 可用但烧钱 | 有钱才用 |
| **HF Inference Providers** | ✅ 官方支持 | **已取消** | ❌ 402 no remaining credits | **死** |
| **HF Spaces（ZeroGPU）** | ✅ | 免费额度 | ❌ `exceeded ZeroGPU runs limit` | **死（除非 PRO）** |
| **Gemini 官方 API** | ✅ Nano Banana | **无免费档** | 定价页 Free Tier = Not available | **死（走 web Cookie）** |
| **Together.ai** | ❌ 仅文生图免费 | 无试用，$5 起充 | 第三方核实 | 低 |
| **Pixazo Free API** | ✅ inpainting | 需绑卡或充 $10 解锁 | 未实测 | 低（门槛高） |
| **Novita.ai** | ✅ | ~$0.50 一次性 | 未实测 | 低（额度太小） |
| **Kavel 匿名层** | ❌ 编辑需 Key | 5 credits | 未实测 | 低 |
| **Discord MJ Proxy** | ⚠️ 垫图 | 依赖 MJ 订阅 | 未实测 | 低 |

---

## 二、【本机实测】被推翻的三条「免费」传言

### 2.1 HF Inference Providers —— 免费额度已于 2026-10-08 取消 ❌

本机实测（2026-10-17，token 用户 `elysia2010`）：

| 请求 | 结果 |
|---|---|
| 匿名 `POST router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-Kontext-dev` | **401** |
| 带 token 走 `hf-inference` provider | `400 {"error":"Model not supported by provider hf-inference"}` |
| 带 token 走 `fal-ai` provider（`/fal-ai/fal-ai/flux-kontext/dev`） | **402 `You have no remaining credits. Purchase pre-paid credits ... or subscribe to PRO`** |

模型 provider 映射（`huggingface.co/api/models/black-forest-labs/FLUX.1-Kontext-dev?expand[]=inferenceProviderMapping`）：
`fal-ai`（task=image-to-image）/ `replicate` / `wavespeed` —— **`hf-inference` 根本不支持 Kontext**。

**政策层**：HF 免费账号此前只有 **$0.10/月** routed 额度，2026-10-08 起**取消**；
第三方追踪站已将其除名并注明 "free accounts no longer receive inference credits — the current billing table lists None"。

**PRO（$9/月）才有**：从官方 pricing 页 HTML 解析出 `$2 of included inference credits monthly` + `8× ZeroGPU quota`。

> 结论：**HF 这条免费池已死。** 要复活只有 PRO $9/月（$2 credits ≈ Kontext-dev via fal 约 40 张/月，另加 8 倍 ZeroGPU）。
> 来源：[HF Inference Providers pricing](https://huggingface.co/docs/inference-providers/en/pricing)｜[HF pricing](https://huggingface.co/pricing)｜[除名记录](https://mvalentsev.github.io/awesome-free-ai-coding/providers/huggingface-inference/)

### 2.2 HF Spaces（ZeroGPU Kontext）—— 免费号 ZeroGPU 额度已耗尽 ❌

本机实测：Space `mcp-tools/FLUX.1-Kontext-Dev` **在线**（`runtime.stage = RUNNING`，`zero-a10g`），
API 签名已成功探明：

```
predict(input_image, prompt, seed, randomize_seed, guidance_scale, steps, api_name="/infer") -> (result, seed)
```

但实际调用两次都被拦：

| 认证 | 响应 |
|---|---|
| 匿名 | `You have exceeded your ZeroGPU runs limit. Authenticate with a Hugging Face token for more quota` |
| 带 HF token | `You have exceeded your ZeroGPU runs limit. Subscribe to Hugging Face PRO to get 40 min of ZeroGPU quota a day` |

> 结论：**Space 通道对免费号已封顶**（与 MEMORY 里「ZeroGPU 5min/天、账号级全局共享」一致，额度早被 anima 路线烧完）。
> 但**调用代码已跑通**，只要 HF PRO 或额度重置，`gradio_client` 一行就能调。

### 2.3 Replicate —— 免注册不可用，但 Try-for-Free 确实含 Kontext Pro ⚠️

- 本机实测：匿名 `GET api.replicate.com/v1/models/...` 与 `/v1/predictions` 均 **401**。
- 但官方 [Try for Free 集合页](https://replicate.com/collections/try-for-free) 原文确认：
  **`black-forest-labs/flux-kontext-pro` 在免费集合里**，且 "models you can run **without purchasing credit** after creating a Replicate account"。
- 官方 FAQ 明确："free for a **limited number of runs**"，次数未公开。

> 结论：**注册即可白跑若干次 Kontext Pro**（本项目最想要的那个模型），次数有限但零成本。值得注册。

---

## 三、【最值得接】Vercel AI Gateway —— $5 / 30 天循环，含 Kontext Pro

官方 pricing 页原文（本机抓取核实）：

> Free tier: **Monthly credit $5 / month included**；Model access: **Free Tier eligible models**；
> "Free users (those who haven't made a payment) get **$5 of credits every 30 days**."

**关键发现：`bfl/flux-kontext-pro` 在免费层模型列表里**（`/ai-gateway/models?freeTier=true` 页面含该 id）。
另外免费层还含 `google/gemini-nano-banana-2.1`、`google/gemini-2.5-flash-image`、`openai/gpt-image-2`、`bfl/flux-2-klein-4b` 等 26 个图像相关模型。

- 单价：Kontext Pro **$0.04/张** → **$5 ≈ 125 张/月**（klein-4b 更便宜，约 $0.014/百万像素）
- 认证：Vercel 账号 + AI Gateway API Key，**免费层无需付款**（"those who haven't made a payment"）
- API：OpenAI 兼容（Chat Completions / Images），纯 HTTP，Termux 无障碍
- 限制：免费层有 per-model 速率限制，超了返回 429；**一旦充值就永久失去每月 $5**
- 审查：BFL / Google / OpenAI 各自的 AUP，商业标准，NSFW 大概率被拦

> 来源：[Vercel AI Gateway pricing](https://vercel.com/docs/ai-gateway/pricing)｜[flux-kontext-pro 模型页](https://vercel.com/ai-gateway/models/flux-kontext-pro)

**这是当前最优的「零成本 + 高质量 img2img」通道**：比 pollen（0.03/张，余额只剩 0.2）宽裕一个量级，且循环发放。

---

## 四、【零门槛】fal.ai Sandbox —— 15 次/天，但只能网页手动（程序化需 Key）

本机抓取页面原文（`fal.ai/sandbox`）：

> **"15 free generations today. No account needed."**
> 示例含 **Edit Multi Images**（4 models，图生图编辑）。

**本机实测（关键，推翻了「匿名可编程」的乐观判断）**：

```
POST https://fal.run/fal-ai/nano-banana-2/edit   （匿名，带 image_urls）
→ 401 {"detail":"Cannot access application \"fal-ai/nano-banana-2\". Authentication is required to access this application."}
```

页面内部字段也印证：`sandboxGuestRequest` / `sandboxSkipBilling` / `sandbox-free-credits-experiment`
都是**前端 UI 会话**里的标记（每条记录 `"sandboxGuestRequest":false`），不是公开 API 的免认证开关。

- img2img：✅ Sandbox UI 里确实能编辑（`fal-ai/nano-banana-pro/edit`、`fal-ai/nano-banana-2/edit` 都在模型表里）
- 程序化：❌ **匿名 REST 一律 401**，必须注册拿 API Key
- 注册赠金：官方 pricing 页未标注，第三方说法不统一，**未核实**

> 来源：[fal.ai Sandbox](https://fal.ai/sandbox)｜[fal.ai pricing](https://fal.ai/pricing)

**用法建议**：15 次/天只能在浏览器里手动点。要脚本化必须先注册。

---

## 五、【要自建】Claw Hunter Proxy —— CF Workers，OpenAI 兼容，声称 1K/天

README（本机抓取）核心事实：

- Cloudflare Workers 部署，**OpenAI 兼容**，自带 Web UI
- 模型表：`gpt-image-2`（OpenAI）T2I ✅ / **I2I ✅**，`nano-banana-2`（Google）T2I ✅ / **I2I ✅**，`kling-v3` 仅 T2I
- "Free forever — 3 AI models, unlimited relay rotation, no credit card required"
- **没有任何公共实例**：README 里所有 URL 都是 `clawhunter-proxy.YOUR-SUBDOMAIN.workers.dev`，必须自己 `wrangler deploy`
- 机制：多平台 relay 轮询（Vercel + Deno + Netlify）+ token 池自动刷新

> 来源：[loves96617665/clawhunter-proxy](https://github.com/loves96617665/clawhunter-proxy)

**判断**：技术上可行（本机有 CF 账号），但「1K/天」是 README 自述、依赖上游非官方转发，稳定性不由自己控制。属于「值得一试但不做主力」。

---

## 六、其余候选（仅核实来源，未实测）

### 6.1 Gemini 官方 API —— 图像生成无免费档 ❌
官方 pricing 页（2026-10-07 更新）把**每个** Nano Banana 模型的 Free Tier 标为 **"Not available"**，
最便宜 $0.0336/张。免费只能走 **Gemini 网页/App（算力额度，5h 刷新 + 周上限）**、
**AI Mode（25 张/24h）**、**Google Flow（50 credits/天）**。
→ 与本项目已排期的「Gemini web 反代 + Cookie」路线一致：**要免费用 Nano Banana 只能走 web Cookie**。

### 6.2 Together.ai —— 无免费试用，最低 $5 充
第三方免费额度追踪站确认无 free trial；图像侧 `FLUX.1-schnell-Free` 仅文生图。

### 6.3 Pixazo Free API —— 免费 inpainting，但需绑卡或充 $10 解锁
免费层含 SD Inpainting + SD1.5/SDXL img2img，门槛在解锁条件。

### 6.4 Novita.ai —— ~$0.50 一次性额度
有明确 `/v3/async/img2img` 端点和 `qwen-image-edit` 等编辑模型，但额度只够验证。

### 6.5 Kavel —— 匿名 5 credits，编辑功能需 Key
匿名层额度只够 1 张文生图，img2img 被锁。

### 6.6 Discord Midjourney Proxy —— 不是真免费
代理软件免费，底层依赖 Midjourney 付费订阅；只支持「垫图」间接图生图。

---

## 七、行动建议（按投入产出）

**立刻可做（0 成本，0 注册）**
1. **fal.ai Sandbox** 手动试 15 次/天 —— 先看 nano-banana / gpt-image-2 的编辑效果对不对路。

**需要一次注册（0 成本，收益最大）**
2. **Vercel AI Gateway** —— 注册 → 建 AI Gateway Key → 用 `bfl/flux-kontext-pro` 跑 img2img。
   **$5/30 天 ≈ 125 张 Kontext Pro**，这是本项目最该接的一条。
3. **Replicate** —— 注册后在 Try for Free 里跑 `black-forest-labs/flux-kontext-pro`，白嫖有限次数的高质量编辑。

**需要花钱（等拍板）**
4. **HF PRO $9/月** —— $2 credits + 8× ZeroGPU。ZeroGPU 8 倍对 anima 路线是直接加强，顺带复活 Kontext Space。

**不建议**
5. HF 免费 Inference / HF Spaces 免费 ZeroGPU（均已封顶）、Gemini API（无免费档）、Together（无试用）、
   Pixazo（要绑卡）、Novita（$0.50 太少）、Kavel（编辑需 Key）、MJ Proxy（假免费）。

**继续白嫖的现役主力**
6. **AI Horde**（无限、无审查、45–65s）+ **Pollinations 匿名档**（文生图 1 张/45s）。

---

## 附：pollen 侧可做的零成本回血

本机实测 quests 接口：194 completed / 22 available / 3 coming_soon。
`POST /account/quests/rewards/{id}/claim` 用 device key → **403 `Reward claims require a dashboard session`**（复测确认）。
API 调用能触发 `use_image_model`，但 `use_text_model` / `use_community_model` 对 API 调用**不记账**（Classic 与 gen 两种端点、带 Referer、community 模型全试过，状态停在 open）。

→ 只能在**手机浏览器登录 enter.pollinations.ai** 手动 claim，可拿约 **2–3 pollen**（`connect_polli_cli` +1、`join_discord` +1、`use_agent` +0.25 等）。

---

*最后更新：2026-10-17。标【本机实测】的条目均有本机请求记录；标【仅核实来源】的未注册未实测。*
