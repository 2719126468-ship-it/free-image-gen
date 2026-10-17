# 项目记忆文档 (MEMORY.md)

> 最后更新：2026-10-17（第 2 次修订：停烧额度 + Device key 发现 + Horde 黑图破案）
> 目标读者：后续参与本项目的 AI 编程助手（Codex / DSH / Claude）
> 用途：新开会话先读此文档恢复上下文，省 Token 且防失忆。

---

## 一、项目概况

- **项目名称**：free-image-gen — 免费 AI 生图/图生图路线调研与工具集
- **运行环境**：Android 10 + Termux（无 root，arm64，Python 3.14，无 GPU）
- **Git 仓库**：`~/free-image-gen`，远程 `github.com/2719126468-ship-it/free-image-gen`，分支 `main`，**每轮任务结束必须 commit + push**
- **核心文档**：`docs/routes.md`（所有实测结论、错误原文、配额机制，1–12 节）
- **当前 HEAD**：`ada9b34`

### 目录结构
```
~/free-image-gen/
├── MEMORY.md              ← 本文件
├── README.md              ← 路线速览（txt2img + img2img 两张表）
├── docs/
│   ├── routes.md          ← 完整实测调研（12 节，权威）
│   └── new-pools-research.md ← 新池调研（含被实测推翻的 3 条传言）
└── scripts/
    ├── vercel_img.py      ← ★★ Vercel AI Gateway img2img（$5/30天免费，kontext-pro）
    ├── replicate_edit.py  ← ★ Replicate Try-for-Free img2img（有限次数）
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
- **状态：用户尚未选定任何一版**。现有候选（全在 `~/th-img/`，不再新增）：
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
| **Vercel AI Gateway** `vercel_img.py` | Vercel 账号（免费不绑卡） | ✅ | ✅ **kontext-pro** | 20–60s | **$5/30天循环 ≈125张** | 商业标准 |
| **Replicate Try-for-Free** `replicate_edit.py` | Replicate 账号（免费） | ✅ | ✅ kontext-pro | 20–60s | 有限次数 | 商业标准 |
| **AI Horde** `horde_img2img.py` | 匿名 `0000000000` | ✅ | ✅ `source_image` | **45s–21min** | 无限 | **无** |
| **Pollinations 新版** `pol_edit.py` | pollen key | ✅ | ✅ **kontext-pro** | 20–40s | 0.03 pollen/张 | **松** |
| **Pollinations 匿名** `pol_anon.py` | 无 | ✅ | ❌ **已证伪** | 1–5s | 1张/45s/IP | 无 |
| Gemini web 反代 | Gemini Cookie | ✅ | ✅ | 快 | 普号免费 | **禁 NSFW** |
| HF ZeroGPU `anima_gen.sh` | HF token | ✅ | — | 1–10s | 5min GPU/天（已耗尽） | 无 |
| Cloudflare `gen_image.sh cf` | API token | ✅ | — | 5–15s | ~50张/天 | 有过滤 |
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

- [ ] **创作任务**：等用户在现有 9 张候选里选方向（k2/k6/k7 + fix_A/B/C + pose_P1/P2/P3），
      **不再自行生成新图**；用户点名要哪个方向再动 pollen
- [x] **Horde PonyXL md5 相同排查**：已破案 —— PonyXL worker 确定性渲染（clip_skip=2+固定seed），
      换 AlbedoBase XL 正常；illustrious-SDXL 是纯黑审查图（YAVG=0.0），弃用
- [ ] **Gemini Cookie**：等用户提供 `__Secure-1PSID` + `__Secure-1PSIDTS`，然后测 `gemini-image` 的 img2img
      （gw2api 二进制就绪 + DNS 已用 proot 修好，纯等 Cookie）
- [ ] **新发现待核实**：Device key（credentials.json）能付 kontext-pro edits 费，余额还有 4.72 pollen；
      但 pollen 是 7 天设备预算（10-24 到期），用不用、怎么用由用户拍板，**先问再烧**
- [ ] **★ 下一步：Vercel AI Gateway**（`scripts/vercel_img.py`，已写好待 key）
      用户注册 vercel.com（**免费、别绑卡**）→ Dashboard → AI Gateway → API Keys → Create
      → `echo 'AI_GATEWAY_API_KEY=vck_...' > ~/.dsh/.vercel-gw-key && chmod 600`
      → 即可 $5/30 天循环跑 `bfl/flux-kontext-pro`（≈125 张/月），彻底摆脱 pollen 焦虑
- [ ] **Replicate Try-for-Free**（`scripts/replicate_edit.py`，已写好待 token）
      注册 replicate.com → api-tokens → `~/.dsh/.replicate-token`，白嫖 kontext-pro 有限次数
- [ ] **新池调研结论**（docs/new-pools-research.md）：
      ❌ 已死：HF Inference 免费额度（2026-10-08 取消，402）、HF Spaces ZeroGPU（额度封顶）、
      Gemini 官方 API 图像（无免费档）、Together（无试用）、fal 匿名 API（401，只能网页手动 15 次/天）
      ✅ 可用：Vercel $5/月、Replicate 免费集合、AI Horde、Pollinations 匿名
      待用户拍板：quest 手动 claim（回血 2–3 pollen）、HF PRO $9/月（$2 credits + 8× ZeroGPU）
- [ ] **Perchance**：如需再战，用 EzSolver + 真 Chrome（或 termux-x11）
- [ ] 公益站注册（需用户提供邮箱/邀请码）：moyuu.cc / vsllm.com / freeapi.dgbmc.top / aotera.cc
- [ ] 已排除：InferencePort（401）、Craiyon（连接失败）、DeepInfra/Together/HF 匿名（要 key）、
      ai-image-generator.co（301 到无关站点）
