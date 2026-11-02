<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import SpineMika from '@/components/SpineMika.vue'
import NoticeModal from '@/components/NoticeModal.vue'
import CalendarPanel from '@/components/CalendarPanel.vue'
import Profile from './Profile.vue'
import MailBox from '@/pages/MailBox.vue'
import Social from '@/pages/Social.vue'

const router = useRouter()

// ── 后端接口 ──
function authHeaders(): Record<string, string> {
  const t = localStorage.getItem('schale_token') || ''
  return t ? { Authorization: `Bearer ${t}` } : {}
}
async function apiGet<T = any>(path: string): Promise<T | null> {
  try {
    const r = await fetch(path, { headers: authHeaders() })
    if (!r.ok) return null
    return (await r.json()) as T
  } catch {
    return null
  }
}

// token 失效时用内置口令重登一次（与 loadAll 里首次登录同一路径）
async function relogin(): Promise<boolean> {
  try {
    const r = await fetch('/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password: 'CHANGE_ME' }),
    })
    if (!r.ok) return false
    const j = await r.json()
    if (j && j.token) {
      localStorage.setItem('schale_token', j.token)
      return true
    }
  } catch {
    /* ignore */
  }
  return false
}


// ── 资源（后续接 BFF，现在先占位） ──
const level = ref(0)
const exp = ref(0)
const expMax = ref(24)
const ap = ref(0)
const apMax = ref(28)
const gem = ref(14.66) // 余额（青晶石）
const credit = ref(1_192_593) // token（信用点）

const now = ref('')
let clock = 0
function tick() {
  const d = new Date()
  now.value = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  // 跨昼/夜/深夜档位时自动换底图（十分钟内必然会对上）
  try {
    if (typeof rotateBg === 'function') rotateBg()
  } catch {
    /* 底图未就绪时忽略 */
  }
}
tick()

const creditText = computed(() => {
  const v = credit.value
  if (v >= 1_000_000) return (v / 1_000_000).toFixed(2) + 'M'
  if (v >= 1_000) return (v / 1_000).toFixed(1) + 'K'
  return String(v)
})

// ── 底部导航 ──
const DOCK = [
  { key: 'cafe', label: '咖啡厅', icon: '☕', ready: true, c: '#a9744f' },
  { key: 'daily', label: '日程', icon: '📅', ready: false, c: '#4f95d6' },
  { key: 'member', label: '成员', icon: '👥', ready: false, c: '#5b8fd0' },
  { key: 'team', label: '编队', icon: '⚔', ready: false, c: '#8a7ad0' },
  { key: 'social', label: '社交', icon: '💬', ready: false, badge: '4', c: '#4f9bea' },
  { key: 'craft', label: '制造', icon: '⚙', ready: false, c: '#e0993f' },
  { key: 'shop', label: '商店', icon: '🛒', ready: true, c: '#3f8fd6' },
  { key: 'gacha', label: '招募', icon: '🎯', ready: false, c: '#e879a6' },
]
const dock = ref('cafe')

// ── 立绘切换 / 欣赏模式 ──
// ── 大厅底图：昼夜成对，按现实时间选，定时轮换 ──
const BG_POOL = ['cherinooffice','cherinooffice2','gamedevroom','committeeroom',
  'trinitymeetingroom','trinitystreet','trinitymarket','trinityhospital',
  'gehennaclassroom','gehennaclubroom2','gehennacampus','gehennacouncilhall',
  'milleniumcorridor','shanteahouse','srtbase','ariuscampus','desertresidence',
  'hyakkiyakomeetingroom','abandonedcorridor','abandonedwarehouse',
  'atelier','auditorium','beachside','amusement']
// 天空/远景组（B1.背景图），适合室外与过渡场景
const SKY_POOL = [
  { day: '/img/sky/sky-day.webp', night: '/img/sky/sky-night.webp' },
  { day: '/img/sky/sky2-day.webp', night: '/img/sky/sky2-night.webp' },
  { day: '/img/sky/dawn-day.webp', night: '/img/sky/dawn-night.webp' },
  { day: '/img/sky/kivotos-day.webp', night: '/img/sky/kivotos-night.webp' },
  { day: '/img/sky/kivotos2-day.webp', night: '/img/sky/kivotos2-night.webp' },
  { day: '/img/sky/schale-day.webp', night: '/img/sky/schale-night.webp' },
  { day: '/img/sky/stadium-day.webp', night: '/img/sky/stadium-night.webp' },
]

// 大厅底图固定为夏莱办公室，按现实时间分三档：白天 / 夜晚 / 深夜
const OFFICE_BG = {
  day: '/img/bg/schale-office.webp',
  night: '/img/bg/schale-office-night.webp',
  night2: '/img/bg/schale-office-night2.webp',
}
const bgIdx = ref(0)
const isNight = ref(false)
const bgA = ref(OFFICE_BG.day)
const bgB = ref('')
const crossOn = ref(false)

/** 场景池：30 组室内 + 7 组天空/远景，天空组按「室外 / 过渡」场景加权使用 */
const MIX = [...BG_POOL, ...SKY_POOL.map((_, i) => 'sky:' + i)]

function pickBg() {
  const forced = typeof location !== 'undefined' ? new URLSearchParams(location.search).get('hour') : null
  const h = forced !== null ? Number(forced) : new Date().getHours()
  isNight.value = h < 6 || h >= 18
  // 夏莱办公室三档：6~17 白天，18~次日 0 点 夜晚，01:00~05:59 深夜（?hour= 可强制）
  if (h >= 6 && h < 18) return OFFICE_BG.day
  if (h >= 18 || h < 1) return OFFICE_BG.night
  return OFFICE_BG.night2
}

function rotateBg(force = false) {
  const next = pickBg()
  if (!bgA.value || force) {
    bgA.value = next
    return
  }
  if (next === bgA.value) {
    // 昼夜刚切换，直接换
    bgA.value = next
    return
  }
  bgB.value = next
  crossOn.value = false
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      crossOn.value = true
      window.setTimeout(() => {
        bgA.value = next
        crossOn.value = false
      }, 900)
    })
  })
}

function nextBg() {
  bgIdx.value = (bgIdx.value + 1) % MIX.length
  rotateBg(true)
}

