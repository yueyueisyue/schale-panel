<script setup lang="ts">
/**
 * 弥香官方 Spine 立绘（从国服 APK 的 Addressables bundle 提取）
 * 资源：CH0069_spr.skel / .atlas / .png（Spine 4.2.33，1024×2048）
 *
 * 能力：
 *   - 常驻待机呼吸（Idle_01）
 *   - 定时随机眨眼（Eye_Close_01）
 *   - 说话时切到 Talk 动作（若有）
 *   - 鼠标移动时头部轻微跟随（靠容器位移模拟，不改骨骼）
 */
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { Application, Assets } from 'pixi.js'
import { Spine } from '@esotericsoftware/spine-pixi-v7'

const emit = defineEmits<{
  (e: 'bounds', box: { left: number; top: number; right: number; bottom: number }): void
}>()
const props = withDefaults(
  defineProps<{
    /** 说话中：切到 Talk 动作（spr 没有 Talk，会退回眨眼+点头） */
    talking?: boolean
    /** 缩放微调，1 = 自适应铺满容器 */
    zoom?: number
    /** 垂直锚点：0 = 底边贴容器底，1 = 顶边贴容器顶 */
    anchorY?: number
    /** 立绘版本：spr = 标准立绘（常服），home = 回忆大厅（躺床） */
    variant?: 'spr' | 'home' | 'sora' | 'soraShop' | 'swim'
  }>(),
  { talking: false, zoom: 1, anchorY: 0.96, variant: 'spr' }
)

const host = ref<HTMLDivElement | null>(null)
const ready = ref(false)
const failed = ref('')

let app: Application | null = null
let spine: Spine | null = null
let blinkTimer = 0
let idleName = 'Idle_01'
let blinkName = 'Eye_Close_01'
let talkName = ''

/** 两套官方 Spine 资源 */
const VARIANTS = {
  spr: {
    dir: '/live2d/mika-spr',
    skel: 'CH0069_spr.skel',
    atlas: 'CH0069_spr.atlas',
    anchorY: 0.94,
    zoom: 1.0,
  },
  sora: {
    dir: '/live2d/sora-spr',
    skel: 'sora_spr.skel',
    atlas: 'sora_spr.atlas',
    anchorY: 0.98,
    zoom: 1.0,
  },
  soraShop: {
    dir: '/live2d/sora-shop',
    skel: 'sora_shop.skel',
    atlas: 'sora_shop.atlas',
    anchorY: 1.0,
    zoom: 1.0,
    fillHeight: true,
  },
  swim: {
    dir: '/live2d/mika-swim',
    skel: 'CH0294_home.skel',
    atlas: 'CH0294_home.atlas',
    anchorY: 0.5,
    zoom: 1.12,
    fillHeight: true,
    offsetY: 0.0,
  },
  home: {
    dir: '/live2d/mika-official',
    skel: 'CH0069_home.skel',
    atlas: 'CH0069_home.atlas',
    anchorY: 0.5,
    zoom: 1.12,
    fillHeight: true,
    offsetY: 0.0,
  },
} as const
const cfg = () => VARIANTS[props.variant] ?? VARIANTS.spr

function fit() {
  if (!app || !spine) return
  const { width, height } = app.screen
  const b = spine.getLocalBounds()
  if (b.width <= 0 || b.height <= 0) return
  const c = cfg() as { cover?: boolean; fillHeight?: boolean; zoom: number; offsetY?: number }
  // 整场景（回忆大厅 / 泳装）用 cover：取宽高比大的一边，四边不留黑，多余处自然裁掉
  const base = c.fillHeight
    ? Math.max(width / b.width, height / b.height)
    : Math.min((width * 0.94) / b.width, (height * 0.98) / b.height)
  const s = base * props.zoom * c.zoom * (c.fillHeight ? 1.0 : 1)
  spine.scale.set(s)
  spine.x = width / 2 - (b.x + b.width / 2) * s
  // offsetY 正值 = 整体下移；cover 模式下以画面中心为基准
  const dy = height * (c.offsetY || 0)
  spine.y = c.fillHeight
    ? height / 2 - (b.y + b.height / 2) * s + dy
    : height * props.anchorY - (b.y + b.height) * s + dy

  const px = (v: number) => Math.round(v)
  emit('bounds', {
    left: px(spine.x + b.x * s),
    top: px(spine.y + b.y * s),
    right: px(spine.x + (b.x + b.width) * s),
    bottom: px(spine.y + (b.y + b.height) * s),
  })
}

function idle() {
  if (!spine) return
  spine.state.setAnimation(0, idleName, true)
}

function blink() {
  if (!spine || !blinkName) return
  // 用第 1 轨道叠加眨眼，不打断待机
  spine.state.setAnimation(1, blinkName, false)
  spine.state.addEmptyAnimation(1, 0.12, 0)
}

