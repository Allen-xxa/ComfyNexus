/**
 * 资产库分类树
 *
 * 与提示词/工作流的目录树同一套交互：树上直接内联改名、内联新建（顶级或任意子级）、
 * 悬停 ⋯ 与右键菜单、拖拽换父级，删除前先确认内容去向。
 *
 * 说明：资产分类就是资产库里的真实文件夹，顺序由磁盘扫描决定、无法自定义重排，
 * 因此拖拽只支持"放入某分类内 / 放到根级"来改变父级，不做同级上下排序。
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import {
  LayoutGrid,
  Star,
  Folder,
  FolderOpen,
  FolderPlus,
  CornerUpLeft,
  MoreVertical,
  Pencil,
  Plus,
  Trash2,
  type LucideIcon
} from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { ResizableSidebar } from '@/components/common/ResizableSidebar'
import { useAssetStore } from '@/stores/useAssetStore'
import { useAssetDragContext } from './AssetDragContext'
import type { AssetCategory } from '@/mocks/asset'

export interface CategoryDeleteRequest {
  id: string
  name: string
  assetCount: number
  childCount: number
}

interface AssetCategoryTreeProps {
  className?: string
  onCreateCategory: (parentId: string | null, name: string) => void
  onRenameCategory: (id: string, name: string) => void
  onMoveCategory: (id: string, newParentId: string | null) => void
  onDeleteCategoryRequest: (request: CategoryDeleteRequest) => void
}

type EditingState =
  | { kind: 'rename'; id: string; originalName: string }
  | { kind: 'create'; parentId: string | null }
  | null

interface MenuState {
  x: number
  y: number
  category: AssetCategory
}

function InlineEditInput({
  initial,
  placeholder,
  onCommit,
  onCancel,
  className
}: {
  initial: string
  placeholder: string
  onCommit: (name: string) => void
  onCancel: () => void
  className?: string
}) {
  const [value, setValue] = useState(initial)
  const doneRef = useRef(false)

  const commit = () => {
    if (doneRef.current) return
    doneRef.current = true
    onCommit(value.trim())
  }

  const cancel = () => {
    if (doneRef.current) return
    doneRef.current = true
    onCancel()
  }

  return (
    <Input
      autoFocus
      value={value}
      placeholder={placeholder}
      onChange={(e) => setValue(e.target.value)}
      onClick={(e) => e.stopPropagation()}
      onMouseDown={(e) => e.stopPropagation()}
      onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === 'Enter') {
          e.preventDefault()
          commit()
        } else if (e.key === 'Escape') {
          e.preventDefault()
          cancel()
        }
      }}
      className={cn(
        'h-7 min-w-0 flex-1 rounded-sm border-primary/60 bg-transparent px-1.5 text-sm',
        className
      )}
    />
  )
}

function MenuAction({
  icon: Icon,
  label,
  onClick,
  destructive
}: {
  icon: LucideIcon
  label: string
  onClick: () => void
  destructive?: boolean
}) {
  return (
    <Button
      type="button"
      variant="ghost"
      onClick={onClick}
      className={cn(
        'h-auto w-full justify-start gap-2 rounded-sm px-2 py-1.5 text-sm font-normal',
        destructive
          ? 'text-destructive hover:bg-destructive/10 hover:text-destructive'
          : 'text-foreground hover:bg-surface-hover'
      )}
    >
      <Icon className="size-3.5" />
      <span>{label}</span>
    </Button>
  )
}

export function AssetCategoryTree({
  className,
  onCreateCategory,
  onRenameCategory,
  onMoveCategory,
  onDeleteCategoryRequest
}: AssetCategoryTreeProps) {
  const { t } = useTranslation()
  const {
    assets,
    categories,
    selectedCategoryId,
    setSelectedCategoryId
  } = useAssetStore()

  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set())
  const [editing, setEditing] = useState<EditingState>(null)
  const [menu, setMenu] = useState<MenuState | null>(null)
  const [dragId, setDragId] = useState<string | null>(null)
  const [folderDropTarget, setFolderDropTarget] = useState<string | null>(null)

  // 卡片是用鼠标事件自己实现的拖拽，落点靠 data-category-id 反查，这里只负责高亮
  const assetDropTargetId = useAssetDragContext()?.dropTargetId ?? null

  const totalAssets = assets.length
  const favoriteCount = assets.filter((a) => a.isFavorite).length
  const uncategorizedCount = assets.filter((a) => !a.categoryId).length

  const childrenMap = useMemo(() => {
    const map = new Map<string, AssetCategory[]>()
    categories.forEach((c) => {
      const key = c.parentId ?? ''
      const list = map.get(key)
      if (list) list.push(c)
      else map.set(key, [c])
    })
    return map
  }, [categories])

  const categoryById = useMemo(() => {
    const map = new Map<string, AssetCategory>()
    categories.forEach((c) => map.set(c.id, c))
    return map
  }, [categories])

  const getChildren = useCallback(
    (parentId: string): AssetCategory[] => childrenMap.get(parentId) ?? [],
    [childrenMap]
  )

  const rootCategories = useMemo(
    () => (childrenMap.get('') ?? []).filter((c) => c.id !== 'all' && c.id !== 'favorites'),
    [childrenMap]
  )

  const isDescendantOf = useCallback((id: string, ancestorId: string): boolean => {
    let cur = categoryById.get(id)?.parentId ?? null
    while (cur) {
      if (cur === ancestorId) return true
      cur = categoryById.get(cur)?.parentId ?? null
    }
    return false
  }, [categoryById])

  const subtreeIds = useCallback((id: string): Set<string> => {
    const result = new Set<string>([id])
    const stack = [id]
    while (stack.length) {
      const current = stack.pop() as string
      for (const child of childrenMap.get(current) ?? []) {
        result.add(child.id)
        stack.push(child.id)
      }
    }
    return result
  }, [childrenMap])

  // 每个分类的"含子分类"资产数一次算完：逐行各自遍历全量资产会让侧栏在库变大后明显卡顿
  const subtreeAssetCounts = useMemo(() => {
    const counts = new Map<string, number>()
    for (const asset of assets) {
      const seen = new Set<string>()
      let cur = asset.categoryId ?? null
      while (cur && !seen.has(cur)) {
        seen.add(cur)
        counts.set(cur, (counts.get(cur) ?? 0) + 1)
        cur = categoryById.get(cur)?.parentId ?? null
      }
    }
    return counts
  }, [assets, categoryById])

  const countAssetsInSubtree = useCallback((id: string): number => subtreeAssetCounts.get(id) ?? 0, [subtreeAssetCounts])

  useEffect(() => {
    if (!menu) return

    const handleDown = (e: MouseEvent) => {
      if (!(e.target as HTMLElement).closest('[data-category-menu]')) {
        setMenu(null)
      }
    }
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setMenu(null)
    }

    document.addEventListener('mousedown', handleDown)
    document.addEventListener('keydown', handleKey)
    return () => {
      document.removeEventListener('mousedown', handleDown)
      document.removeEventListener('keydown', handleKey)
    }
  }, [menu])

  const toggleFolder = useCallback((folderId: string) => {
    setExpandedFolders((prev) => {
      const next = new Set(prev)
      if (next.has(folderId)) next.delete(folderId)
      else next.add(folderId)
      return next
    })
  }, [])

  const expandFolder = useCallback((folderId: string) => {
    setExpandedFolders((prev) => {
      if (prev.has(folderId)) return prev
      const next = new Set(prev)
      next.add(folderId)
      return next
    })
  }, [])

  const startCreate = useCallback((parentId: string | null) => {
    setMenu(null)
    if (parentId) expandFolder(parentId)
    setEditing({ kind: 'create', parentId })
  }, [expandFolder])

  const startRename = useCallback((id: string, currentName: string) => {
    setMenu(null)
    setEditing({ kind: 'rename', id, originalName: currentName })
  }, [])

  const commitEditing = useCallback((name: string) => {
    if (!editing) return
    if (editing.kind === 'rename') {
      if (name && name !== editing.originalName) {
        onRenameCategory(editing.id, name)
      }
    } else if (name) {
      onCreateCategory(editing.parentId, name)
    }
    setEditing(null)
  }, [editing, onRenameCategory, onCreateCategory])

  const cancelEditing = useCallback(() => setEditing(null), [])

  const canDropInside = useCallback((targetId: string): boolean => {
    if (!dragId) return false
    if (targetId === dragId) return false
    if (isDescendantOf(targetId, dragId)) return false
    const target = categoryById.get(targetId)
    if (!target || target.isSystem) return false
    return true
  }, [dragId, isDescendantOf, categoryById])

  const handleDragOver = useCallback((e: React.DragEvent, targetId: string) => {
    if (!canDropInside(targetId)) return
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
    setFolderDropTarget(targetId)
  }, [canDropInside])

  const handleDrop = useCallback((e: React.DragEvent, newParentId: string | null) => {
    e.preventDefault()
    e.stopPropagation()
    if (dragId) {
      const movingId = dragId
      const sameParent = (categoryById.get(movingId)?.parentId ?? null) === newParentId
      if (newParentId !== null && !sameParent) {
        expandFolder(newParentId)
      }
      if (!sameParent) onMoveCategory(movingId, newParentId)
    }
    setDragId(null)
    setFolderDropTarget(null)
  }, [dragId, categoryById, expandFolder, onMoveCategory])

  const renderCreateInput = (level: number) => (
    <div
      key={`create-${level}`}
      className="flex items-center gap-2.5 rounded-md border border-primary/40 bg-primary/5 px-3 py-1.5"
      style={{ marginLeft: level * 2 }}
    >
      <Folder className="size-4 shrink-0 text-primary" />
      <InlineEditInput
        initial=""
        placeholder={t('asset.category.namePlaceholder')}
        onCommit={commitEditing}
        onCancel={cancelEditing}
      />
    </div>
  )

  const renderCategory = (category: AssetCategory, level: number) => {
    const children = getChildren(category.id)
    const hasChildren = children.length > 0
    const isExpanded = expandedFolders.has(category.id)
    const isSelected = selectedCategoryId === category.id
    const isAssetDropTarget = assetDropTargetId === category.id
    const isFolderDropTarget = folderDropTarget === category.id
    const renameEditing = editing?.kind === 'rename' && editing.id === category.id ? editing : null
    const isRenaming = !!renameEditing
    const isCreatingHere = editing?.kind === 'create' && editing.parentId === category.id
    const assetCount = countAssetsInSubtree(category.id)
    const CategoryIcon = isSelected ? FolderOpen : Folder

    return (
      <div key={category.id}>
        <div
          data-category-id={category.id}
          draggable={!isRenaming}
          onDragStart={(e) => {
            if (isRenaming) return
            e.dataTransfer.setData('text/plain', category.id)
            e.dataTransfer.effectAllowed = 'move'
            setDragId(category.id)
          }}
          onDragEnd={() => {
            setDragId(null)
            setFolderDropTarget(null)
          }}
          onDragOver={(e) => handleDragOver(e, category.id)}
          onDrop={(e) => handleDrop(e, category.id)}
          onContextMenu={(e) => {
            e.preventDefault()
            setMenu({ x: e.clientX, y: e.clientY, category })
          }}
          className={cn(
            'group relative flex cursor-pointer items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors',
            'border border-transparent',
            isSelected
              ? 'bg-primary/10 text-primary font-medium'
              : 'text-muted-foreground hover:bg-surface-hover hover:text-foreground',
            isAssetDropTarget && 'border-primary border-dashed bg-primary/10',
            isFolderDropTarget && 'border-primary border-dashed bg-primary/15',
            dragId === category.id && 'opacity-40'
          )}
          style={{ marginLeft: level * 2 }}
          onClick={() => {
            if (isRenaming) return
            setSelectedCategoryId(category.id)
            if (hasChildren) toggleFolder(category.id)
          }}
        >
          <CategoryIcon className={cn(
            'size-4 shrink-0',
            isSelected ? 'text-primary' : 'text-muted-foreground'
          )} />
          {renameEditing ? (
            <InlineEditInput
              initial={renameEditing.originalName}
              placeholder={t('asset.category.namePlaceholder')}
              onCommit={commitEditing}
              onCancel={cancelEditing}
              className="bg-surface"
            />
          ) : (
            <span className="flex-1 truncate">
              {category.isSystem ? t(`asset.category.${category.id}`) : category.name}
            </span>
          )}
          {!isRenaming && assetCount > 0 && (
            <span className="shrink-0 rounded bg-primary/20 px-1.5 py-0.5 font-mono text-[11px]">
              {assetCount}
            </span>
          )}
          {!isRenaming && (
            <Button
              type="button"
              variant="ghost"
              aria-label={t('asset.category.actions')}
              className={cn(
                'h-6 w-6 shrink-0 rounded p-0 text-muted-foreground',
                'opacity-0 hover:bg-surface-hover hover:text-foreground focus-visible:opacity-100',
                'group-hover:opacity-100'
              )}
              onClick={(e) => {
                e.stopPropagation()
                const rect = e.currentTarget.getBoundingClientRect()
                setMenu({ x: rect.right, y: rect.bottom + 4, category })
              }}
            >
              <MoreVertical className="size-3.5" />
            </Button>
          )}
        </div>

        {(hasChildren || isCreatingHere) && isExpanded && (
          <div className="ml-3 border-l border-border-subtle pl-0.5">
            {children.map((child) => renderCategory(child, level + 1))}
            {isCreatingHere && renderCreateInput(level + 1)}
          </div>
        )}
      </div>
    )
  }

  const isCreatingRoot = editing?.kind === 'create' && editing.parentId === null

  return (
    <ResizableSidebar storageKey="asset-category-tree" className={className}>
      <div className="shrink-0 px-3 pb-1 pt-3">
        {isCreatingRoot ? (
          renderCreateInput(0)
        ) : (
          <Button
            variant="ghost"
            size="sm"
            className="w-full justify-start gap-1.5 text-xs text-muted-foreground hover:text-foreground"
            onClick={() => startCreate(null)}
          >
            <Plus className="size-3.5" />
            {t('asset.category.newRoot')}
          </Button>
        )}
      </div>

      <ScrollArea className="min-h-0 flex-1 px-3 pb-3">
        <div className="flex flex-col gap-0.5">
          <div
            data-category-id="all"
            data-is-virtual="true"
            onDragOver={(e) => {
              if (!dragId) return
              e.preventDefault()
              e.dataTransfer.dropEffect = 'move'
              setFolderDropTarget('all')
            }}
            onDrop={(e) => handleDrop(e, null)}
            className={cn(
              'flex cursor-pointer items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-all',
              'border border-transparent',
              selectedCategoryId === 'all'
                ? 'bg-primary/10 text-primary font-medium'
                : 'text-muted-foreground hover:bg-surface-hover hover:text-foreground',
              assetDropTargetId === 'all' && 'border-primary border-dashed bg-primary/10',
              folderDropTarget === 'all' && 'border-primary border-dashed bg-primary/15'
            )}
            onClick={() => setSelectedCategoryId('all')}
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
              assetDropTargetId === 'favorites' && 'border-primary border-dashed bg-primary/10'
            )}
            onClick={() => setSelectedCategoryId('favorites')}
          >
            <Star className="size-4 shrink-0" />
            <span className="flex-1 truncate">{t('asset.category.favorites')}</span>
            <span className="font-mono text-xs">{favoriteCount}</span>
          </div>

          <div
            data-category-id="uncategorized"
            data-is-virtual="true"
            className={cn(
              'flex cursor-pointer items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-all',
              'border border-transparent',
              selectedCategoryId === 'uncategorized'
                ? 'bg-primary/10 text-primary font-medium'
                : 'text-muted-foreground hover:bg-surface-hover hover:text-foreground',
              assetDropTargetId === 'uncategorized' && 'border-primary border-dashed bg-primary/10'
            )}
            onClick={() => setSelectedCategoryId('uncategorized')}
          >
            <FolderOpen className="size-4 shrink-0" />
            <span className="flex-1 truncate">{t('asset.category.uncategorized')}</span>
            <span className="font-mono text-xs">{uncategorizedCount}</span>
          </div>

          <div className="mx-3 my-2 h-px bg-border/50" />

          {rootCategories.map((category) => renderCategory(category, 0))}
        </div>
      </ScrollArea>

      {menu && createPortal(
        <div
          data-category-menu
          className="fixed z-[9999] min-w-[150px] rounded-lg border border-border bg-background p-1 shadow-lg"
          style={{
            left: Math.min(menu.x, window.innerWidth - 180),
            top: Math.min(menu.y, window.innerHeight - 200)
          }}
        >
          <MenuAction
            icon={FolderPlus}
            label={t('asset.category.newChild')}
            onClick={() => startCreate(menu.category.id)}
          />
          {!menu.category.isSystem && (
            <>
              <MenuAction
                icon={Pencil}
                label={t('asset.category.rename')}
                onClick={() => startRename(menu.category.id, menu.category.name)}
              />
              {menu.category.parentId && (
                <MenuAction
                  icon={CornerUpLeft}
                  label={t('asset.category.moveToRoot')}
                  onClick={() => {
                    const id = menu.category.id
                    setMenu(null)
                    onMoveCategory(id, null)
                  }}
                />
              )}
              <div className="my-1 h-px bg-border/50" />
              <MenuAction
                icon={Trash2}
                label={t('asset.category.delete')}
                destructive
                onClick={() => {
                  const { id, name } = menu.category
                  setMenu(null)
                  onDeleteCategoryRequest({
                    id,
                    name,
                    assetCount: countAssetsInSubtree(id),
                    childCount: subtreeIds(id).size - 1
                  })
                }}
              />
            </>
          )}
        </div>,
        document.body
      )}
    </ResizableSidebar>
  )
}
