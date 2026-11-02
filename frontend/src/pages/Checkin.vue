<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

const today = new Date()
const YEAR = today.getFullYear()
const MONTH = today.getMonth() // 0-based
const TODAY = today.getDate()

const MONTH_EN = [
  'JANUARY', 'FEBRUARY', 'MARCH', 'APRIL', 'MAY', 'JUNE',
  'JULY', 'AUGUST', 'SEPTEMBER', 'OCTOBER', 'NOVEMBER', 'DECEMBER',
]

const checked = ref(false)
const canLeave = ref(false)

// localStorage key：一天只能签一次
const KEY = `schale_checkin_${YEAR}-${MONTH + 1}-${TODAY}`

onMounted(() => {
  if (localStorage.getItem(KEY)) {
    checked.value = true
    canLeave.value = true
    return
  }
  // 进场动画结束后才允许点
  window.setTimeout(() => (canLeave.value = true), 900)
})

const dow = computed(() => ['Sun.', 'Mon.', 'Tue.', 'Wed.', 'Thu.', 'Fri.', 'Sat.'])

/** 当月格子：前面补空，后面不补 */
const cells = computed(() => {
  const first = new Date(YEAR, MONTH, 1).getDay() // 0=Sun
  const days = new Date(YEAR, MONTH + 1, 0).getDate()
  const out: (number | null)[] = []
  for (let i = 0; i < first; i++) out.push(null)
  for (let d = 1; d <= days; d++) out.push(d)
  return out
})

/** 每格底下的小标记：今天 / 已签到的日子 */
function markOf(d: number | null): string {
  if (d === null) return ''
  if (d === TODAY && checked.value) return 'done'
  if (d === TODAY) return 'today'
  if (d < TODAY) return 'past'
  return ''
}

function cellDow(i: number): number {
  const first = new Date(YEAR, MONTH, 1).getDay()
  return (first + i) % 7
}

function checkin() {
  if (checked.value || !canLeave.value) return
  checked.value = true
  localStorage.setItem(KEY, String(Date.now()))
  window.setTimeout(go, 1400)
}

function go() {
  router.replace('/home')
}
</script>

