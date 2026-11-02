<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

interface Emo { [k: string]: number }
interface Guest {
  id: string; name: string; favor: number; intimacy: number
  total: number; positive: number; negative: number; streak: number
  lastDay: string; attitude: string; relationship: string; emotions: Emo
}
interface Booth {
  id: string; name: string; count: number; recent: number
  lastText: string; lastWho: string; lastAgo: string
  interject: number; enabled: boolean
}
interface Mood {
  emotions: Emo; dominant: string; label: string; score: number
  attitude: string; relationship: string; favor: number; intimacy: number
}

const mood = ref<Mood | null>(null)
const guests = ref<Guest[]>([])
const booths = ref<Booth[]>([])
const loading = ref(true)
const tab = ref<'booths' | 'guests'>('booths')

const EMO = [
  { key: 'joy', label: '开心', color: '#f5b942' },
  { key: 'trust', label: '信任', color: '#46c08a' },
  { key: 'anticipation', label: '期待', color: '#4f9bea' },
  { key: 'surprise', label: '意外', color: '#b57ce6' },
  { key: 'fear', label: '不安', color: '#8a94a6' },
  { key: 'sadness', label: '低落', color: '#6a8fc4' },
  { key: 'anger', label: '生气', color: '#e8556d' },
  { key: 'disgust', label: '反感', color: '#a2705a' },
]

const emoBars = computed(() =>
  EMO.map((e) => ({ ...e, v: Math.max(0, Math.min(100, Number(mood.value?.emotions?.[e.key] ?? 0))) }))
)

const dominantColor = computed(() => {
  const d = mood.value?.dominant || ''
  return EMO.find((e) => e.key === d)?.color || '#4f9bea'
})

async function apiGet<T = any>(path: string): Promise<T | null> {
  const tk = localStorage.getItem('schale_token')
  if (!tk) return null
  try {
    const r = await fetch(path, { headers: { Authorization: `Bearer ${tk}` } })
    if (!r.ok) return null
    return (await r.json()) as T
  } catch {
    return null
  }
}

async function ensureToken() {
  if (localStorage.getItem('schale_token')) return
  try {
    const r = await fetch('/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password: 'CHANGE_ME' }),
    })
    if (r.ok) {
      const j = await r.json()
      if (j?.token) localStorage.setItem('schale_token', j.token)
    }
  } catch { /* ignore */ }
}

async function load() {
  await ensureToken()
  const d = await apiGet<any>('/api/cafe')
  if (d) {
    mood.value = d.mood || null
    guests.value = d.guests || []
    booths.value = d.booths || []
  }
  loading.value = false
}

function back() {
  router.replace('/home')
}

let timer = 0
onMounted(() => {
  load()
  timer = window.setInterval(load, 60000)
})
onUnmounted(() => window.clearInterval(timer))
</script>

