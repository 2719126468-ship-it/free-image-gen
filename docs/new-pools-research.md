# 新池调研：免费 img2img 候选路线（2026-10-17）

> 背景：pollen 额度紧张（用户两次叫停烧额度），需要找不花钱或注册即送的 img2img 池。
> 本文档所有「已核实」条目都有一手来源或本机实测；标「未核实」的未完成查证。
> 调研子代理超时未收尾，本文档由主会话基于已抓取的官方页面汇总。

---

## 1. Google AI Studio / Gemini API（Nano Banana 官方）—— ⚠️ 推翻「免费」传言

**结论：Gemini API 的图像生成（所有 Nano Banana 模型）没有免费档。**

- 官方定价页（2026-10-07 更新）把每个 Nano Banana 模型的 Free Tier 都标为 **"Not available"**，包括 `gemini-nano-banana-2.1`。API 免费档只覆盖部分文本模型。
- 最便宜的图像输出：Nano Banana 2.1 / 2 Lite，**$0.0336/张（1K）**；Nano Banana Pro $0.134/张。
- 传言对照：
  - "API 免费档 500 张/天" ❌ 不实；
  - "AI Studio 免费 500–1000 张/天" ❌ 官方只说 "modest quota"，且 Nano Banana 列在 AI Pro 付费解锁的模型里。
- **免费能用 Nano Banana 的地方（非 API）**：
  - Gemini 网页/App：免费号可用 Nano Banana 2 / 2 Lite，按"算力额度"计（5 小时刷新 + 周上限），无公开张数；
  - Google AI Mode（搜索）：免费 **25 张/24h**；
  - Google Flow：**50 credits/天**，默认模型 Nano Banana 2 Lite 免费。
