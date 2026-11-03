/**
 * 影院模式的界面构件显隐 Store
 *
 * nav    左侧菜单：应用导航 + 资产分类树
 * filter 顶部筛选区：资产库工具栏
 * detail 影院右侧详情栏
 *
 * 窗体全屏时三者一起收起，退出全屏或用影院舞台右上角的开关可逐项恢复。
 */

import { create } from 'zustand'

export type ChromeRegion = 'nav' | 'filter' | 'detail'

type HiddenMap = Record<ChromeRegion, boolean>

interface ChromeState {
  hidden: HiddenMap
  toggle: (region: ChromeRegion) => void
  hideAll: () => void
  showAll: () => void
}

const ALL_VISIBLE: HiddenMap = { nav: false, filter: false, detail: false }
const ALL_HIDDEN: HiddenMap = { nav: true, filter: true, detail: true }

export const useChromeStore = create<ChromeState>((set) => ({
  hidden: { ...ALL_VISIBLE },
  toggle: (region) =>
    set((state) => ({ hidden: { ...state.hidden, [region]: !state.hidden[region] } })),
  hideAll: () => set({ hidden: { ...ALL_HIDDEN } }),
  showAll: () => set({ hidden: { ...ALL_VISIBLE } })
}))
