# 项目记忆文档 (MEMORY.md)

> 最后更新：2026-10-23 21:05（第 17 次修订：★ **nvidia-smi 在 Kaggle 双卡上解析翻车**（`could not convert string to float: '15360 \nTesla T4'`，异常被吞→静默退回 CPU 档）；GPU 检测全面改 `torch.cuda` API，双卡按单卡显存判断；桩件 4/4）。第 16 次修订：★ `examples/anima_kaggle.ipynb` 适配完成（BUILD=kg1，裁掉 sdcpp/视频，路径/隧道/依赖全部按 Kaggle 改，桩件回归通过）；Kaggle 实跑 22.1s/张已确认，仍缺加载秒数+sd-turbo+GPU 小时；本机新增 `~/.dsh/.kaggle-url` 等价通道；适配提交 `b70f834`）。第 15 次修订：★ pollen 到期前探测 —— klein-4b 出 2 张创作候选（768×1024，md5 不同）、flux.1-schnell 0.002 确认可付、余额读数通了（4.703，实耗 0.017/0.03）；Kaggle 验证卡在需手机验证+浏览器操作，只交付了 `examples/kaggle_sdxl_probe.ipynb`，**无实测数据**）。第 14 次修订：Device key 直付复测 kontext-pro→401 / klein-4b→200；Agnes t2i 出图、i2i 503；Claw Hunter 部署受 workerd/android 阻；收尾提交 `0c97d69`）。第 13 次修订：★ 新增 4.10 + routes.md 第十三节「2026-10 新增免费 API 源实测」——CF 额度已恢复并出真图、NIM/Agnes 端点与 401 原文坐实（待 key）、Prodia 判死、Modal 降级；特性提交 `500b295`，docs 收尾提交 `365c78c`）
> 目标读者：后续参与本项目的 AI 编程助手（Codex / DSH / Claude）
> 用途：新开会话先读此文档恢复上下文，省 Token 且防失忆。

---

## 一、项目概况

- **项目名称**：free-image-gen — 免费 AI 生图/图生图路线调研与工具集
- **运行环境**：Android 10 + Termux（无 root，arm64，Python 3.14，无 GPU）
- **Git 仓库**：`~/free-image-gen`，远程 `github.com/2719126468-ship-it/free-image-gen`，分支 `main`，**每轮任务结束必须 commit + push**
- **核心文档**：`docs/routes.md`（所有实测结论、错误原文、配额机制，1–12 节）
- **当前 HEAD**：`bdafdb3`（★ v6 bf16 自动探测 + cell8 精度基准；`scripts/sdcpp_colab.sh` + `scripts/modal_sdxl.py`）

### 目录结构
```
~/free-image-gen/
├── MEMORY.md              ← 本文件
├── README.md              ← 路线速览（txt2img + img2img 两张表）
├── docs/
│   ├── routes.md          ← 完整实测调研（12 节，权威）
│   ├── new-pools-research.md ← 新池调研（含被实测推翻的 3 条传言）
│   ├── colab-free-tier-reality.md / colab-t4-fix.md / cpu-tier-model-matrix.md
│   │                       ← Colab 线专项：免费档现实 / T4 修复史 / CPU 模型矩阵
│   └── new-sources-2026-10-17.md
├── examples/
│   └── anima_colab.ipynb  ← ★ Colab 一次成型版（9 格，GPU 三档 + CPU 五预设 + 视频）
├── plugins/
│   └── dsh-colab-gen/     ← ★ DSH 插件（工具名 colab_gen，已装 web profile；改码需重启会话）
└── scripts/
    ├── vercel_img.py      ← Vercel AI Gateway img2img（**需绑卡**，实测 403，封存待用）
    ├── replicate_edit.py  ← ★ Replicate Try-for-Free img2img（有限次数）
    ├── nvidia_nim_gen.py  ← ★ NVIDIA NIM 文生图（免费 1000 credits/月，待 key）
    ├── agnes_gen.py       ← ★ Agnes AI（免计费 + **支持 img2img**，待 key）
    ├── novita_gen.py      ← ★ Novita 异步任务式文生图（待 key）
    ├── segmind_gen.py     ← ★ Segmind 文生图（x-api-key，待 key）
    ├── together_gen.py    ← ★ Together FLUX.1-schnell-Free（待 key）
    ├── clawhunter_gen.py  ← ★ Claw Hunter Worker 客户端（部署待桌面端；读 ~/.dsh/.clawhunter-url）
    ├── pol_anon.py        ← ★ 匿名档文生图（零 key）
    ├── pol_edit.py        ← ★ 新版 API img2img（pollen key）
    ├── horde_img2img.py   ← ★ Horde img2img（免费无审查，排队久）
    ├── horde_gen.sh       ← Horde 文生图（多模型轮换）
    ├── perchance_gen.py   ← Perchance 逆向（卡 Turnstile）
    ├── kontext_edit.py    ← HF router kontext（已 402 无额度）
    ├── gen.sh             ← 统一入口 auto 降级
    ├── gen_quota.sh       ← 各引擎实时额度探测
    ├── anima_gen.sh       ← HF ZeroGPU Anima
    ├── gen_image.sh       ← Cloudflare / Pollinations / HF Space
    ├── gradio_space_gen.py← 通用 gradio Space 调用
    ├── space_gen.sh       ← 非 ZeroGPU Space
    ├── colab_gen.sh       ← Google Colab
    └── th_gen.sh          ← TensorHub（匿名 2 次已用尽）
```

---

## 二、当前创作任务（进行中）

**目标**：把参考图 `/sdcard/Pictures/1791021867560.jpg`（蓝发女仆装美人鱼趴在床上）img2img 成
**两条正常人类腿，膝盖分开，双脚踩在床垫上**，保留发型/服装/姿势/构图，
风格「日系二次元写实」，审核宽松，解剖清晰。

- 工作副本：`~/tmp/ref_mermaid.jpg`（768×1024，142702B）
- **★ 2026-10-24 用户改口：先放下人鱼图，改要「好看的图片、擦边即可、不用 NSFW」**，并明确跳过 sd-turbo 验证。
  已在 Kaggle（animagine fp16，T4 单卡 14.6GB）出 **6 张 832×1216 @28 步**，耗时 32.0–38.0s/张，
  1.23–1.54MB，luma 106–149，**md5 全不同**，落 `~/th-img/look/`（01 湿白衬衫海边 / 02 黑蕾丝泳池 /
  03 一字肩毛衣晨光 / 04 旗袍霓虹夜街 / 05 运动内衣健身房 / 06 薄纱海边逆光）。
- **★ 2026-10-23 新增一轮（到期前 pollen，2 张，新方向：人类腿/膝分开/脚踩床垫，中性措辞，未复述任何已否决方案）**：
  `~/th-img/klein_create_1.jpg`（768×1024 / 141485B / md5 `19a295b8…` / luma 152.0）｜
  `~/th-img/klein_create_2.jpg`（768×1024 / 133580B / md5 `7c8edab4…` / luma 153.2，prompt 变体加 relaxed pose + soft natural lighting）。
  模型均为 `black-forest-labs/flux.2-klein-4b`（0.005/张）。**两图 md5 不同，非缓存**。用户尚未选定。
- **状态：用户尚未选定任何一版**。更早的候选（全在 `~/th-img/`，不再新增）：
  - 第一轮 k2（脚踩地）/ k6（双腿全上床）/ k7（脚踝交叉）——对比图
    `kontext_pick.jpg`（3 图带标签，1320×638）+ `kontext_sheet.jpg`（9 图拼版）
  - 第二轮 fix_A / fix_B / fix_C + pose_P1 / pose_P2 / pose_P3（显式"坐着、脚掌踩床垫"措辞）
    ——对比图 `round2_sheet.jpg`（ref + A/B/C）
- **⚠️ 2026-10-17 用户第二次下令停止烧额度**（第二轮 6 张 kontext-pro 约 0.18 pollen，
  被点名"别一直用额度"）。**今后任何 pollen 计费调用前必须先问用户**
- **每轮对话前先问用户是否已选定方向，不要重复生成已否决的方案**

---

## 三、免费路线实测总表（2026-10-17）

| 路线 | 认证 | 文生图 | **img2img** | 速度 | 额度 | 审核 |
|---|---|---|---|---|---|---|
| **Vercel AI Gateway** `vercel_img.py` | Vercel 账号 **+必须绑卡** | ✅ | ✅ kontext-pro | 20–60s | $5/30天（**不绑卡实测 403**） | 商业标准 |
| **Replicate Try-for-Free** `replicate_edit.py` | Replicate 账号（免费） | ✅ | ✅ kontext-pro | 20–60s | 有限次数 | 商业标准 |
| **AI Horde** `horde_img2img.py` | 匿名 `0000000000` | ✅ | ✅ `source_image` | **45s–21min** | 无限 | **无** |
| **Pollinations 新版** `pol_edit.py` | pollen key（Device key **10-24 到期**） | ✅ | ✅ **klein-4b 0.005**（kontext-pro 0.03 现 **401**） | 20–40s | 余额 4.703（实测） | **松** |
| **Pollinations 匿名** `pol_anon.py` | 无 | ✅ | ❌ **已证伪** | 1–5s | 1张/45s/IP | 无 |
| Gemini web 反代 | Gemini Cookie | ✅ | ✅ | 快 | 普号免费 | **禁 NSFW** |
| HF ZeroGPU `anima_gen.sh` | HF token | ✅ | — | 1–10s | 5min GPU/天（已耗尽） | 无 |
| **Cloudflare Workers AI**（2026-10-23 复测：**额度已恢复**） | API token | ✅ | — | 4–12s | ~50张/天 | 有过滤 |
| **Kaggle Notebook**（T4 x2，`examples/anima_kaggle.ipynb`，**2026-10-23 端到端已跑通**） | 手动上传 + Settings GPU/Internet | ✅ | ❌ 未移植 | **22–30s/张**（animagine 832×1216@28，实测 29.4/29.6s） | 30 GPU h/周 | 依模型 |
| **NVIDIA NIM** `nvidia_nim_gen.py` | `nvapi-*` | ⚠️待key | — | — | 1,000 credits/月 | 依模型 |
| **Agnes AI** `agnes_gen.py` | Bearer（实测未计费） | ✅ **t2i 出图** | ⚠️ i2i 卡 503 queue full | 12.5s/张 | 无计费字段 | 未知 |
| Claw Hunter Worker `clawhunter_gen.py` | 自控 Worker（零密钥） | ❌ 部署受阻 workerd/android | — | — | 自建 | 未知 |
| Novita `novita_gen.py` | Bearer | ⚠️待key | 有（另端点） | — | 标称 $10/90天 | 未知 |
| Segmind `segmind_gen.py` | `x-api-key` | ⚠️待key | 有 | — | 标称 100/天 | 未知 |
| Together `together_gen.py` | Bearer | ⚠️待key | — | — | FLUX.1-schnell-Free、3 RPM | 有 |
| ~~Prodia~~ | — | ❌ | — | — | — | **判死：api.prodia.com 无 A 记录** |
| HF Inference router | HF token | ❌ | ❌ **402 免费额度已取消** | — | 2026-10-08 起无 | — |
| HF Spaces ZeroGPU Kontext | 匿名/token | — | ❌ **额度封顶** | — | 需 PRO | — |
| Gemini 官方 API | API key | ❌ | ❌ **图像无免费档** | — | $0.0336/张起 | 严 |
| Perchance | 无 | ⚠️ 卡 Turnstile | — | — | 无限 | 无 |
| TensorHub | 无 | ⚠️ 已用尽 | — | — | 2 次 | 无 |

