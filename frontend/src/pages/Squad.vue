<script setup lang="ts">
/**
 * 编队 —— 把后台那一堆黑窗口收进来。
 * 每张卡对应一个服务：端口在不在听 = 在不在跑；可以单独启停、重启、看日志。
 */
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

type Svc = {
  key: string; name: string; desc: string; port: number
  alive: boolean; pid: number | null; managed: boolean
  auto: boolean; spawned: boolean; log: string
}

const list = ref<Svc[]>([])
const busy = ref('')
const tip = ref('')
const openLog = ref('')
const logText = ref('')
const loading = ref(true)
let timer: number | null = null

function ensureToken() {
  if (!localStorage.getItem('schale_token')) {
    try {
      const raw = localStorage.getItem('schale_login')
      if (raw) localStorage.setItem('schale_token', JSON.parse(raw).token)
    } catch { /* ignore */ }
  }
}

function authHeaders(): Record<string, string> {
  ensureToken()
  const t = localStorage.getItem('schale_token') || ''
  return t ? { Authorization: 'Bearer ' + t } : {}
}

async function relogin(): Promise<boolean> {
  try {
    const r = await fetch('/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password: 'CHANGE_ME' }),
    })
    if (!r.ok) return false
    const j = await r.json()
    if (j?.token) {
      localStorage.setItem('schale_token', j.token)
      return true
    }
  } catch { /* ignore */ }
  return false
}

async function api(path: string, init?: RequestInit) {
  const r = await fetch(path, { ...init, headers: { ...authHeaders(), ...(init?.headers || {}) } })
  if (r.status === 401 && (await relogin())) {
    return fetch(path, { ...init, headers: { ...authHeaders(), ...(init?.headers || {}) } })
  }
  return r
}

async function load() {
  try {
    const r = await api('/api/services')
    const j = await r.json()
    if (Array.isArray(j?.list)) list.value = j.list
  } catch { /* ignore */ }
  loading.value = false
}

function say(msg: string) {
  tip.value = msg
  window.setTimeout(() => { if (tip.value === msg) tip.value = '' }, 2600)
}

async function act(key: string, action: 'start' | 'stop' | 'restart') {
  busy.value = key + action
  try {
    const r = await api(`/api/services/${key}/${action}`, { method: 'POST' })
    const j = await r.json()
    if (Array.isArray(j?.list)) list.value = j.list
    if (j?.ok) {
      const name = j?.name || key
      say(action === 'start' ? `${name} 已启动` : action === 'stop' ? `${name} 已停止` : `${name} 已重启`)
    } else {
      say(j?.error || '操作失败')
    }
  } catch (e: any) {
    say('操作失败：' + (e?.message || e))
  }
  busy.value = ''
}

async function startAll() {
  busy.value = 'all'
  const started: string[] = []
  for (const s of list.value) {
    if (s.key === 'panel' || s.alive) continue
    try {
      const r = await api(`/api/services/${s.key}/start`, { method: 'POST' })
      const j = await r.json()
      if (j?.ok) started.push(s.name)
      if (Array.isArray(j?.list)) list.value = j.list
    } catch { /* 单个失败不影响其它 */ }
  }
  say(started.length ? `已拉起：${started.join('、')}` : '没有需要启动的服务')
  busy.value = ''
}

async function toggleLog(key: string) {
  if (openLog.value === key) { openLog.value = ''; return }
  openLog.value = key
  logText.value = '读取中…'
  try {
    const r = await api(`/api/services/${key}/log?lines=120`)
    const j = await r.json()
    logText.value = j?.text || '（这个服务还没有输出）'
  } catch { logText.value = '读取失败' }
}

const upCount = computed(() => list.value.filter(s => s.alive).length)
const total = computed(() => list.value.length)

function back() {
  router.replace('/home')
}

onMounted(() => {
  load()
  timer = window.setInterval(load, 4000)
})
onUnmounted(() => { if (timer) window.clearInterval(timer) })
</script>

