<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

const emit = defineEmits<{ (e: 'close'): void }>()

const now = new Date()
const year = ref(now.getFullYear())
const month = ref(now.getMonth() + 1)

const WEEK = ['日', '一', '二', '三', '四', '五', '六']

function daysInMonth(y: number, m: number) {
  return new Date(y, m, 0).getDate()
}
function firstWeekday(y: number, m: number) {
  return new Date(y, m - 1, 1).getDay()
}

/** 官方日历图：页眉美术（月份大字 + 年份 + 标题） */
const banner = computed(
  () => `/img/cal/${year.value}-${String(month.value).padStart(2, '0')}.webp`,
)
const label = computed(() => `${year.value} 年 ${month.value} 月`)

// ── 与「工作任务」联动：把任务的截止日标到日历上 ──
const tasks = ref<any[]>([])
function parseDay(s: string): string | null {
  if (!s) return null
  const m1 = s.match(/(\d{4})\D+(\d{1,2})\D+(\d{1,2})/)
  if (m1) return `${m1[1]}-${String(+m1[2]).padStart(2, '0')}-${String(+m1[3]).padStart(2, '0')}`
  return null
}
const dayDots = computed(() => {
  const map: Record<string, number> = {}
  for (const t of tasks.value) {
    const d = parseDay(t.deadline || '')
    if (d) map[d] = (map[d] || 0) + (t.done ? 0 : 1)
  }
  return map
})
const monthTasks = computed(() => {
  const pre = `${year.value}-${String(month.value).padStart(2, '0')}`
  return tasks.value
    .filter((t) => (parseDay(t.deadline || '') || '').startsWith(pre))
    .sort((a, b) => (a.deadline || '').localeCompare(b.deadline || ''))
})
function keyOf(i: number) {
  const n = cells.value[i]?.day
  if (!n) return ''
  return `${year.value}-${String(month.value).padStart(2, '0')}-${String(n).padStart(2, '0')}`
}
async function loadTasks() {
  const t = localStorage.getItem('schale_token')
  if (!t) {
    const r = await fetch('/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password: 'CHANGE_ME' }),
    })
    const j = await r.json()
    if (j?.token) localStorage.setItem('schale_token', j.token)
  }
  const h = localStorage.getItem('schale_token')
  const r = await fetch('/api/tasks', { headers: h ? { Authorization: 'Bearer ' + h } : {} })
  const j = await r.json()
  if (j?.ok) tasks.value = j.items || []
}

const cells = computed(() => {
  const out: { day: number | null; today: boolean; weekend: boolean }[] = []
  const total = daysInMonth(year.value, month.value)
  const lead = firstWeekday(year.value, month.value)
  const isThis = year.value === now.getFullYear() && month.value === now.getMonth() + 1
  for (let i = 0; i < 42; i++) {
    const n = i - lead + 1
    const ok = n >= 1 && n <= total
    out.push({
      day: ok ? n : null,
      today: isThis && ok && n === now.getDate(),
      weekend: i % 7 === 0 || i % 7 === 6,
    })
  }
  return out
})

