/**
 * 资产影院模式
 *
 * 取代原来的详情弹窗：中间是舞台（图片/视频原样展示），右侧是提示词与元信息，
 * 底部轨道展示筛选后的全部资产，点击即切换。左右方向键翻页，Esc 退出。
 */

import { useCallback, useEffect, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { Grid, useGridRef, type CellComponentProps } from 'react-window'
import {
  BookOpen,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Copy,
  Download,
  PanelLeftClose,
  PanelLeftOpen,
  PanelRightClose,
  PanelRightOpen,
  PanelTopClose,
  PanelTopOpen,
  Star,
  X
} from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { useAssetStore } from '@/stores/useAssetStore'
import { useChromeStore, type ChromeRegion } from '@/stores/useChromeStore'
import { useElementSize } from '@/hooks/useElementSize'
import { AssetInfoPanel } from './AssetInfoPanel'
import type { AssetInfoPanelProps } from './AssetInfoPanel'
import type { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'
import { toast } from 'sonner'
import type { Asset } from '@/mocks/asset'

interface AssetTheaterViewProps {
  asset: Asset
  assets: Asset[]
  categoryPath?: string
  onNavigate: (asset: Asset) => void
  onClose: () => void
  onUpdate: AssetInfoPanelProps['onUpdate']
  onDelete: AssetInfoPanelProps['onDelete']
  onOpenLocation: AssetInfoPanelProps['onOpenLocation']
}

interface StripCellData {
  assets: Asset[]
  activeId: string
  onNavigate: (asset: Asset) => void
}

const STRIP_WIDTH = 108
const STRIP_HEIGHT = 78
const STRIP_GAP = 8

const CHROME_REGIONS: ChromeRegion[] = ['nav', 'filter', 'detail']

/** 图标表示"这次点击要做什么"：可见时是收起，收起时是展开 */
const CHROME_ICONS: Record<ChromeRegion, { hide: LucideIcon; show: LucideIcon }> = {
  nav: { hide: PanelLeftClose, show: PanelLeftOpen },
  filter: { hide: PanelTopClose, show: PanelTopOpen },
  detail: { hide: PanelRightClose, show: PanelRightOpen }
}

function safeString(value: unknown): string {
  if (value === null || value === undefined) return ''
  if (typeof value === 'string') return value
  if (typeof value === 'object') return JSON.stringify(value, null, 2)
  return String(value)
}

export function AssetTheaterView({
  asset,
  assets,
  categoryPath,
  onNavigate,
  onClose,
  onUpdate,
  onDelete,
  onOpenLocation
}: AssetTheaterViewProps) {
  const { t } = useTranslation()
  const { exportWorkflow, exportWorkflowToPath, exportToPromptLibrary, toggleFavorite } = useAssetStore()
  const chromeHidden = useChromeStore((state) => state.hidden)
  const toggleChrome = useChromeStore((state) => state.toggle)

  const currentIndex = useMemo(
    () => assets.findIndex((item) => item.id === asset.id),
    [assets, asset.id]
  )
  const hasPrev = currentIndex > 0
  const hasNext = currentIndex >= 0 && currentIndex < assets.length - 1
  const [stripRef, stripSize] = useElementSize<HTMLDivElement>()
  const gridRef = useGridRef(null)

  const goPrev = useCallback(() => {
    if (hasPrev) onNavigate(assets[currentIndex - 1])
  }, [assets, currentIndex, hasPrev, onNavigate])

  const goNext = useCallback(() => {
    if (hasNext) onNavigate(assets[currentIndex + 1])
  }, [assets, currentIndex, hasNext, onNavigate])

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'ArrowLeft') goPrev()
      if (event.key === 'ArrowRight') goNext()
      if (event.key === 'Escape') onClose()
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [goPrev, goNext, onClose])

  // 轨道跟随当前资产滚动
  useEffect(() => {
    if (currentIndex < 0) return
    gridRef.current?.scrollToCell({
      columnIndex: currentIndex,
      rowIndex: 0,
      columnAlign: 'center'
    })
  }, [currentIndex, gridRef])

  const handleCopy = useCallback(async (text: string) => {
    try {
      await navigator.clipboard.writeText(text)
      toast.success(t('asset.toast.copySuccess'))
    } catch {
      toast.error(t('asset.toast.copyFailed'))
    }
  }, [t])

  const handleExportToWorkflow = useCallback(async () => {
    const result = await exportWorkflow(asset.id)
    if (result.success) {
      toast.success(t('asset.toast.exportSuccess'))
    } else {
      toast.error(t('asset.toast.exportFailed'))
    }
  }, [asset.id, exportWorkflow, t])

  const handleExportToLocal = useCallback(async () => {
    try {
      const saveResult = await window.pywebview.api.save_file_dialog(
        `${asset.filename.replace(/\.[^.]+$/, '')}_workflow.json`,
        'JSON files (*.json)'
      )

      if (saveResult.success && saveResult.path) {
        const result = await exportWorkflowToPath(asset.id, saveResult.path)
        if (result.success) {
          toast.success(t('asset.toast.exportSuccess'))
        } else {
          toast.error(t('asset.toast.exportFailed'))
        }
      }
    } catch {
      toast.error(t('asset.toast.exportFailed'))
    }
  }, [asset.filename, asset.id, exportWorkflowToPath, t])

  const handleImportToPromptLibrary = useCallback(async () => {
    const result = await exportToPromptLibrary(asset.id)
    if (result.success) {
      toast.success(t('asset.toast.importToPromptLibrarySuccess'))
    } else if (result.error_message === 'no_prompt_detected') {
      toast.warning(t('asset.noPromptDetected'))
    } else {
      toast.error(result.error_message || t('asset.toast.importToPromptLibraryFailed'))
    }
  }, [asset.id, exportToPromptLibrary, t])

  const stripCellData: StripCellData = useMemo(() => ({
    assets,
    activeId: asset.id,
    onNavigate
  }), [assets, asset.id, onNavigate])

  const StripCell = useCallback(({ columnIndex, style }: CellComponentProps<StripCellData>) => {
    const item = stripCellData.assets[columnIndex]
    if (!item) return null

    return (
      <div style={{ ...style, padding: STRIP_GAP / 2 }}>
        <Button
          variant="ghost"
          onClick={() => stripCellData.onNavigate(item)}
          title={item.filename}
          className={cn(
            'size-full overflow-hidden rounded-md border-2 bg-surface-active p-0',
            item.id === stripCellData.activeId
              ? 'border-primary'
              : 'border-transparent hover:border-border-strong'
          )}
        >
          <img
            src={item.thumbnail}
            alt={item.filename}
            loading="lazy"
            className="size-full object-cover"
          />
        </Button>
      </div>
    )
  }, [stripCellData])

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-theater">
      <div className="flex min-h-0 flex-1">
        <div className="relative flex min-w-0 flex-1 items-center justify-center overflow-hidden bg-theater p-6">
          {asset.type === 'video' ? (
            <video
              key={asset.id}
              src={asset.url}
              controls
              className="max-h-full max-w-full rounded-lg"
            >
              {t('asset.detail.videoNotSupported')}
            </video>
          ) : (
            <img
              src={asset.url}
              alt={asset.filename}
              className="max-h-full max-w-full rounded-lg object-contain"
            />
          )}

          {hasPrev && (
            <Button
              variant="outline"
              size="icon"
              onClick={goPrev}
              title={t('common.previous')}
              className="absolute left-4 top-1/2 size-10 -translate-y-1/2 rounded-full bg-surface/80 backdrop-blur-sm"
            >
              <ChevronLeft className="size-5" />
            </Button>
          )}

          {hasNext && (
            <Button
              variant="outline"
              size="icon"
              onClick={goNext}
              title={t('common.next')}
              className="absolute right-4 top-1/2 size-10 -translate-y-1/2 rounded-full bg-surface/80 backdrop-blur-sm"
            >
              <ChevronRight className="size-5" />
            </Button>
          )}

          <div className="absolute left-1/2 top-4 flex -translate-x-1/2 items-center gap-2 rounded-full border border-border-subtle bg-surface/80 px-3 py-1 text-xs text-muted-foreground backdrop-blur-sm">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => void toggleFavorite(asset.id)}
              title={t('asset.batchFavorite')}
              className={cn('size-6', asset.isFavorite && 'text-warning')}
            >
              <Star className={cn('size-3.5', asset.isFavorite && 'fill-current')} />
            </Button>
            <span className="font-mono">
              {t('asset.theater.position', {
                current: currentIndex + 1,
                total: assets.length
              })}
            </span>
          </div>

          <div className="absolute right-4 top-4 flex items-center gap-2">
            <div className="flex items-center gap-0.5 rounded-full border border-border-subtle bg-surface/80 p-1 backdrop-blur-sm">
              {CHROME_REGIONS.map((region) => {
                const isHidden = chromeHidden[region]
                const Icon = isHidden ? CHROME_ICONS[region].show : CHROME_ICONS[region].hide
                return (
                  <Button
                    key={region}
                    variant="ghost"
                    size="icon"
                    onClick={() => toggleChrome(region)}
                    title={`${t(isHidden ? 'asset.theater.chrome.show' : 'asset.theater.chrome.hide')} ${t(`asset.theater.chrome.${region}`)}`}
                    className={cn(
                      'size-7 rounded-full',
                      isHidden ? 'text-muted-foreground' : 'text-foreground'
                    )}
                  >
                    <Icon className="size-4" />
                  </Button>
                )
              })}
            </div>

            <Button
              variant="outline"
              size="sm"
              onClick={onClose}
              title={t('asset.theater.exitHint')}
              className="gap-1.5 rounded-full bg-surface/80 backdrop-blur-sm"
            >
              <X className="size-4" />
              {t('asset.theater.exit')}
            </Button>
          </div>
        </div>

        {!chromeHidden.detail && (
        <aside className="flex w-[380px] shrink-0 flex-col border-l border-border-subtle bg-surface">
          <div className="flex shrink-0 items-center justify-between gap-2 border-b border-border-subtle px-4 py-2">
            <span className="truncate text-sm font-medium text-foreground">{asset.filename}</span>
            {asset.hasWorkflow && (
              <Popover>
                <PopoverTrigger asChild>
                  <Button variant="outline" size="sm" className="shrink-0 gap-1">
                    <Download className="size-4" />
                    {t('asset.detail.exportWorkflow')}
                    <ChevronDown className="size-4" />
                  </Button>
                </PopoverTrigger>
                <PopoverContent align="end" className="min-w-[200px] p-1">
                  <Button
                    variant="ghost"
                    onClick={handleImportToPromptLibrary}
                    className="h-auto w-full justify-start gap-3 px-3 py-2 text-sm"
                  >
                    <BookOpen className="size-4" />
                    {t('asset.contextMenu.importToPromptLibrary')}
                  </Button>
                  <Button
                    variant="ghost"
                    onClick={handleExportToWorkflow}
                    className="h-auto w-full justify-start gap-3 px-3 py-2 text-sm"
                  >
                    {t('asset.contextMenu.exportToWorkflow')}
                  </Button>
                  <Button
                    variant="ghost"
                    onClick={handleExportToLocal}
                    className="h-auto w-full justify-start gap-3 px-3 py-2 text-sm"
                  >
                    {t('asset.contextMenu.exportToLocal')}
                  </Button>
                </PopoverContent>
              </Popover>
            )}
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto">
            <TheaterPromptSection
              title={t('asset.detail.positivePrompt')}
              value={asset.prompt}
              emptyText={t('asset.theater.noPrompt')}
              onCopy={handleCopy}
            />

            {asset.negativePrompt && (
              <TheaterPromptSection
                title={t('asset.detail.negativePrompt')}
                value={asset.negativePrompt}
                emptyText={t('asset.theater.noPrompt')}
                onCopy={handleCopy}
              />
            )}

            <div className="border-b border-border-subtle px-4 py-3">
              <span className="mb-2 block text-xs font-medium text-muted-foreground">
                {t('asset.detail.parameters')}
              </span>
              <div className="flex flex-wrap gap-2">
                {asset.model && <ParamBadge label={t('asset.param.model')} value={asset.model} />}
                {asset.sampler && <ParamBadge label={t('asset.param.sampler')} value={asset.sampler} />}
                {asset.steps && <ParamBadge label={t('asset.param.steps')} value={String(asset.steps)} />}
                {asset.cfg && <ParamBadge label={t('asset.param.cfg')} value={String(asset.cfg)} />}
                {asset.seed && <ParamBadge label={t('asset.param.seed')} value={String(asset.seed)} />}
                <ParamBadge
                  label={t('asset.param.size')}
                  value={`${asset.width}x${asset.height}`}
                />
              </div>
            </div>

            <AssetInfoPanel
              asset={asset}
              embedded
              onClose={onClose}
              onUpdate={onUpdate}
              onDelete={onDelete}
              categoryPath={categoryPath}
              onOpenLocation={onOpenLocation}
            />
          </div>
        </aside>
        )}
      </div>

      <div ref={stripRef} className="h-[86px] shrink-0 border-t border-border-subtle bg-surface">
        {stripSize.width > 0 && (
          <Grid
            gridRef={gridRef}
            columnCount={assets.length}
            columnWidth={STRIP_WIDTH + STRIP_GAP}
            rowCount={1}
            rowHeight={STRIP_HEIGHT + STRIP_GAP}
            defaultHeight={STRIP_HEIGHT + STRIP_GAP}
            defaultWidth={stripSize.width}
            overscanCount={4}
            cellComponent={StripCell}
            cellProps={stripCellData}
            className="scrollbar-thin"
            style={{ overflowY: 'hidden' }}
          />
        )}
      </div>
    </div>
  )
}

function TheaterPromptSection({
  title,
  value,
  emptyText,
  onCopy
}: {
  title: string
  value?: string
  emptyText: string
  onCopy: (text: string) => void
}) {
  return (
    <div className="border-b border-border-subtle px-4 py-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="text-xs font-medium text-muted-foreground">{title}</span>
        {value && (
          <Button
            variant="ghost"
            size="icon"
            onClick={() => onCopy(safeString(value))}
            className="size-6"
          >
            <Copy className="size-3.5" />
          </Button>
        )}
      </div>
      {value ? (
        <p className="max-h-40 overflow-y-auto whitespace-pre-wrap rounded bg-background p-2 font-mono text-xs leading-relaxed">
          {safeString(value)}
        </p>
      ) : (
        <p className="text-xs text-muted-foreground">{emptyText}</p>
      )}
    </div>
  )
}

function ParamBadge({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start gap-2 rounded bg-background px-2 py-1 text-xs">
      <span className="shrink-0 text-muted-foreground">{label}</span>
      <span className="break-all font-mono text-foreground">{value}</span>
    </div>
  )
}

export default AssetTheaterView
