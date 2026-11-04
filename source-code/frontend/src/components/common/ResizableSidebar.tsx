/**
 * 可拖拽宽度的侧边栏外壳
 *
 * 分类树/文件夹树统一使用：边缘拖拽调宽、双击复位、折叠成窄条。
 * 宽度和折叠状态写入 localStorage，刷新后保持。
 * side 决定把手与折叠按钮在哪一侧：左栏（默认）把手在右缘，右栏把手在左缘。
 */

import { useCallback, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  PanelLeftClose,
  PanelLeftOpen,
  PanelRightClose,
  PanelRightOpen
} from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { cn } from '@/lib/utils'

const WIDTH_KEY_PREFIX = 'sidebar-width:'
const COLLAPSED_KEY_PREFIX = 'sidebar-collapsed:'

interface ResizableSidebarProps {
  /** localStorage 命名空间，不同页面传不同值 */
  storageKey: string
  children: React.ReactNode
  defaultWidth?: number
  minWidth?: number
  maxWidth?: number
  className?: string
  /** 面板相对内容区的位置，决定拖拽把手和折叠按钮在哪一缘 */
  side?: 'left' | 'right'
}

function clampWidth(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

function readStoredWidth(storageKey: string, fallback: number, min: number, max: number): number {
  const stored = Number(localStorage.getItem(WIDTH_KEY_PREFIX + storageKey))
  if (!Number.isFinite(stored) || stored <= 0) return fallback
  return clampWidth(stored, min, max)
}

export function ResizableSidebar({
  storageKey,
  children,
  defaultWidth = 224,
  minWidth = 180,
  maxWidth = 440,
  className,
  side = 'left'
}: ResizableSidebarProps) {
  const { t } = useTranslation()
  const isRight = side === 'right'

  const [collapsed, setCollapsed] = useState(
    () => localStorage.getItem(COLLAPSED_KEY_PREFIX + storageKey) === 'true'
  )
  const [width, setWidth] = useState(() => readStoredWidth(storageKey, defaultWidth, minWidth, maxWidth))
  const dragRef = useRef<{ startX: number; startWidth: number } | null>(null)

  const persistWidth = useCallback(
    (value: number) => {
      const next = clampWidth(value, minWidth, maxWidth)
      setWidth(next)
      localStorage.setItem(WIDTH_KEY_PREFIX + storageKey, String(next))
    },
    [maxWidth, minWidth, storageKey]
  )

  const toggleCollapsed = useCallback(() => {
    setCollapsed((prev) => {
      localStorage.setItem(COLLAPSED_KEY_PREFIX + storageKey, String(!prev))
      return !prev
    })
  }, [storageKey])

  const handleResizeStart = useCallback(
    (event: React.PointerEvent<HTMLDivElement>) => {
      if (event.button !== 0) return
      event.preventDefault()

      dragRef.current = { startX: event.clientX, startWidth: width }

      const startX = event.clientX
      // 右栏向左拖才是变宽，delta 要按把手所在缘镜像
      const signedDelta = (clientX: number) =>
        isRight ? startX - clientX : clientX - startX

      const handleMove = (moveEvent: PointerEvent) => {
        const drag = dragRef.current
        if (!drag) return
        setWidth(clampWidth(drag.startWidth + signedDelta(moveEvent.clientX), minWidth, maxWidth))
      }

      const handleUp = (upEvent: PointerEvent) => {
        window.removeEventListener('pointermove', handleMove)
        window.removeEventListener('pointerup', handleUp)
        const drag = dragRef.current
        dragRef.current = null
        if (drag) {
          persistWidth(drag.startWidth + signedDelta(upEvent.clientX))
        }
      }

      window.addEventListener('pointermove', handleMove)
      window.addEventListener('pointerup', handleUp)
    },
    [isRight, maxWidth, minWidth, persistWidth, width]
  )

  if (collapsed) {
    const ExpandIcon = isRight ? PanelRightOpen : PanelLeftOpen
    return (
      <aside
        className={cn(
          'flex w-10 shrink-0 flex-col items-center bg-surface py-2',
          isRight ? 'border-l border-border-subtle' : 'border-r border-border-subtle',
          className
        )}
      >
        <Button
          variant="ghost"
          size="icon"
          onClick={toggleCollapsed}
          title={t('common.sidebar.expand')}
          className="size-7 text-muted-foreground hover:text-foreground"
        >
          <ExpandIcon className="size-4" />
        </Button>
      </aside>
    )
  }

  const CollapseIcon = isRight ? PanelRightClose : PanelLeftClose

  return (
    <aside
      className={cn(
        'group/sidebar relative flex shrink-0 flex-col bg-surface',
        isRight ? 'border-l border-border-subtle' : 'border-r border-border-subtle',
        className
      )}
      style={{ width }}
    >
      {children}

      <div
        role="separator"
        aria-orientation="vertical"
        onPointerDown={handleResizeStart}
        onDoubleClick={() => persistWidth(defaultWidth)}
        title={t('common.sidebar.resetHint')}
        className={cn(
          'absolute top-0 z-10 h-full w-2 cursor-col-resize',
          isRight
            ? '-left-1 after:absolute after:left-0.5 after:top-0 after:h-full after:w-px after:bg-transparent'
            : '-right-1 after:absolute after:right-0.5 after:top-0 after:h-full after:w-px after:bg-transparent',
          'hover:after:bg-primary/40 active:after:bg-primary'
        )}
      />

      <Button
        variant="ghost"
        size="icon"
        onClick={toggleCollapsed}
        title={t('common.sidebar.collapse')}
        className={cn(
          'absolute top-1/2 z-20 size-6 -translate-y-1/2 rounded-full',
          'border border-border-subtle bg-surface text-muted-foreground shadow-sm',
          'opacity-0 transition-opacity hover:text-foreground',
          'group-hover/sidebar:opacity-100 focus-visible:opacity-100',
          isRight ? '-left-3' : '-right-3'
        )}
      >
        <CollapseIcon className="size-3.5" />
      </Button>
    </aside>
  )
}

export default ResizableSidebar
