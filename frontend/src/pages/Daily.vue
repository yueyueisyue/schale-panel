<script setup lang="ts">
/**
 * 日程：Location Select。
 * 左边是阿罗娜（待机呼吸、点一下播一个预设动作），右边是地区列表，
 * 点某个地区进去看这一区的具体日程（来自 /api/daily 的时间轴）。
 */
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import SpineShop from '@/components/SpineShop.vue'

const router = useRouter()
const TOKEN_KEY = 'schale_token'
const arona = ref<any>(null)

interface Item {
  time: string
  end: string
  activity: string
  mood: string[]
  basis: string[]
  seed: string
}
interface Day {
  planDate: string
  items: Item[]
  state: any
  dream: any
  diary: any
  history: { day: string; count: number }[]
}

const data = ref<Day | null>(null)
const loading = ref(true)
const openId = ref<string | null>(new URLSearchParams(location.search).get('open'))

/** 地区：名字 + 一张俯瞰图 + 评级。日程按时间段切分到各区，读起来像是她今天跑过的地方。 */
const REGIONS = [
  { id: 'schale-biz', name: '夏莱业务区', rate: 12, map: 'schale', desc: '老师办公室所在，白天基本都在这儿。' },
  { id: 'schale-life', name: '夏莱生活区', rate: 12, map: 'schale', desc: '吃饭、休息、发呆的地方。' },
  { id: 'gehenna', name: '格赫娜学院', rate: 12, map: 'gehenna', desc: '风纪委员会管不到的那半边。' },
  { id: 'abydos', name: '阿比多斯高中', rate: 12, map: 'abydos', desc: '沙漠边上的学校，对策委员会常驻。' },
  { id: 'millennium', name: '千年科学学院', rate: 12, map: 'millennium', desc: '研讨会与游戏开发部的地盘。' },
  { id: 'trinity', name: '圣三一综合学院', rate: 12, map: 'trinity', desc: '大圣堂与茶会的所在。' },
  { id: 'shanhaijing', name: '山海经高级中学', rate: 1, map: 'shanhaijing', desc: '红灯笼、茶楼与梅花。' },
  { id: 'hyakki', name: '百鬼夜行联合学院', rate: 12, map: 'hyakki', desc: '樱花与祭典。' },
  { id: 'redwinter', name: '赤冬联邦学院', rate: 12, map: 'redwinter', desc: '风雪里的旧校区。' },
  { id: 'wildhunt', name: '狂烈艺术学院', rate: 12, map: 'wildhunt', desc: '画室与剧场。' },
  { id: 'federal', name: '联邦学生会', rate: 12, map: 'federal', desc: '基沃托斯的行政中枢。' },
]

const totalRate = computed(() => REGIONS.reduce((s, r) => s + r.rate, 0))

/** 把今天的时间轴按顺序摊到各区，形成「这一区今天发生了什么」 */
const regionItems = computed<Record<string, Item[]>>(() => {
  const map: Record<string, Item[]> = {}
  const items = data.value?.items || []
  REGIONS.forEach((r, i) => {
    map[r.id] = items.filter((_, idx) => idx % REGIONS.length === i)
  })
  return map
})

const opened = computed(() => REGIONS.find((r) => r.id === openId.value) || null)

function authHeaders() {
  const t = localStorage.getItem(TOKEN_KEY)
  return t ? { Authorization: 'Bearer ' + t } : {}
}

async function ensureToken() {
  if (localStorage.getItem(TOKEN_KEY)) return
  const r = await fetch('/api/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password: 'CHANGE_ME' }),
  })
  const j = await r.json()
  if (j?.token) localStorage.setItem(TOKEN_KEY, j.token)
}

async function load() {
  await ensureToken()
  try {
    const r = await fetch('/api/daily', { headers: authHeaders() as any })
    const j = await r.json()
    if (j?.ok) data.value = j
  } finally {
    loading.value = false
  }
}

function poke() {
  arona.value?.react?.()
}

onMounted(load)
onUnmounted(() => {
  /* 无定时器 */
})
</script>

