/**
 * 资产拖拽层组件
 */

import { useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { useAssetDragContext } from './AssetDragContext'

interface AssetDragLayerProps {
  getCardRefs: () => Map<string, HTMLDivElement>
}

const EMPTY_IDS: string[] = []
const ORIGIN = { x: 0, y: 0 }

export function AssetDragLayer({ getCardRefs }: AssetDragLayerProps) {
  const dragContext = useAssetDragContext()
  const isDragging = dragContext?.isDragging ?? false
  const draggingAssetIds = dragContext?.draggingAssetIds ?? EMPTY_IDS
  const dragPosition = dragContext?.dragPosition ?? ORIGIN
  const layerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!isDragging || !layerRef.current || draggingAssetIds.length === 0) return

    const layer = layerRef.current
    layer.innerHTML = ''

    const cardRefs = getCardRefs()
    const stackCount = Math.min(draggingAssetIds.length, 5)
    const offset = 15

    const firstCard = cardRefs.get(draggingAssetIds[0])
    if (!firstCard) return
    
    const cardWidth = firstCard.offsetWidth
    const cardHeight = firstCard.offsetHeight

    for (let i = stackCount - 1; i >= 0; i--) {
      const cardId = draggingAssetIds[i]
      const cardEl = cardRefs.get(cardId)
      if (!cardEl) continue

      const clonedCard = cardEl.cloneNode(true) as HTMLDivElement
      clonedCard.style.position = 'absolute'
      clonedCard.style.left = `${i * offset}px`
      clonedCard.style.top = `${i * offset}px`
      clonedCard.style.margin = '0'
      clonedCard.style.transform = 'none'
      clonedCard.style.opacity = '0.5'
      clonedCard.style.pointerEvents = 'none'
      clonedCard.classList.add('shadow-soft-lg')
      clonedCard.style.zIndex = '1'
      clonedCard.style.width = `${cardWidth}px`
      clonedCard.style.height = `${cardHeight}px`
      
      layer.appendChild(clonedCard)
    }

    if (draggingAssetIds.length > 1) {
      const badge = document.createElement('div')
      badge.className = 'flex items-center justify-center rounded-full bg-primary text-primary-foreground text-sm font-bold shadow-soft px-2'
      badge.style.position = 'absolute'
      badge.style.right = '0'
      badge.style.top = '-10px'
      badge.style.minWidth = '28px'
      badge.style.height = '28px'
      badge.style.zIndex = '10'
      badge.textContent = String(draggingAssetIds.length)
      layer.appendChild(badge)
    }

    const totalWidth = cardWidth + (stackCount - 1) * offset
    const totalHeight = cardHeight + (stackCount - 1) * offset
    layer.style.width = `${totalWidth}px`
    layer.style.height = `${totalHeight}px`
  }, [isDragging, draggingAssetIds, getCardRefs])

  if (!isDragging) return null

  return createPortal(
    <div
      ref={layerRef}
      style={{
        position: 'fixed',
        left: dragPosition.x - 20,
        top: dragPosition.y - 20,
        zIndex: 9999,
        pointerEvents: 'none',
        willChange: 'transform'
      }}
    />,
    document.body
  )
}
