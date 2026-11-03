/**
 * 资产拖拽状态 Context
 *
 * 拆成独立模块：不在 Provider 内时返回 null，调用方可以无条件取用，
 * 不需要再用 try/catch 或 require 绕开 Hook 规则。
 */

import { createContext, useContext } from 'react'

export interface AssetDragContextValue {
  isDragging: boolean
  draggingAssetIds: string[]
  dragPosition: { x: number; y: number }
  dropTargetId: string | null
  startDrag: (assetId: string, selectedIds: string[], clientX: number, clientY: number) => void
  updatePosition: (x: number, y: number) => void
  endDrag: () => void
  cancelDrag: () => void
  setDropTargetId: (id: string | null) => void
}

export const AssetDragContext = createContext<AssetDragContextValue | null>(null)

export function useAssetDragContext(): AssetDragContextValue | null {
  return useContext(AssetDragContext)
}
