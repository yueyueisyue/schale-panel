<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import SpineShop from '@/components/SpineShop.vue'
import { panel } from '@/store/panel'

/** 店长：小空（Sora），说白框的署名用她 */
const KEEPER = '小空'

/** 背景图信息：bg.webp 是 1600×1125，柜台下沿在图片高度的 68.5%，
 *  background-position 的纵向对齐点是 30%（与 .bg / .fg 的 CSS 一致）。
 *  用 cover 铺满时图片会被裁，柜台在屏幕上的像素位置随窗口比例变化，
 *  所以这里算出来写进 CSS 变量，人物遮挡线与接触阴影都跟着它走。 */
const BG = { w: 1600, h: 1125, counter: 0.735, posY: 0.3 }
const fgLine = ref(0)
function recalcLine() {
  const vw = window.innerWidth
  const vh = window.innerHeight
  const scale = Math.max(vw / BG.w, vh / BG.h)
  const scaledH = BG.h * scale
  const offsetY = (vh - scaledH) * BG.posY
  fgLine.value = Math.round(offsetY + BG.counter * scaledH)
}

const router = useRouter()

const TOKEN_KEY = 'schale_token'
function authHeaders(): Record<string, string> {
  const t = localStorage.getItem(TOKEN_KEY) || ''
  return t ? { Authorization: 'Bearer ' + t } : {}
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

interface Good {
  id: string; model: string; source: string; kind: string
  apiBase: string; enabled: boolean; context: number
  modalities: string[]; free: boolean
}
interface ShopData {
  goods: Good[]
  today: { tokens: number; calls: number; byPlugin: Record<string, number> }
  week: { day: string; tokens: number; calls: number }[]
  balance: { available: boolean; currency: string; total: number } | null
  services: Record<string, any>
}

const data = ref<ShopData | null>(null)
const res = ref({ ap: 0, apMax: 0, credit: 0, creditText: '0', gem: 0 })
const loading = ref(true)
const tip = ref<string>('')

const CATS = [
  { key: 'goods',   label: '常规道具', icon: 'shop',   img: '/img/shop/item-trinity-2.png' },
  { key: 'gem',     label: '青辉石',   icon: 'buygem', img: '/img/shop/cur-gem.png' },
  { key: 'usage',   label: '用量明细', icon: 'craft',  img: '/img/shop/cur-ap.png' },
  { key: 'week',    label: '近七日活动', icon: 'daily', img: '/img/shop/cur-exp.png' },
  { key: 'service', label: '服务状态', icon: 'member', img: '/img/shop/mat-ssr.png' },
  { key: 'source',  label: '数据来源', icon: 'task',   img: '/img/shop/cur-gold.png' },
]
const _c = new URLSearchParams(location.search).get('cat')
const cat = ref(_c && ['goods','gem','usage','week','service','source'].includes(_c) ? _c : 'goods')

const goods = computed<Good[]>(() => data.value?.goods || [])
const today = computed(() => data.value?.today || { tokens: 0, calls: 0, byPlugin: {} })
const week = computed(() => data.value?.week || [])
const balance = computed(() => data.value?.balance)
const services = computed(() => data.value?.services || {})

const sortedGoods = computed(() => [...goods.value].sort((a, b) => rankOf(a) - rankOf(b)))
function rankOf(g: any) {
  const key = `${g.source}/${g.model}`
  if (key in IMPORTANCE) return IMPORTANCE[key]
  if (/embedding/i.test((g.modalities || []).join(' '))) return 0
  if (g.free) return 1
  return 2
}

const maxWeek = computed(() => Math.max(1, ...week.value.map(w => w.tokens)))
const weekBars = computed(() =>
  week.value.map(w => ({
    ...w,
    h: Math.round((w.tokens / maxWeek.value) * 100),
    label: (w.day || '').slice(5).replace('-', '/'),
    k: fmtTok(w.tokens),
  }))
)
const pluginRows = computed(() => {
  const m = today.value.byPlugin || {}
  const arr = Object.entries(m).map(([k, v]) => ({ name: k, v: Number(v) }))
  arr.sort((a, b) => b.v - a.v)
  const sum = arr.reduce((s, x) => s + x.v, 0) || 1
  return arr.map(x => ({ ...x, pct: Math.round((x.v / sum) * 100), k: fmtTok(x.v) }))
})

const SERVICE_ROWS = computed(() => {
  const s: any = services.value || {}
  const pick = (o: any, label: string) => {
    const up = o?.up
    const ok = o?.healthy
    const extra = o?.models ? `${o.models.length} 个模型` : o?.realm ? `realm ${o.realm}` : ''
    return { label, up: !!up, ok: ok === undefined ? !!up : !!ok, extra }
  }
  return [
    pick(s.gateway, '网关'),
    pick(s.router, '路由层'),
    pick(s.ollama, '向量服务'),
  ]
})

const SOURCES = [
  { k: 'logs/astrbot.log', v: '错误聚合 · 活跃天数 · 启动与插件事件' },
  { k: 'plugin_data/…/usage.jsonl', v: 'token 消耗 · 调用次数 · 按插件明细' },
  { k: 'cmd_config.json', v: 'provider 列表 · 模型 · 上下文 · 能力标签' },
  { k: 'api.deepseek.com/user/balance', v: 'DeepSeek 账户余额（人民币）' },
]

/** 用 Y1（CBT 素材包）里的道具图标当商品图：书=模型、以太=向量、终极书=免费 */
const ICONS = ['/img/shop/item-trinity-2.png', '/img/shop/item-millennium-2.png', '/img/shop/item-gehenna-2.png', '/img/shop/item-ultimate.png']
/** 同一族技能书的四档稀有度：0 白 → 1 蓝 → 2 金 → 3 紫 */
const RARITY_ICONS = [
  '/img/shop/book-0.png',
  '/img/shop/book-1.png',
  '/img/shop/book-2.png',
  '/img/shop/book-3.png',
]

/** API 重要性：本地向量最低，主力对话模型最高 */
const IMPORTANCE: Record<string, number> = {
  'ollama/bge-m3': 0,
  'codebuddy/global:deepseek-v4.1-flash': 1,
  'codebuddy/deepseek-v4.1-flash': 1,
  'deepseek/deepseek-flash': 2,
  'deepseek/deepseek-chat': 3,
}


function iconOf(g: any) {
  return RARITY_ICONS[Math.min(3, rankOf(g))]
}

const CONTACT = ref('欢迎光临～要看看今天的模型吗？')
const charRef = ref<any>(null)
const greeting = ref(false)

/** 点一下她：换一句新台词 + 一个反应动作 */
/** 调试：?expr=05 直接在挂载后播一个部件动画，方便逐个看效果 */
function debugExpr() {
  const e = new URLSearchParams(location.search).get('expr')
  if (!e) return
  window.setTimeout(() => {
    if (e === 'random') charRef.value?.randomExpr?.()
    else if (e === 'talk') charRef.value?.talk?.(6000)
    else charRef.value?.playExpression?.(e)
  }, 1200)
}

async function greet() {
  if (greeting.value) return
  greeting.value = true
  charRef.value?.react?.()
  try {
    const r = await apiGet<any>('/api/hello?scene=shop')
    if (r?.text) CONTACT.value = r.text
  } finally {
    window.setTimeout(() => { greeting.value = false }, 900)
  }
}

function fmtTok(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(2) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return String(n ?? 0)
}
function ctxText(n: number): string {
  if (!n) return '—'
  if (n >= 1_000_000) return n / 1_000_000 + 'M'
  if (n >= 1000) return Math.round(n / 1000) + 'K'
  return String(n)
}
function initials(s: string): string {
  const t = (s || '?').replace(/[^A-Za-z\u4e00-\u9fa5]/g, '')
  return (t[0] || '?').toUpperCase()
}
function toneOf(g: Good, i: number): string {
  if (g.free) return '#3fa46a'
  if (g.kind.includes('embedding')) return '#7a6bd0'
  return ['#4f8fd8', '#d08a3f', '#4f9bea', '#c0557f'][i % 4]
}
function openTip(g: Good) {
  tip.value = `${g.source} / ${g.model}\n上下文 ${ctxText(g.context)} · ${g.modalities.join(' / ') || '—'}\n在 AstrBot 的 cmd_config.json → provider 里调整这一条。`
}
function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape') tip.value = ''
}