const VARIANTS = [
  { key: 'spr' as const, label: '常服立绘' },
  { key: 'home' as const, label: '回忆大厅' },
  { key: 'swim' as const, label: '泳装大厅' },
]
const variantIdx = ref(Number(localStorage.getItem('schale_variant') || 0) || 0)
const variant = computed(() => VARIANTS[variantIdx.value % VARIANTS.length].key)
const zen = ref(false)
function cycleVariant() {
  variantIdx.value = (variantIdx.value + 1) % VARIANTS.length
  localStorage.setItem('schale_variant', String(variantIdx.value))
  // 回忆大厅是整场景，切过去自动进欣赏模式
}
function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape' && zen.value) toggleZen()
}
function toggleZen() {
  zen.value = !zen.value
}

// ── 左侧入口 ──
const ICONS: Record<string, string> = {
  notice: '/img/icon/lobby-notice.png',
  mail: '/img/icon/momotalk.png',
  task: '/img/icon/lobby-task.png',
  shop: '/img/icon/lobby-gem.png',
}

const SIDE = [
  { key: 'notice', label: '公告', icon: '📢', badge: 'noticeBadge', ready: true },
  { key: 'mail', label: '桃信', icon: '💌', badge: 'mailBadge', ready: true },
  { key: 'task', label: '工作任务', icon: '📋', sub: '0/8', ready: false },
  { key: 'shop', label: '购买青辉石', icon: '💎', ready: false },
]

// ── 右侧卡片 ──
const todos = ref([
  { tone: 'warn', text: '余额过半会提醒你', note: '阈值 50% · 每 30 分钟查一次' },
  { tone: 'ok', text: '模型链路正常', note: 'CodeBuddy 主路 · 官方兜底' },
])

const nowInfo = ref({
  online: false,
  groups: 0,
  plugins: 0,
  pluginsTotal: 0,
})


// 大厅问候语：后端 LLM 实时生成，失败就保留本地兜底文案
async function fetchHello() {
  try {
    helloTyping.value = true
    const r = await fetch('/api/hello', { headers: authHeaders() })
    if (!r.ok) {
      // token 过期就重登一次再取
      if (r.status === 401 && (await relogin())) return fetchHello()
      throw new Error('http ' + r.status)
    }
    const j = await r.json()
    if (j && j.text) helloText.value = j.text
    // 情绪由后端 AstrBot 决定；拿不到就留空，交给前端兜底
    if (j && typeof j.emotion === 'string') serverEmotion.value = j.emotion
  } catch {
    /* 保留兜底文案 */
  } finally {
    helloTyping.value = false
  }
}

// ── 公告栏 ──
const calOpen = ref(new URLSearchParams(location.search).get('cal') === '1')
const today = new Date()
const noticeOpen = ref(false)
// 立绘气泡：由后端 LLM 实时生成
const helloText = ref('老师，回来了。今天也要一起加油哦☆')
const helloTyping = ref(false)
// 立绘包围盒（相对 .stage，CSS px）——气泡按它定位，永不遮人
const mikaRef = ref<any>(null)
function onStage() {
  if (zen.value) {
    toggleZen()
    return
  }
  poke()
}

// 立绘包围盒回调：气泡改成百分比定位后不再用它，保留钩子避免模板报错
function onSprBounds(_b: { left: number; top: number; right: number; bottom: number }) {
  /* 预留：以后要做「气泡避让头发」时在这里算 */
}

function poke() {
  mikaRef.value?.playOne?.()
  fetchHello()
}

// 气泡固定在立绘头顶右上角（百分比定位，不依赖包围盒，不会随呼吸抖动）
const noticeTab = ref('')
const socialOpen = ref(false)
const socialView = ref<'home' | 'friends' | 'groups' | 'helpers'>('home')
const mailOpen = ref(false)
const profileOpen = ref(false)

async function loadAll() {
  // 首次进入自动登录，之后用 localStorage 里的 token
  if (!localStorage.getItem('schale_token')) {
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
    } catch {
      /* ignore */
    }
  }
  const ov = await apiGet<any>('/api/overview')
  if (ov?.res) {
    gem.value = ov.res.gem ?? gem.value
    credit.value = ov.res.credit ?? credit.value
    ap.value = ov.res.ap ?? ap.value
    apMax.value = ov.res.apMax ?? apMax.value
  }
  if (ov?.lv) {
    level.value = ov.lv.days ?? 0
    exp.value = ov.lv.exp ?? 0
    expMax.value = ov.lv.expMax ?? 24
  }
  if (ov?.todo?.length) todos.value = ov.todo
  if (ov?.now) {
    nowInfo.value = {
      online: !!ov.now.online,
      groups: ov.now.groups ?? 0,
      plugins: ov.now.plugins ?? 0,
      pluginsTotal: ov.now.pluginsTotal ?? 0,
    }
  }
  const ml = await apiGet<any>('/api/mail')
  if (ml?.people) MAIL_PEOPLE.value = ml.people
  const nt = await apiGet<any>('/api/notice')
  if (nt) {
    NOTICES.value = nt.notices || []
    EVENTS.value = nt.events || []
    ERRORS.value = nt.errors || []
  }
}

let refresh = 0

// ── 未读数：公告 = 今天异常条数，桃信 = 还没看过的印象卡 ──
const noticeSeen = ref<number>(Number(localStorage.getItem('schale_notice_seen') || 0))
const mailRead = ref<string[]>(JSON.parse(localStorage.getItem('schale_mail_read') || '[]'))
const MAIL_PEOPLE = ref<any[]>([])
const NOTICES = ref<any[]>([])
const EVENTS = ref<any[]>([])
const ERRORS = ref<any[]>([])

const noticeBadge = computed(() => {
  const n = ERRORS.value.length - noticeSeen.value
  return n > 0 ? String(n) : ''
})
const mailBadge = computed(() => {
  const n = MAIL_PEOPLE.value.filter((p: any) => !mailRead.value.includes(p.id)).length
  return n > 0 ? String(n) : ''
})

function badgeOf(k: string): string {
  if (k === 'notice') return noticeBadge.value
  if (k === 'mail') return mailBadge.value
  return ''
}

