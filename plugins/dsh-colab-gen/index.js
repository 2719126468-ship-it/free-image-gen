/**
 * dsh-colab-gen —— Host 插件
 *
 * 把 Colab 免费档（examples/anima_colab.ipynb）变成一个原生 harness 工具 `colab_gen`。
 * 直连 notebook 里 Flask 服务的 cloudflared 隧道端点（/health /generate /batch
 * /status /result /upload /flush），不 spawn 任何子进程、零运行时依赖。
 *
 * 隧道地址解析顺序：参数 url > 环境变量 COLAB_URL > ~/.dsh/.colab-url。
 * 生成的图/视频下载回本机（默认 /sdcard/Download），Colab 端 /content 会话结束会清空，
 * 所以本插件负责把它落到本地，这是“DSH 端直调”的关键一步。
 *
 * 模型懒加载：只跑图时永远不下视频权重；kind=video 时服务端首次才下 ~10-20GB。
 */

import { existsSync, readFileSync, mkdirSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'

export const inject = ['tools']

const URLFILE = join(process.env.HOME || '/data/data/com.termux/files/home', '.dsh', '.colab-url')
const DEFAULT_OUTDIR = '/sdcard/Download'
const RESULT_MARK = 'dsh-colab'

function resolveUrl(explicit) {
  const u = (explicit || process.env.COLAB_URL || '').trim()
  if (u) return u.replace(/\/+$/, '')
  try {
    if (existsSync(URLFILE)) return readFileSync(URLFILE, 'utf8').trim().replace(/\/+$/, '')
  } catch {}
  return ''
}

async function httpJson(url, opts = {}, timeoutMs = 30000) {
  const ctrl = new AbortController()
  const t = setTimeout(() => ctrl.abort(), timeoutMs)
  try {
    const res = await fetch(url, { ...opts, signal: ctrl.signal })
    const text = await res.text()
    let data
    try { data = JSON.parse(text) } catch { data = { raw: text.slice(0, 500) } }
    if (!res.ok && !data.error) data.error = `HTTP ${res.status}`
    return { ok: res.ok, status: res.status, data }
  } catch (e) {
    // 隧道挂了 / DNS 失败 / 会话被掐断是最高频的失败，必须转成结构化错误而不是抛出。
    const msg = ctrl.signal.aborted ? 'timeout (会话可能已断，重跑 notebook 第 4 格换新隧道)' : String(e?.message ?? e)
    return { ok: false, status: 0, data: { error: `连不上隧道: ${msg}` } }
  } finally {
    clearTimeout(t)
  }
}

async function httpBinary(url, timeoutMs = 300000) {
  const ctrl = new AbortController()
  const t = setTimeout(() => ctrl.abort(), timeoutMs)
  try {
    const res = await fetch(url, { signal: ctrl.signal })
    if (!res.ok) return { ok: false, error: `HTTP ${res.status}` }
    const buf = Buffer.from(await res.arrayBuffer())
    return { ok: true, buf, type: res.headers.get('content-type') || '' }
  } catch (e) {
    const msg = ctrl.signal.aborted ? 'download timeout' : String(e?.message ?? e)
    return { ok: false, error: `下载失败: ${msg}` }
  } finally {
    clearTimeout(t)
  }
}

function saveBlob(buf, outdir, jid, ext) {
  mkdirSync(outdir, { recursive: true })
  const path = join(outdir, `${RESULT_MARK}_${jid}.${ext}`)
  writeFileSync(path, buf)
  return path
}

/** 提交一个任务并轮询到 done/error，返回最终 job 记录。 */
async function runJob(baseUrl, payload, pollMs, maxWaitMs, signal) {
  const submit = await httpJson(`${baseUrl}/generate`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(payload),
  }, 60000)
  if (!submit.ok || !submit.data.id) {
    return { ok: false, error: submit.data.error || 'submit failed' }
  }
  const jid = submit.data.id
  const t0 = Date.now()
  let last = ''
  const trail = []
  while (!signal?.aborted) {
    const s = await httpJson(`${baseUrl}/status/${jid}`, {}, 30000)
    const st = s.data.status || '?'
    if (st !== last) { trail.push(`${st}@${Math.round((Date.now() - t0) / 1000)}s`); last = st }
    if (st === 'done' || st === 'error') return { ok: st === 'done', jid, job: s.data, trail }
    if (Date.now() - t0 > maxWaitMs) return { ok: false, jid, error: `timeout after ${maxWaitMs / 1000}s`, trail }
    await new Promise((r) => setTimeout(r, pollMs))
  }
  return { ok: false, jid, error: 'cancelled', trail }
}

