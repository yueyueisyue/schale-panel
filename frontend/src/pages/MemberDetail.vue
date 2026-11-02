<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import SpineShop from '@/components/SpineShop.vue'

const route = useRoute()
const router = useRouter()

const key = computed(() => String(route.params.key || 'mika'))
const tab = ref<'basic' | 'upgrade' | 'secret'>('basic')
const data = ref<any>(null)
const loading = ref(true)
const cardOpen = ref(false)
const personaOpen = ref(false)
const personaText = ref('')
const personaSource = ref('')
const personaUpdated = ref('')
const personaSaving = ref(false)
const secretShown = ref(false)
const toast = ref('')

const MODELS: Record<string, { dir: string; skel: string; atlas: string }> = {
  mika: { dir: '/live2d/mika-swim', skel: 'CH0294_home.skel', atlas: 'CH0294_home.atlas' },
  sora: { dir: '/live2d/sora-spr', skel: 'sora_spr.skel', atlas: 'sora_spr.atlas' },
  ayumu: { dir: '/live2d/ayumu-spr', skel: 'NP0013_spr.skel', atlas: 'NP0013_spr.atlas' },
  rin: { dir: '/live2d/rin-spr', skel: 'rin_spr.skel', atlas: 'rin_spr.atlas' },
  momoka: { dir: '/live2d/momoka-spr', skel: 'momoka_spr.skel', atlas: 'momoka_spr.atlas' },
  aoi: { dir: '/live2d/aoi-spr', skel: 'NP0032_spr.skel', atlas: 'NP0032_spr.atlas' },
  arona: { dir: '/live2d/arona-spr', skel: 'arona_spr.skel', atlas: 'arona_spr.atlas' },
  plana: { dir: '/live2d/plana-spr', skel: 'NP0035_spr.skel', atlas: 'NP0035_spr.atlas' },
}
const model = computed(() => MODELS[key.value] || MODELS.mika)

const EMO_LABEL: Record<string, { n: string; c: string }> = {
  joy: { n: '开心', c: '#f2a05a' },
  trust: { n: '信任', c: '#6fc98d' },
  fear: { n: '不安', c: '#8f9bd6' },
  surprise: { n: '意外', c: '#e2b34b' },
  sadness: { n: '低落', c: '#7fa8d8' },
  disgust: { n: '厌烦', c: '#b48fc4' },
  anger: { n: '生气', c: '#e2767f' },
  anticipation: { n: '期待', c: '#66b8e0' },
}

const emoRows = computed(() => {
  const raw = data.value?.persona?.emotions
  if (!raw) return []
  if (Array.isArray(raw)) return raw
  return Object.entries(raw).map(([k, v]) => ({
    k, label: EMO_LABEL[k]?.n || k, c: EMO_LABEL[k]?.c || '#7fc2e8', v: Number(v) || 0,
  }))
})

const bondRows = computed(() => {
  const b = data.value?.bond || {}
  return [
    { k: 'favor', n: '好感度', v: b.favor ?? 0, c: '#f2a05a' },
    { k: 'intimacy', n: '亲密度', v: b.intimacy ?? 0, c: '#f07fa8' },
    { k: 'trust', n: '信任', v: b.trust ?? 0, c: '#6fc98d' },
    { k: 'warmth', n: '温和度', v: b.warmth ?? 0, c: '#66b8e0' },
  ]
})

const innerRows = computed(() => {
  const v = data.value?.inner || {}
  return [
    { k: 'reliance', n: '依赖', v: v.reliance ?? 0, c: '#f07fa8' },
    { k: 'suppress', n: '压抑', v: v.suppress ?? 0, c: '#8f9bd6' },
    { k: 'possessive', n: '独占欲', v: v.possessive ?? 0, c: '#e2767f' },
    { k: 'lonely', n: '孤独', v: v.lonely ?? 0, c: '#7fa8d8' },
    { k: 'curiosity', n: '好奇', v: v.curiosity ?? 0, c: '#e2b34b' },
  ]
})

const STATS = [
  { k: '体力', v: '77301' }, { k: '攻击力', v: '5791' },
  { k: '防御力', v: '115' }, { k: '治疗力', v: '5541' },
]
const SKILLS = ['必杀技能', '基础技能', '被动技能+', '辅助技能']
const MATS = [
  { n: '初級', c: '54K' }, { n: '中級', c: '20K' },
  { n: '上級', c: '7757' }, { n: '最上級', c: '114' },
]

