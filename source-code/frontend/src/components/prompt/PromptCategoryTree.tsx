/**
 * 分类树组件
 *
 * 支持在树上直接操作：内联重命名、内联新建（顶级/子级）、右键与悬停菜单、
 * 拖拽移动分类（嵌套 / 同级排序 / 提升为顶级）。所有操作即时生效，不再走批量保存弹窗。
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import {
  Layers,
  Star,
  User,
  Building,
  Sparkles,
  Image,
  FileText,
  Folder,
  FolderOpen,
  FolderPlus,
  FilePlus,
  MoreVertical,
  Pencil,
  Plus,
  Trash2,
  type LucideIcon
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { useDragContext } from './PromptDragContext'
import { useTranslation } from 'react-i18next'
import type { PromptCategory } from '@/stores/usePromptStore'
import type { CategoryIconName } from '@/mocks/prompt'

const iconMap: Record<CategoryIconName, LucideIcon> = {
  'layers': Layers,
  'star': Star,
  'folder': FileText,
  'file-text': FileText,
  'user': User,
  'building': Building,
  'sparkles': Sparkles,
  'image': Image
}

const isVirtual = (category: PromptCategory) =>
  category.isSystem && (category.id === 'all' || category.id === 'favorites')

const findInTree = (cats: PromptCategory[], id: string): PromptCategory | null => {
  for (const c of cats) {
    if (c.id === id) return c
    if (c.children) {
      const found = findInTree(c.children, id)
      if (found) return found
    }
  }
  return null
}

interface PromptCategoryTreeProps {
  categories: PromptCategory[]
  selectedCategoryId: string
  onSelectCategory: (categoryId: string) => void
  onCreateCategory: (parentId: string | null, name: string) => void
  onRenameCategory: (id: string, name: string) => void
  onDeleteCategory: (id: string, name: string) => void
  onCreatePromptInCategory: (id: string) => void
  onMoveCategory: (id: string, parentId: string | null, index: number) => void
}

type EditingState =
  | { kind: 'rename'; id: string; originalName: string }
  | { kind: 'create'; parentId: string | null }
  | null

interface MenuState {
  x: number
  y: number
  category: PromptCategory
  level: number
}

interface DragState {
  id: string
  parentId: string | null
  hasChildren: boolean
}

type DropState =
  | { kind: 'item'; targetId: string; zone: 'before' | 'after' | 'inside' }
  | null

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

export function PromptCategoryTree({
  categories,
  selectedCategoryId,
  onSelectCategory,
  onCreateCategory,
  onRenameCategory,
  onDeleteCategory,
  onCreatePromptInCategory,
  onMoveCategory
}: PromptCategoryTreeProps) {
  const { dropTargetId } = useDragContext()
  const { t } = useTranslation()

  const [editing, setEditing] = useState<EditingState>(null)
  const [menu, setMenu] = useState<MenuState | null>(null)
  const [drag, setDrag] = useState<DragState | null>(null)
  const [drop, setDrop] = useState<DropState>(null)

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

  const startCreate = useCallback((parentId: string | null) => {
    setMenu(null)
    setEditing({ kind: 'create', parentId })
  }, [])

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

  const canDropOn = useCallback((
    target: PromptCategory,
    targetParentId: string | null,
    zone: 'before' | 'after' | 'inside'
  ): boolean => {
    if (!drag) return false
    if (target.id === drag.id) return false
    if (isVirtual(target)) return false

    if (zone === 'inside') {
      // 只支持两级：只能拖入顶级分类，且被拖分类自身不能带子级
      return targetParentId === null && !drag.hasChildren
    }
    // before/after：落入目标所在的同级组
    if (targetParentId === drag.id) return false
    if (drag.hasChildren && targetParentId !== null) return false
    return true
  }, [drag])

  const handleItemDragOver = useCallback((
    e: React.DragEvent,
    target: PromptCategory,
    targetParentId: string | null
  ) => {
    if (!drag) return
    const rect = e.currentTarget.getBoundingClientRect()
    const y = e.clientY - rect.top

    let zone: 'before' | 'after' | 'inside'
    if (targetParentId === null) {
      zone = y < rect.height * 0.28 ? 'before' : y > rect.height * 0.72 ? 'after' : 'inside'
    } else {
      zone = y < rect.height / 2 ? 'before' : 'after'
    }

    if (!canDropOn(target, targetParentId, zone)) return

    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
    setDrop({ kind: 'item', targetId: target.id, zone })
  }, [drag, canDropOn])

  const handleItemDrop = useCallback((
    e: React.DragEvent,
    target: PromptCategory,
    targetParentId: string | null
  ) => {
    e.preventDefault()
    e.stopPropagation()
    if (!drag || !drop || drop.kind !== 'item' || drop.targetId !== target.id) {
      setDrag(null)
      setDrop(null)
      return
    }

    const movingId = drag.id
    if (drop.zone === 'inside') {
      const index = (target.children ?? []).filter((c) => c.id !== movingId).length
      onMoveCategory(movingId, target.id, index)
    } else {
      const siblings = (
        targetParentId === null
          ? categories.filter((c) => !isVirtual(c))
          : findInTree(categories, targetParentId)?.children ?? []
      ).filter((c) => c.id !== movingId)
      let index = siblings.findIndex((c) => c.id === target.id)
      if (index < 0) index = siblings.length
      if (drop.zone === 'after') index += 1
      onMoveCategory(movingId, targetParentId, index)
    }

    setDrag(null)
    setDrop(null)
  }, [drag, drop, categories, onMoveCategory])

  const renderCreateInput = (level: number) => (
    <div
      className="flex items-center gap-2.5 rounded-md border border-primary/40 bg-primary/5 px-3 py-1.5"
      style={{ marginLeft: level * 2 }}
    >
      <Folder className="size-4 shrink-0 text-primary" />
      <InlineEditInput
        initial=""
        placeholder={t('prompt.category.namePlaceholder')}
        onCommit={commitEditing}
        onCancel={cancelEditing}
      />
    </div>
  )

  const renderCategory = (category: PromptCategory, level: number, parentId: string | null) => {
    const virtual = isVirtual(category)
    const hasChildren = !!category.children?.length
    const isSelected = selectedCategoryId === category.id
    const isPromptDropTarget = dropTargetId === category.id
    const renameEditing = editing?.kind === 'rename' && editing.id === category.id ? editing : null
    const isRenaming = !!renameEditing
    const isCreatingHere = editing?.kind === 'create' && editing.parentId === category.id
    const dropZoneHere = drag && drop?.kind === 'item' && drop.targetId === category.id ? drop.zone : null

    const SystemIcon = iconMap[category.icon] ?? Folder
    const FolderIcon = isSelected ? FolderOpen : Folder

    return (
      <div key={category.id}>
        <div
          data-category-id={category.id}
          data-is-virtual={virtual ? 'true' : undefined}
          draggable={!virtual && !isRenaming}
          onDragStart={(e) => {
            if (virtual) return
            e.dataTransfer.setData('text/plain', category.id)
            e.dataTransfer.effectAllowed = 'move'
            setDrag({ id: category.id, parentId, hasChildren })
          }}
          onDragEnd={() => {
            setDrag(null)
            setDrop(null)
          }}
          onDragOver={(e) => handleItemDragOver(e, category, parentId)}
          onDrop={(e) => handleItemDrop(e, category, parentId)}
          onContextMenu={virtual ? undefined : (e) => {
            e.preventDefault()
            setMenu({ x: e.clientX, y: e.clientY, category, level })
          }}
          className={cn(
            'group relative flex cursor-pointer items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors',
            'border border-transparent',
            isSelected
              ? 'bg-primary/10 text-primary font-medium'
              : 'text-muted-foreground hover:bg-surface-hover hover:text-foreground',
            isPromptDropTarget && 'border-primary border-dashed bg-primary/10',
            dropZoneHere === 'inside' && 'border-primary border-dashed bg-primary/10',
            drag?.id === category.id && 'opacity-40'
          )}
          style={{ marginLeft: level * 2 }}
          onClick={() => !isRenaming && onSelectCategory(category.id)}
        >
          {dropZoneHere === 'before' && (
            <span className="pointer-events-none absolute inset-x-1 -top-px h-0.5 rounded bg-primary" />
          )}
          {dropZoneHere === 'after' && (
            <span className="pointer-events-none absolute inset-x-1 -bottom-px h-0.5 rounded bg-primary" />
          )}
          {virtual ? (
            <SystemIcon className={cn(
              'size-4 shrink-0',
              isSelected ? 'text-primary' : 'text-muted-foreground'
            )} />
          ) : (
            <FolderIcon className={cn(
              'size-4 shrink-0',
              isSelected ? 'text-primary' : 'text-muted-foreground'
            )} />
          )}
          {renameEditing ? (
            <InlineEditInput
              initial={renameEditing.originalName}
              placeholder={t('prompt.category.namePlaceholder')}
              onCommit={commitEditing}
              onCancel={cancelEditing}
              className="bg-surface"
            />
          ) : (
            <span className="truncate">{category.name}</span>
          )}
          {!virtual && !isRenaming && (
            <Button
              type="button"
              variant="ghost"
              aria-label={t('prompt.category.actions')}
              className={cn(
                'ml-auto h-6 w-6 shrink-0 rounded p-0 text-muted-foreground',
                'opacity-0 hover:bg-surface-hover hover:text-foreground focus-visible:opacity-100',
                'group-hover:opacity-100'
              )}
              onClick={(e) => {
                e.stopPropagation()
                const rect = e.currentTarget.getBoundingClientRect()
                setMenu({ x: rect.right, y: rect.bottom + 4, category, level })
              }}
            >
              <MoreVertical className="size-3.5" />
            </Button>
          )}
        </div>

        {(hasChildren || isCreatingHere) && (
          <div className="ml-3 border-l border-border-subtle pl-0.5">
            {hasChildren && category.children!.map((child) =>
              renderCategory(child, level + 1, category.id)
            )}
            {isCreatingHere && renderCreateInput(level + 1)}
          </div>
        )}
      </div>
    )
  }

  const isCreatingRoot = editing?.kind === 'create' && editing.parentId === null

  return (
    <div className="flex h-full flex-col">
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
            {t('prompt.category.newRoot')}
          </Button>
        )}
      </div>

      <ScrollArea className="flex-1 px-3 pb-3">
        <div className="flex flex-col gap-0.5">
          {categories.map((category) => renderCategory(category, 0, null))}
        </div>
      </ScrollArea>

      {menu && createPortal(
        <div
          data-category-menu
          className="fixed z-[9999] min-w-[150px] rounded-lg border border-border bg-background p-1 shadow-lg"
          style={{
            left: Math.min(menu.x, window.innerWidth - 170),
            top: Math.min(menu.y, window.innerHeight - 170)
          }}
        >
          {menu.level === 0 && (
            <MenuAction
              icon={FolderPlus}
              label={t('prompt.category.newChild')}
              onClick={() => startCreate(menu.category.id)}
            />
          )}
          <MenuAction
            icon={FilePlus}
            label={t('prompt.category.newPrompt')}
            onClick={() => {
              setMenu(null)
              onCreatePromptInCategory(menu.category.id)
            }}
          />
          <MenuAction
            icon={Pencil}
            label={t('prompt.category.rename')}
            onClick={() => startRename(menu.category.id, menu.category.name)}
          />
          <div className="my-1 h-px bg-border/50" />
          <MenuAction
            icon={Trash2}
            label={t('prompt.category.delete')}
            destructive
            onClick={() => {
              setMenu(null)
              onDeleteCategory(menu.category.id, menu.category.name)
            }}
          />
        </div>,
        document.body
      )}
    </div>
  )
}