const PARAMETERS = {
  type: 'object',
  additionalProperties: false,
  properties: {
    action: {
      type: 'string',
      enum: ['health', 'generate', 'batch', 'video', 'upload', 'flush', 'status'],
      description:
        'health 查档位/GPU/队列 · generate 生一张 · batch 批量（prompts 数组）· ' +
        'video 用 Wan2.2 生成短片（首次会触发下载视频权重）· upload 上传参考静帧 · ' +
        'flush 让 Colab 端把产出搬进 Drive · status 查某 job id。',
    },
    url: {
      type: 'string',
      description: 'Colab 隧道地址 https://xxx.trycloudflare.com；缺省读 COLAB_URL 或 ~/.dsh/.colab-url。',
    },
    prompt: { type: 'string', description: 'generate / video 的提示词（英文 Danbooru 风格对 Anima 最有效）。' },
    negative: { type: 'string', description: '负向提示词；缺省用 Anima/Wan 各自调好的默认串。' },
    prompts: {
      type: 'array',
      items: { type: 'string' },
      description: 'batch 模式的多条 prompt。',
    },
    kind: {
      type: 'string',
      enum: ['image', 'video'],
      description: 'generate 的产物类型，默认 image。video 等价于 action=video。',
    },
    width: { type: 'integer', description: '宽：Anima 图 832、Wan 视频 1280。' },
    height: { type: 'integer', description: '高：Anima 图 1216、Wan 视频 704。' },
    steps: { type: 'integer', description: '推理步数：图默认 25（省时可 20-22），视频默认 50。' },
    seed: { type: 'integer', description: '随机种子，固定可复现。' },
    n_per_prompt: { type: 'integer', description: 'batch：每条 prompt 出几张，默认 1。' },
    frames: { type: 'integer', description: 'video：帧数，默认 121（@24fps=5s）；降到 49 省一半时间。' },
    fps: { type: 'integer', description: 'video：帧率，Wan2.2 TI2V-5B 原生 24。' },
    image_path: { type: 'string', description: 'video：I2V 参考图（须是 Colab 端路径，一般由 upload 返回）。' },
    local_file: { type: 'string', description: 'upload：本地图文件路径，推给 Colab 供 I2V 使用。' },
    outdir: { type: 'string', description: `本地图/视频落盘目录，默认 ${DEFAULT_OUTDIR}。` },
    jid: { type: 'string', description: 'status：要查的 job id。' },
    wait: { type: 'boolean', description: 'generate/video 是否阻塞到完成再下载，默认 true。false 只返回 job id。' },
    timeout_sec: { type: 'integer', description: '单个任务最长等待秒数：图默认 600，视频默认 1800（含首次下权重）。' },
  },
  required: ['action'],
}

const OUTPUT_SCHEMA = {
  type: 'object',
  additionalProperties: true,
  properties: {
    ok: { type: 'boolean' },
    action: { type: 'string' },
    url: { type: 'string' },
    message: { type: 'string' },
    health: { type: 'object', additionalProperties: true },
    local_path: { type: 'string' },
    jid: { type: 'string' },
    trail: { type: 'array', items: { type: 'string' } },
    error: { type: 'string' },
  },
  required: ['ok', 'action'],
}

