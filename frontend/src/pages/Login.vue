<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

const videoEl = ref<HTMLVideoElement | null>(null)

// 开屏加载动画：先进场，再露出登录界面
const loading = ref(true)
const loaderOut = ref(false)

function finishLoading() {
  if (loaderOut.value) return
  loaderOut.value = true
  window.setTimeout(() => (loading.value = false), 560)
}

onMounted(() => {
  // 视频能播了就提前结束，最多等 2.4 秒
  const v = videoEl.value
  const t = window.setTimeout(finishLoading, 2400)
  if (v) {
    const done = () => {
      window.clearTimeout(t)
      finishLoading()
    }
    if (v.readyState >= 3) done()
    else v.addEventListener('canplay', done, { once: true })
  }
})

const pwd = ref('')
const busy = ref(false)
const err = ref('')
const shake = ref(false)
const muted = ref(true)

function toggleSound() {
  const v = videoEl.value
  if (!v) return
  muted.value = !muted.value
  v.muted = muted.value
}

async function submit() {
  if (busy.value) return
  err.value = ''
  const v = pwd.value.trim()
  if (!v) {
    err.value = '请输入访问密码'
    shake.value = true
    window.setTimeout(() => (shake.value = false), 420)
    return
  }
  busy.value = true
  try {
    const r = await fetch('/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password: v }),
    })
    const d = await r.json().catch(() => ({}))
    if (r.ok && d?.token) {
      localStorage.setItem('schale_token', d.token)
      router.replace('/home')
      return
    }
    err.value = d?.error || d?.message || '密码不对'
    shake.value = true
    window.setTimeout(() => (shake.value = false), 420)
  } catch {
    err.value = '连不上本地服务（BFF 未启动？）'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="login">
    <!-- 开屏加载动画层 -->
    <div v-if="loading" class="loader" :class="{ out: loaderOut }">
      <div class="l-stars" aria-hidden="true"></div>
      <div class="l-wrap">
        <img class="l-logo" src="/img/logo/ba-white.webp" alt="Blue Archive" />
        <span class="l-sweep" aria-hidden="true"></span>
      </div>
      <div class="l-bar"><i></i></div>
      <div class="l-foot">
        <span class="l-tag">SCHALE</span>
        <span class="l-ver num">v0.1.0</span>
      </div>
    </div>

    <!-- 游戏原版开屏动画，循环播放，就是这个界面的背景 -->
    <video
      ref="videoEl"
      class="bgv"
      src="/video/title-full.mp4"
      autoplay
      loop
      muted
      playsinline
      preload="auto"
    ></video>

    <!-- 压层：左下重、右上轻 -->
    <div class="veil" aria-hidden="true"></div>
    <div class="vignette" aria-hidden="true"></div>
    <div class="grain" aria-hidden="true"></div>

    <!-- 顶部 logo + 声音开关 -->
    <header class="top">
      <img src="/img/logo/ba-white.webp" alt="Blue Archive" class="mark" />
      <span class="line" aria-hidden="true"></span>
      <button class="sound" type="button" :title="muted ? '开启声音' : '静音'" @click.stop="toggleSound">
        <span v-if="muted">🔇</span>
        <span v-else>🔊</span>
      </button>
    </header>

    <!-- 登录卡 -->
    <main class="panel" :class="{ shake }">
      <div class="hello">
        <span class="kicker">SCHALE</span>
        <h1>老师，回来了</h1>
        <p class="sub">输入访问密码，办公室的门就开着</p>
      </div>

      <div class="field">
        <input
          v-model="pwd"
          type="password"
          class="input"
          placeholder="访问密码"
          autocomplete="current-password"
          @keydown.enter="submit"
        />
        <button class="go" :disabled="busy" @click="submit">
          <span>{{ busy ? '连接中…' : '进入办公室' }}</span>
        </button>
      </div>

      <p v-if="err" class="err">{{ err }}</p>
    </main>

    <footer class="bot">
      <span>@NEXON Games &amp; Yostar</span>
      <span class="dot">·</span>
      <span>Schale Panel</span>
    </footer>
  </div>
</template>

<style scoped>
.login {
  position: fixed;
  inset: 0;
  overflow: hidden;
  background: #06101f;
}

/* ---- 开屏加载动画层 ---- */
.loader {
  position: absolute;
  inset: 0;
  z-index: 20;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 26px;
  background: radial-gradient(120% 80% at 50% 42%, #123057 0%, #081a30 45%, #03080f 100%);
  opacity: 1;
  transition: opacity 0.55s var(--ease);
}
.loader.out {
  opacity: 0;
  pointer-events: none;
}

.l-stars {
  position: absolute;
  inset: 0;
  background-image:
    radial-gradient(1.6px 1.6px at 18% 26%, rgba(190, 226, 255, 0.85), transparent),
    radial-gradient(1.4px 1.4px at 72% 18%, rgba(190, 226, 255, 0.65), transparent),
    radial-gradient(1.8px 1.8px at 40% 72%, rgba(210, 235, 255, 0.75), transparent),
    radial-gradient(1.2px 1.2px at 84% 64%, rgba(190, 226, 255, 0.55), transparent),
    radial-gradient(1.5px 1.5px at 26% 84%, rgba(210, 235, 255, 0.60), transparent),
    radial-gradient(1.3px 1.3px at 62% 40%, rgba(190, 226, 255, 0.50), transparent);
  animation: pulse-soft 3.6s var(--ease) infinite;
}

.l-wrap {
  position: relative;
  width: clamp(220px, 26vw, 380px);
  animation: logo-in 1.05s var(--ease-out) both;
}
.l-logo {
  display: block;
  width: 100%;
  height: auto;
  filter: brightness(0) invert(1) drop-shadow(0 6px 34px rgba(96, 178, 255, 0.45));
}
.l-sweep {
  position: absolute;
  inset: 0;
  background: linear-gradient(105deg, transparent 38%, rgba(255, 255, 255, 0.85) 50%, transparent 62%);
  mix-blend-mode: screen;
  animation: sweep 1.15s 0.35s var(--ease) both;
}

.l-bar {
  width: clamp(140px, 18vw, 240px);
  height: 2px;
  border-radius: 2px;
  background: rgba(150, 200, 255, 0.16);
  overflow: hidden;
}
.l-bar i {
  display: block;
  width: 100%;
  height: 100%;
  transform-origin: left center;
  background: linear-gradient(90deg, #5aa9ff, #bde3ff);
  animation: fill 2s var(--ease) both;
}

.l-foot {
  position: absolute;
  bottom: 34px;
  left: 0;
  right: 0;
  display: flex;
  justify-content: center;
  gap: 14px;
  font-size: 11px;
  letter-spacing: 0.28em;
  color: rgba(180, 210, 240, 0.42);
}
.l-foot .l-ver {
  letter-spacing: 0.06em;
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
@keyframes sweep {
  0% { transform: translateX(-120%); opacity: 0; }
  20% { opacity: 1; }
  100% { transform: translateX(120%); opacity: 0; }
}
@keyframes fill {
  from { transform: scaleX(0); }
  to { transform: scaleX(1); }
}

/* ---- 背景视频 ---- */
.bgv {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: center 46%;
  filter: saturate(1.06) contrast(1.04);
}

/* ---- 压层 ---- */
.veil {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(112deg, rgba(5, 14, 28, 0.88) 0%, rgba(6, 20, 38, 0.68) 34%, rgba(6, 20, 38, 0.18) 62%, rgba(6, 20, 38, 0.50) 100%),
    linear-gradient(0deg, rgba(3, 8, 16, 0.84) 0%, transparent 46%);
}
.vignette {
  position: absolute;
  inset: 0;
  background: radial-gradient(120% 92% at 50% 46%, transparent 32%, rgba(2, 8, 18, 0.58) 100%);
  pointer-events: none;
}
.grain {
  position: absolute;
  inset: 0;
  opacity: 0.20;
  background-image: repeating-linear-gradient(0deg, rgba(255, 255, 255, 0.05) 0 1px, transparent 1px 3px);
  mix-blend-mode: overlay;
  pointer-events: none;
}

/* ---- 顶部 ---- */
.top {
  position: absolute;
  top: 34px;
  left: 46px;
  right: 46px;
  display: flex;
  align-items: center;
  gap: 18px;
  z-index: 4;
}
.mark {
  width: 168px;
  filter: drop-shadow(0 4px 18px rgba(90, 169, 255, 0.5));
}
.line {
  width: 120px;
  height: 1px;
  background: linear-gradient(90deg, rgba(255, 255, 255, 0.55), transparent);
}
.sound {
  margin-left: auto;
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

/* ---- 登录卡 ---- */
.panel {
  position: absolute;
  left: 8.5vw;
  top: 50%;
  transform: translateY(-50%);
  width: min(380px, 40vw);
  display: flex;
  flex-direction: column;
  gap: 22px;
  animation: fade-up 0.7s 0.15s var(--ease-out) both;
}
.panel.shake {
  animation: shake 0.42s var(--ease);
}

.kicker {
  display: inline-block;
  font-size: 11px;
  letter-spacing: 0.38em;
  color: rgba(150, 205, 255, 0.82);
  padding-left: 2px;
}
.hello h1 {
  margin: 10px 0 8px;
  font-size: clamp(26px, 3vw, 34px);
  font-weight: 800;
  letter-spacing: 0.02em;
  color: #fff;
  text-shadow: 0 2px 24px rgba(0, 20, 50, 0.6);
}
.sub {
  margin: 0;
  font-size: 13px;
  color: rgba(198, 222, 248, 0.72);
}

/* ---- 输入 ---- */
.field {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.input {
  width: 100%;
  height: 46px;
  padding: 0 16px;
  font-family: var(--font-ui);
  font-size: 14px;
  color: #fff;
  background: rgba(255, 255, 255, 0.10);
  border: 1px solid rgba(255, 255, 255, 0.22);
  border-radius: var(--r-sm);
  backdrop-filter: blur(10px);
  outline: none;
  transition: border-color var(--t-fast), background var(--t-fast);
}
.input::placeholder {
  color: rgba(210, 230, 250, 0.45);
}
.input:focus {
  border-color: rgba(140, 200, 255, 0.78);
  background: rgba(255, 255, 255, 0.15);
}

.go {
  position: relative;
  width: 100%;
  height: 46px;
  border: 0;
  cursor: pointer;
  border-radius: var(--r-sm);
  font-family: var(--font-ui);
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: #05213f;
  background: linear-gradient(180deg, #d8ecff 0%, #8dc4ff 100%);
  box-shadow: 0 8px 26px rgba(90, 160, 255, 0.38);
  transition: transform var(--t-fast) var(--ease), box-shadow var(--t-fast);
  clip-path: polygon(0 0, calc(100% - 12px) 0, 100% 12px, 100% 100%, 0 100%);
}
.go:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 12px 32px rgba(90, 160, 255, 0.52);
}
.go:active:not(:disabled) {
  transform: translateY(0);
}
.go:disabled {
  opacity: 0.62;
  cursor: default;
}

.err {
  margin: -6px 0 0;
  font-size: 12.5px;
  color: #ff9fb0;
}

/* ---- 底部 ---- */
.bot {
  position: absolute;
  bottom: 26px;
  left: 0;
  right: 0;
  display: flex;
  justify-content: center;
  gap: 8px;
  font-size: 11px;
  letter-spacing: 0.06em;
  color: rgba(190, 215, 240, 0.42);
}
.bot .dot {
  opacity: 0.5;
}

@keyframes shake {
  0%, 100% { transform: translateY(-50%) translateX(0); }
  22%      { transform: translateY(-50%) translateX(-7px); }
  55%      { transform: translateY(-50%) translateX(6px); }
  80%      { transform: translateY(-50%) translateX(-3px); }
}

@media (max-width: 860px) {
  .panel {
    left: 6vw;
    width: min(360px, 78vw);
  }
  .mark {
    width: 130px;
  }
  .top {
    left: 24px;
    right: 24px;
    top: 22px;
  }
  .line {
    display: none;
  }
}
</style>