---

## 四、各路线关键实测结论

### 4.1 Pollinations 匿名档（零 key，最稳免费文生图）
```bash
python3 scripts/pol_anon.py <out.jpg> "<prompt>" [flux|turbo|sana] [w] [h] [seed]
```
- 端点：`GET https://image.pollinations.ai/prompt/{prompt}?width=&height=&model=&nologo=true&seed=`
- 限流：**1 张 / 45s / IP**，402 `FREE_LIMIT` 带倒计时，**不是封禁**
- 可用模型：`flux` / `turbo` / `sana`（实际后端都是 sana，Exif `manufacturer=sana`）
- 403 需 key：`kontext` / `nanobanana` / `seedream`
- **两个已证伪的坑（重要，别再踩）**：
  1. `POST /prompt/x` + JSON body **是假的** —— 不管传什么恒定返回同一张 82581B 占位图
     （md5 `58cae173c73d139a735241143aeb4980`，768×768）
  2. **`image` 参数无效** —— A/B 对照（同 prompt 同 seed，一个带 image 一个不带）
     像素差 **0.00/255、0% 像素变化**，md5 差异只是 JPEG 编码噪声。**匿名档没有 img2img**
- 首次请求可能命中缓存；用随机 seed + 唯一 prompt 才拿到真实新图

### 4.2 Pollinations 新版 API（唯一高质量 img2img）
```bash
python3 scripts/pol_edit.py <ref> <out> "<instruction>" black-forest-labs/flux.1-kontext-pro
```
- 端点：`POST https://gen.pollinations.ai/v1/images/edits`（OpenAI 兼容，`image` 收 URL 或 data URI）
- **模型 id 必须全名** `black-forest-labs/flux.1-kontext-pro`；`kontext-pro` 别名 → 400 Invalid model
- 计价：kontext-pro **0.03 pollen/张**，klein-4b 0.005
- 超时要给足：768×1024 quality=high 需 20–40s，curl 60s 会断
- 审核地图：kontext/klein ✅ PASS｜`mai-image-2.6`/`gpt-image-1-mini` ❌ Azure 拦截｜
  `community/*/flux-2-dev-free` ❌ logfare 拦截
- **★ 2026-10-23 Device key 直付复测（拍板数据）**：
  `pol_edit.py … flux.1-kontext-pro` → **HTTP 401** `A valid API key is required. Get one at
  https://enter.pollinations.ai/keys, or buy one with USDC (x402) …`（不是 402，不是 Invalid model）
  **但同一把 key 打 `flux.2-klein-4b`（0.005/张）→ HTTP 200 / 188833B JSON → 141451B PNG / 768×1024 /
  luma 161.8 / md5 `aa13110a6305748d…`**。→ **Device key 能直付，是 kontext-pro 这一档被拒**
  （目录里 kontext-pro 仍在、0.03/张）。要定性「额度阈值 vs 独立鉴权」需再花 0.03 对照，等授权。
  另：`community/*-free` 那批免费 id **已下线**（400 `Invalid model or alias`）；
  余额**时通时不通**：`/account/balance` 有时 200（本轮读到 `{"balance":4.703,"accountBalance":{"total":0.203,...}}`），
  其余 `usage/keys` 仍 401/超时
- **★ 2026-10-23 19:30 到期前探测（实耗 0.017 pollen，余额 4.72→4.703 对账吻合）**：
  * `black-forest-labs/flux.2-klein-4b`（**全名！短 id 报 400 Invalid model**）：edits 200 → 141485B/133580B，
    两张 768×1024，md5 `19a295b8…`/`7c8edab4…`（**md5 不同 = 不是缓存**）；同模型 t2i 也 200（12348B/512²）
  * `black-forest-labs/flux.1-schnell`（**0.002，最便宜**）：GET `/image/<prompt>?model=…` → 200/19700B/512²
  * `black-forest-labs/flux.1-kontext-pro`（0.03）仍 **401**（本轮未再试）
  * **GET `/image/...` 也吃 `Authorization: Bearer`**，不必把 key 拼 query
  * **模型目录是 per-key 视图且会变**：上一轮 386 个（含大量 community），本轮只 148 个，
    `community/MarcosFRG/flux-schnell:paid`、`black-forest-labs/flux-3-image-klein` **不在目录里** → 探测前先拉一次
  * 一次 `HTTP 0 Remote end closed connection` 后重试成功，余额对账显示**未扣费** → 连接层断开可安全重试一次
- **`key_budget` 是预算上限不是余额**：dashboard 建的 visible-chickadee（budget=None）edits 402
  - **2026-10-17 修正**：**Device key（`~/.pollinations/credentials.json` 的 apiKey）可以直接付 edits**，
    实测连续 7 张成功，balance 与 accountBalance 同步下降。**以后统一用 Device key 当 POLLEN_KEY**

### 4.3 AI Horde img2img（免费无限，但慢）
```bash
HORDE_USE_KEY=1 python3 scripts/horde_img2img.py <ref> <out.webp> "<prompt>" "<neg>" [denoise] [model]
```
- 白天恢复 800+ worker（夜间只有 16），实测排队 **243s / 1235s**
- 模型：`WAI-ANI-NSFW-PONYXL`(8 workers) / `AlbedoBase XL (SDXL)` / `SwamPonyXL`
- **坑 1（已破案，2026-10-17 diag 实测）**：PonyXL 同 prompt 下 denoise 0.35/0.99
  输出 md5 完全相同（`7946e480...`/复测 `6e40dbd2` vs `0e6d6d33`）——**根因是 worker 端
  clip_skip=2 + 固定 seed 的确定性渲染**：PonyXL 对 denoise 不敏感（合并后等效全重绘），
  AlbedoBase 正常（两次输出像素差 100%）。**结论：换模型即解决，不是 img2img 失效**
- **坑 2**：`WAI-NSFW-illustrious-SDXL` 两个 denoise 输出 md5 相同且 **YAVG=0.0 纯黑图**（526B），
  是 worker 端审查吞图，不是确定性 —— 用 `ffmpeg signalstats` 或 PIL YAVG<6 判定后直接弃
- **坑 3**：`aihorde.net` 必须带 `Client-Agent` 头，否则 403；`stablehorde.net` 是官方正名
- worker 会把 1024 请求降级回 512×512
- 纯黑图 = worker 审查，用 `ffmpeg signalstats` YAVG<6 判定
- **★ 动漫模型实测（2026-10-17，10 个并行，832x1216/25steps/cfg7/k_euler_a）**：
  | 模型 | 耗时 | YAVG | 判定 |
  |---|---|---|---|
  | Flat-2D Animerge | 735s | 138.8 | ✅ 最锐利 |
  | Eimis Anime Diffusion | 735s | 168.7 | ✅ 最亮 |
  | Counterfeit | 651s | 136.1 | ✅ 光影最好 |
  | Elysium Anime | 702s | 116.2 | ✅ |
  | MeinaMix | 740s | 87.2 | ✅ |
  | Anything v5 | 621s | 155.6 | ✅ |
  | Abyss OrangeMix | 656s | 122.6 | ✅ |
  | Hassaku XL / Mistoon Anime | 739s/336s | 23.5 | ⚠️ 字节完全相同=同 worker |
  | Nova Anime XL | 655s | 0.0 | ❌ 纯黑 |
  | WAI-NSFW-illustrious-SDXL（12 worker 最多） | 253s | 0.0 | ❌ 纯黑 |
  | Animagine XL（4 worker） | 3 次全超时 | — | ❌ 排队 800+ 降不下来 |
  **→ 主力用 Flat-2D / Counterfeit / MeinaMix / Anything v5；worker 多 ≠ 能出图**
- worker 会把 832×1216 请求降级成 **512×512**（常态，改不了）

### 4.4 Gemini web 端反代（最强免费 img2img，缺 Cookie）
- **二进制直接可用**：`gemini-web2api-go` v4.22.0 `linux_arm64`（16MB，静态链接）
  ```bash
  curl -sL -o gw2api https://github.com/zexadev/gemini-web2api-go/releases/download/v4.22.0/gemini-web2api-go_v4.22.0_linux_arm64
  chmod +x gw2api && ./gw2api -port 8083 -admin-token ADM -api-key KEY -db ./gemini.db
  ```
- **生图不走 `/v1/images/generations`（404）**，走 `POST /v1/chat/completions` + `"model":"gemini-image"`
- 匿名态：400 `gemini-image is unavailable without a Google account cookie`
- **Termux 关键坑**：Go 二进制找不到 `/etc/resolv.conf`（Android 上不存在），DNS 走 `::1` 失败
  ```
  dial tcp: lookup gemini.google.com on [::1]:53
  ```
  **修法**（proot 绑 resolv.conf）：
  ```bash
  proot -b $PREFIX/etc/resolv.conf:/etc/resolv.conf -b $PREFIX/etc/hosts:/etc/hosts ./gw2api ...
  ```
  修复后错误变 `upstream returned no content frame`（已连通，只是缺登录态）
- **只缺一样**：Gemini Cookie `__Secure-1PSID` + `__Secure-1PSIDTS`
- ⚠️ 作者明确：**不能生成 NSFW**
- 备选项目：`shleeshlee/gemini-api-oneclick`（Python 多账号网关 + 管理面板 + 创作工作室）

### 4.5 Perchance（Turnstile 硬墙，未破）
- 完整链路已摸清（见 routes.md 第十节）：ad code → Turnstile → userKey(64hex) → generate → download
- **根因**：chromium headless UA 含 `HeadlessChrome`，Turnstile 直接拒绝渲染 iframe。
  改 UA 后 widget 能渲染但报 `600010`
- embed 页用 postMessage 协议，无真实 UI 交互不触发验证
- 试过：selenium / nodriver / 原生 CDP / `perchance-api` PyPI 包，全部失败
- 可用渲染器（如需再战）：`ismoiloffS/EzSolver`（nodriver + 真 Chrome）

### 4.6 Pollinations quests（免费回血 pollen）
- 可赚：`use_app +0.25` / `use_text_model +0.25` / `use_image_model +0.25` /
  `connect_polli_cli +1` / `use_agent +0.25` / `use_community_model +0.25`
- **claim 是 dashboard-only**：`POST /account/quests/rewards/{id}/claim` 用 API key → 403
  `Reward claims require a dashboard session`，必须浏览器登录 enter.pollinations.ai
- 已领：`first_api_key` + `use_app` + `use_image_model` = **0.5 pollen**
- 文本模型 **0 余额也能用**（`openai/gpt-oss-20b` 实测成功）
- 设备流：`polli auth login` → 生成 Device key（5 pollen 预算、7 天有效）

### 4.7 Google Colab 远程生成线（2026-10-18 深夜整晚实测，当前主力）

**架构**：`examples/anima_colab.ipynb`（Flask + cloudflared quick tunnel）+ 本机两个客户端：
`scripts/colab_gen.sh`（CLI）与 `colab_gen` DSH 插件（`plugins/dsh-colab-gen/`，已 install 到 web profile）。
隧道地址存 `~/.dsh/.colab-url`，每次 runtime 重启后 cell 4 出**新随机子域**，必须重新存。

#### 三面墙（全部实测坐实，别再撞）