<template>
  <div class="checkin">
    <div class="bg" aria-hidden="true"></div>
    <div class="veil" aria-hidden="true"></div>

    <header class="top">
      <img src="/img/logo/ba-white.webp" alt="Blue Archive" class="mark" />
      <span class="line" aria-hidden="true"></span>
    </header>

    <!-- 标题 -->
    <div class="title">
      <span class="kicker">SCHALE · DAILY</span>
      <h1>弥香的签到簿</h1>
    </div>

    <!-- 日历纸卡 -->
    <div class="stage">
      <div class="paper">
        <!-- 钉子 -->
        <div class="pin" aria-hidden="true"></div>
        <!-- 竖排英文 -->
        <div class="spine" aria-hidden="true">{{ MONTH_EN[MONTH] }} {{ YEAR }}</div>

        <div class="inner">
          <!-- 月份框 -->
          <div class="mon">
            <span class="num">{{ String(MONTH + 1).padStart(2, '0') }}</span>
            <span class="yr">{{ YEAR }}</span>
          </div>

          <!-- 星期条 -->
          <div class="dows">
            <span
              v-for="(d, i) in dow"
              :key="i"
              class="dow"
              :class="{ sun: i === 0, sat: i === 6 }"
            >{{ d }}</span>
          </div>

          <!-- 日期格 -->
          <div class="grid">
            <div
              v-for="(c, i) in cells"
              :key="i"
              class="cell"
              :class="[markOf(c), { blank: c === null }]"
              :data-w="cellDow(i)"
            >
              <span v-if="c !== null" class="d num">{{ c }}</span>
              <span v-if="markOf(c) === 'done'" class="stamp">完成!</span>
              <span v-else-if="markOf(c) === 'today'" class="dot" aria-hidden="true"></span>
            </div>
          </div>

          <!-- 底部操作条 -->
          <div class="act">
            <button
              v-if="!checked"
              class="btn primary"
              :disabled="!canLeave"
              @click="checkin"
            >签　到</button>
            <button v-else class="btn" @click="go">进入办公室</button>
            <span class="hint">{{ checked ? '今天的签到已完成' : '每天只需要签一次' }}</span>
          </div>
        </div>

        <div class="credit">© SCHALE Panel</div>
      </div>
    </div>

    <!-- 左下角小人 -->
    <div class="mascot">
      <img src="/img/mika-q/mika-q1.webp" alt="弥香" />
      <div class="bubble">
        <span class="who">圣园弥香</span>
        <span class="say">{{ checked ? '签好啦☆ 今天也要一起加油哦' : '老师，先签个到吧' }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.checkin {
  position: fixed;
  inset: 0;
  overflow: hidden;
  background: #0a1a2e;
}

.bg {
  position: absolute;
  inset: 0;
  background: url('/img/scenario/bg_aronaroom.jpg') center / cover no-repeat;
  filter: saturate(1.08) brightness(0.92);
  animation: slow-zoom 24s var(--ease) infinite alternate;
}
@keyframes slow-zoom {
  from { transform: scale(1); }
  to   { transform: scale(1.04); }
}

.veil {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(180deg, rgba(6, 26, 52, 0.52) 0%, rgba(6, 26, 52, 0.10) 26%, rgba(6, 26, 52, 0.16) 62%, rgba(6, 26, 52, 0.58) 100%),
    radial-gradient(120% 90% at 50% 44%, transparent 34%, rgba(4, 18, 38, 0.36) 100%);
}

/* ---- 顶部 ---- */
.top {
  position: absolute;
  top: 30px;
  left: 44px;
  display: flex;
  align-items: center;
  gap: 16px;
  z-index: 3;
}
.mark {
  width: 150px;
  filter: drop-shadow(0 4px 16px rgba(90, 169, 255, 0.5));
}
.line {
  width: 110px;
  height: 1px;
  background: linear-gradient(90deg, rgba(255, 255, 255, 0.5), transparent);
}

/* ---- 标题 ---- */
.title {
  position: absolute;
  top: 84px;
  left: 0;
  right: 0;
  text-align: center;
  z-index: 3;
  animation: fade-up 0.7s 0.1s var(--ease-out) both;
}
.kicker {
  font-size: var(--fs-micro);
  letter-spacing: 0.44em;
  text-indent: 0.44em;
  color: rgba(190, 226, 255, 0.72);
}
.title h1 {
  margin: 8px 0 0;
  font-size: clamp(24px, 2.6vw, 32px);
  font-weight: 800;
  letter-spacing: 0.10em;
  color: #fff;
  text-shadow: 0 3px 22px rgba(0, 30, 70, 0.55);
}

/* ---- 日历纸卡 ---- */
.stage {
  position: absolute;
  inset: 132px 0 180px 0;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2;
}

.paper {
  position: relative;
  width: min(860px, 70vw);
  padding: 30px 34px 20px;
  background: linear-gradient(180deg, #fffdf7 0%, #f6f1e6 100%);
  border-radius: 4px;
  box-shadow:
    0 2px 0 rgba(255, 255, 255, 0.9) inset,
    0 22px 60px rgba(4, 20, 42, 0.46),
    0 4px 12px rgba(4, 20, 42, 0.28);
  animation: fade-up 0.8s 0.2s var(--ease-out) both;
}

/* 钉子 */
.pin {
  position: absolute;
  top: -46px;
  left: 50%;
  width: 2px;
  height: 46px;
  background: linear-gradient(180deg, #8fa4bb, #5d7288);
  transform: translateX(-50%);
}
.pin::after {
  content: '';
  position: absolute;
  bottom: -7px;
  left: 50%;
  width: 14px;
  height: 14px;
  transform: translateX(-50%);
  border-radius: 50%;
  background: radial-gradient(circle at 34% 32%, #cfd9e4, #7e91a6 62%, #5a6d80);
  box-shadow: 0 3px 8px rgba(20, 40, 70, 0.4);
}

/* 竖排英文 */
.spine {
  position: absolute;
  left: -2px;
  top: 50%;
  transform: translateY(-50%) rotate(180deg);
  writing-mode: vertical-rl;
  font-family: var(--font-num);
  font-size: 15px;
  letter-spacing: 0.24em;
  color: #b9aa8c;
}

.inner {
  position: relative;
}

/* 月份框 */
.mon {
  display: inline-flex;
  align-items: baseline;
  gap: 8px;
  padding: 2px 12px 4px;
  margin-bottom: 14px;
  border: 3px solid #1d2634;
  border-radius: 2px;
  background: #fff;
}
.mon .num {
  font-family: var(--font-num);
  font-size: 40px;
  font-weight: 800;
  line-height: 1;
  color: #1d2634;
}
.mon .yr {
  font-family: var(--font-num);
  font-size: 13px;
  color: #6b7686;
  letter-spacing: 0.1em;
}

/* 星期条 */
.dows {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 4px;
  margin-bottom: 6px;
}
.dow {
  height: 26px;
  display: grid;
  place-items: center;
  font-size: 12px;
  letter-spacing: 0.08em;
  color: #fff;
  background: #b8c0cc;
  border-radius: 2px;
}
.dow.sun { background: #e4685f; }
.dow.sat { background: #6a9fd0; }

/* 日期格 */
.grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 4px;
}
.cell {
  position: relative;
  min-height: 62px;
  padding: 6px 8px;
  background: #fff;
  border: 1px solid #eceae2;
  border-radius: 2px;
}
.cell.blank {
  background: transparent;
  border-color: transparent;
}
.cell .d {
  font-size: 13px;
  font-weight: 700;
  color: #3c4859;
}
.cell.past .d { color: #a7b0bb; }
.cell.today {
  border-color: #e4685f;
  box-shadow: 0 0 0 2px rgba(228, 104, 95, 0.16) inset;
}
.cell.today .d { color: #d9534a; }
.cell.today .dot {
  position: absolute;
  right: 7px;
  bottom: 7px;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #e4685f;
  animation: pulse-soft 1.8s var(--ease) infinite;
}
.cell.done {
  border-color: #c9d8b6;
  background: #fffdf3;
}
.cell .stamp {
  position: absolute;
  right: 4px;
  bottom: 4px;
  font-size: 10px;
  font-weight: 800;
  color: #c8483f;
  border: 1.5px solid #c8483f;
  border-radius: 2px;
  padding: 0 3px;
  transform: rotate(-8deg);
  opacity: 0.85;
}

.credit {
  margin-top: 14px;
  font-size: 10px;
  letter-spacing: 0.12em;
  color: #b3a993;
  text-align: center;
}

/* ---- 小人 ---- */
.mascot {
  position: absolute;
  left: 3vw;
  bottom: 4vh;
  display: flex;
  align-items: flex-end;
  gap: 14px;
  z-index: 4;
  animation: fade-up 0.9s 0.45s var(--ease-out) both;
}
.mascot img {
  width: clamp(120px, 13vw, 190px);
  filter: drop-shadow(0 10px 26px rgba(6, 24, 48, 0.5));
  animation: bob 4.2s var(--ease) infinite;
}
@keyframes bob {
  0%, 100% { transform: translateY(0); }
  50%      { transform: translateY(-7px); }
}
.bubble {
  display: flex;
  flex-direction: column;
  gap: 3px;
  margin-bottom: 26px;
  padding: 10px 16px;
  background: rgba(255, 255, 255, 0.94);
  border-radius: 12px 12px 12px 2px;
  box-shadow: 0 10px 26px rgba(6, 24, 48, 0.34);
}
.bubble .who {
  font-size: 11px;
  letter-spacing: 0.1em;
  color: var(--ba-600, #2a63b0);
  font-weight: 700;
}
.bubble .say {
  font-size: 13.5px;
  color: #2b3644;
}

/* ---- 底部操作条（在纸卡内部） ---- */
.act {
  margin-top: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
}
.btn {
  min-width: 180px;
  height: 44px;
  padding: 0 30px;
  border: 2px solid #c9d3df;
  border-radius: var(--r-sm);
  background: #fff;
  color: #35506e;
  font-family: var(--font-ui);
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 0.14em;
  cursor: pointer;
  transition: all var(--t-fast) var(--ease);
  clip-path: polygon(0 0, calc(100% - 12px) 0, 100% 12px, 100% 100%, 0 100%);
}
.btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(40, 80, 130, 0.18);
}
.btn.primary {
  background: linear-gradient(180deg, #4d92dd, #2f6fbb);
  color: #fff;
  border-color: transparent;
  box-shadow: 0 8px 22px rgba(47, 111, 187, 0.36);
}
.btn:disabled {
  opacity: 0.5;
  cursor: default;
}
.hint {
  font-size: 11.5px;
  color: #9aa4b1;
  letter-spacing: 0.04em;
}

@media (max-width: 900px) {
  .paper {
    width: 88vw;
    padding: 22px 18px 18px;
  }
  .cell { min-height: 46px; }
  .mascot { left: 2vw; bottom: 2vh; }
  .mascot img { width: 100px; }
  .bubble { display: none; }
  .act { right: 3vw; bottom: 2vh; }
  .btn { min-width: 140px; height: 44px; font-size: 14px; }
  .top { left: 20px; top: 18px; }
  .mark { width: 110px; }
  .line { display: none; }
}
</style>