<template>
  <div class="cafe">
    <div class="bg" aria-hidden="true"></div>
    <div class="tint" aria-hidden="true"></div>

    <!-- 顶栏 -->
    <header class="top">
      <button class="back" @click="back">← 办公室</button>
      <div class="title">
        <span class="kicker">SCHALE · CAFETERIA</span>
        <h1>咖啡馆</h1>
      </div>
      <div class="status" :style="{ '--c': dominantColor }">
        <i class="dot"></i>
        <span>{{ loading ? '正在打烊…' : '营业中' }}</span>
      </div>
    </header>

    <div class="wrap">
      <!-- 左：她此刻的心情 -->
      <aside class="mood-card">
        <h2>她此刻</h2>

        <div class="mood-head" :style="{ '--c': dominantColor }">
          <div class="face">{{ mood?.label || '—' }}</div>
          <div class="score">
            <b class="num">{{ mood?.score ?? 0 }}</b>
            <span>%</span>
          </div>
        </div>

        <ul class="emos">
          <li v-for="e in emoBars" :key="e.key">
            <span class="ename">{{ e.label }}</span>
            <div class="ebar">
              <i :style="{ width: e.v + '%', background: e.color }"></i>
            </div>
            <span class="eval num">{{ e.v }}</span>
          </li>
        </ul>

        <div class="bond">
          <div class="brow">
            <span>好感</span>
            <div class="bbar"><i :style="{ width: (mood?.favor ?? 0) + '%' }"></i></div>
            <b class="num">{{ mood?.favor ?? 0 }}</b>
          </div>
          <div class="brow">
            <span>亲密</span>
            <div class="bbar pink"><i :style="{ width: (mood?.intimacy ?? 0) + '%' }"></i></div>
            <b class="num">{{ mood?.intimacy ?? 0 }}</b>
          </div>
        </div>

        <div class="quote" v-if="mood?.attitude">
          <span class="who">她现在的样子</span>
          <p>{{ mood.attitude }}</p>
        </div>
        <div class="quote" v-if="mood?.relationship">
          <span class="who">你们的关系</span>
          <p>{{ mood.relationship }}</p>
        </div>
      </aside>

      <!-- 右：卡座 / 常客 -->
      <main class="main">
        <div class="tabs">
          <button :class="{ on: tab === 'booths' }" @click="tab = 'booths'">
            🪑 卡座 <b class="num">{{ booths.length }}</b>
          </button>
          <button :class="{ on: tab === 'guests' }" @click="tab = 'guests'">
            👥 常客 <b class="num">{{ guests.length }}</b>
          </button>
        </div>

        <!-- 卡座 -->
        <div v-if="tab === 'booths'" class="list">
          <article v-for="b in booths" :key="b.id" class="booth">
            <div class="b-head">
              <span class="b-name">{{ b.name }}</span>
              <span class="b-count num">{{ b.count }} 条</span>
              <span v-if="b.interject" class="b-chip">今天插话 {{ b.interject }}</span>
            </div>
            <p class="b-last">
              <span class="b-who">{{ b.lastWho || '—' }}</span>
              <span class="b-text">{{ b.lastText || '（还没有消息）' }}</span>
            </p>
            <div class="b-foot">
              <span class="b-ago">{{ b.lastAgo }}</span>
              <span class="b-dots" aria-hidden="true">
                <i v-for="n in Math.min(5, Math.max(1, Math.round(b.recent / 3)))" :key="n"></i>
              </span>
            </div>
          </article>
          <p v-if="!booths.length && !loading" class="empty">咖啡馆里还没有客人。</p>
        </div>

        <!-- 常客 -->
        <div v-else class="list">
          <article v-for="g in guests" :key="g.id" class="guest">
            <div class="g-avatar">{{ (g.name || '?').slice(0, 1) }}</div>
            <div class="g-main">
              <div class="g-head">
                <span class="g-name">{{ g.name }}</span>
                <span class="g-chip">好感 {{ g.favor }}</span>
                <span class="g-chip pink">亲密 {{ g.intimacy }}</span>
                <span v-if="g.streak > 1" class="g-chip warn">连续 {{ g.streak }} 天</span>
              </div>
              <p class="g-att" v-if="g.attitude">{{ g.attitude }}</p>
              <p class="g-rel" v-if="g.relationship">{{ g.relationship }}</p>
              <div class="g-foot">
                <span class="num">聊过 {{ g.total }} 次</span>
                <span class="num ok">正 {{ g.positive }}</span>
                <span class="num bad" v-if="g.negative">负 {{ g.negative }}</span>
                <span v-if="g.lastDay">{{ g.lastDay }}</span>
              </div>
            </div>
          </article>
          <p v-if="!guests.length && !loading" class="empty">还没有人坐下来聊过。</p>
        </div>
      </main>
    </div>
  </div>
</template>

<style scoped>
.cafe {
  position: fixed;
  inset: 0;
  overflow: hidden;
  color: #fff;
}

.bg {
  position: absolute;
  inset: 0;
  background: url('/img/bg-cafe.webp') center / cover no-repeat;
  transform: scale(1.06);
  filter: saturate(1.10) brightness(0.86) contrast(1.04);
}
.tint {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(180deg, rgba(24, 12, 8, 0.60) 0%, rgba(24, 12, 8, 0.14) 20%, rgba(24, 12, 8, 0.12) 62%, rgba(20, 10, 6, 0.56) 100%),
    radial-gradient(120% 92% at 50% 44%, transparent 34%, rgba(16, 8, 4, 0.32) 100%);
}

