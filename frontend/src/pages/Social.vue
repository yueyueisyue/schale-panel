<script setup lang="ts">
/**
 * 社交：大厅之上浮出的一层。
 * 首页三张斜切卡（小组 / 好友 / 助力者），小组进去是「加入小组」列表。
 * 点空白或按 Esc 关闭。
 */
import { computed, onMounted, onUnmounted, ref } from 'vue'

const props = withDefaults(
  defineProps<{
    open?: boolean
    view?: 'home' | 'groups' | 'friends' | 'helpers'
    gid?: string | null
  }>(),
  { open: true, view: 'home', gid: null },
)
const emit = defineEmits<{ (e: 'close'): void }>()

const TOKEN_KEY = 'schale_token'
const view = ref<'home' | 'groups' | 'friends' | 'helpers'>(props.view)

// 常驻助力者：本地资料助手 + 外链 wiki
const ASSISTANTS = [
  {
    key: 'kotori',
    name: '琴寄',
    avatar: '/img/portrait/kotori.png',
    role: '资料助理 · 档案检索',
    desc: '',
    tag: '常驻',
  },
  {
    key: 'kivo',
    name: '基沃托斯古书馆wiki',
    avatar: '/img/portrait/kivo.png',
    role: '资料来源 · 考据与图像',
    desc: '这个面板里大量素材来自这里。想问角色、剧情、立绘、活动，先去翻她。',
    tag: '来源',
    wiki: { label: 'https://kivo.wiki/', icon: '/img/icon/wiki.png', url: 'https://kivo.wiki/' },
  },
  {
    key: 'arona',
    name: '阿罗娜',
    avatar: '/img/icon/calendar-arona.png',
    role: '内置助理 · 夏莱主控 OS',
    desc: '替老师挡杂事、盯日程，也会在深夜提醒你该睡了。',
    tag: '常驻',
  },
]

const groups = ref<any[]>([])
const people = ref<any[]>([])
const shop = ref<any>(null)
const openGid = ref<string | null>(props.gid)
const loading = ref(false)
const q = ref('')
const _ft = new URLSearchParams(location.search).get('ftab')
const ftab = ref<'list' | 'asking' | 'waiting' | 'search'>(
  _ft === 'asking' || _ft === 'waiting' || _ft === 'search' ? _ft : 'list',
)
const fsortDesc = ref(true)
const hidden = ref<string[]>(JSON.parse(localStorage.getItem('schale_friend_hidden') || '[]'))
const FRIEND_TABS = [
  { key: 'list', label: '好友列表' },
  { key: 'asking', label: '好友申请中' },
  { key: 'waiting', label: '等待同意中' },
  { key: 'search', label: '搜索好友' },
] as const
const friends = computed(() => {
  const list = people.value.filter((p: any) => !hidden.value.includes(p.id))
  if (ftab.value !== 'list') return []
  return [...list].sort((a: any, b: any) =>
    fsortDesc.value ? (b.favor || 0) - (a.favor || 0) : (a.favor || 0) - (b.favor || 0),
  )
})
function hideFriend(id: string) {
  if (!hidden.value.includes(id)) hidden.value.push(id)
  localStorage.setItem('schale_friend_hidden', JSON.stringify(hidden.value))
}

const qqIn = ref<any[]>([])
const qqOut = ref<any[]>([])
const qqFriends = ref<any[]>([])
const openFriend = ref<any>(null)
const searchQQ = ref('')
const tip = ref('')
const searchHit = ref<any>(null)
const qqBusy = ref(false)

async function apiPost(path: string, body: any) {
  const r = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(authHeaders() as any) },
    body: JSON.stringify(body),
  })
  return r.json()
}
async function loadQQ() {
  const j = await get('/api/qq/requests')
  if (j?.ok) {
    qqIn.value = j.incoming || []
    qqOut.value = j.outgoing || []
    qqFriends.value = j.friends || []
  }
}
async function decideReq(row: any, accept: boolean) {
  qqBusy.value = true
  try {
    await ensureToken()
    const j = await apiPost('/api/qq/decide', { qq: String(row.qq), accept })
    if (j?.ok) {
      qqIn.value = j.incoming || []
      qqOut.value = j.outgoing || []
      qqFriends.value = j.friends || []
    }
  } finally {
    qqBusy.value = false
  }
}
async function cancelOut(r: any) {
  if (!r || qqBusy.value) return
  qqBusy.value = true
  try {
    const j = await apiPost('/api/qq/cancel', { qq: r.qq })
    if (j) {
      qqOut.value = j.outgoing || []
      tip.value = '已撤回给 ' + (r.name || r.qq) + ' 的申请'
      window.setTimeout(() => { tip.value = '' }, 2200)
    }
  } finally {
    qqBusy.value = false
  }
}

async function doSearchQQ() {
  const q = searchQQ.value.trim()
  if (!/^\d{5,12}$/.test(q)) {
    searchHit.value = { error: '请输入 5~12 位数字 QQ 号' }
    return
  }
  qqBusy.value = true
  try {
    await ensureToken()
    const j = await get('/api/qq/profile?qq=' + q)
    searchHit.value = j?.ok ? j : { error: '查不到这个号' }
  } finally {
    qqBusy.value = false
  }
}
async function addFriend() {
  if (!searchHit.value?.qq) return
  qqBusy.value = true
  try {
    await ensureToken()
    const j = await apiPost('/api/qq/apply', { qq: searchHit.value.qq, name: searchQQ.value.trim() })
    if (j?.ok) {
      qqOut.value = j.outgoing || []
      searchHit.value = { ...searchHit.value, status: 'pending' }
    }
  } finally {
    qqBusy.value = false
  }
}