function markNoticeRead() {
  noticeSeen.value = ERRORS.value.length
  localStorage.setItem('schale_notice_seen', String(noticeSeen.value))
}
function markMailRead(id: string) {
  if (!id || mailRead.value.includes(id)) return
  mailRead.value = [...mailRead.value, id]
  localStorage.setItem('schale_mail_read', JSON.stringify(mailRead.value))
}
function onRail(k: string) {
  if (k === 'task') {
    router.push('/tasks')
    return
  }
  nextBg()
  if (k === 'notice') {
    noticeOpen.value = true
    markNoticeRead()
  } else if (k === 'mail') {
    mailOpen.value = true
    // 打开就算全部看过
    mailRead.value = MAIL_PEOPLE.value.map((p: any) => p.id)
    localStorage.setItem('schale_mail_read', JSON.stringify(mailRead.value))
  }
}

function onDock(k: string) {
  nextBg()
  dock.value = k
  if (k === 'cafe') router.replace('/cafe')
  else if (k === 'shop') router.replace('/shop')
  else if (k === 'member') router.replace('/members')
  else if (k === 'social') {
    socialView.value = 'home'
    socialOpen.value = true
  }
  else if (k === 'daily') router.replace('/daily')
  else if (k === 'team') router.replace('/squad')
}

onMounted(() => {
  // 调试参数：?social=1 直接打开社交浮层，&socview=groups|friends|helpers 指定子页
  {
    const sp = new URLSearchParams(location.search)
    if (sp.get('profile') === '1') profileOpen.value = true
    if (sp.get('social') === '1') {
      const v = sp.get('socview')
      if (v === 'groups' || v === 'friends' || v === 'helpers') socialView.value = v as any
      socialOpen.value = true
    }
  }
  document.title = 'DBG soc=' + socialOpen.value + ' q=' + location.search
  window.addEventListener('keydown', onKey)

  try { rotateBg(true) } catch (e) { /* 底图异常不影响其它初始化 */ }
  clock = window.setInterval(tick, 20000)
  // 调试参数：?zen=1 进欣赏模式，?variant=home 切回忆大厅
  const _sp = new URLSearchParams(location.search)
  if (_sp.has('zen')) zen.value = true
  const _v = _sp.get('variant')
  if (_v) {
    const _i = VARIANTS.findIndex((x) => x.key === _v)
    if (_i >= 0) variantIdx.value = _i
  }
  // ?notice=1 / ?mail=1 直接打开（调试/截图用）
  const sp = new URLSearchParams(location.search)
  if (sp.has('notice')) noticeOpen.value = true
  if (sp.has('mail')) mailOpen.value = true
  noticeTab.value = sp.get('tab') || ''
  loadAll().then(fetchHello)
  refresh = window.setInterval(loadAll, 60000)
})
onUnmounted(() => {
  window.removeEventListener('keydown', onKey)
  window.clearInterval(clock)
  window.clearInterval(refresh)
})
// ═══ 对话气泡：按情绪选贴图（游戏原生 Emoticon / Toon Balloon 系列）═══
// solid: 实心白底（文字直接压上）；outline: 手绘描边圈（需要一层浅底衬着）
const BALLOONS: Record<string, { bg: string; pad: string; solid: boolean; color: string; flip?: boolean }> = {
  calm:      { bg: '/img/deco/balloonN.png',       pad: '15px 30px 26px', solid: true,  color: '#2b3a52', flip: true },
  quiet:     { bg: '/img/deco/balloonT.png',       pad: '15px 30px 24px', solid: true,  color: '#2b3a52', flip: true },
  happy:     { bg: '/img/deco/balloon-pink.png',   pad: '26px 40px 30px', solid: false, color: '#41506a' },
  shy:       { bg: '/img/deco/balloon-toon-blue.png', pad: '26px 38px 30px', solid: false, color: '#41506a' },
  surprise:  { bg: '/img/deco/balloon-blue.png',   pad: '26px 40px 30px', solid: false, color: '#41506a' },
  angry:     { bg: '/img/deco/balloon-toon-red.png', pad: '26px 38px 32px', solid: false, color: '#41506a' },
  tired:     { bg: '/img/deco/balloon-09.png',     pad: '26px 40px 30px', solid: false, color: '#41506a' },
  memo:      { bg: '/img/deco/memo-wide.webp',     pad: '13px 24px 16px', solid: true,  color: '#2b3a52' },
}
const BALLOON_KEYS = Object.keys(BALLOONS)

// 从这句话里判断情绪（够用即可：喊号、语气词、标点）
const serverEmotion = ref('')
const EMOTION_OK = ['calm', 'quiet', 'happy', 'shy', 'surprise', 'angry', 'tired']
// 情绪由后端（AstrBot 的 LLM）决定，前端只在拿不到时按文案兜底
const emotion = computed(() => {
  if (EMOTION_OK.includes(serverEmotion.value)) return serverEmotion.value
  const t = helloText.value || ''
  if (/[!！]/.test(t) && /(诶|欸|咦|啊|什|惊|真的吗)/.test(t)) return 'surprise'
  if (/(哼|讨厌|生气|不许|别闹|真是的)/.test(t)) return 'angry'
  if (/(困|睡|累|哈欠|晚点|休息)/.test(t)) return 'tired'
  if (/(笑|开心|高兴|太好|喜欢|嘿嘿|哈哈|耶)/.test(t)) return 'happy'
  if (/(害羞|脸红|那个|才不|才没有)/.test(t)) return 'shy'
  return 'calm'
})

// 手动覆盖：点工具栏的气泡按钮后按顺序轮换，再点一圈回到「跟随情绪」
const manualBalloon = ref<string | null>(null)
function cycleBalloon() {
  const i = manualBalloon.value ? BALLOON_KEYS.indexOf(manualBalloon.value) : -1
  manualBalloon.value = i >= BALLOON_KEYS.length - 1 ? null : BALLOON_KEYS[i + 1]
}
const balloonKey = computed(() => manualBalloon.value || emotion.value)
const balloon = computed(() => BALLOONS[balloonKey.value] || BALLOONS.calm)