| 墙 | 数值 | 后果 | 绕法 |
|---|---|---|---|
| RAM | **12.6GB**（免费档标准值，25.2 是含显存口径） | CPU 里凑 fp32 权重（13.6GB）→ **kernel 被杀**（日志特征：`AsyncIOLoopKernelRestarter: restarting kernel`） | CPU 里永远只放 fp16 一份（~7GB），升精度在 GPU 上原地 `.to()` |
| VRAM | **14.56GB**（报 15） | Anima fp32 权重 13.6GB 上卡 → 剩 <1GB → 640×960 以上必 OOM | 换 fp16 模型（SDXL 系 fp16 只占 ~7GB） |
| 精度 | **T4 无 bf16/fp8** | Anima(Cosmos bf16 训练)转 fp16 → 激活值超 65504 → inf/NaN → **100% 纯黑图**（mean=0，文件 ~1.8KB） | Anima 在 T4 只能 fp32；要快就换 SDXL 底 |

**黑图判定**：`np.asarray(img).mean() < 6` 即黑图（服务端 render_image 已内置，黑图直接报错不返回）。

#### 实测速度表（T4，全部真图）

| 模型 | 配置 | 耗时 | 备注 |
|---|---|---|---|
| **animagine-xl-4.0 fp16** | 832×1216 @28 | **30s** | ✅ 当前 GPU 默认档，动漫天花板 |
| animagine-xl-4.0 fp16 | 1024×1024 @28 | 32s | |
| Anima fp32 | 512×768 @16 | 64s | 长宽比正常 |
| Anima fp32 | 512×512 @16 | 40s | |
| Anima fp32 | 640×960 @22 | 202s | 含 2 次 OOM 降档白烧，别用 |
| Anima 全 fp16 / hybrid | 任意 | 快但**黑图** | 硬件墙，见上表 |
| OpenVINO CPU 档 | sana06 等 5 预设 | 分钟级 | 2vCPU，官方跑分÷90 |

#### notebook 演进结论（HEAD `1031eb5`，9 格一次成型版）

- cell 3：`GPU_MODEL` 三档开关（animagine 默认 / nova_lcm 8步极速 / anima fp32 慢速），加载后自动 512 测试图防黑图
- cell 4：幂等（重跑不报端口占用/坏二进制）；单 worker 串行队列（并发必 OOM）；OOM 自动 x0.8 降档重试；结果落盘不留内存
- 已踩过的代码坑：`load_components(torch_dtype=)` 和 `torch_dtype=` 被新版 diffusers **静默忽略**（认 `dtype=`）；事后 `.half()` 逐组件转会 dtype 记账错乱出黑图；回退时二次 `from_pretrained` 爆 RAM
- **Colab 的 F5 不会重拉 GitHub 内容**——改了 notebook 必须 File→Open notebook→GitHub 开新副本，或在 URL 里换 commit hash 强刷。旧标签页跑旧代码 = 一切白改

#### 客户端 API（notebook cell 4 起的 Flask）

```
GET  /health          档位/gpu_model/队列/cpu_presets
POST /generate        {prompt,kind:image|video,width,height,steps,seed,cpu_preset}
POST /batch           {prompts:[],n_per_prompt,...}  入队串行消化
GET  /status/<jid>    queued|running|done|error(+seconds,path,bytes)
GET  /result/<jid>    拉 PNG/MP4（/image/<jid> 同义）
POST /upload          multipart file → Colab 端路径（I2V 参考图用）
GET  /flush           产出搬 Drive
```
DSH 插件工具名 `colab_gen`（action 同名）。**插件代码改了要重启 dsh 会话才生效**（Node 模块缓存）。

#### 当前状态（2026-10-18 09:20 复核）

- ⚠️ **GPU 配额耗尽**：`/health` 实测 `gpu:false / gpu_name:none / vram_gb:0.0`，现在只给 CPU 档。恢复靠时间（一般次日）或错峰（国内清早概率高）
- ✅ 隧道每次 runtime 重启都变，最新地址永远以 `~/.dsh/.colab-url` 为准（本轮：`https://kick-trio-years-antenna.trycloudflare.com`，build v6、GPU 配额仍耗尽，见 4.9）
- ❌ `cpu_ready:false` 的含义**不是"权重还在下载"**：见下节，CPU 档整条路是坏的（`OVDiffusionPipeline` 导入失败）
- animagine-xl-4.0 权重（6.94GB）下载过一次，同 runtime 内免重下；runtime 没了要重下 ~8 分钟
- **下一步**：CPU 档先跑 sana06 出图（notebook 自动分流，客户端无感）；GPU 恢复后切回 animagine 30s/张

#### ✅ 2026-10-18 09:50 已修复：Colab CPU 档重写（HEAD `fbb4136`）

**根因（静态分析 optimum-intel 2.2.0 wheel 坐实，不是版本冲突、也不是"权重没下完"）**：
```
optimum/intel/openvino/__init__.py
  L84  from .modeling_open_clip import ...        ← 无 is_open_clip_available() 门
  L97  from .modeling_text2speech import ...      ← 无门，内部拉 kokoro
```
`import optimum.intel` 会硬拉 **open_clip / kokoro / timm / sentence_transformers**，
Colab 镜像一个都没装 → 底层 ModuleNotFoundError 被 `transformers._LazyModule`
重写成那句误导性的 `Could not import module 'OVDiffusionPipeline'.
Are this object's requirements defined correctly?`
→ **换任何 cpu_preset 都炸**，补装哪个包都追不完（闭包里还有一串无门 import）。

**修法：CPU 档彻底不碰 optimum-intel，改纯 diffusers fp16**
- 5 个新预设（体积走 HF blobs API 实测，`ram_gb` 是加载预算）：
  | preset | 仓库 | cls | steps/cfg | ≤px | fp16 预算 |
  |---|---|---|---|---|---|
  | `sdxl_anime`(默认) | sca255/nova_xl_lcm | SDXL | 8 / 1.5 | 1024 | 7.4GB |
  | `sd_turbo` | stabilityai/sd-turbo | SD1.5 | 4 / 0.0 | 768 | **2.6GB**（RAM 紧就它）|
  | `sdxl_light` | stabilityai/sdxl-turbo | SDXL | 4 / 0.0 | 768 | 6.9GB |
  | `animagine` | cagliostrolab/animagine-xl-4.0 | SDXL | 25 / 7.0 | 1024 | 6.9GB |
  | `sana06` | Efficient-Large-Model/Sana_Sprint_0.6B_1024px_diffusers | SanaSprint | 4 / 4.5 | 1024 | 7.7GB |
- **仓库必须带 fp16 变体**才敢在 12.6GB RAM 上跑：nova_xl_lcm 只有 fp16（7.33GB）✅；
  animagine-xl-4.0 无 fp16（plain 6.94GB，diffusers 会先下 fp32 再转 → 峰值按 fp32 计）
- `CPU_ENGINE='openvino'` 保留为可选实验档，失败自动降级 diffusers 并打印原因
- 纯 CPU runtime **不再调 `enable_model_cpu_offload`**（无 accelerator 直接抛 ValueError），
  改 `.to('cpu')` + attention slicing + vae slicing/tiling
- RAM 闸门：预算不够直接报错并提示换 `sd_turbo`，不再 OOM 把会话打死
- CPU 分支加黑图判定（mean<6 报错）、`steps/guidance/seed` 可覆盖
- `/health` 新增 `cpu_engine` / `cpu_engine_mode`；cell 1 去掉 `optimum-intel openvino` 强装

**桩件实测（本机 exec + 假 diffusers/psutil，5/5 通过）**：默认档加载 fp16+variant=fp16 ✅、
animagine 不传 variant ✅、RAM 剩 4GB 拦下 sana06 并给出正确措辞
`float16 权重需 ~7.7GB RAM，当前只剩 4.0GB -> 换更小的 cpu_preset（sd_turbo 只要 2.6GB）` ✅、
openvino 模式失败自动降级 ✅、预设表字段完整 ✅。语法终检 7/7 格通过。

**⚠️ 生效前提**：Colab 的 **F5 不会重拉 GitHub**。必须 File→Open notebook→GitHub→贴
`https://github.com/2719126468-ship-it/free-image-gen/blob/main/examples/anima_colab.ipynb`
开**新副本**，重跑 cell 1→2→4（CPU 档跳过 cell 3），新 URL 再写回 `~/.dsh/.colab-url`。
旧标签页跑的还是旧代码 —— 现在隧道上那个 runtime 就是旧的（`cpu_error` 仍是那句 OVDiffusionPipeline）。

#### ✅✅ 2026-10-18 10:15 真机验证：加载器通了，但撞第二面墙 —— **CPU 上 fp16 是反向优化**（HEAD `d0d01ae`）

**新隧道 `scientific-italiano-quilt-minnesota` 跑的是 v2 代码，`/health` 确认新结构生效**：
`cpu_engine_mode:"diffusers"`、`cpu_presets` 换成 5 个新档、`cpu_error:null`
→ 提 `cpu_preset:"sd_turbo"` 后 **`cpu_ready:true` / `cpu_engine:"diffusers-fp16"`**
**= optimum-intel 那座墙确实绕过了，重写方向正确。**

**但同一张图（sd_turbo，4 步 / 512×512）跑了 25+ 分钟没出图。**
根因：**PyTorch CPU 的 fp16 matmul 是逐算子升 fp32 模拟的，比 fp32 慢数倍**。
我 v2 为了省 RAM 把 fp16 排第一，方向正好反了。

**v3 修法（`d0d01ae`）**：
- dtype 顺序按设备定：**无 CUDA → fp32 优先**（fp32 过不了 RAM 闸门才退 fp16）；有 CUDA → fp16 优先
- `variant='fp16'` 只在真要加载 fp16 权重时传
- 纯 CPU **不开** `enable_attention_slicing` / `vae_tiling`（省的是显存，CPU 上纯减速）；需要时手动 `CPU_SLICING=True`
- `torch.set_num_threads(os.cpu_count())`：桩件显示默认只吃 2 线程
- 渲染加 `callback_on_step_end` 回写 `progress`/`elapsed` → **能区分「慢」和「卡死」**（这次就是吃了没进度的亏，只能靠轮询猜）
- 闸门拦下 fp32 后 `continue` 试 fp16（v2 的 `break` 会直接抛错，失去降级机会）
- `sdxl_anime` 补 `float32:14.7` 预算（nova_xl_lcm 只有 fp16 权重，转 fp32 体积翻倍）
- `engine` 标签记实际 dtype（v2 里 fp32 也误标 `diffusers-fp16`）

**桩件实测（本机 exec + 假 diffusers/psutil，6 组）**，11GB 可用 RAM 下各档最终 dtype：
| preset | 最终 dtype | 说明 |
|---|---|---|
| `sd_turbo` | **fp32** | 2.6GB，最快通路，先拿它证明端到端 |
| `animagine` | **fp32** | 6.9GB |
| `sana06` | **fp32** | 7.7GB |
| `sdxl_anime` | fp16（自动降级） | fp32 要 14.7GB > 11GB，闸门拦下后降 fp16 |
| `sdxl_light` | fp16（自动降级） | 同上 |
RAM 压到 4GB 时 sana06 两档都被拦并给出明确指令 ✅

