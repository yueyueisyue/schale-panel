<script setup lang="ts">
/**
 * 成员：人格卡列表。
 * 以后每张卡就是一个可切换的角色人格，点「使用」把当前人格写进 localStorage，
 * 大厅 / 商店 / 桃信的立绘与称呼都跟着换。
 */
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
function openMember(p: any) {
  if (!p.ready) return
  const k = p.id || p.key
  router.push(`/member/${k}`)
}

interface Persona {
  id: string
  name: string
  kana: string
  club: string
  tone: string
  art?: string
  tags: string[]
  ready: boolean
  level: number
  favor: number
  note: string
}

const PERSONAS = ref<Persona[]>([
  {
    id: 'mika',
    name: '圣园弥香',
    kana: 'Misono Mika',
    club: '圣三一综合学园',
    tone: '#f2a8c4',
    art: '/img/portrait/mika.png',
    tags: ['常服立绘', '回忆大厅', '桃信'],
    ready: true,
    level: 85,
    favor: 100,
    note: '轻声递小发现，停住等你接话',
  },
  {
    id: 'sora',
    name: '小空',
    kana: 'Sora',
    club: '天使 24 便利店',
    tone: '#7fc2e8',
    art: '/img/portrait/sora.png',
    tags: ['店员立绘', '商店柜台'],
    ready: true,
    level: 85,
    favor: 62,
    note: '欢迎光临～要看看今天的模型吗？',
  },
  {
    id: 'slot3',
    name: '待接入',
    kana: 'Empty',
    club: '—',
    tone: '#b9c6d6',
    art: '',
    tags: [],
    ready: false,
    level: 0,
    favor: 0,
    note: '把 Spine 骨架放进 public/live2d 就能挂上',
  },
  {
    id: 'slot4',
    name: '待接入',
    kana: 'Empty',
    club: '—',
    tone: '#b9c6d6',
    art: '',
    tags: [],
    ready: false,
    level: 0,
    favor: 0,
    note: '同一个人格的换装也可以占一格',
  },
  {
    id: 'ayumu',
    name: '步美',
    kana: 'Ayumu',
    club: '联邦学生会',
    tone: '#f0d9a0',
    art: '/img/portrait/ayumu-cut.png',
    tags: ['任务看板', '文件整理'],
    ready: true,
    level: 85,
    favor: 80,
    note: '这是待处理的事务清单……那就拜托您了。',
  },
  {
    id: 'rin',
    name: '琳',
    kana: 'Rin',
    club: '联邦学生会',
    tone: '#8fb8e0',
    art: '/img/portrait/rin.png',
    tags: ['常服立绘', '任务页'],
    ready: true,
    level: 90,
    favor: 88,
    note: '行政官，负责把每份文件归到该去的地方。',
  },
  {
    id: 'aoi',
    name: '葵',
    kana: 'Aoi',
    club: '联邦学生会',
    tone: '#b9a6e0',
    art: '/img/portrait/aoi.png',
    tags: ['调停室'],
    ready: true,
    level: 85,
    favor: 70,
    note: '调停室的负责人，话不多但很可靠。',
  },
  {
    id: 'momoka',
    name: '桃香',
    kana: 'Momoka',
    club: '联邦学生会',
    tone: '#f2a8c4',
    art: '/img/portrait/momoka.png',
    tags: ['店员立绘', '小吃货'],
    ready: true,
    level: 85,
    favor: 66,
    note: '我午饭的外卖到了，之后再联系！',
  },
])

const using = ref<string>(localStorage.getItem('schale_persona') || 'mika')
const starred = ref<string[]>(JSON.parse(localStorage.getItem('schale_persona_star') || '["mika"]'))
const q = ref('')
const sort = ref<'level' | 'favor'>('level')

const list = computed(() => {
  const kw = q.value.trim().toLowerCase()
  const arr = PERSONAS.value.filter(
    (p) => !kw || p.name.toLowerCase().includes(kw) || p.kana.toLowerCase().includes(kw) || p.club.includes(kw),
  )
  return arr.slice().sort((a, b) => {
    if (a.id === using.value) return -1
    if (b.id === using.value) return 1
    return sort.value === 'level' ? b.level - a.level : b.favor - a.favor
  })
})

function use(p: Persona) {
  if (!p.ready) return
  using.value = p.id
  localStorage.setItem('schale_persona', p.id)
}

