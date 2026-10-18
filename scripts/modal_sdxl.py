#!/usr/bin/env python3
"""
modal_sdxl.py —— 在 Modal 免费 GPU 上跑 SDXL 动漫（"现在就要画质"最可靠的路）

为什么需要它（2026-10-18 结论）：
  · Colab 免费 CPU：SDXL 两难 —— fp32 权重 14.7GB 装不进 12.6GB；fp16 装得下但 CPU 慢一个量级
  · Colab GPU：配额耗尽，等恢复不可控
  · Modal：注册无需绑卡，Starter 每月 $30 免费额度，按秒计费、空闲缩容到零
           A10G 上 SDXL 约 3 秒/张（1024²），$30 ≈ 数万张/月量级

一次性准备（在你自己的机器/任意能上网的环境）：
    pip install modal
    modal token new          # 浏览器授权，写入 ~/.modal.toml
    modal run scripts/modal_sdxl.py --prompt "1girl, solo, blue hair, masterpiece"

之后想批量/服务化：
    modal deploy scripts/modal_sdxl.py     # 起一个 HTTPS 端点
"""
import modal

APP = "sdxl-anime"
MODEL_ID = "cagliostrolab/animagine-xl-4.0"   # SDXL 动漫天花板，ungated

# 镜像：只装必要依赖；模型权重缓存在 Volume 里，避免每次冷启动重下 7GB
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("torch==2.5.1", "diffusers==0.32.2", "transformers==4.46.3",
                 "accelerate==1.1.1", "safetensors", "pillow")
)
cache = modal.Volume.from_name("hf-cache", create_if_missing=True)

app = modal.App(APP)


@app.cls(image=image, gpu="A10G", timeout=600,
         volumes={"/root/.cache/huggingface": cache},
         scaledown_window=120)
class SDXL:
    @modal.enter()
    def load(self):
        import torch
        from diffusers import StableDiffusionXLPipeline
        self.pipe = StableDiffusionXLPipeline.from_pretrained(
            # animagine-xl-4.0 仓库里没有 fp16 变体（只有 fp32 safetensors），
            # diffusers 会下载 fp32 再按 torch_dtype 转成 fp16 —— 显存只占转换后那份。
            MODEL_ID, torch_dtype=torch.float16, use_safetensors=True,
        ).to("cuda")
        self.pipe.set_progress_bar_config(disable=True)
        try:
            self.pipe.enable_vae_slicing()
        except Exception:
            pass
        print("[+] SDXL ready on A10G")

    @modal.method()
    def txt2img(self, prompt: str, negative: str = "", width: int = 832,
                height: int = 1216, steps: int = 28, guidance: float = 7.0,
                seed: int = -1):
        import torch, io, base64
        g = torch.Generator("cuda").manual_seed(seed if seed >= 0 else torch.seed())
        img = self.pipe(
            prompt=prompt,
            negative_prompt=negative or "censor, mosaic, (worst quality, low quality:1.4), bad anatomy, watermark",
            width=width, height=height, num_inference_steps=steps,
            guidance_scale=guidance, generator=g,
        ).images[0]
        buf = io.BytesIO(); img.save(buf, format="PNG")
        return img.size, len(buf.getvalue()), base64.b64encode(buf.getvalue()).decode()


@app.local_entrypoint()
def main(prompt: str = "1girl, solo, blue hair, masterpiece, best quality",
         negative: str = "", width: int = 832, height: int = 1216,
         steps: int = 28, guidance: float = 7.0, seed: int = -1,
         out: str = "modal_sdxl.png"):
    import base64, time
    t0 = time.time()
    size, nbytes, b64 = SDXL().txt2img.remote(
        prompt, negative, width, height, steps, guidance, seed)
    open(out, "wb").write(base64.b64decode(b64))
    print("[+] %s  %s  %.0fKB  总耗时 %.1fs" % (out, size, nbytes / 1024, time.time() - t0))
