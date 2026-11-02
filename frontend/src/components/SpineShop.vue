<script setup lang="ts">
/**
 * 商店页专用立绘：直接用 pixi + spine 渲染，不走 SpineMika。
 * 理由：同一套小空贴图放进 SpineMika 会渲染成半透明，
 * 用这条精简路径（与 SpineTest 一致）可以稳定得到不透明结果。
 */
import { onMounted, onUnmounted, ref } from 'vue'
import { Application, Assets } from 'pixi.js'
import { Spine } from '@esotericsoftware/spine-pixi-v7'

const props = withDefaults(
  defineProps<{
    dir?: string
    skel?: string
    atlas?: string
    zoom?: number
    anchorY?: number
    /** 按高度铺满：人物占满容器高度，底部对齐 */
    fill?: boolean
    /** 垂直微调：正数向下（占容器高度的比例） */
    offsetY?: number
  }>(),
  { dir: '/live2d/sora-spr', skel: 'sora_spr.skel', atlas: 'sora_spr.atlas', zoom: 1, anchorY: 1, fill: true, offsetY: 0 }
)

let baseX = 0
let baseY = 0


const host = ref<HTMLDivElement | null>(null)
const failed = ref('')

let app: Application | null = null
let spine: Spine | null = null
let ro: ResizeObserver | null = null
let anims: string[] = []
let blinkName = ''
let reacting = false

/** 唯一别名，避免多次挂载时 Assets 缓存互相覆盖 */
let key = ''

onMounted(async () => {
  if (!host.value) return
  try {
    app = new Application({
      background: 0x000000,
      backgroundAlpha: 0,
      antialias: false,
      resolution: Math.min(window.devicePixelRatio || 1, 1.5),
      autoDensity: true,
      resizeTo: host.value,
    })
    app.ticker.maxFPS = 30
    document.addEventListener('visibilitychange', onVis)
    host.value.appendChild(app.view as unknown as HTMLCanvasElement)

    key = 'shop' + Math.random().toString(36).slice(2, 8)
    Assets.add({ alias: key + '-skel', src: `${props.dir}/${props.skel}` })
    Assets.add({ alias: key + '-atlas', src: `${props.dir}/${props.atlas}` })
    await Assets.load([key + '-skel', key + '-atlas'])

    spine = Spine.from({
      skeleton: key + '-skel',
      atlas: key + '-atlas',
      scale: 1,
      autoUpdate: true,
    })
    app.stage.addChild(spine)

    const names = spine.skeleton.data.animations.map((a) => a.name)
    const idle = names.find((n) => /^Idle_01$/i.test(n)) || names.find((n) => /idle/i.test(n)) || names[0]
    if (idle) spine.state.setAnimation(0, idle, true)

    anims = names
    const blink = names.find((n) => /Eye_Close/i.test(n))
    blinkName = blink || ''
    // 眨眼：用骨架自带的 Eye_Close_01 播一次再清轨。
    // 直接改槽位挂 Eyecover 会被 Idle_01 覆盖回去，导致眼睛卡在闭眼状态。
    const NOBLINK = new URLSearchParams(location.search).has('noblink')
    const hasClose = names.includes('Eye_Close_01')
    if (!NOBLINK && hasClose) {
      let blinkTimer = 0
      const loop = () => {
        if (!spine) return
        try {
          spine.state.setAnimation(1, 'Eye_Close_01', false)
        } catch {
          /* ignore */
        }
        blinkTimer = window.setTimeout(() => {
          try {
            spine?.state.clearTrack(1)
          } catch {
            /* ignore */
          }
        }, 190)
        window.setTimeout(loop, 6000 + Math.random() * 5000)
      }
      window.setTimeout(loop, 5000 + Math.random() * 4000)
    }

    resetFaceOnLoad()
    const eyeScale = Number(new URLSearchParams(location.search).get('eyefit') || '') || 1
    fitEyes(eyeScale)
    fit()
    ro = new ResizeObserver(() => fit())
    ro.observe(host.value)
  } catch (e) {
    failed.value = (e as Error).message
    console.error('[spine-shop]', e)
  }
})