async function boot() {
  if (!host.value) return
  try {
    app = new Application({
      backgroundAlpha: 0,
      antialias: false,
      resolution: Math.min(window.devicePixelRatio || 1, 1.5),
      autoDensity: true,
      resizeTo: host.value,
    })
    app.ticker.maxFPS = 30
    document.addEventListener('visibilitychange', onVis)
    host.value.appendChild(app.view as unknown as HTMLCanvasElement)

    const store = (window as any).__spineAssets ??= new Map<string, boolean>()
    const alias = 'mika-' + Date.now().toString(36)
    const v = cfg()
    await Assets.load([
      { alias: `${alias}-skel`, src: `${v.dir}/${v.skel}` },
      { alias: `${alias}-atlas`, src: `${v.dir}/${v.atlas}` },
    ])
    store.set(alias, true)

    // 切变体会重挂组件，旧实例可能已在加载途中被销毁
    if (!app || !app.stage) return
    spine = Spine.from({
      skeleton: `${alias}-skel`,
      atlas: `${alias}-atlas`,
      autoUpdate: true,
    })
    app.stage.addChild(spine)

    // 回忆大厅那套骨架里带整间房的场景装饰（床、窗帘、窗框…），
    // 当立绘用时把场景部件摘掉，只留角色本身
    if (props.variant === 'home' && false) {
      // 回忆大厅那套骨架里带整间宿舍（墙、窗、床、桌、窗帘、月光），
      // 当立绘用时只保留角色本体
      const scenery =
        /^(BG_|BG$|Window|radiator|Table|Mood|mood|L_Curtain|R_Curtain|Char_BG)/i
      for (const slot of spine.skeleton.slots) {
        if (scenery.test(slot.data.name)) slot.setAttachment(null)
      }
    }

    if (typeof location !== 'undefined' && new URLSearchParams(location.search).has('slots')) {
      const list = spine.skeleton.slots.map((sl: any) => `${sl.data.name}|${sl.getAttachment()?.name ?? '-'}`)
      const pre = document.createElement('pre')
      pre.id = 'spine-slots'
      pre.style.cssText = 'position:fixed;left:0;top:0;z-index:9999;max-height:100vh;overflow:auto;font-size:10px;background:#000c;color:#0f0;padding:6px;margin:0'
      pre.textContent = list.join('\n')
      document.body.appendChild(pre)
    }

    const names = spine.skeleton.data.animations.map((a) => a.name)
    idleName = names.find((n) => /^Idle_01$/i.test(n)) || names[0] || ''
    blinkName = names.find((n) => /Eye_Close/i.test(n)) || ''
    talkName = names.find((n) => /^Talk_/i.test(n)) || ''

    if (idleName) idle()
    fit()
    ready.value = true

    // 随机眨眼：3~7 秒一次
    const schedule = () => {
      blinkTimer = window.setTimeout(() => {
        blink()
        schedule()
      }, 3000 + Math.random() * 4000)
    }
    schedule()

    const ro = new ResizeObserver(() => fit())
    ro.observe(host.value)
    onUnmounted(() => ro.disconnect())
  } catch (e) {
    failed.value = (e as Error).message + ' @ ' + (e as Error).stack?.split('\n')[1]
    console.error('[SpineMika]', e)
  }
}

watch(
  () => props.talking,
  (on) => {
    if (!spine) return
    if (on && talkName) spine.state.setAnimation(0, talkName, true)
    else if (!on && idleName) idle()
  }
)

watch(
  () => [props.zoom, props.anchorY],
  () => fit()
)


/** 点一下：只播一个预设动作（可被打断重播），到点回待机 */
let stopTimer = 0
let lastPick = ''
function playOne(ms = 1300) {
  if (!spine) return
  const pool = (spine.skeleton.data.animations || [])
    .map((a) => a.name)
    .filter((n: string) => /^\d+$/.test(n))
  if (!pool.length) return
  let pick = pool[Math.floor(Math.random() * pool.length)]
  if (pool.length > 1 && pick === lastPick) pick = pool[(pool.indexOf(pick) + 1) % pool.length]
  lastPick = pick
  window.clearTimeout(stopTimer)
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
  }, ms)
}

onMounted(boot)
defineExpose({ playOne })
// 页面不可见时停掉渲染循环，切页/最小化不再吃 GPU
function onVis() {
  if (!app) return
  if (document.hidden) app.ticker.stop()
  else app.ticker.start()
}

onUnmounted(() => {
  document.removeEventListener('visibilitychange', onVis)
  window.clearTimeout(blinkTimer)
  spine?.destroy()
  app?.destroy(false, { children: true })
})
</script>

<template>
  <div class="mika-wrap" :class="{ ready }">
    <div ref="host" class="mika"></div>
    <p v-if="failed" class="err">立绘加载失败：{{ failed }}</p>
  </div>
</template>

<style scoped>
.mika-wrap {
  position: relative;
  width: 100%;
  height: 100%;
  opacity: 1;
}
.mika {
  width: 100%;
  height: 100%;
}
.err {
  position: absolute;
  left: 50%;
  bottom: 12px;
  transform: translateX(-50%);
  font-size: 12px;
  color: #ff9fb0;
}
</style>
