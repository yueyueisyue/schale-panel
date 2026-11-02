<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'

const emit = defineEmits<{ (e: 'close'): void }>()
const props = defineProps<{ level?: number; exp?: number; expMax?: number }>()

function authHeaders(): Record<string, string> {
  const t = localStorage.getItem('schale_token') || ''
  return t ? { Authorization: `Bearer ${t}` } : {}
}

type View = 'account' | 'player' | 'idcard'
const view = ref<View>('account')

const nick = ref('月')
const title = ref('工程部顾问')
const greeting = ref('光啊！')
const level = ref(props.level ?? 86)
const expMax = ref(props.expMax ?? 10614)
const exp = ref(props.exp ?? 679)
const friendCode = ref('sli84nh')
const friendMax = ref(1)

type Member = { key: string; name: string; level: number; art: string; full?: boolean }
const MEMBERS: Member[] = [
  { key: 'mika', name: '圣园弥香', level: 85, art: '/img/portrait/mika-story.webp', full: true },
  { key: 'sora', name: '小空', level: 85, art: '/img/portrait/sora.png' },
  { key: 'ayumu', name: '岩柜步', level: 85, art: '/img/portrait/ayumu-cut.png' },
  { key: 'rin', name: '琳', level: 90, art: '/img/portrait/rin.png' },
  { key: 'momoka', name: '桃香', level: 85, art: '/img/portrait/momoka.png' },
  { key: 'aoi', name: '葵', level: 85, art: '/img/portrait/aoi.png' },
]
const duty = ref<Member>(MEMBERS[0])
const pickerOpen = ref(false)
const pendingPick = ref<Member>(MEMBERS[0])

function openPicker() { pendingPick.value = duty.value; pickerOpen.value = true }
function confirmPick() { duty.value = pendingPick.value; pickerOpen.value = false; save() }

type R18State = 'off' | 'warn' | 'tease' | 'on'
const R18_ICON: Record<R18State, string> = {
  off: '/img/ui/chun-off.png', warn: '/img/ui/chun-warn.png',
  tease: '/img/ui/chun-tease.png', on: '/img/ui/chun-on.png',
}
const R18_TEXT: Record<R18State, string> = {
  off: '点击图标开始', warn: '喂！不可以色色！点击再确认一次……',
  tease: '真、真的要开吗？开了我可就不管了哦——', on: '已开启，随时可以关掉。',
}
const r18 = ref<R18State>('off')
const flash = ref(false)

function tapR18() {
  flash.value = true
  window.setTimeout(() => { flash.value = false }, 320)
  if (r18.value === 'off') r18.value = 'warn'
  else if (r18.value === 'warn') r18.value = 'tease'
  else if (r18.value === 'tease') { r18.value = 'on'; save() }
  else { r18.value = 'off'; save() }
}

const editKey = ref<'' | 'nick' | 'title' | 'greeting'>('')
const editVal = ref('')
const EDIT_LABEL: Record<string, string> = { nick: '昵称', title: '称号', greeting: '问候语' }

function openEdit(k: 'nick' | 'title' | 'greeting') {
  editKey.value = k
  editVal.value = k === 'nick' ? nick.value : k === 'title' ? title.value : greeting.value
}
function commitEdit() {
  const v = editVal.value.trim()
  if (!v) return
  if (editKey.value === 'nick') nick.value = v
  else if (editKey.value === 'title') title.value = v
  else if (editKey.value === 'greeting') greeting.value = v
  editKey.value = ''
  save()
}

async function save() {
  const pref = {
    nick: nick.value, title: title.value, greeting: greeting.value,
    duty: duty.value.key, dutyName: duty.value.name, r18: r18.value === 'on',
  }
  localStorage.setItem('schale_pref', JSON.stringify(pref))
  try {
    await fetch('/api/prefs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify(pref),
    })
  } catch { /* 只存本地 */ }
}