/* 顶栏 */
.top {
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 76px;
  padding: 0 24px;
  display: flex;
  align-items: center;
  gap: 18px;
  background: linear-gradient(180deg, rgba(28, 14, 8, 0.82), rgba(28, 14, 8, 0.18));
  backdrop-filter: blur(10px);
  border-bottom: 1px solid rgba(255, 226, 190, 0.14);
  z-index: 6;
}
.back {
  padding: 7px 14px;
  border: 1px solid rgba(255, 226, 190, 0.28);
  border-radius: var(--r-sm);
  background: rgba(60, 30, 16, 0.5);
  color: #ffe9cc;
  font-size: 12.5px;
  cursor: pointer;
  transition: background var(--t-fast);
}
.back:hover { background: rgba(120, 60, 30, 0.7); }

.title { display: flex; flex-direction: column; gap: 1px; }
.title .kicker {
  font-size: 9.5px;
  letter-spacing: 0.34em;
  color: rgba(255, 224, 190, 0.55);
}
.title h1 {
  margin: 0;
  font-size: 19px;
  font-weight: 800;
  letter-spacing: 0.08em;
  color: #fff4e4;
}

.status {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 6px 14px;
  border-radius: var(--r-pill);
  background: rgba(60, 30, 16, 0.5);
  border: 1px solid rgba(255, 226, 190, 0.22);
  font-size: 12px;
  color: #ffe9cc;
}
.status .dot {
  width: 7px; height: 7px;
  border-radius: 50%;
  background: var(--c);
  box-shadow: 0 0 8px var(--c);
  animation: pulse-soft 2.4s infinite;
}

/* 布局 */
.wrap {
  position: absolute;
  top: 76px; left: 0; right: 0; bottom: 0;
  padding: 20px 24px 24px;
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 18px;
  align-items: start;
  z-index: 3;
}

/* 心情卡 */
.mood-card {
  padding: 18px 18px 16px;
  background: rgba(255, 250, 242, 0.94);
  border-radius: var(--r-card);
  box-shadow: var(--sh-pop);
  color: var(--ink);
  overflow-y: auto;
  clip-path: polygon(0 0, calc(100% - 16px) 0, 100% 16px, 100% 100%, 0 100%);
}
.mood-card h2 {
  margin: 0 0 14px;
  font-size: 13.5px;
  font-weight: 800;
  letter-spacing: 0.14em;
  color: var(--ink-2);
}

