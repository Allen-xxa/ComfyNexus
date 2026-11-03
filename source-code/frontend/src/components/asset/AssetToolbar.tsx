/**
 * 资产库顶部工具栏
 *
 * 这一行只负责"怎么看"（视图、尺寸、刷新、导入、批量）；"看哪些"交给下方的
 * AssetFilterBar 二级筛选区，两者一起被筛选区的显隐开关控制。
 */

import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Search, Upload, Download, CheckSquare, Settings, RefreshCw, Loader2, Eye, ChevronDown, FolderTree, Columns3, LayoutGrid } from 'lucide-react'
import { Button, Input, Label, Slider, Switch } from '@/components/ui'
import { Popover, PopoverTrigger, PopoverContent } from '@/components/ui/popover'
import { useAssetStore } from '@/stores/useAssetStore'
import { AssetFilterBar } from './AssetFilterBar'
import { cn } from '@/lib/utils'

interface AssetToolbarProps {
  onOpenSettings?: () => void
  /** 影院模式下隐藏排布相关控件，退出后再显示 */
  hideLayoutControls?: boolean
}

export function AssetToolbar({ onOpenSettings, hideLayoutControls }: AssetToolbarProps) {
  const { t } = useTranslation()
  const {
    searchQuery,
    setSearchQuery,
    isBatchMode,
    selectedAssetIds,
    toggleBatchMode,
    scanLibrary,
    incrementalScanLibrary,
    isScanning,
    importAssets,
    exportZip,
    thumbnailSize,
    setThumbnailSize,
    showFoldersInList,
    setShowFoldersInList,
    viewMode,
    setViewMode
  } = useAssetStore()

  const [isImporting, setIsImporting] = useState(false)
  const [isExporting, setIsExporting] = useState(false)
  const [isRefreshMenuOpen, setIsRefreshMenuOpen] = useState(false)

  const handleIncrementalRefresh = async () => {
    setIsRefreshMenuOpen(false)
    await incrementalScanLibrary()
  }

  const handleFullRefresh = async () => {
    setIsRefreshMenuOpen(false)
    await scanLibrary()
  }

  const handleImport = async () => {
    if (isImporting) return

    try {
      setIsImporting(true)
      const paths = await window.pywebview.api.browse_files_for_shortcut({
        title: t('asset.importDialogTitle'),
        file_types: ['Image Files (*.png *.jpg *.jpeg *.webp)', 'Video Files (*.mp4 *.webm)', 'All Files (*.*)'],
        multiple: true
      })

      if (paths && paths.length > 0) {
        const result = await importAssets(paths)
        if (result.success) {
          console.log('[AssetToolbar] 导入成功:', result.importedCount)
        }
      }
    } catch (error) {
      console.error('[AssetToolbar] 导入失败:', error)
    } finally {
      setIsImporting(false)
    }
  }

  const handleExport = async () => {
    if (isExporting || selectedAssetIds.length === 0) return

    try {
      setIsExporting(true)
      const result = await exportZip(selectedAssetIds)
      if (result.success) {
        console.log('[AssetToolbar] 导出成功:', result.zipPath)
      }
    } catch (error) {
      console.error('[AssetToolbar] 导出失败:', error)
    } finally {
      setIsExporting(false)
    }
  }

  return (
    <header className="shrink-0 border-b border-border-subtle bg-surface p-4">
      <div className="flex items-center justify-between gap-4">
        <div className="flex max-w-md flex-1 items-center gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder={t('asset.searchPlaceholder')}
              className="rounded-full pl-9"
            />
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-end gap-2">
          {!hideLayoutControls && (
            <div className="flex items-center gap-0.5 rounded-md border border-border-subtle bg-surface-active p-0.5">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setViewMode('masonry')}
              title={t('asset.viewModes.masonry')}
              className={cn(
                'size-7',
                viewMode === 'masonry'
                  ? 'bg-primary/15 text-primary hover:bg-primary/20'
                  : 'text-muted-foreground hover:text-foreground'
              )}
            >
              <Columns3 className="size-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setViewMode('grid')}
              title={t('asset.viewModes.grid')}
              className={cn(
                'size-7',
                viewMode === 'grid'
                  ? 'bg-primary/15 text-primary hover:bg-primary/20'
                  : 'text-muted-foreground hover:text-foreground'
              )}
            >
              <LayoutGrid className="size-4" />
            </Button>
          </div>
          )}
          <div
            className="flex items-center gap-2 rounded-md border border-border-subtle bg-surface-active px-2.5 py-1.5"
            title={t('asset.showFoldersHint')}
          >
            <FolderTree className="size-4 text-muted-foreground" />
            <Label htmlFor="asset-show-folders" className="cursor-pointer text-xs text-muted-foreground">
              {t('asset.showFolders')}
            </Label>
            <Switch
              id="asset-show-folders"
              checked={showFoldersInList}
              onCheckedChange={setShowFoldersInList}
              aria-label={t('asset.showFolders')}
            />
          </div>
          {!hideLayoutControls && (
            <div className="flex items-center gap-2">
              <Eye className="size-4 text-muted-foreground" />
              <Slider
                value={[thumbnailSize]}
                onValueChange={(value) => setThumbnailSize(value[0])}
                min={100}
                max={500}
                step={10}
                className="w-24"
              />
              <span className="w-12 text-xs text-muted-foreground">
                {t('asset.thumbnailSizeValue', { size: thumbnailSize })}
              </span>
            </div>
          )}
          <Popover open={isRefreshMenuOpen} onOpenChange={setIsRefreshMenuOpen}>
            <PopoverTrigger asChild>
              <Button
                variant="outline"
                size="sm"
                disabled={isScanning}
              >
                {isScanning ? (
                  <Loader2 className="mr-1 size-4 animate-spin" />
                ) : (
                  <RefreshCw className="mr-1 size-4" />
                )}
                {t('asset.refresh')}
                <ChevronDown className="ml-1 size-4" />
              </Button>
            </PopoverTrigger>
            <PopoverContent align="start" className="min-w-[160px] p-1">
              <Button
                variant="ghost"
                size="sm"
                onClick={handleIncrementalRefresh}
                className="h-auto w-full justify-start gap-2 px-3 py-2 text-sm"
              >
                <RefreshCw className="size-4" />
                {t('asset.incrementalRefresh')}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleFullRefresh}
                className="h-auto w-full justify-start gap-2 px-3 py-2 text-sm text-warning"
              >
                <RefreshCw className="size-4" />
                {t('asset.fullRefresh')}
              </Button>
            </PopoverContent>
          </Popover>
          <Button
            variant="outline"
            size="sm"
            onClick={handleImport}
            disabled={isImporting}
          >
            {isImporting ? (
              <Loader2 className="mr-1 size-4 animate-spin" />
            ) : (
              <Upload className="mr-1 size-4" />
            )}
            {t('asset.import')}
          </Button>
          {isBatchMode && selectedAssetIds.length > 0 && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleExport}
              disabled={isExporting}
            >
              {isExporting ? (
                <Loader2 className="mr-1 size-4 animate-spin" />
              ) : (
                <Download className="mr-1 size-4" />
              )}
              {t('asset.export')}
            </Button>
          )}
          <Button
            variant={isBatchMode ? 'default' : 'outline'}
            size="sm"
            onClick={toggleBatchMode}
            className={cn(isBatchMode && 'bg-success/15 text-success hover:bg-success/25')}
          >
            <CheckSquare className="mr-1 size-4" />
            {isBatchMode ? t('asset.exitBatch') : t('asset.batchManage')}
          </Button>
          <Button variant="outline" size="icon" onClick={onOpenSettings}>
            <Settings className="size-4" />
          </Button>
        </div>
      </div>

      <AssetFilterBar />
    </header>
  )
}
