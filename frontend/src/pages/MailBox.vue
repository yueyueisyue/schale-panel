<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch, onBeforeUnmount } from 'vue'
import { panel } from '@/store/panel'

const emit = defineEmits<{ (e: 'close'): void }>()

interface Person {
  id: string
  name: string
  phrases: string[]
  msgCount: number
  favor: number
  intimacy: number
  emotions: Record<string, number>
  dominant: string
  dominantLabel: string
  dominantScore: number
  attitude: string
  relationship: string
  lastAttitude: string
  total: number
  positive: number
  negative: number
  streak: number
  lastDay: string
  deep: boolean
  isOwner: boolean
}

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

const AVATAR_COLORS = [
  '#9ec9e8', '#f0b1be', '#a8d8bd', '#f2cd94', '#c3b0e6',
  '#9ed6dd', '#e8bc9c', '#b8c6e0', '#e0a8b8', '#bcd89a',
]

const people = ref<Person[]>([])
const loading = ref(true)
const activeId = ref('')
const tab = ref<'members' | 'unread'>(
  (typeof location !== 'undefined' && new URLSearchParams(location.search).get('mailtab') === 'unread')
    ? 'unread' : 'members')
const thought = ref('')
const thinking = ref(false)
const thoughtFor = ref('')
const detailOpen = ref(true)

/** 三个面板默认折叠，点标题栏或放大镜展开（还原游戏效果） */
const openPanels = ref<Record<string, boolean>>({ imp: true, emo: true, act: true })

// ── 排行：好感度 / 时间 / 群组，可切升降序 ──
const SORTS = [
  { key: 'favor', label: '好感度' },
  { key: 'time', label: '时间' },
  { key: 'group', label: '群组' },
] as const
const sortBy = ref<'favor' | 'time' | 'group'>('favor')
const sortDesc = ref(true)
const sortMenu = ref(false)

function pickSort(k: 'favor' | 'time' | 'group') {
  sortBy.value = k
  sortMenu.value = false
}

const sortedPeople = computed(() => {
  const arr = [...people.value]
  const dir = sortDesc.value ? -1 : 1
  arr.sort((a: any, b: any) => {
    if (sortBy.value === 'time') {
      const ta = Number(a.lastTs || 0)
      const tb = Number(b.lastTs || 0)
      return (ta - tb) * dir
    }
    if (sortBy.value === 'group') {
      const ga = String(a.group || '')
      const gb = String(b.group || '')
      if (ga !== gb) return ga.localeCompare(gb, 'zh') * dir
      return (Number(a.favor || 0) - Number(b.favor || 0)) * dir
    }
    const fa = Number(a.favor || 0)
    const fb = Number(b.favor || 0)
    if (fa !== fb) return (fa - fb) * dir
    return (Number(a.intimacy || 0) - Number(b.intimacy || 0)) * dir
  })
  return arr
})
function togglePanel(k: string) {
  openPanels.value = { ...openPanels.value, [k]: !openPanels.value[k] }
}
// 调试用：?panel=imp|emo|act 直接展开某个面板
if (typeof location !== 'undefined') {
  const p = new URLSearchParams(location.search).get('panel')
  if (p && p in openPanels.value) openPanels.value = { ...openPanels.value, [p]: true }
}

const active = computed(() => people.value.find((p) => p.id === activeId.value) || null)

const emoBars = computed(() => {
  const p = active.value
  if (!p) return []
  return EMO.map((e) => ({
    ...e,
    value: Math.max(0, Math.min(100, Number(p.emotions?.[e.key] ?? 0))),
  }))
})

function avatarColor(id: string): string {
  let h = 0
  for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) >>> 0
  return AVATAR_COLORS[h % AVATAR_COLORS.length]
}

function initial(name: string): string {
  if (!name) return '?'
  const m = name.match(/[\u4e00-\u9fa5]/)
  return m ? m[0] : name.slice(0, 1).toUpperCase()
}

function shortLine(p: Person): string {
  const ph = p.phrases?.filter(Boolean) || []
  if (ph.length) return ph[0]
  if (p.attitude) return p.attitude
  if (p.isOwner) return `好感 ${p.favor} · 聊过 ${p.total} 次`
  return `聊过 ${p.total} 次`
}

