# free-image-gen

免费 AI 生图工具集：**5 条独立路线**，覆盖不同额度、速度与质量档位。所有结论均来自 2026-10 在 Android/Termux（无 GPU）上的实测。

```bash
./scripts/gen.sh "1girl, blue long hair, anime realistic"    # auto: 自动选有额度的引擎
./scripts/gen.sh "..." out 12345 horde                        # 指定引擎
./scripts/gen_quota.sh                                        # 查看各引擎实时额度
```

## 五条路线对比

| 引擎 | 认证 | 额度 | NSFW | 速度 | 质量 |
|---|---|---|---|---|---|
| **horde** AI Horde | 匿名 `0000000000` | **无限量** | **无审查** | 37s–13min | 中高 |
| **anima** HF ZeroGPU | HF token | 5 min GPU/天 | 无审查 | 1–10s | **最高** |
| **cf** Cloudflare | API token | ~50 张/天 | **有过滤** | 5–15s | 高 |
| **poll** Pollinations | 无 | 1 张/45s | 可关 | 10–30s | 低 |
| **th** TensorHub | 无 | 匿名 2 次 | 无审查 | 3–4min | 中 |
| **colab** Google Colab | Google 账号 | 12h/会话 | 无审查 | 5–10min/张 | 任意 |

`gen.sh auto` 模式按 anima → horde → cf → poll 自动降级，谁有额度用谁。

详细调研（含踩坑记录、错误信息原文、配额机制实测）见 [docs/routes.md](docs/routes.md)。

## 快速开始

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
