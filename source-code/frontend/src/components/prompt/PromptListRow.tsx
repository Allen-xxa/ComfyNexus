/**
 * 提示词列表行
 *
 * 左栏的紧凑列表项：缩略图 + 名称 + 提示词摘要 + 关键参数。
 * 点击即选中并在右侧详情面板展示，批量模式下点击改为勾选。
 */

import { useCallback, useRef, useState } from 'react'
import { Star } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useDragContext } from './PromptDragContext'
import type { Prompt } from '@/stores/usePromptStore'

interface PromptListRowProps {
  prompt: Prompt
  isActive: boolean
  isSelected: boolean
  isBatchMode: boolean
  selectedPromptIds: string[]
  onActivate: (prompt: Prompt) => void
  onToggleSelect: (id: string) => void
  onToggleFavorite: (id: string) => void
}

export function PromptListRow({
  prompt,
  isActive,
  isSelected,
  isBatchMode,
  selectedPromptIds,
  onActivate,
  onToggleSelect,
  onToggleFavorite
}: PromptListRowProps) {
  const [isLocalDragging, setIsLocalDragging] = useState(false)
  const { isDragging: isGlobalDragging, startDrag, updatePosition, endDrag, setDropTargetId } =
    useDragContext()

  const mouseDownPosRef = useRef({ x: 0, y: 0 })
  const isDragTriggeredRef = useRef(false)
  const isMouseDownRef = useRef(false)

  const params = prompt.params
  const modelName = params?.model ? params.model.split(/[\\/]/).pop() || '' : ''
  const paramText = [
    modelName,
    params?.sampler,
    params?.steps ? `${params.steps} 步` : ''
  ].filter(Boolean).join(' · ')

  const handleClick = useCallback(() => {
    if (isDragTriggeredRef.current) return
    if (isBatchMode) {
      onToggleSelect(prompt.id)
      return
    }
    onActivate(prompt)
  }, [isBatchMode, onActivate, onToggleSelect, prompt])

  const handleFavorite = useCallback((e: React.MouseEvent) => {
    e.stopPropagation()
    onToggleFavorite(prompt.id)
  }, [onToggleFavorite, prompt.id])

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button !== 0) return
    if ((e.target as HTMLElement).closest('button')) return

    mouseDownPosRef.current = { x: e.clientX, y: e.clientY }
    isDragTriggeredRef.current = false
    isMouseDownRef.current = true

    const handleMouseMove = (moveEvent: MouseEvent) => {
      if (!isMouseDownRef.current) return

      const dx = moveEvent.clientX - mouseDownPosRef.current.x
      const dy = moveEvent.clientY - mouseDownPosRef.current.y
      if (Math.sqrt(dx * dx + dy * dy) <= 5) return

      if (!isDragTriggeredRef.current) {
        isDragTriggeredRef.current = true
        setIsLocalDragging(true)
        startDrag(prompt.id, selectedPromptIds, moveEvent.clientX, moveEvent.clientY)
      }

      updatePosition(moveEvent.clientX, moveEvent.clientY)

      const target = document.elementFromPoint(moveEvent.clientX, moveEvent.clientY)
      const categoryItem = target?.closest('[data-category-id]')
      if (categoryItem) {
        const categoryId = categoryItem.getAttribute('data-category-id')
        const isVirtual = categoryItem.getAttribute('data-is-virtual') === 'true'
        if (categoryId && (!isVirtual || categoryId === 'favorites')) {
          setDropTargetId(categoryId)
        } else {
          setDropTargetId(null)
        }
      } else {
        setDropTargetId(null)
      }
    }

    const handleMouseUp = () => {
      isMouseDownRef.current = false
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)

      if (isDragTriggeredRef.current) {
        setIsLocalDragging(false)
        endDrag()
      }

      setTimeout(() => {
        isDragTriggeredRef.current = false
      }, 0)
    }

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
  }, [prompt.id, selectedPromptIds, startDrag, updatePosition, endDrag, setDropTargetId])

  const isVisualDragging = isLocalDragging && isGlobalDragging

  return (
    <div
      data-prompt-row={prompt.id}
      className={cn(
        'group flex cursor-pointer gap-3 rounded-lg border border-transparent px-2.5 py-2.5 transition-colors',
        isActive
          ? 'border-primary/30 bg-primary/10'
          : 'hover:border-border-subtle hover:bg-muted/50',
        isSelected && 'border-success/40 bg-success/10',
        isVisualDragging && 'opacity-50'
      )}
      onClick={handleClick}
      onMouseDown={handleMouseDown}
    >
      <div className="relative size-14 flex-shrink-0 overflow-hidden rounded-md border border-border-subtle bg-muted">
        {prompt.previewImage ? (
          <img
            src={prompt.previewImage}
            alt={prompt.name}
            className="size-full object-cover"
            loading="lazy"
            draggable={false}
          />
        ) : (
          <div className="flex size-full items-center justify-center text-[10px] text-muted-foreground/60">
            —
          </div>
        )}
        {params?.assetType === 'video' && (
          <span className="absolute bottom-0 left-0 rounded-tr bg-black/60 px-1 text-[9px] font-medium text-white">
            VIDEO
          </span>
        )}
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5">
          <span
            className={cn(
              'truncate text-[13px] font-medium',
              isActive ? 'text-primary' : 'text-foreground'
            )}
            title={prompt.name}
          >
            {prompt.name}
          </span>
          <button
            type="button"
            className="ml-auto flex-shrink-0 p-0.5"
            onClick={handleFavorite}
            title="收藏"
          >
            <Star
              className={cn(
                'size-3.5 transition-colors',
                prompt.isFavorite
                  ? 'fill-warning text-warning'
                  : 'text-muted-foreground/40 hover:text-warning'
              )}
            />
          </button>
        </div>

        <p className="mt-0.5 line-clamp-2 text-[11px] leading-snug text-muted-foreground">
          {prompt.positivePrompt || '（无提示词）'}
        </p>

        {paramText && (
          <p className="mt-1 truncate font-mono text-[10px] text-muted-foreground/70" title={paramText}>
            {paramText}
          </p>
        )}
      </div>

      {isBatchMode && (
        <div
          className={cn(
            'mt-1 flex size-4 flex-shrink-0 items-center justify-center rounded border-2',
            isSelected ? 'border-success bg-success' : 'border-border-subtle'
          )}
        >
          {isSelected && <span className="text-[9px] text-primary-foreground">✓</span>}
        </div>
      )}
    </div>
  )
}