- **对本项目的意义**：这与已排期的「Gemini web 反代（gw2api + Cookie）」路线完全吻合——**要免费用 Nano Banana 只能走 web 端 Cookie，API 无免费**。AI Mode 25 张/24h 是新的可编程候选（走搜索 AI Mode 需登录态，未测）。
- 来源：[Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing)、[Rate limits](https://ai.google.dev/gemini-api/docs/rate-limits)、[Nano Banana 免费额度汇总（laozhang.ai，2026-10-08 更新）](https://blog.laozhang.ai/en/posts/gemini-image-generation-free-limit-2026)

## 2. Replicate —— ❌ 无免费额度（匿名 API 401，未证实注册赠金）

- 本机实测：`GET https://api.replicate.com/v1/models/black-forest-labs/flux-1.1-pro` 和 `/v1/predictions` 匿名均 **401**（2026-10-17 实测）。
- 官方 billing 文档（https://replicate.com/docs/topics/billing）正文未能完整抓取（页面 JS 渲染）。
- 注册赠金：**未核实**（有历史说法称不再送免费 credit，以官方页面为准）。
- 评级：**低**（需付费或信用卡绑定，匿名无任何可用面）。

## 3. fal.ai —— ⚠️ 有 img2img 模型端点，免费额度未核实

- 官方定价页（https://fal.ai/pricing）确认存在 `flux-3/edit-image`、`nano-banana/edit` 等 img2img 端点，按量计费。
- 注册赠金：**未核实**（定价页未标注免费额度；有第三方汇总称 fal 有少量试用 key，需注册实测）。
- 评级：**中**（模型全、端点标准，但免费面存疑，注册后一测便知）。

## 4. Together.ai —— ❌ 无免费试用（第三方核实）

- 第三方免费额度追踪站（https://benchlm.ai/free-tier/together）：**无 free trial，最低充值 $5**，动态限额。
- Together 主打文本 LLM，图像管线（FLUX 等）需付费 key。
- 评级：**低**。

## 5. Pollinations quests —— ✅ 本机已实测，回血通道确认（但 claim 卡 dashboard）

- 本机实测（2026-10-17，Device key）：
  - quests 列表：194 个 `completed`、22 个 `available`、3 个 `coming_soon`；
  - `available` 里理论合计 **121 pollen**，其中大额：`top_up_100_since_launch` +50、`app_pollen_10` +10、`app_listed` +10、`github:issue:17712/17689` 各 +10、`honey_census` +5、`merged_pr` +5 等。
  - **claim 必须走 dashboard 会话**：`POST /account/quests/rewards/{id}/claim` 用 device key → **403 `Reward claims require a dashboard session`**（已复测）。
  - 多数大额 quest（top_up_* / app_* / github:issue:*）是**给充值过/贡献过的账号的回赠**，本账号（未充值）大概率只满足 `connect_polli_cli` +1、`join_discord` +1、`use_*` 系列 +0.25×4。
  - **quest 事件触发机制实测**：API 调用能触发图像类（`use_image_model` 此前已 completed），但**文本类 quest（use_text_model / use_community_model）对 API 调用不记账**——Classic `text.pollinations.ai/openai` POST/GET、带 Referer、`gen.pollinations.ai/v1/chat/completions` 调 `community/morriszdweck/glm-5.3-flash-free`（调用成功、0 消耗）均试过，状态停在 `open`。推测文本类事件只认 dashboard 网页端会话。
- **可行动项**：在手机浏览器登录 enter.pollinations.ai dashboard，手动点 claim，`connect_polli_cli` +1 + `join_discord` +1 + `use_agent` +0.25 等约 **2–3 pollen** 可立即入账（够 ~66 张 klein-4b 或 ~70 张 kontext-pro？——不够，够约 6–8 张 kontext-pro）。
- 评级：**高（立即执行，零消耗）**。

## 6. AI Horde —— ✅ 已在用，额度本质「无限」

- 匿名 `0000000000` 无限排队生图，本机当天实测 45–65s/张（白天 worker 充足时）。
- kudos 机制：匿名号 kudos 为负也**不影响出图**，只影响排队优先级；想提权可注册账号攒 kudos。
- 本轮新发现（已写入 MEMORY）：PonyXL 是 worker 端确定性渲染（换 AlbedoBase XL 正常）；illustrious-SDXL 会吞成纯黑图（YAVG=0.0）。
- 评级：**高（已是主力免费池）**。

## 7. Pollinations 匿名档文生图 —— ✅ 持续可用（与 img2img 无关，备胎）

- 1 张/45s/IP，模型 flux/turbo/sana。匿名档 img2img 已证伪（MEMORY 4.1）。
- 评级：**高（纯文生图兜底）**。

## 8. HF Inference Providers（router）—— ✅ 本机已实测，免费面已死，PRO 才有月度额度

本机实测（2026-10-17，token `elysia2010`）：

- 匿名无 token：`POST https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-Kontext-dev` → **401**；
- 带 token 走 hf-inference provider：`{"error":"Model not supported by provider hf-inference"}`（Kontext-dev 只映射到 fal-ai / replicate / wavespeed，task=image-to-image）；
- 带 token 走 fal provider：`POST https://router.huggingface.co/fal-ai/fal-ai/flux-kontext/dev` → **402 `You have no remaining credits. Purchase pre-paid credits ... or subscribe to PRO`**。

**关键行业事实（2026-10-08 生效）**：HF 免费账号**不再发任何 inference credits**
（此前是 $0.10/月；第三方追踪站 awesome-free-ai-coding 于 10-08 将其除名并注明
"free accounts no longer receive inference credits — the current billing table lists None"）。

**PRO 订阅（$9/月）**：`$2 of included inference credits monthly`（本机从官方 pricing 页
HTML 解析确认）+ 8× ZeroGPU 配额。ZeroGPU 8 倍配额对 anima 路线是直接加强。

**结论**：HF router 这条免费池已死；要复活只有 PRO $9/月（得 $2 credits + 8× ZeroGPU，
折算 Kontext-dev via fal 约 $0.05/张 → 约 40 张/月 + ZeroGPU 大量生图）。**等用户拍板**。

- 来源：[HF Inference Providers pricing](https://huggingface.co/docs/inference-providers/en/pricing)、
  [HF pricing 页（PRO $2 credits 解析）](https://huggingface.co/pricing)、
  [awesome-free-ai-coding 归档记录（2026-10-08 除名）](https://mvalentsev.github.io/awesome-free-ai-coding/providers/huggingface-inference/)

## 9. 未完成查证的候选（子代理超时，留待下轮）

| 候选 | 状态 | 下一步 |
|---|---|---|
| Novita.ai 注册赠金（yangmao.ai 称有免费额度） | 未核实 | 注册实测 |
| getimg.ai 100 免费 credit 是否开放 API | 未核实 | 注册实测 |
| Runware / BFL 官方 API 免费面 | 未核实 | 查官方 pricing |
| HF Spaces 非 ZeroGPU 的 kontext/omni-gen Space | 未核实 | gradio_space_gen.py 扫 Space |
| AI Mode 25 张/24h 可编程性 | 未核实 | 需 Google 登录态，浏览器侧测试 |
| Discord/TG bot 免费 img2img 通道 | 未核实 | 找 bot + 测试 |

---

## 结论（本轮行动建议）

1. **零成本立即可做**：手机浏览器登录 enter.pollinations.ai 把 available 的小额 quest 手动 claim（约 2–3 pollen 回血）；
2. **主线不变**：Gemini web Cookie（gw2api 已就绪）是唯一 Nano Banana 免费通道，AI Mode 25 张/24h 是补充；
3. **主力免费池**继续 AI Horde + Pollinations 匿名档（文生图）；
4. **HF router 免费面已死**（2026-10-08 起），PRO $9/月才有 $2 credits + 8× ZeroGPU，等用户拍板；
5. 注册类赠金（fal / Novita / getimg）等用户拍板要不要注册（要邮箱）。
