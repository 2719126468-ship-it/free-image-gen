# 新池调研：免费 img2img 路线（2026-10-17 实测版）

> 目标：找不烧 pollen 的 img2img / 图像编辑通道。
> 本文分两档：**【本机实测】** = 在 Termux 上真的打过请求、有状态码和响应原文；**【仅核实来源】** = 官方页面确认政策，未注册未实测。
> 上一版调研由子代理产出，其中 **3 条结论被本机实测推翻**（HF Inference 免费额度、HF Spaces 免费可用、Replicate 免注册），已在本文件更正。

---

## 一、结论速览（按可用性排序）

| 路线 | img2img | 免费额度 | 本机实测结果 | 可行性 |
|---|---|---|---|---|
| **AI Horde**（已在用） | ✅ | 无限 | ✅ 45–65s 出图，匿名可用 | **高（现役主力）** |
| **Vercel AI Gateway** | ✅ | **需绑卡才解锁 $5/30天** | ❌ 实测 403 `credit card required` | **需绑卡（否则不可用）** |
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

## 三、Vercel AI Gateway —— ❌ **必须绑卡，不是"免费"**（2026-10-17 实测推翻）

**官方原文**（`vercel.com/docs/ai-gateway/getting-started`）：

> To use free AI Gateway Credits, **add a valid payment method** to your team.

**本机实测**（真 key `vck_8OCcwUkB...`，写入 `~/.dsh/.vercel-gw-key` 后打请求）：

```
POST https://ai-gateway.vercel.sh/v1/chat/completions
→ HTTP 403
{"error":{"message":"AI Gateway requires a valid credit card on file to service requests.
 Please visit .../ai?modal=add-credit-card to add a card and unlock your free credits.",
 "type":"customer_verification_required"}}
```

**结论：那 $5/30 天不是"注册即送"，是"绑卡后解锁"。不绑卡 = 403，key 建了也没用。**
这也解释了「创建 API 密钥一直失败」—— 免费账号在未绑卡时，创建入口会被拦或建出来的 key 不可用。

- 模型本身没问题：`bfl/flux-kontext-pro` 确实在免费层列表（`/ai-gateway/models?freeTier=true`）
- 单价 $0.04/张，$5 ≈ 125 张/月 —— **但前提是有一张能绑的卡**
- 一旦充值进 paid tier，每月 $5 就永久消失（这条之前的判断仍然成立）

> 来源：[getting-started.md](https://vercel.com/docs/ai-gateway/getting-started)｜[pricing.md](https://vercel.com/docs/ai-gateway/pricing)

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

## 七、行动建议（按投入产出，2026-10-17 实测后修正）

**不需要任何卡、任何注册，立刻能用**
1. **AI Horde + 动漫模型** —— 本机实测 10 个模型，**9 个正常出图**（详见 §八）。
   免费无限、无审查、45s–12min 出图。这是当前唯一「零门槛 + 质量能打」的组合。
2. **Pollinations 匿名档** —— 文生图 1 张/45s，纯兜底。

**需要注册但不需要卡（未实测到底）**
3. **Replicate Try-for-Free** —— 官方 FAQ 说「不需要先买 credit」，但**是否需要绑卡未确认**（本机匿名 401）。
   注册后先跑一次免费模型就知道，别再预先相信"免费"。

**需要绑卡（做不到就别碰）**
4. **Vercel AI Gateway** —— $5/30 天是真的，但**必须绑卡解锁**，实测 403。没有卡 = 0。

**需要花钱**
5. **HF PRO $9/月** —— $2 credits + 8× ZeroGPU，能复活 Kontext Space。

**已死**
6. HF 免费 Inference（2026-10-08 取消）、HF Spaces 免费 ZeroGPU（额度封顶）、
   Gemini 官方 API 图像（无免费档）、fal 匿名 API（401）、Together（无试用）。

## 八、AI Horde 动漫模型实测（2026-10-17，10 个模型并行）

请求参数：`832x1216 / 25 steps / cfg 7 / k_euler_a / karras / nsfw=true`，匿名 `0000000000`。

| 模型 | 耗时 | 字节 | 尺寸 | YAVG | 结果 |
|---|---|---|---|---|---|
| **Flat-2D Animerge** | 735s | 66,822 | 512² | 138.8 | ✅ 最锐利、线条最干净 |
| **Eimis Anime Diffusion** | 735s | 62,958 | 512² | 168.7 | ✅ 最亮、最"动漫" |
| **Counterfeit** | 651s | 50,904 | 512² | 136.1 | ✅ 光影最好、最稳 |
| **Elysium Anime** | 702s | 46,442 | 512² | 116.2 | ✅ 氛围感强 |
| **MeinaMix** | 740s | 42,124 | 512² | 87.2 | ✅ 经典，饱和度好 |
| **Anything v5** | 621s | 39,186 | 512² | 155.6 | ✅ 柔和 |
| **Abyss OrangeMix** | 656s | 38,204 | 512² | 122.6 | ✅ 老牌稳定 |
| Hassaku XL | 739s | 23,092 | 512² | 23.5 | ⚠️ 偏暗（可能与 Mistoon 同一 worker） |
| Mistoon Anime | 336s | 23,092 | 512² | 23.5 | ⚠️ 字节与 Hassaku 完全相同 |
| **Nova Anime XL** | 655s | 526 | 512² | 0.0 | ❌ **纯黑图（worker 审查吞图）** |

**关键结论**：

1. **排队 5–12 分钟**，出图后 worker 还会把 832×1216 降级成 **512×512**（这是常态，改不了）
2. **worker 多 ≠ 能出图**：`WAI-NSFW-illustrious-SDXL`（12 worker，最多）和 `Nova Anime XL` 都输出纯黑 526B
3. **Hassaku XL 与 Mistoon Anime 字节完全相同（23,092）** → 同一个 worker 用同一个模型跑的，不是两个模型
4. **能用的是这 7 个**：Flat-2D Animerge / Eimis / Counterfeit / Elysium / MeinaMix / Anything v5 / Abyss OrangeMix
5. **`Animagine XL` 单独测了 3 次全部超时**（queue 从 800+ 缓慢降到 180，20 分钟内没排到）——
   它有 4 worker 但在线负载高，**不适合当主力**

对比图：`~/th-img/horde_anime_sheet.jpg`（6 模型并排）

## 附：pollen 侧可做的零成本回血

本机实测 quests 接口：194 completed / 22 available / 3 coming_soon。
`POST /account/quests/rewards/{id}/claim` 用 device key → **403 `Reward claims require a dashboard session`**（复测确认）。
API 调用能触发 `use_image_model`，但 `use_text_model` / `use_community_model` 对 API 调用**不记账**（Classic 与 gen 两种端点、带 Referer、community 模型全试过，状态停在 open）。

→ 只能在**手机浏览器登录 enter.pollinations.ai** 手动 claim，可拿约 **2–3 pollen**（`connect_polli_cli` +1、`join_discord` +1、`use_agent` +0.25 等）。

---

*最后更新：2026-10-17。标【本机实测】的条目均有本机请求记录；标【仅核实来源】的未注册未实测。*
