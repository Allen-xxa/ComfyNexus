/**
 * 资产信息面板
 */

import { useState, useCallback, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { Pencil, Check, X, XCircle, Calendar, HardDrive, Image, FileVideo, Star, Pin, Trash2, FolderTree, FileText, FolderOpen } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Textarea } from '@/components/ui/Textarea'
import { ConfirmDialog } from '@/components/common/ConfirmDialog'
import { cn } from '@/lib/utils'
import type { Asset } from '@/mocks/asset'

export interface AssetInfoPanelProps {
  asset: Asset | null
  onClose: () => void
  onUpdate: (assetId: string, data: { filename?: string; description?: string; tags?: string[]; rating?: number }) => Promise<{ success: boolean; error_message?: string }>
  pinned?: boolean
  onTogglePin?: () => void
  onDelete?: (assetId: string) => Promise<boolean>
  categoryPath?: string
  onOpenLocation?: (assetId: string) => Promise<boolean>
  /** 嵌入模式：由外层负责滚动，不渲染自己的标题栏和预览图（影院模式右侧详情用） */
  embedded?: boolean
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`
}

function formatDate(dateStr: string): string {
  try {
    const date = new Date(dateStr)
    return date.toLocaleDateString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    })
  } catch {
    return dateStr
  }
}

function getFileExtension(filename: string): string {
  const ext = filename.split('.').pop()?.toUpperCase() || ''
  return ext
}

function getFilenameWithoutExt(filename: string): string {
  const lastDot = filename.lastIndexOf('.')
  return lastDot > 0 ? filename.substring(0, lastDot) : filename
}

export function AssetInfoPanel({ asset, onClose, onUpdate, pinned, onTogglePin, onDelete, categoryPath, onOpenLocation, embedded }: AssetInfoPanelProps) {
  const { t } = useTranslation()
  const [isEditMode, setIsEditMode] = useState(false)
  const [editFilename, setEditFilename] = useState('')
  const [editDescription, setEditDescription] = useState('')
  const [editTags, setEditTags] = useState<string[]>([])
  const [editRating, setEditRating] = useState(0)
  const [newTagInput, setNewTagInput] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)

  const handleEnterEditMode = useCallback(() => {
    if (asset) {
      setEditFilename(getFilenameWithoutExt(asset.filename))
      setEditDescription(asset.description || '')
      setEditTags(asset.tags || [])
      setEditRating(asset.rating || 0)
      setIsEditMode(true)
    }
  }, [asset])

  const handleCancelEdit = useCallback(() => {
    setIsEditMode(false)
    setNewTagInput('')
  }, [])

  const handleSave = useCallback(async () => {
    if (!asset) return
    
    setIsSaving(true)
    try {
      const result = await onUpdate(asset.id, {
        filename: editFilename,
        description: editDescription,
        tags: editTags,
        rating: editRating
      })
      
      if (result.success) {
        setIsEditMode(false)
        setNewTagInput('')
      }
    } finally {
      setIsSaving(false)
    }
  }, [asset, editFilename, editDescription, editTags, editRating, onUpdate])

  const handleRatingClick = useCallback(async (rating: number) => {
    if (!asset) return
    const newRating = rating === (asset.rating || 0) ? 0 : rating
    await onUpdate(asset.id, { rating: newRating })
  }, [asset, onUpdate])

  const handleAddTag = useCallback((e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && newTagInput.trim()) {
      e.preventDefault()
      const newTag = newTagInput.trim()
      if (!editTags.includes(newTag)) {
        setEditTags([...editTags, newTag])
      }
      setNewTagInput('')
    }
  }, [editTags, newTagInput])

  const handleRemoveTag = useCallback((tagToRemove: string) => {
    setEditTags(editTags.filter(tag => tag !== tagToRemove))
  }, [editTags])

  const handleDeleteClick = useCallback(() => {
    setShowDeleteConfirm(true)
  }, [])

  const handleConfirmDelete = useCallback(async () => {
    if (!asset || !onDelete) return
    const success = await onDelete(asset.id)
    if (success) {
      setShowDeleteConfirm(false)
      onClose()
    }
  }, [asset, onDelete, onClose])

  const fileExtension = useMemo(() => asset ? getFileExtension(asset.filename) : '', [asset])

  if (!asset) {
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        <p>{t('asset.info.selectAsset')}</p>
      </div>
    )
  }

  return (
    <div className={cn(
      "flex flex-col border-l border-border-subtle",
      embedded
        ? "border-t bg-surface"
        : cn("h-full", pinned ? "bg-surface" : "bg-surface/95 backdrop-blur-sm")
    )}>
      {!embedded && (
        <div className="flex items-center justify-between border-b border-border-subtle px-4 py-3">
          <span className="text-sm font-medium text-foreground">{t('asset.info.title')}</span>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              onClick={onTogglePin}
              className="size-7"
              title={pinned ? t('asset.info.unpin') : t('asset.info.pin')}
            >
              <Pin className={cn("size-4", pinned && "fill-current text-primary")} />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={onClose}
              className="size-7"
            >
              <XCircle className="size-4" />
            </Button>
          </div>
        </div>
      )}

      <div className={embedded ? "p-4" : "flex-1 overflow-y-auto p-4"}>
        {!embedded && (
          <div className="mb-4 aspect-video overflow-hidden rounded-lg bg-surface-active">
            <img
              src={asset.thumbnail}
              alt={asset.filename}
              className="size-full object-contain"
            />
          </div>
        )}

        {!isEditMode ? (
          <>
            <div className="mb-4">
              <div className="mb-1 flex items-center justify-between">
                <span className="text-xs font-medium text-muted-foreground">{t('asset.info.filename')}</span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleEnterEditMode}
                  className="h-6 gap-1 border border-border-subtle bg-surface-hover px-2 text-[11px] text-foreground hover:bg-surface-active"
                >
                  <Pencil className="size-3" />
                  {t('common.edit')}
                </Button>
              </div>
              <p className="break-all text-sm text-foreground">{asset.filename}</p>
            </div>

            <div className="mb-4">
              <span className="mb-1 block text-xs font-medium text-muted-foreground">{t('asset.info.tags')}</span>
              <div className="flex flex-wrap gap-1.5">
                {(asset.tags || []).length > 0 ? (
                  asset.tags!.map((tag, index) => (
                    <span
                      key={index}
                      className="rounded border border-border-subtle bg-surface-active px-2 py-0.5 text-[11px] text-foreground"
                    >
                      {tag}
                    </span>
                  ))
                ) : (
                  <span className="text-xs text-muted-foreground">{t('asset.info.noTags')}</span>
                )}
              </div>
            </div>

            <div className="mb-4">
              <span className="mb-1 block text-xs font-medium text-muted-foreground">{t('asset.info.rating')}</span>
              <div className="flex gap-0.5">
                {[1, 2, 3, 4, 5].map((star) => (
                  <Button
                    key={star}
                    variant="ghost"
                    size="icon"
                    onClick={() => handleRatingClick(star)}
                    className={cn(
                      "size-6 p-0.5 transition-transform hover:scale-110",
                      star <= (asset.rating || 0) ? "text-warning" : "text-muted-foreground hover:text-warning/70"
                    )}
                  >
                    <Star className={cn("size-5", star <= (asset.rating || 0) && "fill-current")} />
                  </Button>
                ))}
              </div>
            </div>

            <div className="mb-4">
              <span className="mb-1 block text-xs font-medium text-muted-foreground">{t('asset.info.description')}</span>
              <p className="min-h-[36px] text-sm leading-relaxed text-foreground">
                {asset.description || t('asset.info.noDescription')}
              </p>
            </div>
          </>
        ) : (
          <>
            <div className="mb-4">
              <div className="mb-1 flex items-center justify-between">
                <span className="text-xs font-medium text-muted-foreground">{t('asset.info.filename')}</span>
                <div className="flex gap-1">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleCancelEdit}
                    className="h-6 px-2 text-[11px] text-muted-foreground hover:text-foreground"
                  >
                    <X className="size-3" />
                    {t('common.cancel')}
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleSave}
                    disabled={isSaving}
                    className="h-6 gap-1 border border-success/30 bg-success/10 px-2 text-[11px] text-success hover:bg-success/20"
                  >
                    <Check className="size-3" />
                    {t('common.save')}
                  </Button>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Input
                  value={editFilename}
                  onChange={(e) => setEditFilename(e.target.value)}
                  className="h-8 flex-1 bg-background text-sm"
                  placeholder={t('asset.info.filenamePlaceholder')}
                />
                <span className="text-sm text-muted-foreground">.{fileExtension.toLowerCase()}</span>
              </div>
            </div>

            <div className="mb-4">
              <span className="mb-1 block text-xs font-medium text-muted-foreground">{t('asset.info.tags')}</span>
              <div className="flex flex-wrap items-center gap-1.5 rounded border border-dashed border-border-subtle bg-background p-1">
                {editTags.map((tag, index) => (
                  <span
                    key={index}
                    className="group flex cursor-pointer items-center gap-1 rounded border border-border-subtle bg-surface-active px-2 py-0.5 text-[11px] text-foreground transition-colors hover:bg-primary/20"
                    onClick={() => handleRemoveTag(tag)}
                  >
                    {tag}
                    <X className="size-2.5 opacity-60 transition-opacity hover:opacity-100" />
                  </span>
                ))}
                <Input
                  value={newTagInput}
                  onChange={(e) => setNewTagInput(e.target.value)}
                  onKeyDown={handleAddTag}
                  placeholder={t('asset.info.tagPlaceholder')}
                  className="min-w-[100px] flex-1 border-0 bg-transparent px-1 py-0.5 text-[11px] placeholder:text-muted-foreground focus:ring-0"
                />
              </div>
            </div>

            <div className="mb-4">
              <span className="mb-1 block text-xs font-medium text-muted-foreground">{t('asset.info.description')}</span>
              <Textarea
                value={editDescription}
                onChange={(e) => setEditDescription(e.target.value)}
                className="h-[60px] resize-none bg-background text-sm placeholder:text-muted-foreground"
                placeholder={t('asset.info.descriptionPlaceholder')}
              />
            </div>
          </>
        )}

        <div className="border-t border-border-subtle pt-4">
          <span className="mb-3 block text-xs font-medium text-muted-foreground">{t('asset.info.basicInfo')}</span>
          
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-xs">
              {asset.type === 'image' ? (
                <Image className="size-4 text-muted-foreground" />
              ) : (
                <FileVideo className="size-4 text-muted-foreground" />
              )}
              <span className="text-muted-foreground">{t('asset.info.resolution')}:</span>
              <span className="text-foreground">{asset.width} × {asset.height}</span>
            </div>

            <div className="flex items-center gap-2 text-xs">
              <HardDrive className="size-4 text-muted-foreground" />
              <span className="text-muted-foreground">{t('asset.info.fileSize')}:</span>
              <span className="text-foreground">{formatFileSize(asset.size)}</span>
            </div>

            <div className="flex items-center gap-2 text-xs">
              <span className="size-4 text-center text-muted-foreground">{fileExtension}</span>
              <span className="text-muted-foreground">{t('asset.info.format')}:</span>
              <span className="text-foreground">{fileExtension}</span>
            </div>

            <div className="flex items-center gap-2 text-xs">
              <Calendar className="size-4 text-muted-foreground" />
              <span className="text-muted-foreground">{t('asset.info.createdAt')}:</span>
              <span className="text-foreground">{formatDate(asset.createdAt)}</span>
            </div>

            <div className="flex items-center gap-2 text-xs">
              <FolderTree className="size-4 shrink-0 text-muted-foreground" />
              <span className="shrink-0 text-muted-foreground">{t('asset.info.category')}:</span>
              <span className="min-w-0 truncate text-foreground">
                {categoryPath || t('asset.category.uncategorized')}
              </span>
            </div>

            <div className="flex items-center gap-2 text-xs">
              <FileText className="size-4 shrink-0 text-muted-foreground" />
              <span className="shrink-0 text-muted-foreground">{t('asset.info.path')}:</span>
              <span className="min-w-0 truncate text-foreground" title={asset.filePath}>{asset.filePath}</span>
            </div>
          </div>

          {onOpenLocation && (
            <Button
              variant="outline"
              size="sm"
              className="mt-3 w-full gap-2"
              onClick={() => void onOpenLocation(asset.id)}
            >
              <FolderOpen className="size-4" />
              {t('asset.info.openLocation')}
            </Button>
          )}
        </div>

        {onDelete && (
          <div className="mt-4 border-t border-border-subtle pt-4">
            <Button
              variant="destructive"
              className="w-full gap-2"
              onClick={handleDeleteClick}
            >
              <Trash2 className="size-4" />
              {t('asset.contextMenu.delete')}
            </Button>
          </div>
        )}
      </div>

      <ConfirmDialog
        open={showDeleteConfirm}
        onOpenChange={setShowDeleteConfirm}
        title={t('asset.confirm.deleteTitle')}
        description={t('asset.confirm.deleteSingleDescription')}
        confirmText={t('common.delete')}
        variant="destructive"
        onConfirm={handleConfirmDelete}
      />
    </div>
  )
}