function authHeaders(): Record<string, string> {
  const t = localStorage.getItem('schale_token') || ''
  return t ? { Authorization: `Bearer ${t}` } : {}
}

async function ensureToken(): Promise<string> {
  let t = localStorage.getItem('schale_token') || ''
  if (t) return t
  try {
    const r = await fetch('/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password: 'CHANGE_ME' }),
    })
    if (r.ok) {
      const j = await r.json()
      if (j?.token) { localStorage.setItem('schale_token', j.token); t = j.token }
    }
  } catch { /* ignore */ }
  return t
}

async function load(force = false) {
  loading.value = true
  try {
    await ensureToken()
    const r = await fetch(`/api/member/${key.value}${force ? '?force=1' : ''}`, { headers: authHeaders() })
    if (r.ok) data.value = await r.json()
  } catch { /* ignore */ }
  loading.value = false
}

function say(msg: string) {
  toast.value = msg
  window.setTimeout(() => { toast.value = '' }, 2200)
}

function playVoice() {
  const src = `/voice/${key.value}-01.mp3`
  const a = new Audio(src)
  a.play().catch(() => say('还没有这位的语音包，先从游戏里导一下'))
}

async function openPersona() {
  personaOpen.value = true
  try {
    await ensureToken()
    const r = await fetch(`/api/persona/${key.value}`, { headers: authHeaders() })
    if (r.ok) {
      const j = await r.json()
      personaText.value = j.text || ''
      personaSource.value = j.source || ''
      personaUpdated.value = j.updated || ''
    }
  } catch { /* ignore */ }
}



function openSecret() {
  if (secretShown.value) return
  secretShown.value = true
  load()
}

onMounted(() => {
  load()
  const q = new URLSearchParams(location.search)
  const t = q.get('tab')
  if (t === 'upgrade' || t === 'secret' || t === 'basic') tab.value = t as any
  if (q.get('card') === '1') cardOpen.value = true
  if (q.get('persona') === '1') openPersona()
})
</script>