function star(p: Persona) {
  const i = starred.value.indexOf(p.id)
  if (i >= 0) starred.value.splice(i, 1)
  else starred.value.push(p.id)
  localStorage.setItem('schale_persona_star', JSON.stringify(starred.value))
}

onMounted(() => {
  document.title = '成员 · 夏莱'
})
</script>

<template>
  <div class="members">
    <div class="bg"></div>
    <div class="veil"></div>

    <header class="top">
      <button class="back" @click="router.push('/home')">
        <svg viewBox="0 0 24 24"><path d="M14.5 5.5 8 12l6.5 6.5" /></svg>
      </button>
      <div class="ttl">
        <span class="kicker">SCHALE · MEMBERS</span>
        <h1>成员</h1>
      </div>
      <span class="count">{{ list.length }} / {{ PERSONAS.length }}</span>

      <div class="tools">
        <label class="search">
          <svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="6.4" /><path d="m16 16 4 4" /></svg>
          <input v-model="q" placeholder="搜索人格名或学园" />
        </label>
        <div class="sorts">
          <button :class="{ on: sort === 'level' }" @click="sort = 'level'">等级</button>
          <button :class="{ on: sort === 'favor' }" @click="sort = 'favor'">好感度</button>
        </div>
      </div>
    </header>

    <main class="grid">
      <article
        v-for="p in list"
        :key="p.id"
        class="card"
        :class="{ using: using === p.id, off: !p.ready }"
        :style="{ '--tone': p.tone }"
        role="button"
        @click="openMember(p)"
      >
        <div class="face">
          <img v-if="p.art" class="portrait" :src="p.art" :alt="p.name" />
          <span v-else class="initial">{{ p.name.slice(0, 1) }}</span>
          <span class="lv">等级 {{ p.level }}</span>
          <button class="star" :class="{ on: starred.includes(p.id) }" @click.stop="star(p)">
            <svg viewBox="0 0 24 24">
              <path d="m12 3.6 2.6 5.4 5.9.8-4.3 4.1 1.1 5.9-5.3-2.9-5.3 2.9 1.1-5.9L3.5 9.8l5.9-.8z" />
            </svg>
          </button>
          <span v-if="using === p.id" class="now">使用中</span>
        </div>

        <div class="meta">
          <h3>{{ p.name }}</h3>
          <p class="kana">{{ p.kana }} · {{ p.club }}</p>
          <p class="note">{{ p.note }}</p>
          <div class="tags">
            <span v-for="t in p.tags" :key="t">{{ t }}</span>
          </div>
        </div>

        <button class="pick" :disabled="!p.ready || using === p.id" @click="use(p)">
          {{ using === p.id ? '正在使用' : p.ready ? '切换到这一位' : '尚未接入' }}
        </button>
      </article>
    </main>
  </div>
</template>

<style scoped>
.members {
  position: fixed;
  inset: 0;
  overflow: hidden;
  font-family: var(--font-ui, system-ui, sans-serif);
  color: #223046;
}
.bg {
  position: absolute;
  inset: 0;
  background: url('/img/sky/sky2-day.webp') center 40% / cover no-repeat;
  filter: saturate(1.02) brightness(0.96);
  transform: scale(1.04);
}
.veil {
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, rgba(240, 247, 253, 0.74) 0%, rgba(234, 243, 252, 0.52) 32%, rgba(230, 241, 251, 0.48) 100%);
}

