/**
 * 资产库文件夹卡片
 */

import { useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { Folder, Images } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAssetDragContext } from './AssetDragContext'
import type { AssetCategory } from '@/mocks/asset'

interface AssetFolderCardProps {
  category: AssetCategory
  assetCount: number
  onOpen: (categoryId: string) => void
}

export function AssetFolderCard({ category, assetCount, onOpen }: AssetFolderCardProps) {
  const { t } = useTranslation()

  const dragContext = useAssetDragContext()
  const isDragging = dragContext?.isDragging ?? false
  const isDropTarget = dragContext?.dropTargetId === category.id

  const handleClick = useCallback(() => {
    if (isDragging) return
    onOpen(category.id)
  }, [category.id, isDragging, onOpen])

  return (
    <div
      data-folder-card
      data-category-id={category.id}
      role="button"
      tabIndex={0}
      onClick={handleClick}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          handleClick()
        }
      }}
      className={cn(
        'group flex h-28 cursor-pointer flex-col justify-between rounded-lg border border-border-subtle bg-surface p-3 transition-all',
        'hover:-translate-y-0.5 hover:border-border-strong hover:bg-surface-hover hover:shadow-soft',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        isDropTarget && 'border-primary border-dashed bg-primary/10 ring-2 ring-primary/30'
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex size-10 items-center justify-center rounded-md bg-primary/10 text-primary">
          <Folder className="size-5" />
        </div>
        <div className="flex items-center gap-1 rounded bg-surface-active px-1.5 py-0.5 text-[11px] text-muted-foreground">
          <Images className="size-3" />
          <span>{assetCount}</span>
        </div>
      </div>

      <div className="min-w-0">
        <p className="truncate text-sm font-medium text-foreground">
          {category.name}
        </p>
        <p className="mt-1 truncate text-xs text-muted-foreground">
          {t('asset.folder.open')}
        </p>
      </div>
    </div>
  )
}
