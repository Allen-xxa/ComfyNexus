/**
 * 提示词卡片组件
 */

import { useState, useCallback, useRef, useEffect, forwardRef } from 'react'
import { Copy, Pencil, Check, Trash2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/Button'
import { useDragContext } from './PromptDragContext'
import { useTranslation } from 'react-i18next'
import type { Prompt } from '@/stores/usePromptStore'

interface PromptCardProps {
  prompt: Prompt
  isSelected: boolean
  isBatchMode: boolean
  selectedPromptIds: string[]
  onSelect: (id: string) => void
  onEdit: (prompt: Prompt) => void
  onCopy: (text: string, type: 'positive' | 'negative') => void
  onToggleFavorite: (id: string) => void
  onDelete: (id: string) => void
  onHover: (prompt: Prompt | null) => void
}

export const PromptCard = forwardRef<HTMLDivElement, PromptCardProps>(function PromptCard(
  {
    prompt,
    isSelected,
    isBatchMode,
    selectedPromptIds,
    onSelect,
    onEdit,
    onCopy,
    onToggleFavorite: _onToggleFavorite,
    onDelete: _onDelete,
    onHover
  },
  ref
) {
  const { t } = useTranslation()
  const [copiedType, setCopiedType] = useState<'positive' | 'negative' | null>(null)
  const [isLocalDragging, setIsLocalDragging] = useState(false)
  
  const { isDragging: isGlobalDragging, startDrag, updatePosition, endDrag, setDropTargetId } = useDragContext()
  
  const mouseDownPosRef = useRef({ x: 0, y: 0 })
  const isDragTriggeredRef = useRef(false)
  const isMouseDownRef = useRef(false)

  useEffect(() => {
    if (isGlobalDragging) {
      onHover(null)
    }
  }, [isGlobalDragging, onHover])

  useEffect(() => {
    if (isGlobalDragging && isLocalDragging) {
      document.body.style.cursor = 'grabbing'
      document.body.style.userSelect = 'none'
    } else {
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }
    
    return () => {
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }
  }, [isGlobalDragging, isLocalDragging])

  const handleCopy = useCallback((type: 'positive' | 'negative', e: React.MouseEvent) => {
    e.stopPropagation()
    const text = type === 'positive' ? prompt.positivePrompt : prompt.negativePrompt
    onCopy(text, type)
    setCopiedType(type)
    setTimeout(() => setCopiedType(null), 1500)
  }, [prompt, onCopy])

  const handleEdit = useCallback((e: React.MouseEvent) => {
    e.stopPropagation()
    onEdit(prompt)
  }, [prompt, onEdit])

  const handleDelete = useCallback((e: React.MouseEvent) => {
    e.stopPropagation()
    _onDelete(prompt.id)
  }, [prompt, _onDelete])

  const handleCardClick = useCallback(() => {
    if (isBatchMode && !isDragTriggeredRef.current) {
      onSelect(prompt.id)
    }
  }, [isBatchMode, onSelect, prompt.id])

  const handleMouseEnter = useCallback(() => {
    if (!isBatchMode && !isGlobalDragging) {
      onHover(prompt)
    }
  }, [isBatchMode, isGlobalDragging, onHover, prompt])

  const handleMouseLeave = useCallback(() => {
    if (!isGlobalDragging) {
      onHover(null)
    }
  }, [isGlobalDragging, onHover])

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button !== 0) return
    if ((e.target as HTMLElement).closest('button')) return
    if (isBatchMode && !isSelected) return
    
    e.preventDefault()
    
    mouseDownPosRef.current = { x: e.clientX, y: e.clientY }
    isDragTriggeredRef.current = false
    isMouseDownRef.current = true
    
    const handleMouseMove = (moveEvent: MouseEvent) => {
      if (!isMouseDownRef.current) return
      
      const dx = moveEvent.clientX - mouseDownPosRef.current.x
      const dy = moveEvent.clientY - mouseDownPosRef.current.y
      const distance = Math.sqrt(dx * dx + dy * dy)
      
      if (distance > 5 && !isDragTriggeredRef.current) {
        isDragTriggeredRef.current = true
        setIsLocalDragging(true)
        startDrag(prompt.id, selectedPromptIds, moveEvent.clientX, moveEvent.clientY)
      }
      
      if (isDragTriggeredRef.current) {
        updatePosition(moveEvent.clientX, moveEvent.clientY)
        
        const target = document.elementFromPoint(moveEvent.clientX, moveEvent.clientY)
        const categoryItem = target?.closest('[data-category-id]')
        if (categoryItem) {
          const categoryId = categoryItem.getAttribute('data-category-id')
          const isVirtual = categoryItem.getAttribute('data-is-virtual') === 'true'
          const isFavorites = categoryId === 'favorites'
          
          if (categoryId && (!isVirtual || isFavorites)) {
            setDropTargetId(categoryId)
          } else {
            setDropTargetId(null)
          }
        } else {
          setDropTargetId(null)
        }
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

  // 参数展示：模型只显示文件名，其余压成短标签
  const params = prompt.params
  const modelName = params?.model ? params.model.split(/[\\/]/).pop() || '' : ''
  const chips: string[] = []
  if (params?.width && params?.height) chips.push(`${params.width}×${params.height}`)
  if (params?.steps) chips.push(`${params.steps} 步`)
  if (params?.cfg != null) chips.push(`CFG ${params.cfg}`)
  if (params?.sampler) chips.push(params.sampler)
  if (params?.seed != null) chips.push(`seed ${params.seed}`)
  const isVideo = params?.assetType === 'video'

  return (
    <div
      ref={ref}
      data-prompt-card={prompt.id}
      className={cn(
        'group flex h-[188px] w-full flex-shrink-0 overflow-hidden rounded-lg border transition-all duration-200 cursor-grab',
        'bg-card shadow-soft hover:shadow-soft-md hover:-translate-y-1.5',
        'active:cursor-grabbing',
        isSelected
          ? 'border-success shadow-soft-md ring-1 ring-success'
          : 'border-border-subtle hover:border-border',
        isVisualDragging && 'opacity-50 scale-[0.98] border-primary ring-2 ring-primary/30'
      )}
      onClick={handleCardClick}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      onMouseDown={handleMouseDown}
    >
      <div className="w-32 flex-shrink-0 border-r border-border-subtle bg-background cursor-grab">
        {prompt.previewImage ? (
          <img
            src={prompt.previewImage}
            alt={prompt.name}
            className="h-full w-full object-cover opacity-90 transition-opacity duration-300 group-hover:opacity-100"
            loading="lazy"
            draggable={false}
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-xs text-muted-foreground/60">
            {t('prompt.card.noPreview')}
          </div>
        )}
      </div>

      <div className="relative flex flex-1 flex-col justify-between p-3.5">
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between">
            <h3 className="max-w-[140px] truncate text-sm font-semibold text-foreground" title={prompt.name}>
              {prompt.name}
            </h3>

            {!isBatchMode && (
              <div className="absolute right-3 top-3 z-10 flex items-center overflow-hidden rounded-md opacity-0 shadow-soft transition-opacity group-hover:opacity-100">
                <Button
                  variant="ghost"
                  size="sm"
                  className={cn(
                    'h-6 w-6 p-0 bg-success/10 hover:bg-success/25 text-success',
                    copiedType === 'positive' && 'bg-success/25'
                  )}
                  onClick={(e) => handleCopy('positive', e)}
                >
                  {copiedType === 'positive' ? (
                    <Check className="size-3.5" />
                  ) : (
                    <Copy className="size-3.5" />
                  )}
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className={cn(
                    'h-6 w-6 p-0 bg-danger/10 hover:bg-danger/25 text-danger',
                    copiedType === 'negative' && 'bg-danger/25'
                  )}
                  onClick={(e) => handleCopy('negative', e)}
                >
                  {copiedType === 'negative' ? (
                    <Check className="size-3.5" />
                  ) : (
                    <Copy className="size-3.5" />
                  )}
                </Button>
              </div>
            )}

            {isBatchMode && (
              <div
                className={cn(
                  'flex size-5 items-center justify-center rounded border-2 transition-all duration-200',
                  isSelected
                    ? 'border-success bg-success shadow-soft'
                    : 'border-border-subtle bg-surface hover:border-success/50'
                )}
              >
                {isSelected && <Check className="size-3 text-primary-foreground" />}
              </div>
            )}
          </div>

          {modelName && (
            <div
              className="truncate font-mono text-[11px] text-muted-foreground"
              title={params.model}
            >
              {modelName}
            </div>
          )}

          {chips.length > 0 && (
            <div className="flex flex-wrap items-center gap-x-1.5 gap-y-1 text-[11px] text-muted-foreground/80">
              {isVideo && (
                <span className="rounded bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary">
                  VIDEO
                </span>
              )}
              {params?.workflowName && (
                <span
                  className="max-w-[8rem] truncate rounded bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary"
                  title={`${t('prompt.card.workflowSource')}: ${params.workflowName}`}
                >
                  ⚙ {params.workflowName}
                </span>
              )}
              {chips.map((chip) => (
                <span key={chip} className="rounded bg-muted px-1.5 py-0.5">
                  {chip}
                </span>
              ))}
            </div>
          )}

          {prompt.remark && (
            <div className="line-clamp-1 text-[11px] text-muted-foreground/60" title={prompt.remark}>
              {prompt.remark}
            </div>
          )}
        </div>

        <div className="mt-3 flex items-center gap-2">
          {prompt.tags.slice(0, 2).map((tag) => (
            <span
              key={tag}
              className="rounded border border-border-subtle bg-background/50 px-2 py-0.5 text-[11px] text-muted-foreground"
            >
              {tag}
            </span>
          ))}
          {prompt.tags.length > 2 && (
            <span className="text-[11px] text-muted-foreground">
              +{prompt.tags.length - 2}
            </span>
          )}

          {!isBatchMode && (
            <div className="ml-auto flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100">
              <Button
                variant="ghost"
                size="sm"
                className="h-6 w-6 p-0"
                onClick={handleEdit}
              >
                <Pencil className="size-3.5 text-muted-foreground hover:text-primary" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="h-6 w-6 p-0 hover:bg-danger/10"
                onClick={handleDelete}
              >
                <Trash2 className="size-3.5 text-muted-foreground hover:text-danger" />
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
})
