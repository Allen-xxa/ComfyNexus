/**
 * 可拖拽宽度的侧边栏外壳
 *
 * 分类树/文件夹树统一使用：右缘拖拽调宽、双击复位、折叠成窄条。
 * 宽度和折叠状态写入 localStorage，刷新后保持。
 */

import { useCallback, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { PanelLeftClose, PanelLeftOpen } from 'lucide-react'
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
  className
}: ResizableSidebarProps) {
  const { t } = useTranslation()

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

      const handleMove = (moveEvent: PointerEvent) => {
        const drag = dragRef.current
        if (!drag) return
        setWidth(clampWidth(drag.startWidth + moveEvent.clientX - drag.startX, minWidth, maxWidth))
      }

      const handleUp = (upEvent: PointerEvent) => {
        window.removeEventListener('pointermove', handleMove)
        window.removeEventListener('pointerup', handleUp)
        const drag = dragRef.current
        dragRef.current = null
        if (drag) {
          persistWidth(drag.startWidth + upEvent.clientX - drag.startX)
        }
      }

      window.addEventListener('pointermove', handleMove)
      window.addEventListener('pointerup', handleUp)
    },
    [maxWidth, minWidth, persistWidth, width]
  )

  if (collapsed) {
    return (
      <aside
        className={cn(
          'flex w-10 shrink-0 flex-col items-center border-r border-border-subtle bg-surface py-2',
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
          <PanelLeftOpen className="size-4" />
        </Button>
      </aside>
    )
  }

  return (
    <aside
      className={cn(
        'group/sidebar relative flex shrink-0 flex-col border-r border-border-subtle bg-surface',
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
          'absolute -right-1 top-0 z-10 h-full w-2 cursor-col-resize',
          'after:absolute after:right-0.5 after:top-0 after:h-full after:w-px after:bg-transparent',
          'hover:after:bg-primary/40 active:after:bg-primary'
        )}
      />

      <Button
        variant="ghost"
        size="icon"
        onClick={toggleCollapsed}
        title={t('common.sidebar.collapse')}
        className={cn(
          'absolute -right-3 top-1/2 z-20 size-6 -translate-y-1/2 rounded-full',
          'border border-border-subtle bg-surface text-muted-foreground shadow-sm',
          'opacity-0 transition-opacity hover:text-foreground',
          'group-hover/sidebar:opacity-100 focus-visible:opacity-100'
        )}
      >
        <PanelLeftClose className="size-3.5" />
      </Button>
    </aside>
  )
}

export default ResizableSidebar