/** 载入后把脸复位：清掉闭眼/汗滴这类一次性部件，回到待机 */
/** 眼白槽位显式给纯白 + 正常混合，避免被上层贴图吃掉 */

/** 虹膜网格在 4.2 里靠 clipping 约束到眼眶，运行时没实现裁剪，
 *  虹膜会盖住整块眼白。这里把眼睛相关网格按质心等比缩小一点，露出眼白。 */
function fitEyes(factor = 0.82) {
  if (!spine) return
  const re = /^[LR]_(Eye_0\d|Eye_P\w*|Eye_PP)$/
  for (const slot of spine.skeleton.slots) {
    const a: any = slot.getAttachment()
    if (!a || !re.test(a.name || '')) continue
    const verts = a.vertices
    if (!verts || !verts.length) continue
    let cx = 0
    let cy = 0
    const n = verts.length / 2
    for (let i = 0; i < verts.length; i += 2) {
      cx += verts[i]
      cy += verts[i + 1]
    }
    cx /= n
    cy /= n
    for (let i = 0; i < verts.length; i += 2) {
      verts[i] = cx + (verts[i] - cx) * factor
      verts[i + 1] = cy + (verts[i + 1] - cy) * factor
    }
  }
}

function resetFaceOnLoad() {
  if (!spine) return
  for (const n of ['Eyecover_01', 'L_Sweat_01', 'R_Sweat_01']) {
    try {
      const slot = spine.skeleton.findSlot(n)
      if (slot) slot.setAttachment(null)
    } catch {
      /* ignore */
    }
  }
  try {
    spine.state.clearTracks()
    spine.state.setAnimation(0, 'Idle_01', true)
  } catch {
    /* ignore */
  }
}

function fit() {
  if (!app || !spine) return
  const { width, height } = app.screen
  const b = spine.getLocalBounds()
  const base = props.fill
    ? height / b.height
    : Math.min((width * 0.96) / b.width, (height * 0.98) / b.height)
  const s = base * props.zoom
  spine.scale.set(s)
  spine.x = width / 2 - (b.x + b.width / 2) * s
  spine.y = (props.fill ? height - (b.y + b.height) * s : height * props.anchorY - (b.y + b.height) * s) + height * (props.offsetY || 0)
  baseX = spine.x
  baseY = spine.y
}

/** 被点一下时的反应：轻微上弹 + 眨眼 + 歪一下，给点「她注意到你了」的反馈 */
let reactRaf = 0
function react() {
  if (!app || !spine) return
  // 连点也能重新来一遍：以上一次定好的基准位置为准，不读当前（正在动的）坐标
  window.cancelAnimationFrame(reactRaf)
  const s0x = baseX
  const s0y = baseY
  const t0 = performance.now()
  const dur = 620
  const tick = () => {
    if (!spine) return
    const k = Math.min(1, (performance.now() - t0) / dur)
    const bounce = Math.sin(k * Math.PI) * 0.028
    spine.y = s0y - app!.screen.height * bounce
    spine.rotation = Math.sin(k * Math.PI * 2) * 0.012
    spine.x = s0x + Math.sin(k * Math.PI * 2) * 3
    if (k < 1) {
      reactRaf = requestAnimationFrame(tick)
    } else {
      spine.y = s0y
      spine.x = s0x
      spine.rotation = 0
    }
  }
  reactRaf = requestAnimationFrame(tick)
  playOne()
}

/** 表情：直接用骨架自带的编号动画（00~27、99），它们才是作者做的表情。
 *  播完把第 1 轨清掉并复位部件，避免停在半途的姿势。 */
const PART_DEFAULT: Record<string, string | null> = {
  Mouse_01: 'Mouse_01',
  L_eyebrows_01: 'L_eyebrows_01',
  R_eyebrows_01: 'R_eyebrows_01',
  Eyecover_01: null,
  L_Sweat_01: null,
  R_Sweat_01: null,
  L_B_Eyebrows_01: 'L_B_Eyebrows_01',
  R_B_Eyebrows_01: 'R_B_Eyebrows_01',
}

