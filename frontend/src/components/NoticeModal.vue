<script setup lang="ts">
/**
 * 夏莱新闻 · 公告栏
 * 三 tab：公告 / 活动 / 异常通知
 * 数据后续接 BFF 的 /api/notice；现在先用 props 传入的 mock。
 */
import { computed, ref, watch } from 'vue'

type Tone = 'info' | 'ok' | 'warn' | 'error'

interface NoticeItem {
  id: string
  title: string
  time: string
  tone: Tone
  body: string
  /** 右侧配图，留空则显示纯文本详情 */
  image?: string
  /** 详情里的小标签 */
  tags?: string[]
  /** 建议动作 */
  advice?: string
}

const props = withDefaults(
  defineProps<{
    open: boolean
    /** 公告：bot 状态总结 */
    notices?: NoticeItem[]
    /** 活动：近期事件 */
    events?: NoticeItem[]
    /** 异常通知：错误与建议 */
    errors?: NoticeItem[]
    /** 初始 tab，用于外部指定 */
    tab?: string
  }>(),
  {
    notices: () => [],
    events: () => [],
    errors: () => [],
    tab: '',
  }
)

const emit = defineEmits<{
  (e: 'update:open', v: boolean): void
  (e: 'close'): void
}>()

const TAB = [
  { key: 'notice', label: '公告', icon: '📢' },
  { key: 'event', label: '活动', icon: '🗓' },
  { key: 'error', label: '异常通知', icon: '🔧' },
] as const

const tab = ref<'notice' | 'event' | 'error'>('notice')
watch(
  () => props.tab,
  (v) => {
    if (v === 'event' || v === 'error' || v === 'notice') tab.value = v
  },
  { immediate: true }
)

const list = computed<NoticeItem[]>(() => {
  if (tab.value === 'notice') return props.notices
  if (tab.value === 'event') return props.events
  return props.errors
})

const activeId = ref('')
const current = computed<NoticeItem | null>(() => {
  const arr = list.value
  if (!arr.length) return null
  return arr.find((x) => x.id === activeId.value) || arr[0]
})

function pick(it: NoticeItem) {
  activeId.value = it.id
}

function close() {
  emit('update:open', false)
  emit('close')
}

const toneText: Record<Tone, string> = {
  info: '提示',
  ok: '正常',
  warn: '注意',
  error: '异常',
}
</script>

<template>
  <transition name="modal">
    <div v-if="open" class="mask" @click.self="close">
      <div class="sheet">
        <!-- 标题栏 -->
        <header class="head">
          <h2>夏莱新闻</h2>
          <button class="x" type="button" title="关闭" @click="close">✕</button>
        </header>

        <!-- Tab -->
        <nav class="tabs">
          <button
            v-for="t in TAB"
            :key="t.key"
            class="tab"
            :class="{ on: tab === t.key }"
            @click="tab = t.key; activeId = ''"
          >
            <span class="t-ico">{{ t.icon }}</span>
            <span>{{ t.label }}</span>
            <span
              v-if="t.key === 'error' && errors.length"
              class="t-num num"
            >{{ errors.length }}</span>
          </button>
        </nav>

        <!-- 主体 -->
        <div class="body">
          <!-- 列表 -->
          <ul class="list">
            <li
              v-for="it in list"
              :key="it.id"
              class="item"
              :class="[it.tone, { on: current?.id === it.id }]"
              @click="pick(it)"
            >
              <span class="dot" aria-hidden="true"></span>
              <span class="txt">{{ it.title }}</span>
              <span class="time num">{{ it.time }}</span>
            </li>
            <li v-if="!list.length" class="empty">这里什么都没有，一切安好</li>
          </ul>

          <!-- 详情 -->
          <section class="detail">
            <template v-if="current">
              <div class="d-head">
                <span class="badge" :class="current.tone">{{ toneText[current.tone] }}</span>
                <span class="d-time num">{{ current.time }}</span>
              </div>
              <h3>{{ current.title }}</h3>

              <div v-if="current.image" class="d-img">
                <img :src="current.image" :alt="current.title" />
              </div>

              <p class="d-body">{{ current.body }}</p>

              <div v-if="current.tags?.length" class="d-tags">
                <span v-for="(t, i) in current.tags" :key="i" class="d-tag">{{ t }}</span>
              </div>

              <div v-if="current.advice" class="d-advice">
                <span class="a-label">建议</span>
                <span class="a-text">{{ current.advice }}</span>
              </div>
            </template>
            <div v-else class="empty-big">还没有内容</div>
          </section>
        </div>

        <!-- 底部 -->
        <footer class="foot">
          <button class="ghost" type="button" @click="close">今日不再显示</button>
          <button class="primary" type="button" @click="close">知道了</button>
        </footer>
      </div>
    </div>
  </transition>
