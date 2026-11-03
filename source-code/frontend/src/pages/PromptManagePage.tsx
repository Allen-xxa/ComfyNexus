/**
 * 提示词管理页面
 *
 * 三栏布局：分类树 | 提示词列表 | 详情面板
 * 选中条目直接在右侧展示全文与参数，编辑/新建也在右侧面板内完成，不再弹框。
 */

import { useState, useCallback, useRef, useEffect, useMemo } from 'react'
import { toast } from 'sonner'
import { LayoutGrid, List as ListIcon } from 'lucide-react'
import {
  PromptToolbar,
  PromptCategoryTree,
  PromptGrid,
  PromptListRow,
  PromptDetailPanel,
  CategoryManageDialog,
  DragProvider,
  PromptDragLayer,
  PromptSelectionBox,
  PromptBatchToolbar
} from '@/components/prompt'
import type { PromptPanelMode } from '@/components/prompt/PromptDetailPanel'
import { ConfirmDialog } from '@/components/common/ConfirmDialog'
import type { PromptGridRef } from '@/components/prompt/PromptGrid'
import { cn } from '@/lib/utils'
import {
  usePromptStore,
  type Prompt,
  type PromptInput,
  type CategoryInput
} from '@/stores/usePromptStore'
import { useTranslation } from 'react-i18next'

type ViewMode = 'list' | 'grid'

