/**
 * 工作流管理页面
 */

import { useState, useCallback, useEffect, useMemo, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { Upload, Search, Loader2, FolderOpen, CheckSquare, FolderSync, Cog, LayoutGrid, LayoutList } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui'
import { Input } from '@/components/ui/Input'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { ResizableSidebar } from '@/components/common/ResizableSidebar'
import { WorkflowSidebar, WorkflowDragLayer, WorkflowSelectionBox, WorkflowBatchToolbar, WorkflowGrid, WorkflowListView, WorkflowDetailPanel, WorkflowSettingsModal } from '@/components/workflow'
import { DragProvider, useDragContext } from '@/components/workflow/WorkflowDragContext'
import { useWorkflowStore } from '@/stores/useWorkflowStore'
import { useEnvStore } from '@/stores/useEnvStore'
import { workflowApi } from '@/api/workflow'
import { toast } from '@/utils/toast'
import { loadNodeTypeMap, loadLocalNodeMap } from '@/utils/workflowParser'
import { EnvRequiredGuide } from '@/components/common/EnvRequiredGuide'
import type { Workflow, WorkflowInfoUpdate } from '@/types/workflow'
import type { WorkflowGridRef } from '@/components/workflow/WorkflowGrid'
import type { WorkflowListRef } from '@/components/workflow/WorkflowListView'

function WorkflowManagePageInner() {
  const { t } = useTranslation()
  const currentEnvId = useEnvStore(state => state.currentEnvId)
  const {
    isLoading,
    getFilteredWorkflows,
    refreshWorkflows,
    deleteWorkflow,
    toggleFavorite,
    updateWorkflowInfo,
    addWorkflow,
    selectedWorkflowIds,
    isBatchMode,
    toggleWorkflowSelection,
    clearSelection,
    batchToggleFavorite,
    batchDeleteWorkflows,
    setBatchMode,
    addFolder,
    updateFolder,
    deleteFolder,
    filterTags,
    activeFilterTag,
    setActiveFilterTag,
    viewMode,
    setViewMode
  } = useWorkflowStore()

  const { dropTargetId } = useDragContext()

  const [activeWorkflowId, setActiveWorkflowId] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [isImporting, setIsImporting] = useState(false)
  
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false)
  const [workflowToDelete, setWorkflowToDelete] = useState<Workflow | null>(null)
  const [batchDeleteConfirmOpen, setBatchDeleteConfirmOpen] = useState(false)
  const [folderDeleteOpen, setFolderDeleteOpen] = useState(false)
  const [pendingFolderDelete, setPendingFolderDelete] = useState<{ id: string; name: string; hasWorkflows: boolean } | null>(null)
  const [settingsOpen, setSettingsOpen] = useState(false)
  
  const [isSelecting, setIsSelecting] = useState(false)
  const [selectionStart, setSelectionStart] = useState<{ x: number; y: number } | null>(null)
  const [selectionEnd, setSelectionEnd] = useState<{ x: number; y: number } | null>(null)
  
  const gridRef = useRef<WorkflowGridRef>(null)
  const listRef = useRef<WorkflowListRef>(null)
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const selectionStartRef = useRef<{ x: number; y: number } | null>(null)
  const isSelectingRef = useRef(false)

  useEffect(() => {
    if (currentEnvId) {
      refreshWorkflows()
      // 预加载节点映射表（强制检查是否需要重新扫描）
      loadNodeTypeMap().then(() => {
        loadLocalNodeMap(true).catch(() => {})
      }).catch(() => {})
    }
  }, [currentEnvId, refreshWorkflows])

  const filteredWorkflows = getFilteredWorkflows().filter(w =>
    searchQuery === '' ||
    w?.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    w?.description?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (Array.isArray(w?.tags) && w.tags.some(tag => tag?.toLowerCase().includes(searchQuery.toLowerCase())))
  )

  // 右侧详情面板跟着当前筛选走：选中的工作流被筛掉或删除时自动落到列表第一项
  const activeWorkflow = useMemo(
    () => filteredWorkflows.find(w => w.id === activeWorkflowId) ?? null,
    [filteredWorkflows, activeWorkflowId]
  )

  useEffect(() => {
    if (activeWorkflow) return
    const first = filteredWorkflows[0]
    if (first) setActiveWorkflowId(first.id)
  }, [activeWorkflow, filteredWorkflows])

  const getCardRefs = useCallback((): Map<string, HTMLDivElement> =>
    (viewMode === 'list'
      ? listRef.current?.getCardRefs()
      : gridRef.current?.getCardRefs()) ?? new Map(),
  [viewMode])

  const handleOpenDetail = useCallback((workflow: Workflow) => {
    setActiveWorkflowId(workflow.id)
  }, [])

  const handleExport = useCallback(async (workflow: Workflow) => {
    const content = await workflowApi.exportWorkflow(workflow.id)
    if (content) {
      const blob = new Blob([content], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${workflow.name}.json`
      a.click()
      URL.revokeObjectURL(url)
      toast.success(t('workflow.toast.exportSuccess'))
    } else {
      toast.error(t('workflow.toast.exportFailed'))
    }
  }, [t])

  const handleImport = useCallback(() => {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = '.json'
    input.onchange = async (e) => {
      const file = (e.target as HTMLInputElement).files?.[0]
      if (file) {
        setIsImporting(true)
        const workflow = await workflowApi.importWorkflow(file)
        if (workflow) {
          addWorkflow(workflow)
          toast.success(t('workflow.toast.importSuccess'))
        } else {
          toast.error(t('workflow.toast.importFailed'))
        }
        setIsImporting(false)
      }
    }
    input.click()
  }, [addWorkflow, t])

  const handleDeleteClick = useCallback((workflow: Workflow) => {
    setWorkflowToDelete(workflow)
    setDeleteConfirmOpen(true)
  }, [])

  const confirmDelete = useCallback(async () => {
    if (workflowToDelete) {
      await deleteWorkflow(workflowToDelete.id)
      toast.success(t('workflow.toast.deleteSuccess'))
      setDeleteConfirmOpen(false)
      setWorkflowToDelete(null)
    }
  }, [workflowToDelete, deleteWorkflow, t])

  const handleToggleFavorite = useCallback(async (workflow: Workflow) => {
    await toggleFavorite(workflow.id)
  }, [toggleFavorite])

  const handleSaveInfo = useCallback(async (workflowId: string, info: WorkflowInfoUpdate) => {
    await updateWorkflowInfo(workflowId, info)
  }, [updateWorkflowInfo])

  const getIntersectingCardIds = useCallback((
    start: { x: number; y: number },
    end: { x: number; y: number }
  ): string[] => {
    const selectionRect = {
      left: Math.min(start.x, end.x),
      right: Math.max(start.x, end.x),
      top: Math.min(start.y, end.y),
      bottom: Math.max(start.y, end.y)
    }

    const intersectingIds: string[] = []
    const cardRefs = getCardRefs()

    cardRefs.forEach((cardEl, workflowId) => {
      const cardRect = cardEl.getBoundingClientRect()

      if (
        cardRect.left < selectionRect.right &&
        cardRect.right > selectionRect.left &&
        cardRect.top < selectionRect.bottom &&
        cardRect.bottom > selectionRect.top
      ) {
        intersectingIds.push(workflowId)
      }
    })

    return intersectingIds
  }, [getCardRefs])

  const handleSelectionMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button !== 0) return
    if ((e.target as HTMLElement).closest('[data-workflow-card]')) return

    const point = { x: e.clientX, y: e.clientY }
    setIsSelecting(true)
    setSelectionStart(point)
    setSelectionEnd(point)
    selectionStartRef.current = point
    isSelectingRef.current = true
  }, [])

  useEffect(() => {
    if (!isSelecting) return

    const handleMouseMove = (e: MouseEvent) => {
      if (!isSelectingRef.current || !selectionStartRef.current) return

      setSelectionEnd({ x: e.clientX, y: e.clientY })

      const intersectingIds = getIntersectingCardIds(selectionStartRef.current, { x: e.clientX, y: e.clientY })
      
      if (intersectingIds.length > 0 && !isBatchMode) {
        setBatchMode(true)
      }
      
      useWorkflowStore.setState(state => {
        const newIds = new Set(state.selectedWorkflowIds)
        intersectingIds.forEach(id => newIds.add(id))
        return { selectedWorkflowIds: Array.from(newIds) }
      })
    }

    const handleMouseUp = () => {
      setIsSelecting(false)
      setSelectionStart(null)
      setSelectionEnd(null)
      isSelectingRef.current = false
      selectionStartRef.current = null
    }

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)

    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }
  }, [isSelecting, getIntersectingCardIds, isBatchMode, setBatchMode])

  useEffect(() => {
    if (!isSelecting) return

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setIsSelecting(false)
        setSelectionStart(null)
        setSelectionEnd(null)
        isSelectingRef.current = false
        selectionStartRef.current = null
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [isSelecting])

  const handleBatchFavorite = useCallback(async () => {
    if (selectedWorkflowIds.length === 0) return
    const success = await batchToggleFavorite(selectedWorkflowIds)
    if (success) {
      toast.success(t('workflow.toast.favoriteSuccess', { count: selectedWorkflowIds.length }))
    } else {
      toast.error(t('workflow.toast.favoriteFailed'))
    }
  }, [selectedWorkflowIds, batchToggleFavorite, t])

  const handleBatchDeleteClick = useCallback(() => {
    setBatchDeleteConfirmOpen(true)
  }, [])

  const handleBatchDeleteConfirm = useCallback(async () => {
    if (selectedWorkflowIds.length === 0) return
    const success = await batchDeleteWorkflows(selectedWorkflowIds)
    if (success) {
      toast.success(t('workflow.toast.batchDeleteSuccess', { count: selectedWorkflowIds.length }))
    } else {
      toast.error(t('workflow.toast.deleteFailed'))
    }
    setBatchDeleteConfirmOpen(false)
  }, [selectedWorkflowIds, batchDeleteWorkflows, t])

  const handleCreateFolder = useCallback(async (parentId: string | null, name: string) => {
    const folder = await addFolder(name, parentId ?? undefined)
    if (!folder) toast.error(t('workflow.toast.createFolderFailed'))
    else toast.success(t('workflow.toast.createFolderSuccess'))
  }, [addFolder, t])

  const handleRenameFolder = useCallback(async (id: string, name: string) => {
    const ok = await updateFolder(id, { name })
    if (!ok) toast.error(t('workflow.toast.renameFolderFailed'))
  }, [updateFolder, t])

  const handleMoveFolder = useCallback(async (id: string, newParentId: string | null) => {
    const ok = await updateFolder(id, { parentId: newParentId ?? 'root' })
    if (!ok) toast.error(t('workflow.toast.folderMoveFailed'))
  }, [updateFolder, t])

  const handleDeleteFolderRequest = useCallback((id: string, name: string, hasWorkflows: boolean) => {
    setPendingFolderDelete({ id, name, hasWorkflows })
    setFolderDeleteOpen(true)
  }, [])

  const handleConfirmDeleteFolder = useCallback(async () => {
    if (!pendingFolderDelete) return
    const ok = await deleteFolder(pendingFolderDelete.id, true)
    if (ok) toast.success(t('workflow.toast.deleteFolderSuccess'))
    else toast.error(t('workflow.toast.deleteFolderFailed'))
    setFolderDeleteOpen(false)
    setPendingFolderDelete(null)
  }, [pendingFolderDelete, deleteFolder, t])

  return (
    <div className="flex h-full flex-col bg-background text-foreground">
      <header className="shrink-0 border-b border-border-subtle bg-surface p-4">
        <div className="flex items-center justify-between gap-4">
          <div className="relative max-w-md flex-1">
            <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder={t('workflow.searchPlaceholder')}
              className="w-full border border-border-subtle bg-surface-active py-1.5 pl-9 pr-3 text-sm text-foreground transition-colors placeholder:text-muted-foreground focus:border-primary"
            />
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-0.5 rounded-md border border-border-subtle bg-surface-active p-0.5">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setViewMode('list')}
                title={t('workflow.viewModes.list')}
                className={cn(
                  'size-7',
                  viewMode === 'list'
                    ? 'bg-primary/15 text-primary hover:bg-primary/20'
                    : 'text-muted-foreground hover:text-foreground'
                )}
              >
                <LayoutList className="size-4" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setViewMode('card')}
                title={t('workflow.viewModes.card')}
                className={cn(
                  'size-7',
                  viewMode === 'card'
                    ? 'bg-primary/15 text-primary hover:bg-primary/20'
                    : 'text-muted-foreground hover:text-foreground'
                )}
              >
                <LayoutGrid className="size-4" />
              </Button>
            </div>

            <Button
              variant={isBatchMode ? 'default' : 'outline'}
              size="sm"
              onClick={() => setBatchMode(!isBatchMode)}
              className={cn(
                isBatchMode && 'bg-success/15 text-success border-success hover:bg-success/20'
              )}
            >
              <CheckSquare className="size-4" />
              {isBatchMode ? t('workflow.batch.done') : t('workflow.batch.mode')}
            </Button>
            
            <Button
              onClick={handleImport}
              disabled={isImporting}
              className="gap-1.5 border border-primary/30 bg-primary/20 text-primary hover:bg-primary/30"
            >
              {isImporting ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Upload className="size-4" />
              )}
              {isImporting ? t('workflow.importing') : t('workflow.import')}
            </Button>

            <Button
              variant="ghost"
              size="sm"
              onClick={() => setSettingsOpen(true)}
              className="text-muted-foreground hover:text-foreground"
            >
              <Cog className="size-4" />
            </Button>
          </div>
        </div>

        {filterTags.length > 0 && (
          <div className="mt-3 flex items-center gap-2">
            <span className="text-xs text-muted-foreground">{t('workflow.quickFilter')}:</span>
            <div className="flex gap-2">
              {filterTags.map((tag) => (
                <Button
                  key={tag.id}
                  variant="ghost"
                  size="sm"
                  onClick={() => setActiveFilterTag(tag.id)}
                  className={cn(
                    'h-auto rounded-full px-3 py-1 text-xs',
                    activeFilterTag === tag.id
                      ? 'bg-primary/15 text-primary hover:bg-primary/20'
                      : 'bg-surface-active text-muted-foreground hover:text-foreground'
                  )}
                >
                  {tag.name}
                </Button>
              ))}
            </div>
          </div>
        )}
      </header>

      <main className="flex flex-1 overflow-hidden">
        <WorkflowSidebar
          className="z-10"
          dropTargetId={dropTargetId}
          onCreateFolder={handleCreateFolder}
          onRenameFolder={handleRenameFolder}
          onDeleteFolderRequest={handleDeleteFolderRequest}
          onMoveFolder={handleMoveFolder}
        />

        <div 
          ref={scrollContainerRef}
          className={cn('min-w-0 flex-1 overflow-y-auto', viewMode === 'list' ? 'p-3' : 'p-6')}
          onMouseDown={handleSelectionMouseDown}
        >
          {isLoading ? (
            <div className="flex h-64 items-center justify-center">
              <Loader2 className="size-8 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <>
              {viewMode === 'list' ? (
                <WorkflowListView
                  ref={listRef}
                  workflows={filteredWorkflows}
                  activeWorkflowId={activeWorkflowId}
                  selectedWorkflowIds={selectedWorkflowIds}
                  isBatchMode={isBatchMode}
                  onSelectWorkflow={toggleWorkflowSelection}
                  onOpenDetail={handleOpenDetail}
                  onExportWorkflow={handleExport}
                  onDeleteWorkflow={handleDeleteClick}
                  onToggleFavorite={handleToggleFavorite}
                />
              ) : (
                <WorkflowGrid
                  ref={gridRef}
                  workflows={filteredWorkflows}
                  selectedWorkflowIds={selectedWorkflowIds}
                  isBatchMode={isBatchMode}
                  onSelectWorkflow={toggleWorkflowSelection}
                  onAnalyzeWorkflow={handleOpenDetail}
                  onExportWorkflow={handleExport}
                  onDeleteWorkflow={handleDeleteClick}
                  onToggleFavorite={handleToggleFavorite}
                  onPreviewChange={refreshWorkflows}
                />
              )}

              {filteredWorkflows.length === 0 && (
                <div className="flex h-64 flex-col items-center justify-center text-muted-foreground">
                  <FolderOpen className="mb-4 size-12" />
                  <p>{searchQuery ? t('workflow.noResults') : t('workflow.empty')}</p>
                </div>
              )}
            </>
          )}
        </div>

        <ResizableSidebar
          storageKey="workflow-detail-panel"
          side="right"
          defaultWidth={360}
          minWidth={300}
          maxWidth={620}
        >
          <WorkflowDetailPanel
            className="min-h-0 flex-1"
            workflow={activeWorkflow}
            onExport={handleExport}
            onDelete={handleDeleteClick}
            onToggleFavorite={handleToggleFavorite}
            onSaveInfo={handleSaveInfo}
            onPreviewChange={refreshWorkflows}
          />
        </ResizableSidebar>
      </main>

      <WorkflowDragLayer getCardRefs={getCardRefs} />

      {isSelecting && selectionStart && selectionEnd && (
        <WorkflowSelectionBox
          startPoint={selectionStart}
          endPoint={selectionEnd}
        />
      )}

      <WorkflowBatchToolbar
        selectedCount={selectedWorkflowIds.length}
        totalCount={filteredWorkflows.length}
        onClearSelection={clearSelection}
        onBatchFavorite={handleBatchFavorite}
        onBatchDelete={handleBatchDeleteClick}
      />

      <AlertDialog open={deleteConfirmOpen} onOpenChange={setDeleteConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('workflow.deleteTitle')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('workflow.deleteConfirm', { name: workflowToDelete?.name || '' })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDelete}>{t('common.confirm')}</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={batchDeleteConfirmOpen} onOpenChange={setBatchDeleteConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('workflow.batch.deleteTitle')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('workflow.batch.deleteConfirm', { count: selectedWorkflowIds.length })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
            <AlertDialogAction onClick={handleBatchDeleteConfirm}>{t('common.confirm')}</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={folderDeleteOpen} onOpenChange={setFolderDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('workflow.folder.deleteTitle')}</AlertDialogTitle>
            <AlertDialogDescription>
              {pendingFolderDelete?.hasWorkflows
                ? t('workflow.folder.deleteWithWorkflows', { name: pendingFolderDelete.name })
                : t('workflow.folder.deleteConfirm', { name: pendingFolderDelete?.name || '' })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
            <AlertDialogAction onClick={handleConfirmDeleteFolder}>{t('common.confirm')}</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <WorkflowSettingsModal
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
      />
    </div>
  )
}

function WorkflowManagePageContent() {
  const currentEnvId = useEnvStore(state => state.currentEnvId)
  const environments = useEnvStore(state => state.environments)
  const noEnvironment = environments.length === 0 || !currentEnvId

  if (noEnvironment) {
    return (
      <EnvRequiredGuide 
        icon={<FolderSync className="size-24 text-muted-foreground" />}
      />
    )
  }

  return <WorkflowManagePageInner />
}

export default function WorkflowManagePage() {
  const { t } = useTranslation()
  
  const handleDropToFolder = useCallback(async (folderId: string, workflowIds: string[]) => {
    const { batchMoveToFolder, batchToggleFavorite } = useWorkflowStore.getState()
    const count = workflowIds.length
    
    if (folderId === 'favorites') {
      const success = await batchToggleFavorite(workflowIds)
      if (success) {
        toast.success(t('workflow.toast.favoriteSuccess', { count }))
      }
      return
    }
    
    const success = await batchMoveToFolder(workflowIds, folderId)
    if (success) {
      toast.success(t('workflow.toast.moveSuccess', { count }))
    }
  }, [t])

  return (
    <DragProvider onDrop={handleDropToFolder}>
      <WorkflowManagePageContent />
    </DragProvider>
  )
}