async function ensureToken(): Promise<boolean> {
  if (localStorage.getItem(TOKEN_KEY)) return true
  try {
    const r = await fetch('/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password: 'CHANGE_ME' }),
    })
    if (!r.ok) return false
    const j = await r.json()
    if (j?.token) { localStorage.setItem(TOKEN_KEY, j.token); return true }
  } catch { /* ignore */ }
  return false
}

async function load() {
  loading.value = true
  await ensureToken()
  const [shop, ov] = await Promise.all([
    apiGet<{ ok: boolean } & ShopData>('/api/shop'),
    apiGet<any>('/api/overview'),
  ])
  if (shop?.ok) {
    data.value = shop as ShopData
  }
  if (ov?.ok) {
    res.value = {
      ap: ov.res?.ap ?? 0,
      apMax: ov.res?.apMax ?? 0,
      creditText: ov.res?.creditText ?? '0',
      credit: ov.res?.credit ?? 0,
      gem: ov.res?.gem ?? 0,
    }
  }
  loading.value = false
}

let timer = 0
onMounted(() => {
  load()
  timer = window.setInterval(load, 60000)
  window.addEventListener('keydown', onKey)
  recalcLine()
  window.addEventListener('resize', recalcLine)
  debugExpr()
  if (new URLSearchParams(location.search).has('autoclick')) {
    window.setTimeout(() => greet(), 12000)
  }
})

