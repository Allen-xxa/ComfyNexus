/**
 * 资产库分类树
 */

import { useState, useMemo, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import {
  LayoutGrid,
  Star,
  Folder,
  FolderOpen,
  Settings
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/Button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { ResizableSidebar } from '@/components/common/ResizableSidebar'
import { useAssetStore } from '@/stores/useAssetStore'
import { useAssetDragContext } from './AssetDragContext'
import type { AssetCategory } from '@/mocks/asset'

interface AssetCategoryTreeProps {
  className?: string
  onOpenCategoryManage?: () => void
}

function CategoryItem({
  category,
  level = 0,
  selectedCategoryId,
  expandedFolders,
  dropTargetId,
  onToggle,
  onSelect,
  getChildren,
  getAssetCount
}: {
  category: AssetCategory
  level?: number
  selectedCategoryId: string
  expandedFolders: Set<string>
  dropTargetId: string | null
  onToggle: (id: string) => void
  onSelect: (id: string) => void
  getChildren: (parentId: string) => AssetCategory[]
  getAssetCount: (categoryId: string) => number
}) {
  const { t } = useTranslation()
  const children = getChildren(category.id)
  const hasChildren = children.length > 0
  const isExpanded = expandedFolders.has(category.id)
  const isSelected = selectedCategoryId === category.id
  const isDropTarget = dropTargetId === category.id
  const assetCount = getAssetCount(category.id)

  const CategoryIcon = isSelected ? FolderOpen : Folder

  return (
    <>
      <div
        data-category-id={category.id}
        className={cn(
          'flex cursor-pointer items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-all',
          'border border-transparent',
          isSelected
            ? 'bg-primary/10 text-primary font-medium'
            : 'text-muted-foreground hover:bg-surface-hover hover:text-foreground',
          isDropTarget && 'border-primary border-dashed bg-primary/10'
        )}
        style={{ marginLeft: level * 2 }}
        onClick={() => {
          onSelect(category.id)
          if (hasChildren) {
            onToggle(category.id)
          }
        }}
      >
        <CategoryIcon className={cn(
          'size-4 flex-shrink-0',
          isSelected ? 'text-primary' : 'text-muted-foreground'
        )} />
        <span className="flex-1 truncate">
          {category.isSystem ? t(`asset.category.${category.id}`) : category.name}
        </span>
        {assetCount > 0 && (
          <span className="rounded bg-primary/20 px-1.5 py-0.5 font-mono text-[11px]">
            {assetCount}
          </span>
        )}
      </div>

      {hasChildren && isExpanded && (
        <div className="ml-3 border-l border-border-subtle pl-0.5">
          {children.map((child) => (
            <CategoryItem
              key={child.id}
              category={child}
              level={level + 1}
              selectedCategoryId={selectedCategoryId}
              expandedFolders={expandedFolders}
              dropTargetId={dropTargetId}
              onToggle={onToggle}
              onSelect={onSelect}
              getChildren={getChildren}
              getAssetCount={getAssetCount}
            />
          ))}
        </div>
      )}
    </>
  )
}

export function AssetCategoryTree({ className, onOpenCategoryManage }: AssetCategoryTreeProps) {
  const { t } = useTranslation()
  const {
    assets,
    categories,
    selectedCategoryId,
    setSelectedCategoryId
  } = useAssetStore()

  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set())

  const dropTargetId = useAssetDragContext()?.dropTargetId ?? null

  const totalAssets = assets.length
  const favoriteCount = assets.filter((a) => a.isFavorite).length
  const uncategorizedCount = assets.filter((a) => !a.categoryId).length

  const categoryTree = useMemo(() => {
    console.log('[AssetCategoryTree] 计算分类树，categories 数量:', categories.length)
    console.log('[AssetCategoryTree] categories:', categories.map(c => ({ id: c.id, name: c.name, parentId: c.parentId, isSystem: c.isSystem })))
    
    const rootCategories = categories.filter((c) => !c.parentId && c.id !== 'all' && c.id !== 'favorites')
    console.log('[AssetCategoryTree] rootCategories 数量:', rootCategories.length, rootCategories.map(c => c.name))
    
    const getChildren = (parentId: string): AssetCategory[] => {
      return categories.filter((c) => c.parentId === parentId)
    }
    return { rootCategories, getChildren }
  }, [categories])

  const toggleFolder = useCallback((folderId: string) => {
    setExpandedFolders((prev) => {
      const next = new Set(prev)
      if (next.has(folderId)) {
        next.delete(folderId)
      } else {
        next.add(folderId)
      }
      return next
    })
  }, [])

  const handleSelectCategory = useCallback((categoryId: string) => {
    setSelectedCategoryId(categoryId)
  }, [setSelectedCategoryId])

  const getAssetCount = useCallback((categoryId: string) => {
    return assets.filter((a) => a.categoryId === categoryId).length
  }, [assets])

  return (
    <ResizableSidebar storageKey="asset-category-tree" className={className}>
      <ScrollArea className="min-h-0 flex-1 p-3">
        <div className="flex flex-col gap-0.5">
          <div
            data-category-id="all"
            data-is-virtual="true"
            className={cn(
              'flex cursor-pointer items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-all',
              'border border-transparent',
              selectedCategoryId === 'all'
                ? 'bg-primary/10 text-primary font-medium'
                : 'text-muted-foreground hover:bg-surface-hover hover:text-foreground',
              dropTargetId === 'all' && 'border-primary border-dashed bg-primary/10'
            )}
            onClick={() => handleSelectCategory('all')}
          >
            <LayoutGrid className="size-4 shrink-0" />
            <span className="flex-1 truncate">{t('asset.category.all')}</span>
            <span className="font-mono text-xs">{totalAssets}</span>
          </div>

          <div
            data-category-id="favorites"
            data-is-virtual="true"
            className={cn(
              'flex cursor-pointer items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-all',
              'border border-transparent',
              selectedCategoryId === 'favorites'
                ? 'bg-primary/10 text-primary font-medium'
                : 'text-muted-foreground hover:bg-surface-hover hover:text-foreground',
              dropTargetId === 'favorites' && 'border-primary border-dashed bg-primary/10'
            )}
            onClick={() => handleSelectCategory('favorites')}
          >
            <Star className="size-4 shrink-0" />
            <span className="flex-1 truncate">{t('asset.category.favorites')}</span>
            <span className="font-mono text-xs">{favoriteCount}</span>
          </div>

          <div className="mx-3 my-2 h-px bg-border/50" />

          <div
            data-category-id="uncategorized"
            data-is-virtual="true"
            className={cn(
              'flex cursor-pointer items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-all',
              'border border-transparent',
              selectedCategoryId === 'uncategorized'
                ? 'bg-primary/10 text-primary font-medium'
                : 'text-muted-foreground hover:bg-surface-hover hover:text-foreground',
              dropTargetId === 'uncategorized' && 'border-primary border-dashed bg-primary/10'
            )}
            onClick={() => handleSelectCategory('uncategorized')}
          >
            <FolderOpen className="size-4 shrink-0" />
            <span className="flex-1 truncate">{t('asset.category.uncategorized')}</span>
            <span className="font-mono text-xs">{uncategorizedCount}</span>
          </div>

          {categoryTree.rootCategories.map((category) => (
            <CategoryItem
              key={category.id}
              category={category}
              selectedCategoryId={selectedCategoryId}
              expandedFolders={expandedFolders}
              dropTargetId={dropTargetId}
              onToggle={toggleFolder}
              onSelect={handleSelectCategory}
              getChildren={categoryTree.getChildren}
              getAssetCount={getAssetCount}
            />
          ))}
        </div>
      </ScrollArea>

      <div className="shrink-0 border-t border-border-subtle p-3">
        <Button
          variant="ghost"
          className="w-full justify-start gap-2 text-muted-foreground hover:text-foreground"
          onClick={onOpenCategoryManage}
        >
          <Settings className="size-4" />
          {t('asset.manageCategory')}
        </Button>
      </div>
    </ResizableSidebar>
  )
}
