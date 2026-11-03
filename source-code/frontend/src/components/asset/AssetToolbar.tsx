/**
 * 资产库顶部工具栏
 */

import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Search, Upload, Download, CheckSquare, Settings, RefreshCw, Loader2, Eye, Star, ChevronDown, FolderTree, ArrowUpDown, Columns3, LayoutGrid } from 'lucide-react'
import { Button, Input, Label, Select, SelectContent, SelectItem, SelectTrigger, SelectValue, Slider, Switch } from '@/components/ui'
import { Popover, PopoverTrigger, PopoverContent } from '@/components/ui/popover'
import { useAssetStore, type SortBy } from '@/stores/useAssetStore'
import { cn } from '@/lib/utils'

interface AssetToolbarProps {
  onOpenSettings?: () => void
  /** 影院模式下隐藏排布相关控件，退出后再显示 */
  hideLayoutControls?: boolean
}

const RATING_FILTERS = [
  { value: 'all', label: 'allRatings' },
  { value: '0', label: 'unrated' },
  { value: '1', label: '1star' },
  { value: '2', label: '2stars' },
  { value: '3', label: '3stars' },
  { value: '4', label: '4stars' },
  { value: '5', label: '5stars' }
] as const

const SORT_OPTIONS = [
  { value: 'createdAt', label: 'createdAt' },
  { value: 'name', label: 'name' },
  { value: 'size', label: 'size' }
] as const

export function AssetToolbar({ onOpenSettings, hideLayoutControls }: AssetToolbarProps) {
  const { t } = useTranslation()
  const {
    searchQuery,
    setSearchQuery,
    filterTags,
    activeFilterTag,
    setActiveFilterTag,
    isBatchMode,
    selectedAssetIds,
    getAssetCount,
    toggleBatchMode,
    scanLibrary,
    incrementalScanLibrary,
    isScanning,
    importAssets,
    exportZip,
    thumbnailSize,
    setThumbnailSize,
    ratingFilter,
    setRatingFilter,
    sortBy,
    setSortBy,
    showFoldersInList,
    setShowFoldersInList,
    viewMode,
    setViewMode
  } = useAssetStore()

  const [isImporting, setIsImporting] = useState(false)
  const [isExporting, setIsExporting] = useState(false)
  const [isRefreshMenuOpen, setIsRefreshMenuOpen] = useState(false)
  const totalCount = getAssetCount()

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
          <Select
            value={sortBy}
            onValueChange={(value) => setSortBy(value as SortBy)}
          >
            <SelectTrigger className="h-8 w-auto gap-1 px-3">
              <ArrowUpDown className="size-4" />
              <SelectValue placeholder={t('asset.sort')} />
            </SelectTrigger>
            <SelectContent>
              {SORT_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {t(`asset.sortOptions.${option.label}`)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select
            value={ratingFilter}
            onValueChange={(value) => setRatingFilter(value)}
          >
            <SelectTrigger className="h-8 w-auto gap-1 px-3">
              <Star className="size-4" />
              <SelectValue placeholder={t('asset.ratingFilter')} />
            </SelectTrigger>
            <SelectContent>
              {RATING_FILTERS.map((rating) => (
                <SelectItem key={rating.value} value={rating.value}>
                  {t(`asset.rating.${rating.label}`)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
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

      <div className="mt-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">{t('asset.quickFilter')}:</span>
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

        <div className="text-xs text-muted-foreground">
          {isBatchMode ? (
            <span>
              {t('asset.selectedCount', { count: selectedAssetIds.length })}
            </span>
          ) : (
            <span>
              {t('asset.totalCount', { count: totalCount })}
            </span>
          )}
        </div>
      </div>
    </header>
  )
}