**⚠️ 关键操作提醒**：Colab **F5 不重拉 GitHub**，改 notebook 后必须 File→Open notebook→GitHub
开**新副本**才生效。现在这个 runtime 是 v2，那张 fp16 图要么等它自己跑完、要么直接开新副本重跑
（单 worker 串行，队列没排空前热改全局函数对 in-flight 任务无效）。

**✅ v3 真机结果（隧道 `lift-josh-arthur-connected`，`/health` 有 `cpu_slicing` 字段=确认新代码）**：
提 `sd_turbo` 4步/512px → `/status` 回 `progress:"1/4" elapsed:17.3` 后 **error**：
```
AttributeError: 'NoneType' object has no attribute 'pop'
```
- **两个结论**：
  1. 🎯 **速度基线拿到了：fp32 约 17s/步** → sd_turbo 4步/512px 全图 ≈ **70s**。
     对比 v2 的 fp16 跑 **35 分钟没出图** → **「CPU 走 fp32 快路径」判断完全正确**，这面墙绕过了。
  2. 🐛 进度回调把任务炸了：diffusers 对回调返回值做 `callback_outputs.pop('latents',...)`，
     **回调必须原样返回 kwargs dict**，v3 的 `_prog` 返回 None → 直接 AttributeError。
- **v4 已修（HEAD `debd07c`）**：`_prog` 返回 `cb_kwargs`（非 dict 退 `{}`）+ 整段包 try
  （进度上报永不影响出图）；最后一步 `step==n-1` 也上报（原每2步一次，4步任务永停 3/4）；
  `/health` 加 `build` 字段自证版本。集成测试 4 组全过（完整渲染到 4/4、无 _jid 不造假 job、
  黑图 mean<6 报错、set_job 抛异常仍出图）。
- **⚠️ 但 v4 同样需要开新副本才生效**（F5 不重拉 GitHub + cell4 幂等复用旧 Flask）。
  当前 runtime 是 v3，那张 sd_turbo 已 error，队列空。

**✅✅ v4 真机端到端跑通（隧道 `arbitrary-broadband-board-bras`，`/health` 回 `build:"v4"` 自证）**
CPU 档第一次真正出图，`cpu_engine:"diffusers-float32"` / `cpu_ready:true` / `cpu_error:null`：

| 任务 | 配置 | progress | 推理 elapsed | 含重载总 seconds | 产物 |
|---|---|---|---|---|---|
| 自测 | sd_turbo 512×512 steps4 | 4/4 | **77.1s** | 233.3s | ✅ 550970B PNG 512×512 luma=118.5 真图 |
| **色图** | sd_turbo 512×768 steps4 NSFW | 4/4 | **113.7s** | 191.1s | ✅ done（隧道死前未拉回，见下） |
| sana06 | 768×1024 steps4 NSFW | — | — | — | ❌ 提交后隧道 530 死，结果丢在 /content |

- **CPU 档速度基线确立：sd_turbo fp32 ≈ 19–28s/步**（512² 77s/4步、512×768 113.7s/4步）。
  比 v2 的 fp16（35 分钟没出图）快 **一个数量级以上**，"CPU 走 fp32"彻底验证正确。
- 首任务 233s = 77s 推理 + 约 156s 下 2.6GB 权重 + 加载编译；后续任务命中内存只剩推理。
- **CPU 档定位**：只适合 `sd_turbo` 这类 4 步小图（<2min/张）快速验证。SDXL 档
  （sdxl_anime 8步 / animagine 25步）按 20s/步推 8步≈2.7min、25步≈8min+，且 SDXL unet
  比 SD1.5 大、单步更慢 → 正式出图仍等 GPU 恢复切 animagine 30s/张。

**🔴 隧道 530 死亡复盘（`arbitrary-broadband-board-bras`，03:22 起 sana06 任务卡住后崩）**：
- 现象：`/health` 与 `/status` 全 **HTTP 530**，返回 7734B 的 Cloudflare 拦截 HTML 页
  （`content_type:text/html`，含 `1033`），持续 4 分钟不恢复 = **源站（Flask runtime）已死**，非瞬时抖动。
- 触发点：sana06 是 **768×1024 + 需重载 7.7GB 权重**（切档触发 `del pipe` + 重新 from_pretrained）。
  极可能 **RAM 峰值把 Colab kernel 打死**（12.6GB 墙：sd_turbo 2.6GB 还在内存时又拉 7.7GB）。
  → **教训：切 cpu_preset 会双模型共存撑爆 RAM**。已在 v4 的 `load_cpu_pipe` 里 `del CPU['pipe']`+gc，
  但 diffusers 下载新权重的瞬时峰值仍可能压过旧模型释放。**待办 v5：切档前强制 `del` 旧 pipe + `gc.collect()`
  确认释放，或干脆一个 runtime 只跑一个 preset。**
- 拉图失败特征：`curl` 拿到 HTML 而非 PNG，`PIL.UnidentifiedImageError: cannot identify image file`。
  **判定隧道是否真死**：`curl -w "%{http_code}"` 看是不是 530 + `content_type` 是不是 text/html，
  别只看有没有字节数（拦截页也有 7734B）。

**✅✅✅ v5 真机完全跑通并交付色图（隧道 `carlo-plumbing-exceed-watt`，`/health` 回 `build:"v5"`）**
全程单 preset `sd_turbo`（不切档 → 不触发 RAM 叠加雷区），两张无审查色图真机出图 + 拉回本机落盘：

| 图 | 配置 | progress | 推理 elapsed | 含首载 total | 本机文件 | 校验 |
|---|---|---|---|---|---|---|
| 1 | sd_turbo 512×768 steps4 | 4/4 | **112.9s** | 269.6s | `~/th-img/colab_v5_nsfw.png` 744191B | 512×768 luma=136.1 sd=63.1 ✅真图 |
| 2 | sd_turbo 512×768 steps4 | 4/4 | **108.6s** | 181.3s | `~/th-img/colab_v5_nsfw2.png` 758232B | 512×768 luma=133.5 sd=63.4 ✅真图 |

- **CPU 档速度基线钉死：sd_turbo fp32 512×768 ≈ 109–113s/张（4步）**。
  首张 total 269.6s 含下 2.6GB 权重+编译；第二张 181.3s（命中内存，省下载）。
- v5 的 RAM 闸门（权重+act_gb）没被触发拦截 —— 因为全程 sd_turbo（fp32 权重5.2+act2.5=7.7GB < 11GB 可用），
  验证了「单 preset 不切档」是 CPU 档最稳用法。
- **隧道在提第三张时死**：`Error 1033`（cloudflared 连不上 CF 边缘，非源站 OOM）——
  quick tunnel 固有脆弱性，与 notebook 代码无关。前两张已在死前拉回，不受影响。
- **交付纪律固化**：`/result/<jid>` 拿到后**立刻** curl 落盘（带 4 次重试），别攒着批量拉
  —— 上次 sana06 就是图 done 了但隧道先死，结果丢在 /content 拉不回。

**结论：Colab CPU 档 v5 已可实用**（sd_turbo 应急通路，~2min/张无审查）。
GPU 恢复后仍优先 animagine 30s/张（画质高得多）。重开 notebook 用 GitHub main（v6，`78d195f`）。

---

### 4.8 SDXL 在 Colab 免费 CPU 上的真实天花板（2026-10-18 查证）

用户反馈 sd1.5 画质不行要 SDXL。**两个硬数字决定一切**：
| dtype | SDXL 权重 | 12.6GB 墙 | CPU 速度 |
|---|---|---|---|
| fp32 | **14.7GB** | ❌ 装不下 | 快（若装得下）|
| fp16 | 7.3GB | ✅ | **慢一个量级**（sd_turbo fp16 实测 35min 没出图）|
| bf16 | 7.3GB | ✅ | 取决于 CPU 有无 `avx512_bf16`/`amx_bf16` |

**⚠️ 纠正外部建议（有出处但结论不适用）**：有人说"CPU 上换 bf16 是单点收益最大改动，PyTorch 官方 Xeon 实测 3.91×"。
数字本身没错（PyTorch 博客，BF16+compile+SDPA 在 Xeon 上），但**测试机是 Sapphire Rapids（有 AMX）**。
AVX512_BF16 首次出现于 **Cooper Lake(2021)/Ice Lake+**；**Colab 免费档长期是 Skylake-SP / Cascade Lake
（2017-2019），有 avx512f/vnni 但无 avx512_bf16** → PyTorch 会软件 fallback，**不比 fp32 快**。
→ 所以 v6 里 bf16 是**自动探测后启用**（`_cpu_bf16_capable()` 读 /proc/cpuinfo），探测不到就跳过，
  绝不无脑切 bf16。cell 8 的基准 cell 会实测出这台机器的真实加速比。

**v6 已落地（`78d195f`）**：cell1 打印 CPU 型号+AVX512/AMX 位+bf16 判定；cell4 dtype 三态
（CUDA→fp16 / CPU+bf16硬件→bf16 / 否则→fp32）; SDPA 挂 unet（★pipeline 无此方法）; torch.compile 默认关;
新增 cell8 精度基准。桩件 12 项全过。**真实加速比待重开 notebook 跑 cell1+cell8。**

#### 真要 SDXL 画质的三条路（按可靠性）
| 方案 | 可行性 | 实测/查证依据 | 状态 |
|---|---|---|---|
| **sdcpp + GGUF Q4_K** | ★最实际 | `off-grid-ai/animagine-xl-4.0-GGUF` Q4_K=**2.80GB** ungated；ggml 用 AVX2/AVX512 原生 int kernel，非 PyTorch 软件 fallback | `scripts/sdcpp_colab.sh` 已写，参数对 upstream 源码核实 |
| **Modal 免费 GPU** | ⚠️降级备用 | 官方 pricing 页（2026-10-23 抓取）原文「Starter has no monthly fee and includes $30 of compute (GPUs, CPUs, Memory) per month」，全页 `credit card` **0 命中** → 「$30 档必须绑卡」在可验证范围内**无官方原文支撑**（只能真注册证实）；按用户结论**降级为「有卡时备用」** | `scripts/modal_sdxl.py` 保留；需 `pip install modal && modal token new` |
| Colab CPU + bf16 | ⚠️ 看运气 | 取决于分到的 CPU 是否 Ice Lake+；免费档大概率 Skylake/Cascade → 无效 | v6 已自动探测，cell8 实测 |
| Colab GPU | 等配额 | animagine fp16 30s/张 @832×1216，画质最好 | GPU 耗尽中，`/health` 看 `gpu:true` |

#### sdcpp 关键坑（写进脚本注释）
- **预编译二进制是 Ubuntu 24.04 构建（glibc 2.39），Colab 是 22.04（glibc 2.35）→ 跑不了**，
  必须源码 build（`git clone --recursive` + `cmake -DSD_WEBP=OFF`，约 3-5 分钟）
- CLI 参数真名（对 `examples/common/common.cpp` options 表核实）：
  `-m/-p/-n/-W/-H/--steps/--cfg-scale/--sampling-method(不是 sample-method)/-s/-o/-t`
- Q4_K 2.8GB vs Q8_0 4.18GB vs bf16 6.94GB（SDXL-base）；Q4_K 画质/体积最优
- 想更快：`--steps 20`、`--offload-to-cpu`、`--vae-tiling`

#### 🔴 2026-10-18 09:26 实测（已修，见上节）：Colab **CPU 档整条路是坏的**