const bubbleAnchor = computed(() => ({ left: '55%', top: '11%' }))
const bubbleStyle = computed(() => ({
  ...bubbleAnchor.value,
  background: balloon.value.solid ? 'none' : 'url(' + balloon.value.bg + ') center / 100% 100% no-repeat',
  borderImageSource: balloon.value.solid ? 'url(' + balloon.value.bg + ')' : 'none',
  padding: balloon.value.solid ? '0 6px' : '24px 44px 28px',
  color: balloon.value.color,
  transform: balloon.value.flip ? 'scaleX(-1)' : 'none',
}))

// ═══ 情绪符号（游戏 Emoticon_* 素材，气泡旁边飘一下）═══
const EMOTES: Record<string, { src: string; size: number; dx: number; dy: number; rot?: number }[]> = {
  happy:    [{ src: '/img/emote/twinkle.png', size: 46, dx: -6,  dy: -10, rot: 8 },
             { src: '/img/emote/note.png',    size: 34, dx: 256, dy: -46, rot: -12 }],
  shy:      [{ src: '/img/emote/shy.png',     size: 62, dx: 10,  dy: -8 },
             { src: '/img/emote/sweat1.png',  size: 20, dx: 300, dy: -6 }],
  surprise: [{ src: '/img/emote/excl-orange.png', size: 58, dx: 268, dy: -52, rot: 12 },
             { src: '/img/emote/sweat1.png',      size: 20, dx: 6,   dy: -4 }],
  angry:    [{ src: '/img/emote/anger.png',   size: 56, dx: 4,   dy: -18 },
             { src: '/img/emote/excl-red.png', size: 46, dx: 276, dy: -50, rot: -10 }],
  tired:    [{ src: '/img/emote/sweat2.png',  size: 22, dx: 292, dy: -18 },
             { src: '/img/emote/think.png',   size: 52, dx: -16, dy: -34, rot: -6 }],
  quiet:    [{ src: '/img/emote/chat.png',    size: 40, dx: 20,  dy: -14, rot: -8 }],
  calm:     [{ src: '/img/emote/chat.png',    size: 30, dx: 18,  dy: -12, rot: -10 }],
}
const emoteList = computed(() => EMOTES[balloonKey.value] || EMOTES.calm)

</script>

<template>
  <div class="home" :class="{ zen, 'v-home': variant === 'home' || variant === 'swim' }">
    <!-- 底图 -->
    <div class="bg" :style="{ backgroundImage: `url(${bgA})` }" aria-hidden="true"></div>
    <div class="bg bg2" :class="{ show: crossOn }" :style="{ backgroundImage: `url(${bgB})` }" aria-hidden="true"></div>
    <div class="bg-tint" aria-hidden="true"></div>

    <!-- ═══ 顶部 ═══ -->
    <header class="top">
      <!-- 等级 -->
      <div class="lvbox" role="button" tabindex="0" title="账号信息" @click="profileOpen = true">
        <div class="lv-num">
          <span class="lv-k">等级</span>
          <b>{{ level }}</b>
        </div>
        <div class="lv-meta">
          <span class="lv-name">老师</span>
          <span class="lv-bar"><i :style="{ width: Math.min(100, (exp / expMax) * 100) + '%' }"></i></span>
          <span class="lv-txt num">{{ exp }} / {{ expMax }} 时</span>
        </div>
      </div>
      <button class="lv-reward" title="等级奖励">
        <svg viewBox="0 0 24 24"><rect x="4" y="3" width="16" height="18" rx="2.5" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M8 8h8M8 12h8M8 16h5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>
        <em>等级奖励</em>
      </button>

      <!-- 资源条 -->
      <div class="res">
        <div class="pill">
          <img src="/img/currency/ap.webp" alt="" />
          <span class="num">{{ ap }}/{{ apMax }}</span>
          <button class="plus" title="今日剩余调用额度">+</button>
        </div>
        <div class="pill">
          <img src="/img/currency/credit.webp" alt="" />
          <span class="num">{{ creditText }}</span>
        </div>
        <div class="pill">
          <img src="/img/currency/gem.webp" alt="" />
          <span class="num">{{ gem.toFixed(2) }}</span>
          <button class="plus" title="DeepSeek 余额">+</button>
        </div>
      </div>

      <!-- 右上三个小按钮 -->
      <div class="tright">
        <button class="tbtn" title="会话"><svg viewBox="0 0 24 24"><circle cx="12" cy="8" r="3.6" fill="none" stroke="currentColor" stroke-width="1.9"/><path d="M5 20c0-3.6 3.1-6.2 7-6.2s7 2.6 7 6.2" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"/></svg></button>
        <button class="tbtn" title="信箱"><svg viewBox="0 0 24 24"><rect x="3" y="5.5" width="18" height="13" rx="2" fill="none" stroke="currentColor" stroke-width="1.9"/><path d="M4 7l8 6 8-6" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"/></svg></button>
        <button class="tbtn" title="菜单"><svg viewBox="0 0 24 24"><path d="M5 7h14M5 12h14M5 17h14" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg></button>
      </div>
    </header>

    <!-- ═══ 左侧 2×2 ═══ -->
    <nav class="side-grid">
      <button
        v-for="s in SIDE"
        :key="s.key"
        class="sq"
        :class="[s.key, { dim: !s.ready }]"
        @click="onRail(s.key)"
      >
        <span class="sq-ico">
          <img
            class="sq-img"
            :src="ICONS[s.key]"
            :alt="s.label"
          />
          <i v-if="badgeOf(s.key)" class="badge">{{ badgeOf(s.key) }}</i>
          <em v-if="s.sub" class="sq-sub num">{{ s.sub }}</em>
        </span>
        <span class="sq-label">{{ s.label }}</span>
      </button>
    </nav>

    <!-- ═══ 立绘区 ═══ -->
    <main class="stage" @click="onStage">
      <SpineMika ref="mikaRef" :key="variant" :variant="variant" class="mika-spine" :class="'v-' + variant" :anchor-y="1.12" :zoom="1.16" @bounds="onSprBounds" />

      <!-- ═══ 气泡：跟随立绘头部右上方 ═══ -->
      <div
        v-if="variant !== 'home' && variant !== 'swim'"
        class="bubble"
        :class="{ typing: helloTyping, outline: !balloon.solid, solid: balloon.solid }"
        :style="bubbleStyle"
        @click.stop="fetchHello"
        title="点一下，让她重新说一句"
      >
        <span class="bub-in" :style="{ transform: balloon.flip ? 'scaleX(-1)' : 'none' }">
          <span class="who">圣园弥香</span>
          <p>{{ helloText }}</p>
        </span>
      </div>
      <span v-if="variant !== 'home' && variant !== 'swim'" class="emo-layer" :style="bubbleAnchor">
        <i
          v-for="(e, i) in emoteList"
          :key="balloonKey + i"
          class="emo"
          :style="{
            backgroundImage: 'url(' + e.src + ')',
            width: e.size + 'px',
            height: e.size + 'px',
            marginLeft: e.dx + 'px',
            marginTop: e.dy + 'px',
            transform: 'rotate(' + (e.rot || 0) + 'deg)',
            animationDelay: (i * 0.12) + 's',
          }"
        />
      </span>

    </main>

    <!-- ═══ 立绘工具 + 指引任务 ═══ -->
    <div class="viewer-tools">
      <button class="vtool" :title="'切换立绘（当前：' + VARIANTS[variantIdx % VARIANTS.length].label + '）'" @click="cycleVariant">
        <i class="vt-ic" style="--u: url(/img/icon/swap.svg)"></i>
      </button>
      <button class="vtool" :title="zen ? '显示界面' : '欣赏模式：隐藏界面'" @click="toggleZen">
        <i class="vt-ic" :class="{ flipped: zen }" style="--u: url(/img/icon/full.svg)"></i>
      </button>
      <button class="vtool" :title="'气泡样式：' + balloonKey + '（点一下换下一个）'" @click="cycleBalloon">
        <i class="vt-ic" style="--u: url(/img/icon/balloon.svg)"></i>
      </button>
    </div>

    <button class="guide" title="日历" @click="calOpen = true">
      <span class="guide-ring cal-art">
        <img class="cal-arona" src="/img/icon/calendar-arona.png" alt="日历" />
        <b class="cal-day num">{{ today.getDate() }}</b>
      </span>
      <em>日历</em>
      <i v-if="todos.length" class="gdot num">{{ todos.length }}</i>
    </button>


    <!-- ═══ 左右箭头 ═══ -->
    <button class="arrow left" title="上一位">‹</button>
    <button class="arrow right" title="下一位">›</button>

    <!-- ═══ 底部 dock ═══ -->
    <nav class="dock">
      <button
        v-for="d in DOCK"
        :key="d.key"
        class="dk"
        :class="{ on: dock === d.key, dim: !d.ready }"
        :style="{ color: d.c }"
        @click="onDock(d.key)"
      >
        <span class="dk-ico">
          <i class="dk-ic" :style="{ '--u': 'url(/img/icon/' + d.key + '.svg)' }"></i>
          <i v-if="d.badge" class="dang">{{ d.badge }}</i>
        </span>
        <span class="dk-label">{{ d.label }}</span>
      </button>

      <span class="dock-clock" title="当前时间">
        <b>{{ now }}</b>
        <i class="dc-keys"><em>△</em><em>×</em><em>○</em><em>□</em></i>
      </span>
    </nav>

    <!-- 弹窗 -->
    <NoticeModal v-model:open="noticeOpen" :notices="NOTICES" :events="EVENTS" :errors="ERRORS" :tab="noticeTab" />
    <Profile v-if="profileOpen" :level="level" :exp="exp" :exp-max="expMax" @close="profileOpen = false" />
    <Social v-if="socialOpen" :view="socialView" @close="socialOpen = false" />
    <MailBox v-if="mailOpen" @close="mailOpen = false" />
    <CalendarPanel v-if="calOpen" @close="calOpen = false" />
  </div>
