# free-image-gen

免费 AI 生图 / **图生图（img2img）** 工具集，覆盖不同额度、速度与质量档位。所有结论均来自 2026-10 在 Android/Termux（无 GPU）上的实测。

```bash
./scripts/gen.sh "1girl, blue long hair, anime realistic"    # auto: 自动选有额度的引擎
./scripts/gen.sh "..." out 12345 horde                        # 指定引擎
./scripts/gen_quota.sh                                        # 查看各引擎实时额度
```

## 路线对比

### 文生图（txt2img）

| 引擎 | 认证 | 额度 | NSFW | 速度 | 质量 |
|---|---|---|---|---|---|
| **horde** AI Horde | 匿名 `0000000000` | **无限量** | **无审查** | 37s–13min | 中高 |
| **anima** HF ZeroGPU | HF token | 5 min GPU/天 | 无审查 | 1–10s | **最高** |
| **cf** Cloudflare | API token | ~50 张/天 | **有过滤** | 5–15s | 高 |
| **poll** Pollinations 匿名 | 无 | 1 张/45s | 可关 | 10–30s | 低 |
| **th** TensorHub | 无 | 匿名 2 次 | 无审查 | 3–4min | 中 |
| **colab** Google Colab | Google 账号 | 12h/会话 | 无审查 | 5–10min/张 | 任意 |

`gen.sh auto` 模式按 anima → horde → cf → poll 自动降级，谁有额度用谁。

### 图生图 / 图像编辑（img2img）

| 引擎 | 认证 | 免费额度 | 审查 | 速度 | 说明 |
|---|---|---|---|---|---|
| **`vercel_img.py`** | Vercel 账号 **+ 必须绑卡** | $5/30 天（绑卡后解锁） | 商业标准 | 20–60s | ⚠️ 不绑卡实测 403 |
| **`replicate_edit.py`** | Replicate 账号（免费） | Try-for-Free 有限次数（含 kontext-pro） | 商业标准 | 20–60s | 白嫖高质量编辑 |
| **`horde_img2img.py`** | 匿名 | **无限**（排队 45s–20min） | **无审查** | 慢 | 无审查首选 |
| **`pol_edit.py`** | pollen key | 0.03 pollen/张 | 松 | 20–40s | 烧钱，余额告急 |
| **`kontext_edit.py`** | HF token | 已 402 | — | — | 停用 |

详细调研见 [docs/routes.md](docs/routes.md)（踩坑记录、错误原文、配额机制）与
[docs/new-pools-research.md](docs/new-pools-research.md)（新池调研，含被实测推翻的传言）。

## 快速开始

### 0. img2img：Vercel AI Gateway（**必须先绑卡**，实测不绑卡 403）

```bash
# 注册 vercel.com → 添加有效支付方式 → Dashboard → AI Gateway → API Keys → Create
echo 'AI_GATEWAY_API_KEY=vck_xxx' > ~/.dsh/.vercel-gw-key && chmod 600 ~/.dsh/.vercel-gw-key

./scripts/vercel_img.py ref.jpg out.jpg "把尾巴换成两条人腿，膝盖分开，双脚踩在床垫上" \
    bfl/flux-kontext-pro
```

> 实测原文：`AI Gateway requires a valid credit card on file to service requests`（HTTP 403）。
> 没有可绑的卡 = 这条路用不了。

### 0.5 img2img：Replicate Try-for-Free（白嫖有限次数）

```bash
echo 'REPLICATE_API_TOKEN=r8_xxx' > ~/.dsh/.replicate-token && chmod 600 ~/.dsh/.replicate-token
./scripts/replicate_edit.py ref.jpg out.jpg "把尾巴换成两条人腿" black-forest-labs/flux-kontext-pro
```

### 1. AI Horde（零配置，推荐先跑通）

```bash
./scripts/horde_gen.sh "masterpiece, 1girl, solo, blue long hair" ~/Pictures 12345
```

无需注册、无需 key。默认轮换 4 个模型；遇到 worker 审查返回的纯黑图会自动换下一个模型。

### 2. Anima（质量最高，需 HF token）

```bash
echo 'HF_TOKEN=hf_xxx' > ~/.dsh/.hf-token && chmod 600 ~/.dsh/.hf-token
./scripts/anima_gen.sh "1girl, solo, blue long hair, sitting on bed" ~/Pictures
```

在 https://huggingface.co/settings/tokens 建 read token。默认 Space `mrfakename/anima-v1-fast`，可用 `ANIMA_SPACE=` 切换。

### 3. Cloudflare（速度最快）

```bash
cat > ~/.dsh/.cf-ai.env <<'EOF'
CF_ACCOUNT_ID=your_32_hex_account_id
CF_AI_TOKEN=your_api_token
EOF
chmod 600 ~/.dsh/.cf-ai.env
./scripts/gen.sh "..." ~/Pictures 1 cf
```

### 4. Google Colab（突破每日上限）

打开 [examples/anima_colab.ipynb](examples/anima_colab.ipynb)，选 GPU 运行时，跑前 3 格。第 3 格会打印 `https://xxx.trycloudflare.com`，然后：

```bash
echo 'https://xxx.trycloudflare.com' > ~/.dsh/.colab-url
./scripts/colab_gen.sh "1girl, solo, blue long hair"    # 自动读取 url 文件
```

12 小时会话约 70–140 张，是本地免费方案的 10–20 倍产能。

## 凭据存放位置

所有密钥都在仓库**外**，不会误推：

| 文件 | 内容 |
|---|---|
| `~/.dsh/.hf-token` | `HF_TOKEN=...` |
| `~/.dsh/.cf-ai.env` | `CF_ACCOUNT_ID=...` / `CF_AI_TOKEN=...` |
| `~/.dsh/.colab-url` | Colab 隧道地址 |

## 目录结构

```
scripts/
  gen.sh          统一入口，auto 模式自动降级
  gen_quota.sh    实时额度探测
  anima_gen.sh    HF ZeroGPU Anima-2.9B
  horde_gen.sh    AI Horde（模型轮换 + 黑图检测）
  colab_gen.sh    Colab notebook 客户端
  gen_image.sh    Cloudflare / Pollinations / HF Space
  th_gen.sh       TensorHub
docs/routes.md    完整调研报告
examples/         Colab notebook
```

## 已知限制

- **Anima 每日 6–7 张**：ZeroGPU 配额是账号级全局共享（换 Space 不涨额度），且扣的是 Space **声明的** duration 而非实际运行时间。免费档 300 秒 ÷ 45 秒/次 ≈ 6 张。
- **Cloudflare 有 NSFW prompt 过滤**，直出成人内容会被拒。
- **AI Horde 的 `censored` 元数据不可信**：实测 `state=ok censored=False` 却返回纯黑图，脚本改用 `ffmpeg signalstats` 的 YAVG<6 判定。
- **Horde 预签名 URL 几分钟失效**，必须立即下载。
- Colab 会话 12 小时是免费档硬限，到点需重跑 notebook 前 3 格。

依赖：`bash`、`python3`、`curl`、`ffmpeg`（用于 webp→png 与黑图检测）、`python curl_cffi`。