- 提交 `POST /generate {cpu_preset:"sdxl_anime", 768x1024, steps:8}` → job 入队正常，
  30s 后 `/status/<jid>` 返回：
  ```
  ModuleNotFoundError: Could not import module 'OVDiffusionPipeline'.
  Are this object's requirements defined correctly?
  ```
- 根因：`optimum.intel` 在当前 Colab 镜像里导入失败（OpenVINO 运行时/版本不匹配），
  **5 个 cpu_preset 全走同一入口 → 全废**。`/health` 的 `cpu_ready:false` 就是这个意思，
  不是"还在下载权重"（原判读有误，已更正）。换 preset / 重提交都没用，要修得改 notebook
  的 `load_cpu_pipe()`（pin `optimum-intel`+`openvino` 版本，或退回 diffusers fp16 CPU 直跑）
- **推论**：GPU 配额耗尽期间 Colab 线**完全不可用**（video 也 `kind=video and not HAS_GPU → 400`）。
  这段时间出图只能走 Pollinations 匿名 / AI Horde / Cloudflare 等本机路线

#### 🔴 2026-10-18 09:27 实测：AI Horde **>845px 直接 403**（匿名档）

- `HORDE_W=832 HORDE_H=1216` → 四个模型全 403，原文：
  `Due to heavy demand, for requests over 845x845 or over the applicable first-order-equivalent sampler work bu...`
  （**832×1216 面积 1,011,712 > 845² = 714,025**，被"一阶等效算力"卡掉，不是单边超 845）
- 降到 **512×768（393,216）即可提交**，实测 `AbsoluteReality queue=258 wait=531s`
- ⚠️ 与 4.3 节旧记录冲突：昨天 10 模型并行是 **832×1216 成功**的（Flat-2D 735s 出图）。
  说明该 403 是**按当前负载动态生效**的限流，不是固定规则 → 高峰期一律用 ≤845² 面积
- 本机 `python3` **没有 numpy**（`ModuleNotFoundError: No module named 'numpy'`）→
  黑图/亮度判定改用 PIL：`im.convert('L')` + `ImageStat.Stat(im).mean[0]`，别写 numpy
- 视频（Wan2.2 TI2V-5B）从未实测成功，权重 10-20GB 会加剧 RAM/时间压力，**优先级放后**
---

### 4.9 ★ Colab CPU 档 v7：sdcpp(GGUF) 引擎 + 闸门/精度修正（2026-10-18 13:17–13:45 真机+桩件）

**新 runtime 复核（隧道 `kick-trio-years-antenna`）**：`/health` 回 `build:"v6"` / `gpu:false` /
`cpu_bf16:**false**` / `cpu_sdpa:true` / `avail` 未暴露。→ 4.8 的预判**坐实**：免费档 CPU 没有
`avx512_bf16`/`amx_bf16`，v6 的自动探测正确地跳过了 bf16（无硬件却硬切 bf16 = 更慢）。

**真机把「CPU SDXL 两难」的退路也钉死了**：
- 提交 `cpu_preset:"sana06", 1024×1024, steps 4` → 闸门拦下 fp32 → 自动退 **fp16**
  （`/health` 的 `cpu_engine:"diffusers-float16"` 自证）
- **实测 588s/步**（`/status` 在 elapsed 588.4s 才出 `progress:"1/4"`）→ 4 步 ≈ **40 分钟/张**
- 对比 `sd_turbo` fp32 **27s/步**（v5 基线）→ **fp16 在 CPU 上慢约 22 倍**
- **结论（第四面墙）**：CPU 上「fp32 过不了 RAM 闸门」不等于"降档还能用"，而是**任务实质报废** ——
  退路 fp16 是 20 倍慢。闸门因此必须**分辨率感知**，且要给 `force_dtype` 显式逃生口，
  否则 512² 小图也被按 1024² 的 act 预算误杀。

**v7 已落地（notebook cell 4 `BUILD='v7'`）**

| 改动 | 细节 |
|---|---|
| **sdcpp 引擎** | `cpu_preset:"sdcpp"`（animagine-xl-4.0 **Q4_K**，2.80GB）/ `"sdcpp_q8"`（4.18GB），走 stable-diffusion.cpp CLI。首次请求自动 `git clone --depth 1` + submodule + `cmake` build（5–10 分钟）+ 下 GGUF；`GET /sdcpp/build` 可预热；`/health` 暴露 `sdcpp_bin/sdcpp_gguf/sdcpp_building/sdcpp_error`。CLI stdout 的 `N/M - x.xx s/it` 解析回写 job `progress` |
| 闸门分辨率感知 | `act_eff = act_gb × clamp(mp/1.05, 0.55, 1.0)`，512² 只按 1/4 计 |
| `force_dtype` | 请求体加 `force_dtype: float32\|float16\|bfloat16` → 跳过自动 dtype 选择（闸门仍生效） |
| `/health` | 新增 **`avail_ram_gb`**（以后不用再猜 12.6GB 里实际剩多少）、`force_dtype`、`cpu_presets` 追加 sdcpp/sdcpp_q8 |
| 尺寸 | sdcpp 出图长边 ≤1024 且**按比例**缩放（900×1300 → 704×1024，不再压成方块），64 对齐 |

**桩件实测 7/7 通过**（本机 exec + 假 flask/torch/diffusers/psutil + 假 `sd-cli` 脚本）：
路由 9 条（含 `/sdcpp/build`）｜`/health` 字段齐且 `build=v7`｜**复现真机**「10.7GB 可用 + 1024² → 退 fp16」｜
512² + `force_dtype=float32` 放行｜两档都被拦时抛可读错误（不再静默 OOM 打死会话）｜
`cpu_preset=sdcpp*` 正确分流到 `render_sdcpp`｜diffusers 路径无回归（含进度回调不炸）。
沙箱里另验：进度解析 `1/4→4/4`、长边缩放、`rc≠0` 抛错带尾部日志、构建链路 `clone→submodule→cmake→build`。

**客户端同步（两个坑一起修）**：
- 插件 `colab_gen` 的 `cpu_preset` 枚举原本是 **`sdxl_lightning` / `sd15_lcm`** —— 这两个名字
  **服务端不认**（`set_cpu_preset` 只匹配 `CPU_PRESETS` 键），传进去**不报错、静默留在默认档 `sdxl_anime`**，
  即"传了名字却出了别的模型"。已改成 v6 真键名 `sd_turbo/sdxl_anime/sdxl_light/animagine/sana06`，
  并追加 `sdcpp/sdcpp_q8` 与新参数 `force_dtype`；health 文案也去掉了过期的「OpenVINO INT4」。
- `scripts/colab_gen.sh` 用法文案与 `FORCE_DTYPE` 环境变量同步。

**⚠️ 生效前提仍是开新副本**（F5 不重拉 GitHub）：File→Open notebook→GitHub→
`examples/anima_colab.ipynb` → 跑 1→2→4 → 新 URL 写回 `~/.dsh/.colab-url`。
**当前 runtime 跑的是 v6，还没有 `/sdcpp/build`**（`/health` 里看不到 `sdcpp_bin` 就是这个原因）。

#### 4.9.3 🔴 v7.1 真机补充：diffusers SDXL 在 CPU 上是**不可能**，不只是慢（隧道 `eyes-flux-cal-depth`）

`POST /generate {cpu_preset:"animagine", 512×768, steps 12}` → 旧闸门**放行**（需 8.6+0.8=9.4 ≤ 11.6），
然后：
```
14:14:34  avail_ram_gb 9.6   (加载中)
14:15:19  avail_ram_gb 5.8   (继续吃)
14:16:02  HTTP 1033 → 14:18:30 起永久 HTTP 530   = Flask 源站已死 → Colab kernel 被打死
```
- **结论：animagine(6.9GB)·sana06(7.7GB) fp32 在 12.6GB 总量 / 11.6GB 可用的免费档上会把 kernel 打死**，
  与 `avail_ram_gb` 的闸门判断无关 —— 权重之外还有 **1.5 倍瞬时峰值**（`from_pretrained` 读 safetensors
  再拷一份到模块，最大组件双份）。sd_turbo(5.2GB) 是唯一能活下来的档。
- **v7.2 修法**：`peak = need × 1.5 + act`（1.5x = 加载瞬时双份），闸门宁严不宽 ——
  被拦只损失一次请求，放行错误就是整台 runtime 死。桩件复测：sana06 1024²@10.7 直接拒绝（旧版退 fp16 30 分钟/张）、
  sd_turbo 512×768@11.6 仍放行、sdxl_anime 两档都被拦并给可读错误、`force_dtype` 生效、sdcpp 分流、diffusers 无回归。
- **意义**：至此 CPU 上 SDXL 的三条路全部判死（fp32 装不下 / fp16 慢 20 倍 / 放行也会打死 kernel），
  **sdcpp+GGUF 是唯一剩下的活路**（2.8GB mmap，不碰 diffusers 的加载峰值）。

#### 4.9.4 ✅ 预编译包在 Colab 上真能跑（省掉 10 分钟编译）+ v7.3 修 bin 查找（隧道 `semester-vast-explore-vital`）

**v7.2 真机时间线（结论先行）**：
- `POST /sdcpp/build` → 14:25–14:26:20 `/health` 一直是 `building:false / err:null`（**这是在下载 2.8GB GGUF**，
  `building` 只在 `_sdcpp_build()` 内置真，下载阶段看不到 → 监视脚本不能只看 building）
- 14:26:24 `building:true` → **1 秒后**回 `false`，`err:null`、`bin:null`
- 提交 `cpu_preset:"sdcpp"` → job error：`RuntimeError: sdcpp 未就绪: sd-cli 不存在`

**判定：预编译二进制其实成功了**（26MB zip → 解包 `/content/sdpre/` → `--help` rc=0，1 秒级；否则会走 cmake 那 5–10 分钟）。
**glibc 担忧被实测推翻** —— 官方 Ubuntu 24.04 包在这台 Colab 上能跑，`_sdcpp_prebuilt()` 这条前置探测值回票价。

**v7.2 的真 bug**：`_sdcpp_bin()` 只查 `SDCPP_ROOT/build/{bin/,}sd-cli` 和 `shutil.which('sd-cli')`，
**不认 `SDCPP['bin']`、也不扫 `/content/sdpre/`** → 二进制明明就绪，`_sdcpp_warm()` 还返回 True，
出图却报"sd-cli 不存在"。

**v7.3 修法（一次到位）**
1. `_sdcpp_bin()`：先认 `SDCPP['bin']` → 再查 build/ 三个位置 → 再 **walk `/content/sdpre/`** → 最后 `which`
2. `_sdcpp_warm()` 收尾**验证**：`_sdcpp_bin()` 仍为空就抛 `构建结束但 _sdcpp_bin() 仍为空（看 sdcpp_log）`
   —— 不再"返回 True 却没二进制"
3. **`SDCPP['log']` 环形日志（40 条）+ `/health` 里的 `sdcpp_log` 末 12 条**：预编译/build/下载每一步都留痕，
   一次 curl 就知道卡在哪（这轮就是吃了"只看得到 error=null"的亏）
4. 预编译命中后**再软链一份到 `SDCPP_ROOT/build/bin/sd-cli`**，任何只认老路径的代码也能命中
5. `/health` 增 `sdcpp_bin_kind`（prebuilt / source-build）、`sdcpp_gguf_exists`
6. **新增 `POST /sh {"cmd":"..."}` 自救通道**（rc/stdout/stderr 回传）：改 cell 4 必须重开 notebook，
   但"看文件在不在 / 跑一下二进制 / 看报错"这类排查不该再付一次用户重载成本