.mood-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  padding: 10px 14px;
  margin-bottom: 14px;
  border-radius: var(--r-sm);
  background: linear-gradient(135deg, color-mix(in srgb, var(--c) 16%, #fff), #fff);
  border-left: 3px solid var(--c);
}
.mood-head .face {
  font-size: 21px;
  font-weight: 800;
  color: var(--c);
  letter-spacing: 0.06em;
}
.mood-head .score b { font-size: 22px; color: var(--ink); }
.mood-head .score span { font-size: 12px; color: var(--ink-3); }

.emos {
  list-style: none;
  margin: 0 0 14px;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 7px;
}
.emos li {
  display: grid;
  grid-template-columns: 34px 1fr 26px;
  align-items: center;
  gap: 8px;
}
.ename { font-size: 11.5px; color: var(--ink-2); }
.ebar {
  height: 6px;
  border-radius: 3px;
  background: rgba(38, 48, 63, 0.10);
  overflow: hidden;
}
.ebar i {
  display: block;
  height: 100%;
  border-radius: 3px;
  transition: width var(--t-slow) var(--ease-out);
}
.eval { font-size: 11px; color: var(--ink-3); text-align: right; }

.bond {
  padding-top: 12px;
  margin-bottom: 12px;
  border-top: 1px dashed rgba(38, 48, 63, 0.12);
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.brow {
  display: grid;
  grid-template-columns: 30px 1fr 30px;
  align-items: center;
  gap: 8px;
  font-size: 11.5px;
  color: var(--ink-2);
}
.bbar {
  height: 7px;
  border-radius: 4px;
  background: rgba(38, 48, 63, 0.10);
  overflow: hidden;
}
.bbar i {
  display: block;
  height: 100%;
  background: linear-gradient(90deg, #7fc4ff, #4f9bea);
  transition: width var(--t-slow) var(--ease-out);
}
.bbar.pink i { background: linear-gradient(90deg, #ffb8d0, #e8556d); }
.brow b { font-size: 11.5px; color: var(--ink); text-align: right; }

.quote {
  margin-top: 10px;
  padding: 9px 12px;
  border-radius: var(--r-sm);
  background: rgba(255, 244, 228, 0.85);
  border-left: 3px solid #f0b46a;
}
.quote .who {
  display: block;
  font-size: 10px;
  letter-spacing: 0.08em;
  color: #b8813f;
  margin-bottom: 3px;
}
.quote p {
  margin: 0;
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--ink);
}

/* 主区 */
.main {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-height: 0;
}
.tabs {
  display: flex;
  gap: 10px;
  flex: none;
}
.tabs button {
  padding: 9px 20px;
  border: 1px solid rgba(255, 226, 190, 0.22);
  border-radius: var(--r-sm);
  background: rgba(60, 30, 16, 0.46);
  color: rgba(255, 232, 204, 0.72);
  font-size: 13px;
  cursor: pointer;
  transition: all var(--t-fast);
}
.tabs button b { margin-left: 5px; font-size: 12px; opacity: 0.7; }
.tabs button.on {
  background: rgba(255, 250, 242, 0.94);
  color: #4a2a14;
  border-color: transparent;
  box-shadow: var(--sh-card);
}

.list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  align-content: start;
  padding-right: 4px;
}

/* 卡座 */
.booth {
  padding: 14px 16px 12px;
  background: rgba(255, 250, 242, 0.94);
  border-radius: var(--r-card);
  box-shadow: var(--sh-card);
  color: var(--ink);
  clip-path: polygon(0 0, calc(100% - 14px) 0, 100% 14px, 100% 100%, 0 100%);
}
.b-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.b-name {
  font-size: 14.5px;
  font-weight: 800;
  color: var(--ink);
}
.b-count {
  font-size: 11.5px;
  color: var(--ink-3);
}
.b-chip {
  margin-left: auto;
  padding: 2px 8px;
  border-radius: var(--r-pill);
  font-size: 10px;
  color: #b8813f;
  background: #fff4e4;
}
.b-last {
  margin: 0 0 9px;
  font-size: 12.5px;
  line-height: 1.55;
  display: flex;
  gap: 6px;
}
.b-who {
  flex: none;
  color: #2a63b0;
  font-weight: 600;
}
.b-text {
  color: var(--ink-2);
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.b-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.b-ago { font-size: 10.5px; color: var(--ink-3); }
.b-dots { display: flex; gap: 3px; }
.b-dots i {
  width: 5px; height: 5px;
  border-radius: 50%;
  background: #d9c3a8;
}

/* 常客 */
.guest {
  display: flex;
  gap: 12px;
  padding: 14px 16px;
  background: rgba(255, 250, 242, 0.94);
  border-radius: var(--r-card);
  box-shadow: var(--sh-card);
  color: var(--ink);
  clip-path: polygon(0 0, calc(100% - 14px) 0, 100% 14px, 100% 100%, 0 100%);
}
.g-avatar {
  flex: none;
  width: 38px; height: 38px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  font-size: 15px;
  font-weight: 800;
  color: #fff;
  background: linear-gradient(135deg, #7fb3ea, #3d7dd6);
}
.g-main { flex: 1; min-width: 0; }
.g-head {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 5px;
}
.g-name { font-size: 14px; font-weight: 800; }
.g-chip {
  padding: 1px 7px;
  border-radius: var(--r-pill);
  font-size: 10px;
  color: #2a63b0;
  background: #eaf3ff;
}
.g-chip.pink { color: #b8385c; background: #ffeef3; }
.g-chip.warn { color: #b8813f; background: #fff4e4; }
.g-att {
  margin: 0 0 2px;
  font-size: 12px;
  color: var(--ink);
  line-height: 1.55;
}
.g-rel {
  margin: 0 0 6px;
  font-size: 11.5px;
  color: var(--ink-3);
  line-height: 1.5;
}
.g-foot {
  display: flex;
  gap: 10px;
  font-size: 10.5px;
  color: var(--ink-3);
}
.g-foot .ok { color: #46c08a; }
.g-foot .bad { color: #e8556d; }

.empty {
  grid-column: 1 / -1;
  text-align: center;
  padding: 40px 0;
  font-size: 13px;
  color: rgba(255, 232, 204, 0.55);
}

@media (max-width: 1100px) {
  .wrap { grid-template-columns: 260px 1fr; }
  .list { grid-template-columns: 1fr; }
}
</style>