<template>
  <main class="squad">
    <div class="veil"></div>

    <header class="top">
      <button class="rnd" @click="back" title="返回大厅">
        <svg viewBox="0 0 24 24" width="20" height="20"><path d="M15 5 8 12l7 7" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>
      </button>
      <h1>编队 <em>服务控制台</em></h1>
      <div class="meter">
        <b>{{ upCount }}</b><i>/ {{ total }}</i>
        <span>在线</span>
      </div>
      <button class="all" :disabled="busy === 'all'" @click="startAll">
        {{ busy === 'all' ? '启动中…' : '全部启动' }}
      </button>
    </header>

    <p v-if="tip" class="tip">{{ tip }}</p>

    <section class="grid">
      <article
        v-for="s in list"
        :key="s.key"
        class="card"
        :class="{ on: s.alive, me: !s.managed }"
      >
        <div class="row1">
          <span class="dot" :class="{ live: s.alive }"></span>
          <h2>{{ s.name }}</h2>
          <span v-if="s.auto" class="chip auto">开机自启</span>
          <span v-if="!s.managed" class="chip me">当前</span>
        </div>

        <p class="desc">{{ s.desc }}</p>

        <div class="kvs">
          <div><i>端口</i><b>{{ s.port || '—' }}</b></div>
          <div><i>进程</i><b>{{ s.pid || '—' }}</b></div>
          <div><i>状态</i><b :class="{ live: s.alive }">{{ s.alive ? '运行中' : '未运行' }}</b></div>
        </div>

        <div class="ops">
          <button
            v-if="s.managed"
            class="op go"
            :disabled="s.alive || !!busy"
            @click="act(s.key, 'start')"
          >{{ busy === s.key + 'start' ? '…' : '启动' }}</button>
          <button
            v-if="s.managed"
            class="op stop"
            :disabled="!s.alive || !!busy"
            @click="act(s.key, 'stop')"
          >{{ busy === s.key + 'stop' ? '…' : '停止' }}</button>
          <button
            v-if="s.managed"
            class="op"
            :disabled="!!busy"
            @click="act(s.key, 'restart')"
          >{{ busy === s.key + 'restart' ? '…' : '重启' }}</button>
          <button class="op ghost" @click="toggleLog(s.key)">
            {{ openLog === s.key ? '收起日志' : '日志' }}
          </button>
        </div>

        <pre v-if="openLog === s.key" class="log">{{ logText }}</pre>
      </article>
    </section>

    <p v-if="loading" class="loading">读取服务状态…</p>

    <footer class="foot">
      <span>状态每 4 秒刷新一次 · 端口在听即视为在线</span>
      <span class="rev">SCHALE · SQUAD</span>
    </footer>
  </main>
</template>

