/**
 * 工作流紧凑列表视图
 *
 * 一行一个工作流：缩略图 + 名称/说明 + 标签 + 节点数 + 更新日期。
 * 交互与卡片视图共用 useWorkflowDrag，因此拖到左侧文件夹移动、框选、批量勾选的手感一致；
 * 区别只在"单击"——列表的单击用于选中并驱动右侧详情面板。
 */

import { forwardRef, useCallback, useImperativeHandle, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { Check, Download, ImageOff, Star, Trash2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/Button'
import { useWorkflowDrag } from './useWorkflowDrag'
import type { Workflow } from '@/types/workflow'

export interface WorkflowListRef {
  getCardRefs: () => Map<string, HTMLDivElement>
}

interface WorkflowListViewProps {
  workflows: Workflow[]
  activeWorkflowId?: string | null
  selectedWorkflowIds: string[]
  isBatchMode: boolean
  onSelectWorkflow: (id: string) => void
  onOpenDetail: (workflow: Workflow) => void
  onExportWorkflow: (workflow: Workflow) => void
  onDeleteWorkflow: (workflow: Workflow) => void
  onToggleFavorite: (workflow: Workflow) => void
}

/** 行内只显示到 MM-DD，年份在详情面板里看全量 */
const formatRowDate = (dateString: string) => {
  const date = new Date(dateString)
  return `${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

interface WorkflowRowProps {
  workflow: Workflow
  isActive: boolean
  isSelected: boolean
  isBatchMode: boolean
  selectedWorkflowIds: string[]
  onSelectWorkflow: (id: string) => void
  onOpenDetail: (workflow: Workflow) => void
  onExportWorkflow: (workflow: Workflow) => void
  onDeleteWorkflow: (workflow: Workflow) => void
  onToggleFavorite: (workflow: Workflow) => void
  cardRef: (el: HTMLDivElement | null) => void
}

function WorkflowRow({
  workflow,
  isActive,
  isSelected,
  isBatchMode,
  selectedWorkflowIds,
  onSelectWorkflow,
  onOpenDetail,
  onExportWorkflow,
  onDeleteWorkflow,
  onToggleFavorite,
  cardRef
}: WorkflowRowProps) {
  const { t } = useTranslation()
  const { isVisualDragging, handleMouseDown, wasDragTriggered } = useWorkflowDrag({
    workflowId: workflow.id,
    selectedWorkflowIds,
    isBatchMode,
    isSelected
  })

  const handleClick = useCallback(() => {
    if (wasDragTriggered()) return
    if (isBatchMode) onSelectWorkflow(workflow.id)
    else onOpenDetail(workflow)
  }, [isBatchMode, onSelectWorkflow, onOpenDetail, wasDragTriggered, workflow])

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key !== 'Enter' && e.key !== ' ') return
    e.preventDefault()
    if (isBatchMode) onSelectWorkflow(workflow.id)
    else onOpenDetail(workflow)
  }, [isBatchMode, onSelectWorkflow, onOpenDetail, workflow])

  return (
    <div
      ref={cardRef}
      data-workflow-card={workflow.id}
      role="button"
      tabIndex={0}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      onMouseDown={handleMouseDown}
      className={cn(
        'group flex w-full cursor-grab items-center gap-3 rounded-lg border px-2 py-1.5 text-left transition-colors',
        'active:cursor-grabbing',
        isActive
          ? 'border-primary/40 bg-primary/10'
          : 'border-transparent hover:border-border-subtle hover:bg-surface-hover',
        isBatchMode && isSelected && 'border-success/50 bg-success/10',
        isVisualDragging && 'opacity-50 ring-2 ring-primary/30'
      )}
    >
      <div className="size-10 shrink-0 overflow-hidden rounded-md border border-border-subtle bg-surface-active">
        {workflow.preview ? (
          <img src={workflow.preview} alt={workflow.name} className="size-full object-cover" />
        ) : (
          <div className="flex size-full items-center justify-center">
            <ImageOff className="size-4 text-muted-foreground" />
          </div>
        )}
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5">
          <span className="truncate text-sm font-medium text-foreground">{workflow.name}</span>
          {workflow.isFavorite && <Star className="size-3 shrink-0 fill-current text-warning" />}
        </div>
        <div className="truncate text-xs text-muted-foreground">
          {workflow.description || t('workflow.detail.noDescription')}
        </div>
      </div>

      <div className="hidden shrink-0 items-center gap-1.5 lg:flex">
        {(workflow.tags || []).slice(0, 2).map((tag, index) => (
          <span
            key={tag}
            className={cn(
              'max-w-[110px] truncate rounded border px-1.5 py-0.5 text-[11px]',
              index === 0
                ? 'border-primary/20 bg-primary/10 text-primary'
                : 'border-border-subtle bg-surface-active text-foreground'
            )}
          >
            {tag}
          </span>
        ))}
      </div>

      <span className="w-16 shrink-0 text-right font-mono text-xs text-muted-foreground">
        {t('workflow.card.nodeCount', { count: workflow.nodes })}
      </span>
      <span className="w-12 shrink-0 text-right font-mono text-xs text-muted-foreground">
        {formatRowDate(workflow.updatedAt)}
      </span>

      {isBatchMode ? (
        <div
          className={cn(
            'flex size-5 shrink-0 items-center justify-center rounded border-2 transition-colors',
            isSelected
              ? 'border-success bg-success'
              : 'border-border-subtle bg-surface'
          )}
        >
          {isSelected && <Check className="size-3 text-primary-foreground" />}
        </div>
      ) : (
        <div className="flex shrink-0 items-center gap-1 opacity-0 transition-opacity group-focus-within:opacity-100 group-hover:opacity-100">
          <Button
            variant="ghost"
            size="icon"
            onClick={(e) => {
              e.stopPropagation()
              onToggleFavorite(workflow)
            }}
            className={cn(
              'size-6 rounded p-1 text-muted-foreground hover:bg-surface-hover hover:text-foreground',
              workflow.isFavorite && 'text-warning'
            )}
            title={t('workflow.card.favorite')}
          >
            <Star className={cn('size-3.5', workflow.isFavorite && 'fill-current')} />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={(e) => {
              e.stopPropagation()
              onExportWorkflow(workflow)
            }}
            className="size-6 rounded p-1 text-muted-foreground hover:bg-surface-hover hover:text-primary"
            title={t('workflow.card.export')}
          >
            <Download className="size-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={(e) => {
              e.stopPropagation()
              onDeleteWorkflow(workflow)
            }}
            className="size-6 rounded p-1 text-muted-foreground hover:bg-danger/10 hover:text-danger"
            title={t('common.delete')}
          >
            <Trash2 className="size-3.5" />
          </Button>
        </div>
      )}
    </div>
  )
}

export const WorkflowListView = forwardRef<WorkflowListRef, WorkflowListViewProps>(
  function WorkflowListView(
    {
      workflows,
      activeWorkflowId,
      selectedWorkflowIds,
      isBatchMode,
      onSelectWorkflow,
      onOpenDetail,
      onExportWorkflow,
      onDeleteWorkflow,
      onToggleFavorite
    },
    ref
  ) {
    const cardRefsRef = useRef<Map<string, HTMLDivElement>>(new Map())

    useImperativeHandle(ref, () => ({
      getCardRefs: () => cardRefsRef.current
    }), [])

    const setCardRef = useCallback((id: string) => (el: HTMLDivElement | null) => {
      if (el) {
        cardRefsRef.current.set(id, el)
      } else {
        cardRefsRef.current.delete(id)
      }
    }, [])

    return (
      <div className="space-y-1">
        {workflows.map((workflow) => (
          <WorkflowRow
            key={workflow.id}
            workflow={workflow}
            isActive={workflow.id === activeWorkflowId}
            isSelected={selectedWorkflowIds.includes(workflow.id)}
            isBatchMode={isBatchMode}
            selectedWorkflowIds={selectedWorkflowIds}
            onSelectWorkflow={onSelectWorkflow}
            onOpenDetail={onOpenDetail}
            onExportWorkflow={onExportWorkflow}
            onDeleteWorkflow={onDeleteWorkflow}
            onToggleFavorite={onToggleFavorite}
            cardRef={setCardRef(workflow.id)}
          />
        ))}
      </div>
    )
  }
)