async function load() {
  let pref: any = null
  try {
    const raw = localStorage.getItem('schale_pref')
    if (raw) pref = JSON.parse(raw)
  } catch { /* ignore */ }
  if (!pref) {
    try {
      const r = await fetch('/api/prefs', { headers: authHeaders() })
      if (r.ok) pref = await r.json()
    } catch { /* ignore */ }
  }
  if (!pref) return
  if (typeof pref.nick === 'string' && pref.nick) nick.value = pref.nick
  if (typeof pref.title === 'string' && pref.title) title.value = pref.title
  if (typeof pref.greeting === 'string' && pref.greeting) greeting.value = pref.greeting
  const m = MEMBERS.find((x) => x.key === pref.duty)
  if (m) duty.value = m
  r18.value = pref.r18 ? 'on' : 'off'
}

function copyCode() {
  try { navigator.clipboard.writeText(friendCode.value) } catch { /* ignore */ }
}

function onKey(e: KeyboardEvent) {
  if (e.key !== 'Escape') return
  if (editKey.value) { editKey.value = ''; return }
  if (pickerOpen.value) { pickerOpen.value = false; return }
  if (view.value === 'account') emit('close')
  else view.value = 'account'
}
onMounted(() => {
  load()
  const q = new URLSearchParams(location.search)
  if (q.get('picker') === '1') pickerOpen.value = true
  const v = q.get('view')
  if (v === 'player' || v === 'idcard') view.value = v
  window.addEventListener('keydown', onKey)
})
onUnmounted(() => window.removeEventListener('keydown', onKey))

const r18On = computed(() => r18.value === 'on')
</script>