// ── 专属对话 ────────────────────────────────────────────
const speakBusy = ref(false)
const atOn = ref(false)
const chatTarget = ref<any>(null)
const chatKey = computed(() => String(active.value?.avatarId || active.value?.id || ''))
// 历史往来 + 面板内的来回，按时间戳合成一条时间线（旧 → 新）
const mergedMsgs = computed(() => {
  type Row = { ts: number; role: string; text: string; split?: string; cont?: boolean }
  const rows: Row[] = []
  for (const blk of ctxBlocks.value) {
    for (const it of blk.items) rows.push({ ts: Number(it.ts || 0), role: it.role, text: it.text })
  }
  for (const t of threads.value) {
    if (t.role === 'aside') continue
    rows.push({ ts: Number(t.ts || 0), role: t.role === 'them' ? 'them' : 'me', text: t.text })
  }
  rows.sort((a, b) => a.ts - b.ts)
  // 面板里的记录和 bot 记忆里的同一条消息会各来一份，按「同人同话」去重
  const norm = (t: string) => t.replace(/\s+/g, '').slice(0, 80)
  const dedup: Row[] = []
  for (const r of rows) {
    const prev = dedup[dedup.length - 1]
    if (prev && prev.role === r.role && norm(prev.text) === norm(r.text) && Math.abs((r.ts || 0) - (prev.ts || 0)) < 180) {
      prev.ts = Math.max(prev.ts || 0, r.ts || 0)
      continue
    }
    dedup.push({ ...r })
  }
  rows.length = 0
  rows.push(...dedup)
  const out: Row[] = []
  let last = 0
  let prevRole = ''
  const p2 = (n: number) => String(n).padStart(2, '0')
  for (const r of rows) {
    const split = Boolean(r.ts && (!last || r.ts - last > 1800))
    if (split) {
      const d = new Date(r.ts * 1000)
      out.push({ ts: r.ts, role: 'split', text: '', split: `${p2(d.getMonth() + 1)}-${p2(d.getDate())} ${p2(d.getHours())}:${p2(d.getMinutes())}` })
      prevRole = ''
    }
    // 同一人紧接着发的：标成承接句，模板里省掉头像和名字
    out.push({ ...r, cont: !split && prevRole === r.role })
    prevRole = r.role
    last = r.ts || last
  }
  return out
})

const ctxBlocks = ref<Array<{ day: string; items: Array<{ role: string; text: string; ts?: number }> }>>([])
const threads = ref<Array<{ role: string; text: string; ts?: number }>>([])
const asides = ref<Array<{ text: string; ts?: number }>>([])
const draft = ref('')
const asideText = ref('')
const asideOn = ref(false)
const sending = ref(false)
const chatScroll = ref<HTMLElement | null>(null)

function scrollChat() {
  requestAnimationFrame(() => {
    const el = chatScroll.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

let chatTimer: number | undefined

watch(active, () => {
  threads.value = []
  void loadChat()
  if (chatTimer) window.clearInterval(chatTimer)
  // 每 6 秒静默拉一次，bot 在 QQ 里的新消息会自动出现
  chatTimer = window.setInterval(() => {
    if (active.value && !sending.value) void loadChat()
  }, 6000)
}, { immediate: false })

onBeforeUnmount(() => {
  if (chatTimer) window.clearInterval(chatTimer)
})

async function loadChat() {
  if (!active.value) return
  const pid = chatKey.value
  if (!pid) return
  try {
    const r = await fetch(`/api/chat/${pid}`, { headers: { Authorization: 'Bearer ' + (await ensureToken()) } })
    const j = await r.json()
    threads.value = Array.isArray(j?.threads) ? j.threads : []
    asides.value = Array.isArray(j?.asides) ? j.asides : []
    ctxBlocks.value = Array.isArray(j?.context) ? j.context : []
    scrollChat()
  } catch {
    threads.value = []
    ctxBlocks.value = []
  }
}

async function send() {
  const text = draft.value.trim()
  if (!text || sending.value) return
  sending.value = true
  try {
    const r = await fetch(`/api/chat/${chatKey.value}/send`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${await ensureToken()}` },
      body: JSON.stringify({ text, at: atOn.value, group_id: active.value?.group_id || null }),
    })
    const j = await r.json()
    if (j && j.ok) {
      draft.value = ''
      if (j.thread) threads.value = j.thread.threads || []
    } else {
      threads.value.push({ role: 'aside', text: (j && j.error) || '发送失败' })
    }
  } catch (e) {
    threads.value.push({ role: 'aside', text: '发送失败：' + String(e) })
  } finally {
    sending.value = false
  }
}

async function speak() {
  if (speakBusy.value) return
  speakBusy.value = true
  try {
    const r = await fetch(`/api/chat/${chatKey.value}/speak`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${await ensureToken()}` },
      body: JSON.stringify({ at: atOn.value, group_id: active.value?.group_id || null }),
    })
    const j = await r.json()
    if (j && j.thread) threads.value = j.thread.threads || []
    if (!j || !j.ok) {
      threads.value.push({ role: 'aside', text: (j && j.error) || '她这次没想好要说什么' })
    }
  } catch (e) {
    threads.value.push({ role: 'aside', text: '发起失败：' + String(e) })
  } finally {
    speakBusy.value = false
  }
}

async function ensureToken(force = false): Promise<string> {
  let t = force ? '' : (localStorage.getItem('schale_token') || '')
  if (t) return t
  try {
    const r = await fetch('/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password: 'CHANGE_ME' }),
    })
    if (r.ok) {
      const j = await r.json()
      if (j?.token) {
        localStorage.setItem('schale_token', j.token)
        t = j.token
      }
    }
  } catch {
    /* ignore */
  }
  return t
}