function shift(d: number) {
  let m = month.value + d
  let y = year.value
  if (m < 1) {
    m = 12
    y -= 1
  }
  if (m > 12) {
    m = 1
    y += 1
  }
  year.value = y
  month.value = m
}
function goToday() {
  year.value = now.getFullYear()
  month.value = now.getMonth() + 1
}
function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape') emit('close')
  if (e.key === 'ArrowLeft') shift(-1)
  if (e.key === 'ArrowRight') shift(1)
}
onMounted(() => {
  window.addEventListener('keydown', onKey)
  loadTasks()
})
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <div class="calmask" @click.self="emit('close')">
    <div class="calbox">
      <button class="x" @click="emit('close')">✕</button>

      <div class="banner">
        <img :src="banner" :alt="label" />
      </div>

      <div class="wname">
        <span v-for="(w, i) in WEEK" :key="w" :class="{ we: i === 0 || i === 6 }">{{ w }}</span>
      </div>

      <div class="grid">
        <span
          v-for="(c, i) in cells"
          :key="i"
          class="cell"
          :class="{ empty: !c.day, today: c.today, we: c.weekend }"
        >
          {{ c.day ?? '' }}
          <i v-if="c.day && dayDots[keyOf(i)]" class="dot"></i>
        </span>
      </div>

      <div v-if="monthTasks.length" class="mlist">
        <b>本月待办 {{ monthTasks.length }} 条</b>
        <span v-for="t in monthTasks.slice(0, 4)" :key="t.id" :class="{ dn: t.done }">
          <i>{{ (parseDay(t.deadline) || '').slice(8) }} 日</i>{{ t.title }}
        </span>
      </div>

      <div class="cbar">
        <button class="nav" @click="shift(-1)" title="上个月">‹</button>
        <div class="lab">
          <b>{{ label }}</b>
          <i>共 {{ daysInMonth(year, month) }} 天 · 今天 {{ now.getMonth() + 1 }} 月 {{ now.getDate() }} 日 星期{{ WEEK[now.getDay()] }}</i>
        </div>
        <button class="nav" @click="shift(1)" title="下个月">›</button>
        <button class="now" @click="goToday">回到本月</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.calmask {
  position: fixed;
  inset: 0;
  z-index: 42;
  display: grid;
  place-items: center;
  background: rgba(6, 20, 38, 0.58);
  backdrop-filter: blur(4px);
}
.calbox {
  position: relative;
  width: min(980px, 88vw);
  max-height: 92vh;
  display: flex;
  flex-direction: column;
  border-radius: 18px;
  overflow: hidden;
  background: #fbf6ea;
  box-shadow: 0 30px 70px rgba(4, 16, 34, 0.5);
}
.x {
  position: absolute;
  right: 12px;
  top: 10px;
  z-index: 3;
  width: 32px;
  height: 32px;
  border: 0;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.88);
  color: #33587e;
  font-size: 14px;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(20, 50, 80, 0.25);
}
.banner {
  position: relative;
  height: 106px;
  overflow: hidden;
  flex: none;
  background: #4a3a24;
}
.banner img {
  width: 100%;
  display: block;
  transform: translateY(-3%) scale(1.01);
}
.wname {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  padding: 10px 18px 0;
  flex: none;
}
.wname span {
  text-align: center;
  font-size: 12px;
  font-weight: 700;
  color: #a08b68;
}
.wname span.we {
  color: #d1746f;
}
.grid {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  grid-auto-rows: 1fr;
  gap: 4px;
  padding: 8px 18px 14px;
  min-height: 340px;
}
.cell {
  display: flex;
  align-items: flex-start;
  justify-content: flex-start;
  padding: 7px 0 0 9px;
  font-size: 15px;
  font-weight: 700;
  color: #4a3a24;
  background: rgba(255, 253, 247, 0.9);
  border-radius: 8px;
  box-shadow: inset 0 0 0 1px rgba(216, 200, 170, 0.7);
}
.cell.we {
  color: #b85a55;
}
.cell.empty {
  background: transparent;
  box-shadow: none;
}
.cell.today {
  color: #fff;
  background: linear-gradient(180deg, #f2707f, #e0455c);
  box-shadow: 0 4px 12px rgba(224, 69, 92, 0.34);
}
.mlist {
  flex: none;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  padding: 0 20px 10px;
  font-size: 12px;
  color: #7a6444;
}
.mlist b {
  font-size: 12.5px;
  color: #4a3a24;
}
.mlist span {
  padding: 3px 10px;
  border-radius: 999px;
  background: #fff8e8;
  box-shadow: inset 0 0 0 1px rgba(214, 198, 168, 0.8);
}
.mlist span.dn {
  opacity: 0.55;
  text-decoration: line-through;
}
.mlist i {
  font-style: normal;
  font-weight: 800;
  color: #c88a2a;
  margin-right: 4px;
}
.dot {
  position: absolute;
  right: 6px;
  top: 7px;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #f0455e;
}
.cell {
  position: relative;
}
.cbar {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 12px 20px 16px;
  flex: none;
  background: linear-gradient(180deg, rgba(255, 250, 240, 0.6), #f3e9d6);
}
.nav {
  width: 40px;
  height: 40px;
  border: 1px solid #d8c7a8;
  border-radius: 10px;
  background: #fffdf7;
  color: #7a6444;
  font-size: 20px;
  line-height: 1;
  cursor: pointer;
}
.nav:hover {
  background: #fff;
}
.lab {
  flex: 1;
  text-align: center;
}
.lab b {
  display: block;
  font-size: 17px;
  color: #4a3a24;
}
.lab i {
  font-style: normal;
  font-size: 12.5px;
  color: #8a7756;
}
.now {
  height: 36px;
  padding: 0 16px;
  border: 0;
  border-radius: 9px;
  background: #c9a25e;
  color: #fff;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}
</style>