</template>

<style scoped>
.mask {
  position: fixed;
  inset: 0;
  z-index: 60;
  display: grid;
  place-items: center;
  background: rgba(4, 14, 30, 0.62);
  backdrop-filter: blur(4px);
}

.sheet {
  width: min(1080px, 92vw);
  height: min(760px, 86vh);
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: 6px;
  box-shadow: 0 28px 80px rgba(2, 10, 24, 0.6);
  overflow: hidden;
  clip-path: polygon(0 0, calc(100% - 20px) 0, 100% 20px, 100% 100%, 0 100%);
}

/* 标题栏 */
.head {
  position: relative;
  height: 54px;
  padding: 0 20px;
  display: flex;
  align-items: center;
  background: linear-gradient(180deg, #4f9bea, #2f74c4);
}
.head h2 {
  margin: 0;
  font-size: 17px;
  font-weight: 800;
  letter-spacing: 0.10em;
  color: #fff;
  text-shadow: 0 2px 8px rgba(0, 30, 70, 0.35);
}
.x {
  margin-left: auto;
  width: 30px;
  height: 30px;
  display: grid;
  place-items: center;
  font-size: 15px;
  color: #fff;
  background: transparent;
  border: 0;
  border-radius: 4px;
  cursor: pointer;
  transition: background var(--t-fast);
}
.x:hover {
  background: rgba(255, 255, 255, 0.22);
}

/* Tab */
.tabs {
  display: flex;
  background: #eef3f9;
  border-bottom: 1px solid #dde6f1;
}
.tab {
  position: relative;
  flex: 1;
  height: 46px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  border: 0;
  background: transparent;
  font-family: var(--font-ui);
  font-size: 13.5px;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: #6b7c92;
  cursor: pointer;
  transition: color var(--t-fast), background var(--t-fast);
}
.tab:hover {
  background: #e4ecf6;
}
.tab.on {
  color: #2f74c4;
  background: #fff;
}
.tab.on::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  bottom: -1px;
  height: 3px;
  background: #4f9bea;
}
.t-ico {
  font-size: 15px;
}
.t-num {
  min-width: 17px;
  height: 17px;
  padding: 0 5px;
  display: grid;
  place-items: center;
  font-size: 10px;
  color: #fff;
  background: #e8556d;
  border-radius: var(--r-pill);
}

/* 主体 */
.body {
  flex: 1;
  display: flex;
  min-height: 0;
}