const opened = computed(() => groups.value.find((g) => g.id === openGid.value) || null)
const shown = computed(() => {
  const k = q.value.trim()
  if (!k) return groups.value
  return groups.value.filter((g) => g.name.includes(k) || String(g.id).includes(k))
})

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
async function get(path: string) {
  const r = await fetch(path, { headers: authHeaders() as any })
  return r.json()
}
async function load() {
  loading.value = true
  await ensureToken()
  try {
    const [g, m, s] = await Promise.all([get('/api/groups'), get('/api/mail'), get('/api/shop')])
    if (g?.groups) groups.value = g.groups
    if (m?.people) people.value = m.people
    if (s?.ok) shop.value = s
    await loadQQ()
    const wantFriend = new URLSearchParams(location.search).get('friend')
    if (wantFriend) {
      const hit = people.value.find((p: any) => String(p.id) === wantFriend || String(p.avatarId) === wantFriend)
      if (hit) openFriend.value = hit
    }
  } finally {
    loading.value = false
  }
}

const ENTRIES = [
  {
    key: 'groups',
    label: '小组',
    desc: '可加入或参与小组活动。',
    art: '/img/bg/committeeroom-day.webp',
  },
  {
    key: 'friends',
    label: '好友',
    desc: '可寻找并添加新好友。',
    art: '/img/bg/generalreadingroom-day.webp',
  },
  {
    key: 'helpers',
    label: '助力者',
    desc: '可设置并管理助力者。',
    art: '/img/bg/milleniumseminarclubroom-day.webp',
  },
] as const

function go(k: string) {
  view.value = k as any
}
function back() {
  if (view.value === 'home') emit('close')
  else if (openGid.value) openGid.value = null
  else view.value = 'home'
}
function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape') back()
}