<template>
  <div class="acct">
    <div class="acct-bg"></div>

    <header class="acct-hd">
      <button class="back" @click="view === 'account' ? emit('close') : (view = 'account')">‹</button>
      <h2>{{ view === 'idcard' ? 'ID卡 ?' : '账号信息' }}</h2>
      <button class="x" @click="emit('close')">✕</button>
    </header>

    <!-- ═══ 账号信息页 ═══ -->
    <template v-if="view === 'account'">
      <div class="acct-body">
        <aside class="art" :class="{ full: duty.full }" :style="{ '--art': `url(${duty.art})` }">
          <img :src="duty.art" :alt="duty.name" />
          <div class="art-lv">
            <span class="k">等级</span>
            <b class="num">{{ level }}</b>
            <span class="n">{{ nick }}</span>
            <div class="bar"><i :style="{ width: Math.min(100, (exp / expMax) * 100) + '%' }"></i></div>
            <span class="t num">{{ exp }} / {{ expMax }}</span>
          </div>
        </aside>

        <div class="set">
          <div class="band">昵称</div>
          <div class="row">
            <span class="k">昵称</span>
            <b class="v">{{ nick }}</b>
            <b class="v">老师</b>
            <button class="pen" title="修改昵称" @click="openEdit('nick')">
              <svg viewBox="0 0 24 24"><path d="M4 20h4l10-10-4-4L4 16v4Z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/></svg>
            </button>
          </div>

          <div class="band">简介设定</div>
          <div class="row">
            <span class="k">称号</span>
            <span class="chipv">{{ title }}</span>
            <button class="pen" title="修改称号" @click="openEdit('title')">
              <svg viewBox="0 0 24 24"><path d="M4 20h4l10-10-4-4L4 16v4Z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/></svg>
            </button>
          </div>
          <div class="row">
            <span class="k">值日员</span>
            <img class="ava" :src="duty.art" :alt="duty.name" />
            <em class="v">{{ duty.name }}</em>
            <button class="pen" title="选择值日员" @click="openPicker">
              <svg viewBox="0 0 24 24"><path d="M4 20h4l10-10-4-4L4 16v4Z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/></svg>
            </button>
          </div>
          <div class="row">
            <span class="k">问候语</span>
            <em class="v">{{ greeting }}</em>
            <button class="pen" title="修改问候语" @click="openEdit('greeting')">
              <svg viewBox="0 0 24 24"><path d="M4 20h4l10-10-4-4L4 16v4Z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/></svg>
            </button>
          </div>
          <div class="row r18" :class="{ lit: r18On }">
            <span class="k">涩涩模式</span>
            <button class="r18-btn" :class="[r18, { flash }]" :title="R18_TEXT[r18]" @click.stop="tapR18">
              <img :src="R18_ICON[r18]" alt="涩涩开关" />
              <i class="ping"></i>
            </button>
            <em class="v small">{{ R18_TEXT[r18] }}</em>
          </div>
        </div>
      </div>

      <footer class="acct-foot">
        <button class="bigbtn" @click="view = 'player'">玩家信息</button>
        <button class="bigbtn" @click="view = 'idcard'">ID卡</button>
      </footer>
    </template>

    <!-- ═══ ID 卡页 ═══ -->
    <div v-else-if="view === 'idcard'" class="idbody">
      <div class="idcard">
        <div class="idart">
          <img :src="duty.art" :alt="duty.name" />
          <span class="idlogo">碧蓝档案<em>Blue Archive</em></span>
        </div>
        <div class="idinfo">
          <span class="plv">等级{{ level }}</span>
          <b class="pn big">{{ nick }}</b>
          <span class="ptitle">{{ title }}</span>
          <p class="idcode">好友码 : <b>{{ friendCode }}</b></p>
          <p class="idseason">赛季纪录</p>
          <div class="idgrid">
            <div><span>上次总力战</span><b>第一名</b></div>
            <div><span>上次大决战</span><b>第一名</b></div>
            <div><span>战术对抗赛</span><b>第3804名</b></div>
            <div><span>上次无限制决战</span><b>一阶段</b></div>
          </div>
          <p class="idintro">自我介绍</p>
          <p class="idsign">{{ greeting }}</p>
        </div>
      </div>
      <aside class="idside">
        <button class="side" @click="copyCode">
          <svg viewBox="0 0 24 24"><rect x="8" y="3" width="12" height="14" rx="2" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="M6 7v12a2 2 0 0 0 2 2h9" fill="none" stroke="currentColor" stroke-width="1.7"/></svg>
          复制好友码
        </button>
        <button class="side">
          <svg viewBox="0 0 24 24"><path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>
          扩大ID卡
        </button>
        <button class="side" @click="openEdit('greeting')">
          <svg viewBox="0 0 24 24"><path d="M4 20h4l10-10-4-4L4 16v4Z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/></svg>
          编辑ID卡
        </button>
      </aside>
    </div>

    <!-- ═══ 玩家信息弹窗 ═══ -->
    <template v-if="view === 'player'">
      <div class="pmask" @click="view = 'account'"></div>
      <div class="pcard">
        <header class="phd">
          <h3>玩家信息</h3>
          <button class="x" @click="view = 'account'">✕</button>
        </header>
        <nav class="ptabs">
          <button class="on">简介</button>
          <button>进行状况</button>
          <button>助力者</button>
        </nav>
        <div class="pbody">
          <div class="ptop">
            <img class="pava" :src="duty.art" :alt="duty.name" />
            <div class="pmeta">
              <span class="plv">等级{{ level }}</span>
              <b class="pn">{{ nick }}</b>
              <span class="ptitle">{{ title }}</span>
              <ul class="prows">
                <li><span>小组</span><em>—</em></li>
                <li><span>目前好友</span><em>{{ friendMax }}/50</em></li>
                <li><span>好友码</span><em>{{ friendCode }}</em></li>
              </ul>
            </div>
          </div>
          <div class="pband">问候语</div>
          <div class="pgreet">{{ greeting }}</div>
          <div class="pfoot"><span>IP归属地：</span><i>△ × ○ □</i></div>
        </div>
      </div>
    </template>

    <!-- 值日员选择 -->
    <div v-if="pickerOpen" class="pick">
      <div class="pmask" @click="pickerOpen = false"></div>
      <div class="pick-box">
        <header><h3>选择值日员</h3><button class="x" @click="pickerOpen = false">✕</button></header>
        <div class="pick-bar"><span>已选择 1/1</span><span class="sort">成员等级 ▾</span></div>
        <div class="grid">
          <button v-for="m in MEMBERS" :key="m.key" class="card" :class="{ on: pendingPick.key === m.key }" @click="pendingPick = m">
            <img :src="m.art" :alt="m.name" />
            <span class="lv num">等级 {{ m.level }}</span>
            <span class="nm">{{ m.name }}</span>
          </button>
        </div>
        <footer>
          <button class="ghost" @click="pickerOpen = false">取消</button>
          <button class="ok" @click="confirmPick">确认</button>
        </footer>
      </div>
    </div>

    <!-- 就地编辑 -->
    <div v-if="editKey" class="edit">
      <div class="pmask" @click="editKey = ''"></div>
      <div class="edit-box">
        <h3>修改{{ EDIT_LABEL[editKey] }}</h3>
        <input v-model="editVal" maxlength="24" @keyup.enter="commitEdit" />
        <footer>
          <button class="ghost" @click="editKey = ''">取消</button>
          <button class="ok" @click="commitEdit">保存</button>
        </footer>
      </div>
    </div>
  </div>