/* 列表 */
.list {
  width: 42%;
  margin: 0;
  padding: 0;
  list-style: none;
  overflow-y: auto;
  border-right: 1px solid #dde6f1;
  background: #fbfdff;
}
.item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  border-bottom: 1px solid #eef2f7;
  cursor: pointer;
  transition: background var(--t-fast);
}
.item:hover {
  background: #f2f7fd;
}
.item.on {
  background: #eaf3ff;
  box-shadow: inset 3px 0 0 #4f9bea;
}
.dot {
  width: 7px;
  height: 7px;
  flex: none;
  border-radius: 50%;
  background: #4f9bea;
}
.item.ok .dot { background: #46c08a; }
.item.warn .dot { background: #f5b942; }
.item.error .dot { background: #e8556d; }

.txt {
  flex: 1;
  font-size: 13px;
  line-height: 1.45;
  color: #2b3644;
}
.time {
  font-size: 11px;
  color: #9aa6b6;
  flex: none;
}
.empty {
  padding: 28px 16px;
  text-align: center;
  font-size: 12.5px;
  color: #9aa6b6;
}

/* 详情 */
.detail {
  flex: 1;
  padding: 20px 22px;
  overflow-y: auto;
}
.d-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}
.badge {
  padding: 2px 9px;
  border-radius: 3px;
  font-size: 11px;
  font-weight: 700;
  color: #fff;
  background: #4f9bea;
}
.badge.ok { background: #46c08a; }
.badge.warn { background: #f5b942; color: #5a3d00; }
.badge.error { background: #e8556d; }
.d-time {
  font-size: 11.5px;
  color: #9aa6b6;
}
.detail h3 {
  margin: 0 0 12px;
  font-size: 16px;
  font-weight: 800;
  line-height: 1.45;
  color: #1d2634;
}
.d-img {
  margin-bottom: 14px;
  border-radius: 4px;
  overflow: hidden;
  box-shadow: 0 8px 24px rgba(20, 50, 90, 0.16);
}
.d-img img {
  display: block;
  width: 100%;
  height: auto;
}
.d-body {
  margin: 0;
  font-size: 13px;
  line-height: 1.78;
  color: #46536a;
  white-space: pre-wrap;
}
.d-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 14px;
}
.d-tag {
  padding: 2px 9px;
  font-size: 11px;
  color: #4a6484;
  background: #eef4fb;
  border-radius: 3px;
}
.d-advice {
  margin-top: 16px;
  padding: 11px 13px;
  display: flex;
  gap: 10px;
  background: #f6f9fd;
  border-left: 3px solid #4f9bea;
  border-radius: 3px;
}
.a-label {
  flex: none;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: #2f74c4;
}
.a-text {
  font-size: 12.5px;
  line-height: 1.7;
  color: #46536a;
}
.empty-big {
  display: grid;
  place-items: center;
  height: 100%;
  font-size: 13px;
  color: #9aa6b6;
}

/* 底部 */
.foot {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  padding: 12px 20px;
  border-top: 1px solid #dde6f1;
  background: #fafcfe;
}
.ghost,
.primary {
  height: 36px;
  padding: 0 20px;
  border-radius: var(--r-sm);
  font-family: var(--font-ui);
  font-size: 12.5px;
  font-weight: 700;
  letter-spacing: 0.06em;
  cursor: pointer;
  transition: all var(--t-fast);
}
.ghost {
  color: #6b7c92;
  background: #fff;
  border: 1px solid #d3dce8;
}
.ghost:hover {
  background: #f2f6fb;
}
.primary {
  color: #fff;
  background: linear-gradient(180deg, #4f9bea, #2f74c4);
  border: 0;
  box-shadow: 0 6px 16px rgba(47, 116, 196, 0.32);
}
.primary:hover {
  transform: translateY(-1px);
  box-shadow: 0 9px 22px rgba(47, 116, 196, 0.42);
}

/* 动画 */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.24s var(--ease);
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
.modal-enter-active .sheet,
.modal-leave-active .sheet {
  transition: transform 0.28s var(--ease-out);
}
.modal-enter-from .sheet,
.modal-leave-to .sheet {
  transform: translateY(16px) scale(0.98);
}

@media (max-width: 820px) {
  .body { flex-direction: column; }
  .list { width: 100%; max-height: 40vh; border-right: 0; border-bottom: 1px solid #dde6f1; }
  .sheet { width: 94vw; }
}
</style>