function renderText(value) {
  const lines = []
  // 失败优先：任何 action 的 ok=false 都先吐错误。否则「没连上 / 连不上」会被下面的
  // health 分支误渲染成「CPU 档」、upload 分支误渲染成「已上传: undefined」。
  if (!value.ok) {
    lines.push(`✘ ${value.error || value.job?.error || value.health?.error || value.message || '失败'}`)
    if (Array.isArray(value.trail) && value.trail.length) lines.push(`  轨迹: ${value.trail.join(' → ')}`)
    return [{ type: 'text', text: lines.join('\n') }]
  }
  if (value.action === 'health') {
    const h = value.health || {}
    lines.push(h.gpu ? `档位: GPU  ${h.gpu_name} (${h.vram_gb}GB)` : '档位: CPU 档（无卡，生成不可用，请错峰重试）')
    lines.push(`队列: ${h.pending ?? '?'} 待处理 · 已建任务 ${h.jobs ?? 0} · 视频模型${h.video_loaded ? '已加载' : '未加载（按需下）'}`)
    if (value.url) lines.push(`URL: ${value.url}`)
    if (h.video_error) lines.push(`视频加载错误: ${h.video_error}`)
  } else if (value.local_path) {
    lines.push(`✔ 已下载到本机: ${value.local_path}`)
    if (value.jid) lines.push(`  job ${value.jid}${value.seconds ? ` · ${value.seconds}s` : ''}`)
  } else if (value.action === 'batch') {
    lines.push(value.message || 'batch submitted')
    if (Array.isArray(value.ids)) lines.push(`  共 ${value.ids.length} 个 job：${value.ids.slice(0, 6).map((i) => i.slice(0, 8)).join(', ')}${value.ids.length > 6 ? ' …' : ''}`)
    lines.push('  用 action=status + jid 逐个查，完成后会各自落盘')
  } else if (value.action === 'upload') {
    lines.push(`✔ 已上传，Colab 端路径: ${value.remote_path}`)
    lines.push('  把它填进 video 的 image_path 即可图生视频')
  } else if (value.action === 'flush') {
    lines.push(value.drive ? '✔ 已请求 Colab 端把产出搬进 Drive' : 'Colab 端无 Drive，产出仍在 /content（会话结束清空）')
  } else if (value.jid && !value.local_path) {
    // 非阻塞提交（wait=false）：只拿到 job id，提示后续怎么查。
    lines.push(`✔ 已提交 job ${value.jid}${value.queued != null ? `（队列 ${value.queued}）` : ''}`)
    lines.push('  用 action=status + jid 查进度并落盘')
  } else {
    lines.push(value.message || 'ok')
  }
  if (Array.isArray(value.trail) && value.trail.length) lines.push(`  轨迹: ${value.trail.join(' → ')}`)
  return [{ type: 'text', text: lines.join('\n') }]
}

async function doGenerate(baseUrl, args, signal) {
  const kind = args.kind === 'video' || args.action === 'video' ? 'video' : 'image'
  const isVideo = kind === 'video'
  const payload = {
    kind,
    prompt: args.prompt || '',
    width: args.width || (isVideo ? 1280 : 832),
    height: args.height || (isVideo ? 704 : 1216),
    steps: args.steps || (isVideo ? 50 : 25),
    seed: Number.isFinite(args.seed) ? args.seed : Math.floor(Math.random() * 100000),
  }
  if (args.negative) payload.negative = args.negative
  if (isVideo) {
    payload.frames = args.frames || 121
    payload.fps = args.fps || 24
    if (args.image_path) payload.image_path = args.image_path
  }
  const maxWait = (args.timeout_sec || (isVideo ? 1800 : 600)) * 1000
  const wait = args.wait !== false

  if (!wait) {
    const submit = await httpJson(`${baseUrl}/generate`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(payload),
    }, 60000)
    return { ok: submit.ok, action: kind, jid: submit.data.id, queued: submit.data.queued, error: submit.data.error }
  }

  const r = await runJob(baseUrl, payload, isVideo ? 15000 : 6000, maxWait, signal)
  if (!r.ok) return { ok: false, action: kind, jid: r.jid, error: r.error || r.job?.error || 'failed', trail: r.trail }
  const ext = r.job.ext || (isVideo ? 'mp4' : 'png')
  const bin = await httpBinary(`${baseUrl}/result/${r.jid}`, 300000)
  if (!bin.ok) return { ok: false, action: kind, jid: r.jid, error: bin.error, trail: r.trail }
  const outdir = args.outdir || DEFAULT_OUTDIR
  const local = saveBlob(bin.buf, outdir, r.jid.slice(0, 10), ext)
  return {
    ok: true, action: kind, jid: r.jid, local_path: local,
    bytes: r.job.bytes, seconds: r.job.seconds, trail: r.trail,
    message: `${kind} done in ${r.job.seconds}s → ${local}`,
  }
}

