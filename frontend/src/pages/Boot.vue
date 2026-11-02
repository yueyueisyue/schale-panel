<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const leaving = ref(false)
const muted = ref(true)
const videoEl = ref<HTMLVideoElement | null>(null)

function toggleSound() {
  const v = videoEl.value
  if (!v) return
  muted.value = !muted.value
  v.muted = muted.value
}

function enter() {
  if (leaving.value) return
  leaving.value = true
  // 给淡出一点时间，再进登录
  window.setTimeout(() => router.replace('/login'), 520)
}

// 任何一次点击/按键都算"想进去"
function onAnyKey(e: KeyboardEvent) {
  if (e.key === 'Enter' || e.key === ' ') enter()
}

onMounted(() => {
  window.addEventListener('keydown', onAnyKey)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onAnyKey)
})
</script>

<template>
  <div class="cover" :class="{ leaving }">
    <!-- 游戏原版开屏动画，循环播放 -->
    <video
      ref="videoEl"
      class="video"
      src="/video/title-full.mp4"
      autoplay
      loop
      muted
      playsinline
      preload="auto"
    ></video>

    <!-- 压暗 + 暗角，保证文字可读 -->
    <div class="veil" aria-hidden="true"></div>
    <div class="vignette" aria-hidden="true"></div>

    <!-- 右上角声音开关 -->
    <button class="sound" type="button" :title="muted ? '开启声音' : '静音'" @click.stop="toggleSound">
      <span v-if="muted">🔇</span>
      <span v-else>🔊</span>
    </button>

    <!-- 主视觉：logo + 进入 -->
    <div class="stage">
      <img class="logo" src="/img/logo/ba-white.webp" alt="Blue Archive" />
      <p class="kicker">SCHALE · 老师办公室</p>

      <button class="enter" type="button" @click.stop="enter">
        <span class="label">点击进入</span>
        <span class="hint">按 Enter 也可以</span>
      </button>
    </div>

    <div class="foot">
      <span class="tag">SCHALE PANEL</span>
      <span class="ver num">v0.1.0</span>
    </div>
  </div>
</template>

<style scoped>
.cover {
  position: fixed;
  inset: 0;
  overflow: hidden;
  background: #03080f;
  opacity: 1;
  transition: opacity 0.5s var(--ease);
  cursor: pointer;
}
.cover.leaving {
  opacity: 0;
}

/* ---- 视频层 ---- */
.video {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  /* 视频源是 13:6 超宽，小屏靠裁切保住中间城市 */
  object-position: center 46%;
  filter: saturate(1.06) contrast(1.04);
}

/* ---- 压暗层 ---- */
.veil {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(180deg, rgba(3, 10, 22, 0.55) 0%, rgba(3, 10, 22, 0.10) 22%, rgba(3, 10, 22, 0.28) 62%, rgba(3, 10, 22, 0.86) 100%),
    linear-gradient(90deg, rgba(3, 12, 26, 0.52) 0%, rgba(3, 12, 26, 0.10) 34%, transparent 60%);
}
.vignette {
  position: absolute;
  inset: 0;
  background: radial-gradient(120% 90% at 50% 46%, transparent 34%, rgba(2, 8, 18, 0.62) 100%);
  pointer-events: none;
}

/* ---- 声音开关 ---- */
.sound {
  position: absolute;
  top: 22px;
  right: 24px;
  z-index: 5;
  width: 42px;
  height: 42px;
  display: grid;
  place-items: center;
  font-size: 17px;
  color: #eaf4ff;
  background: rgba(8, 24, 46, 0.42);
  border: 1px solid rgba(160, 205, 255, 0.28);
  border-radius: var(--r-pill);
  backdrop-filter: blur(8px);
  cursor: pointer;
  transition: background var(--t-fast) var(--ease), transform var(--t-fast) var(--ease);
}
.sound:hover {
  background: rgba(20, 52, 92, 0.62);
  transform: scale(1.06);
}

/* ---- 主视觉 ---- */
.stage {
  position: absolute;
  inset: 0;
  z-index: 4;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 18px;
  padding-bottom: 6vh;
  pointer-events: none;
}
.stage > * {
  pointer-events: auto;
}

.logo {
  width: clamp(240px, 30vw, 460px);
  height: auto;
  filter: brightness(0) invert(1) drop-shadow(0 8px 40px rgba(90, 165, 255, 0.55));
  animation: logo-in 1.2s var(--ease-out) both;
}
@keyframes logo-in {
  from {
    opacity: 0;
    transform: scale(0.92) translateY(10px);
  }
  to {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}

.kicker {
  margin: 0;
  font-size: var(--fs-sec);
  letter-spacing: 0.42em;
  text-indent: 0.42em;
  color: rgba(226, 240, 255, 0.72);
  animation: fade-in 1s 0.35s var(--ease) both;
}

/* ---- 进入按钮 ---- */
.enter {
  margin-top: 26px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 14px 44px;
  color: #0d325c;
  background: linear-gradient(135deg, #eaf6ff 0%, #b6dcff 100%);
  border: none;
  border-radius: var(--r-sm);
  clip-path: polygon(0 0, calc(100% - 12px) 0, 100% 12px, 100% 100%, 0 100%);
  box-shadow: 0 10px 30px rgba(30, 90, 160, 0.40);
  cursor: pointer;
  animation: fade-in 0.9s 0.6s var(--ease) both, pulse-soft 3.2s 1.6s var(--ease) infinite;
  transition: transform var(--t-fast) var(--ease), box-shadow var(--t-fast) var(--ease);
}
.enter:hover {
  transform: translateY(-2px);
  box-shadow: 0 14px 38px rgba(60, 130, 210, 0.55);
}
.enter:active {
  transform: translateY(0);
}
.enter .label {
  font-size: var(--fs-title);
  font-weight: 700;
  letter-spacing: 0.16em;
  text-indent: 0.16em;
}
.enter .hint {
  font-size: var(--fs-micro);
  color: rgba(18, 58, 104, 0.62);
  letter-spacing: 0.08em;
}

/* ---- 页脚 ---- */
.foot {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 22px;
  z-index: 4;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 14px;
  font-size: var(--fs-micro);
  color: rgba(200, 222, 245, 0.50);
  letter-spacing: 0.22em;
  pointer-events: none;
}
.foot .ver {
  letter-spacing: 0.06em;
}

@media (max-width: 720px) {
  .stage {
    padding-bottom: 10vh;
  }
  .enter {
    padding: 12px 32px;
  }
}
</style>
