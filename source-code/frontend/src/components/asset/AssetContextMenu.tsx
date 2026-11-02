/**
 * 资产右键菜单
 */

import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Heart, Download, Trash2, ChevronRight, FolderOpen, BookOpen } from 'lucide-react'
import { Button } from '@/components/ui'
import { ConfirmDialog } from '@/components/common/ConfirmDialog'
import { useAssetStore } from '@/stores/useAssetStore'
import type { Asset } from '@/mocks/asset'
import { cn } from '@/lib/utils'
import { toast } from 'sonner'

interface Position {
  x: number
  y: number
}

interface AssetContextMenuProps {
  asset: Asset | null
  position: Position | null
  onClose: () => void
}

export function AssetContextMenu({ asset, position, onClose }: AssetContextMenuProps) {
  const { t } = useTranslation()
  const { toggleFavorite, deleteAssets, openLocation, exportWorkflow, exportWorkflowToPath, exportToPromptLibrary } = useAssetStore()
  const menuRef = useRef<HTMLDivElement>(null)
  const [adjustedPosition, setAdjustedPosition] = useState<Position | null>(null)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [showNoPromptConfirm, setShowNoPromptConfirm] = useState(false)

  useEffect(() => {
    if (position) {
      const menuWidth = 180
      const menuHeight = 180

      let x = position.x
      let y = position.y

      if (x + menuWidth > window.innerWidth) {
        x = window.innerWidth - menuWidth - 10
      }
      if (y + menuHeight > window.innerHeight) {
        y = window.innerHeight - menuHeight - 10
      }

      setAdjustedPosition({ x, y })
    }
  }, [position])

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (showDeleteConfirm || showNoPromptConfirm) {
        return
      }
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose()
      }
    }

    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (showDeleteConfirm || showNoPromptConfirm) {
          return
        }
        onClose()
      }
    }

    if (position) {
      document.addEventListener('mousedown', handleClickOutside)
      document.addEventListener('keydown', handleEscape)
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
      document.removeEventListener('keydown', handleEscape)
    }
  }, [position, onClose, showDeleteConfirm, showNoPromptConfirm])

  if (!asset || !position || !adjustedPosition) {
    return null
  }

  const handleFavorite = async () => {
    await toggleFavorite(asset.id)
    onClose()
  }

  const handleDelete = () => {
    setShowDeleteConfirm(true)
  }

  const handleConfirmDelete = async () => {
    await deleteAssets([asset.id])
    setShowDeleteConfirm(false)
    onClose()
  }

  const handleOpenLocation = async () => {
    await openLocation(asset.id)
    onClose()
  }

  const handleExportToWorkflow = async () => {
    const result = await exportWorkflow(asset.id)
    if (result.success) {
      toast.success(t('asset.toast.exportSuccess'))
    } else {
      toast.error(result.error_message || t('asset.toast.exportFailed'))
    }
    onClose()
  }

  const handleExportToLocal = async () => {
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
      console.error('[AssetContextMenu] 导出到本地失败:', error)
      toast.error(t('asset.toast.exportFailed'))
    }
    onClose()
  }

  const handleImportToPromptLibrary = async (force = false) => {
    const result = await exportToPromptLibrary(asset.id, force)
    if (result.success) {
      toast.success(t('asset.toast.importToPromptLibrarySuccess'))
      onClose()
    } else if (result.error_message === 'no_prompt_detected') {
      setShowNoPromptConfirm(true)
    } else {
      toast.error(result.error_message || t('asset.toast.importToPromptLibraryFailed'))
      onClose()
    }
  }

  const handleConfirmNoPrompt = async () => {
    setShowNoPromptConfirm(false)
    await handleImportToPromptLibrary(true)
  }

  return (
    <div
      ref={menuRef}
      className="fixed z-50 min-w-[180px] rounded-lg border border-border-subtle bg-surface/95 p-1 shadow-soft-lg backdrop-blur-lg"
      style={{
        left: `${adjustedPosition.x}px`,
        top: `${adjustedPosition.y}px`
      }}
    >
      <Button
        variant="ghost"
        onClick={handleFavorite}
        className="h-auto w-full justify-start gap-3 px-3 py-2 text-sm"
      >
        <Heart className={cn('size-4', asset.isFavorite && 'fill-danger text-danger')} />
        {asset.isFavorite ? t('asset.contextMenu.unfavorite') : t('asset.contextMenu.favorite')}
      </Button>

      <Button
        variant="ghost"
        onClick={handleOpenLocation}
        className="h-auto w-full justify-start gap-3 px-3 py-2 text-sm"
      >
        <FolderOpen className="size-4" />
        {t('asset.contextMenu.openLocation')}
      </Button>

      {/* 转入提示词库：不依赖工作流，只要资产带提示词或参数都可导入 */}
      <Button
        variant="ghost"
        onClick={() => handleImportToPromptLibrary(false)}
        className="h-auto w-full justify-start gap-3 px-3 py-2 text-sm"
      >
        <BookOpen className="size-4" />
        {t('asset.contextMenu.importToPromptLibrary')}
      </Button>

      {asset.hasWorkflow && (
        <div className="group relative">
          <Button
            variant="ghost"
            className="h-auto w-full justify-between gap-3 px-3 py-2 text-sm"
          >
            <div className="flex items-center gap-3">
              <Download className="size-4" />
              {t('asset.contextMenu.export')}
            </div>
            <ChevronRight className="size-4" />
          </Button>

          <div className="absolute left-full top-0 hidden min-w-[180px] rounded-lg border border-border-subtle bg-surface/95 p-1 shadow-soft-lg backdrop-blur-lg group-hover:block">
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

      <div className="my-1 h-px bg-border-subtle" />

      <Button
        variant="ghost"
        onClick={handleDelete}
        className="h-auto w-full justify-start gap-3 px-3 py-2 text-sm text-danger hover:bg-danger/10"
      >
        <Trash2 className="size-4" />
        {t('asset.contextMenu.delete')}
      </Button>

      <ConfirmDialog
        open={showDeleteConfirm}
        onOpenChange={setShowDeleteConfirm}
        title={t('asset.confirm.deleteTitle')}
        description={t('asset.confirm.deleteSingleDescription')}
        confirmText={t('common.delete')}
        variant="destructive"
        onConfirm={handleConfirmDelete}
      />

      <ConfirmDialog
        open={showNoPromptConfirm}
        onOpenChange={setShowNoPromptConfirm}
        title={t('asset.noPromptDetected')}
        description={t('asset.noPromptDetectedDescription')}
        confirmText={t('asset.continueImport')}
        variant="default"
        onConfirm={handleConfirmNoPrompt}
      />
    </div>
  )
}