onUnmounted(() => {
  clearInterval(timer)
  window.removeEventListener('keydown', onKey)
  window.removeEventListener('resize', recalcLine)
})
</script>

<template>
  <div class="shop" :style="{ '--fgl': fgLine + 'px' }">
    <!-- 背景 -->
    <div class="bg" />
    <div class="bg-veil" />
    <!-- 前景柜台：与背景同一张图，只露出下半部分，边缘羽化 -->
    <div class="fg" />

    <!-- 顶栏 -->
    <header class="top">
      <button class="back" @click="router.replace('/home')">
        <svg viewBox="0 0 24 24"><path d="M14.5 5.5 8 12l6.5 6.5" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>
      </button>
      <h1>商店<em>?</em></h1>

      <div class="res">
        <span class="pill"><i class="ap" />{{ res.ap }}<em>/{{ res.apMax }}</em><b>+</b></span>
        <span class="pill"><i class="cr" />{{ res.creditText }}<b>+</b></span>
        <span class="pill"><i class="gm" />{{ res.gem.toFixed(2) }}<b>+</b></span>
      </div>

      <div class="topr">
        <button class="tbtn" title="刷新" @click="load">⟳</button>
        <button class="tbtn" title="办公室" @click="router.replace('/home')">⌂</button>
      </div>
    </header>

    <!-- 左侧分类 -->
    <nav class="cats">
      <div class="cat-head">商品分类</div>
      <button
        v-for="c in CATS" :key="c.key"
        class="cat" :class="{ on: cat === c.key }"
        @click="cat = c.key"
      >
        <img class="ci" :src="c.img" :alt="c.label" />
        <span>{{ c.label }}</span>
      </button>
    </nav>

    <!-- 中间：立绘 + 前台 -->
    <section class="stage" title="点一下她" @click="greet">
      <div class="ground"></div>
      <div class="char">
        <SpineShop ref="charRef" :zoom="1.06" fill :offset-y="0.33" />
      </div>
    </section>

    <!-- 招呼气泡 -->
    <div class="say">
      <span>{{ KEEPER }}</span>
      <p>{{ CONTACT }}</p>
    </div>

    <!-- 右侧内容 -->
    <main class="panel">
      <!-- 商品 -->
      <div v-if="cat === 'goods'" class="grid">
        <article v-for="(g, i) in sortedGoods" :key="g.id" class="card">
          <h3>{{ g.source }}<br><em>{{ g.model }}</em></h3>
          <div class="art" :style="{ '--tone': toneOf(g, i) }">
            <div class="sheet">
              <img class="itm" :src="iconOf(g)" :alt="g.model" />
            </div>
            <span class="qty">{{ g.free ? 'FREE' : 'API' }}</span>
          </div>
          <ul class="attrs">
            <li>上下文 {{ ctxText(g.context) }}</li>
            <li>{{ g.modalities.join(' · ') || '—' }}</li>
          </ul>
          <div class="buy" :class="{ free: g.free }">
            <span class="price">{{ g.free ? '免费' : '按量' }}</span>
            <button @click="openTip(g)">查看</button>
          </div>
        </article>
        <p v-if="!goods.length" class="empty">还没有读到 provider，检查 data_dir 是否指向 AstrBot 的 data 目录。</p>
      </div>

      <!-- 青辉石：余额 -->
      <div v-else-if="cat === 'gem'" class="blocks">
        <div class="block">
          <h4><span>钱包</span></h4>
          <div class="pbody">
            <div class="big">
              <b>{{ balance ? balance.total.toFixed(2) : '—' }}</b>
              <em>{{ balance?.currency || 'CNY' }}</em>
            </div>
            <p class="hint">{{ balance?.available ? '账户可用，余额足够继续调用。' : '余额读不到，检查 DeepSeek key 是否配置。' }}</p>
          </div>
        </div>
        <div class="block">
          <h4><span>今日消耗</span></h4>
          <div class="pbody kvs">
            <div><dt>调用</dt><dd>{{ today.calls }} 次</dd></div>
            <div><dt>token</dt><dd>{{ fmtTok(today.tokens) }}</dd></div>
            <div><dt>平均</dt><dd>{{ today.calls ? Math.round(today.tokens / today.calls) : 0 }} / 次</dd></div>
          </div>
        </div>
      </div>

      <!-- 用量明细 -->
      <div v-else-if="cat === 'usage'" class="blocks">
        <div class="block wide">
          <h4><span>按插件</span></h4>
          <div class="pbody">
            <div v-for="r in pluginRows" :key="r.name" class="row">
              <span class="rn">{{ r.name || '未标注' }}</span>
              <span class="bar"><i :style="{ width: r.pct + '%' }" /></span>
              <span class="rv">{{ r.k }}</span>
            </div>
            <p v-if="!pluginRows.length" class="hint">今天还没有调用记录。</p>
          </div>
        </div>
      </div>

      <!-- 近七日 -->
      <div v-else-if="cat === 'week'" class="blocks">
        <div class="block wide">
          <h4><span>近七日 token</span></h4>
          <div class="pbody">
            <div class="chart">
              <div v-for="b in weekBars" :key="b.day" class="col">
                <span class="cv">{{ b.k }}</span>
                <i :style="{ height: b.h + '%' }" />
                <em>{{ b.label }}</em>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 服务状态 -->
      <div v-else-if="cat === 'service'" class="blocks">
        <div class="block wide">
          <h4><span>链路</span></h4>
          <div class="pbody">
            <div v-for="s in SERVICE_ROWS" :key="s.label" class="srow">
              <i class="dot" :class="{ ok: s.up, bad: !s.up }" />
              <span class="sn">{{ s.label }}</span>
              <span class="sv">{{ s.up ? (s.ok ? '正常' : '可达但异常') : '离线' }}</span>
              <span class="sx">{{ s.extra }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 数据来源 -->
      <div v-else class="blocks">
        <div class="block wide">
          <h4><span>读取自</span></h4>
          <div class="pbody">
            <div v-for="s in SOURCES" :key="s.k" class="srow">
              <span class="sn mono">{{ s.k }}</span>
              <span class="sv sm">{{ s.v }}</span>
            </div>
          </div>
        </div>
      </div>
    </main>

    <!-- 底部更新条 -->
    <footer class="foot">
      <span class="clock">🕐 距离更新 <b>约 1 分钟</b></span>
      <button class="refresh" @click="load">⟳ 更新</button>
    </footer>

    <!-- 查看弹层 -->
    <div v-if="tip" class="tipmask" @click="tip = ''">
      <div class="tipbox" @click.stop>
        <pre>{{ tip }}</pre>
        <button @click="tip = ''">知道了</button>
      </div>
    </div>

    <div v-if="loading" class="loading">营业中…</div>
  </div>
</template>

<style scoped>
.shop {
  position: absolute;
  inset: 0;
  overflow: hidden;
  font-family: var(--font-ui, 'Noto Sans SC', system-ui, sans-serif);
  color: #2b3444;
  background: #cfe6f5;
}

/* 背景 */
.bg {
  position: absolute;
  inset: 0;
  background: url('/img/shop/bg.webp') center 30% / cover no-repeat;
  filter: saturate(1.06) brightness(0.92) blur(3px);
  transform: scale(1.03);
}
.fg {
  position: absolute;
  inset: 0;
  background: url('/img/shop/bg.webp') center 30% / cover no-repeat;
  filter: saturate(1.05) brightness(0.98);
  -webkit-mask-image: linear-gradient(180deg, transparent var(--fgl, 68.5%), #000 calc(var(--fgl, 68.5%) + 26px));
  mask-image: linear-gradient(180deg, transparent var(--fgl, 68.5%), #000 calc(var(--fgl, 68.5%) + 26px));
  z-index: 9;
  pointer-events: none;
}
.bg-veil {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(180deg, rgba(226, 243, 255, 0.72) 0%, rgba(226, 243, 255, 0.24) 18%, rgba(226, 243, 255, 0) 40%),
    radial-gradient(120% 90% at 60% 40%, rgba(255, 255, 255, 0.18) 0%, rgba(180, 214, 238, 0.42) 100%);
}

/* 顶栏 */
.top {
  position: absolute;
  left: 0; right: 0; top: 0;
  height: 62px;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 0 18px;
  background: linear-gradient(180deg, rgba(240, 249, 255, 0.94), rgba(240, 249, 255, 0.62));
  box-shadow: 0 2px 14px rgba(20, 60, 100, 0.12);
  z-index: 20;
}
.back {
  width: 42px; height: 42px;
  border-radius: 50%;
  border: 0;
  background: #2f6fa8;
  color: #fff;
  display: grid; place-items: center;
  cursor: pointer;
  box-shadow: 0 3px 10px rgba(20, 60, 100, 0.3);
}
.back svg { width: 22px; height: 22px; }
.top h1 {
  margin: 0;
  font-size: 21px;
  font-weight: 800;
  letter-spacing: 0.04em;
  color: #23405e;
}
.top h1 em {
  display: inline-grid;
  place-items: center;
  width: 17px; height: 17px;
  margin-left: 7px;
  border-radius: 50%;
  background: #2f6fa8;
  color: #fff;
  font-size: 11px;
  font-style: normal;
  vertical-align: 4px;
}
.res { display: flex; gap: 10px; margin-left: auto; }
.pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 30px;
  padding: 0 10px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.9);
  font-size: 13px;
  font-weight: 700;
  color: #2a3d55;
  box-shadow: 0 1px 4px rgba(30, 70, 110, 0.12);
}
.pill em { font-style: normal; color: #8798ad; font-weight: 600; }
.pill b { color: #4f9bea; font-size: 15px; }
.pill i { width: 15px; height: 15px; border-radius: 4px; display: inline-block; }
.pill i.ap { background: linear-gradient(160deg, #7fd2a0, #3f9e6c); }
.pill i.cr { background: linear-gradient(160deg, #ffd76b, #e2a62b); }
.pill i.gm { background: linear-gradient(160deg, #9ed8ff, #4f9bea); }
.topr { display: flex; gap: 8px; }
.tbtn {
  width: 34px; height: 34px;
  border-radius: 8px;
  border: 1px solid rgba(120, 165, 205, 0.34);
  background: rgba(255, 255, 255, 0.86);
  color: #3f6f9c;
  font-size: 15px;
  cursor: pointer;
}

/* 左侧分类 */
.cats {
  position: absolute;
  left: 0; top: 62px; bottom: 0;
  width: 212px;
  padding: 12px 10px 20px;
  z-index: 12;
  display: flex;
  flex-direction: column;
  gap: 12px;
  pointer-events: none;
}
.cats > * { pointer-events: auto; }
.cat-head {
  margin: 0 0 4px 2px;
  width: fit-content;
  padding: 8px 20px 8px 14px;
  background: #23405e;
  clip-path: polygon(0 0, 100% 0, calc(100% - 14px) 100%, 0 100%);
  color: #ffd76b;
  font-size: 14.5px;
  font-weight: 800;
  letter-spacing: 0.06em;
}
.cat {
  display: flex;
  align-items: center;
  gap: 10px;
  height: 46px;
  padding: 0 12px;
  border: 0;
  background: rgba(255, 255, 255, 0.94);
  color: #2c4763;
  font-size: 14.5px;
  font-weight: 700;
  text-align: left;
  cursor: pointer;
  clip-path: polygon(0 0, 100% 0, calc(100% - 12px) 100%, 0 100%);
  box-shadow: 0 2px 8px rgba(30, 70, 110, 0.12);
  transition: transform 0.16s, background 0.16s, color 0.16s;
}
.cat:hover { transform: translateX(3px); }
.cat.on {
  background: #23405e;
  color: #ffd76b;
  box-shadow: 0 4px 14px rgba(20, 50, 85, 0.34);
}
.ci {
  width: 26px; height: 26px;
  flex: none;
  object-fit: contain;
  filter: drop-shadow(0 1px 2px rgba(30, 70, 110, 0.18));
}

/* 中间立绘 */
.stage {
  position: absolute;
  cursor: pointer;
  background: transparent;
  left: 150px;
  top: 0;
  bottom: 0;
  width: min(640px, 43vw);
  z-index: 8;
  overflow: hidden;
  pointer-events: auto;
}
.ground {
  position: absolute;
  left: 150px;
  top: calc(var(--fgl, 69%) - 34px);
  width: min(640px, 43vw);
  height: 66px;
  z-index: 9;
  pointer-events: none;
  background: radial-gradient(58% 50% at 50% 30%, rgba(18, 44, 78, 0.34) 0%, rgba(18, 44, 78, 0.12) 55%, transparent 78%);
  filter: blur(7px);
}
.char {
  position: absolute;
  inset: 0;
  background: transparent;
}
.stage canvas {
  display: block;
  background: transparent !important;
}
.say {
  position: absolute;
  left: 30px;
  bottom: 22%;
  width: min(268px, 22vw);
  z-index: 11;
  padding: 10px 18px 12px;
  background: rgba(255, 255, 255, 0.96);
  border-radius: 16px;
  box-shadow: 0 8px 22px rgba(30, 70, 110, 0.18);
  text-align: center;
}
.say::after {
  content: '';
  position: absolute;
  right: -7px;
  top: 50%;
  width: 15px; height: 15px;
  margin-top: -7px;
  background: inherit;
  transform: rotate(45deg);
  border-radius: 3px;
}
.say span { display: block; font-size: 11px; color: #8fa0b3; font-weight: 700; }
.say p { margin: 3px 0 0; font-size: 14.5px; font-weight: 700; color: #2b3444; }

/* 右侧面板 */
.panel {
  position: absolute;
  left: calc(212px + min(430px, 34vw));
  right: 0;
  top: 62px;
  bottom: 72px;
  padding: 14px 22px 10px 8px;
  z-index: 10;
  overflow-y: auto;
  scrollbar-width: thin;
}
.panel::-webkit-scrollbar { width: 6px; }
.panel::-webkit-scrollbar-thumb { background: rgba(90, 140, 185, 0.4); border-radius: 3px; }

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
  gap: 14px;
  align-items: stretch;
}
.card {
  background: rgba(255, 255, 255, 0.95);
  border: 1px solid rgba(190, 218, 240, 0.9);
  border-radius: 12px;
  padding: 10px 10px 0;
  box-shadow: 0 4px 14px rgba(30, 70, 110, 0.12);
  display: flex;
  flex-direction: column;
  height: 100%;
}
.card h3 {
  min-height: 38px;
  margin: 0 0 8px;
  font-size: 13.5px;
  line-height: 1.4;
  color: #1f4a78;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.card h3 em {
  font-style: normal;
  font-size: 12px;
  color: #6b8aa8;
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.card .attrs {
  flex: 1;
  min-height: 46px;
  margin: 8px 0 10px;
  padding: 0;
  list-style: none;
  font-size: 11.5px;
  color: #6b8aa8;
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.card .attrs li {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.card h3 {
  margin: 0 0 8px;
  font-size: 13px;
  font-weight: 800;
  color: #2a3d55;
  line-height: 1.35;
  min-height: 36px;
}
.card h3 em {
  font-style: normal;
  font-weight: 600;
  font-size: 11.5px;
  color: #7c8ea4;
  word-break: break-all;
}
.art {
  position: relative;
  height: 116px;
  border-radius: 8px;
  background:
    radial-gradient(120% 100% at 50% 0%, color-mix(in srgb, var(--tone) 26%, #fff) 0%, #f2f8fd 70%, #e6f1fa 100%);
  display: grid;
  place-items: center;
  overflow: hidden;
}
.sheet {
  position: absolute;
  inset: 8px 8px 10px;
  display: grid;
  place-items: center;
  border-radius: 6px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.92), rgba(246, 251, 255, 0.7));
  box-shadow: inset 0 0 0 1px rgba(160, 195, 225, 0.5);
}
.sheet .itm {
  width: auto;
  height: auto;
  max-width: 74%;
  max-height: 84%;
  object-fit: contain;
  display: block;
  filter: drop-shadow(0 3px 7px rgba(30, 60, 95, 0.22));
}
.sheet i {
  position: absolute;
  left: 10px;
  right: 10px;
  height: 3px;
  border-radius: 2px;
  background: rgba(120, 150, 180, 0.28);
}
.sheet i:nth-child(2) { bottom: 22px; }
.sheet i:nth-child(3) { bottom: 14px; right: 26px; }
.sheet i:nth-child(4) { bottom: 6px; right: 34px; }
.qty {
  position: absolute;
  right: 7px; top: 6px;
  padding: 1px 6px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.86);
  box-shadow: 0 1px 3px rgba(30, 70, 110, 0.16);
  font-size: 11px;
  font-weight: 800;
  color: var(--tone);
  letter-spacing: 0.06em;
}
.attrs {
  list-style: none;
  margin: 8px 0 8px;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 4px 8px;
}
.attrs li {
  font-size: 11px;
  color: #6c8098;
  background: #eef5fb;
  border-radius: 5px;
  padding: 2px 6px;
}
.buy {
  margin: 0 -10px;
  border-top: 1px solid rgba(190, 218, 240, 0.9);
  border-radius: 0 0 12px 12px;
  background: linear-gradient(180deg, #63b6f2, #3f92da);
  display: flex;
  align-items: center;
  padding: 0 10px;
  height: 40px;
  gap: 8px;
}
.buy.free { background: linear-gradient(180deg, #67c79a, #3fa46a); }
.buy .price {
  font-size: 13.5px;
  font-weight: 800;
  color: #fff;
  letter-spacing: 0.02em;
}
.buy button {
  margin-left: auto;
  height: 26px;
  padding: 0 14px;
  border: 1px solid rgba(255, 255, 255, 0.72);
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.2);
  color: #fff;
  font-size: 12.5px;
  font-weight: 700;
  cursor: pointer;
}
.buy button:hover { background: rgba(255, 255, 255, 0.34); }
.empty { color: #5b7791; font-size: 13px; }

/* 通用块 */
.blocks { display: grid; gap: 14px; grid-template-columns: 1fr 1fr; align-content: start; }
.block {
  background: rgba(255, 255, 255, 0.95);
  border: 1px solid rgba(190, 218, 240, 0.9);
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 4px 14px rgba(30, 70, 110, 0.12);
}
.block.wide { grid-column: 1 / -1; }
.block h4 {
  margin: 0;
  padding: 9px 14px;
  background: linear-gradient(180deg, #dff0fb, #d3e8f8);
  border-bottom: 1px solid #cfe3f0;
  display: flex;
  align-items: center;
  gap: 8px;
}
.block h4 span {
  font-size: 13.5px;
  font-weight: 800;
  letter-spacing: 0.06em;
  color: #326fa0;
}
.block h4 img {
  width: 18px; height: 18px;
  object-fit: contain;
}
.block .pbody { padding: 12px 16px 14px; }
.block h4_x {
  margin: 0;
  padding: 9px 16px;
  background: linear-gradient(180deg, #e3f2fc, #d3eafa);
  border-bottom: 1px solid rgba(190, 218, 240, 0.9);
  font-size: 13.5px;
  font-weight: 800;
  color: #2f6fa8;
}
.pbody { padding: 12px 16px 14px; }
.big { display: flex; align-items: baseline; gap: 8px; }
.big b { font-size: 34px; font-weight: 900; color: #23405e; letter-spacing: -0.01em; }
.big em { font-style: normal; font-size: 13px; color: #7c8ea4; font-weight: 700; }
.hint { margin: 8px 0 0; font-size: 12px; color: #7c8ea4; }
.kvs { display: grid; gap: 8px; }
.kvs > div { display: flex; justify-content: space-between; font-size: 13px; }
.kvs dt { color: #6c8098; margin: 0; }
.kvs dd { margin: 0; font-weight: 700; color: #2a3d55; }

.row { display: flex; align-items: center; gap: 10px; margin-bottom: 9px; }
.rn { width: 92px; font-size: 12.5px; color: #40597a; font-weight: 700; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.bar { flex: 1; height: 8px; border-radius: 4px; background: #e6f1fa; overflow: hidden; }
.bar i { display: block; height: 100%; border-radius: 4px; background: linear-gradient(90deg, #6fbdf0, #3f92da); }
.rv { width: 54px; text-align: right; font-size: 12px; color: #6c8098; }

.chart { display: flex; align-items: flex-end; gap: 10px; height: 190px; padding-top: 10px; }
.col { flex: 1; display: flex; flex-direction: column; align-items: center; height: 100%; }
.col .cv { font-size: 10.5px; color: #7c8ea4; }
.col i {
  display: block;
  width: 62%;
  min-height: 6px;
  margin: 4px 0 6px;
  border-radius: 5px 5px 2px 2px;
  background: linear-gradient(180deg, #7cc6f5, #3f92da);
}
.col em { font-style: normal; font-size: 11px; color: #6c8098; }

.srow { display: flex; align-items: center; gap: 10px; padding: 7px 0; border-bottom: 1px dashed rgba(190, 218, 240, 0.9); }
.srow:last-child { border-bottom: 0; }
.dot { width: 8px; height: 8px; border-radius: 50%; flex: none; }
.dot.ok { background: #4cbd85; box-shadow: 0 0 0 3px rgba(76, 189, 133, 0.18); }
.dot.bad { background: #e8556d; box-shadow: 0 0 0 3px rgba(232, 85, 109, 0.18); }
.sn { font-size: 13px; font-weight: 700; color: #2a3d55; }
.sn.mono { font-family: ui-monospace, Consolas, monospace; font-size: 12px; color: #3f6f9c; }
.sv { margin-left: auto; font-size: 12.5px; font-weight: 700; color: #3f6f9c; }
.sv.sm { font-weight: 500; color: #7c8ea4; font-size: 12px; }
.sx { font-size: 11.5px; color: #8fa0b3; }

/* 底部 */
.foot {
  position: absolute;
  right: 22px;
  bottom: 14px;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 10px 8px 16px;
  background: rgba(255, 255, 255, 0.94);
  border-radius: 10px;
  box-shadow: 0 6px 18px rgba(30, 70, 110, 0.16);
  z-index: 22;
}
.clock { font-size: 12.5px; color: #3f6f9c; font-weight: 700; }
.clock b { color: #23405e; }
.refresh {
  height: 30px;
  padding: 0 14px;
  border: 1px solid rgba(90, 150, 200, 0.4);
  border-radius: 7px;
  background: linear-gradient(180deg, #ffffff, #eaf4fc);
  color: #2f6fa8;
  font-size: 12.5px;
  font-weight: 800;
  cursor: pointer;
}
.refresh:hover { background: #fff; }

/* 弹层 */
.tipmask {
  position: absolute;
  inset: 0;
  background: rgba(10, 30, 52, 0.42);
  backdrop-filter: blur(3px);
  display: grid;
  place-items: center;
  z-index: 40;
}
.tipbox {
  width: min(440px, 84vw);
  background: #fff;
  border-radius: 14px;
  padding: 18px 20px 14px;
  box-shadow: 0 20px 50px rgba(10, 30, 52, 0.34);
}
.tipbox pre {
  margin: 0 0 14px;
  font-family: ui-monospace, Consolas, monospace;
  font-size: 12.5px;
  line-height: 1.7;
  color: #2a3d55;
  white-space: pre-wrap;
}
.tipbox button {
  width: 100%;
  height: 38px;
  border: 0;
  border-radius: 8px;
  background: linear-gradient(180deg, #63b6f2, #3f92da);
  color: #fff;
  font-size: 14px;
  font-weight: 800;
  cursor: pointer;
}

.loading {
  position: absolute;
  left: 50%; bottom: 16px;
  transform: translateX(-50%);
  padding: 6px 16px;
  border-radius: 999px;
  background: rgba(20, 50, 85, 0.72);
  color: #fff;
  font-size: 12px;
  z-index: 30;
}
</style>
