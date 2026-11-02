<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import SpineShop from '@/components/SpineShop.vue'

const emit = defineEmits<{ (e: 'close'): void }>()

type Kind = 'daily' | 'weekly' | 'achievement' | 'challenge'
interface Task {
  id: string
  kind: Kind
  title: string
  progress: number
  target: number
  percent: number
  done: boolean
  deadline?: string
  note?: string
  reward?: number
  rewardIcon?: string
  doneAt?: string
}

const TOKEN_KEY = 'schale_token'
const DEV_PWD = 'CHANGE_ME'

const tabs: { key: 'all' | Kind; label: string }[] = [
  { key: 'all', label: '全部' },
  { key: 'daily', label: '每日' },
  { key: 'weekly', label: '每周' },
  { key: 'achievement', label: '成就' },
  { key: 'challenge', label: '挑战' },
]
const KIND_LABEL: Record<Kind, string> = {
  daily: '每日',
  weekly: '每周',
  achievement: '成就',
  challenge: '挑战',
}

const tab = ref<'all' | Kind>('all')
const items = ref<Task[]>([])
const loading = ref(false)
const editing = ref<Task | null>(null)
const reward = ref<Task | null>(null)

const KEEPER = ref('琳')
const CAST = ref<any[]>([])
// 不在任务页出现的模型：小空·店服（自带收银台，留给商店）、阿罗娜
const HIDDEN = ['/live2d/sora-shop', '/live2d/arona-spr']
const cast = ref(Number(new URLSearchParams(location.search).get('cast') || 0))
onMounted(async () => {
  try {
    const r = await fetch('/live2d/models.json')
    const list = await r.json()
    if (Array.isArray(list) && list.length) CAST.value = list.filter((m: any) => !HIDDEN.includes(m.dir))
  } catch {
    /* 兜底留空 */
  }
})
const router = useRouter()
function back() {
  emit('close')
  router.replace('/home')
}
function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape') back()
}
onMounted(() => window.addEventListener('keydown', onKey))
onUnmounted(() => window.removeEventListener('keydown', onKey))
const current = computed(() => CAST.value[cast.value] || { name: '', key: '' })
const LINE = ref('这是待处理的事务清单……那就拜托您了。')
const LINES = [
  '这是待处理的事务清单……那就拜托您了。',
  '老师，这些已经帮您核对过啦。',
  '完成了……？好、好快啊……！',
  '还有几项没勾掉，要我提醒您吗？',
]

const shown = computed(() =>
  tab.value === 'all' ? items.value : items.value.filter((t) => t.kind === tab.value),
)
const doneAll = computed(() => items.value.filter((t) => t.done).length)
const dailyDone = computed(() => items.value.filter((t) => t.kind === 'daily' && t.done).length)
const dailyTotal = computed(() => items.value.filter((t) => t.kind === 'daily').length)

function authHeaders(): Record<string, string> {
  const t = localStorage.getItem(TOKEN_KEY)
  return t ? { Authorization: 'Bearer ' + t } : {}
}
async function ensureToken() {
  if (localStorage.getItem(TOKEN_KEY)) return
  const r = await fetch('/api/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password: DEV_PWD }),
  })
  const j = await r.json()
  if (j?.token) localStorage.setItem(TOKEN_KEY, j.token)
}
async function get(path: string) {
  const r = await fetch(path, { headers: authHeaders() })
  return r.json()
}
async function post(path: string, body: any) {
  const r = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  })
  return r.json()
}

async function load() {
  loading.value = true
  try {
    await ensureToken()
    const j = await get('/api/tasks')
    if (j?.ok) items.value = j.items || []
  } finally {
    loading.value = false
  }
}

function newTask() {
  editing.value = {
    id: '',
    kind: tab.value === 'all' ? 'daily' : tab.value,
    title: '',
    progress: 0,
    target: 1,
    percent: 0,
    done: false,
    deadline: '',
    note: '',
    reward: 3,
    rewardIcon: 'gem',
  }
}