function resetParts() {
  if (!spine) return
  for (const [slot, att] of Object.entries(PART_DEFAULT)) {
    try {
      spine.skeleton.setAttachment(slot, att)
    } catch {
      /* ignore */
    }
  }
}

let talkTimer = 0
let talkStep = 0
let talkSeq: string[] = []

/** 说话：用骨架自带的编号动画当口型，快速轮播，停下来就回待机。
 *  这就是游戏里角色说话时嘴在动的做法。 */
function talk(ms = 2600) {
  if (!spine) return
  if (!talkSeq.length) {
    talkSeq = anims.filter((n) => /^\d+$/.test(n))
  }
  if (!talkSeq.length) return
  stopTalk()
  talkStep = 0
  const tick = () => {
    if (!spine) return
    const name = talkSeq[talkStep % talkSeq.length]
    talkStep += 1
    try {
      spine.state.setAnimation(1, name, false)
    } catch {
      /* ignore */
    }
    talkTimer = window.setTimeout(tick, 150 + Math.random() * 110)
  }
  tick()
  window.setTimeout(stopTalk, ms)
}

function stopTalk() {
  window.clearTimeout(talkTimer)
  try {
    spine?.state.clearTrack(1)
  } catch {
    /* ignore */
  }
  resetParts()
}

/** 点一下：只播一个预设动作（可被打断重播），到点回待机 */
let stopTimer = 0
let lastPick = ''
function playOne(ms = 1300) {
  if (!spine) return
  const pool = anims.filter((n) => /^\d+$/.test(n))
  if (!pool.length) return
  let pick = pool[Math.floor(Math.random() * pool.length)]
  // 连续点的时候不要抽到同一个，否则看起来像没反应
  if (pool.length > 1 && pick === lastPick) pick = pool[(pool.indexOf(pick) + 1) % pool.length]
  lastPick = pick
  window.clearTimeout(stopTimer)
  window.clearTimeout(talkTimer)
  try {
    spine.state.clearTrack(1)
    spine.state.setAnimation(1, pick, false)
  } catch {
    return
  }
  stopTimer = window.setTimeout(() => {
    try {
      spine?.state.clearTrack(1)
    } catch {
      /* ignore */
    }
    resetParts()
  }, ms)
}

/** 点一下：一个动作 + 轻弹 */
function randomExpr() {
  playOne()
}

/** 第 1 轨道放一个「部件/表情」动画，播完淡出，回到待机 */
function playPart(name?: string) {
  if (!spine) return
  const pool = anims.filter((n) => /^\d+$/.test(n))
  const pick = name || (pool.length ? pool[Math.floor(Math.random() * pool.length)] : '')
  if (!pick) return
  const track = spine.state.setAnimation(1, pick, false)
  if (!track) return
  const dur = track.animationEnd - track.animationStart
  spine.state.addEmptyAnimation(1, 0.18, Math.max(0.35, dur * 0.9))
}

defineExpose({ react, playPart, randomExpr, playOne, resetParts, talk, stopTalk })

// 页面不可见时停掉渲染循环，切页/最小化不再吃 GPU
function onVis() {
  if (!app) return
  if (document.hidden) app.ticker.stop()
  else app.ticker.start()
}

onUnmounted(() => {
  document.removeEventListener('visibilitychange', onVis)
  ro?.disconnect()
  spine?.destroy()
  app?.destroy(false, { children: true })
})
</script>

<template>
  <div class="shop-spine">
    <div ref="host" class="host"></div>
    <p v-if="failed" class="err">立绘加载失败：{{ failed }}</p>
  </div>
</template>

<style scoped>
.shop-spine {
  position: relative;
  width: 100%;
  height: 100%;
}
.host {
  width: 100%;
  height: 100%;
}
.err {
  position: absolute;
  left: 50%;
  bottom: 10px;
  transform: translateX(-50%);
  font-size: 12px;
  color: #e8556d;
  background: #fff;
  padding: 3px 10px;
  border-radius: 8px;
}
</style>