<template>
  <div class="daily">
    <div class="bg"></div>
    <div class="veil"></div>

    <header class="top">
      <button class="back" @click="router.push('/home')">
        <svg viewBox="0 0 24 24"><path d="M14.5 5.5 8 12l6.5 6.5" /></svg>
      </button>
      <h1>日程</h1>
      <span class="ticket">🎫 持有券 <b>7 / 7</b></span>
      <span class="exp">经验值 <b>关闭</b></span>
      <span class="date">{{ data?.planDate || '—' }}</span>
    </header>

    <section class="stage" @click="poke">
      <div class="arona-glow"></div>
      <SpineShop
        ref="arona"
        dir="/live2d/arona-spr"
        skel="arona_spr.skel"
        atlas="arona_spr.atlas"
        :zoom="0.74"
        :anchor-y="1.0"
        fill
        :offset-y="0.02"
        title="点一下换动作"
      />
      <p class="hint">点一下换一个动作</p>
    </section>

    <main class="panel">
      <div class="head">
        <div class="kicker">
          <span class="en">Location Select</span>
          <span class="cn">区域评级总和</span>
          <span class="rate">评级 {{ totalRate }}</span>
        </div>
        <button class="info" @click="openId = null">ⓘ 票券信息</button>
      </div>

      <ul class="list">
        <li v-for="r in REGIONS" :key="r.id" class="row" :class="{ on: openId === r.id }" @click="openId = r.id">
          <span class="badge">评级{{ r.rate }}</span>
          <span class="name">{{ r.name }}</span>
          <div class="thumb" :style="{ backgroundImage: `url(/img/map/${r.map}-thumb.webp)` }"></div>
          <div class="reward">
            <span>奖励</span>
            <i>🎫</i>
          </div>
        </li>
      </ul>
    </main>

    <!-- 地区详情：整屏学院地图 -->
    <transition name="pop">
      <div v-if="opened" class="detail">
        <div class="mapview" :style="{ backgroundImage: `url(/img/map/${opened.map}.webp)` }"></div>
        <div class="mapveil"></div>

        <span class="tickets"><i>🎟</i> 持有券 <b>7/7</b></span>

        <aside class="mvinfo">
          <header>
            <span class="badge">评级{{ opened.rate }}</span>
            <h2>{{ opened.name }}</h2>
          </header>
          <div class="line"><i :style="{ width: Math.min(100, opened.rate * 8) + '%' }"></i></div>
          <p class="desc">{{ opened.desc }} · 今天 {{ (regionItems[opened.id] || []).length }} 段日程</p>
          <ul class="tl">
            <li v-for="(it, i) in regionItems[opened.id] || []" :key="i">
              <span class="t">{{ it.time }}</span>
              <div>
                <p>{{ it.activity }}</p>
                <span class="chips"><b v-for="m in it.mood.slice(0, 3)" :key="m">{{ m }}</b></span>
              </div>
            </li>
            <li v-if="!(regionItems[opened.id] || []).length" class="empty">这一区今天没安排。</li>
          </ul>
        </aside>

        <button class="allplan" @click="openId = null">
          <b>全部日程</b>
          <i>{{ REGIONS.length }}</i>
        </button>
        <button class="x" @click="openId = null">✕</button>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.daily {
  position: fixed;
  inset: 0;
  overflow: hidden;
  font-family: var(--font-ui, system-ui, sans-serif);
  color: #223046;
  background: #cfe4f6;
}
.bg {
  position: absolute;
  inset: 0;
  background: url('/img/sky/sky-day.webp') center 42% / cover no-repeat;
  filter: saturate(1.04) brightness(1.02);
}
.veil {
  position: absolute;
  inset: 0;
  background: linear-gradient(120deg, rgba(226, 242, 255, 0.94) 0%, rgba(214, 235, 253, 0.86) 42%, rgba(198, 226, 248, 0.62) 100%);
}

.top {
  position: relative;
  z-index: 4;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px 26px 0;
}
.back {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  border: none;
  background: #fff;
  box-shadow: 0 4px 14px rgba(24, 60, 100, 0.18);
  display: grid;
  place-items: center;
  cursor: pointer;
}
.back svg {
  width: 22px;
  height: 22px;
  fill: none;
  stroke: #3d5b7d;
  stroke-width: 2.2;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.top h1 {
  margin: 0;
  font-size: 26px;
  font-weight: 900;
}
.ticket,
.exp {
  padding: 5px 14px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.9);
  font-size: 12.5px;
  font-weight: 700;
  color: #43607f;
  box-shadow: inset 0 0 0 1px rgba(186, 214, 238, 0.9);
}
.ticket b,
.exp b {
  color: #2f79c8;
}
.date {
  margin-left: auto;
  font-size: 12.5px;
  font-weight: 800;
  color: #6d8299;
}

.arona-glow {
  position: absolute;
  inset: 8% 12% 6%;
  z-index: 0;
  border-radius: 50%;
  background: radial-gradient(
    closest-side,
    rgba(120, 176, 226, 0.6) 0%,
    rgba(120, 176, 226, 0.26) 58%,
    rgba(120, 176, 226, 0) 100%
  );
  pointer-events: none;
}
.stage > :not(.arona-glow) { position: relative; z-index: 1; }
.stage {
  position: absolute;
  left: 0;
  top: 72px;
  bottom: 0;
  width: 46%;
  z-index: 2;
  cursor: pointer;
}
.hint {
  position: absolute;
  left: 22px;
  bottom: 12px;
  margin: 0;
  font-size: 11.5px;
  color: rgba(70, 100, 135, 0.6);
}