async function saveTask() {
  const t = editing.value
  if (!t) return
  const j = await post('/api/tasks/upsert', {
    id: t.id,
    kind: t.kind,
    title: t.title,
    target: t.target,
    progress: t.progress,
    deadline: t.deadline,
    note: t.note,
    reward: t.reward,
    rewardIcon: t.rewardIcon,
  })
  if (j?.ok) items.value = j.items
  editing.value = null
  LINE.value = LINES[1]
}

async function removeTask(t: Task) {
  const j = await post('/api/tasks/delete', { id: t.id })
  if (j?.ok) items.value = j.items
}

async function finish(t: Task) {
  const j = await post('/api/tasks/toggle', { id: t.id })
  if (j?.ok) {
    items.value = j.items
    const now = items.value.find((x) => x.id === t.id)
    if (now?.done) {
      reward.value = now
      LINE.value = LINES[2]
    }
  }
}

function rewardIcon(u?: string) {
  if (u === 'ap') return '/img/currency/ap.webp'
  if (u === 'credit') return '/img/currency/credit.webp'
  return '/img/currency/gem.webp'
}

// 工作栏底图：楼上办公室昼夜一对，按现实时间切换（?hour= 可强制）
const veilBg = computed(() => {
  const forced = new URLSearchParams(location.search).get('hour')
  const h = forced !== null ? Number(forced) : new Date().getHours()
  const night = h < 6 || h >= 18
  return `url('/img/scenario/bg_upper-${night ? 'night' : 'day'}.webp')`
})

onMounted(load)
</script>