<style scoped>
.squad {
  position: fixed;
  inset: 0;
  z-index: 30;
  overflow-y: auto;
  padding: 18px 26px 26px;
  font-family: 'Microsoft YaHei', 'PingFang SC', system-ui, sans-serif;
  color: #21405e;
}
.veil {
  position: fixed;
  inset: 0;
  z-index: -1;
  background:
    radial-gradient(120% 90% at 50% 0%, #dceeff 0%, #b9d9f4 42%, #8fbde6 100%);
}

.top {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 14px;
}
.rnd {
  width: 42px; height: 42px;
  display: grid; place-items: center;
  border-radius: 50%;
  border: none;
  background: rgba(255,255,255,.92);
  color: #2f6ea3;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(20,60,100,.18);
}
.rnd:hover { background: #fff; }
.top h1 {
  margin: 0;
  font-size: 26px;
  font-weight: 800;
  letter-spacing: .04em;
  display: flex;
  align-items: baseline;
  gap: 10px;
}
.top h1 em {
  font-size: 12.5px;
  font-style: normal;
  font-weight: 600;
  color: #4d7fa8;
  letter-spacing: .12em;
}
.meter {
  margin-left: auto;
  display: flex;
  align-items: baseline;
  gap: 2px;
  padding: 7px 14px;
  border-radius: 999px;
  background: rgba(255,255,255,.86);
  box-shadow: 0 3px 10px rgba(20,60,100,.14);
}
.meter b { font-size: 20px; color: #2f8bd6; }
.meter i { font-style: normal; font-size: 12px; color: #7d9ab5; margin-right: 6px; }
.meter span { font-size: 11.5px; color: #5b809f; }
.all {
  padding: 9px 20px;
  border: none;
  border-radius: 10px;
  background: linear-gradient(180deg, #5fb4f0, #2f8bd6);
  color: #fff;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: .04em;
  cursor: pointer;
  box-shadow: 0 6px 16px rgba(30,110,180,.32);
}
.all:disabled { opacity: .6; cursor: default; }

.tip {
  margin: 0 0 12px;
  padding: 8px 14px;
  border-radius: 9px;
  background: rgba(255,255,255,.9);
  color: #2f6ea3;
  font-size: 12.5px;
  box-shadow: 0 3px 10px rgba(20,60,100,.12);
}

.grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}
.card {
  padding: 14px 16px 12px;
  border-radius: 14px;
  background: rgba(255,255,255,.9);
  border: 1.5px solid rgba(255,255,255,.6);
  box-shadow: 0 8px 22px rgba(20,60,100,.14);
}
.card.on { border-color: rgba(110,196,150,.7); }
.card.me { background: rgba(238,247,255,.94); }

.row1 { display: flex; align-items: center; gap: 8px; }
.dot {
  width: 10px; height: 10px;
  border-radius: 50%;
  background: #c3d3e0;
  box-shadow: 0 0 0 3px rgba(195,211,224,.28);
}
.dot.live {
  background: #4cc184;
  box-shadow: 0 0 0 3px rgba(76,193,132,.24);
}
.row1 h2 { margin: 0; font-size: 16px; font-weight: 800; }
.chip {
  margin-left: auto;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 10.5px;
  font-weight: 700;
}
.chip.auto { background: #e5f1fb; color: #4a86bb; }
.chip.me { background: #fde9f0; color: #d0557f; }

.desc {
  margin: 6px 0 10px;
  font-size: 12px;
  color: #5e7f9c;
  line-height: 1.6;
}

.kvs {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin-bottom: 11px;
}
.kvs div {
  padding: 7px 10px;
  border-radius: 9px;
  background: #f1f8ff;
}
.kvs i { display: block; font-style: normal; font-size: 10.5px; color: #7a9cba; }
.kvs b { font-size: 13.5px; color: #2b5279; }
.kvs b.live { color: #2f9e6b; }

.ops { display: flex; gap: 7px; }
.op {
  flex: 1;
  padding: 7px 0;
  border: 1.5px solid #cfe4f6;
  border-radius: 9px;
  background: #fff;
  color: #3d6f9c;
  font-size: 12.5px;
  font-weight: 700;
  cursor: pointer;
}
.op:hover:not(:disabled) { background: #f2f9ff; }
.op:disabled { opacity: .45; cursor: default; }
.op.go { border-color: #a9dcf7; color: #2179b5; }
.op.stop { border-color: #f6cdd8; color: #c05274; }
.op.ghost { border-color: #e2edf7; color: #6d8ba6; flex: 0 0 92px; }

.log {
  margin: 10px 0 0;
  max-height: 190px;
  overflow: auto;
  padding: 10px 12px;
  border-radius: 9px;
  background: #12283e;
  color: #bcd8ef;
  font: 400 11.5px/1.6 Consolas, 'Cascadia Mono', monospace;
  white-space: pre-wrap;
  word-break: break-all;
}

.loading { text-align: center; color: #4d7fa8; font-size: 13px; }

.foot {
  display: flex;
  justify-content: space-between;
  margin-top: 16px;
  font-size: 11.5px;
  color: #5f86a6;
}
.rev { letter-spacing: .14em; opacity: .7; }
</style>