**桩件 4/4 + 全格回归 12 项全过**：`sdpre/**` 被认出（复现并修掉 v7.2 的 bug）｜`SDCPP['bin']` 优先｜
warm 无二进制时大声失败｜日志上限 40/末 12 条｜`/sh` 的 rc/stdout/stderr/空命令 400｜闸门与 sdcpp 分流无回归。

#### 4.9.5 ✅ sdcpp 首次真机跑通加载（30 秒）+ 🔴 1.0MP 出图把 kernel 打死（隧道 `kept-station-jerusalem-says`）

**加载阶段：彻底成功，成本 30 秒**（`/health` 的 `sdcpp_log` 原文）：
```
[sd.cpp] 下载 animagine-xl-4.0-Q4_K.gguf（2.80GB，仅首次）
[+] 预编译 sd-cli 可用（--help rc=0），跳过源码编译
[+] sdcpp 就绪(prebuilt): /content/sdpre/sd-cli + /content/animagine-xl-4.0-Q4_K.gguf
```
- **预编译包确实能在 Colab 跑**：解包出 `sd-cli`(1.4MB) + `sd-server` + `libwebp.so.7`，`--help` rc=0
  → **源码编译那 5–10 分钟永久省掉**；GGUF 2.8GB 下载 <30s（Colab 机房带宽）
- `_sdcpp_bin()` 现在认 `SDCPP['bin']` 与 `/content/sdpre/**`，v7.2 的"sd-cli 不存在"已消失
- **`/sh` 自救通道实测可用**（`nproc`→2、`df`→87G 空闲），排查不用再付用户重载成本

**出图阶段：`832×1216 / 20 步` 跑到 7.5 分钟后隧道 1033 → 转永久 530（Flask 源站死）**
- 症状与 4.9.3 同款：**SDXL 在 1.0MP 上把整个 kernel 带走**。Q4_K 权重只有 2.8GB，
  说明吃爆的不是权重，而是 **UNet/attention 的中间张量 + VAE 解码**（SDXL VAE 在 1MP 上很重）
- 另一个发现：**`/status` 全程没有 `progress`** —— sd.cpp 用 `\r` 覆盖刷新进度行，
  v7.3 用 `for line in pr.stdout` 逐行读**永远读不到**（text 模式只在 `\n` 处断行）

**v7.4（已 push）三项保护**
1. **子进程 `RLIMIT_AS` 硬上限**（`mem_cap_gb`，默认 `min(9.5, avail-1.2)`）：
   sd-cli 自己 bad_alloc 失败 → job 报错、Flask 活着、**runtime 不再被 OOM killer 带走**
2. **默认省内存参数**：`--vae-tiling --vae-tile-size 128 --disable-prefetch`；sdcpp 默认长边从 1024 收到 **768**
   （`max_side` 可覆盖）
3. **进度读取改成按 `\r`/`\n` 手工切字符**（`read(1)` 累加），并新增
   `SDCPP['tail']`（末 8 行）+ `/health.sdcpp_tail` + 失败时把 tail 写进 `sdcpp_log`
4. **`sdcpp_args` 透传**：以后调 `--flash-attn on` / 分辨率 / 步数**不用再重载**

**桩件 5/5**：`\r` 进度 1/4→4/4 全解析｜默认参数 + 832×1216→512×768｜`sdcpp_args` + `max_side` 覆盖到 704×1024｜
tail 留痕｜失败时 tail 双写（job error + sdcpp_log）。

**下一步（真机）**：512×768 / 15 步首跑验证端到端 → 再逐步抬到 768 长边、开 `--flash-attn on` 试速度。

#### 4.9.6 🔴 512×768 也撑不住 + **拿到 sd.cpp 的硬速度数字**（隧道 `handle-hose-combining-converted`）

**sdcpp 加载依旧 45 秒**（prebuilt + 2.8GB GGUF），`/sh` 里 `nproc=2`、`/` 87G。
**首次拿到真实进度**（v7.4 的 `
` 解析生效）：
```
15:09:19  progress 1/15  elapsed 332.3  last_line "|===> | 1/15 - 163.30s/it"
15:11:42  progress 2/15  elapsed 488.7   （第 2 步 156.4s）
15:13:15 起 /status 空 → 15:21 /health 永久 530
```
- **硬数字：sdcpp Q4_K / SDXL / 512×768 / `-t 2` ≈ 160s/步**
  → 15 步 ≈ 40 分钟，20 步 ≈ 53 分钟
- **第 2 步后源站再次消失**。两次死亡都发生在"重算力持续 7 分钟"之后，怀疑不是纯 OOM，
  而是 **2 vCPU 被 sd-cli 100% 吃满 → cloudflared 心跳掉队 → CF 端把 quick tunnel 判死**（1033 → 530）

**v7.5（已 push）四项**
1. **`-t` 默认 `nproc-1`**（2 vCPU → `-t 1`，留一核给 Flask/cloudflared）+ `os.nice(10)`
2. **`--flash-attn on` 默认开**，若上游报不支持 → **自动去掉重跑一次**（`flash_attn` 参数可关）
3. **产物保全**：出图后 ① 复制到 `/content/drive/MyDrive/sdcpp_out/`（Drive 挂着就存档，隧道死了也不丢）
   ② 试传 `0x0.st` 拿临时直链，写进 `SDCPP['last_url']` / `/health.sdcpp_last_url`
4. `threads` / `mem_cap_gb` / `max_side` / `sdcpp_args` 全部请求级可调

**桩件 2/2**：2 vCPU 场景 `-t 1` + flash-attn on + `\r` 进度｜flash-attn 不支持时自动重跑并出图。

#### 📊 CPU vs GPU：今天所有路线的硬数字（2026-10-18 全部真机）

| 路线 | 每步 | 一张图 | 结论 |
|---|---|---|---|
| `sd_turbo` fp32（SD1.5 512×768） | 27s | ~2 分钟 | 能跑，**画质被用户否** |
| `sana06` fp16（1024²） | 345–588s | ≥40 分钟 | 判死（VAE 解码再 +20 分钟） |
| **sdcpp Q4_K（SDXL 512×768, `-t 2`）** | **160s** | **~53 分钟（20 步）** | **能跑但不可用**；`-t 1` 更慢 |
| Colab GPU `animagine` fp16 | — | **30 秒** | 配额耗尽中，等恢复 |
| AI Horde `Animagine XL` | — | 排队 ~19 分钟 | 免费、无审查、640×960 上限（≤845² 面积） |

**结论（写进待办，别再绕）**：**Colab 免费 CPU（2 vCPU）不是 SDXL 的可用平台** ——
三条路（diffusers fp32 装不下还打死 kernel / diffusers fp16 慢 20 倍 / sdcpp 160s 一步）都验证完了。
SDXL 画质今天只有两条路：**GPU（Colab 配额恢复，或换 Kaggle）** 或 **Horde**。

**★ 新增候选路线：Kaggle Notebooks**（未实测，但 notebook 已可移植）：
免费 **30 GPU 小时/周**（P100 16GB / T4×2），比 Colab 免费档稳。
`examples/anima_colab.ipynb` 无需改动即可跑 —— cell 2 的 `OUT_DIR = '/content/out' if IN_COLAB else './out'`、
cell 4 的 `SDCPP_DIR = '/content' if isdir else abspath('.')` 已经做了回退；
Kaggle 上只要开 Internet + 在 cell 1 装 diffusers/transformers/flask/flask-cors 即可，
cloudflared 仍走 quick tunnel。**下一步优先试这个，而不是继续优化 CPU 档。**

#### 4.9.2 ★ v7 真机首跑：v7 代码生效 + cmake 第一枪就炸（2026-10-18 14:05，隧道 `eyes-flux-cal-depth`）

**v7 确认在跑**：`/health` → `build:"v7"`、`cpu_presets` 含 `sdcpp/sdcpp_q8`、`sdcpp_*` 字段齐、
**`avail_ram_gb: 11.6`**（12.7GB 总量下真实可用值，终于不用猜了）。

**`POST /sdcpp/build` 45s 后回报（原文）**：
```
cmake configure 失败(rc=1):
CMake Error at CMakeLists.txt:179 (message):
  SD_WEBM requires SD_WEBP because WebM output reuses libwebp VP8 encoding.
```
→ **cmake 开关是联动的**：只给 `-DSD_WEBP=OFF` 会被上游 FATAL_ERROR 拒（SD_WEBM 默认 ON）。
这是 v7 的原生 bug（v7 只关了 WEBP），与 sdcpp 本身无关。

**v7.1（同一 runtime 无法热修，必须再开新副本）**：
- cmake 三组开关**依次回退**：`SD_WEBP=OFF+SD_WEBM=OFF` → `SD_WEBP=ON+SD_WEBM=OFF` → 裸 `Release`；
  每轮先 `rmtree(build)` 清脏缓存，三组全败才抛错
- 新增 **预编译探测** `_sdcpp_prebuilt()`：取 GitHub release 的 `Linux*x86_64*.zip`（26MB，非 vulkan/rocm），
  解包后 **用 `--help` 实测 rc** —— 能跑就省掉 10 分钟编译（Colab 22.04 vs 官方包 24.04 的 glibc 差，
  大概率不行，但试错成本 26MB，值得），跑不动立刻回落源码构建
- 预热顺序改成**先下 GGUF 再编译**（编译炸了权重也不白等）
- `BUILD='v7.1'` 自证（`/health` 一眼看出跑的是哪版）

**桩件实测 4/4**（假 `_sdcpp_run`/假 `shutil`）：预编译可用时零编译直返｜cmake 三组回退序列正确
（前两组故意抛 SD_WEBM 错、第三组过）｜预热顺序 = gguf → build｜终态能找到 `build/bin/sd-cli`。

**教训（写进纪律）**：改 notebook 的**任何**外部命令行参数，先在本地把上游 CMakeLists/options 表读完再推；
`-DSD_WEBP=OFF` 这种"看起来显然"的开关，漏了联动项就是一次用户重载成本。
**待真机验证**：sdcpp 在 2 vCPU 上的 build 真实耗时、Q4_K 每步秒数（预期 10–20s/步 → 25 步 5–8 分钟）。

#### 4.9.1 同轮的两条真图产出（2026-10-18 13:17–14:05）

**① Colab CPU fp16 全程记时（sana06 1024² 4 步，隧道 `kick-trio-years-antenna`）**：
`progress 1/4 @588.4s` → `3/4 @1277.4s` → `4/4 @1627.4s`（第 1 步含编译预热，之后 **~345s/步**），
到 **2400s+ 仍卡在 `4/4 running`** —— **fp16 的 VAE 解码在 1024² 上比采样还慢**，整张图真实耗时 ≥40 分钟。**CPU fp16 档彻底判死。**
→ 与 4.9 结论一致：CPU 上 fp16 不是可用档，只是"能跑完"。