async function run(args, signal) {
  const baseUrl = resolveUrl(args.url)
  if (!baseUrl) {
    return {
      ok: false, action: args.action,
      error: '没有 Colab 隧道地址。跑 notebook 第 4 格拿 URL，' +
        `再 \`echo '<url>' > ${URLFILE}\`，或传参 url=，或设环境变量 COLAB_URL。`,
    }
  }

  switch (args.action) {
    case 'health': {
      const h = await httpJson(`${baseUrl}/health`, {}, 20000)
      return { ok: h.ok, action: 'health', url: baseUrl, health: h.data, error: h.data.error }
    }
    case 'generate':
    case 'video':
    case 'image':
      return doGenerate(baseUrl, { ...args, kind: args.action === 'video' ? 'video' : args.kind }, signal)
    case 'batch': {
      const list = Array.isArray(args.prompts) ? args.prompts : (args.prompt ? [args.prompt] : [])
      if (!list.length) return { ok: false, action: 'batch', error: 'batch 需要 prompts 数组' }
      const body = {
        prompts: list,
        n_per_prompt: args.n_per_prompt || 1,
        kind: args.kind === 'video' ? 'video' : 'image',
        width: args.width || 832,
        height: args.height || 1216,
        steps: args.steps || 25,
        seed: Number.isFinite(args.seed) ? args.seed : 1000,
      }
      if (args.negative) body.negative = args.negative
      const r = await httpJson(`${baseUrl}/batch`, {
        method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body),
      }, 60000)
      return {
        ok: r.ok, action: 'batch', url: baseUrl, ids: r.data.ids,
        message: r.ok ? `已入队 ${r.data.count} 个 job` : undefined, error: r.data.error,
      }
    }
    case 'status': {
      if (!args.jid) return { ok: false, action: 'status', error: 'status 需要 jid' }
      const s = await httpJson(`${baseUrl}/status/${args.jid}`, {}, 20000)
      if (s.data.status === 'done') {
        const ext = s.data.ext || 'png'
        const bin = await httpBinary(`${baseUrl}/result/${args.jid}`, 300000)
        if (bin.ok) {
          const local = saveBlob(bin.buf, args.outdir || DEFAULT_OUTDIR, args.jid.slice(0, 10), ext)
          return { ok: true, action: 'status', jid: args.jid, local_path: local, job: s.data }
        }
      }
      return { ok: s.ok, action: 'status', jid: args.jid, job: s.data, error: s.data.error }
    }
    case 'upload': {
      if (!args.local_file || !existsSync(args.local_file)) {
        return { ok: false, action: 'upload', error: `local_file 不存在: ${args.local_file || '(空)'}` }
      }
      const form = new FormData()
      const buf = readFileSync(args.local_file)
      form.append('file', new Blob([buf]), args.local_file.split('/').pop() || 'ref.png')
      const ctrl = new AbortController()
      const t = setTimeout(() => ctrl.abort(), 180000)
      try {
        const res = await fetch(`${baseUrl}/upload`, { method: 'POST', body: form, signal: ctrl.signal })
        const data = await res.json()
        return { ok: res.ok, action: 'upload', remote_path: data.path, error: data.error }
      } finally { clearTimeout(t) }
    }
    case 'flush': {
      const r = await httpJson(`${baseUrl}/flush`, {}, 180000)
      return { ok: r.ok, action: 'flush', drive: r.data.drive, error: r.data.error }
    }
    default:
      return { ok: false, action: args.action, error: `未知 action: ${args.action}` }
  }
}

export function apply(ctx) {
  ctx.effect(() => ctx.tools.register({
    name: 'colab_gen',
    description:
      '调用远端 Google Colab 免费 T4（examples/anima_colab.ipynb 起的 Flask+cloudflared 隧道）做无审查生图/生视频，' +
      '结果下载回本机。action=health 看当前是 GPU 还是 CPU 档；' +
      'action=generate 出单张（Anima/SDXL，图 832x1216 steps25）；action=batch 批量；' +
      'action=video 走 Wan2.2 TI2V-5B 出 5s 短片（首次触发下载 ~10-20GB 视频权重，之后复用）；' +
      'action=upload 把本地图推上去供图生视频；action=flush 让 Colab 端把产出搬进 Drive；action=status+jid 查任务并落盘。' +
      '无审查：模型权重跑在你租的卡上，没有内容过滤层。' +
      '注意：Colab 免费档会话仅 3.5-6h 且 /content 会话结束清空，产出务必下载或 flush。',
    parameters: PARAMETERS,
    output: { schema: OUTPUT_SCHEMA, render: (_a, v) => renderText(v) },
    // 同一时刻只让一个远端任务在跑：T4 单卡并发会 OOM。
    isConcurrencySafe: () => false,
    timeoutMs: 1900000,
    presentCall: (args) => ({
      card: 'terminal',
      title: `Colab ${args.action || ''}` + (args.prompt ? `: ${String(args.prompt).slice(0, 40)}` : ''),
      description: [args.kind && `kind=${args.kind}`,
        (args.width || args.height) && `${args.width || '?'}x${args.height || '?'}`,
        args.steps && `steps=${args.steps}`, args.frames && `${args.frames}f`]
        .filter(Boolean).join(' · ') || undefined,
    }),
    presentResult: (_a, result) => ({
      card: 'terminal',
      title: result.isError ? 'colab_gen 失败' : 'colab_gen',
      output: String(result.content?.map((b) => b.text ?? '').join('\n') ?? '').slice(0, 4000),
    }),
    async execute(args, exec) {
      return run(args || {}, exec?.signal)
    },
  }))
}