export default function PromptManagePage() {
  const { t } = useTranslation()
  const {
    prompts,
    categories,
    filterTags,
    selectedCategoryId,
    selectedPromptIds,
    isBatchMode,
    searchQuery,
    activeFilterTag,
    isLoading,
    loadData,
    setSelectedCategoryId,
    setActiveFilterTag,
    setSearchQuery,
    toggleBatchMode,
    togglePromptSelection,
    createPrompt,
    updatePrompt,
    deleteSelectedPrompts,
    toggleFavorite,
    movePromptsToCategory,
    createCategory,
    updateCategory,
    deleteCategory,
    exportPrompts,
    importPrompts,
    getFilteredPrompts,
    getPromptCount,
    setBatchMode,
    setSelectedPromptIds
  } = usePromptStore()

  const [showCategoryManage, setShowCategoryManage] = useState(false)
  const [activePromptId, setActivePromptId] = useState<string | null>(null)
  const [panelMode, setPanelMode] = useState<PromptPanelMode>('view')
  const [viewMode, setViewMode] = useState<ViewMode>('list')
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false)
  const [batchDeleteConfirmOpen, setBatchDeleteConfirmOpen] = useState(false)
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null)
  const [pendingDeleteName, setPendingDeleteName] = useState<string>('')
  const [sortBy, setSortBy] = useState<'name' | 'created_at' | 'updated_at' | 'usage_count'>('updated_at')

  const [isSelecting, setIsSelecting] = useState(false)
  const [selectionStart, setSelectionStart] = useState<{ x: number; y: number } | null>(null)
  const [selectionEnd, setSelectionEnd] = useState<{ x: number; y: number } | null>(null)

  const gridRef = useRef<PromptGridRef>(null)
  const selectionStartRef = useRef<{ x: number; y: number } | null>(null)
  const isSelectingRef = useRef(false)

  useEffect(() => {
    loadData()
  }, [loadData])

  const filteredPrompts = getFilteredPrompts()
  const totalCount = getPromptCount()

  const sortedPrompts = useMemo(() => {
    const filtered = getFilteredPrompts()
    return [...filtered].sort((a, b) => {
      let comparison = 0
      switch (sortBy) {
        case 'name':
          comparison = a.name.localeCompare(b.name, 'zh-CN')
          break
        case 'created_at':
          comparison = new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime()
          break
        case 'updated_at':
          comparison = new Date(a.updatedAt).getTime() - new Date(b.updatedAt).getTime()
          break
        case 'usage_count':
          comparison = (a.usageCount || 0) - (b.usageCount || 0)
          break
      }
      return sortBy === 'name' ? comparison : -comparison
    })
    // 筛选条件变化时 prompts 本身没变，必须把它们也列进依赖
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [getFilteredPrompts, sortBy, prompts, searchQuery, selectedCategoryId, activeFilterTag])

  /** 详情始终按 id 从最新列表里取，避免编辑后展示的还是旧对象 */
  const activePrompt = useMemo(
    () => prompts.find((p) => p.id === activePromptId) ?? null,
    [prompts, activePromptId]
  )

  // 首次加载或筛选后当前条目不在列表里时，自动选中第一条
  useEffect(() => {
    if (panelMode !== 'view') return
    if (activePromptId && sortedPrompts.some((p) => p.id === activePromptId)) return
    setActivePromptId(sortedPrompts[0]?.id ?? null)
  }, [sortedPrompts, activePromptId, panelMode])

  const handleActivatePrompt = useCallback((prompt: Prompt) => {
    setActivePromptId(prompt.id)
    if (panelMode !== 'view') setPanelMode('view')
  }, [panelMode])

  const handleStartCreate = useCallback(() => {
    setPanelMode('create')
  }, [])

  const handleStartEdit = useCallback((prompt: Prompt) => {
    setActivePromptId(prompt.id)
    setPanelMode('edit')
  }, [])

  const handleCancelEdit = useCallback(() => {
    setPanelMode('view')
  }, [])

  // 编辑/新建时按 Esc 直接退出编辑态
  useEffect(() => {
    if (panelMode === 'view') return

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setPanelMode('view')
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [panelMode])

  const handleSavePrompt = useCallback(async (data: PromptInput) => {
    if (panelMode === 'edit' && activePrompt) {
      const success = await updatePrompt(activePrompt.id, data)
      if (success) {
        toast.success(t('prompt.toast.updateSuccess'))
        setPanelMode('view')
        return true
      }
      toast.error(t('prompt.toast.updateFailed'))
      return false
    }

    const result = await createPrompt(data)
    if (result.prompt) {
      toast.success(t('prompt.toast.createSuccess'))
      setActivePromptId(result.prompt.id)
      setPanelMode('view')
      return true
    }
    toast.error(result.error || t('prompt.toast.createFailed'))
    return false
  }, [panelMode, activePrompt, updatePrompt, createPrompt, t])

  const handleCopyPrompt = useCallback((text: string, type: 'positive' | 'negative') => {
    navigator.clipboard.writeText(text)
    toast.success(type === 'positive' ? t('prompt.toast.copyPositive') : t('prompt.toast.copyNegative'))
  }, [t])

  const handleToggleFavorite = useCallback(async (id: string) => {
    const success = await toggleFavorite(id)
    if (!success) {
      toast.error(t('prompt.toast.updateFailed'))
    }
  }, [toggleFavorite, t])

  const handleDeletePrompt = useCallback((prompt: Prompt) => {
    setPendingDeleteId(prompt.id)
    setPendingDeleteName(prompt.name)
    setDeleteConfirmOpen(true)
  }, [])

  const handleConfirmDelete = useCallback(async () => {
    if (!pendingDeleteId) return

    const success = await usePromptStore.getState().deletePrompt(pendingDeleteId)
    if (success) {
      toast.success(t('prompt.toast.deleteSuccess'))
      if (activePromptId === pendingDeleteId) {
        setActivePromptId(null)
        setPanelMode('view')
      }
    } else {
      toast.error(t('prompt.toast.deleteFailed'))
    }
    setDeleteConfirmOpen(false)
    setPendingDeleteId(null)
    setPendingDeleteName('')
  }, [pendingDeleteId, activePromptId, t])

  const handleBatchDeleteClick = useCallback(() => {
    setBatchDeleteConfirmOpen(true)
  }, [])

  const handleBatchDeleteConfirm = useCallback(async () => {
    const success = await deleteSelectedPrompts()
    if (success) {
      toast.success(t('prompt.toast.batchDeleteSuccess'))
    } else {
      toast.error(t('prompt.toast.deleteFailed'))
    }
    setBatchDeleteConfirmOpen(false)
  }, [deleteSelectedPrompts, t])

  const findCategoryById = useCallback((categoryId: string, categoryList: typeof categories): typeof categories[0] | undefined => {
    for (const category of categoryList) {
      if (category.id === categoryId) {
        return category
      }
      if (category.children) {
        const found = findCategoryById(categoryId, category.children)
        if (found) return found
      }
    }
    return undefined
  }, [])

  const handleDropToCategory = useCallback(async (categoryId: string, promptIds: string[]) => {
    const count = promptIds.length

    if (categoryId === 'favorites') {
      let successCount = 0
      for (const id of promptIds) {
        const success = await toggleFavorite(id)
        if (success) successCount++
      }
      if (successCount > 0) {
        toast.success(t('prompt.toast.favoriteSuccess', { count: successCount }))
      } else {
        toast.error(t('prompt.toast.favoriteFailed'))
      }
      return
    }

    const success = await movePromptsToCategory(promptIds, categoryId)
    if (success) {
      const category = findCategoryById(categoryId, categories)
      toast.success(t('prompt.toast.moveSuccess', { count, category: category?.name || categoryId }))
    } else {
      toast.error(t('prompt.toast.moveFailed'))
    }
  }, [movePromptsToCategory, toggleFavorite, categories, findCategoryById, t])

  const handleAddCategory = useCallback(async (data: CategoryInput) => {
    const newCategory = await createCategory(data)
    if (newCategory) {
      toast.success(t('prompt.toast.categoryAddSuccess'))
    } else {
      toast.error(t('prompt.toast.categoryAddFailed'))
    }
  }, [createCategory, t])

  const handleUpdateCategory = useCallback(async (id: string, data: Partial<CategoryInput>) => {
    const success = await updateCategory(id, data)
    if (success) {
      toast.success(t('prompt.toast.categoryUpdateSuccess'))
    } else {
      toast.error(t('prompt.toast.categoryUpdateFailed'))
    }
  }, [updateCategory, t])

  const handleDeleteCategory = useCallback(async (id: string) => {
    const success = await deleteCategory(id)
    if (success) {
      toast.success(t('prompt.toast.categoryDeleteSuccess'))
    } else {
      const error = usePromptStore.getState().error
      toast.error(error || t('prompt.toast.categoryDeleteFailed'))
    }
  }, [deleteCategory, t])

  const handleExport = useCallback(async () => {
    const result = await exportPrompts()
    if (result.success && result.data) {
      const blob = new Blob([JSON.stringify(result.data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `prompts_${new Date().toISOString().slice(0, 10)}.json`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      toast.success(t('prompt.toast.exportSuccess'))
    } else {
      toast.error(result.error || t('prompt.toast.exportFailed'))
    }
  }, [exportPrompts, t])

  const handleImport = useCallback(async (data: unknown) => {
    const result = await importPrompts(data)
    if (result.success) {
      toast.success(result.message || t('prompt.toast.importSuccess', { count: result.importedCount || 0 }))
    } else {
      toast.error(result.error || t('prompt.toast.importFailed'))
    }
  }, [importPrompts, t])

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
    const cardRefs = gridRef.current?.getCardRefs() ?? new Map()

    cardRefs.forEach((cardEl, promptId) => {
      const cardRect = cardEl.getBoundingClientRect()

      if (
        cardRect.left < selectionRect.right &&
        cardRect.right > selectionRect.left &&
        cardRect.top < selectionRect.bottom &&
        cardRect.bottom > selectionRect.top
      ) {
        intersectingIds.push(promptId)
      }
    })

    return intersectingIds
  }, [])

  const handleSelectionMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button !== 0) return
    if ((e.target as HTMLElement).closest('[data-prompt-card]')) return

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

      usePromptStore.setState(state => {
        const newIds = new Set(state.selectedPromptIds)
        intersectingIds.forEach(id => newIds.add(id))
        return { selectedPromptIds: Array.from(newIds) }
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

  return (
    <DragProvider onDrop={handleDropToCategory}>
      <div className="flex h-full flex-col">
        <header className="flex-shrink-0 border-b border-border-subtle bg-surface p-4">
          <PromptToolbar
            searchQuery={searchQuery}
            onSearchChange={setSearchQuery}
            filterTags={filterTags}
            activeFilterTag={activeFilterTag}
            onFilterTagChange={setActiveFilterTag}
            isBatchMode={isBatchMode}
            selectedCount={selectedPromptIds.length}
            totalCount={totalCount}
            onToggleBatchMode={toggleBatchMode}
            onAddPrompt={handleStartCreate}
            onImport={handleImport}
            onExport={handleExport}
            sortBy={sortBy}
            onSortChange={setSortBy}
          />
        </header>

        <main className="flex min-h-0 flex-1 overflow-hidden">
          <aside className="w-52 flex-shrink-0 border-r border-border-subtle bg-surface">
            <PromptCategoryTree
              categories={categories}
              selectedCategoryId={selectedCategoryId}
              onSelectCategory={setSelectedCategoryId}
              onOpenCategoryManage={() => setShowCategoryManage(true)}
            />
          </aside>

          <section
            className={cn(
              'flex flex-shrink-0 flex-col border-r border-border-subtle bg-surface',
              viewMode === 'grid' ? 'w-[440px]' : 'w-[336px]'
            )}
          >
            <div className="flex flex-shrink-0 items-center justify-between border-b border-border-subtle px-3 py-1.5">
              <span className="text-[11px] text-muted-foreground">
                {t('prompt.toolbar.totalPrompts', { count: filteredPrompts.length })}
              </span>
              <div className="flex items-center gap-0.5">
                <button
                  type="button"
                  className={cn(
                    'rounded p-1 transition-colors',
                    viewMode === 'list'
                      ? 'bg-primary/10 text-primary'
                      : 'text-muted-foreground hover:bg-muted'
                  )}
                  title={t('prompt.detail.viewList')}
                  onClick={() => setViewMode('list')}
                >
                  <ListIcon className="size-3.5" />
                </button>
                <button
                  type="button"
                  className={cn(
                    'rounded p-1 transition-colors',
                    viewMode === 'grid'
                      ? 'bg-primary/10 text-primary'
                      : 'text-muted-foreground hover:bg-muted'
                  )}
                  title={t('prompt.detail.viewGrid')}
                  onClick={() => setViewMode('grid')}
                >
                  <LayoutGrid className="size-3.5" />
                </button>
              </div>
            </div>

            <div
              className={cn('min-h-0 flex-1 overflow-y-auto', viewMode === 'grid' ? 'p-3' : 'space-y-0.5 p-1.5')}
              onMouseDown={viewMode === 'grid' ? handleSelectionMouseDown : undefined}
            >
              {isLoading ? (
                <div className="flex h-full items-center justify-center">
                  <div className="text-muted-foreground">{t('prompt.loading')}</div>
                </div>
              ) : sortedPrompts.length === 0 ? (
                <div className="flex h-full items-center justify-center px-4">
                  <p className="text-center text-xs text-muted-foreground">{t('prompt.card.noPrompts')}</p>
                </div>
              ) : viewMode === 'list' ? (
                sortedPrompts.map((prompt) => (
                  <PromptListRow
                    key={prompt.id}
                    prompt={prompt}
                    isActive={activePromptId === prompt.id}
                    isSelected={selectedPromptIds.includes(prompt.id)}
                    isBatchMode={isBatchMode}
                    selectedPromptIds={selectedPromptIds}
                    onActivate={handleActivatePrompt}
                    onToggleSelect={togglePromptSelection}
                    onToggleFavorite={handleToggleFavorite}
                  />
                ))
              ) : (
                <PromptGrid
                  ref={gridRef}
                  prompts={sortedPrompts}
                  selectedPromptIds={selectedPromptIds}
                  isBatchMode={isBatchMode}
                  activePromptId={activePromptId}
                  onSelectPrompt={togglePromptSelection}
                  onActivatePrompt={handleActivatePrompt}
                  onEditPrompt={handleStartEdit}
                  onCopyPrompt={handleCopyPrompt}
                  onToggleFavorite={handleToggleFavorite}
                  onDeletePrompt={(id) => {
                    const target = prompts.find((p) => p.id === id)
                    if (target) handleDeletePrompt(target)
                  }}
                />
              )}
            </div>
          </section>

          <section className="min-w-0 flex-1">
            <PromptDetailPanel
              prompt={activePrompt}
              categories={categories}
              mode={panelMode}
              onStartCreate={handleStartCreate}
              onStartEdit={handleStartEdit}
              onCancelEdit={handleCancelEdit}
              onSave={handleSavePrompt}
              onCopy={handleCopyPrompt}
              onToggleFavorite={handleToggleFavorite}
              onDelete={handleDeletePrompt}
            />
          </section>
        </main>

        <CategoryManageDialog
          open={showCategoryManage}
          onOpenChange={setShowCategoryManage}
          categories={categories}
          onAddCategory={handleAddCategory}
          onUpdateCategory={handleUpdateCategory}
          onDeleteCategory={handleDeleteCategory}
        />

        <PromptDragLayer getCardRefs={() => gridRef.current?.getCardRefs() ?? new Map()} />

        {isSelecting && selectionStart && selectionEnd && (
          <PromptSelectionBox
            startPoint={selectionStart}
            endPoint={selectionEnd}
          />
        )}

        <ConfirmDialog
          open={deleteConfirmOpen}
          onOpenChange={setDeleteConfirmOpen}
          title={t('prompt.confirm.deleteTitle')}
          description={t('prompt.confirm.deleteDescription', { name: pendingDeleteName })}
          confirmText={t('prompt.confirm.confirmButton')}
          variant="destructive"
          onConfirm={handleConfirmDelete}
        />

        <ConfirmDialog
          open={batchDeleteConfirmOpen}
          onOpenChange={setBatchDeleteConfirmOpen}
          title={t('prompt.confirm.batchDeleteTitle')}
          description={t('prompt.confirm.batchDeleteDescription', { count: selectedPromptIds.length })}
          confirmText={t('prompt.confirm.confirmButton')}
          variant="destructive"
          onConfirm={handleBatchDeleteConfirm}
        />

        <PromptBatchToolbar
          selectedCount={selectedPromptIds.length}
          totalCount={filteredPrompts.length}
          onClearSelection={() => {
            setSelectedPromptIds([])
            setBatchMode(false)
          }}
          onBatchFavorite={async () => {
            let successCount = 0
            for (const id of selectedPromptIds) {
              const success = await toggleFavorite(id)
              if (success) successCount++
            }
            if (successCount > 0) {
              toast.success(t('prompt.toast.favoriteSuccess', { count: successCount }))
            }
          }}
          onBatchDelete={handleBatchDeleteClick}
        />
      </div>
    </DragProvider>
  )
}