**② AI Horde 拿到真 SDXL（免费、无审查、零 pollen）**
（两条都成功：`horde_771001_640x960.png` Animagine XL 663371B luma155.6 sd55.6；
`horde_771002_640x960.png` AlbedoBase XL 615021B luma118.2 sd70.1；排队各约 19 分钟）：
`Animagine XL`（SDXL 动漫天花板）640×960 / 28 步 / k_euler，排队 331 → 0，
**1127s 出图**，产物 `~/th-img/horde_771001_640x960.png` **663371B / 640×960 / luma 155.6 / stddev 55.6**（真图）。
- ⚠️ 与 4.3 的旧记录吻合：**面积 ≤845² 才不被 403**（640×960=614400 < 714025 ✅）
- 结论：**等 GPU / 等 sdcpp 真机验证期间，SDXL 画质的现成来源是 Horde**（`scripts/horde_gen.sh`，
  `HORDE_MODELS='Animagine XL'` 单模型跑最稳，别混多模型让它排队轮换）

### 4.11 🔴 Kaggle 环境坑：GPU 检测别碰 nvidia-smi（2026-10-23 真机）

**事故**：Kaggle 已开 T4 x2，cell 1 却打印 `GPU : 无（CPU 档）`，报错原文
`nvidia-smi: could not convert string to float: '15360 \nTesla T4'`。

- **根因**：`nvidia-smi --query-gpu=name,memory.total --format=csv,noheader` 是**每卡一行**；
  双卡输出两行 → 旧代码 `split(',')[1]` 拿到 ` 15360 MiB\nTesla T4`（第二行卡名拼进来）→ `float()` 抛错
- **最坏的部分不是报错而是静默降级**：异常被 `except` 吞掉，`HAS_GPU` 停在 False，
  表面现象是"没有 GPU"，实际是解析失败 → 排查方向被带偏
- **规则（写死）**：GPU/显存探测**一律走 `torch.cuda`**
  （`is_available()` / `device_count()` / `get_device_name(0)` / `get_device_properties(0).total_memory` /
  `mem_get_info(0)`），**不要解析 nvidia-smi 文本**；它只配当人工排障命令
- **双卡口径**：`VRAM_GB` = **cuda:0 单卡**（SDXL fp16 约 14.6GB 够用），`VRAM_TOTAL_GB` 仅展示 ——
  单纯相加会误判模型装得下，实际扩散模型只跑在一张卡上
- **桩件 4/4**：双卡判定 + 单卡/合计数值 + 无卡提示（含 Restart Session 指引）+ API 抛错安全降级

**修复后真机验证（隧道 `drinking-flowers-revenue-personally`）**：`/health` 回
`engine:"kaggle" / gpu:true / gpu_name:"Tesla T4" / **vram_gb:14.6（单卡，不是 29GB）** / build:"kg1" / avail_ram_gb:28.5`；
`/generate` 832×1216@28 两张 = **29.4s / 29.6s**，1563939B / 1675257B，luma 133.6 / 161.3，
md5 `2f442c28…` / `a1afec5f…`（**不同 → seed 生效**）。全链路 `/health → /generate → /result` 通。
仍缺：animagine 加载秒数（cell 3 输出里）、sd-turbo 512×768@4（须改 `GPU_MODEL` 重跑 cell 3）、剩余 GPU 小时

### 4.15 「二次元写实」用 blue_pencil-XL v7（2026-10-24 实测选型）

用户要 **二次元写实（2.5D）**。同 prompt/seed/832×1216@28 对比后定选：

| 模型 | 出图 | 字节 | luma | 对比 | 边缘 | 备注 |
|---|---|---|---|---|---|---|
| **blue_pencil-XL v7.0.0** | 26s | 1.54MB | 143.6 | **63.5** | **31.1** | ✅ 2.5D 最佳（单文件 6.5GB，加载 44s） |
| animagine-4.0 | 27s | 1.37MB | 98.1 | 63.0 | 24.5 | 偏暗偏 2D |
| nova_xl_lcm | **13s(8步)** | 1.32MB | 141.9 | 45.2 | 19.6 | 最快最软，草稿用 |

**两个调用坑**：① `sca255/nova_xl_lcm` 只有 fp16 权重 → `from_pretrained(..., variant='fp16')`；
② `blue_pencil-XL` 是单文件 ckpt，`from_single_file(url)` 会 HEAD 校验失败
→ 必须 `hf_hub_download(repo, filename)` 落盘再 `from_single_file(local_path)`。

### 4.14 illustrious vs noobai 对照数据（2026-10-24，cuda:1 侧进程）

同 prompt / 同 seed（777001 人像、777002 全身）/ 832×1216@28，各自官方 cfg：

| 模型 | 加载 | 显存 | 出图 | 人像 | 全身 | 观感（含客观指标） |
|---|---|---|---|---|---|---|
| illustrious (cfg6.0) | 41s | 6.5GB | 26s/25s | 1.46MB luma132.2 **sd31.2** | 1.28MB luma139.7 **sd38.6** | 平、干净、赛璐璐/官方绘柄，脸部稳 |
| noobai (cfg5.0) | 63s | 6.5GB | 26s/27s | 1.39MB luma149.4 **sd42.2** | 1.13MB luma147.2 **sd56.4** | 对比/层次强，标签驱动猛，易"过火" |

**客观判别**：noobai 的亮度标准差比 illustrious 高 +11/+18（对比更强、光影更重）——
不用肉眼看也能区分。两者都与 animagine 同档（25–27s/张、6.5GB）；
Anima fp32 512×768 要 89–99s。

**稳定性铁律（两次 530 换来的）**：**不要在 notebook 内切模型/跑重活** ——
`POST /model` 加载 6.9GB 权重的峰值把 kernel 顶死过两次。
→ 换模型与批量出图一律走 `CUDA_VISIBLE_DEVICES=1` 的**侧进程**（脚本经 `/sh` 写入并 `setsid` 后台跑），
notebook 只留小模型甚至不用；本轮 A/B 全程 notebook 存活。

### 4.13 ✅ Anima 在 Kaggle T4 上可用（fp32 / 512×768 / 89-99s）—— 三个坑的解法（2026-10-24 实测）

用户问「真的不能用 anima 吗」→ **能用**，但必须按实测修正的三点来，否则必炸：

| 坑 | 报错原文 | 解法 |
|---|---|---|
| `t5_tokenizer` 装不上 | `ValueError: Either model_file or model_proto must be specified.`（repo 只有 tokenizer.json，**无 spiece.model**） | 用 `T5TokenizerFast` |
| 它的 config 不兼容 | `AttributeError: 'list' object has no attribute 'keys'`（`extra_special_tokens` 是 list，4.5x 要 dict） | 本地改 `{}` + 去掉 `tokenizer_class` |
| guider 缺失 | `TypeError: 'NoneType' object is not callable`（`load_components()` 不加载 guider） | `update_components(guider=ClassifierFreeGuidance(4.5))` |
| tokenizer 静默失败 | 同上 NoneType（Qwen2 tokenizer 也没载入） | 显式 `AutoTokenizer(..., subfolder='tokenizer')` |
| dtype 传参无效 | 警告 `Unexpected input 'dtype'` | 逐组件 `.to(torch.float32)`；**T4 无 bf16，fp16=100% 黑图** |

**性能**：加载 20–22s（HF 缓存）｜显存 10.5/14.56GB｜**512×768@24 = 89–99s/张**；
**640×960 必 OOM**（fp32 >14.5GB），且 `AnimaModularPipeline` **没有** `enable_model_cpu_offload`（实测 AttributeError）
→ **分辨率天花板 512×768**。

**多卡白捡的算力**：Kaggle T4 x2 是两张独立 15GB 卡，notebook 占 `cuda:0`，
Anima 可放 `CUDA_VISIBLE_DEVICES=1` 独立进程并行跑（本轮 4 张即如此）。
**文件取回**：0x0.st 停服、x0.at 弹验证码、tmpfiles 直链是 HTML → 用 **pomf2.lain.la** 或 **qu.ax** 出直链。

已写回 notebook cell 3：`GPU_MODEL='anima'` 走完整修正路径（默认 512×768@24），`/model` 可直接切。

### 4.12 ★ Kaggle 换模型：远端 `/model` + 三个可用的动漫底（2026-10-24）

用户嫌 `animagine-xl-4.0`「不好看」→ 核实并接入两个更强的 SDXL 动漫底：

| 档 | 仓库 | 核实结论 |
|---|---|---|
| `illustrious` | OnomaAIResearch/Illustrious-xl-early-release-v0 | **diffusers 格式 ✅**、437 likes、ungated → 默认 832×1216@28 cfg6.0 |
| `noobai` | Laxhar/noobai-XL-1.1 | **diffusers 格式 ✅**、190 likes、ungated → 默认 832×1216@28 cfg5.0 |
| ~~pony6~~ | AstraliteHeart/pony-diffusion-v6-xl | **HF API 401** → 已下架/受限，排除 |
| `anima` | circlestone-labs/Anima-Base-v1.0-Diffusers | 无 model_index.json（ModularPipeline），bf16 训练 → **T4 只能 fp32**，慢 |

**关键改动：模型可以远端切了**。cell 3 抽出 `load_gpu_model(name)`（删旧 pipe → 载新 → 512 测试图防黑图 →
更新全局 `GPU_MODEL`），cell 4 新增 `GET/POST /model`（后台线程，不阻塞隧道），`/health` 增加
`gpu_models` / `switching` / `switch_error` / `switch_last`。**以后换模型不用让用户改 cell 3 重跑**。
桩件 8/8 通过（默认加载、两次热切、未知模型 400、无 loader 400、黑图置空、GET 列表、后台切换状态）。

### 4.10 ★ 2026-10 新增免费 API 源实测（详见 docs/routes.md 第十三节）

**一句话结论**：CF Workers AI 额度**已恢复**（唯一「零成本+秒级+免绑卡」）；
NIM / Agnes 端点与鉴权方式已坐实但**都缺 key**（Agnes 是唯一明确支持 img2img 的免费候选）；
Prodia **判死**（域名无 A 记录）；Modal 按用户结论**降级为「有卡时备用」**。

| 源 | 免绑卡 | 实测证据 | 状态 |
|---|---|---|---|
| Cloudflare Workers AI | ✅（已有 token） | SDXL 1024²：**HTTP 200 / 980554B / md5 `12c5917f…` / luma 98.8**；flux-schnell 4.36s；lightning 8.17s | **主力** |
| Pollinations 匿名 | ✅ 零注册 | 402 `FREE_LIMIT`（1 张/45s）原文已录；等满后 turbo/sana 各出一张 512²（22630B / 23835B）；`/models` 匿名只回 `["sana"]` | **限流备用** |
| NVIDIA NIM | 二手来源称免卡 | `integrate…/v1/models` 匿名 200（84 个，全 LLM）；`ai.api.nvidia.com/v1/genai/…` → **401 `Header of type authorization was missing`** | 待 key |
| **Agnes AI** | ✅ 实测（key 到手后） | **t2i 200 / 760830B / 1024² / md5 `560b3b45…` / 12.5s**；i2i 格式被接受但**四次 503 `image queue is full`**（跨 17 分钟仍满） | **t2i 已验证**；i2i 待错峰 |
| **Claw Hunter Worker** | 自控端点 | `wrangler --version` → **`Error: Unsupported platform: android arm64 LE`**（workerd 无 android/arm64 构建） | **待桌面端部署**（客户端脚本已就绪） |
| Novita | 标称 $10/90天 | **400 `MISSING_API_KEY`** | 待 key |
| Segmind | 标称 100/天 | **401 `Missing Authorization or x-api-key`** | 待 key |
| Together | FLUX schnell Free | **401** Missing API key（注意：urllib 默认 UA 会被 CF 拦成 **403 error code: 1010**，脚本已统一加 UA） | 待 key |
| Prodia | — | `dns.google` 查 `api.prodia.com`：Status 0 **无 Answer**（无 A 记录） | **判死** |

