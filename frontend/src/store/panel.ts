import { reactive } from 'vue'

/**
 * 面板显示用的可配置项。
 * 运行时从 /panel-config.json 读取，改完刷新页面即可生效，不用重新打包。
 */
export interface PanelConfig {
  /** 角色名：显示在气泡署名、签到簿标题、桃信想法分隔条上 */
  characterName: string
  /** 角色名首字，用作头像占位 */
  characterInitial: string
  /** 主人称呼，显示在桃信首位与等级卡 */
  ownerName: string
}

export const panel = reactive<PanelConfig>({
  characterName: '圣园弥香',
  characterInitial: '弥',
  ownerName: '老师',
})

export async function loadPanelConfig(): Promise<void> {
  try {
    const r = await fetch('/panel-config.json', { cache: 'no-cache' })
    if (!r.ok) return
    const j = await r.json()
    if (j?.characterName) panel.characterName = String(j.characterName)
    if (j?.characterInitial) panel.characterInitial = String(j.characterInitial)
    if (j?.ownerName) panel.ownerName = String(j.ownerName)
    if (!j?.characterInitial && j?.characterName) {
      panel.characterInitial = String(j.characterName).slice(0, 1)
    }
  } catch {
    /* 读不到就用默认值 */
  }
}
