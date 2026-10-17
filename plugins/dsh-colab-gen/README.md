# @local/dsh-colab-gen

把远端 **Google Colab 免费 T4**（[examples/anima_colab.ipynb](../../examples/anima_colab.ipynb) 起的 Flask + cloudflared 隧道）变成 DSH 的原生工具 `colab_gen`：无审查生图 / 生视频，结果下载回本机。

## 它解决什么

你不用打开浏览器、不用手跑 notebook、不用记隧道地址。装好后直接在 DSH 对话里说「用 Colab 画一张 …」，模型调用 `colab_gen` 工具，自动：

1. 从 `~/.dsh/.colab-url`（或 `COLAB_URL` / 参数 `url`）读隧道地址
2. `action=health` 判断当前是 GPU 档还是 CPU 档
3. 提交任务 → 轮询 → 把图/视频拉回本机 `/sdcard/Download`

## 前置：Colab 端要先跑起来

1. 打开 [examples/anima_colab.ipynb](../../examples/anima_colab.ipynb)，运行时改 GPU
2. 依次跑第 1 → 2 → 3 → 4 格
3. 第 4 格打印 `https://xxx.trycloudflare.com`，把它存本机：

```bash
echo 'https://xxx.trycloudflare.com' > ~/.dsh/.colab-url
```

会话结束 / 隧道变化后重跑第 4 格并更新这个文件。

## 安装插件

```
DSH → 插件 → 添加插件 → 本地目录：
/data/data/com.termux/files/home/free-image-gen/plugins/dsh-colab-gen
```

启用后重载，`colab_gen` 工具即生效。

## 工具用法

| action | 作用 | 关键参数 |
|---|---|---|
| `health` | 看档位 / GPU / 队列 / 视频模型是否已加载 | — |
| `generate` | 出一张图（Anima/SDXL） | `prompt` `width` `height` `steps` `seed` |
| `batch` | 批量 | `prompts[]` `n_per_prompt` |
| `video` | Wan2.2 出 5s 短片 | `prompt` `image_path`(I2V) `frames` `steps` |
| `upload` | 把本地图推到 Colab 供 I2V | `local_file` |
| `flush` | 让 Colab 端把产出搬进 Drive | — |
| `status` | 查某 job 并在完成时落盘 | `jid` |

### 例子

```js
// 出图
colab_gen({ action: "generate", prompt: "1girl, solo, blue long hair", width: 832, height: 1216, steps: 22 })

// 图生视频（先上传参考图拿路径，再 I2V）
colab_gen({ action: "upload", local_file: "/sdcard/Download/xxx.png" })
colab_gen({ action: "video", prompt: "gentle camera push in, hair swaying", image_path: "<上一步返回的 path>" })
```

## 关键设计：模型懒加载（回答"会不会太大"）

- **只跑图 → 永远不下视频权重**。视频模型（`Wan2.2-TI2V-5B`，~10-20GB）只有在第一次 `kind=video` 请求时，服务端才 `load_video_pipe()` 下载。
- **单 worker 串行队列**。notebook 里一个 worker 线程消费队列，同一时刻只有一个推理任务，避免 T4 单卡并发 OOM（这是旧版给每个 job 起一个线程的严重 bug）。
- **结果落盘，不留内存**。旧版把 PNG bytes 全堆在 `JOBS` dict 里，12.6GB 系统内存撑不住大批产出；现在每个结果写文件，`/result/<jid>` 从磁盘读。
- Colab 临时盘 102GB 是「工位」不是「仓库」：会话结束即清空，所以要靠本插件下载回本地、或 `flush` 搬进 Drive（免费 Drive 仅 15GB）。

## 约束（免费档实测）

- 会话 **3.5-6h**（不是 12h），到点进程被杀，需重跑 notebook 第 4 格换新隧道。
- 可能连到 **CPU 档**：`health` 会报 `gpu=false`，此时生成被禁，去做后处理。
- 系统内存 **12.6GB 是正常的**（25.2GB 是把 15GB 显存算进去了）。免费档天花板 = Anima + SDXL + Wan2.2 5B；Flux/14B 会 OOM。
