/**
 * 资产详情弹窗
 */

import { useState, useCallback, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import {
  ChevronLeft,
  ChevronRight,
  Maximize2,
  Minimize2,
  X,
  Copy,
  Download,
  ChevronDown,
  BookOpen
} from 'lucide-react'
import { Button } from '@/components/ui'
import type { Asset } from '@/mocks/asset'
import { cn } from '@/lib/utils'
import { toast } from 'sonner'
import { useAssetStore } from '@/stores/useAssetStore'

interface AssetDetailDialogProps {
  asset: Asset | null
  open: boolean
  onOpenChange: (open: boolean) => void
  assets?: Asset[]
  onNavigate?: (asset: Asset) => void
}

export function AssetDetailDialog({
  asset,
  open,
  onOpenChange,
  assets = [],
  onNavigate
}: AssetDetailDialogProps) {
  const { t } = useTranslation()
  const { exportWorkflow, exportWorkflowToPath, exportToPromptLibrary } = useAssetStore()
  const [isFocusMode, setIsFocusMode] = useState(false)
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    prompt: true,
    negative: false,
    params: true
  })

  const currentIndex = asset ? assets.findIndex((a) => a.id === asset.id) : -1
  const hasPrev = currentIndex > 0
  const hasNext = currentIndex < assets.length - 1

  const handlePrev = useCallback(() => {
    if (hasPrev && onNavigate) {
      onNavigate(assets[currentIndex - 1])
    }
  }, [hasPrev, currentIndex, assets, onNavigate])

  const handleNext = useCallback(() => {
    if (hasNext && onNavigate) {
      onNavigate(assets[currentIndex + 1])
    }
  }, [hasNext, currentIndex, assets, onNavigate])

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!open) return
      if (e.key === 'ArrowLeft') handlePrev()
      if (e.key === 'ArrowRight') handleNext()
      if (e.key === 'Escape') {
        if (isFocusMode) {
          setIsFocusMode(false)
        } else {
          onOpenChange(false)
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [open, handlePrev, handleNext, onOpenChange, isFocusMode])

  useEffect(() => {
    if (isFocusMode && open) {
      document.documentElement.requestFullscreen?.()
    } else if (document.fullscreenElement) {
      document.exitFullscreen?.()
    }
  }, [isFocusMode, open])

  useEffect(() => {
    return () => {
      if (document.fullscreenElement) {
        document.exitFullscreen?.()
      }
    }
  }, [])

  useEffect(() => {
    const handleFullscreenChange = () => {
      if (!document.fullscreenElement && isFocusMode) {
        setIsFocusMode(false)
      }
    }

    document.addEventListener('fullscreenchange', handleFullscreenChange)
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange)
  }, [isFocusMode])

  const toggleSection = (section: string) => {
    setExpandedSections((prev) => ({ ...prev, [section]: !prev[section] }))
  }

  const handleCopy = async (text: string) => {
    await navigator.clipboard.writeText(text)
    toast.success(t('asset.toast.copySuccess'))
  }

  const safeString = (value: unknown): string => {
    if (value === null || value === undefined) return ''
    if (typeof value === 'string') return value
    if (typeof value === 'object') return JSON.stringify(value, null, 2)
    return String(value)
  }

  const handleExportToWorkflow = async () => {
    if (!asset?.id) return
    const result = await exportWorkflow(asset.id)
    if (result.success) {
      toast.success(t('asset.toast.exportSuccess'))
    } else {
      toast.error(t('asset.toast.exportFailed'))
    }
  }

  const handleExportToLocal = async () => {
    if (!asset?.id) return
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
    } catch (error) {
      console.error('[AssetDetailDialog] 导出到本地失败:', error)
      toast.error(t('asset.toast.exportFailed'))
    }
  }

  const handleImportToPromptLibrary = async () => {
    if (!asset?.id) return
    const result = await exportToPromptLibrary(asset.id)
    if (result.success) {
      toast.success(t('asset.toast.importToPromptLibrarySuccess'))
    } else if (result.error_message === 'no_prompt_detected') {
      toast.warning(t('asset.noPromptDetected'))
    } else {
      toast.error(result.error_message || t('asset.toast.importToPromptLibraryFailed'))
    }
  }

  if (!asset) return null

  return (
    <div
      className={cn(
        'fixed inset-0 z-50 flex items-center justify-center transition-opacity duration-300',
        open ? 'opacity-100' : 'pointer-events-none opacity-0'
      )}
    >
      <div
        className="absolute inset-0 bg-background/85 backdrop-blur-sm"
        onClick={() => onOpenChange(false)}
      />

      <div
        className={cn(
          'relative flex overflow-hidden rounded-xl border border-border-subtle bg-surface shadow-soft-lg transition-all duration-300',
          isFocusMode 
            ? 'fixed inset-0 z-50 h-full w-full rounded-none border-0' 
            : 'h-[90vh] w-[90vw] max-w-[1400px]',
          open ? 'scale-100' : 'scale-[0.98]'
        )}
      >
        <div className={cn(
          'relative flex flex-1 items-center justify-center bg-background p-4',
          isFocusMode && 'p-0'
        )}>
          {asset.type === 'video' ? (
            <video
              src={asset.url}
              controls
              autoPlay
              className="max-h-full max-w-full rounded-lg"
              style={{ maxHeight: 'calc(90vh - 2rem)' }}
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
              onClick={handlePrev}
              className="absolute left-4 top-1/2 size-12 -translate-y-1/2 rounded-full border border-border-subtle bg-surface/80 backdrop-blur-sm"
            >
              <ChevronLeft className="size-6" />
            </Button>
          )}

          {hasNext && (
            <Button
              variant="outline"
              size="icon"
              onClick={handleNext}
              className="absolute right-4 top-1/2 size-12 -translate-y-1/2 rounded-full border border-border-subtle bg-surface/80 backdrop-blur-sm"
            >
              <ChevronRight className="size-6" />
            </Button>
          )}

          {isFocusMode && (
            <div className="absolute right-4 top-4 z-50 flex gap-2 opacity-50 hover:opacity-100 transition-opacity">
              <Button
                variant="outline"
                size="icon"
                onClick={() => setIsFocusMode(false)}
                title={t('asset.detail.exitFocusMode')}
                className="size-10 rounded-full border border-border-subtle bg-surface/80 backdrop-blur-sm"
              >
                <Minimize2 className="size-5" />
              </Button>
              <Button
                variant="outline"
                size="icon"
                onClick={() => onOpenChange(false)}
                className="size-10 rounded-full border border-border-subtle bg-surface/80 backdrop-blur-sm"
              >
                <X className="size-5" />
              </Button>
            </div>
          )}
        </div>

        <div
          className={cn(
            'flex w-[380px] shrink-0 flex-col border-l border-border-subtle bg-surface transition-all duration-300',
            isFocusMode && 'w-0 translate-x-full border-l-0 overflow-hidden'
          )}
        >
          <div className="flex items-center justify-end gap-2 border-b border-border-subtle p-4">
            <Button
              variant="outline"
              size="icon"
              onClick={() => setIsFocusMode(!isFocusMode)}
              title={isFocusMode ? t('asset.detail.exitFocusMode') : t('asset.detail.focusMode')}
              className="size-8"
            >
              {isFocusMode ? <Minimize2 className="size-4" /> : <Maximize2 className="size-4" />}
            </Button>

            {asset.hasWorkflow && (
              <div className="group relative">
                <Button size="sm">
                  <Download className="mr-1 size-4" />
                  {t('asset.detail.exportWorkflow')}
                  <ChevronDown className="ml-1 size-4" />
                </Button>
                <div className="absolute right-0 top-full z-50 hidden min-w-[180px] rounded-lg border border-border-subtle bg-surface/95 p-1 shadow-soft-lg backdrop-blur-lg group-hover:block">
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
                </div>
              </div>
            )}

            <Button
              variant="outline"
              size="icon"
              onClick={() => onOpenChange(false)}
              className="size-8"
            >
              <X className="size-4" />
            </Button>
          </div>

          <div className="flex-1 overflow-y-auto p-4">
            <AccordionSection
              title={t('asset.detail.positivePrompt')}
              isExpanded={expandedSections.prompt}
              onToggle={() => toggleSection('prompt')}
            >
              <div className="relative">
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => handleCopy(safeString(asset.prompt))}
                  className="absolute right-2 top-2 z-10 size-8"
                >
                  <Copy className="size-4" />
                </Button>
                <div className="max-h-[300px] overflow-y-auto rounded bg-background">
                  <p className="whitespace-pre-wrap p-3 font-mono text-sm">
                    {safeString(asset.prompt)}
                  </p>
                </div>
              </div>
            </AccordionSection>

            {asset.negativePrompt && (
              <AccordionSection
                title={t('asset.detail.negativePrompt')}
                isExpanded={expandedSections.negative}
                onToggle={() => toggleSection('negative')}
              >
                <div className="relative">
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => handleCopy(safeString(asset.negativePrompt))}
                    className="absolute right-2 top-2 z-10 size-8"
                  >
                    <Copy className="size-4" />
                  </Button>
                  <div className="max-h-[300px] overflow-y-auto rounded bg-background">
                    <p className="whitespace-pre-wrap p-3 font-mono text-sm">
                      {safeString(asset.negativePrompt)}
                    </p>
                  </div>
                </div>
              </AccordionSection>
            )}

            <AccordionSection
              title={t('asset.detail.parameters')}
              isExpanded={expandedSections.params}
              onToggle={() => toggleSection('params')}
            >
              <div className="flex flex-wrap gap-2">
                {asset.model && (
                  <ParamBadge label={t('asset.param.model')} value={asset.model} />
                )}
                {asset.sampler && (
                  <ParamBadge label={t('asset.param.sampler')} value={asset.sampler} />
                )}
                {asset.steps && (
                  <ParamBadge label={t('asset.param.steps')} value={String(asset.steps)} />
                )}
                {asset.cfg && (
                  <ParamBadge label={t('asset.param.cfg')} value={String(asset.cfg)} />
                )}
                {asset.seed && (
                  <ParamBadge label={t('asset.param.seed')} value={String(asset.seed)} />
                )}
                <ParamBadge
                  label={t('asset.param.size')}
                  value={`${asset.width}x${asset.height}`}
                />
              </div>
            </AccordionSection>
          </div>
        </div>
      </div>
    </div>
  )
}

function AccordionSection({
  title,
  isExpanded,
  onToggle,
  children
}: {
  title: string
  isExpanded: boolean
  onToggle: () => void
  children: React.ReactNode
}) {
  return (
    <div className="mb-3 overflow-hidden rounded-lg border border-border-subtle bg-surface-active">
      <Button
        variant="ghost"
        onClick={onToggle}
        className="h-auto w-full justify-between p-3 text-sm font-medium"
      >
        <span>{title}</span>
        <ChevronDown
          className={cn('size-4 transition-transform', isExpanded && 'rotate-180')}
        />
      </Button>
      <div
        className={cn(
          'transition-all duration-200',
          isExpanded ? 'max-h-[500px] overflow-y-auto' : 'max-h-0 overflow-hidden'
        )}
      >
        <div className="p-3 pt-0">{children}</div>
      </div>
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