<template>
  <div class="md">
    <div class="md-bg"></div>

    <header class="md-hd">
      <button class="back" @click="router.push('/members')">‹</button>
      <h2>成员 ?</h2>
      <button class="x" @click="router.push('/home')">✕</button>
    </header>

    <!-- 左：立绘 -->
    <div class="stage">
      <SpineShop
        :key="key"
        :dir="model.dir"
        :skel="model.skel"
        :atlas="model.atlas"
        :fill="false"
        :anchor-y="1.0"
        :zoom="1.0"
      />
      <div class="lvbar">
        <span class="tag">★85</span>
        <b>{{ data?.basic?.name || '—' }}</b>
        <div class="bar"><i style="width:62%"></i></div>
        <span class="num">−1/52265</span>
      </div>
      <div class="tools">
        <button class="tb" title="信息卡" @click="cardOpen = true">
          <svg viewBox="0 0 24 24"><path d="M6 3h9l4 4v14H6z" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M9 9h6M9 13h6M9 17h4" stroke="currentColor" stroke-width="1.7"/></svg>
        </button>
        <button class="tb" title="人格卡" @click="openPersona">
          <svg viewBox="0 0 24 24">
            <rect x="3" y="8" width="13" height="9" rx="2" fill="none" stroke="currentColor" stroke-width="1.8"/>
            <circle cx="14" cy="12.5" r="0.9" fill="currentColor"/>
            <path d="M16.5 6.4a4.2 4.2 0 0 1 0 5.4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
            <path d="M19 4.6a7 7 0 0 1 0 9" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
            <path d="m17.6 15.4 2.4 2.4-2.4 2.4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>
        <button class="tb" title="语音" @click="playVoice">
          <svg viewBox="0 0 24 24"><path d="M5 10v4h3l4 4V6L8 10H5Z" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M16 8.5a5 5 0 0 1 0 7" fill="none" stroke="currentColor" stroke-width="1.8"/></svg>
        </button>
      </div>
    </div>

    <!-- 右：面板 -->
    <div class="panel">
      <nav class="tabs">
        <button :class="{ on: tab === 'basic' }" @click="tab = 'basic'">基本信息</button>
        <button :class="{ on: tab === 'upgrade' }" @click="tab = 'upgrade'">升级</button>
        <button :class="{ on: tab === 'secret' }" @click="tab = 'secret'; openSecret()">神秘解放</button>
      </nav>

      <!-- 基本信息：人格设定卡 -->
      <div v-if="tab === 'basic'" class="pane">
        <div class="band"><span>人格设定</span><em class="srch">{{ data?.basic?.club }}</em></div>

        <div class="pcard2">
          <div class="phead">
            <img class="pava2" :src="`/img/portrait/${key}.png`" :alt="data?.basic?.name" />
            <div class="pmeta2">
              <b class="pname">{{ data?.basic?.name }}</b>
              <span class="pen">{{ data?.basic?.en }}</span>
              <div class="pchips">
                <i>{{ data?.basic?.school }}</i>
                <i>{{ data?.basic?.club }}</i>
                <i v-if="data?.basic?.grade !== '—'">{{ data?.basic?.grade }}</i>
              </div>
            </div>
          </div>
          <p class="pint">{{ data?.intro }}</p>
        </div>

        <div class="prow2">
          <span class="pk">性格</span>
          <p class="pv">{{ data?.traits }}</p>
        </div>
        <div class="prow2">
          <span class="pk">说话方式</span>
          <p class="pv">{{ data?.persona?.attitude || '—' }}</p>
        </div>
        <div class="prow2">
          <span class="pk">和老师</span>
          <p class="pv">{{ data?.persona?.relationship || '—' }}</p>
        </div>

        <div class="band"><span>情绪切片</span></div>
        <div class="emobars">
          <div v-for="e in emoRows" :key="e.k" class="emo">
            <span class="en">{{ e.label || e.k }}</span>
            <div class="ebar"><i :style="{ width: Math.max(4, e.v || 0) + '%', background: e.c || '#7fc2e8' }"></i></div>
            <b class="ev">{{ e.v || 0 }}</b>
          </div>
          <p v-if="!emoRows.length" class="empty">还没有情绪记录</p>
        </div>

        <div class="band"><span>互动统计</span></div>
        <div class="statgrid">
          <div><span>总次数</span><b>{{ data?.persona?.stats?.total ?? 0 }}</b></div>
          <div><span>正面</span><b class="up">{{ data?.persona?.stats?.positive ?? 0 }}</b></div>
          <div><span>负面</span><b class="dn">{{ data?.persona?.stats?.negative ?? 0 }}</b></div>
          <div><span>群里发言</span><b>{{ data?.persona?.stats?.group ?? 0 }}</b></div>
        </div>

        <div v-if="(data?.persona?.phrases || []).length" class="phrases">
          <span class="pk">口头语</span>
          <ul>
            <li v-for="(t, i) in data.persona.phrases" :key="i">「{{ t }}」</li>
          </ul>
        </div>
      </div>

      <!-- 升级：相处量化 -->
      <div v-else-if="tab === 'upgrade'" class="pane">
        <div class="band"><span>相处数据</span><em class="srch">累计 {{ data?.bond?.talks ?? 0 }} 次</em></div>
        <p v-if="!data?.bond?.talks" class="empty-note">
          还没有和{{ data?.basic?.name || '她' }}的相处记录——这里只算你们两个人的账，不会借用别人的数据。
        </p>

        <div class="qbars">
          <div v-for="b in bondRows" :key="b.k" class="qbar">
            <span class="qn">{{ b.n }}</span>
            <div class="qtrack"><i :style="{ width: b.v + '%', background: b.c }"></i></div>
            <b class="qv">{{ b.v }}</b>
          </div>
        </div>

        <div class="statgrid three">
          <div><span>对话总次数</span><b>{{ data?.bond?.talks ?? 0 }}</b></div>
          <div><span>记忆碎片</span><b>{{ data?.bond?.memories ?? 0 }}</b></div>
          <div><span>正面占比</span><b class="up">{{ data?.bond?.warmth ?? 0 }}%</b></div>
        </div>

        <div class="band"><span>最近的心得</span></div>
        <div class="memo">
          <p v-if="loading">正在回想……</p>
          <ul v-else>
            <li v-for="(t, i) in (data?.upgrade || [])" :key="i">{{ t.replace(/^[·•]\s*/, '') }}</li>
          </ul>
          <button class="peek" @click="load(true)">重新整理</button>
        </div>
      </div>

      <!-- 神秘解放：内心量化 -->
      <div v-else class="pane">
        <div class="band"><span>内心读数</span><em class="srch">她自己看不到</em></div>
        <p v-if="!data?.bond?.talks" class="empty-note">
          还没聊过，读不出什么。这几条要等你们真正说上话才会动。
        </p>

        <div class="qbars">
          <div v-for="b in innerRows" :key="b.k" class="qbar">
            <span class="qn">{{ b.n }}</span>
            <div class="qtrack"><i :style="{ width: b.v + '%', background: b.c }"></i></div>
            <b class="qv">{{ b.v }}</b>
          </div>
        </div>

        <div class="lockrow">
          <div class="fav"><span>依赖度</span><b>{{ data?.inner?.reliance ?? 0 }}</b></div>
          <div class="fav"><span>坦白意愿</span><b>{{ data?.inner?.honesty ?? 0 }}</b></div>
        </div>

        <div class="secret">
          <h4>她不愿说出口的</h4>
          <p v-if="loading">……</p>
          <p v-else class="sec-text">{{ data?.secret || '（她还没准备好）' }}</p>
          <button class="peek" @click="load(true)">重新聆听</button>
        </div>
      </div>

    </div>

    <!-- 信息卡（图5） -->
    <div v-if="cardOpen" class="cardmask" @click="cardOpen = false">
      <div class="icard" @click.stop>
        <header><h3>简介</h3><button class="x" @click="cardOpen = false">✕</button></header>
        <div class="ibody">
          <div class="ileft">
            <div class="ihead">
              <img class="iava" :src="`/img/portrait/${key === 'mika' ? 'mika' : key}.png`" :alt="data?.basic?.name" />
              <div class="imeta">
                <span class="iclub">{{ data?.basic?.club }} · {{ data?.basic?.grade }}</span>
                <b class="iname">{{ data?.basic?.name }}</b>
              </div>
            </div>
            <div class="iband">基本信息</div>
            <p class="iintro">{{ data?.intro }}</p>
          </div>
          <ul class="iright">
            <li><span>生日</span><b>{{ data?.basic?.birth }}</b></li>
            <li><span>身高</span><b>{{ data?.basic?.height }}</b></li>
            <li><span>兴趣</span><b>{{ data?.basic?.hobby }}</b></li>
            <li><span>设计</span><b>{{ data?.basic?.design }}</b></li>
            <li><span>绘制</span><b>{{ data?.basic?.art }}</b></li>
            <li><span>配音</span><b>{{ data?.basic?.cv }}</b></li>
          </ul>
        </div>
      </div>
    </div>

    <!-- 人格卡（只读查看） -->
    <div v-if="personaOpen" class="cardmask" @click="personaOpen = false">
      <div class="pedit" @click.stop>
        <header class="phd-row">
          <h3>人格卡 · {{ data?.basic?.name || '—' }}</h3>
          <span class="ptag on">{{ personaSource === 'astrbot' ? 'AstrBot 原生' : '面板默认' }}</span>
          <button class="x" @click="personaOpen = false">✕</button>
        </header>
        <p class="phint">
          这只是<b>查看</b>。人格卡以 AstrBot 里那张为准，面板不会改它，也不会在它后面追加任何东西。
          要改请在 AstrBot 后台改，这里只负责让你看见她到底被写成了什么样。
        </p>
        <div class="pmeta-row">
          <span>共 {{ (personaText || '').length }} 字</span>
          <span v-if="personaUpdated">最后更新 {{ personaUpdated }}</span>
        </div>
        <pre class="psrc">{{ personaText || '读取中……' }}</pre>
        <footer class="pfoot-row">
          <button class="ok" @click="personaOpen = false">知道了</button>
        </footer>
      </div>
    </div>

    <div v-if="toast" class="toast">{{ toast }}</div>
  </div>