onMounted(() => {
  load()
  window.addEventListener('keydown', onKey)
})
onUnmounted(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <div v-if="open" class="social" @click.self="emit('close')">
    <div class="veil"></div>

    <!-- 返回 / 关闭 -->
    <button class="back" @click.stop="back">
      <svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="#24588f" stroke-width="2.4"
        stroke-linecap="round" stroke-linejoin="round">
        <path d="M15 5 8 12l7 7" />
      </svg>
    </button>
    <button class="close" @click.stop="emit('close')">✕</button>

    <!-- 首页 -->
    <section v-if="view === 'home'" class="home">
      <header class="title">
        <svg class="ticon" viewBox="0 0 48 48" fill="none">
          <rect x="6" y="6" width="26" height="26" rx="8" fill="#eaf5ff" stroke="#2f6fa8" stroke-width="2.4" />
          <rect x="17" y="15" width="26" height="26" rx="8" fill="#bfe4ff" stroke="#2f6fa8" stroke-width="2.4" />
          <path d="M24 27.5a4.2 4.2 0 1 0 0-8.4" stroke="#2f6fa8" stroke-width="2.2" stroke-linecap="round" />
          <circle cx="34" cy="15" r="3.4" fill="#f6c445" stroke="#2f6fa8" stroke-width="1.8" />
        </svg>
        <h1>社交</h1>
      </header>

      <div class="rule"></div>

      <div class="entries">
        <button v-for="e in ENTRIES" :key="e.key" class="entry" @click="go(e.key)">
          <div class="art" :style="{ backgroundImage: `url(${e.art})` }"></div>
          <div class="txt">
            <h2>
              <span v-if="e.key === 'groups'" class="ei flag">
                <svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="#ffffff" stroke-width="2.4"
                  stroke-linecap="round" stroke-linejoin="round">
                  <path d="M5 3v18" /><path d="M5 4h13l-2.6 4.5L18 13H5" />
                </svg>
              </span>
              <span v-else-if="e.key === 'friends'" class="ei hand">
                <svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="#ffffff" stroke-width="2.4"
                  stroke-linecap="round" stroke-linejoin="round">
                  <path d="M3 12h4l3 3 4-4 3 3h4" /><path d="M7 9h3M14 9h3" />
                </svg>
              </span>
              <span v-else class="ei a">A</span>
              {{ e.label }}
            </h2>
            <p>{{ e.desc }}</p>
          </div>
        </button>
      </div>

      <div class="rule bottom"></div>
    </section>

    <!-- 加入小组 -->
    <section v-else-if="view === 'groups'" class="groups">
      <header class="ghead">
        <div class="search">
          <input v-model="q" placeholder="搜索小组" />
          <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="#4b7aa8" stroke-width="2.2"
            stroke-linecap="round">
            <circle cx="11" cy="11" r="6.4" /><path d="m16 16 4 4" />
          </svg>
        </div>
        <button class="ghost">筛选 <b>关闭</b> <i>▾</i></button>
        <button class="ghost" @click="load"><span class="rf">↻</span> 更新列表</button>
      </header>

      <div class="glist">
        <article v-for="g in shown" :key="g.id" class="grow" @click="openGid = g.id">
          <div class="gava">
            <img :src="`/api/gavatar/${g.id}`" :alt="g.name" @error="($event.target as any).style.display = 'none'" />
            <b>{{ g.name.slice(0, 1) }}</b>
          </div>
          <div class="ginfo">
            <h3>{{ g.name }}</h3>
            <ul>
              <li><span>小组ID</span><em>{{ g.id }}</em></li>
              <li><span>加入方式</span><em>{{ g.join || '自由加入' }}</em></li>
            </ul>
          </div>
          <div class="gside">
            <span class="cap">
              <svg viewBox="0 0 24 24" width="15" height="15" fill="currentColor">
                <circle cx="12" cy="8" r="3.6" /><path d="M4.6 20c0-3.7 3.3-6.2 7.4-6.2s7.4 2.5 7.4 6.2z" />
              </svg>
              {{ g.members }} / 50
            </span>
            <button class="visit">访问</button>
          </div>
        </article>
        <p v-if="!shown.length" class="empty">没有匹配的小组</p>
      </div>

      <footer class="gfoot">
        <button class="ghost big">自动加入</button>
        <button class="ghost big">创建小组</button>
      </footer>
    </section>

    <!-- 好友 -->
    <section v-else-if="view === 'friends'" class="friends">
      <aside class="frail">
        <button
          v-for="t in FRIEND_TABS"
          :key="t.key"
          class="ftab"
          :class="{ on: ftab === t.key }"
          @click="ftab = t.key"
        >{{ t.label }}</button>
      </aside>

      <div class="fmain">
        <header class="fhead">
          <span class="fcount">目前好友 <b>{{ friends.length }}</b>/50</span>
          <div class="fsort">
            <button class="ghost">等级 <i>▾</i></button>
            <button class="ghost icon" @click="fsortDesc = !fsortDesc">⇅</button>
          </div>
        </header>

        <div v-if="ftab === 'list'" class="flist">
          <article
            v-for="p in friends"
            :key="p.id"
            class="frow clickable"
            @click="openFriend = p"
          >
            <div class="fava">
              <img :src="`/api/avatar/${p.avatarId || p.id}`" @error="($event.target as any).style.display = 'none'" />
              <b>{{ (p.name || '?').slice(0, 1) }}</b>
              <span class="info" @click.stop="openFriend = p">i</span>
            </div>
            <div class="finfo">
              <h3>等级{{ 60 + Math.min(40, p.favor || 0) }} <em>{{ p.name }}</em></h3>
              <ul>
                <li><span>目前好友</span><em>{{ p.total ?? 0 }}</em></li>
                <li><span>最后登录</span><em>{{ p.lastDay || '—' }}</em></li>
              </ul>
            </div>
            <div class="fside">
              <span class="chip">印象 {{ p.favor ?? 0 }}</span>
              <button class="visit del" @click.stop="hideFriend(p.id)">删除好友</button>
            </div>
          </article>
          <p v-if="!friends.length" class="empty">这里还没有好友</p>
        </div>

        <!-- 好友申请中：别人申请机器人 QQ -->
        <div v-if="ftab === 'asking'" class="flist">
          <article v-for="r in qqIn" :key="'in' + r.qq" class="frow">
            <div class="fava">
              <img :src="`/api/avatar/${r.qq}`" @error="($event.target as any).style.display = 'none'" />
              <b>{{ (r.name || r.qq).slice(0, 1) }}</b>
            </div>
            <div class="finfo">
              <h3><em>{{ r.name || r.qq }}</em></h3>
              <ul>
                <li><span>QQ</span><em>{{ r.qq }}</em></li>
                <li><span>附言</span><em>{{ r.msg || '（无）' }}</em></li>
              </ul>
            </div>
            <div class="fside">
              <button class="visit" :disabled="qqBusy" @click.stop="decideReq(r, true)">通过</button>
              <button class="visit del" :disabled="qqBusy" @click.stop="decideReq(r, false)">拒绝</button>
            </div>
          </article>
          <p v-if="!qqIn.length" class="empty">
            机器人 QQ 目前没有新的好友申请。有人在 QQ 里申请加它，就会出现在这里。
          </p>
        </div>

        <p v-if="tip" class="tip">{{ tip }}</p>

        <!-- 等待同意中：机器人申请别人 -->
        <div v-if="ftab === 'waiting'" class="flist">
          <article v-for="r in qqOut" :key="'out' + r.qq" class="frow">
            <div class="fava">
              <img :src="`/api/avatar/${r.qq}`" @error="($event.target as any).style.display = 'none'" />
              <b>{{ (r.name || r.qq).slice(0, 1) }}</b>
            </div>
            <div class="finfo">
              <h3><em>{{ r.name || r.qq }}</em></h3>
              <ul>
                <li><span>QQ</span><em>{{ r.qq }}</em></li>
                <li><span>申请时间</span><em>{{ r.ts ? new Date(r.ts * 1000).toLocaleDateString() : '—' }}</em></li>
              </ul>
            </div>
            <div class="fside">
              <span class="chip" :class="r.status === 'accepted' ? 'okc' : 'waitc'">
                {{ r.status === 'accepted' ? '已通过' : r.status === 'rejected' ? '未通过' : '等待中' }}
              </span>
              <button
                v-if="r.status !== 'accepted'"
                class="ghost tiny"
                :disabled="qqBusy"
                @click.stop="cancelOut(r)"
              >撤回</button>
            </div>
          </article>
          <p v-if="!qqOut.length" class="empty">还没有发出过好友申请。</p>
        </div>

        <!-- 搜索好友 -->
        <div v-if="ftab === 'search'" class="fsearch">
          <div class="sbar">
            <input v-model="searchQQ" placeholder="输入 QQ 号" @keyup.enter="doSearchQQ" />
            <button class="ghost" :disabled="qqBusy" @click="doSearchQQ">搜索</button>
          </div>
          <article v-if="searchHit" class="frow found">
            <div class="fava">
              <img v-if="searchHit.qq" :src="`/api/avatar/${searchHit.qq}`" @error="($event.target as any).style.display = 'none'" />
              <b>{{ (searchHit.qq || '?').slice(0, 1) }}</b>
            </div>
            <div class="finfo">
              <h3><em>{{ searchHit.error || searchHit.qq }}</em></h3>
              <ul v-if="!searchHit.error">
                <li><span>状态</span><em>{{ searchHit.friend ? '已是好友' : searchHit.status === 'pending' ? '等待同意' : '可以添加' }}</em></li>
              </ul>
            </div>
            <div class="fside">
              <button
                v-if="!searchHit.error && !searchHit.friend && searchHit.status !== 'pending'"
                class="visit"
                :disabled="qqBusy"
                @click="addFriend"
              >加为好友</button>
              <span v-else-if="!searchHit.error" class="chip waitc">
                {{ searchHit.friend ? '已是好友' : '等待中' }}
              </span>
            </div>
          </article>
          <p v-else class="empty">输入对方的 QQ 号，就能查到头像并发出好友申请。</p>
        </div>
      </div>

      <!-- 好友详情浮层 -->
      <div v-if="openFriend" class="fdet" @click.self="openFriend = null">
        <div class="fdet-in">
          <button class="fdet-x" @click="openFriend = null">✕</button>
          <div class="fdet-head">
            <span class="fdet-ava">
              <img :src="`/api/avatar/${openFriend.avatarId || openFriend.id}`" @error="($event.target as any).style.display = 'none'" />
              <b>{{ (openFriend.name || '?').slice(0, 1) }}</b>
            </span>
            <h4>{{ openFriend.name }}</h4>
            <p>{{ openFriend.club || openFriend.group || '—' }}</p>
            <span class="fdet-heart">♥ 印象 {{ openFriend.favor ?? 0 }}</span>
          </div>
          <ul class="fdet-kv">
            <li><span>好感度</span><em>{{ openFriend.favor ?? 0 }}</em></li>
            <li><span>亲密度</span><em>{{ openFriend.intimacy ?? 0 }}</em></li>
            <li><span>聊过</span><em>{{ openFriend.total ?? 0 }} 次</em></li>
            <li><span>正面 / 负面</span><em>{{ openFriend.positive ?? 0 }} / {{ openFriend.negative ?? 0 }}</em></li>
            <li><span>连续互动</span><em>{{ openFriend.streak ?? 0 }} 天</em></li>
            <li><span>最后活跃</span><em>{{ openFriend.lastDay || '—' }}</em></li>
          </ul>
          <div v-if="openFriend.attitude" class="fdet-note">
            <b>她对这位的印象</b>
            <p>{{ openFriend.attitude }}</p>
          </div>
          <div v-if="openFriend.relationship" class="fdet-note">
            <b>关系</b>
            <p>{{ openFriend.relationship }}</p>
          </div>
          <div v-if="(openFriend.phrases || []).length" class="fdet-note">
            <b>他说过的话</b>
            <p v-for="(ph, i) in openFriend.phrases.slice(0, 4)" :key="i" class="ph">「{{ ph }}」</p>
          </div>
        </div>
      </div>
    </section>

    <!-- 助力者 -->
    <section v-else class="groups">
      <header class="ghead">
        <div class="search"><input placeholder="搜索助力者" /></div>
        <button class="ghost" @click="load"><span class="rf">↻</span> 更新列表</button>
      </header>
      <div class="alist">
        <article v-for="a in ASSISTANTS" :key="a.key" class="acard">
          <img class="aava" :src="a.avatar" :alt="a.name" />
          <div class="ainfo">
            <h3>{{ a.name }}</h3>
            <span class="arole">{{ a.role }}</span>
            <p v-if="a.desc" class="adesc">{{ a.desc }}</p>
            <a v-if="a.wiki" class="wikichip" :href="a.wiki.url" target="_blank" rel="noreferrer">
              <img :src="a.wiki.icon" alt="" />{{ a.wiki.label }}
            </a>
          </div>
          <div class="gside">
            <span class="cap on">{{ a.tag }}</span>
          </div>
        </article>
      </div>

      <p class="credit">
        这个面板用了基沃托斯古书馆（<a href="https://kivo.wiki/" target="_blank" rel="noreferrer">kivo.wiki</a>）里的大量素材，
        立绘、背景、图标、素材整理几乎都靠它，非常感谢。
      </p>
    </section>

    <!-- 群详情 -->
    <div v-if="opened" class="modal" @click.self="openGid = null">
      <div class="sheet">
        <header>
          <div class="gava big">
            <img :src="`/api/gavatar/${opened.id}`" @error="($event.target as any).style.display = 'none'" />
            <b>{{ opened.name.slice(0, 1) }}</b>
          </div>
          <div>
            <h3>{{ opened.name }}</h3>
            <p>小组ID {{ opened.id }} · {{ opened.join || '自由加入' }}</p>
          </div>
          <button class="x" @click="openGid = null">✕</button>
        </header>
        <div class="stats">
          <div><b>{{ opened.members }}</b><span>成员</span></div>
          <div><b>{{ opened.count }}</b><span>累计消息</span></div>
          <div><b>{{ opened.recent }}</b><span>最近缓存</span></div>
          <div><b>{{ opened.enabled ? '在线' : '停用' }}</b><span>状态</span></div>
        </div>
        <div class="last">
          <span class="k">最近一条</span>
          <p><b>{{ opened.lastWho || '—' }}</b>{{ opened.lastText || '（还没有发言）' }}</p>
        </div>
        <div class="members">
          <span class="k">在群里的人</span>
          <div class="tags">
            <span v-for="n in opened.memberNames" :key="n">{{ n }}</span>
            <span v-if="opened.members > opened.memberNames.length" class="more">
              +{{ opened.members - opened.memberNames.length }}
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.social {
  position: fixed;
  inset: 0;
  z-index: 40;
  display: grid;
  place-items: center;
  font-family: var(--font-ui, system-ui);
}
.veil {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(120% 90% at 50% 40%, rgba(28, 74, 140, 0.5) 0%, rgba(16, 46, 96, 0.72) 70%),
    linear-gradient(180deg, rgba(12, 34, 72, 0.55), rgba(8, 24, 54, 0.68));
  backdrop-filter: blur(3px) saturate(1.05);
}
.back,
.close {
  position: absolute;
  top: 26px;
  z-index: 3;
  width: 52px;
  height: 52px;
  display: grid;
  place-items: center;
  border: 0;
  border-radius: 50%;
  background: radial-gradient(circle at 34% 28%, #ffffff, #dcecfa 70%, #bcd8ef);
  box-shadow: 0 6px 16px rgba(4, 20, 44, 0.36), inset 0 2px 0 rgba(255, 255, 255, 0.8);
  cursor: pointer;
  color: #24588f;
}
.back { left: 26px; }
.close { right: 26px; font-size: 20px; font-weight: 700; color: #4a7ba6; }

/* ── 首页 ── */
.home {
  position: relative;
  z-index: 2;
  width: min(1320px, 94vw);
  display: grid;
  justify-items: center;
  gap: 22px;
}
.title {
  display: flex;
  align-items: center;
  gap: 18px;
  filter: drop-shadow(0 4px 10px rgba(4, 20, 44, 0.4));
}
.title .ticon { width: 62px; height: 62px; }
.title h1 {
  margin: 0;
  font-size: 62px;
  font-weight: 800;
  letter-spacing: 0.14em;
  color: #fff;
  text-shadow: 0 3px 0 #1d4b86, 0 8px 18px rgba(6, 24, 50, 0.55);
}
.rule {
  width: 100%;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.55) 18%, rgba(255, 255, 255, 0.55) 82%, transparent);
}
.rule.bottom { margin-top: 6px; }

.entries {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 34px;
  width: 100%;
  padding: 10px 0 4px;
}
.entry {
  position: relative;
  height: 230px;
  padding: 0;
  border: 0;
  overflow: hidden;
  cursor: pointer;
  text-align: left;
  background: #dceaf7;
  box-shadow: 0 14px 30px rgba(4, 20, 44, 0.34), inset 0 0 0 1px rgba(150, 196, 232, 0.55);
  clip-path: polygon(4% 0, 100% 0, 96% 100%, 0 100%);
  transition: transform 0.16s, box-shadow 0.16s;
}
.entry:hover {
  transform: translateY(-4px);
  box-shadow: 0 20px 40px rgba(4, 20, 44, 0.42), inset 0 0 0 1px rgba(120, 175, 220, 0.8);
}
.entry .art {
  position: absolute;
  inset: 0;
  background-size: cover;
  background-position: center 68%;
  filter: saturate(1.02) brightness(0.86);
}
.entry .art::after { content: none; }
.entry .txt {
  position: relative;
  z-index: 3;
  padding: 22px 26px 18px;
}
.entry h2 {
  margin: 0 0 8px;
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 34px;
  font-weight: 800;
  letter-spacing: 0.04em;
  color: #ffffff;
  text-shadow: 0 2px 6px rgba(6, 26, 52, 0.85), 0 1px 2px rgba(6, 26, 52, 0.7);
}
.entry h2 .ei {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  background: none;
  border: 0;
  box-shadow: none;
}
.entry h2 .ei svg { width: 27px; height: 27px; }
.entry h2 .ei.a {
  background: #f6c445;
  border: 2px solid #ffffff;
  border-radius: 8px;
  color: #ffffff;
  font-size: 19px;
  font-weight: 900;
}
.entry p {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: #f2f9ff;
  text-shadow: 0 2px 6px rgba(6, 26, 52, 0.85);
}
.entry p::before {
  content: '';
  display: inline-block;
  width: 3px;
  height: 13px;
  margin-right: 7px;
  vertical-align: -2px;
  background: #bfe3ff;
}

/* ── 列表视图 ── */
.groups {
  position: relative;
  z-index: 2;
  width: min(1180px, 92vw);
  max-height: 86vh;
  display: grid;
  grid-template-rows: auto 1fr auto;
  gap: 14px;
  padding: 18px;
  border-radius: 18px;
  background: linear-gradient(180deg, rgba(178, 216, 245, 0.92), rgba(150, 197, 236, 0.92));
  box-shadow: 0 20px 50px rgba(4, 20, 44, 0.4), inset 0 0 0 2px rgba(255, 255, 255, 0.6);
}
.ghead { display: grid; grid-template-columns: 1fr auto auto; gap: 12px; }
.search {
  position: relative;
  display: flex;
  align-items: center;
  height: 48px;
  padding: 0 14px;
  border-radius: 10px;
  background: #fff;
  box-shadow: inset 0 0 0 2px rgba(150, 195, 230, 0.7);
}
.search input {
  flex: 1;
  border: 0;
  outline: 0;
  font-size: 16px;
  color: #2b4a68;
  background: transparent;
}
.search input::placeholder { color: #9db4c9; }
.ghost {
  height: 48px;
  padding: 0 18px;
  border: 0;
  border-radius: 10px;
  background: #fff;
  color: #2b4a68;
  font-size: 16px;
  font-weight: 700;
  box-shadow: inset 0 0 0 2px rgba(150, 195, 230, 0.7);
  cursor: pointer;
}
.ghost b { font-weight: 500; color: #8aa6bf; }
.ghost i { font-style: normal; color: #8aa6bf; margin-left: 4px; }
.ghost .rf { margin-right: 6px; color: #3f8fd6; }
.ghost.big { height: 54px; padding: 0 26px; font-size: 18px; }

.credit { margin: 4px 2px 0; padding: 10px 14px; border-radius: 10px; background: rgba(255,255,255,.72); font-size: 12px; color: #4d7797; line-height: 1.7; }
.credit a { color: #2f7fc4; text-decoration: none; font-weight: 700; }
.alist { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 14px; }
.acard {
  display: flex; gap: 14px; align-items: center; padding: 14px 16px;
  border-radius: 12px; background: linear-gradient(120deg, #ffffff, #eef7ff);
  box-shadow: 0 6px 20px rgba(40, 82, 122, .12);
}
.acard .aava { width: 76px; height: 76px; flex: none; border-radius: 12px; object-fit: cover; border: 2px solid #d6e8f7; }
.acard .ainfo { flex: 1; min-width: 0; }
.acard h3 { margin: 0 0 2px; font-size: 17px; font-weight: 800; color: #1d3f60; }
.acard .arole { font-size: 12px; color: #5a7896; }
.acard .adesc { margin: 6px 0 8px; font-size: 12.5px; color: #46627c; line-height: 1.55; }
.wikichip {
  display: inline-flex; align-items: center; gap: 6px; padding: 5px 12px 5px 6px;
  border-radius: 999px; background: #e8f4ff; color: #2f5c85; font-size: 12px;
  font-weight: 700; text-decoration: none;
}
.wikichip img { width: 20px; height: 20px; border-radius: 6px; display: block; }
.cap.on { background: #2f5c85; color: #fff; }
.glist {
  overflow: auto;
  display: grid;
  gap: 12px;
  align-content: start;
  padding-right: 4px;
}
.grow {
  display: grid;
  grid-template-columns: 96px 1fr auto;
  gap: 18px;
  align-items: center;
  padding: 12px 18px 12px 12px;
  border-radius: 14px;
  background: #fff;
  box-shadow: 0 4px 12px rgba(20, 60, 100, 0.16);
  cursor: pointer;
}
.grow:hover { box-shadow: 0 8px 20px rgba(20, 60, 100, 0.24); }
.gava {
  position: relative;
  width: 96px;
  height: 96px;
  border-radius: 14px;
  overflow: hidden;
  background: linear-gradient(150deg, #cfe6f8, #a8cbe8);
  box-shadow: inset 0 0 0 3px #fff, 0 2px 6px rgba(20, 60, 100, 0.2);
  display: grid;
  place-items: center;
}
.gava img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; z-index: 2; }
.gava b { position: relative; z-index: 1; font-size: 34px; color: #fff; font-weight: 800; }
.gava.plain b { z-index: 2; }
.gava.big { width: 68px; height: 68px; border-radius: 12px; }
.gava.big b { font-size: 26px; }
.ginfo h3 { margin: 0 0 6px; font-size: 26px; font-weight: 800; color: #1f4a78; letter-spacing: 0.02em; }
.ginfo ul { margin: 0; padding: 0; list-style: none; display: grid; gap: 4px; }
.ginfo li { display: flex; gap: 14px; font-size: 15px; }
.ginfo li span { width: 62px; color: #6f8ca6; }
.ginfo li em { font-style: normal; color: #23425f; font-weight: 700; }
.gside { display: grid; justify-items: end; gap: 10px; }
.cap {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  height: 30px;
  padding: 0 12px;
  border-radius: 6px;
  background: #24507f;
  color: #eaf4ff;
  font-size: 15px;
  font-weight: 700;
  clip-path: polygon(4% 0, 100% 0, 96% 100%, 0 100%);
}
.cap .hh { color: #f28ba8; font-style: normal; }
.visit {
  width: 104px;
  height: 42px;
  border: 0;
  border-radius: 8px;
  background: linear-gradient(180deg, #6fc4f2, #3f9ee0);
  color: #fff;
  font-size: 18px;
  font-weight: 800;
  cursor: pointer;
  clip-path: polygon(5% 0, 100% 0, 95% 100%, 0 100%);
  box-shadow: 0 3px 0 rgba(20, 70, 120, 0.25);
}
.visit:hover { filter: brightness(1.06); }
.empty { text-align: center; color: #3f6c96; padding: 30px 0; }
.gfoot { display: flex; justify-content: flex-end; gap: 12px; }


/* ── 好友管理 ── */
.friends {
  position: relative;
  z-index: 2;
  width: min(1320px, 94vw);
  height: min(760px, 84vh);
  display: grid;
  grid-template-columns: 260px 1fr;
  gap: 16px;
}
.frail { display: grid; align-content: start; gap: 8px; padding-top: 60px; }
.ftab {
  height: 56px;
  padding: 0 20px;
  text-align: left;
  border: 0;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.94);
  color: #24588f;
  font-size: 19px;
  font-weight: 700;
  cursor: pointer;
  clip-path: polygon(0 0, 100% 0, 97% 100%, 0 100%);
  box-shadow: 0 4px 12px rgba(20, 60, 100, 0.18);
}
.ftab.on {
  background: linear-gradient(180deg, #2f6fa8, #1f4a78);
  color: #ffd964;
  text-shadow: 0 1px 0 rgba(0, 0, 0, 0.25);
}
.fmain {
  display: grid;
  grid-template-rows: auto 1fr;
  gap: 12px;
  padding: 16px;
  border-radius: 16px;
  background: linear-gradient(180deg, rgba(186, 220, 246, 0.9), rgba(160, 203, 238, 0.9));
  box-shadow: inset 0 0 0 2px rgba(255, 255, 255, 0.55), 0 18px 44px rgba(4, 20, 44, 0.34);
}
.fhead { display: flex; align-items: center; gap: 12px; }
.fcount { font-size: 20px; font-weight: 700; color: #1f4a78; }
.fcount b { color: #d9731f; }
.fsort { margin-left: auto; display: flex; gap: 10px; }
.ghost.icon { width: 54px; padding: 0; font-size: 18px; }
.flist { overflow: auto; display: grid; gap: 12px; align-content: start; padding-right: 4px; }
.frow {
  display: grid;
  grid-template-columns: 96px 1fr auto;
  gap: 18px;
  align-items: center;
  padding: 12px 18px 12px 12px;
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 4px 12px rgba(20, 60, 100, 0.18), inset 0 0 0 2px rgba(150, 195, 230, 0.5);
}
.fava {
  position: relative;
  width: 96px;
  height: 96px;
  border-radius: 10px;
  overflow: hidden;
  background: linear-gradient(150deg, #cfe6f8, #a8cbe8);
  box-shadow: inset 0 0 0 3px #fff;
  display: grid;
  place-items: center;
}
.fava img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; z-index: 2; }
.fava b { position: relative; z-index: 1; font-size: 34px; color: #fff; font-weight: 800; }
.fava .info {
  position: absolute;
  right: 4px;
  bottom: 4px;
  z-index: 3;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #fff;
  color: #2f6fa8;
  font-size: 13px;
  font-weight: 800;
  display: grid;
  place-items: center;
  box-shadow: 0 1px 4px rgba(20, 60, 100, 0.3);
}
.finfo h3 { margin: 0 0 6px; font-size: 20px; font-weight: 700; color: #24588f; }
.finfo h3 em { font-style: normal; font-size: 24px; font-weight: 800; color: #1f4a78; margin-left: 10px; }
.finfo ul { margin: 0; padding: 0; list-style: none; display: grid; gap: 4px; }
.finfo li { display: flex; gap: 16px; font-size: 15px; }
.finfo li span { width: 76px; color: #6f8ca6; }
.finfo li em { font-style: normal; color: #23425f; font-weight: 700; }
.fside { display: grid; justify-items: end; gap: 10px; }
.tip {
  margin: 0 0 10px;
  padding: 8px 14px;
  border-radius: 10px;
  background: rgba(46, 120, 178, 0.12);
  color: #2f6d9e;
  font-size: 13px;
}
.chip {
  padding: 3px 14px;
  border-radius: 6px;
  background: #eef5fb;
  box-shadow: inset 0 0 0 1px rgba(150, 195, 230, 0.8);
  color: #5f86a8;
  font-size: 13px;
}
.visit.del { width: 118px; background: linear-gradient(180deg, #dbeaf7, #b9d6ee); color: #2f6fa8; }

/* ── 群详情 ── */
.modal {
  position: absolute;
  inset: 0;
  z-index: 5;
  display: grid;
  place-items: center;
  background: rgba(6, 22, 46, 0.55);
  backdrop-filter: blur(4px);
}
.sheet {
  width: min(760px, 88vw);
  padding: 18px;
  border-radius: 18px;
  background: #fff;
  box-shadow: 0 24px 60px rgba(4, 20, 44, 0.45);
}
.sheet header { display: flex; align-items: center; gap: 14px; }
.sheet header h3 { margin: 0; font-size: 22px; color: #1f4a78; }
.sheet header p { margin: 4px 0 0; font-size: 13px; color: #7f95aa; }
.sheet .x {
  margin-left: auto;
  width: 34px;
  height: 34px;
  border: 0;
  border-radius: 50%;
  background: #eef5fb;
  color: #5b7e9e;
  font-size: 15px;
  cursor: pointer;
}
.stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin: 16px 0; }
.stats div {
  display: grid;
  justify-items: center;
  gap: 2px;
  padding: 10px 0;
  border-radius: 12px;
  background: #f1f8fe;
}
.stats b { font-size: 20px; color: #24588f; }
.stats span { font-size: 12px; color: #7f95aa; }
.last, .members { margin-top: 10px; }
.last .k, .members .k { font-size: 12px; font-weight: 700; color: #7f95aa; letter-spacing: 0.06em; }
.last p {
  margin: 6px 0 0;
  padding: 10px 12px;
  border-radius: 10px;
  background: #f1f8fe;
  font-size: 14px;
  color: #2b4a68;
  line-height: 1.6;
}
.last p b { color: #24588f; margin-right: 8px; }
.tags { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.tags span {
  padding: 4px 10px;
  border-radius: 999px;
  background: #eef6fd;
  color: #3f6c96;
  font-size: 12px;
}
.tags .more { background: #24588f; color: #fff; }

.frow.clickable {
  cursor: pointer;
  transition: transform 0.14s, box-shadow 0.14s;
}
.frow.clickable:hover {
  transform: translateY(-1px);
  box-shadow: 0 10px 22px rgba(30, 80, 130, 0.18);
}
.chip.okc {
  background: rgba(70, 192, 138, 0.16);
  color: #2b8a63;
  border-color: rgba(70, 192, 138, 0.4);
}
.chip.waitc {
  background: rgba(245, 185, 66, 0.18);
  color: #9a6a10;
  border-color: rgba(245, 185, 66, 0.45);
}
.fsearch {
  padding: 14px 18px 6px;
  flex: 1;
  align-self: flex-start;
  width: 100%;
}
.sbar {
  display: flex;
  gap: 10px;
  margin-bottom: 14px;
}
.sbar input {
  flex: 1;
  height: 42px;
  padding: 0 16px;
  border: 1px solid #cfe0ee;
  border-radius: 10px;
  font-size: 15px;
  color: #244a72;
  background: #fff;
  outline: none;
}
.sbar input:focus {
  border-color: #7fb4e0;
  box-shadow: 0 0 0 3px rgba(127, 180, 224, 0.18);
}
.found {
  align-items: center;
}
.fdet {
  position: absolute;
  inset: 0;
  z-index: 6;
  display: grid;
  place-items: center;
  background: rgba(8, 24, 44, 0.42);
  backdrop-filter: blur(2px);
}
.fdet-in {
  position: relative;
  width: min(520px, 88%);
  max-height: 86%;
  overflow-y: auto;
  padding: 22px 24px 20px;
  border-radius: 16px;
  background: #fff;
  box-shadow: 0 26px 60px rgba(4, 20, 40, 0.38);
}
.fdet-x {
  position: absolute;
  right: 14px;
  top: 12px;
  width: 30px;
  height: 30px;
  border: 0;
  border-radius: 50%;
  background: #eef5fb;
  color: #4a6d92;
  font-size: 14px;
  cursor: pointer;
}
.fdet-head {
  text-align: center;
  padding-bottom: 14px;
  border-bottom: 1px dashed #dbe8f3;
}
.fdet-ava {
  position: relative;
  display: inline-block;
  width: 86px;
  height: 86px;
  border-radius: 50%;
  overflow: hidden;
  background: #d8e9f7;
  border: 3px solid #fff;
  box-shadow: 0 6px 16px rgba(30, 70, 110, 0.22);
}
.fdet-ava img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  z-index: 2;
}
.fdet-ava b {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  font-size: 34px;
  color: #4b7bab;
  z-index: 1;
}
.fdet-head h4 {
  margin: 10px 0 2px;
  font-size: 20px;
  color: #1f3a5c;
}
.fdet-head p {
  margin: 0;
  font-size: 12.5px;
  color: #7d93aa;
}
.fdet-heart {
  display: inline-block;
  margin-top: 8px;
  padding: 3px 12px;
  border-radius: 999px;
  background: #fde8ef;
  color: #d8547f;
  font-size: 12px;
  font-weight: 700;
}
.fdet-kv {
  list-style: none;
  margin: 14px 0 0;
  padding: 0;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px 18px;
}
.fdet-kv li {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  padding: 6px 0;
  border-bottom: 1px solid #f0f5fa;
}
.fdet-kv span {
  color: #7d93aa;
}
.fdet-kv em {
  font-style: normal;
  font-weight: 700;
  color: #23486e;
}
.fdet-note {
  margin-top: 14px;
  padding: 10px 14px;
  border-left: 3px solid #7fb4e0;
  background: #f6fafd;
  border-radius: 0 8px 8px 0;
}
.fdet-note b {
  display: block;
  font-size: 12px;
  color: #4f86b8;
  margin-bottom: 4px;
}
.fdet-note p {
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  color: #33536f;
}
.fdet-note p.ph {
  color: #5c7590;
}
</style>