**纪律执行**：`pol_edit.py`（kontext-pro 0.03 pollen/张）**本轮未跑** —— 烧 pollen 前先问用户（#4）。
`gen.sh` / `gen_quota.sh` 已注册 5 个新引擎名（`nim|agnes|novita|segmind|together`），
`--probe` 无 key 也能跑，输出直接带状态码与原文。

---

## 五、凭据清单（全部 600 权限，**绝不 commit**）

| 文件 | 内容 | 状态 |
|---|---|---|
| `~/.dsh/.pollinations-key` | `POLLINATIONS_KEY=sk_...`（visible-chickadee） | 余额 0.44 pollen |
| `~/.pollinations/credentials.json` | polli 设备 key（`account:[profile,usage,keys,machines]`，5 pollen 预算） | 有效 |
| `~/.dsh/.hf-router-token` | `HF_TOKEN=hf_...` | router 无额度（402） |
| `~/.dsh/.cf-ai.env` | `CF_AI_TOKEN` + `CF_ACCOUNT_ID` | 每日 10k neurons 已耗尽 |
| `~/.dsh/.horde-key` | Horde API key | 有效 |

---

## 六、Termux 环境踩坑（通用）

1. **`/tmp` 不存在** → 用 `~/tmp`
2. **Android argv 上限 131072** → base64 走文件，不要塞命令行
3. **pip**：`pypi.org` 直连可用；清华镜像 403。必须 `-i https://pypi.org/simple`
4. **无 C 扩展的包优先**：`orjson`/`pydantic`/`numpy`/`playwright` 在 Termux 编译极慢或失败
   - `orjson` 可用纯 stdlib `json` shim 替代（已写到 site-packages）
   - `playwright` 无 arm64 wheel，装不上
5. **chromium**：`/data/data/com.termux/files/usr/lib/chromium/chrome`（真二进制），
   `chromium-browser` 是 launcher 脚本；必须 `--no-sandbox`
6. **后台进程**：`nohup setsid ... & disown`，否则 bash 调用超时会连带 SIGKILL
7. **Go 二进制 DNS**：见 4.4，需 proot 绑 resolv.conf
8. **Python heredoc** 里用 `False` 不是 `false`；嵌套 heredoc 用唯一分隔符避免解析冲突
9. **`read_image` 不可用**：当前模型 `z-ai/glm-5.3` 不支持图片输入 → 无法自查图，
   靠 PIL 读尺寸/md5 + 用户判断

---

## 七、开发纪律

1. 每次任务完成必须 `git commit` + `git push`，并更新本文件
2. **所有结论必须实测**，禁止根据 README/文档推断（用户已纠正多次）
3. 声称"可用"前必须给出：HTTP 状态码 + 字节数 + md5 或尺寸
4. **不要烧付费额度**：用户明确要求停止无节制消耗 pollen（"别一直用额度了"）
5. 失败的路线要记录**错误原文**，避免下次重复踩坑
6. 不要重复生成已被否决的方案；创作任务先确认方向
7. 长任务放后台，用 `job_output` 收，不要 busy-poll

---

## 八、待办 / 下一步

- [x] **Colab CPU 档 v2 真机验证**：加载器可用（`cpu_ready:true` / `cpu_engine:diffusers-fp16`），
      optimum-intel 墙已绕过；但 fp16 推理慢到不可用（sd_turbo 4步512px >25min 未出图）→ 已出 v3
- [x] **★ bf16 判定（2026-10-18 13:17 真机拿到）**：`/health` → `cpu_bf16:false` → 免费档 CPU 无
      `avx512_bf16`/`amx_bf16`，**bf16 路正式证伪**，v6 自动探测行为正确（跳过 bf16 直上 fp32）
- [ ] **★ 重开 notebook 跑 v7（sdcpp）**：File→Open notebook→GitHub 开新副本 → 跑 1→2→4 →
      新 URL 写回 `~/.dsh/.colab-url` → `GET /sdcpp/build` 预热（看 `/health` 的 `sdcpp_building/error`）
      → `POST /generate {"cpu_preset":"sdcpp","width":832,"height":1216,"steps":25}` → 把
      build 耗时、每步秒数、产物校验写进 4.9。**这是 CPU 上唯一能跑完 SDXL 的路**
- [x] **★ 2026-10 新源接入**：CF 额度已恢复（真图已出）；NIM/Agnes/Novita/Segmind/Together 脚本就绪并探活，
      只缺 key（放 `~/.dsh/.{nim,agnes,novita,segmind,together}-key`）；Prodia 判死；Modal 降级（详见 4.10 + routes.md §13）
- [x] **★ Pollinations Device key 直付复测**：kontext-pro → 401 原文；同 key klein-4b → 200/141451B PNG。
      **Device key 通路通**，kontext 档待再授权 0.03 定性（见 4.2 + routes.md §13.10）
- [x] **★ Agnes 接入**：t2i 已验证出图（1024²/760830B）；i2i 通道格式被接受但连续 503 queue full，
      需错峰；key 落 `~/.dsh/.agnes-key`
- [ ] **Claw Hunter 部署（待桌面端）**：Termux 上 `workerd` 无 android/arm64 构建（原文已录），
      需在 x86_64/arm64 Linux 或 macOS 上 `npx wrangler login && npx wrangler deploy`，
      部署后把 URL 写 `~/.dsh/.clawhunter-url`，客户端 `scripts/clawhunter_gen.py` 即可用
- [x] **★ Kaggle 版适配**：`examples/anima_kaggle.ipynb`（BUILD=kg1）已完成 5 个适配点，裁掉 sdcpp/视频，
      桩件回归通过（/health 无 video_*/sdcpp_*、engine=kaggle、video→400、GPU 出图 OK、路由 10 条）
- [ ] **★ Kaggle 实机补三项**：① animagine 加载秒数 ② sd-turbo 512×768@4 全项 ③ 剩余 GPU 小时
      （拿到 URL 后我跑 `/health` + `/generate` 各一次做端到端验证，再回填 routes.md §14.4）
- [ ] **★ Kaggle SDXL 验证（待用户操作）**：`examples/kaggle_sdxl_probe.ipynb` 已备好（3 格：依赖+GPU探测 /
      animagine 832×1216@28 / sd-turbo 512×768@4）；**卡点=Kaggle 手机验证 + 浏览器点 Accelerator/Internet**，
      本轮零实测数据。跑完把 GPU 型号/显存/两图耗时字节 md5/剩余 GPU 小时贴回来，补进 routes.md §14
- [ ] **★ Device key 10-24 到期**：余额 4.703 会作废；已确认可付 = `flux.1-schnell` 0.002 / `flux.2-klein-4b` 0.005（t2i+edits）；
      kontext-pro 仍 401。若还要用，得在到期前决定（当前无待办消耗）
- [ ] **★ SDXL 画质（用户明确要）**：bf16 已证伪（上游结论见上一行），剩余两条：sdcpp(v7，待真机) / Modal 免费 GPU（`scripts/modal_sdxl.py`，需 `modal token new`）；先重开 notebook 跑 **cell1**（看 CPU 型号+bf16 判定）
      和 **cell8**（bf16/fp32/fp16 单步实测）→ 若 bf16 真快则 CPU 走 bf16；
      否则走 `scripts/sdcpp_colab.sh`（Q4_K 2.8GB，CPU 唯一能跑完 SDXL 的路）或 `scripts/modal_sdxl.py`（A10G 3s/张）
- [ ] **★ Colab CPU 档 v3 待真机验证**：**必须开新副本**（F5 不重拉 GitHub，当前 runtime 还是 v2）
      → cell 1→2→4 → 新 URL 写回 ~/.dsh/.colab-url → 提 `cpu_preset:"sd_turbo"`（现在走 fp32）
      → 看 `/status/<jid>` 的 `progress`/`elapsed` 判断真实速度，把秒数记进 4.7 节
- [ ] **★ Colab 线（当前主力）**：GPU 配额耗尽中，恢复后：
      ① 新标签页开 notebook（File→Open notebook→GitHub，别用旧标签）② 跑 1→2→3→4
      ③ 新 URL 更新 `~/.dsh/.colab-url` ④ cell 5 自测一张 832×1216@28（应 ~30s）⑤ cell 6 批量
      CPU 档期间也能用：notebook 自动分流 OpenVINO sana06（慢，分钟级/张）
- [ ] **创作任务**：等用户在现有 9 张候选里选方向（k2/k6/k7 + fix_A/B/C + pose_P1/P2/P3），
      **不再自行生成新图**；用户点名要哪个方向再动 pollen
- [x] **Horde PonyXL md5 相同排查**：已破案 —— PonyXL worker 确定性渲染（clip_skip=2+固定seed），
      换 AlbedoBase XL 正常；illustrious-SDXL 是纯黑审查图（YAVG=0.0），弃用
- [ ] **Gemini Cookie**：等用户提供 `__Secure-1PSID` + `__Secure-1PSIDTS`，然后测 `gemini-image` 的 img2img
      （gw2api 二进制就绪 + DNS 已用 proot 修好，纯等 Cookie）
- [ ] **新发现待核实**：Device key（credentials.json）能付 kontext-pro edits 费，余额还有 4.72 pollen；
      但 pollen 是 7 天设备预算（10-24 到期），用不用、怎么用由用户拍板，**先问再烧**
- [x] **Vercel AI Gateway 已实测：必须绑卡，不是免费**（2026-10-17）
      key 已写入 `~/.dsh/.vercel-gw-key`（vck_8OCcwUkB...），但调用 → **HTTP 403**
      `AI Gateway requires a valid credit card on file to service requests`
      官方 getting-started 原文也写 "To use free AI Gateway Credits, **add a valid payment method**"
      → 没有可绑的卡就用不了，这条路**封存**；脚本 `vercel_img.py` 保留待有卡时启用
- [ ] **Replicate Try-for-Free**（`scripts/replicate_edit.py`，已写好待 token）
      注册 replicate.com → api-tokens → `~/.dsh/.replicate-token`，白嫖 kontext-pro 有限次数
- [ ] **新池调研结论**（docs/new-pools-research.md）：
      ❌ 已死：HF Inference 免费额度（2026-10-08 取消，402）、HF Spaces ZeroGPU（额度封顶）、
      Gemini 官方 API 图像（无免费档）、Together（无试用）、fal 匿名 API（401，只能网页手动 15 次/天）
      ✅ 可用：AI Horde（10 个动漫模型实测 9 个能出图）、Pollinations 匿名、Replicate 免费集合（待验是否要卡）
      ❌ 不可用：Vercel（必须绑卡，403）
      待用户拍板：quest 手动 claim（回血 2–3 pollen）、HF PRO $9/月（$2 credits + 8× ZeroGPU）
- [ ] **Perchance**：如需再战，用 EzSolver + 真 Chrome（或 termux-x11）
- [ ] 公益站注册（需用户提供邮箱/邀请码）：moyuu.cc / vsllm.com / freeapi.dgbmc.top / aotera.cc
- [ ] 已排除：InferencePort（401）、Craiyon（连接失败）、DeepInfra/Together/HF 匿名（要 key）、
      ai-image-generator.co（301 到无关站点）