async function load() {
  loading.value = true
  const t = await ensureToken()
  try {
    let r = await fetch('/api/mail', { headers: { Authorization: `Bearer ${t}` } })
    if (r.status === 401) {
      localStorage.removeItem('schale_token')
      const t2 = await ensureToken(true)
      r = await fetch('/api/mail', { headers: { Authorization: `Bearer ${t2}` } })
    }
    if (r.ok) {
      const j = await r.json()
      if (j?.ok && Array.isArray(j.people)) {
        people.value = j.people
        if (!activeId.value && people.value.length) {
          activeId.value = people.value[0].id
          think(activeId.value)
        }
      }
    }
  } catch {
    /* ignore */
  }
  loading.value = false
  void loadChat()
}

async function think(pid: string) {
  if (!pid) return
  if (thoughtFor.value === pid && thought.value) return
  thinking.value = true
  thought.value = ''
  thoughtFor.value = pid
  const t = await ensureToken()
  try {
    const r = await fetch('/api/mail/think', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${t}` },
      body: JSON.stringify({ id: pid }),
    })
    const j = await r.json()
    if (thoughtFor.value === pid) thought.value = j?.text || j?.error || '……'
  } catch {
    if (thoughtFor.value === pid) thought.value = '……（连不上）'
  } finally {
    if (thoughtFor.value === pid) thinking.value = false
  }
}

function openPerson(p: Person) {
  threads.value = []
  window.setTimeout(() => { void loadChat() }, 30)
  activeId.value = p.id
  detailOpen.value = true
  think(p.id)
}

function onKey(e: KeyboardEvent) {
  if (e.key !== 'Escape') return
  if (detailOpen.value) detailOpen.value = false
  else emit('close')
}

onMounted(() => {
  load()
  window.addEventListener('keydown', onKey)
})
onUnmounted(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <div class="mask" @click.self="emit('close')">
    <section class="box" @click.stop>
      <!-- 粉色标题栏 -->
      <header class="bar">
        <div class="brand">
          <svg class="ic" viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
            <path
              d="M3.2 6.6c0-.9.7-1.6 1.6-1.6h14.4c.9 0 1.6.7 1.6 1.6v10.8c0 .9-.7 1.6-1.6 1.6H4.8c-.9 0-1.6-.7-1.6-1.6V6.6z"
              fill="none"
              stroke="currentColor"
              stroke-width="1.9"
            />
            <path
              d="M3.6 7.2 12 13l8.4-5.8"
              fill="none"
              stroke="currentColor"
              stroke-width="1.9"
              stroke-linecap="round"
            />
          </svg>
          <h2>桃信</h2>
          <span class="q">?</span>
        </div>
        <button class="close" @click="emit('close')" aria-label="关闭">
          <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
            <path
              d="M6 6l12 12M18 6L6 18"
              stroke="currentColor"
              stroke-width="2.2"
              stroke-linecap="round"
            />
          </svg>
        </button>
      </header>

      <div class="body">
        <!-- 左侧窄栏：两个白色线性图标 -->
        <nav class="rail">
          <button class="rt" :class="{ on: tab === 'members' }" @click="tab = 'members'">
            <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
              <circle cx="12" cy="8" r="4" fill="currentColor" />
              <path d="M4 21c0-4.4 3.6-7 8-7s8 2.6 8 7z" fill="currentColor" />
            </svg>
          </button>
          <button class="rt" :class="{ on: tab === 'unread' }" @click="tab = 'unread'">
            <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
              <path
                d="M4 5h16v11H9l-5 4z"
                fill="currentColor"
              />
            </svg>
            <i v-if="people.length" class="dot">{{ people.length }}</i>
          </button>
        </nav>

        <!-- 列表 -->
        <div class="list">
          <div class="lhead">
            <h3>{{ tab === 'members' ? `成员 (${people.length})` : `未读信息 (${people.length})` }}</h3>
            <div class="btns">
              <div class="pbtn-wrap">
                <button class="pbtn" @click="sortMenu = !sortMenu">
                  {{ SORTS.find(x => x.key === sortBy)?.label }} ▾
                </button>
                <div v-if="sortMenu" class="sort-menu">
                  <button
                    v-for="o in SORTS"
                    :key="o.key"
                    class="sort-opt"
                    :class="{ on: sortBy === o.key }"
                    @click="pickSort(o.key)"
                  >
                    {{ o.label }}
                  </button>
                </div>
              </div>
              <button class="pbtn slim" :title="sortDesc ? '从大到小' : '从小到大'" @click="sortDesc = !sortDesc">
                <svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true">
                  <path d="M4 6.5h11M4 12h8M4 17.5h5" stroke="currentColor" stroke-width="2" stroke-linecap="round" fill="none" />
                  <path v-if="sortDesc" d="M19 8v9m0 0l-2.6-2.6M19 17l2.6-2.6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none" />
                  <path v-else d="M19 17V8m0 0l-2.6 2.6M19 8l2.6 2.6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none" />
                </svg>
              </button>
            </div>
          </div>

          <div v-if="loading" class="tip">读取中…</div>
          <div v-else-if="!people.length" class="tip">还没有认识的人。</div>

          <ul v-else class="rows">
            <li v-for="p in sortedPeople" :key="p.id">
              <button class="row" :class="{ on: p.id === activeId && detailOpen }" @click="openPerson(p)">
                <span class="ava" :style="{ background: avatarColor(p.id) }">
                  <img :src="`/api/avatar/${p.avatarId || p.id}`" :alt="p.name" loading="lazy" @error="($event.target as HTMLImageElement).style.display = 'none'" />
                  <b>{{ initial(p.name) }}</b>
                </span>
                <span class="col">
                  <span class="nm">{{ p.name }}</span>
                  <span class="ln">{{ shortLine(p) }}</span>
                </span>
                <span class="hf">
                  <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true">
                    <path
                      d="M12 21s-7.5-4.7-9.4-9A5.3 5.3 0 0 1 12 6.2 5.3 5.3 0 0 1 21.4 12C19.5 16.3 12 21 12 21z"
                      fill="currentColor"
                    />
                  </svg>
                  <em>{{ p.favor }}</em>
                </span>
              </button>
            </li>
          </ul>
        </div>

        <!-- 详情（图2 那种） -->
        <div class="detail" :class="{ show: detailOpen }">
          <template v-if="active">
            <button class="back" @click="detailOpen = false">
              <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
                <path d="M15 5l-7 7 7 7" stroke="currentColor" stroke-width="2.2" fill="none" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
              返回
            </button>

            <div class="dtop">
              <span class="dava" :style="{ background: avatarColor(active.id) }">
                <img :src="`/api/avatar/${active.avatarId || active.id}`" :alt="active.name" @error="($event.target as HTMLImageElement).style.display = 'none'" />
                <b>{{ initial(active.name) }}</b>
                <i class="dheart"><img src="/img/deco/heart.png" alt="" />{{ active.favor }}</i>
              </span>
              <h4>{{ active.name }}</h4>
              <p class="dline">{{ active.line || active.attitude || active.relationship || '还没有说过话' }}</p>
              <span class="dchip" v-if="active.total">💬 聊过 {{ active.total }} 次</span>
            </div>

            <!-- 成员页：印象 / 情绪 / 互动 -->
            <div v-if="tab === 'members'" class="panes">
              <div class="panel">
                <h5><span>印象</span></h5>
                <div class="pbody">
                  <p v-if="active.attitude"><b>态度</b>{{ active.attitude }}</p>
                  <p v-if="active.relationship"><b>关系</b>{{ active.relationship }}</p>
                  <p v-if="!active.attitude && !active.relationship" class="dim">还没有形成明确的印象。</p>
                </div>
              </div>

              <div class="panel">
                <h5><span>情绪</span></h5>
                <div class="pbody emos">
                  <div v-for="e in emoBars" :key="e.key" class="erow">
                    <span class="el">{{ e.label }}</span>
                    <span class="eb"><i :style="{ width: e.value + '%', background: e.color }"></i></span>
                    <span class="ev">{{ e.value }}</span>
                  </div>
                </div>
              </div>

              <div class="panel">
                <h5><span>互动</span></h5>
                <div class="pbody">
                  <div class="kvs">
                    <span><b>{{ active.total }}</b>总次数</span>
                    <span><b class="ok">{{ active.positive }}</b>正面</span>
                    <span><b class="bad">{{ active.negative }}</b>负面</span>
                    <span><b>{{ active.msgCount || 0 }}</b>群里发言</span>
                  </div>
                  <p v-if="active.lastDay" class="dim"><b>最后</b>{{ active.lastDay }}</p>
                </div>
              </div>
            </div>

            <!-- 未读页：专属对话 -->
            <div v-else class="chatbox">
              <div ref="chatScroll" class="msgs">
                <p v-if="!mergedMsgs.length" class="empty">
                  还没有和 {{ active.name }} 的对话。右边是你以 {{ panel.characterName }} 的身份发的。
                </p>

                <template v-for="(m, i) in mergedMsgs" :key="'m' + i">
                  <div v-if="m.role === 'split'" class="daysplit"><span>{{ m.split }}</span></div>
                  <div v-else-if="m.role === 'me'" class="msg me" :class="{ cont: m.cont }">
                    <div class="mcol right">
                      <span v-if="!m.cont" class="mwho me">{{ panel.characterName }}</span>
                      <p class="bub mine">{{ m.text }}</p>
                    </div>
                    <span v-if="!m.cont" class="mava mika">弥</span>
                  </div>
                  <div v-else class="msg them" :class="{ cont: m.cont }">
                    <span v-if="!m.cont" class="mava" :style="{ background: avatarColor(active.id) }">
                      <img :src="`/api/avatar/${active.avatarId || active.id}`" alt="" @error="($event.target as HTMLImageElement).style.display = 'none'" />
                      <b>{{ initial(active.name) }}</b>
                    </span>
                    <div class="mcol">
                      <span v-if="!m.cont" class="mwho">{{ active.name }}<i v-if="active.groupName" class="gmark">{{ active.groupName }}</i></span>
                      <p class="bub">{{ m.text }}</p>
                    </div>
                  </div>
                </template>

                <div v-if="sending" class="msg them">
                  <span class="mava" :style="{ background: avatarColor(active.id) }"><b>{{ initial(active.name) }}</b></span>
                  <div class="mcol">
                    <span class="mwho">{{ active.name }}<i v-if="active.groupName" class="gmark">{{ active.groupName }}</i></span>
                    <p class="bub typing"><i></i><i></i><i></i></p>
                  </div>
                </div>
              </div>

              <div class="composer">
                <div v-if="asideOn" class="asidebar">
                  <span>旁白</span>
                  <input v-model="asideText" placeholder="只给 bot 看的心里话，不会发给对方" @keydown.enter.prevent="send()" />
                </div>
                <div class="cline">
                  <button
                    class="atbtn"
                    :class="{ on: atOn }"
                    :title="atOn ? '群里会 @ 他' : '不 @，句首带名字'"
                    @click="atOn = !atOn"
                  >@</button>
                  <button
                    class="speakbtn"
                    :class="{ busy: speakBusy }"
                    :disabled="speakBusy"
                    :title="speakBusy ? '她正在想……' : '让她自己说一句'"
                    @click="speak"
                  >
                    <img
                      :src="speakBusy ? '/img/ui/heart-typing.png' : '/img/ui/heart-idle.png'"
                      alt="让她自己说"
                    />
                  </button>
                  <button class="abtn" :class="{ on: asideOn }" title="插话（旁白）" @click="asideOn = !asideOn">
                    <svg viewBox="0 0 24 24" width="17" height="17">
                      <path d="M4 6h16M4 12h10M4 18h7" stroke="currentColor" stroke-width="2" stroke-linecap="round" fill="none" />
                    </svg>
                  </button>
                  <input
                    v-model="draft"
                    class="dinput"
                    :placeholder="`发给 ${active.name}……`"
                    @keydown.enter.prevent="send()"
                  />
                  <button class="sbtn" :disabled="sending || (!draft.trim() && !asideText.trim())" @click="send()">
                    发送
                  </button>
                </div>
              </div>
            </div>

          </template>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.mask {
  position: fixed;
  inset: 0;
  z-index: 90;
  background: rgba(6, 16, 30, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  animation: fade-in 0.2s var(--ease);
}
.box {
  width: min(1080px, 94vw);
  height: min(720px, 88vh);
  background: #f3f6f6;
  border-radius: 10px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-shadow: 0 24px 64px rgba(2, 10, 24, 0.44);
  animation: pop 0.24s var(--ease-out);
}
@keyframes pop {
  from { opacity: 0; transform: translateY(12px) scale(0.99); }
}

/* 标题栏 */
.bar {
  height: 54px;
  flex: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 10px 0 20px;
  background: linear-gradient(96deg, #fb92a5 0%, #fc9cae 55%, #fb92a5 100%);
  color: #fff;
}
.brand {
  display: flex;
  align-items: center;
  gap: 9px;
}
.brand .ic { filter: drop-shadow(0 1px 2px rgba(150, 45, 75, 0.26)); }
.brand h2 {
  font-size: 21px;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-shadow: 0 1px 3px rgba(150, 45, 75, 0.24);
}
.q {
  width: 18px;
  height: 18px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.9);
  color: #ec7f9c;
  font-size: 12px;
  font-weight: 700;
  display: grid;
  place-items: center;
}
.close {
  width: 38px;
  height: 38px;
  border: 0;
  background: transparent;
  color: #fff;
  cursor: pointer;
  border-radius: 8px;
  display: grid;
  place-items: center;
  transition: background 0.15s;
}
.close:hover { background: rgba(255, 255, 255, 0.2); }

/* 主体 */
.body { flex: 1; display: flex; min-height: 0; }

/* 左侧窄栏 */
.rail {
  width: 66px;
  flex: none;
  background: #4c5b6f;
  display: flex;
  flex-direction: column;
  padding-top: 8px;
}
.rt {
  position: relative;
  height: 54px;
  border: 0;
  background: transparent;
  color: #e6ecf4;
  cursor: pointer;
  display: grid;
  place-items: center;
  transition: background 0.15s;
}
.rt:hover { background: rgba(255, 255, 255, 0.1); }
.rt.on { background: #f3f6f6; color: #67788d; }
.dot {
  position: absolute;
  right: 10px;
  top: 8px;
  min-width: 17px;
  height: 17px;
  padding: 0 4px;
  border-radius: 9px;
  background: #f2603c;
  color: #fff;
  font-size: 10px;
  font-style: normal;
  font-weight: 700;
  display: grid;
  place-items: center;
}

/* 列表 */
.list {
  width: 312px;
  flex: none;
  background: #fff;
  border-right: 1px solid #e6ecec;
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.lhead {
  height: 52px;
  flex: none;
  padding: 0 12px 0 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #e8eeee;
}
.lhead h3 { font-size: 14px; font-weight: 700; color: #2f3d52; }
.btns { display: flex; gap: 6px; }
.pbtn {
  height: 28px;
  padding: 0 12px;
  border-radius: 6px;
  background: #fff;
  border: 1px solid #e2eaf3;
  box-shadow: 0 1px 3px rgba(30, 60, 100, 0.07);
  color: #5c6c82;
  font-size: 11px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.pbtn.slim { padding: 0 7px; }

.rows { flex: 1; overflow-y: auto; }
.rows::-webkit-scrollbar { width: 5px; }
.rows::-webkit-scrollbar-thumb { background: #ccd8e6; border-radius: 3px; }

.row {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 9px 12px 9px 14px;
  border: 0;
  background: transparent;
  cursor: pointer;
  text-align: left;
  transition: background 0.13s;
}
.row:hover { background: #f7fbfb; }
.row.on { background: #e6f0f7; }

.ava {
  position: relative;
  width: 46px;
  height: 46px;
  flex: none;
  border-radius: 50%;
  overflow: hidden;
  display: grid;
  place-items: center;
  box-shadow: 0 2px 7px rgba(20, 40, 70, 0.16);
}
.ava img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  z-index: 2;
}
.ava b {
  position: relative;
  z-index: 1;
  color: #fff;
  font-size: 17px;
  font-weight: 700;
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.22);
}

.col {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.nm {
  font-size: 14px;
  font-weight: 700;
  color: #26334a;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ln {
  font-size: 12px;
  color: #94a2b6;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.hf {
  flex: none;
  display: flex;
  align-items: center;
  gap: 3px;
  color: #f26a92;
}
.hf em { font-style: normal; font-size: 13.5px; font-weight: 700; }

/* 详情 */
.detail {
  flex: 1;
  min-width: 0;
  display: none;
  flex-direction: column;
  background: #fff;
  overflow-y: auto;
  padding: 0 0 20px;
}
.detail.show { display: flex; }
.detail::-webkit-scrollbar { width: 6px; }
.detail::-webkit-scrollbar-thumb { background: #d6e0ec; border-radius: 3px; }

.back {
  align-self: flex-start;
  margin: 10px 0 0 14px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: 0;
  background: transparent;
  color: #8b99ad;
  font-size: 12px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 6px;
}
.back:hover { background: #f3f6f6; }

.dtop {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 22px 20px 16px;
  background: #ffffff;
  flex: none;
}
.dtop .dava {
  position: relative;
  width: 104px; height: 104px;
  border-radius: 50%;
  display: grid; place-items: center;
  color: #fff; font-size: 38px; font-weight: 700;
  box-shadow: 0 4px 14px rgba(30, 70, 110, .14);
}
.dtop .dava img { position: absolute; inset: 0; width: 100%; height: 100%; border-radius: 50%; object-fit: cover; z-index: 2; }
.dtop .dava b { position: relative; z-index: 1; }
.dheart img { width: 13px; height: 13px; margin-right: 3px; vertical-align: -1px; }
.dheart {
  position: absolute;
  right: -6px; bottom: 2px;
  z-index: 3;
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 2px 9px;
  border-radius: 999px;
  background: #f7739a;
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  font-style: normal;
  box-shadow: 0 2px 6px rgba(230, 80, 130, .36);
}
.dtop h4 { margin: 2px 0 0; font-size: 19px; font-weight: 800; color: #2b3444; }
.dline { margin: 0; font-size: 13px; color: #7b8798; text-align: center; max-width: 380px; }
.dchip {
  margin-top: 2px;
  padding: 3px 13px;
  border: 1px solid #cfdde8;
  border-radius: 999px;
  background: #fbfdfe;
  font-size: 12px;
  color: #5f7c8d;
}
.dava {
  position: relative;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  overflow: hidden;
  display: grid;
  place-items: center;
  flex: none;
  box-shadow: 0 3px 10px rgba(20, 40, 70, 0.18);
}
.dava img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; z-index: 2; }
.dava b { position: relative; z-index: 1; color: #fff; font-size: 22px; font-weight: 700; }


.dtop h4 { font-size: 18px; font-weight: 700; color: #26334a; margin-bottom: 7px; }
.tags { display: flex; flex-wrap: wrap; gap: 6px; }
.tg {
  padding: 2px 9px;
  border-radius: 20px;
  background: #f3f6f6;
  color: #6b7c92;
  font-size: 11px;
}
.tg.heart { background: #fdeef3; color: #e0567e; font-weight: 700; }

/* 对话 */
/* 专属对话 */
.chatbox { display: flex; flex-direction: column; flex: 1; min-height: 0; }
.msgs { flex: 1; overflow-y: auto; padding: 14px 22px 8px; display: flex; flex-direction: column; gap: 10px; }
.empty { margin: 30px auto; color: #9db4c9; font-size: 12.5px; }
.ctxblock + .ctxhead {
  margin: 2px 0 8px; text-align: center;
  font-size: 11.5px; font-weight: 700; letter-spacing: .06em;
  color: #93a9bd;
}
.ctxblock { margin-top: 3px; }
.daysplit {
  display: flex; align-items: center; justify-content: center;
  margin: 12px 0 10px;
}
.daysplit span {
  padding: 3px 12px; border-radius: 9px;
  background: rgba(126, 160, 190, .14);
  color: #7d93a8; font-size: 11px; letter-spacing: .02em;
}
.aside {
  align-self: center;
  max-width: 78%;
  padding: 5px 14px;
  border-radius: 999px;
  background: #eef5fb;
  color: #6d90ad;
  font-size: 11.5px;
  font-style: italic;
}
.bub.typing i, .dots i {
  display: inline-block; width: 5px; height: 5px; margin: 0 1.5px;
  border-radius: 50%; background: #9db4c9;
  animation: blink 1s infinite;
}
.bub.typing i:nth-child(2) { animation-delay: .15s; }
.bub.typing i:nth-child(3) { animation-delay: .3s; }
@keyframes blink { 0%, 100% { opacity: .25 } 50% { opacity: 1 } }

.atbtn {
  flex: none;
  width: 34px; height: 34px;
  display: grid; place-items: center;
  border: 1.5px solid #cfe1f0; border-radius: 10px;
  background: #fff; color: #6f8aa3;
  font: 700 15px/1 ui-sans-serif, system-ui, sans-serif;
  cursor: pointer; transition: all .15s;
}
.atbtn:hover { border-color: #9fc6e6; color: #3f7fb5; }
.atbtn.on {
  background: linear-gradient(180deg, #7cc0f0, #4a9fe0);
  border-color: #3f92d4; color: #fff;
  box-shadow: 0 3px 10px rgba(74, 159, 224, .35);
}
.speakbtn {
  flex: none;
  width: 38px; height: 38px;
  display: grid; place-items: center;
  border: none; border-radius: 11px;
  background: transparent;
  cursor: pointer;
  padding: 0;
  transition: background .15s;
}
.speakbtn img { width: 24px; height: auto; image-rendering: pixelated; transition: transform .12s; }
.speakbtn:hover { background: rgba(255, 214, 232, .5); }
.speakbtn:hover img { transform: scale(1.12); }
.speakbtn.busy { background: rgba(255, 214, 232, .62); }
.speakbtn.busy img { animation: heartBeat 1.05s ease-in-out infinite; }
@keyframes heartBeat {
  0%, 100% { transform: scale(1); }
  22% { transform: scale(1.2); }
  44% { transform: scale(.98); }
  66% { transform: scale(1.14); }
}
.composer { border-top: 1px solid #e3eef7; background: #fbfdff; padding: 10px 18px 12px; }
.asidebar { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.asidebar span { font-size: 11px; color: #7ea0bc; background: #eef5fb; padding: 2px 8px; border-radius: 999px; }
.asidebar input { flex: 1; height: 30px; border: 1.5px solid #dbe9f6; border-radius: 8px; padding: 0 10px; font-size: 12.5px; outline: none; color: #2b4c6b; background: #fff; }
.cline { display: flex; align-items: center; gap: 8px; }
.abtn { width: 36px; height: 36px; border-radius: 9px; border: 1.5px solid #dbe9f6; background: #fff; color: #6d90ad; cursor: pointer; display: grid; place-items: center; }
.abtn.on { background: #eaf4ff; border-color: #a9dcf7; color: #2180bd; }
.dinput { flex: 1; height: 38px; border: 1.5px solid #dbe9f6; border-radius: 10px; padding: 0 13px; font-size: 13px; outline: none; color: #24425f; background: #fff; }
.dinput:focus { border-color: #9fd2f4; }
.sbtn { height: 38px; padding: 0 20px; border: none; border-radius: 10px; background: linear-gradient(180deg, #f486ab, #e75b8c); color: #fff; font-size: 13px; font-weight: 700; cursor: pointer; }
.sbtn:disabled { opacity: .5; cursor: default; }
.chat { padding: 16px 22px 6px; display: flex; flex-direction: column; gap: 11px; }
.msg.cont { margin-top: 3px; }
.msg.cont .bub { border-top-left-radius: 12px; }
.msg { display: flex; gap: 9px; align-items: flex-start; }
.msg.me { justify-content: flex-end; }
.mava {
  width: 32px;
  height: 32px;
  flex: none;
  border-radius: 50%;
  overflow: hidden;
  display: grid;
  place-items: center;
  position: relative;
  box-shadow: 0 2px 6px rgba(20, 40, 70, 0.16);
}
.mava img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; z-index: 2; }
.mava b { position: relative; z-index: 1; color: #fff; font-size: 13px; font-weight: 700; }

.mava.mika { background: linear-gradient(145deg, #f5a9c4, #e0729c); color: #fff; font-size: 13px; font-weight: 700; }

.mcol { display: flex; flex-direction: column; gap: 3px; max-width: 72%; }
.mcol.right { align-items: flex-end; }
.gmark {
  margin-left: 6px; padding: 1px 6px; border-radius: 7px;
  background: rgba(120, 150, 180, .16);
  font-style: normal; font-size: 10.5px; font-weight: 500; color: #6c8299;
}
.mwho { font-size: 11px; color: #94a2b6; padding-left: 2px; }
.mwho.me { padding-right: 2px; color: #e0729c; font-weight: 700; }
.bub {
  margin: 0;
  padding: 9px 13px;
  border-radius: 10px;
  font-size: 13.5px;
  line-height: 1.55;
}
.bub.dim { color: #a3b0c2; }
.msg.them .bub { background: #4c5b6f; color: #fff; border-top-left-radius: 3px; }
.bub.mine {
  background: #4a8acb;
  color: #fff;
  border-top-right-radius: 3px;
  box-shadow: 0 3px 10px rgba(61, 134, 212, 0.22);
}
.dots { display: inline-flex; gap: 4px; align-items: center; height: 18px; }
.dots i {
  width: 5px; height: 5px; border-radius: 50%;
  background: rgba(255, 255, 255, 0.85);
  animation: blink 1.1s infinite;
}
.dots i:nth-child(2) { animation-delay: 0.18s; }
.dots i:nth-child(3) { animation-delay: 0.36s; }
@keyframes blink { 0%,60%,100% { opacity: 0.3; } 30% { opacity: 1; } }

.read {
  align-self: center;
  padding: 3px 14px;
  border-radius: 20px;
  background: #e8eeee;
  color: #8b98a8;
  font-size: 11px;
}

/* 数据面板 */
.panel {
  margin: 10px 22px 0;
  border: 1px solid #cfe3f0;
  border-radius: 10px;
  padding: 0;
  background: #ffffff;
  overflow: hidden;
  flex: none;
}
.panel h5 {
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  margin: 0;
  padding: 9px 14px;
  background: #d7ecf8;
  font-size: 13.5px;
  font-weight: 700;
  letter-spacing: .06em;
  color: #326fa0;
}
.panel h5 .zoom {
  position: absolute;
  right: 10px;
  width: 26px; height: 26px;
  display: grid; place-items: center;
  border-radius: 7px;
  background: #fff;
  box-shadow: 0 1px 3px rgba(40, 90, 130, .16);
  font-style: normal;
  font-size: 13px;
}
.panel > p, .panel > .emos, .panel > .stats { padding: 10px 16px; }
.panel > p { margin: 0; }
.panel > p + p { border-top: 1px solid #f0f5f8; }
.panel h5 { font-size: 12px; font-weight: 700; color: #5b6b82; margin-bottom: 8px; }
.panel p { margin: 0 0 5px; font-size: 12.5px; color: #465468; line-height: 1.6; }
.panel p b { display: inline-block; min-width: 34px; margin-right: 8px; color: #94a2b6; font-weight: 400; }
.panel p.dim { color: #94a2b6; }

.emos { display: grid; grid-template-columns: 1fr 1fr; gap: 7px 18px; }
.erow { display: flex; align-items: center; gap: 7px; }
.el { width: 26px; flex: none; font-size: 11px; color: #7d8ca0; }
.eb { flex: 1; height: 5px; border-radius: 3px; background: #e9eff7; overflow: hidden; }
.eb i { display: block; height: 100%; border-radius: 3px; transition: width 0.45s var(--ease-out); }
.ev { width: 20px; text-align: right; font-size: 10.5px; color: #94a2b6; }

.kvs { display: flex; gap: 20px; flex-wrap: wrap; }
.kvs span { display: flex; align-items: baseline; gap: 5px; font-size: 11.5px; color: #94a2b6; }
.kvs b { font-size: 17px; font-weight: 700; color: #26334a; }
.kvs b.ok { color: #46c08a; }
.kvs b.bad { color: #e8556d; }

.tip { flex: 1; display: grid; place-items: center; color: #a3b0c2; font-size: 13px; }

.pbtn-wrap { position: relative; }
.sort-menu {
  position: absolute;
  top: 34px;
  right: 0;
  z-index: 20;
  min-width: 118px;
  padding: 6px;
  background: #fff;
  border: 1px solid #dbe6ef;
  border-radius: 10px;
  box-shadow: 0 8px 24px rgba(20, 50, 90, 0.16);
}
.sort-opt {
  display: block;
  width: 100%;
  padding: 8px 12px;
  border: 0;
  border-radius: 7px;
  background: transparent;
  font-size: 13px;
  color: #46586d;
  text-align: left;
  cursor: pointer;
}
.sort-opt:hover { background: #f1f7fd; }
.sort-opt.on { background: #e6f2fc; color: #2f6fbb; font-weight: 700; }

.panes { margin: 4px 22px 0; display: flex; flex-direction: column; gap: 10px; flex: none; }
.panel { border: 1px solid #cfe3f0; border-radius: 10px; background: #fff; overflow: hidden; }
.panel h5 {
  display: flex; align-items: center; justify-content: center;
  position: relative; margin: 0; padding: 9px 14px;
  background: #d7ecf8; font-size: 13.5px; font-weight: 700;
  letter-spacing: .06em; color: #326fa0;
}
.pbody { animation: pbody-in .18s var(--ease); }
.pbody > p { margin: 0; padding: 7px 16px; font-size: 13px; color: #4f5d70; }
.pbody > p b { display: inline-block; width: 42px; color: #8b98a8; font-weight: 500; }
.pbody .kvs { display: flex; flex-wrap: wrap; gap: 6px 18px; padding: 10px 16px 4px; font-size: 12.5px; color: #6c7a8c; }
.pbody .kvs b { font-family: var(--font-num); font-size: 15px; color: #2b3444; margin-right: 4px; }
.pbody .kvs .ok { color: #46c08a; }
.pbody .kvs .bad { color: #e8556d; }
</style>
