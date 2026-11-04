/**
 * 工作流详情面板
 *
 * 常驻在列表右侧，替代原先的"分析"弹窗：预览、信息编辑、统计、节点图、插件清单
 * 都在同一列里纵向排开，宽度由外层 ResizableSidebar 决定（节点图需要看细节时拉宽即可）。
 * 数据全部来自 store 里的 workflow.rawData，工作流被删除或切换筛选时由页面负责重选。
 */

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Download, Network, Star, Trash2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/Button'
import { PreviewCarousel } from './PreviewCarousel'
import { WorkflowGraph } from './WorkflowGraph'
import { WorkflowStats } from './WorkflowStats'
import { WorkflowInfoEditor } from './WorkflowInfoEditor'
import { DependencyPanel } from './DependencyPanel'
import { getWorkflowStats, loadNodeTypeMap, loadLocalNodeMap } from '@/utils/workflowParser'
import { workflowApi } from '@/api/workflow'
import type {
  PluginDependency,
  PluginInstallStatus,
  Workflow,
  WorkflowInfoUpdate
} from '@/types/workflow'

interface WorkflowDetailPanelProps {
  workflow: Workflow | null
  onExport: (workflow: Workflow) => void
  onDelete: (workflow: Workflow) => void
  onToggleFavorite: (workflow: Workflow) => void
  onSaveInfo: (workflowId: string, info: WorkflowInfoUpdate) => void
  onPreviewChange?: () => void
  className?: string
}

const FULL_DATE_OPTIONS: Intl.DateTimeFormatOptions = {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit'
}

export function WorkflowDetailPanel({
  workflow,
  onExport,
  onDelete,
  onToggleFavorite,
  onSaveInfo,
  onPreviewChange,
  className
}: WorkflowDetailPanelProps) {
  const { t } = useTranslation()
  const [selectedPluginId, setSelectedPluginId] = useState<string | null>(null)
  const [pluginStatusMap, setPluginStatusMap] = useState<Record<string, PluginInstallStatus>>({})
  const [statusNonce, setStatusNonce] = useState(0)
  const [isMapLoaded, setIsMapLoaded] = useState(false)

  // 节点类型映射是解析插件的前提；页面进入时已预热，这里只做兜底并记录就绪态
  useEffect(() => {
    let cancelled = false
    loadNodeTypeMap()
      .then(() => loadLocalNodeMap())
      .catch(() => undefined)
      .then(() => {
        if (!cancelled) setIsMapLoaded(true)
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    setSelectedPluginId(null)
  }, [workflow?.id])

  const stats = useMemo(() => {
    if (!workflow?.rawData || !isMapLoaded) return null
    return getWorkflowStats(workflow.rawData)
  }, [workflow, isMapLoaded])

  const refreshPluginStatus = useCallback(() => setStatusNonce((n) => n + 1), [])

  useEffect(() => {
    if (!stats || stats.plugins.length === 0) {
      setPluginStatusMap({})
      return
    }
    let cancelled = false
    workflowApi
      .checkPluginsStatus(stats.plugins.map((p) => ({ githubUrl: p.githubUrl, name: p.name })))
      .then((result) => {
        if (!cancelled) setPluginStatusMap(result)
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [stats, statusNonce])

  const plugins: PluginDependency[] = useMemo(() => {
    if (!stats) return []
    return stats.plugins.map((p) => ({
      githubUrl: p.githubUrl,
      name: p.name,
      color: p.color,
      nodeCount: p.count,
      nodes: p.nodes,
      installStatus: pluginStatusMap[p.name] || 'missing'
    }))
  }, [stats, pluginStatusMap])

  if (!workflow) {
    return (
      <div className={cn('flex h-full items-center justify-center p-6 text-center', className)}>
        <p className="text-sm text-muted-foreground">{t('workflow.detail.selectHint')}</p>
      </div>
    )
  }

  return (
    <div className={cn('flex h-full min-h-0 flex-col bg-surface', className)}>
      <div className="flex shrink-0 items-center gap-2 border-b border-border-subtle px-3 py-2">
        <span className="min-w-0 flex-1 truncate text-sm font-medium text-foreground" title={workflow.name}>
          {workflow.name}
        </span>
        <Button
          variant="ghost"
          size="icon"
          onClick={() => onToggleFavorite(workflow)}
          className={cn(
            'size-7 shrink-0 text-muted-foreground hover:bg-surface-hover hover:text-foreground',
            workflow.isFavorite && 'text-warning'
          )}
          title={t('workflow.card.favorite')}
        >
          <Star className={cn('size-4', workflow.isFavorite && 'fill-current')} />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          onClick={() => onExport(workflow)}
          className="size-7 shrink-0 text-muted-foreground hover:bg-surface-hover hover:text-primary"
          title={t('workflow.card.export')}
        >
          <Download className="size-4" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          onClick={() => onDelete(workflow)}
          className="size-7 shrink-0 text-muted-foreground hover:bg-danger/10 hover:text-danger"
          title={t('common.delete')}
        >
          <Trash2 className="size-4" />
        </Button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="px-3 pt-3">
          <PreviewCarousel
            preview={workflow.preview}
            previews={workflow.previews}
            height={160}
            workflowId={workflow.id}
            onPreviewChange={onPreviewChange}
          />
        </div>

        <div className="border-b border-border-subtle p-3">
          <WorkflowInfoEditor
            name={workflow.name}
            description={workflow.description || ''}
            tags={workflow.tags || []}
            onSave={(info) => onSaveInfo(workflow.id, info)}
          />
        </div>

        <div className="border-b border-border-subtle p-3 text-xs text-muted-foreground">
          <div className="flex items-center justify-between">
            <span>{t('workflow.createTime')}</span>
            <span className="font-mono text-foreground">
              {new Date(workflow.createdAt).toLocaleString('zh-CN', FULL_DATE_OPTIONS)}
            </span>
          </div>
          <div className="mt-1 flex items-center justify-between">
            <span>{t('workflow.updateTime')}</span>
            <span className="font-mono text-foreground">
              {new Date(workflow.updatedAt).toLocaleString('zh-CN', FULL_DATE_OPTIONS)}
            </span>
          </div>
        </div>

        {workflow.rawData ? (
          <>
            {stats && (
              <div className="border-b border-border-subtle p-3">
                <WorkflowStats
                  totalNodes={stats.totalNodes}
                  totalLinks={stats.totalLinks}
                  nodeTypesCount={stats.nodeTypes.length}
                  pluginsCount={stats.plugins.length}
                />
              </div>
            )}

            <div className="border-b border-border-subtle p-3">
              <div className="mb-2 flex items-center gap-1.5 text-[12px] font-bold text-foreground">
                <Network className="size-3.5 text-muted-foreground" />
                {t('workflow.detail.graph')}
              </div>
              <div className="h-[220px]">
                <WorkflowGraph
                  data={workflow.rawData}
                  selectedPluginId={selectedPluginId}
                  className="size-full"
                />
              </div>
            </div>

            <DependencyPanel
              plugins={plugins}
              selectedPluginId={selectedPluginId}
              onPluginClick={(name) => setSelectedPluginId((prev) => (prev === name ? null : name))}
              onRefresh={refreshPluginStatus}
              className="min-h-[220px]"
            />
          </>
        ) : (
          <div className="p-3 text-sm text-muted-foreground">{t('workflow.detail.noRawData')}</div>
        )}
      </div>
    </div>
  )
}