.panel {
  position: absolute;
  right: 30px;
  top: 92px;
  bottom: 22px;
  width: min(760px, 48%);
  z-index: 3;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.head {
  display: flex;
  align-items: flex-end;
  gap: 14px;
  padding: 6px 10px 2px;
}
.kicker {
  display: flex;
  align-items: baseline;
  gap: 10px;
  flex-wrap: wrap;
}
.en {
  font-size: 30px;
  font-weight: 900;
  font-style: italic;
  letter-spacing: 0.01em;
  color: #2f6fb0;
  text-shadow: 0 2px 0 rgba(255, 255, 255, 0.75);
}
.cn {
  font-size: 12.5px;
  font-weight: 800;
  color: #5d7c9c;
}
.rate {
  font-size: 12.5px;
  font-weight: 900;
  color: #2f79c8;
}
.info {
  margin-left: auto;
  height: 34px;
  padding: 0 14px;
  border: none;
  border-radius: 9px;
  background: rgba(255, 255, 255, 0.92);
  font-size: 12.5px;
  font-weight: 800;
  color: #3f648c;
  cursor: pointer;
  box-shadow: 0 3px 10px rgba(30, 70, 110, 0.14);
}

.list {
  list-style: none;
  margin: 0;
  padding: 0 6px 6px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 9px;
}
.row {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  height: 92px;
  padding-left: 12px;
  border-radius: 12px;
  background: linear-gradient(100deg, rgba(255, 255, 255, 0.96) 0%, rgba(240, 249, 255, 0.9) 46%, rgba(226, 242, 254, 0.86) 100%);
  box-shadow: 0 6px 18px rgba(28, 66, 106, 0.12), inset 0 0 0 1px rgba(255, 255, 255, 0.8);
  cursor: pointer;
  overflow: hidden;
  transition: transform 0.14s ease, box-shadow 0.14s ease;
}
.row:hover {
  transform: translateX(-3px);
  box-shadow: 0 10px 24px rgba(28, 66, 106, 0.2), inset 0 0 0 1px rgba(255, 255, 255, 0.9);
}
.row.on {
  box-shadow: 0 10px 24px rgba(28, 66, 106, 0.22), inset 0 0 0 2px #4f9bea;
}
.badge {
  flex: none;
  padding: 4px 9px;
  border-radius: 6px;
  background: #26456b;
  color: #fff;
  font-size: 12.5px;
  font-weight: 900;
}
.name {
  flex: none;
  font-size: 19px;
  font-weight: 900;
  color: #26456b;
  min-width: 190px;
}
.thumb {
  flex: 1;
  height: 92px;
  background-size: cover;
  background-position: center 60%;
  -webkit-mask-image: linear-gradient(90deg, transparent 0%, #000 22%, #000 84%, transparent 100%);
  mask-image: linear-gradient(90deg, transparent 0%, #000 22%, #000 84%, transparent 100%);
  opacity: 0.95;
}
.reward {
  flex: none;
  width: 92px;
  align-self: stretch;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  background: rgba(255, 255, 255, 0.66);
  border-left: 1px solid rgba(196, 220, 240, 0.9);
}
.reward span {
  font-size: 12px;
  font-weight: 900;
  color: #3f648c;
}
.reward i {
  font-size: 22px;
  font-style: normal;
}

.detail {
  position: absolute;
  inset: 0;
  z-index: 20;
}
.sheet {
  width: min(680px, 82vw);
  max-height: 78vh;
  overflow-y: auto;
  padding: 20px 22px 22px;
  border-radius: 16px;
  background: #fff;
  box-shadow: 0 18px 50px rgba(6, 20, 40, 0.32);
}
.sheet header {
  display: flex;
  align-items: center;
  gap: 10px;
}
.sheet h2 {
  margin: 0;
  font-size: 21px;
  font-weight: 900;
  color: #26456b;
}
.x {
  margin-left: auto;
  width: 30px;
  height: 30px;
  border: none;
  border-radius: 50%;
  background: #eff6fd;
  color: #5c7896;
  font-size: 15px;
  cursor: pointer;
}
.desc {
  margin: 10px 0 8px;
  font-size: 13px;
  color: #5c7896;
}
.line {
  height: 9px;
  border-radius: 999px;
  background: #eaf2fa;
  overflow: hidden;
}
.line i {
  display: block;
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #ffd05e, #f6b93b);
}
.sub {
  margin: 14px 0 8px;
  font-size: 12.5px;
  font-weight: 800;
  color: #3f648c;
}
.tl {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 9px;
}
.tl li {
  display: flex;
  gap: 12px;
  padding: 9px 12px;
  border-radius: 10px;
  background: #f5faff;
}
.tl .t {
  flex: none;
  width: 52px;
  font-size: 12px;
  font-weight: 900;
  color: #3f8fd6;
}
.tl p {
  margin: 0;
  font-size: 13px;
  line-height: 1.55;
  color: #33455c;
}
.chips {
  display: inline-flex;
  gap: 5px;
  margin-top: 5px;
}
.chips b {
  padding: 1px 8px;
  border-radius: 999px;
  background: #e6f1fb;
  color: #4a7ba8;
  font-size: 11px;
  font-weight: 800;
}
.empty {
  color: #8ea3b8;
  font-size: 12.5px;
  justify-content: center;
}
.pop-enter-active,
.pop-leave-active {
  transition: opacity 0.18s ease;
}
.pop-enter-from,
.pop-leave-to {
  opacity: 0;
}

.detail {
  position: absolute;
  inset: 0;
  z-index: 9;
}
.mapview {
  position: absolute;
  inset: 0;
  background-size: cover;
  background-position: center 42%;
  transform: scale(1.02);
}
.mapveil {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(120% 90% at 50% 20%, transparent 40%, rgba(12, 34, 60, 0.22) 100%),
    linear-gradient(180deg, rgba(12, 34, 60, 0.16) 0%, transparent 24%);
  pointer-events: none;
}
.tickets {
  position: absolute;
  left: 26px;
  top: 22px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 7px 16px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.9);
  box-shadow: 0 6px 18px rgba(20, 60, 100, 0.18);
  font-size: 13.5px;
  font-weight: 700;
  color: #2f6fa8;
}
.tickets b {
  color: #1f4a78;
  font-size: 15px;
}
.mvinfo {
  position: absolute;
  right: 26px;
  top: 22px;
  width: min(420px, 34vw);
  max-height: calc(100% - 130px);
  overflow-y: auto;
  padding: 16px 18px 18px;
  border-radius: 14px;
  background: rgba(247, 252, 255, 0.94);
  border: 1px solid rgba(150, 196, 232, 0.7);
  box-shadow: 0 16px 40px rgba(10, 34, 60, 0.26);
  backdrop-filter: blur(6px);
}
.mvinfo header {
  display: flex;
  align-items: center;
  gap: 10px;
}
.mvinfo header h2 {
  margin: 0;
  font-size: 19px;
  font-weight: 800;
  color: #1f4a78;
}
.mvinfo .badge {
  padding: 3px 10px;
  border-radius: 7px;
  background: #1f4a78;
  color: #fff;
  font-size: 12.5px;
  font-weight: 700;
}
.mvinfo .line {
  margin: 10px 0 8px;
  height: 9px;
  border-radius: 5px;
  background: #e2eefa;
  overflow: hidden;
}
.mvinfo .line i {
  display: block;
  height: 100%;
  border-radius: 5px;
  background: linear-gradient(90deg, #ffd166, #f2a53a);
}
.mvinfo .desc {
  margin: 0 0 10px;
  font-size: 12.5px;
  color: #5b7794;
  line-height: 1.6;
}
.mvinfo .tl {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.mvinfo .tl li {
  display: flex;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 9px;
  background: #fff;
  box-shadow: 0 2px 8px rgba(30, 70, 110, 0.08);
}
.mvinfo .tl .t {
  flex: none;
  font-size: 12px;
  font-weight: 700;
  color: #4f86b8;
  padding-top: 2px;
}
.mvinfo .tl p {
  margin: 0 0 5px;
  font-size: 12.5px;
  line-height: 1.55;
  color: #2f4a66;
}
.mvinfo .chips b {
  display: inline-block;
  margin-right: 4px;
  padding: 1px 7px;
  border-radius: 999px;
  background: #eaf4fd;
  color: #4f86b8;
  font-size: 11px;
  font-weight: 600;
}
.mvinfo .empty {
  font-size: 12.5px;
  color: #7d93aa;
}
.allplan {
  position: absolute;
  right: 26px;
  bottom: 22px;
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 12px 26px;
  border: 0;
  border-radius: 12px;
  background: linear-gradient(180deg, #7fc6f2, #4aa3e0);
  color: #fff;
  font-size: 15px;
  font-weight: 800;
  cursor: pointer;
  box-shadow: 0 10px 24px rgba(24, 96, 160, 0.34);
}
.allplan i {
  font-style: normal;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.35);
  font-size: 12px;
  line-height: 22px;
  text-align: center;
}
.detail .x {
  position: absolute;
  left: 26px;
  bottom: 22px;
  width: 44px;
  height: 44px;
  border: 0;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.9);
  color: #33587e;
  font-size: 16px;
  cursor: pointer;
  box-shadow: 0 8px 20px rgba(20, 60, 100, 0.2);
}
</style>