</template>

<style scoped>
.acct { position: fixed; inset: 0; z-index: 60; display: flex; flex-direction: column; overflow: hidden; }
.acct-bg {
  position: absolute; inset: 0; z-index: 0;
  background: linear-gradient(160deg, #d8ecfb 0%, #c6e2f7 42%, #dff1fd 100%);
}
.acct-bg::after {
  content: ''; position: absolute; inset: 0;
  background:
    radial-gradient(ellipse 60% 45% at 22% 18%, rgba(255,255,255,.85), transparent 60%),
    radial-gradient(ellipse 50% 40% at 82% 78%, rgba(255,255,255,.6), transparent 65%);
}
.acct-hd { position: relative; z-index: 3; display: flex; align-items: center; gap: 14px; padding: 14px 22px; }
.acct-hd h2 { margin: 0; font-size: 22px; font-weight: 800; color: #1d3f60; letter-spacing: .02em; }
.back {
  width: 34px; height: 34px; border: none; border-radius: 50%;
  background: rgba(255,255,255,.85); color: #2c5d8f; font-size: 20px; line-height: 1; cursor: pointer;
  box-shadow: 0 3px 10px rgba(40,82,122,.16);
}
.x {
  margin-left: auto; width: 32px; height: 32px; border: none; border-radius: 9px;
  background: rgba(255,255,255,.8); color: #35618c; font-size: 15px; cursor: pointer;
}
.acct-body {
  position: relative; z-index: 2; flex: 1; min-height: 0;
  display: grid; grid-template-columns: 42% 1fr; gap: 18px; padding: 0 22px 8px;
}
.art {
  position: relative; border-radius: 16px; overflow: hidden;
  background: radial-gradient(ellipse 80% 60% at 50% 30%, #f2fbff 0%, #d9edfb 55%, #c7e3f6 100%);
}
/* 底衬：同一张立绘放大模糊，把左右留白填成氛围 */
.art::before {
  content: ''; position: absolute; inset: -12%;
  background-image: var(--art);
  background-position: center 30%;
  background-size: cover;
  filter: blur(26px) saturate(1.15) brightness(1.06);
  opacity: .55;
}
/* 立绘本体：整幅 contain，不裁不缩放变形 */
.art > img {
  position: relative; z-index: 1;
  width: 100%; height: 100%;
  object-fit: contain;
  object-position: center bottom;
  display: block;
  filter: drop-shadow(0 10px 26px rgba(24, 62, 98, .22));
}
/* 个人剧情立绘本身带背景，直接满幅铺满 */
.art.full::before { display: none; }
.art.full > img {
  object-fit: cover;
  object-position: 66% 38%;
  filter: none;
}
.art-lv {
  position: absolute; z-index: 3; left: 12px; right: 12px; bottom: 12px;
  display: grid; grid-template-columns: auto 1fr; gap: 3px 12px; align-items: center;
  padding: 10px 14px; border-radius: 12px;
  background: linear-gradient(120deg, rgba(12,34,62,.88), rgba(20,54,92,.72)); color: #fff;
}
.art-lv .k { font-size: 11px; color: #ffd66b; letter-spacing: .1em; }
.art-lv b { grid-row: span 2; font-size: 36px; line-height: 1; }
.art-lv .n { font-size: 13px; font-weight: 700; }
.art-lv .bar { grid-column: 2; height: 5px; border-radius: 3px; background: rgba(255,255,255,.22); overflow: hidden; }
.art-lv .bar i { display: block; height: 100%; background: linear-gradient(90deg, #7fc3f5, #4d92dd); }
.art-lv .t { grid-column: 2; font-size: 10px; color: rgba(220,238,255,.75); }
.set { position: relative; z-index: 3; overflow-y: auto; padding: 2px 4px 8px; }
.band {
  margin: 10px 0 8px; padding: 7px 12px; border-radius: 8px;
  background: linear-gradient(90deg, #2c5d8f, #4a86bd); color: #eaf5ff;
  font-size: 12.5px; font-weight: 700; letter-spacing: .16em; text-align: center;
}
.row {
  display: flex; align-items: center; gap: 12px; padding: 12px 14px; margin-bottom: 8px;
  background: rgba(255,255,255,.94); border-radius: 10px; box-shadow: 0 2px 8px rgba(40,82,122,.08);
}
.row .k { width: 74px; flex: none; font-size: 13px; color: #5a7896; }
.row .v { font-size: 15px; font-weight: 700; color: #22405e; }
.row .v.small { font-size: 12.5px; font-weight: 500; color: #4d7797; }
.chipv {
  padding: 5px 16px; border-radius: 7px; border: 1.5px solid #bcd8ef;
  background: #eaf4fd; color: #2b5f92; font-size: 13px; font-weight: 700;
}
.ava { width: 58px; height: 58px; border-radius: 9px; object-fit: cover; border: 2px solid #d6e8f7; }
.pen {
  margin-left: auto; width: 30px; height: 30px; flex: none; display: grid; place-items: center;
  border: none; border-radius: 8px; background: #eef5fc; color: #436e96; cursor: pointer;
}
.pen svg { width: 16px; height: 16px; }
.r18.lit { box-shadow: 0 0 0 2px rgba(240,86,122,.4), 0 2px 10px rgba(240,86,122,.18); }
.r18-btn {
  position: relative; flex: none; width: 58px; height: 58px; padding: 0;
  border: 2px solid #d6e8f7; border-radius: 9px; background: #fff; cursor: pointer;
}
.r18-btn img { width: 100%; height: 100%; object-fit: contain; display: block; border-radius: 7px; }
.r18-btn .ping {
  position: absolute; inset: -6px; border-radius: 12px; pointer-events: none; opacity: 0;
  background: radial-gradient(circle, rgba(255,130,175,.5), rgba(255,130,175,0) 70%);
}
.r18-btn.flash .ping { animation: ping .32s ease-out; }
.r18-btn.on { border-color: #f0567a; }
@keyframes ping { 0% { opacity: .9; transform: scale(.7); } 100% { opacity: 0; transform: scale(1.5); } }
.acct-foot {
  position: relative; z-index: 3; display: flex; gap: 26px; justify-content: center; padding: 10px 22px 20px;
}
.bigbtn {
  min-width: 300px; padding: 16px 0; border: none; border-radius: 12px;
  background: linear-gradient(180deg, #86d3f6, #4aa9e0); color: #fff;
  font-size: 21px; font-weight: 800; letter-spacing: .06em; cursor: pointer;
  box-shadow: 0 8px 22px rgba(48,132,190,.32);
}
.bigbtn:nth-child(2) { background: linear-gradient(180deg, #9ee0f8, #58b6e8); }

/* 玩家信息弹窗 */
.pmask { position: fixed; inset: 0; background: rgba(10,30,54,.45); z-index: 4; }
.pcard {
  position: fixed; left: 50%; top: 50%; transform: translate(-50%, -50%);
  z-index: 5; width: min(560px, calc(100vw - 80px)); max-height: calc(100vh - 90px);
  display: flex; flex-direction: column; overflow: hidden;
  border-radius: 16px; background: #f7fbff; box-shadow: 0 24px 60px rgba(6,24,46,.42);
}
.phd { position: relative; display: grid; place-items: center; padding: 12px; }
.phd h3 { margin: 0; font-size: 18px; font-weight: 800; color: #1d3f60; }
.phd .x { position: absolute; right: 12px; top: 10px; margin: 0; }
.ptabs { display: flex; gap: 6px; padding: 0 12px 10px; }
.ptabs button {
  flex: 1; padding: 9px 0; border: none; border-radius: 8px 8px 0 0;
  background: #e3f0fb; color: #3f6b93; font-size: 14px; font-weight: 700; cursor: pointer;
}
.ptabs button.on { background: #fff; color: #1d3f60; box-shadow: 0 -2px 0 #7cc0ec inset; }
.pbody { padding: 0 12px 12px; overflow-y: auto; background: #fff; }
.ptop { display: flex; gap: 14px; padding: 12px 8px; }
.pava {
  width: 128px; height: 128px; flex: none; border-radius: 10px;
  object-fit: cover; object-position: center 12%;
  border: 2px solid #d6e8f7; background: #eaf4fd;
}
.pmeta { display: flex; flex-direction: column; gap: 5px; }
.plv { font-size: 12px; color: #5a7896; }
.pn { font-size: 24px; font-weight: 800; color: #1d3f60; line-height: 1.1; }
.ptitle {
  align-self: flex-start; padding: 4px 14px; border-radius: 7px;
  border: 1.5px solid #bcd8ef; background: #eaf4fd; color: #2b5f92; font-size: 12px; font-weight: 700;
}
.prows { list-style: none; margin: 6px 0 0; padding: 0; border-top: 1px solid #e6f1fa; }
.prows li { display: flex; padding: 7px 2px; border-bottom: 1px solid #eef5fc; font-size: 13px; }
.prows li span { width: 92px; color: #5a7896; }
.prows li em { font-style: normal; color: #22405e; font-weight: 700; }
.pband {
  margin: 4px 8px 8px; padding: 7px 12px; border-radius: 8px;
  background: linear-gradient(90deg, #2c5d8f, #4a86bd); color: #eaf5ff;
  font-size: 12.5px; font-weight: 700; letter-spacing: .16em; text-align: center;
}
.pgreet {
  margin: 0 8px; min-height: 96px; padding: 12px 14px;
  border: 1px solid #dbeaf7; border-radius: 8px; background: #fff;
  font-size: 14px; color: #22405e; line-height: 1.6;
}
.pfoot {
  display: flex; justify-content: space-between; align-items: center;
  margin: 10px 8px 0; padding-top: 8px; border-top: 1px solid #eef5fc;
  font-size: 12px; color: #6b8aa6;
}
.pfoot i { font-style: normal; letter-spacing: .3em; color: #9fbad2; }

/* ID 卡 */
.idbody {
  position: relative; z-index: 2; flex: 1; display: grid;
  grid-template-columns: 1fr 250px; gap: 20px; padding: 0 24px 24px; min-height: 0;
}
.idcard {
  display: grid; grid-template-columns: 40% 1fr; overflow: hidden;
  border-radius: 14px; background: #fff; box-shadow: 0 14px 40px rgba(20,60,100,.22);
}
.idart { position: relative; overflow: hidden; background: #dcecf9; }
.idart img { width: 100%; height: 100%; object-fit: cover; object-position: 44% 8%; display: block; }
.idlogo {
  position: absolute; left: 12px; bottom: 12px;
  font-size: 15px; font-weight: 800; color: #fff; text-shadow: 0 2px 8px rgba(0,0,0,.4);
}
.idlogo em { display: block; font-style: normal; font-size: 9px; letter-spacing: .18em; opacity: .9; }
.idinfo { padding: 18px 20px; overflow-y: auto; display: flex; flex-direction: column; gap: 8px; }
.pn.big { font-size: 30px; }
.idcode { margin: 2px 0 0; font-size: 13px; color: #2b5f92; }
.idseason { margin: 6px 0 0; font-size: 12px; color: #4d7797; font-weight: 700; }
.idgrid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.idgrid > div { padding: 9px 12px; border-radius: 8px; background: #f1f8fe; }
.idgrid span { display: block; font-size: 11px; color: #6b8aa6; }
.idgrid b { font-size: 15px; color: #1d3f60; }
.idintro { margin: 8px 0 0; font-size: 12px; color: #4d7797; font-weight: 700; }
.idsign { margin: 0; font-size: 13px; color: #22405e; }
.idside { display: flex; flex-direction: column; gap: 12px; }
.side {
  display: flex; align-items: center; gap: 10px; padding: 14px 16px;
  border: none; border-radius: 11px; background: rgba(255,255,255,.96); color: #22405e;
  font-size: 15px; font-weight: 700; cursor: pointer; box-shadow: 0 6px 18px rgba(40,82,122,.14);
}
.side svg { width: 20px; height: 20px; color: #3f7fb4; }

/* 值日员选择 */
.pick { position: fixed; inset: 0; display: grid; place-items: center; z-index: 30; }
.pick-box {
  position: relative; z-index: 31; width: min(760px, calc(100vw - 80px));
  max-height: calc(100vh - 100px); display: flex; flex-direction: column;
  border-radius: 16px; background: #f6fbff; overflow: hidden; box-shadow: 0 22px 60px rgba(6,24,46,.45);
}
.pick-box header { position: relative; display: grid; place-items: center; padding: 12px; border-bottom: 1px solid #e2eefa; }
.pick-box h3 { margin: 0; font-size: 17px; font-weight: 800; color: #1d3f60; }
.pick-box header .x { position: absolute; right: 12px; top: 10px; margin: 0; }
.pick-bar { display: flex; justify-content: space-between; align-items: center; padding: 10px 16px; font-size: 12.5px; color: #4d7797; }
.pick-bar .sort { padding: 5px 12px; border-radius: 7px; background: #e7f1fb; font-weight: 700; }
.grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 10px; padding: 6px 16px 16px; overflow-y: auto; }
.card {
  position: relative; padding: 0; border: none; border-radius: 10px; background: #fff;
  cursor: pointer; overflow: hidden; box-shadow: 0 2px 8px rgba(40,82,122,.1);
  display: flex; flex-direction: column;
}
.card img { width: 100%; height: 92px; object-fit: cover; object-position: center 14%; display: block; }
.card .lv {
  position: absolute; left: 4px; top: 4px; padding: 1px 6px; border-radius: 6px;
  background: rgba(12,34,62,.7); color: #fff; font-size: 9.5px; font-weight: 700;
}
.card .nm { padding: 6px 4px 7px; font-size: 12px; font-weight: 700; color: #22405e; }
.card.on { box-shadow: 0 0 0 3px #8ed94f, 0 3px 10px rgba(90,160,40,.25); }
.pick-box footer { display: flex; gap: 12px; justify-content: center; padding: 14px; border-top: 1px solid #e2eefa; }
.pick-box footer button, .edit-box footer button {
  min-width: 150px; padding: 11px 0; border: none; border-radius: 9px;
  font-size: 14px; font-weight: 700; cursor: pointer;
}
.ghost { background: #e7f1fb; color: #3f6b93; }
.ok { background: linear-gradient(180deg, #6fc1ee, #4a9fd6); color: #fff; }

/* 编辑弹窗 */
.edit { position: fixed; inset: 0; display: grid; place-items: center; z-index: 40; }
.edit-box {
  position: relative; z-index: 41; width: min(420px, calc(100vw - 80px));
  padding: 18px 20px 16px; border-radius: 14px; background: #f7fbff; box-shadow: 0 20px 50px rgba(6,24,46,.42);
}
.edit-box h3 { margin: 0 0 12px; font-size: 15px; font-weight: 800; color: #1d3f60; }
.edit-box input {
  width: 100%; box-sizing: border-box; padding: 11px 14px;
  border: 1.5px solid #cfe4f6; border-radius: 9px; background: #fff;
  font-size: 14px; color: #22405e; outline: none;
}
.edit-box footer { display: flex; gap: 10px; justify-content: flex-end; margin-top: 14px; }
.edit-box footer button { min-width: 92px; }
</style>
