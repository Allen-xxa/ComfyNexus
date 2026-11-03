/**
 * 工作流目录导航组件
 *
 * 支持在树上直接操作：内联重命名、内联新建（顶级/任意层级子级）、悬停 ⋯ 与右键菜单、
 * 拖拽换父级。所有操作即时生效，不再走批量保存弹窗。
 *
 * 说明：工作流文件夹是真实的文件系统目录，顺序由磁盘扫描决定、无法自定义重排，
 * 因此拖拽只支持"放入某文件夹内 / 放到根级"来改变父级，不做同级上下排序。
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
import { useWorkflowStore } from '@/stores/useWorkflowStore'
import type { WorkflowFolder } from '@/types/workflow'

interface WorkflowSidebarProps {
  className?: string
  dropTargetId?: string | null
  onCreateFolder: (parentId: string | null, name: string) => void
  onRenameFolder: (id: string, name: string) => void
  onDeleteFolderRequest: (id: string, name: string, hasWorkflows: boolean) => void
  onMoveFolder: (id: string, newParentId: string | null) => void
}

type EditingState =
  | { kind: 'rename'; id: string; originalName: string }
  | { kind: 'create'; parentId: string | null }
  | null

interface MenuState {
  x: number
  y: number
  folder: WorkflowFolder
}

interface DragState {
  id: string
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

export function WorkflowSidebar({
  className,
  dropTargetId,
  onCreateFolder,
  onRenameFolder,
  onDeleteFolderRequest,
  onMoveFolder
}: WorkflowSidebarProps) {
  const { t } = useTranslation()
  const {
    folders,
    workflows,
    filterType,
    selectedFolderId,
    setFilterType,
    setSelectedFolderId
  } = useWorkflowStore()

  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set())
  const [editing, setEditing] = useState<EditingState>(null)
  const [menu, setMenu] = useState<MenuState | null>(null)
  const [drag, setDrag] = useState<DragState | null>(null)
  const [dropTarget, setDropTarget] = useState<string | null>(null)

  const totalWorkflows = workflows.length
  const favoriteCount = workflows.filter((w) => w.isFavorite).length

  const childrenMap = useMemo(() => {
    const map = new Map<string, WorkflowFolder[]>()
    folders.forEach((f) => {
      const key = f.parentId ?? ''
      const list = map.get(key)
      if (list) list.push(f)
      else map.set(key, [f])
    })
    return map
  }, [folders])

  const folderById = useMemo(() => {
    const map = new Map<string, WorkflowFolder>()
    folders.forEach((f) => map.set(f.id, f))
    return map
  }, [folders])

  const getChildren = useCallback(
    (parentId: string): WorkflowFolder[] => childrenMap.get(parentId) ?? [],
    [childrenMap]
  )

  const rootFolders = useMemo(() => childrenMap.get('') ?? [], [childrenMap])

  const isDescendantOf = useCallback((id: string, ancestorId: string): boolean => {
    let cur = folderById.get(id)?.parentId ?? null
    while (cur) {
      if (cur === ancestorId) return true
      cur = folderById.get(cur)?.parentId ?? null
    }
    return false
  }, [folderById])

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

  const countWorkflowsInSubtree = useCallback((id: string): number => {
    const ids = subtreeIds(id)
    let count = 0
    for (const w of workflows) {
      if (w.folderId && ids.has(w.folderId)) count += 1
    }
    return count
  }, [subtreeIds, workflows])

  useEffect(() => {
    if (!menu) return

    const handleDown = (e: MouseEvent) => {
      if (!(e.target as HTMLElement).closest('[data-folder-menu]')) {
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
        onRenameFolder(editing.id, name)
      }
    } else if (name) {
      onCreateFolder(editing.parentId, name)
    }
    setEditing(null)
  }, [editing, onRenameFolder, onCreateFolder])

  const cancelEditing = useCallback(() => setEditing(null), [])

  const canDropInside = useCallback((targetId: string): boolean => {
    if (!drag) return false
    if (targetId === drag.id) return false
    if (isDescendantOf(targetId, drag.id)) return false
    return true
  }, [drag, isDescendantOf])

  const handleFolderDragOver = useCallback((e: React.DragEvent, targetId: string) => {
    if (!canDropInside(targetId)) return
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
    setDropTarget(targetId)
  }, [canDropInside])

  const handleFolderDrop = useCallback((e: React.DragEvent, newParentId: string | null) => {
    e.preventDefault()
    e.stopPropagation()
    if (drag) {
      const movingId = drag.id
      const sameParent = (folderById.get(movingId)?.parentId ?? null) === newParentId
      if (newParentId !== null && !sameParent) {
        expandFolder(newParentId)
      }
      if (!sameParent) onMoveFolder(movingId, newParentId)
    }
    setDrag(null)
    setDropTarget(null)
  }, [drag, folderById, expandFolder, onMoveFolder])

  const renderCreateInput = (level: number) => (
    <div
      key={`create-${level}`}
      className="flex items-center gap-2.5 rounded-md border border-primary/40 bg-primary/5 px-3 py-1.5"
      style={{ marginLeft: level * 2 }}
    >
      <Folder className="size-4 shrink-0 text-primary" />
      <InlineEditInput
        initial=""
        placeholder={t('workflow.folder.namePlaceholder')}
        onCommit={commitEditing}
        onCancel={cancelEditing}
      />
    </div>
  )

  const renderFolder = (folder: WorkflowFolder, level: number) => {
    const children = getChildren(folder.id)
    const hasChildren = children.length > 0
    const isExpanded = expandedFolders.has(folder.id)
    const isSelected = selectedFolderId === folder.id && filterType === 'folder'
    const isWorkflowDropTarget = dropTargetId === folder.id
    const isFolderDropTarget = dropTarget === folder.id
    const renameEditing = editing?.kind === 'rename' && editing.id === folder.id ? editing : null
    const isRenaming = !!renameEditing
    const isCreatingHere = editing?.kind === 'create' && editing.parentId === folder.id
    const workflowCount = countWorkflowsInSubtree(folder.id)
    const FolderIcon = isSelected ? FolderOpen : Folder

    return (
      <div key={folder.id}>
        <div
          data-folder-id={folder.id}
          draggable={!isRenaming}
          onDragStart={(e) => {
            if (isRenaming) return
            e.dataTransfer.setData('text/plain', folder.id)
            e.dataTransfer.effectAllowed = 'move'
            setDrag({ id: folder.id })
          }}
          onDragEnd={() => {
            setDrag(null)
            setDropTarget(null)
          }}
          onDragOver={(e) => handleFolderDragOver(e, folder.id)}
          onDrop={(e) => handleFolderDrop(e, folder.id)}
          onContextMenu={(e) => {
            e.preventDefault()
            setMenu({ x: e.clientX, y: e.clientY, folder })
          }}
          className={cn(
            'group relative flex cursor-pointer items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors',
            'border border-transparent',
            isSelected
              ? 'bg-primary/10 text-primary font-medium'
              : 'text-muted-foreground hover:bg-surface-hover hover:text-foreground',
            isWorkflowDropTarget && 'border-primary border-dashed bg-primary/10',
            isFolderDropTarget && 'border-primary border-dashed bg-primary/15',
            drag?.id === folder.id && 'opacity-40'
          )}
          style={{ marginLeft: level * 2 }}
          onClick={() => {
            if (isRenaming) return
            setSelectedFolderId(folder.id)
            if (hasChildren) toggleFolder(folder.id)
          }}
        >
          <FolderIcon className={cn(
            'size-4 shrink-0',
            isSelected ? 'text-primary' : 'text-muted-foreground'
          )} />
          {renameEditing ? (
            <InlineEditInput
              initial={renameEditing.originalName}
              placeholder={t('workflow.folder.namePlaceholder')}
              onCommit={commitEditing}
              onCancel={cancelEditing}
              className="bg-surface"
            />
          ) : (
            <span className="flex-1 truncate">{folder.name}</span>
          )}
          {!isRenaming && workflowCount > 0 && (
            <span className="shrink-0 rounded bg-primary/20 px-1.5 py-0.5 font-mono text-[11px]">
              {workflowCount}
            </span>
          )}
          {!isRenaming && (
            <Button
              type="button"
              variant="ghost"
              aria-label={t('workflow.folder.actions')}
              className={cn(
                'h-6 w-6 shrink-0 rounded p-0 text-muted-foreground',
                'opacity-0 hover:bg-surface-hover hover:text-foreground focus-visible:opacity-100',
                'group-hover:opacity-100'
              )}
              onClick={(e) => {
                e.stopPropagation()
                const rect = e.currentTarget.getBoundingClientRect()
                setMenu({ x: rect.right, y: rect.bottom + 4, folder })
              }}
            >
              <MoreVertical className="size-3.5" />
            </Button>
          )}
        </div>

        {(hasChildren || isCreatingHere) && isExpanded && (
          <div className="ml-3 border-l border-border-subtle pl-0.5">
            {children.map((child) => renderFolder(child, level + 1))}
            {isCreatingHere && renderCreateInput(level + 1)}
          </div>
        )}
      </div>
    )
  }

  const isCreatingRoot = editing?.kind === 'create' && editing.parentId === null

  return (
    <aside className={cn('flex w-56 flex-col flex-shrink-0 border-r border-border-subtle bg-surface', className)}>
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
            {t('workflow.folder.newRoot')}
          </Button>
        )}
      </div>

      <ScrollArea className="flex-1 px-3 pb-3">
        <div className="flex flex-col gap-0.5">
          <div
            data-folder-id="all"
            data-is-virtual="true"
            onDragOver={(e) => {
              if (!drag) return
              e.preventDefault()
              e.dataTransfer.dropEffect = 'move'
              setDropTarget('all')
            }}
            onDrop={(e) => handleFolderDrop(e, null)}
            className={cn(
              'flex cursor-pointer items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-all',
              'border border-transparent',
              filterType === 'all'
                ? 'bg-primary/10 text-primary font-medium'
                : 'text-muted-foreground hover:bg-surface-hover hover:text-foreground',
              dropTarget === 'all' && 'border-primary border-dashed bg-primary/15'
            )}
            onClick={() => setFilterType('all')}
          >
            <LayoutGrid className="size-4 shrink-0" />
            <span className="flex-1 truncate">{t('workflow.sidebar.allWorkflows')}</span>
            <span className="font-mono text-xs">{totalWorkflows}</span>
          </div>

          <div
            data-folder-id="favorites"
            data-is-virtual="true"
            className={cn(
              'flex cursor-pointer items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-all',
              'border border-transparent',
              filterType === 'favorites'
                ? 'bg-primary/10 text-primary font-medium'
                : 'text-muted-foreground hover:bg-surface-hover hover:text-foreground',
              dropTargetId === 'favorites' && 'border-primary border-dashed bg-primary/10'
            )}
            onClick={() => setFilterType('favorites')}
          >
            <Star className="size-4 shrink-0" />
            <span className="flex-1 truncate">{t('workflow.sidebar.favorites')}</span>
            <span className="font-mono text-xs">{favoriteCount}</span>
          </div>

          <div className="mx-3 my-2 h-px bg-border/50" />

          {rootFolders.map((folder) => renderFolder(folder, 0))}
        </div>
      </ScrollArea>

      {menu && createPortal(
        <div
          data-folder-menu
          className="fixed z-[9999] min-w-[150px] rounded-lg border border-border bg-background p-1 shadow-lg"
          style={{
            left: Math.min(menu.x, window.innerWidth - 180),
            top: Math.min(menu.y, window.innerHeight - 200)
          }}
        >
          <MenuAction
            icon={FolderPlus}
            label={t('workflow.folder.newChild')}
            onClick={() => startCreate(menu.folder.id)}
          />
          <MenuAction
            icon={Pencil}
            label={t('workflow.folder.rename')}
            onClick={() => startRename(menu.folder.id, menu.folder.name)}
          />
          {menu.folder.parentId && (
            <MenuAction
              icon={CornerUpLeft}
              label={t('workflow.folder.moveToRoot')}
              onClick={() => {
                const id = menu.folder.id
                setMenu(null)
                onMoveFolder(id, null)
              }}
            />
          )}
          <div className="my-1 h-px bg-border/50" />
          <MenuAction
            icon={Trash2}
            label={t('workflow.folder.delete')}
            destructive
            onClick={() => {
              const { id, name } = menu.folder
              setMenu(null)
              onDeleteFolderRequest(id, name, countWorkflowsInSubtree(id) > 0)
            }}
          />
        </div>,
        document.body
      )}
    </aside>
  )
}
