/**
 * 工作流卡片组件 - 左右分栏布局
 */

import { useCallback, forwardRef } from 'react'
import { useTranslation } from 'react-i18next'
import { Download, Trash2, Network, Send, Star, Check } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/Button'
import { PreviewCarousel } from './PreviewCarousel'
import { useWorkflowDrag } from './useWorkflowDrag'
import type { Workflow } from '@/types/workflow'

interface WorkflowCardProps {
  workflow: Workflow
  isSelected?: boolean
  isBatchMode?: boolean
  selectedWorkflowIds?: string[]
  onSelect?: (id: string) => void
  onAnalyze?: (workflow: Workflow) => void
  onLoad?: (workflow: Workflow) => void
  onExport?: (workflow: Workflow) => void
  onDelete?: (workflow: Workflow) => void
  onToggleFavorite?: (workflow: Workflow) => void
  onPreviewChange?: () => void
  className?: string
}

function formatDate(dateString: string) {
  const date = new Date(dateString)
  return date.toLocaleDateString('zh-CN', {
    year: '2-digit',
    month: '2-digit',
    day: '2-digit'
  }).replace(/\//g, '-')
}

export const WorkflowCard = forwardRef<HTMLDivElement, WorkflowCardProps>(function WorkflowCard(
  {
    workflow,
    isSelected = false,
    isBatchMode = false,
    selectedWorkflowIds = [],
    onSelect,
    onAnalyze,
    onLoad,
    onExport,
    onDelete,
    onToggleFavorite,
    onPreviewChange,
    className
  },
  ref
) {
  const { t } = useTranslation()

  const { isVisualDragging, handleMouseDown, wasDragTriggered } = useWorkflowDrag({
    workflowId: workflow.id,
    selectedWorkflowIds,
    isBatchMode,
    isSelected
  })

  const handleCardClick = useCallback(() => {
    if (isBatchMode && !wasDragTriggered() && onSelect) {
      onSelect(workflow.id)
    }
  }, [isBatchMode, onSelect, workflow.id, wasDragTriggered])

  return (
    <div
      ref={ref}
      data-workflow-card={workflow.id}
      className={cn(
        'group flex w-full flex-shrink-0 flex-col overflow-hidden rounded-xl border transition-all duration-200 cursor-grab',
        'bg-card shadow-soft hover:shadow-soft-md hover:-translate-y-1.5',
        'active:cursor-grabbing',
        isSelected
          ? 'border-success shadow-soft-md ring-1 ring-success'
          : 'border-border-subtle hover:border-border',
        isVisualDragging && 'opacity-50 scale-[0.98] border-primary ring-2 ring-primary/30',
        className
      )}
      onClick={handleCardClick}
      onMouseDown={handleMouseDown}
    >
      <div className="flex items-center justify-between border-b border-border-subtle bg-gradient-to-r from-card to-surface-hover px-4 py-1.5">
        <h3
          className="truncate text-base font-bold leading-tight text-foreground transition-colors group-hover:text-primary"
          title={workflow.name}
        >
          {workflow.name}
        </h3>
        <div className="flex shrink-0 items-center gap-1">
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
          {!isBatchMode && onExport && (
            <Button
              variant="ghost"
              size="icon"
              onClick={() => onExport(workflow)}
              className="size-6 rounded p-1 text-muted-foreground transition-colors hover:bg-surface-hover hover:text-primary"
              title={t('workflow.card.export')}
            >
              <Download className="size-3.5" />
            </Button>
          )}
          {!isBatchMode && onDelete && (
            <Button
              variant="ghost"
              size="icon"
              onClick={() => onDelete(workflow)}
              className="size-6 rounded p-1 text-muted-foreground transition-colors hover:bg-danger/10 hover:text-danger"
              title={t('common.delete')}
            >
              <Trash2 className="size-3.5" />
            </Button>
          )}
        </div>
      </div>

      <div className="flex flex-1 flex-row">
        <div className="size-[150px] shrink-0 border-r border-border-subtle">
          <PreviewCarousel
            preview={workflow.preview}
            previews={workflow.previews}
            height={150}
            workflowId={workflow.id}
            onPreviewChange={onPreviewChange}
          />
        </div>

        <div className="flex min-w-0 flex-1 flex-col bg-gradient-to-br from-card to-surface-hover p-4">
          <div className="mb-3 flex flex-wrap gap-1.5">
            {(workflow.tags || []).map((tag, index) => (
              <span
                key={index}
                className={cn(
                  'rounded border px-2 py-0.5 text-xs',
                  index === 0
                    ? 'border-primary/20 bg-primary/10 text-primary'
                    : 'border-border-subtle bg-surface-active text-foreground'
                )}
              >
                {tag}
              </span>
            ))}
          </div>

          <div className="line-clamp-3 flex-1 text-xs leading-relaxed text-muted-foreground">
            {workflow.description}
          </div>

          <div className="mt-auto border-t border-border-subtle/50 pt-3">
            <div className="mb-2 flex items-center justify-between font-mono text-xs text-muted-foreground">
              <span className="flex items-center gap-1">
                <Network className="size-3" />
                {t('workflow.card.nodeCount', { count: workflow.nodes })}
              </span>
              <span className="flex items-center gap-1">
                {formatDate(workflow.updatedAt)}
              </span>
            </div>

            <div className="flex gap-2">
              {!isBatchMode && workflow.rawData && onAnalyze && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="flex-1 gap-1 border border-border-subtle bg-surface-hover text-xs text-foreground hover:bg-surface-active"
                  onClick={() => onAnalyze(workflow)}
                >
                  <Network className="size-3" />
                  {t('workflow.card.analyze')}
                </Button>
              )}
              {!isBatchMode && onLoad && (
                <Button
                  size="sm"
                  className="flex-1 gap-1 bg-primary text-xs text-primary-foreground hover:bg-primary-hover"
                  onClick={() => onLoad(workflow)}
                >
                  <Send className="size-3" />
                  {t('workflow.card.load')}
                </Button>
              )}
              {!isBatchMode && onToggleFavorite && (
                <Button
                  variant="ghost"
                  size="sm"
                  className={cn(
                    'border border-border-subtle bg-surface-hover text-xs text-foreground hover:bg-surface-active',
                    workflow.isFavorite && 'border-warning/30 bg-warning/10 text-warning hover:bg-warning/20'
                  )}
                  onClick={() => onToggleFavorite(workflow)}
                  title={t('workflow.card.favorite')}
                >
                  <Star className={cn('h-3 w-3', workflow.isFavorite && 'fill-current')} />
                </Button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
})