.top {
  position: relative;
  z-index: 2;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px 26px 8px;
}
.back {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  border: none;
  background: #fff;
  box-shadow: 0 4px 14px rgba(24, 60, 100, 0.16);
  display: grid;
  place-items: center;
  cursor: pointer;
}
.back svg {
  width: 22px;
  height: 22px;
  fill: none;
  stroke: #3d5b7d;
  stroke-width: 2.2;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.kicker {
  font-size: 10.5px;
  letter-spacing: 0.22em;
  color: #7d90a8;
  font-weight: 700;
}
.ttl h1 {
  margin: 1px 0 0;
  font-size: 26px;
  font-weight: 900;
  letter-spacing: 0.02em;
}
.count {
  padding: 3px 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.9);
  font-size: 12px;
  font-weight: 800;
  color: #3d6da8;
  box-shadow: inset 0 0 0 1px rgba(180, 210, 236, 0.9);
}
.tools {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 10px;
}
.search {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 38px;
  padding: 0 14px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.92);
  box-shadow: inset 0 0 0 1px rgba(184, 213, 238, 0.9);
}
.search svg {
  width: 16px;
  height: 16px;
  fill: none;
  stroke: #7f95ad;
  stroke-width: 2;
  stroke-linecap: round;
}
.search input {
  width: 168px;
  border: none;
  outline: none;
  background: transparent;
  font-size: 13px;
  color: #2b3a4f;
}
.sorts {
  display: flex;
  gap: 6px;
}
.sorts button {
  height: 38px;
  padding: 0 16px;
  border: none;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.86);
  font-size: 13px;
  font-weight: 700;
  color: #566a82;
  cursor: pointer;
  box-shadow: inset 0 0 0 1px rgba(184, 213, 238, 0.9);
}
.sorts button.on {
  background: linear-gradient(180deg, #4f9bea, #2f79c8);
  color: #fff;
  box-shadow: 0 6px 16px rgba(47, 121, 200, 0.3);
}

.grid {
  position: relative;
  z-index: 2;
  padding: 10px 26px 26px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(248px, 1fr));
  gap: 16px;
  max-height: calc(100vh - 96px);
  overflow-y: auto;
}
.card {
  border-radius: 14px;
  background: #fff;
  box-shadow: 0 10px 28px rgba(20, 55, 95, 0.14);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.card.using {
  box-shadow: 0 10px 30px rgba(20, 55, 95, 0.18), 0 0 0 2px var(--tone);
}
.card.off {
  opacity: 0.62;
}
.face {
  position: relative;
  height: 262px;
  overflow: hidden;
  background:
    radial-gradient(120% 90% at 50% 10%, color-mix(in srgb, var(--tone) 78%, #fff) 0%, color-mix(in srgb, var(--tone) 42%, #fff) 46%, #eef6fd 100%);
  display: grid;
  place-items: center;
}
.portrait {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: center 12%;
  display: block;
}
.off .portrait {
  filter: grayscale(0.55) brightness(0.98);
  opacity: 0.72;
}
.initial {
  font-size: 62px;
  font-weight: 900;
  color: rgba(255, 255, 255, 0.92);
  text-shadow: 0 6px 18px rgba(30, 70, 110, 0.25);
}
.lv {
  position: absolute;
  left: 0;
  bottom: 0;
  left: 8px;
  bottom: 8px;
  padding: 3px 13px 3px 11px;
  font-size: 13px;
  font-weight: 800;
  color: #fff;
  letter-spacing: 0.02em;
  background: rgba(24, 42, 68, 0.72);
  border-radius: 7px;
  box-shadow: 0 2px 8px rgba(10, 28, 52, 0.28);
}
.star {
  position: absolute;
  right: 8px;
  top: 8px;
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.82);
  display: grid;
  place-items: center;
  cursor: pointer;
}
.star svg {
  width: 16px;
  height: 16px;
  fill: none;
  stroke: #9fb2c6;
  stroke-width: 1.8;
}
.star.on svg {
  fill: #f6c344;
  stroke: #e0a92a;
}
.now {
  position: absolute;
  left: 8px;
  top: 8px;
  padding: 3px 10px;
  border-radius: 999px;
  background: #46c08a;
  color: #fff;
  font-size: 11px;
  font-weight: 800;
}
.meta {
  padding: 12px 14px 10px;
  flex: 1;
}
.meta h3 {
  margin: 0;
  font-size: 17px;
  font-weight: 900;
}
.kana {
  margin: 2px 0 0;
  font-size: 11.5px;
  color: #8b9bb0;
  font-weight: 600;
}
.note {
  margin: 8px 0 0;
  font-size: 12.5px;
  line-height: 1.5;
  color: #4c5e75;
  min-height: 36px;
}
.tags {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}
.tags span {
  padding: 2px 9px;
  border-radius: 999px;
  background: #eef5fc;
  color: #5b7ea6;
  font-size: 11px;
  font-weight: 700;
}
.pick {
  margin: 0 14px 14px;
  height: 40px;
  border: none;
  border-radius: 10px;
  background: linear-gradient(180deg, #4f9bea, #2f79c8);
  color: #fff;
  font-size: 13.5px;
  font-weight: 800;
  cursor: pointer;
  box-shadow: 0 6px 16px rgba(47, 121, 200, 0.26);
}
.pick:disabled {
  background: #e6eef7;
  color: #9aabbd;
  box-shadow: none;
  cursor: default;
}
</style>
