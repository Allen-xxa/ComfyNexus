/**
 * 资产库页面
 */

import React, { useEffect, useMemo, useState, useCallback, useRef, Fragment } from 'react'
import { useTranslation } from 'react-i18next'
import { Folder, ChevronRight } from 'lucide-react'
import {
  AssetToolbar,
  AssetCategoryTree,
  AssetMasonryGrid,
  AssetGridView,
  AssetTheaterView,
  AssetContextMenu,
  AssetBatchToolbar,
  AssetSettingsDialog,
  ScanProgressBar,
  AssetInfoPanel,
  AssetDragProvider,
  AssetDragLayer,
  AssetSelectionBox,
  AssetCategoryManageDialog
} from '@/components/asset'
import { ConfirmDialog } from '@/components/common/ConfirmDialog'
import { Button } from '@/components/ui/Button'
import { useAssetStore } from '@/stores/useAssetStore'
import { useChromeStore } from '@/stores/useChromeStore'
import { useFullscreenStore } from '@/stores/useFullscreenStore'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import type { Asset } from '@/mocks/asset'
import type { AssetMasonryGridRef } from '@/components/asset'
import type { AssetCategory } from '@/mocks/asset'

function getCategoryPath(
  categoryId: string,
  categories: AssetCategory[]
): AssetCategory[] {
  const path: AssetCategory[] = []
  let current = categories.find((c) => c.id === categoryId)

  while (current) {
    path.unshift(current)
    current = current.parentId
      ? categories.find((c) => c.id === current!.parentId)
      : undefined
  }

  return path
}

interface ContextMenuState {
  asset: Asset | null
  position: { x: number; y: number } | null
}