</template>

<style scoped>
.md { position: fixed; inset: 0; overflow: hidden; }
.md-bg {
  position: absolute; inset: 0;
  background: linear-gradient(150deg, #cfe9fb 0%, #b9dcf6 45%, #dff0fd 100%);
}
.md-bg::after {
  content: ''; position: absolute; inset: 0;
  background: radial-gradient(ellipse 55% 45% at 20% 20%, rgba(255,255,255,.8), transparent 62%);
}
.md-hd { position: relative; z-index: 3; display: flex; align-items: center; gap: 14px; padding: 14px 22px; }
.md-hd h2 { margin: 0; font-size: 22px; font-weight: 800; color: #1d3f60; }
.back {
  width: 34px; height: 34px; border: none; border-radius: 50%; cursor: pointer;
  background: rgba(255,255,255,.85); color: #2c5d8f; font-size: 20px; line-height: 1;
  box-shadow: 0 3px 10px rgba(40,82,122,.16);
}
.x { margin-left: auto; width: 32px; height: 32px; border: none; border-radius: 9px; background: rgba(255,255,255,.8); color: #35618c; cursor: pointer; }

.stage { position: absolute; left: 0; top: 56px; bottom: 0; width: 42%; z-index: 2; }
.lvbar {
  position: absolute; left: 18px; right: 18px; bottom: 16px; display: grid;
  grid-template-columns: auto auto 1fr auto; gap: 10px; align-items: center;
  padding: 9px 14px; border-radius: 10px; color: #fff;
  background: linear-gradient(120deg, rgba(12,34,62,.9), rgba(20,54,92,.7));
}
.lvbar .tag { padding: 2px 7px; border-radius: 6px; background: #ffcf4d; color: #4a3410; font-size: 11px; font-weight: 800; }
.lvbar b { font-size: 14px; }
.lvbar .bar { height: 5px; border-radius: 3px; background: rgba(255,255,255,.22); overflow: hidden; }
.lvbar .bar i { display: block; height: 100%; background: linear-gradient(90deg, #7fc3f5, #4d92dd); }
.lvbar .num { font-size: 10.5px; color: rgba(216,236,255,.8); }
.tools { position: absolute; left: 18px; bottom: 74px; display: flex; gap: 10px; }
.tb {
  width: 40px; height: 40px; display: grid; place-items: center; cursor: pointer;
  border: none; border-radius: 10px; background: rgba(255,255,255,.92); color: #2c5d8f;
  box-shadow: 0 4px 12px rgba(40,82,122,.18);
}
.tb svg { width: 20px; height: 20px; }

.panel {
  position: relative; z-index: 2; margin-left: 42%; height: calc(100% - 56px);
  display: flex; flex-direction: column; padding: 0 20px 16px; overflow: hidden;
}
.tabs { display: flex; gap: 8px; margin-bottom: 10px; }
.tabs button {
  flex: 1; padding: 11px 0; border: none; cursor: pointer;
  background: rgba(255,255,255,.72); color: #3f6b93; font-size: 15px; font-weight: 700;
  clip-path: polygon(6% 0, 100% 0, 94% 100%, 0 100%);
}
.tabs button.on { background: #fff; color: #1d3f60; box-shadow: 0 0 0 2px #7cc0ec inset; }
.pane { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; }
.band {
  display: flex; justify-content: space-between; align-items: center;
  padding: 7px 14px; border-radius: 7px; color: #eaf5ff;
  background: linear-gradient(90deg, #2c5d8f, #4a86bd); font-size: 13px; font-weight: 700; letter-spacing: .12em;
}
.band .srch { font-style: normal; font-size: 11.5px; opacity: .85; letter-spacing: 0; }
.stats {
  display: grid; grid-template-columns: 1fr 1fr 96px; gap: 8px 18px;
  padding: 12px 14px; border-radius: 10px; background: #fff;
  box-shadow: 0 2px 8px rgba(40,82,122,.1);
}
.stats > div { display: flex; justify-content: space-between; font-size: 13.5px; color: #4d7797; }
.stats > div b { color: #1d3f60; font-size: 15px; }
.stats .lock { grid-column: 3; grid-row: 1 / span 2; border: none; border-radius: 8px; background: #2f5c85; color: #fff; font-size: 12px; cursor: pointer; line-height: 1.4; }
.skills { display: flex; gap: 8px; align-items: center; padding: 10px; border-radius: 10px; background: #fff; }
.sk { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 4px; font-size: 11px; color: #4d7797; }
.sk .hex { width: 34px; height: 34px; background: #e7b23c; clip-path: polygon(50% 0, 100% 25%, 100% 75%, 50% 100%, 0 75%, 0 25%); }
.sk em { font-style: normal; font-size: 10px; color: #8fabc4; }
.act { width: 64px; padding: 10px 0; border: none; border-radius: 8px; background: #62b8e8; color: #fff; font-size: 12px; font-weight: 700; cursor: pointer; line-height: 1.35; }
.wpn { display: flex; align-items: center; gap: 12px; padding: 10px 14px; border-radius: 10px; background: #fff; }
.wpn .tl { font-size: 13px; color: #4d7797; }
.wpn-body { flex: 1; display: flex; align-items: center; gap: 10px; }
.wlv { font-size: 11.5px; color: #4d7797; }
.gun { flex: 1; height: 14px; border-radius: 3px; background: linear-gradient(90deg, #2f5c85, #6a4d8f 60%, #2f5c85); }
.stars { color: #f0b23c; font-size: 12px; }
.gear { display: flex; gap: 8px; align-items: center; padding: 10px; border-radius: 10px; background: #fff; }
.slot { position: relative; flex: 1; display: flex; flex-direction: column; align-items: center; gap: 3px; padding: 6px; border-radius: 8px; background: #eef6fd; }
.slot .g { font-size: 10px; color: #4d7797; }
.slot .ic { width: 34px; height: 34px; border-radius: 7px; background: radial-gradient(circle, #d9b06a, #a8792f); }
.slot b { font-size: 10.5px; color: #2f5c85; }
.slot.empty { color: #9fbad2; font-size: 12px; justify-content: center; }
.traits { margin: 0; padding: 10px 14px; border-radius: 10px; background: #fff; font-size: 13px; color: #22405e; line-height: 1.6; }

.pcard2 { padding: 14px 16px; border-radius: 12px; background: #fff; box-shadow: 0 2px 10px rgba(40,82,122,.1); }
.phead { display: flex; gap: 14px; align-items: center; }
.pava2 { width: 84px; height: 84px; flex: none; border-radius: 12px; object-fit: cover; object-position: center 10%; border: 2px solid #d6e8f7; }
.pmeta2 { display: flex; flex-direction: column; gap: 4px; }
.pname { font-size: 24px; font-weight: 800; color: #1d3f60; line-height: 1.1; }
.pen { font-size: 12px; color: #7f9cb6; letter-spacing: .06em; }
.pchips { display: flex; gap: 6px; flex-wrap: wrap; }
.pchips i { padding: 3px 10px; border-radius: 999px; background: #eaf4fd; color: #2b5f92; font-size: 11.5px; font-style: normal; font-weight: 700; }
.pint { margin: 12px 0 0; font-size: 13.5px; color: #22405e; line-height: 1.8; }
.prow2 { display: flex; gap: 12px; padding: 11px 16px; border-radius: 10px; background: #fff; }
.prow2 .pk, .phrases .pk { width: 64px; flex: none; font-size: 13px; color: #5a7896; }
.prow2 .pv { margin: 0; font-size: 13.5px; color: #22405e; line-height: 1.6; }
.emobars { display: flex; flex-direction: column; gap: 8px; padding: 12px 16px; border-radius: 10px; background: #fff; }
.emo { display: grid; grid-template-columns: 56px 1fr 34px; gap: 10px; align-items: center; }
.emo .en { font-size: 12px; color: #5a7896; }
.ebar { height: 9px; border-radius: 5px; background: #eef5fc; overflow: hidden; }
.ebar i { display: block; height: 100%; border-radius: 5px; }
.emo .ev { font-size: 12px; color: #46627c; text-align: right; }
.empty { margin: 0; font-size: 12.5px; color: #8fabc4; }
.statgrid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
.statgrid > div { display: flex; flex-direction: column; gap: 3px; padding: 11px 14px; border-radius: 10px; background: #fff; }
.statgrid span { font-size: 11.5px; color: #6b8aa6; }
.statgrid b { font-size: 19px; color: #1d3f60; }
.statgrid b.up { color: #2f9e6b; }
.statgrid b.dn { color: #d1667f; }
.phrases { display: flex; gap: 12px; padding: 12px 16px; border-radius: 10px; background: #fff; }
.phrases ul { margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column; gap: 6px; }
.phrases li { font-size: 13px; color: #22405e; }
.empty-note { margin: 0; padding: 10px 14px; border-radius: 10px; background: #eef6fd; font-size: 12.5px; color: #4d7797; line-height: 1.6; }
.qbars { display: flex; flex-direction: column; gap: 11px; padding: 14px 16px; border-radius: 12px; background: #fff; }
.qbar { display: grid; grid-template-columns: 70px 1fr 38px; gap: 12px; align-items: center; }
.qn { font-size: 13px; color: #5a7896; }
.qtrack { height: 11px; border-radius: 6px; background: #eef5fc; overflow: hidden; }
.qtrack i { display: block; height: 100%; border-radius: 6px; transition: width .5s ease; }
.qv { font-size: 14px; color: #1d3f60; text-align: right; }
.statgrid.three { grid-template-columns: repeat(3, 1fr); }
.grow { display: flex; flex-direction: column; gap: 6px; padding: 12px 14px; border-radius: 10px; background: #fff; }
.grow-row { display: flex; align-items: center; gap: 12px; font-size: 13px; color: #4d7797; }
.grow-row b { color: #1d3f60; font-size: 14px; }
.grow-row .r { margin-left: auto; }
.grow-row .bar { flex: 1; height: 8px; border-radius: 4px; background: #2b3d52; overflow: hidden; }
.grow-row .bar i { display: block; height: 100%; background: linear-gradient(90deg, #7fc3f5, #4d92dd); }
.grow-row em { font-style: normal; font-size: 11px; color: #6b8aa6; }
.stars5 { color: #f0b23c; letter-spacing: 2px; }
.mats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
.mat { position: relative; display: flex; flex-direction: column; align-items: center; gap: 4px; padding: 8px; border-radius: 9px; background: #fff; }
.mat .clip { width: 36px; height: 42px; border-radius: 6px; background: linear-gradient(160deg, #cfe6f8, #7fb6e0); }
.mat .cnt { font-size: 10.5px; color: #4d7797; }
.mat b { width: 100%; text-align: center; padding: 2px 0; border-radius: 5px; background: #2b3d52; color: #fff; font-size: 11px; }
.upfoot { display: flex; gap: 10px; align-items: center; }
.coin { flex: 1; padding: 9px 14px; border-radius: 8px; background: #2b3d52; color: #ffd66b; font-size: 13px; }
.auto { padding: 10px 18px; border: none; border-radius: 8px; background: #8ed3f2; color: #fff; font-weight: 700; cursor: pointer; line-height: 1.35; }
.up { flex: 1; padding: 12px 0; border: none; border-radius: 8px; background: #dfe9f2; color: #7f9cb6; font-size: 15px; font-weight: 800; cursor: pointer; }
.memo { padding: 12px 16px; border-radius: 10px; background: #fff; }
.memo h4, .secret h4 { margin: 0 0 8px; font-size: 13px; color: #2f5c85; letter-spacing: .08em; }
.memo ul { margin: 0; padding-left: 0; list-style: none; display: flex; flex-direction: column; gap: 8px; }
.memo li { position: relative; padding-left: 16px; font-size: 13.5px; color: #22405e; line-height: 1.65; }
.memo li::before { content: '·'; position: absolute; left: 3px; color: #62b8e8; font-weight: 800; }
.lockrow { display: flex; gap: 10px; }
.nolock { flex: 1; padding: 14px; border: none; border-radius: 9px; background: #c9d6e2; color: #5b7c99; font-size: 14px; font-weight: 700; }
.fav { flex: 1; padding: 8px 14px; border-radius: 9px; background: #fff; }
.fav span { display: block; font-size: 11px; color: #6b8aa6; }
.fav b { font-size: 15px; color: #1d3f60; }
.cap { margin-top: 4px; padding: 26px 0; border-radius: 10px; background: #c9d6e2; color: #5b7c99; font-size: 17px; font-weight: 800; text-align: center; letter-spacing: .1em; }
.secret { padding: 14px 16px; border-radius: 10px; background: #fff; }
.sec-text { margin: 0 0 10px; font-size: 14px; color: #22405e; line-height: 1.85; white-space: pre-wrap; }
.peek { padding: 8px 16px; border: none; border-radius: 8px; background: #eef5fc; color: #3f6b93; font-size: 12.5px; font-weight: 700; cursor: pointer; }

.pedit {
  width: min(760px, calc(100vw - 80px));
  max-height: calc(100vh - 90px);
  display: flex; flex-direction: column;
  padding: 18px 20px 14px; border-radius: 14px; background: #f7fbff;
  box-shadow: 0 24px 60px rgba(6,24,46,.45); overflow-y: auto;
}
.pedit header { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
.pedit h3 { margin: 0; font-size: 16px; font-weight: 800; color: #1d3f60; }
.pedit .ptag { padding: 2px 9px; border-radius: 999px; background: #e7f1fb; color: #5a7896; font-size: 11px; font-weight: 700; }
.pedit .ptag.on { background: #ffe6ef; color: #c2416b; }
.pedit .x { margin-left: auto; }
.plabel { margin: 8px 0 5px; font-size: 12px; font-weight: 700; color: #3f6b93; letter-spacing: .04em; }
.pedit textarea.small { height: 96px; }
.psrc {
  margin: 0; padding: 14px 16px; max-height: 46vh; overflow: auto;
  border: 1.5px solid #cfe4f6; border-radius: 10px; background: #fff;
  font: 400 13px/1.78 'Microsoft YaHei', 'PingFang SC', system-ui, sans-serif;
  color: #22405e; white-space: pre-wrap; word-break: break-word;
}
.pmeta-row { display: flex; gap: 16px; margin: 0 0 8px; font-size: 12px; color: #6b8aa6; }
.pfoot-row { display: flex; justify-content: flex-end; margin-top: 12px; }
.phint { margin: 0 0 10px; font-size: 12px; color: #6b8aa6; line-height: 1.6; }
.pedit textarea {
  width: 100%; box-sizing: border-box; flex: none;
  height: 300px; resize: vertical; padding: 12px 14px;
  border: 1.5px solid #cfe4f6; border-radius: 10px; background: #fff;
  font: 400 13.5px/1.72 'Microsoft YaHei', 'PingFang SC', system-ui, sans-serif;
  color: #22405e; outline: none;
}
.pedit footer { display: flex; justify-content: flex-end; gap: 10px; margin-top: 12px; }
.pedit footer button { min-width: 116px; padding: 10px 0; border: none; border-radius: 9px; font-size: 13.5px; font-weight: 700; cursor: pointer; }
.cardmask { position: fixed; inset: 0; z-index: 40; display: grid; place-items: center; background: rgba(10,30,54,.45); }
.icard { width: min(900px, calc(100vw - 80px)); border-radius: 14px; background: #f7fbff; overflow: hidden; box-shadow: 0 24px 60px rgba(6,24,46,.45); }
.icard header { position: relative; display: grid; place-items: center; padding: 12px; background: #dceefb; }
.icard h3 { margin: 0; font-size: 17px; font-weight: 800; color: #1d3f60; }
.icard header .x { position: absolute; right: 12px; top: 10px; margin: 0; }
.ibody { display: grid; grid-template-columns: 1fr 300px; gap: 16px; padding: 16px; }
.ihead { display: flex; gap: 12px; align-items: center; margin-bottom: 10px; }
.iava { width: 76px; height: 76px; border-radius: 9px; object-fit: cover; object-position: center 12%; border: 2px solid #d6e8f7; }
.imeta { display: flex; flex-direction: column; gap: 4px; }
.iclub { font-size: 12px; color: #4d7797; }
.iname { font-size: 26px; font-weight: 800; color: #1d3f60; }
.iband { padding: 6px 12px; border-radius: 7px; background: linear-gradient(90deg, #2c5d8f, #4a86bd); color: #eaf5ff; font-size: 12.5px; font-weight: 700; letter-spacing: .12em; text-align: center; }
.iintro { margin: 10px 0 0; font-size: 13.5px; color: #22405e; line-height: 1.8; }
.iright { list-style: none; margin: 0; padding: 0 0 0 12px; border-left: 1px solid #dbeaf7; }
.iright li { display: flex; justify-content: space-between; padding: 8px 2px; border-bottom: 1px solid #eef5fc; font-size: 13px; }
.iright span { color: #5a7896; }
.iright b { color: #1d3f60; }
.toast {
  position: fixed; left: 50%; bottom: 90px; transform: translateX(-50%); z-index: 50;
  padding: 9px 18px; border-radius: 9px; background: rgba(18,44,74,.9); color: #fff; font-size: 13px;
}
</style>
