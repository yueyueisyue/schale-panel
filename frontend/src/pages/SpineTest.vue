<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { Application, Assets, Container, Sprite } from 'pixi.js'
import { Spine } from '@esotericsoftware/spine-pixi-v7'

const host = ref<HTMLDivElement | null>(null)
const status = ref('准备中…')
const anims = ref<string[]>([])
const current = ref('')
const hidCount = ref(0)

let app: Application | null = null
let spine: Spine | null = null

const BASE = '/live2d/mika-official'

// ?v=spr 用标准立绘（1024×2048，Idle + 眨眼）
// ?v=home（默认）用回忆大厅（52 个动画，含 Talk/Pat/Look）
const variant = (new URLSearchParams(location.search).get('v') || 'spr').toLowerCase()
const RES =
  variant === 'sora'
    ? { dir: '/live2d/sora-spr', skel: 'sora_spr.skel', atlas: 'sora_spr.atlas' }
    : variant === 'sorashop'
    ? { dir: '/live2d/sora-shop', skel: 'sora_shop.skel', atlas: 'sora_shop.atlas' }
    : variant === 'home'
    ? { dir: '/live2d/mika-official', skel: 'CH0069_home.skel', atlas: 'CH0069_home.atlas' }
    : { dir: '/live2d/mika-spr', skel: 'CH0069_spr.skel', atlas: 'CH0069_spr.atlas' }

onMounted(async () => {
  if (!host.value) return
  try {
    status.value = '创建渲染器…'
    app = new Application({
      backgroundAlpha: 0,
      antialias: true,
      resolution: Math.min(window.devicePixelRatio || 1, 2),
      autoDensity: true,
      resizeTo: host.value,
    })
    host.value.appendChild(app.view as unknown as HTMLCanvasElement)

    status.value = '加载骨架与图集…'
    Assets.add({ alias: 'mika-skel', src: `${RES.dir}/${RES.skel}` })
    Assets.add({ alias: 'mika-atlas', src: `${RES.dir}/${RES.atlas}` })
    await Assets.load(['mika-skel', 'mika-atlas'])

    status.value = '实例化 Spine…'
    spine = Spine.from({
      skeleton: 'mika-skel',
      atlas: 'mika-atlas',
      scale: 1,
      autoUpdate: true,
    })

    // 动画清单
    const list = spine.skeleton.data.animations.map((a) => a.name)
    anims.value = list
    status.value = `加载成功 · ${list.length} 个动画`

    // 居中 + 自适应
    app.stage.addChild(spine)
    fit()

    const idle = list.find((n) => /^Idle_01$/i.test(n)) || list.find((n) => /idle/i.test(n)) || list[0]
    if (idle) {
      spine.state.setAnimation(0, idle, true)
      current.value = idle
    }

    // 隐藏场景装饰骨骼（床、窗帘等），只留角色
    const HIDE = variant === "home" ? /^(BG_|Dev_|Dummy)/i : /^$/
    const slots = spine.skeleton.slots
    const hidden: string[] = []
    for (const sl of slots) {
      if (HIDE.test(sl.data.name)) {
        sl.setAttachment(null)
        hidden.push(sl.data.name)
      }
    }
    hidCount.value = hidden.length

    const ro = new ResizeObserver(() => fit())
    ro.observe(host.value)
    onUnmounted(() => ro.disconnect())
  } catch (e) {
    status.value = '错误：' + (e as Error).message
    console.error('[spine]', e)
  }
})

function fit() {
  if (!app || !spine) return
  const { width, height } = app.screen
  const b = spine.getLocalBounds()
  const scale = Math.min((width * 0.86) / b.width, (height * 0.92) / b.height)
  spine.scale.set(scale)
  spine.x = width / 2 - (b.x + b.width / 2) * scale
  spine.y = height * 0.94 - (b.y + b.height) * scale
}

function play(name: string, loop = false) {
  if (!spine) return
  spine.state.setAnimation(0, name, loop)
  current.value = name
}

onUnmounted(() => {
  spine?.destroy()
  app?.destroy(true, { children: true })
})

// 供模板使用
defineExpose({ play })
</script>

<template>
  <div class="wrap">
    <div ref="host" class="stage"></div>

    <div class="hud">
      <div class="line"><b>状态</b>{{ status }}</div>
      <div class="line"><b>当前</b>{{ current || '—' }}</div>
      <div class="anims">
        <button
          v-for="a in anims"
          :key="a"
          :class="{ on: a === current }"
          @click="play(a, /idle|start/i.test(a))"
        >{{ a }}</button>
      </div>
    </div>

    <!-- 防止 tree-shake 掉未使用的导入 -->
    <div style="display: none">{{ Container.name }}{{ Sprite.name }}</div>
  </div>
</template>

<style scoped>
.wrap {
  position: fixed;
  inset: 0;
  display: flex;
  background: radial-gradient(120% 80% at 50% 20%, #1a2f52 0%, #0a1526 55%, #050a12 100%);
}
.stage {
  flex: 1;
  min-width: 0;
  position: relative;
}
.hud {
  position: absolute;
  left: 20px;
  top: 20px;
  width: min(420px, 34vw);
  padding: 16px 18px;
  border-radius: 12px;
  background: rgba(8, 20, 38, 0.72);
  border: 1px solid rgba(120, 180, 255, 0.22);
  backdrop-filter: blur(10px);
  color: #cfe4ff;
  font-size: 12.5px;
  line-height: 1.7;
}
.hud .line b {
  display: inline-block;
  width: 44px;
  color: #7fb4f0;
  font-weight: 600;
}
.anims {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
  max-height: 42vh;
  overflow: auto;
}
.anims button {
  padding: 4px 9px;
  font-size: 11.5px;
  color: #bcd8f6;
  background: rgba(40, 80, 140, 0.42);
  border: 1px solid rgba(120, 180, 255, 0.24);
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.16s, color 0.16s;
}
.anims button:hover {
  background: rgba(70, 130, 210, 0.6);
  color: #fff;
}
.anims button.on {
  background: linear-gradient(180deg, #d8ecff, #8dc4ff);
  color: #05213f;
  border-color: transparent;
}
</style>