export default function AssetLibraryPage() {
  const { t } = useTranslation()
  const {
    loadData,
    getFilteredAssets,
    deleteAssets,
    selectedAssetIds,
    clearSelection,
    toggleBatchMode,
    isBatchMode,
    updateAssetInfo,
    toggleFavorite,
    moveToCategory,
    assets,
    selectedCategoryId,
    setSelectedCategoryId,
    setBatchMode,
    categories,
    createCategory,
    updateCategory,
    deleteCategory,
    openLocation,
    incrementalScanLibrary,
    viewMode
  } = useAssetStore()

  // 影院模式：只记 id，资产数据始终从 store 派生，改名/评分才能实时反映在舞台上
  const [theaterAssetId, setTheaterAssetId] = useState<string | null>(null)
  const chromeHidden = useChromeStore((state) => state.hidden)
  const showAllChrome = useChromeStore((state) => state.showAll)
  const [selectedInfoAsset, setSelectedInfoAsset] = useState<Asset | null>(null)
  // 保留上一次的 asset 数据，让滑出动画期间内容不消失
  const [lastInfoAsset, setLastInfoAsset] = useState<Asset | null>(null)
  const [contextMenu, setContextMenu] = useState<ContextMenuState>({
    asset: null,
    position: null
  })
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [pendingDeleteIds, setPendingDeleteIds] = useState<string[]>([])
  const [showSettings, setShowSettings] = useState(false)
  const [showCategoryManage, setShowCategoryManage] = useState(false)

  const [infoPanelPinned, setInfoPanelPinned] = useState(() => {
    return localStorage.getItem('asset-info-panel-pinned') === 'true'
  })

  const handleToggleInfoPanelPin = useCallback(() => {
    setInfoPanelPinned(prev => {
      const newValue = !prev
      localStorage.setItem('asset-info-panel-pinned', String(newValue))
      return newValue
    })
  }, [])

  const [isSelecting, setIsSelecting] = useState(false)
  const [selectionStart, setSelectionStart] = useState<{ x: number; y: number } | null>(null)
  const [selectionEnd, setSelectionEnd] = useState<{ x: number; y: number } | null>(null)
  const selectionStartRef = useRef<{ x: number; y: number } | null>(null)
  const isSelectingRef = useRef(false)

  const gridRef = useRef<AssetMasonryGridRef>(null)
  const scrollContainerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    loadData()
    incrementalScanLibrary()
  }, [loadData, incrementalScanLibrary])

  const filteredAssets = getFilteredAssets()

  const theaterAsset = useMemo(
    () => (theaterAssetId ? assets.find((a) => a.id === theaterAssetId) ?? null : null),
    [assets, theaterAssetId]
  )

  const resolveCategoryPath = useCallback(
    (asset: Asset | null) =>
      asset?.categoryId
        ? getCategoryPath(asset.categoryId, categories).map((cat) => cat.name).join(' / ')
        : '',
    [categories]
  )

  useEffect(() => {
    if (selectedInfoAsset) {
      setLastInfoAsset(selectedInfoAsset)
    }
  }, [selectedInfoAsset])

  const infoAsset = selectedInfoAsset || lastInfoAsset
  const infoCategoryPath = resolveCategoryPath(infoAsset)

  // 进入影院模式时详情面板必须让位给舞台（固定态也一样收起），退出影院后按原状态回来
  const infoPanelInFlow = infoPanelPinned && !theaterAsset
  const infoPanelShown = !theaterAsset && (infoPanelPinned || !!selectedInfoAsset)

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

    cardRefs.forEach((cardEl, assetId) => {
      const cardRect = cardEl.getBoundingClientRect()

      if (
        cardRect.left < selectionRect.right &&
        cardRect.right > selectionRect.left &&
        cardRect.top < selectionRect.bottom &&
        cardRect.bottom > selectionRect.top
      ) {
        intersectingIds.push(assetId)
      }
    })

    return intersectingIds
  }, [])

  const handleSelectionMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button !== 0) return
    if ((e.target as HTMLElement).closest('[data-asset-card]')) return
    if ((e.target as HTMLElement).closest('[data-folder-card]')) return
    if ((e.target as HTMLElement).closest('button')) return

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
      
      useAssetStore.setState(state => {
        const newIds = new Set(state.selectedAssetIds)
        intersectingIds.forEach(id => newIds.add(id))
        return { selectedAssetIds: Array.from(newIds) }
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

  const handleDropToCategory = useCallback(async (categoryId: string, assetIds: string[]) => {
    const count = assetIds.length
    
    if (categoryId === 'favorites') {
      let successCount = 0
      for (const id of assetIds) {
        const success = await toggleFavorite(id)
        if (success) successCount++
      }
      if (successCount > 0) {
        toast.success(t('asset.toast.favoriteSuccess', { count: successCount }))
      } else {
        toast.error(t('asset.toast.favoriteFailed'))
      }
      return
    }
    
    const success = await moveToCategory(assetIds, categoryId)
    if (success) {
      toast.success(t('asset.toast.moveSuccess', { count }))
    } else {
      toast.error(t('asset.toast.moveFailed'))
    }
  }, [moveToCategory, toggleFavorite, t])

  // 单击延迟处理：避免悬浮 info 面板遮挡双击
  const clickTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const handleImageClick = useCallback((asset: Asset) => {
    if (isBatchMode) return
    // 延迟执行单击，给双击留出时间
    if (clickTimerRef.current) clearTimeout(clickTimerRef.current)
    clickTimerRef.current = setTimeout(() => {
      setSelectedInfoAsset(asset)
      clickTimerRef.current = null
    }, 250)
  }, [isBatchMode])

  const handleOpenTheater = useCallback((asset: Asset) => {
    setTheaterAssetId(asset.id)
  }, [])

  const handleImageDoubleClick = useCallback((asset: Asset) => {
    // 取消单击的延迟，防止 info 面板弹出
    if (clickTimerRef.current) {
      clearTimeout(clickTimerRef.current)
      clickTimerRef.current = null
    }
    handleOpenTheater(asset)
  }, [handleOpenTheater])

  const handleContextMenu = useCallback((e: React.MouseEvent, asset: Asset) => {
    e.preventDefault()
    setContextMenu({
      asset,
      position: { x: e.clientX, y: e.clientY }
    })
  }, [])

  const handleCloseContextMenu = useCallback(() => {
    setContextMenu({ asset: null, position: null })
  }, [])

  const handleCloseTheater = useCallback(() => {
    setTheaterAssetId(null)
    // 窗体全屏时保持收起，其余情况把菜单/筛选/详情放回原位
    if (!useFullscreenStore.getState().isFullscreen) {
      showAllChrome()
    }
  }, [showAllChrome])

  const handleBatchDeleteClick = useCallback(() => {
    setPendingDeleteIds(selectedAssetIds)
    setShowDeleteConfirm(true)
  }, [selectedAssetIds])

  const handleConfirmDelete = useCallback(async () => {
    if (pendingDeleteIds.length > 0) {
      await deleteAssets(pendingDeleteIds)
      clearSelection()
      toggleBatchMode()
    }
    setShowDeleteConfirm(false)
    setPendingDeleteIds([])
  }, [pendingDeleteIds, deleteAssets, clearSelection, toggleBatchMode])

  const handleCloseInfoPanel = useCallback(() => {
    setSelectedInfoAsset(null)
  }, [])

  const handleUpdateAssetInfo = useCallback(async (
    assetId: string,
    data: { filename?: string; description?: string; tags?: string[]; rating?: number }
  ) => {
    const result = await updateAssetInfo(assetId, data)
    if (result.success && result.asset) {
      if (selectedInfoAsset?.id === assetId) {
        setSelectedInfoAsset(result.asset)
      }
    }
    return result
  }, [updateAssetInfo, selectedInfoAsset])

  const handleDeleteAsset = useCallback(async (assetId: string) => {
    const success = await deleteAssets([assetId])
    if (success) {
      setSelectedInfoAsset(null)
      if (assetId === theaterAssetId) setTheaterAssetId(null)
    }
    return success
  }, [deleteAssets, theaterAssetId])

  const getCardRefs = useCallback(() => {
    return gridRef.current?.getCardRefs() ?? new Map()
  }, [])

  // 点击页面空白区域关闭悬浮 info 面板
  const handlePageClick = useCallback((e: React.MouseEvent) => {
    if (theaterAsset) return
    if (!infoPanelPinned && selectedInfoAsset) {
      const target = e.target as HTMLElement
      // 不关闭：点击在 info 面板内、卡片上、或对话框上
      if (target.closest('[data-info-panel]') || target.closest('[data-asset-card]')) return
      setSelectedInfoAsset(null)
    }
  }, [infoPanelPinned, selectedInfoAsset, theaterAsset])

  return (
    <AssetDragProvider onDrop={handleDropToCategory}>
      <div className="flex h-full flex-col" onClick={handlePageClick}>
        {!chromeHidden.filter && (
          <AssetToolbar
            onOpenSettings={() => setShowSettings(true)}
            hideLayoutControls={!!theaterAsset}
          />
        )}

        {/* 横向用 clip、纵向用 hidden：clip 不产生滚动容器，轨道列表定位时的滚动才不会顺带把
            整行（含分类树）推出可视区；纵向仍需 hidden 保证这一层按可用高度收缩，不被内容撑高 */}
        <main className="relative flex flex-1 overflow-y-hidden overflow-x-clip">
          {!chromeHidden.nav && (
            <AssetCategoryTree onOpenCategoryManage={() => setShowCategoryManage(true)} />
          )}

          <div className="relative flex min-h-0 min-w-0 flex-1">
            <div
              ref={scrollContainerRef}
              className={cn(
                'min-w-0 flex-1 bg-background',
                viewMode === 'grid' ? 'flex flex-col overflow-hidden' : 'overflow-y-auto'
              )}
              onMouseDown={handleSelectionMouseDown}
            >
              {selectedCategoryId &&
                selectedCategoryId !== 'all' &&
                selectedCategoryId !== 'favorites' &&
                selectedCategoryId !== 'uncategorized' && (
                  <div className="flex shrink-0 items-center gap-1 border-b border-border-subtle bg-surface px-4 py-2">
                    {getCategoryPath(selectedCategoryId, categories).map((cat, index, path) => (
                      <Fragment key={cat.id}>
                        {index > 0 && (
                          <ChevronRight className="size-4 text-muted-foreground" />
                        )}
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setSelectedCategoryId(cat.id)}
                          className={cn(
                            'h-auto gap-1 px-2 py-1 text-sm',
                            index === path.length - 1 && 'font-medium text-primary'
                          )}
                        >
                          <Folder className="size-3.5" />
                          {cat.name}
                        </Button>
                      </Fragment>
                    ))}
                  </div>
                )}
              {viewMode === 'grid' ? (
                <AssetGridView
                  ref={gridRef}
                  onImageClick={handleImageClick}
                  onImageDoubleClick={handleImageDoubleClick}
                  onView={handleOpenTheater}
                  onImageContextMenu={handleContextMenu}
                />
              ) : (
                <AssetMasonryGrid
                  ref={gridRef}
                  onImageClick={handleImageClick}
                  onImageDoubleClick={handleImageDoubleClick}
                  onView={handleOpenTheater}
                  onImageContextMenu={handleContextMenu}
                />
              )}
            </div>

            <div
              className={cn(
                'overflow-hidden transition-all duration-300 ease-in-out',
                infoPanelInFlow
                  ? 'w-[320px] shrink-0'
                  : 'absolute right-0 top-0 z-40 h-full w-[320px] shadow-lg',
                infoPanelShown
                  ? 'translate-x-0 opacity-100'
                  : 'pointer-events-none translate-x-full opacity-0'
              )}
              data-info-panel
            >
              {(lastInfoAsset || infoPanelPinned) && (
                <AssetInfoPanel
                  asset={selectedInfoAsset || lastInfoAsset}
                  onClose={handleCloseInfoPanel}
                  onUpdate={handleUpdateAssetInfo}
                  pinned={infoPanelPinned}
                  onTogglePin={handleToggleInfoPanelPin}
                  onDelete={handleDeleteAsset}
                  categoryPath={infoCategoryPath}
                  onOpenLocation={openLocation}
                />
              )}
            </div>

            {theaterAsset && (
              <div className="absolute inset-0 z-30 flex flex-col bg-theater">
                <AssetTheaterView
                  asset={theaterAsset}
                  assets={filteredAssets}
                  categoryPath={resolveCategoryPath(theaterAsset)}
                  onNavigate={(item) => setTheaterAssetId(item.id)}
                  onClose={handleCloseTheater}
                  onUpdate={handleUpdateAssetInfo}
                  onDelete={handleDeleteAsset}
                  onOpenLocation={openLocation}
                />
              </div>
            )}
          </div>
        </main>

        <AssetContextMenu
          asset={contextMenu.asset}
          position={contextMenu.position}
          onClose={handleCloseContextMenu}
        />

        <AssetBatchToolbar onDeleteConfirm={handleBatchDeleteClick} />

        <AssetSettingsDialog
          open={showSettings}
          onOpenChange={setShowSettings}
        />

        <ScanProgressBar />

        <AssetCategoryManageDialog
          open={showCategoryManage}
          onOpenChange={setShowCategoryManage}
          categories={categories}
          assets={assets}
          onCreateCategory={createCategory}
          onUpdateCategory={updateCategory}
          onDeleteCategory={deleteCategory}
        />

        <ConfirmDialog
          open={showDeleteConfirm}
          onOpenChange={setShowDeleteConfirm}
          title={t('asset.confirm.deleteTitle')}
          description={t('asset.confirm.deleteDescription', { count: pendingDeleteIds.length })}
          confirmText={t('common.confirm')}
          variant="destructive"
          onConfirm={handleConfirmDelete}
        />

        <AssetDragLayer getCardRefs={getCardRefs} />

        {isSelecting && selectionStart && selectionEnd && (
          <AssetSelectionBox startPoint={selectionStart} endPoint={selectionEnd} />
        )}
      </div>
    </AssetDragProvider>
  )
}