<template>
  <div class="tasks">
    <div class="veil" :style="{ backgroundImage: veilBg }"></div>

    <button class="back" @click="back()">‹</button>

    <div class="castbar">
      <button
        v-for="(c, i) in CAST"
        :key="c.key"
        class="cast"
        :class="{ on: cast === i }"
        @click="cast = i"
      >{{ c.name }}</button>
    </div>

    <div class="stage">
      <SpineShop
        v-if="current.dir"
        :key="current.key"
        :dir="current.dir"
        :skel="current.skel"
        :atlas="current.atlas || ''"
        :fill="false"
        :anchor-y="1.02"
        :zoom="0.92"
      />
      <img v-else-if="current.img" class="still" :src="current.img" :alt="current.name" />
      <div class="bubble">
        <b>{{ current.name }}</b>
        <p>{{ LINE }}</p>
      </div>
    </div>

    <section class="board">
      <nav class="tabs">
        <button
          v-for="t in tabs"
          :key="t.key"
          class="tab"
          :class="{ on: tab === t.key }"
          @click="tab = t.key"
        >{{ t.label }}</button>
      </nav>

      <div class="list">
        <article v-for="t in shown" :key="t.id" class="card" :class="{ done: t.done }">
          <header>
            <span class="kind" :class="t.kind">{{ KIND_LABEL[t.kind] }}</span>
            <h3>{{ t.title }}</h3>
            <div class="ops">
              <button class="op" title="编辑" @click="editing = { ...t }">✎</button>
              <button class="op" title="删除" @click="removeTask(t)">✕</button>
            </div>
          </header>

          <p v-if="t.deadline" class="limit">限时 {{ t.deadline }}</p>
          <p v-if="t.note" class="note">{{ t.note }}</p>

          <div class="row">
            <div class="bars">
              <span class="pg">进度 <b>{{ t.progress }}</b> / {{ t.target }}</span>
              <i class="track"><b :style="{ width: t.percent + '%' }"></b></i>
            </div>
            <span class="rw"><img :src="rewardIcon(t.rewardIcon)" alt="" /><em>×{{ t.reward }}</em></span>
            <button class="act" :class="{ ok: t.done }" @click="finish(t)">
              {{ t.done ? '已完成' : '确认完成' }}
            </button>
          </div>
        </article>

        <p v-if="!shown.length" class="empty">这一栏还没有任务，点右下角「新建任务」加一条。</p>
      </div>

      <footer class="foot">
        <div class="sum">
          <b>完成 {{ dailyDone }} / {{ dailyTotal }} 每日任务</b>
          <i>全部已勾掉 {{ doneAll }} / {{ items.length }}</i>
        </div>
        <button class="ghost" @click="load">刷新</button>
        <button class="primary" @click="newTask">＋ 新建任务</button>
      </footer>
    </section>

    <!-- 编辑 / 新建 -->
    <div v-if="editing" class="mask" @click.self="editing = null">
      <div class="edit">
        <h4>{{ editing.id ? '编辑任务' : '新建任务' }}</h4>
        <label>类型
          <select v-model="editing.kind">
            <option value="daily">每日</option>
            <option value="weekly">每周</option>
            <option value="achievement">成就</option>
            <option value="challenge">挑战</option>
          </select>
        </label>
        <label>标题
          <input v-model="editing.title" placeholder="例如：在咖啡厅获得好感度 1 次" />
        </label>
        <div class="two">
          <label>进度
            <input v-model.number="editing.progress" type="number" min="0" />
          </label>
          <label>目标
            <input v-model.number="editing.target" type="number" min="1" />
          </label>
        </div>
        <label>限时（可选）
          <input v-model="editing.deadline" placeholder="2026年11月05日03点59分59秒截止" />
        </label>
        <label>备注（可选）
          <input v-model="editing.note" placeholder="写点提醒自己的话" />
        </label>
        <div class="two">
          <label>奖励数量
            <input v-model.number="editing.reward" type="number" min="0" />
          </label>
          <label>奖励图标
            <select v-model="editing.rewardIcon">
              <option value="gem">青辉石</option>
              <option value="ap">道具券</option>
              <option value="credit">信用点</option>
            </select>
          </label>
        </div>
        <div class="ebtns">
          <button class="ghost" @click="editing = null">取消</button>
          <button class="primary" @click="saveTask">保存</button>
        </div>
      </div>
    </div>

    <!-- 完成提示 -->
    <div v-if="reward" class="mask win" @click="reward = null">
      <div class="gwin">
        <p class="big">任务完成！</p>
        <div class="gcard">
          <span>{{ reward.title }}</span>
          <img :src="rewardIcon(reward.rewardIcon)" alt="" />
          <i>×{{ reward.reward }}</i>
        </div>
        <p class="tip">点击继续</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.tasks {
  position: fixed;
  inset: 0;
  z-index: 44;
  overflow: hidden;
  font-family: var(--font-ui, system-ui, sans-serif);
}
.veil {
  position: absolute;
  inset: 0;
  background-position: center 50%;
  background-size: cover;
  background-repeat: no-repeat;
  filter: blur(7px) saturate(1.05) brightness(1.02);
  transform: scale(1.06);
}
.back {
  z-index: 30;
  position: absolute;
  left: 22px;
  top: 18px;
  z-index: 4;
  width: 46px;
  height: 46px;
  border: 2px solid rgba(190, 225, 250, 0.7);
  border-radius: 50%;
  background: rgba(18, 48, 82, 0.72);
  color: #cfe6fb;
  font-size: 22px;
  cursor: pointer;
}
.stage {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 104px;
  width: 36%;
  z-index: 2;
}
.castbar {
  position: absolute;
  left: 22px;
  top: 74px;
  z-index: 4;
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  max-width: 300px;
}
.cast {
  padding: 6px 14px;
  border: 1px solid rgba(190, 225, 250, 0.55);
  border-radius: 999px;
  background: rgba(16, 44, 74, 0.55);
  color: #d5e9fa;
  font-size: 12.5px;
  cursor: pointer;
  backdrop-filter: blur(6px);
}
.cast.on {
  background: #fff;
  color: #2f5f8c;
  font-weight: 800;
}
.still {
  position: absolute;
  left: 50%;
  bottom: 0;
  width: 100%;
  height: 100%;
  transform: translateX(-50%);
  transform-origin: 50% 92%;
  object-fit: contain;
  object-position: center bottom;
  animation: breath 6.5s ease-in-out infinite;
  filter: drop-shadow(0 10px 26px rgba(6, 26, 52, 0.34));
}
@keyframes breath {
  0%, 100% { transform: scale(1) translateY(0); }
  50% { transform: scale(1.012) translateY(-4px); }
}
.still {
  position: absolute;
  left: 0;
  bottom: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: center 12%;
}
.bubble {
  position: absolute;
  left: 26px;
  bottom: 34px;
  width: min(320px, 26vw);
  padding: 12px 18px 14px;
  border-radius: 18px;
  background: rgba(246, 251, 255, 0.95);
  box-shadow: 0 12px 30px rgba(2, 14, 30, 0.42);
  z-index: 3;
}
.bubble b {
  display: block;
  font-size: 12px;
  color: #4f86b8;
  margin-bottom: 4px;
}
.bubble p {
  margin: 0;
  font-size: 13.5px;
  line-height: 1.6;
  color: #2f4a66;
}
.board {
  position: absolute;
  left: 34%;
  right: 0;
  top: 0;
  bottom: 0;
  z-index: 3;
  display: flex;
  flex-direction: column;
  padding: 16px 26px 16px 8px;
}
.tabs {
  display: flex;
  gap: 0;
  margin-bottom: 12px;
}
.tab {
  position: relative;
  flex: 1;
  height: 46px;
  border: 0;
  background: rgba(248, 252, 255, 0.92);
  color: #2f5f8c;
  font-size: 16px;
  font-weight: 700;
  cursor: pointer;
  clip-path: polygon(10px 0, 100% 0, calc(100% - 10px) 100%, 0 100%);
}
.tab + .tab {
  margin-left: -6px;
}
.tab.on {
  background: linear-gradient(180deg, #234a74, #17395c);
  color: #ffd75e;
  z-index: 2;
}
.list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-right: 6px;
}
.card {
  padding: 12px 16px 14px;
  border-radius: 12px;
  background: rgba(249, 253, 255, 0.95);
  box-shadow: 0 8px 22px rgba(4, 18, 38, 0.28), inset 0 0 0 1px rgba(190, 218, 240, 0.8);
}
.card.done {
  opacity: 0.72;
}
.card header {
  display: flex;
  align-items: center;
  gap: 10px;
}
.card h3 {
  margin: 0;
  font-size: 15.5px;
  font-weight: 800;
  color: #23486e;
  flex: 1;
}
.kind {
  flex: none;
  padding: 3px 12px;
  border-radius: 7px;
  color: #fff;
  font-size: 12.5px;
  font-weight: 800;
}
.kind.daily { background: linear-gradient(180deg, #59b6f0, #2f92d8); }
.kind.weekly { background: linear-gradient(180deg, #63c98c, #34a866); }
.kind.achievement { background: linear-gradient(180deg, #f2a13c, #dd7f18); }
.kind.challenge { background: linear-gradient(180deg, #a97ade, #7f4bc0); }
.ops {
  display: flex;
  gap: 6px;
  opacity: 0;
  transition: opacity 0.15s;
}
.card:hover .ops {
  opacity: 1;
}
.op {
  width: 26px;
  height: 26px;
  border: 1px solid #cfe1f0;
  border-radius: 7px;
  background: #fff;
  color: #5a7f9f;
  font-size: 12px;
  cursor: pointer;
}
.limit {
  margin: 6px 0 0;
  font-size: 12px;
  color: #e0642e;
  font-weight: 700;
}
.note {
  margin: 4px 0 0;
  font-size: 12px;
  color: #7b93a8;
}
.row {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-top: 8px;
}
.bars {
  flex: 1;
}
.pg {
  font-size: 12px;
  color: #5a7f9f;
}
.pg b {
  color: #23486e;
}
.track {
  display: block;
  margin-top: 5px;
  height: 12px;
  border-radius: 6px;
  background: #2c3d4d;
  overflow: hidden;
}
.track b {
  display: block;
  height: 100%;
  border-radius: 6px;
  background: linear-gradient(90deg, #55c8f2, #2fa8e0);
}
.rw {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border-radius: 8px;
  background: #eaf4fd;
  box-shadow: inset 0 0 0 1px rgba(170, 205, 232, 0.9);
}
.rw img {
  width: 22px;
  height: 22px;
  object-fit: contain;
}
.rw em {
  font-style: normal;
  font-size: 11.5px;
  font-weight: 700;
  color: #4f86b8;
}
.act {
  flex: none;
  min-width: 104px;
  height: 40px;
  border: 0;
  border-radius: 10px;
  background: linear-gradient(180deg, #ffe066, #ffc61a);
  color: #5c4400;
  font-size: 14.5px;
  font-weight: 800;
  cursor: pointer;
  box-shadow: 0 6px 16px rgba(220, 170, 20, 0.34);
}
.act.ok {
  background: #dfe8f0;
  color: #7d93aa;
  box-shadow: none;
}
.empty {
  margin: 30px 0;
  text-align: center;
  color: rgba(220, 236, 250, 0.75);
  font-size: 13px;
}
.foot {
  flex: none;
  display: flex;
  align-items: center;
  gap: 14px;
  padding-top: 12px;
}
.sum {
  flex: 1;
}
.sum b {
  display: block;
  font-size: 14px;
  color: #eaf4ff;
}
.sum i {
  font-style: normal;
  font-size: 12px;
  color: rgba(200, 224, 244, 0.8);
}
.ghost {
  height: 40px;
  padding: 0 18px;
  border: 1px solid rgba(190, 225, 250, 0.6);
  border-radius: 10px;
  background: rgba(20, 52, 86, 0.6);
  color: #d7ebfb;
  font-size: 13px;
  cursor: pointer;
}
.primary {
  height: 42px;
  padding: 0 24px;
  border: 0;
  border-radius: 10px;
  background: linear-gradient(180deg, #ffe066, #ffc61a);
  color: #5c4400;
  font-size: 14px;
  font-weight: 800;
  cursor: pointer;
}
.mask {
  position: absolute;
  inset: 0;
  z-index: 6;
  display: grid;
  place-items: center;
  background: rgba(4, 16, 32, 0.62);
  backdrop-filter: blur(3px);
}
.edit {
  width: min(520px, 88vw);
  padding: 20px 22px 18px;
  border-radius: 16px;
  background: #fbfdff;
  box-shadow: 0 24px 60px rgba(2, 14, 30, 0.5);
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.edit h4 {
  margin: 0 0 4px;
  font-size: 17px;
  color: #23486e;
}
.edit label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12.5px;
  color: #5a7f9f;
}
.edit input,
.edit select {
  height: 38px;
  padding: 0 12px;
  border: 1px solid #cfe1f0;
  border-radius: 9px;
  font-size: 14px;
  color: #23486e;
  background: #fff;
  outline: none;
}
.edit .two {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.ebtns {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 6px;
}
.win .gwin {
  text-align: center;
}
.gwin .big {
  margin: 0 0 16px;
  font-size: 34px;
  font-weight: 900;
  color: #ffd75e;
  text-shadow: 0 6px 18px rgba(0, 0, 0, 0.5);
  letter-spacing: 0.04em;
}
.gcard {
  width: 180px;
  margin: 0 auto;
  padding: 12px;
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 14px 34px rgba(0, 0, 0, 0.4);
}
.gcard span {
  display: block;
  font-size: 13px;
  color: #23486e;
  margin-bottom: 8px;
}
.gcard img {
  width: 74px;
  height: 74px;
  object-fit: contain;
}
.gcard i {
  display: block;
  font-style: normal;
  font-size: 15px;
  font-weight: 800;
  color: #23486e;
}
.gwin .tip {
  margin-top: 18px;
  font-size: 13px;
  color: rgba(230, 242, 252, 0.9);
}
</style>