</template>


<style scoped>
.home {
  position: fixed;
  inset: 0;
  overflow: hidden;
  font-family: var(--font-ui);
  user-select: none;
}

/* ── 底图 ── */
.bg {
  position: absolute;
  inset: 0;
  /* 铺满画面、四边不留黑边，按容器比例轻微裁切 */
  background-position: center center;
  background-size: cover;
  background-repeat: no-repeat;
  transition: opacity 0.9s var(--ease);
  will-change: opacity;
}
.bg.bg2 { opacity: 0; }
.bg.bg2.show { opacity: 1; }
.bg-tint {
  position: absolute;
  inset: 0;
  /* 办公室原图直出，不加任何压暗层 */
  background: none;
}

/* ═══ 顶部 ═══ */
.top {
  position: absolute;
  left: 0; right: 0; top: 0;
  height: 76px;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 16px;
  z-index: 6;
}

.lvbox {
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 10px;
  height: 54px;
  padding: 0 18px 0 14px;
  border-radius: 10px;
  background: linear-gradient(160deg, rgba(28, 58, 96, 0.88), rgba(14, 34, 62, 0.86));
  border: 1px solid rgba(150, 196, 240, 0.30);
  box-shadow: 0 6px 20px rgba(2, 12, 28, 0.42);
  clip-path: polygon(0 0, 100% 0, calc(100% - 12px) 100%, 0 100%);
}
.lv-num { display: flex; flex-direction: column; align-items: center; line-height: 1; }
.lv-k { font-size: 9.5px; letter-spacing: 0.14em; color: rgba(190, 220, 250, 0.72); }
.lv-num b { font-family: var(--font-num); font-size: 26px; font-weight: 800; color: #fff; }
.lv-meta { display: flex; flex-direction: column; gap: 3px; min-width: 108px; }
.lv-name { font-size: 12.5px; font-weight: 700; color: #eaf4ff; }
.lv-bar { display: block; height: 5px; border-radius: 3px; background: rgba(255, 255, 255, 0.18); overflow: hidden; }
.lv-bar i { display: block; height: 100%; border-radius: 3px; background: linear-gradient(90deg, #7fc3f5, #4d92dd); }
.lv-txt { font-size: 9.5px; color: rgba(190, 220, 250, 0.70); }

.lv-reward {
  display: flex; flex-direction: column; align-items: center; gap: 1px;
  width: 62px; height: 54px;
  border-radius: 10px;
  background: linear-gradient(160deg, rgba(28, 58, 96, 0.80), rgba(14, 34, 62, 0.78));
  border: 1px solid rgba(150, 196, 240, 0.26);
  color: #cfe6fb;
  cursor: pointer;
  transition: background var(--t-fast) var(--ease);
}
.lv-reward:hover { background: linear-gradient(160deg, rgba(44, 82, 130, 0.90), rgba(20, 46, 80, 0.88)); }
.lv-reward svg { width: 20px; height: 20px; }
.lv-reward em { font-style: normal; font-size: 9.5px; }

.res {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  gap: 10px;
}
.pill {
  display: flex;
  align-items: center;
  gap: 7px;
  height: 38px;
  padding: 0 8px 0 10px;
  border-radius: 19px;
  background: rgba(255, 255, 255, 0.90);
  box-shadow: 0 3px 12px rgba(2, 12, 28, 0.30);
}
.pill img { width: 20px; height: 16px; object-fit: contain; }
.pill .num { font-size: 13.5px; font-weight: 700; color: #2b3a52; }
.plus {
  width: 20px; height: 20px;
  margin-left: 2px;
  border: none; border-radius: 50%;
  background: #dfe9f4;
  color: #5d7591;
  font-size: 14px; line-height: 18px;
  cursor: pointer;
  transition: background var(--t-fast) var(--ease);
}
.plus:hover { background: #c9dcef; }

.tright { margin-left: auto; display: flex; gap: 8px; }
.tbtn {
  width: 38px; height: 34px;
  display: grid; place-items: center;
  border-radius: 9px;
  background: rgba(255, 255, 255, 0.14);
  border: 1px solid rgba(190, 220, 250, 0.24);
  color: #dbeaf9;
  cursor: pointer;
  transition: background var(--t-fast) var(--ease);
}
.tbtn:hover { background: rgba(255, 255, 255, 0.28); }
.tbtn svg { width: 18px; height: 18px; }

/* ═══ 左侧 2×2 ═══ */
.side-grid {
  position: absolute;
  left: 18px;
  top: 92px;
  display: grid;
  grid-template-columns: repeat(2, 78px);
  gap: 12px 10px;
  z-index: 4;
}
.sq {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 0;
  border: none;
  background: none;
  cursor: pointer;
  color: #fff;
  transition: transform var(--t-fast) var(--ease);
}
.sq:hover { transform: translateY(-2px); }
.sq.dim { opacity: 1; }
.sq-ico {
  width: 66px;
  height: 66px;
  border-radius: 15px;
  display: grid;
  place-items: center;
  background: transparent;
  border: none;
  overflow: hidden;
}
.sq-ico svg { width: 38px; height: 38px; }
.sq.notice .sq-ico { color: #7fc3f5; background: transparent; border-color: transparent; }
.sq.mail .sq-ico { color: #f78ba8; background: rgba(255, 232, 243, 0.96); border-color: #ffd3e6; box-shadow: 0 4px 14px rgba(226, 120, 165, 0.24); }
.sq.task .sq-ico { color: #6fb6ea; background: transparent; border-color: transparent; }
.sq.shop .sq-ico { color: #63b9e8; background: transparent; border-color: transparent; }
.sq-label {
  font-size: 12px;
  font-weight: 600;
  color: #f2f8ff;
  text-shadow: 0 1px 4px rgba(2, 12, 28, 0.72);
  white-space: nowrap;
}
.sq-sub {
  position: absolute;
  top: -4px; left: -6px;
  padding: 1px 6px;
  border-radius: 8px;
  background: #4d92dd;
  border: 2px solid #fff;
  box-sizing: content-box;
  font-size: 9.5px;
  font-style: normal;
  font-weight: 700;
  color: #fff;
  line-height: 14px;
}
.badge {
  position: absolute;
  top: -5px; right: -5px;
  min-width: 18px; height: 18px;
  padding: 0 5px;
  border-radius: 9px;
  background: #f0455e;
  border: 2px solid #fff;
  box-sizing: content-box;
  color: #fff;
  font-size: 10.5px; font-weight: 700;
  line-height: 18px; text-align: center;
  font-family: var(--font-num);
  font-style: normal;
}

/* ═══ 立绘 ═══ */
.stage {
  position: absolute;
  left: 190px; right: 120px;
  top: 46px; bottom: -40px;
  z-index: 2;
  overflow: hidden;
}
.mika-spine {
  position: absolute;
  inset: -2% 0 -26% 0;
  pointer-events: auto;
  filter:
    brightness(1) saturate(1)
    drop-shadow(0 2px 5px rgba(10, 28, 56, 0.34))
    drop-shadow(0 16px 34px rgba(4, 18, 38, 0.34));
}

/* ═══ 立绘工具 ═══ */
.viewer-tools {
  position: absolute;
  right: 16px;
  top: 86px;
  display: flex;
  gap: 8px;
  z-index: 6;
}
.vtool {
  position: relative;
  width: 52px; height: 42px;
  display: grid; place-items: center; gap: 1px;
  border: 1px solid rgba(200, 226, 250, 0.42);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.92);
  color: #5b7ea3;
  cursor: pointer;
  box-shadow: 0 4px 14px rgba(2, 12, 28, 0.28);
  transition: background var(--t-fast) var(--ease), transform var(--t-fast) var(--ease);
}
.vtool:hover { background: #fff; transform: translateY(-1px); }
.vtool svg { width: 20px; height: 20px; }
.vtool em { font-style: normal; font-size: 9.5px; line-height: 1; color: #7b93ad; }

/* ═══ 指引任务 ═══ */
.guide {
  position: absolute;
  right: 18px;
  top: 148px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  border: none;
  background: none;
  cursor: pointer;
  z-index: 5;
}
.guide-ring {
  position: relative;
  width: 66px; height: 66px;
  display: grid; place-items: center;
  border-radius: 50%;
  background: radial-gradient(circle at 34% 28%, #eaf6ff, #b9dcf5 62%, #8fc4ea);
  border: 3px solid rgba(255, 255, 255, 0.94);
  box-shadow: 0 6px 20px rgba(2, 12, 28, 0.40), inset 0 0 0 2px rgba(120, 180, 230, 0.42);
  color: #4f7ea8;
}
.guide-ring svg { width: 32px; height: 32px; }
.guide-ring.cal-art {
  width: 83px;
  height: 83px;
  padding: 0;
  overflow: visible;
  background: transparent;
  border: none;
  box-shadow: none;
}
.cal-arona {
  width: 100%;
  height: 100%;
  object-fit: contain;
  display: block;
  filter: drop-shadow(0 4px 8px rgba(10, 32, 58, 0.3));
}
.guide-ring.cal-art .cal-day {
  position: absolute;
  right: -4px;
  bottom: -2px;
  min-width: 20px;
  height: 20px;
  border-radius: 10px;
  background: #f0567a;
  color: #fff;
  font-size: 12px;
  font-weight: 800;
  line-height: 20px;
  text-align: center;
  box-shadow: 0 2px 6px rgba(200, 40, 80, 0.35);
}
.guide-ring.cal {
  position: relative;
  overflow: hidden;
  background: radial-gradient(circle at 34% 28%, #ffffff, #dcefff 62%, #b6d9f2);
}
.guide-ring.cal .cal-top {
  position: absolute;
  left: 0;
  right: 0;
  top: 0;
  height: 18px;
  background: linear-gradient(180deg, #f0605f, #d94a4a);
}
.guide-ring.cal .cal-top::before,
.guide-ring.cal .cal-top::after {
  content: '';
  position: absolute;
  top: 3px;
  width: 5px;
  height: 9px;
  border-radius: 3px;
  background: #fff;
}
.guide-ring.cal .cal-top::before { left: 16px; }
.guide-ring.cal .cal-top::after { right: 16px; }
.guide-ring.cal b {
  position: relative;
  margin-top: 10px;
  font-size: 25px;
  font-weight: 800;
  color: #2f5f8c;
  letter-spacing: -0.02em;
}
.guide em {
  font-style: normal;
  font-size: 12px; font-weight: 700;
  color: #fff;
  text-shadow: 0 1px 5px rgba(2, 12, 28, 0.80);
}
.gdot {
  position: absolute;
  top: -2px; right: -2px;
  min-width: 19px; height: 19px;
  border-radius: 10px;
  background: #f0455e;
  border: 2px solid #fff;
  box-sizing: content-box;
  color: #fff; font-size: 10.5px; font-weight: 700;
  line-height: 19px; text-align: center;
}

/* ═══ 气泡 ═══ */
.bubble {
  position: absolute;
  transform: none;
  border: 0;
  border-radius: 0;
  box-shadow: none;
  text-align: left;
  width: max-content;
  min-width: 200px;
  max-width: 360px;
  cursor: pointer;
  z-index: 4;
}
.bubble .bub-in { display: block; }
/* 实心气球用九宫格拉伸：两端保持圆头，中间随文字宽度伸缩，不会压扁也不会露方框 */
.bubble.solid {
  border: 30px solid transparent;
  border-image-slice: 62 fill;
  border-image-width: 30px;
  border-image-repeat: stretch;
  filter: drop-shadow(0 8px 18px rgba(6, 20, 40, 0.26));
}
.bubble.solid .bub-in { padding: 2px 14px 6px; }
/* 情绪符号独立成层：锚在气泡左上角，不跟着气泡镜像 */
.emo-layer {
  position: absolute;
  width: 0;
  height: 0;
  z-index: 5;
  pointer-events: none;
}
/* 情绪符号：从气泡边缘弹出后轻微浮动 */
.emo {
  position: absolute;
  left: 0;
  top: 0;
  display: block;
  background: center / contain no-repeat;
  pointer-events: none;
  z-index: 5;
  opacity: 0;
  animation: emoPop 0.34s cubic-bezier(0.34, 1.56, 0.64, 1) forwards;
  filter: drop-shadow(0 3px 6px rgba(10, 30, 50, 0.28));
}
@keyframes emoPop {
  0%   { opacity: 0; scale: 0.5; }
  70%  { opacity: 1; scale: 1.12; }
  100% { opacity: 1; scale: 1; }
}
/* 描边款：等比铺图（拉伸会把手绘圈压扁），文字居中，白描边保证可读 */
.bubble.outline {
  background-color: transparent;
  background-size: 100% 100%;
  background-position: center;
  background-repeat: no-repeat;
  min-height: 108px;
  display: flex;
  align-items: center;
}
.bubble.outline .bub-in { width: 100%; }
.bubble.outline .who,
.bubble.outline p {
  text-shadow:
    0 1px 2px rgba(255, 255, 255, 0.98),
    0 0 8px rgba(255, 255, 255, 0.92),
    0 0 16px rgba(255, 255, 255, 0.72);
}

.bubble:hover { filter: brightness(1.03); }
.bubble .who {
  display: block;
  font: 700 11px/1.2 'Microsoft YaHei', 'PingFang SC', system-ui, sans-serif;
  color: #7b93ad;
  margin-bottom: 3px;
  letter-spacing: 0.02em;
}
.bubble p {
  margin: 0;
  font: 400 14px/1.55 'Microsoft YaHei', 'PingFang SC', system-ui, sans-serif;
  letter-spacing: 0.01em;
  color: #2b3a52;
}
.bubble.typing p { color: #94a2b6; }
.bubble.typing p::after { content: '…'; animation: blink 1s infinite; }

/* ═══ 箭头 ═══ */
.arrow {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  width: 30px; height: 52px;
  border: none;
  background: rgba(255, 255, 255, 0.10);
  color: rgba(230, 244, 255, 0.72);
  font-size: 26px; line-height: 1;
  cursor: pointer;
  z-index: 3;
}
.arrow.left { left: 0; border-radius: 0 10px 10px 0; }
.arrow.right { right: 0; border-radius: 10px 0 0 10px; }
.arrow:hover { background: rgba(255, 255, 255, 0.22); color: #fff; }

/* ═══ 底部 dock ═══ */
.dock {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 92px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0;
  padding: 0 34px;
  background: linear-gradient(180deg, rgba(246, 251, 255, 0.94) 0%, rgba(224, 238, 250, 0.9) 62%, rgba(208, 228, 246, 0.9) 100%);
  box-shadow: 0 -6px 22px rgba(4, 20, 42, 0.28);
  clip-path: polygon(1.6% 0, 98.4% 0, 100% 100%, 0 100%);
  backdrop-filter: blur(10px) saturate(1.2);
  -webkit-backdrop-filter: blur(10px) saturate(1.2);
  z-index: 6;
}
.dk {
  flex: 1 1 0;
  min-width: 0;
  position: relative;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  border: none;
  background: transparent;
  cursor: pointer;
  transition: transform 0.16s var(--ease, ease-out);
}
.dk:hover {
  transform: translateY(-2px);
}
.dk-ico {
  position: relative;
  width: 40px;
  height: 40px;
  display: grid;
  place-items: center;
}
.dk-ic {
  width: 38px;
  height: 38px;
  display: block;
  background: currentColor;
  -webkit-mask: var(--u) center / contain no-repeat;
  mask: var(--u) center / contain no-repeat;
  filter: drop-shadow(0 2px 3px rgba(20, 60, 100, 0.18));
}
.dk-label {
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0.02em;
  color: #2f4a68;
  text-shadow: 0 1px 0 rgba(255, 255, 255, 0.72);
}
/* 当前项：从底栏里凸出来的一块白卡 */
.dk.on {
  background: linear-gradient(180deg, #ffffff 0%, #f2f9ff 100%);
  box-shadow: 0 -4px 16px rgba(20, 60, 100, 0.16), inset 0 -2px 0 rgba(150, 195, 235, 0.5);
}
.dk.on::before {
  content: '';
  position: absolute;
  left: 10px;
  right: 10px;
  top: 0;
  height: 3px;
  background: #4f9bea;
  border-radius: 0 0 3px 3px;
}
.dk.on .dk-label {
  color: #2f6fb0;
}
.dk-label { font-size: 12.5px; font-weight: 700; text-shadow: 0 1px 0 rgba(255, 255, 255, 0.85); }
.dang {
  position: absolute;
  top: -6px; right: -10px;
  min-width: 16px; height: 16px;
  border-radius: 8px;
  background: #f0455e;
  border: 2px solid #fff;
  box-sizing: content-box;
  color: #fff; font-size: 9.5px; font-weight: 700;
  line-height: 16px; text-align: center;
  font-style: normal;
}

/* ═══ 欣赏模式 ═══ */
.home.zen .top,
.home.zen .side-grid,
.home.zen .dock,
.home.zen .bubble,
.home.zen .guide,
.home.zen .arrow {
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.34s var(--ease);
}
.home.zen .stage { left: 0; right: 0; top: 0; bottom: 0; }
.home.zen .mika-spine { inset: 0; }
.home.zen .mika-spine {
  filter:
    brightness(0.92) saturate(1.06)
    drop-shadow(0 0 2px rgba(255, 255, 255, 0.42))
    drop-shadow(0 20px 60px rgba(2, 12, 30, 0.86));
}
.home.zen .bg-tint {
  background: radial-gradient(120% 96% at 50% 44%, transparent 30%, rgba(3, 12, 28, 0.86) 100%);
}
.home.zen .viewer-tools { opacity: 0.9; }
.home.zen .vtool {
  background: rgba(10, 22, 40, 0.55) !important;
  border-color: rgba(255, 255, 255, 0.5) !important;
  color: #eaf4ff !important;
}
.home.zen .viewer-tools:hover { opacity: 1; }

/* 回忆大厅整场景铺满时压掉底图 */
.home.v-home .stage { inset: 0; }
.home.v-swim .stage { inset: 0; }
.home.v-swim .mika-spine { inset: -2% -3% -8% -3%; }
.home.v-swim .bg {
  opacity: 1;
  filter: blur(34px) brightness(0.46) saturate(1.25);
  transform: scale(1.2);
}
.home.v-swim .bg-tint {
  background: radial-gradient(120% 96% at 50% 46%, rgba(4, 14, 30, 0.12) 30%, rgba(3, 10, 22, 0.68) 100%);
}
.home.v-home .bg {
  opacity: 1;
  filter: blur(34px) brightness(0.46) saturate(1.25);
  transform: scale(1.2);
}
.home.v-home .bg-tint {
  background: radial-gradient(120% 96% at 50% 46%, rgba(4, 14, 30, 0.12) 30%, rgba(3, 10, 22, 0.68) 100%);
}

.sq-img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  display: block;
  padding: 3px;
  filter: drop-shadow(0 3px 7px rgba(10, 32, 58, 0.32));
}
.sq.mail .sq-img { padding: 7px; }
.sq.shop .sq-img { padding: 10px 1px; }
.dk-img { width: 38px; height: 38px; object-fit: contain; mix-blend-mode: multiply; }

.viewer-tools .vtool img { width: 100%; height: 100%; object-fit: contain; display: block; }
.viewer-tools .vtool img.flipped { transform: scaleX(-1) rotate(180deg); }
.viewer-tools .vtool { width: 58px; height: 40px; background: transparent; box-shadow: none; padding: 0; border: 0; }
.viewer-tools { gap: 10px; }

/* 矢量图标：用 mask 着色，颜色跟随 currentColor */
.sq-ic, .dk-ic, .vt-ic {
  display: block;
  background: currentColor;
  -webkit-mask-image: var(--u);
  mask-image: var(--u);
  -webkit-mask-repeat: no-repeat;
  mask-repeat: no-repeat;
  -webkit-mask-position: center;
  mask-position: center;
  -webkit-mask-size: contain;
  mask-size: contain;
}
.sq-ic { width: 32px; height: 32px; }
.sq { color: #4a7fb5; }
.sq.notice { color: #4f8fd8; }
.sq.mail { color: #e8799f; }
.sq.task { color: #4f9bea; }
.sq.shop { color: #5aa9dc; }
.dk-ic { width: 30px; height: 30px; }
.vt-ic { width: 22px; height: 22px; display: block; }
.vt-ic.flipped { transform: scaleX(-1) rotate(180deg); }
.dock-clock {
  position: absolute;
  right: 22px;
  bottom: 12px;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
  pointer-events: none;
}
.dock-clock b {
  font-family: var(--font-num, 'Segoe UI', sans-serif);
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: #4a5d76;
}
.dc-keys {
  display: flex;
  gap: 5px;
  font-style: normal;
  opacity: 0.55;
}
.dc-keys em {
  font-style: normal;
  font-size: 10px;
  color: #6b7f96;
}
</style>
