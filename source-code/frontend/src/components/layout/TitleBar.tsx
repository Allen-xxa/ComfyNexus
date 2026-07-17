/**
 * 自定义标题栏组件
 * 使用 pywebview-drag-region 类实现拖拽
 * 支持环境列表拖动排序
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { Minus, X, Maximize2, Minimize2, Play, Square, RotateCw, Plus, Maximize } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { bridgeService } from '@/services/bridge'
import { ThemeToggle } from '@/components/common/ThemeToggle'
import { LanguageToggle } from '@/components/common/LanguageToggle'
import { useProcessStore } from '@/stores/useProcessStore'
import { useEnvStore } from '@/stores/useEnvStore'
import { useEnvSwitchGuard } from '@/contexts/EnvSwitchGuardContext'
import { useToast } from '@/hooks/useToast'
import { DeleteConfirmDialog } from '@/components/env/DeleteConfirmDialog'
import { CloseConfirmDialog } from '@/components/common/CloseConfirmDialog'
import { EnvironmentHoverCard, EnvironmentDetailInfo } from '@/components/env/EnvironmentHoverCard'
import { useFullscreenStore } from '@/stores/useFullscreenStore'
import { useSettingsStore } from '@/stores/useSettingsStore'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/Button'
import { DndContext, closestCenter, KeyboardSensor, PointerSensor, useSensor, useSensors, DragEndEvent, Modifier } from '@dnd-kit/core'
import { SortableContext, sortableKeyboardCoordinates, horizontalListSortingStrategy, useSortable } from '@dnd-kit/sortable'

const restrictHorizontalMovement: Modifier = ({ transform, containerNodeRect, draggingNodeRect }) => {
  if (!draggingNodeRect || !containerNodeRect) {
    return transform
  }

  const containerLeft = containerNodeRect.left
  const containerRight = containerNodeRect.right
  const itemLeft = draggingNodeRect.left + transform.x
  const itemRight = draggingNodeRect.right + transform.x

  let clampedX = transform.x

  if (itemLeft < containerLeft) {
    clampedX = containerLeft - draggingNodeRect.left
  } else if (itemRight > containerRight) {
    clampedX = containerRight - draggingNodeRect.right
  }

  return {
    ...transform,
    x: clampedX,
    y: 0,
  }
}

function SortableEnvButton({ 
  env, 
  isActive, 
  titleBarHeight,
  fontScale,
  titleBarStyle,
  onSwitch,
  onDelete,
  onMouseEnter,
  onMouseLeave
}: { 
  env: { id: string; alias: string }
  isActive: boolean
  titleBarHeight: number
  fontScale: number
  titleBarStyle: 'normal' | 'enhanced'
  onSwitch: (envId: string) => void
  onDelete: (envId: string, alias: string, e: React.MouseEvent) => void
  onMouseEnter: (envId: string, e: React.MouseEvent<HTMLButtonElement>) => void
  onMouseLeave: () => void
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ 
    id: env.id,
    strategy: horizontalListSortingStrategy,
  })

  const style = {
    transform: transform 
      ? `translate3d(${transform.x}px, 0, 0)` 
      : undefined,
    transition,
    zIndex: isDragging ? 50 : undefined,
  }

  const iconSize = Math.round(12 * fontScale)
  const fontSize = `${Math.round(12 * fontScale)}px`
  
  const buttonHeight = titleBarStyle === 'enhanced' ? undefined : `${Math.round(28 * fontScale)}px`
  const buttonPadding = titleBarStyle === 'enhanced'
    ? `${Math.max(2, titleBarHeight * 0.1)}px`
    : '2px'

  return (
    <div 
      ref={setNodeRef} 
      style={style} 
      className={cn(
        "relative group pywebview-no-drag",
        isDragging && "z-50"
      )}
    >
      <Button
        {...attributes}
        {...listeners}
        onClick={() => onSwitch(env.id)}
        onMouseEnter={(e) => onMouseEnter(env.id, e)}
        onMouseLeave={onMouseLeave}
        variant={isActive ? "default" : "secondary"}
        className={cn(
          'gap-1 px-2 whitespace-nowrap cursor-grab active:cursor-grabbing',
          isDragging && 'shadow-lg opacity-90'
        )}
        style={{ 
          fontSize,
          height: buttonHeight,
          paddingTop: buttonPadding,
          paddingBottom: buttonPadding
        }}
        title={env.alias}
      >
        <span>{env.alias}</span>
        
        {/* 删除按钮 */}
        <X
          size={iconSize}
          className={cn(
            "ml-0.5 transition-colors",
            isActive 
              ? "hover:text-destructive/70" 
              : "hover:text-destructive"
          )}
          onClick={(e) => onDelete(env.id, env.alias, e)}
        />
      </Button>
    </div>
  )
}

export function TitleBar() {
  const { t } = useTranslation()
  const [isMaximized, setIsMaximized] = useState(false)
  const { isFullscreen, toggleFullscreen } = useFullscreenStore()
  const { status, isStarting, loadComfyUIStatus, setStarting, setRestarting, startComfyUI } = useProcessStore()
  const { 
    environments, 
    currentEnvId, 
    switchEnvironment,
    deleteEnvironment,
    createEnvironment,
    reorderEnvironments
  } = useEnvStore()
  const { checkBeforeSwitch } = useEnvSwitchGuard()
  const { success, error: showError } = useToast()
  const { systemSettings } = useSettingsStore()

  // 删除确认对话框状态
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null)
  const [deleteTargetAlias, setDeleteTargetAlias] = useState<string>('')

  // 关闭确认对话框状态
  const [showCloseConfirm, setShowCloseConfirm] = useState(false)

  // 悬停卡片状态
  const [hoveredEnvId, setHoveredEnvId] = useState<string | null>(null)
  const [hoverCardPosition, setHoverCardPosition] = useState<{ x: number; y: number } | undefined>(undefined)

  // 动态计算标题栏高度（考虑 DPI 缩放）
  const [titleBarHeight, setTitleBarHeight] = useState(40)

  // 从 store 获取标题栏样式
  const titleBarStyle = systemSettings.titleBarStyle || 'normal'
  
  // 计算缩放比例：增强模式标题栏高度 1.25 倍，按钮和字体 1.2 倍
  const heightScale = titleBarStyle === 'enhanced' ? 1.25 : 1
  const fontScale = titleBarStyle === 'enhanced' ? 1.2 : 1

  // 从 store 获取 ComfyUI 运行状态
  const isComfyUIRunning = status.isRunning
  
  // DnD sensors
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 5,
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  )

  // 初始化时计算标题栏高度
  useEffect(() => {
    const calculateHeight = () => {
      // 获取设备像素比（DPI 缩放比例）
      const dpr = window.devicePixelRatio || 1
      
      // 基准高度 40px，根据 DPI 缩放反向调整
      // 例如：150% DPI (dpr=1.5) → 40 / 1.5 ≈ 27px
      //      200% DPI (dpr=2.0) → 40 / 2.0 = 20px
      //      100% DPI (dpr=1.0) → 40 / 1.0 = 40px
      const baseHeight = 40
      const adjustedHeight = Math.max(24, Math.round(baseHeight / dpr))
      
      // 应用增强模式缩放
      const finalHeight = Math.round(adjustedHeight * heightScale)
      
      setTitleBarHeight(finalHeight)
      console.log(`DPI 缩放比例: ${dpr}, 标题栏高度: ${finalHeight}px, 增强模式: ${titleBarStyle}`)
    }

    calculateHeight()

    // 监听窗口缩放变化（用户可能会动态调整 DPI）
    window.addEventListener('resize', calculateHeight)
    return () => window.removeEventListener('resize', calculateHeight)
  }, [heightScale, titleBarStyle])

  // 检查最大化状态
  useEffect(() => {
    const checkMaximized = async () => {
      try {
        const maximized = await bridgeService.isMaximized()
        setIsMaximized(maximized)
      } catch (error) {
        console.error('Failed to check maximized status:', error)
      }
    }
    
    checkMaximized()
    
    // 监听最大化状态变化
    const interval = setInterval(checkMaximized, 1000)
    return () => clearInterval(interval)
  }, [])

  // 注册拖动错误 Toast 显示函数
  useEffect(() => {
    window.showDragErrorToast = () => {
      showError(t('titleBar.drag.error'))
    }
    
    return () => {
      delete window.showDragErrorToast
    }
  }, [showError, t])

  // ESC 键退出拖动
  useEffect(() => {
    const handleKeyDown = async (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        try {
          await bridgeService.forceReleaseMouse()
        } catch (err) {
          console.error('[ESC] 强制释放失败:', err)
        }
      }
    }
    
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [])

  const handleMinimize = async () => {
    try {
      await bridgeService.minimizeApp()
    } catch (error) {
      console.error('Failed to minimize:', error)
    }
  }

  const handleToggleMaximize = async () => {
    try {
      if (isFullscreen) {
        const result = await bridgeService.fullscreenToMaximize()
        if (result.success) {
          useFullscreenStore.getState().setFullscreen(false)
          setIsMaximized(true)
        } else {
          console.error('Failed to switch from fullscreen to maximize:', result.message)
        }
        return
      }
      
      await bridgeService.maximizeApp()
      setIsMaximized(!isMaximized)
    } catch (error) {
      console.error('Failed to toggle maximize:', error)
    }
  }

  const handleTitleBarDoubleClick = useCallback(async () => {
    const action = systemSettings.titleBarDoubleClickAction || 'maximize'
    if (action === 'fullscreen') {
      await handleToggleFullscreen()
    } else {
      await handleToggleMaximize()
    }
  }, [systemSettings.titleBarDoubleClickAction])

  const handleToggleFullscreen = async () => {
    try {
      await toggleFullscreen()
    } catch (error) {
      console.error('Failed to toggle fullscreen:', error)
    }
  }

  const isDragging = useRef(false)
  const dragOffset = useRef<{ x: number; y: number } | null>(null)

  const handleDragRegionMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button !== 0) return
    if (isFullscreen) return
    dragOffset.current = { x: e.clientX, y: e.clientY }
  }, [isFullscreen])

  useEffect(() => {
    const handleMouseMove = async (e: MouseEvent) => {
      if (!dragOffset.current) return
      if (isFullscreen) return
      
      if (!isDragging.current) {
        const dx = e.movementX
        const dy = e.movementY
        const distance = Math.sqrt(dx * dx + dy * dy)
        
        if (distance < 2) return
        
        try {
          const maximized = await bridgeService.isMaximized()
          if (maximized) {
            const result = await bridgeService.restoreWindowOnDrag()
            if (result.success && result.windowX !== undefined && result.windowY !== undefined) {
              const dpr = window.devicePixelRatio || 1
              dragOffset.current = {
                x: (e.screenX / dpr) - result.windowX,
                y: (e.screenY / dpr) - result.windowY
              }
              setIsMaximized(false)
            }
          }
          isDragging.current = true
        } catch (error) {
          console.error('Failed to restore window on drag:', error)
          return
        }
      }
      
      if (isDragging.current && dragOffset.current) {
        const dpr = window.devicePixelRatio || 1
        const newX = (e.screenX / dpr) - dragOffset.current.x
        const newY = (e.screenY / dpr) - dragOffset.current.y
        await bridgeService.moveWindowTo(newX, newY)
      }
    }
    
    const handleMouseUp = () => {
      dragOffset.current = null
      isDragging.current = false
    }
    
    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
    
    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }
  }, [isFullscreen])

  const handleClose = async () => {
    console.log('[TitleBar] handleClose called')
    try {
      const behavior = await bridgeService.getCloseBehavior()
      console.log('[TitleBar] getCloseBehavior result:', JSON.stringify(behavior))
      if (behavior.success && behavior.dontAskAgain && behavior.action) {
        console.log('[TitleBar] dontAskAgain mode, action:', behavior.action)
        if (behavior.action === 'minimize') {
          await bridgeService.minimizeToTray()
        } else {
          await bridgeService.closeApp()
        }
      } else {
        console.log('[TitleBar] showing confirm dialog, setShowCloseConfirm(true)')
        setShowCloseConfirm(true)
      }
    } catch (error) {
      console.error('[TitleBar] Failed to close:', error)
    }
  }

  // 注册全局关闭对话框函数，供后端 ALT+F4 拦截时调用
  useEffect(() => {
    window.triggerCloseDialog = handleClose
    
    return () => {
      delete (window as any).triggerCloseDialog
    }
  }, [handleClose])

  // 弹窗关闭时复位后端 ALT+F4 弹窗待处理标志（无论选择最小化、退出还是直接关闭弹窗）。
  // 退出程序路径由 closeApp 设置的 _app_exit_requested 放行，不受此复位影响。
  const handleCloseConfirmOpenChange = useCallback((open: boolean) => {
    setShowCloseConfirm(open)
    if (!open) {
      bridgeService.resetCloseDialogState().catch((error) => {
        console.error('[TitleBar] Failed to reset close dialog state:', error)
      })
    }
  }, [])

  const handleCloseConfirm = async (dontAskAgain: boolean) => {
    console.log('[TitleBar] handleCloseConfirm called, dontAskAgain:', dontAskAgain)
    try {
      if (dontAskAgain) {
        await bridgeService.setCloseBehavior('close', true)
      }
      console.log('[TitleBar] calling closeApp...')
      await bridgeService.closeApp()
      console.log('[TitleBar] closeApp returned')
    } catch (error) {
      console.error('[TitleBar] Failed to close app:', error)
    }
  }

  const handleMinimizeConfirm = async (dontAskAgain: boolean) => {
    try {
      if (dontAskAgain) {
        await bridgeService.setCloseBehavior('minimize', true)
      }
      await bridgeService.minimizeToTray()
    } catch (error) {
      console.error('Failed to minimize to tray:', error)
    }
  }

  // 处理启动/停止 ComfyUI
  const handleToggleComfyUI = useCallback(async () => {
    try {
      // 如果正在运行或正在启动，则停止
      if (isComfyUIRunning || isStarting) {
        // 停止 ComfyUI
        const result = await bridgeService.stopComfyUI()
        if (result.success) {
          success(t('titleBar.comfyui.stopped'))
          await loadComfyUIStatus()
          setStarting(false)
        } else {
          showError(result.error || t('titleBar.comfyui.stopFailed'))
        }
      } else {
        if (!currentEnvId) {
          showError(t('titleBar.comfyui.selectEnvFirst'))
          return
        }

        await startComfyUI()
      }
    } catch (error) {
      console.error('Failed to toggle ComfyUI:', error)
      showError(t('common.operationFailed'))
      setStarting(false)
    }
  }, [isComfyUIRunning, isStarting, currentEnvId, success, showError, setStarting, loadComfyUIStatus, startComfyUI, t])

  const handleRestartComfyUI = useCallback(async () => {
    try {
      // 立即显示重启中的提示
      success(t('titleBar.comfyui.restarting'))
      
      if (isComfyUIRunning) {
        const stopResult = await bridgeService.stopComfyUI()
        if (!stopResult.success) {
          showError(t('titleBar.comfyui.stopFailed'))
          return
        }
        
        await new Promise(resolve => setTimeout(resolve, 1000))
      }

      if (!currentEnvId) {
        showError(t('titleBar.comfyui.selectEnvFirst'))
        return
      }

      // 设置重启标记，用于启动成功后显示 toast
      setRestarting(true)
      await startComfyUI()
    } catch (error) {
      console.error('Failed to restart ComfyUI:', error)
      showError(t('titleBar.comfyui.restartFailed'))
      setStarting(false)
      setRestarting(false)
    }
  }, [isComfyUIRunning, currentEnvId, success, showError, setStarting, setRestarting, startComfyUI, t])

  // 处理环境切换
  const handleSwitch = useCallback(async (envId: string) => {
    if (envId !== currentEnvId) {
      try {
        const canSwitch = await checkBeforeSwitch(envId)
        if (canSwitch) {
          await switchEnvironment(envId)
        }
      } catch (error) {
        console.error('Failed to switch environment:', error)
      }
    }
  }, [currentEnvId, switchEnvironment, checkBeforeSwitch])

  // 处理删除按钮点击
  const handleDeleteClick = useCallback((envId: string, alias: string, e: React.MouseEvent) => {
    e.stopPropagation()
    setDeleteTargetId(envId)
    setDeleteTargetAlias(alias)
    setShowDeleteConfirm(true)
  }, [])

  // 处理删除确认
  const handleDeleteConfirm = useCallback(async () => {
    if (deleteTargetId) {
      try {
        await deleteEnvironment(deleteTargetId)
        setShowDeleteConfirm(false)
        setDeleteTargetId(null)
        setDeleteTargetAlias('')
        success(t('env.message.deleteSuccess'))
      } catch (error) {
        console.error('Failed to delete environment:', error)
        showError(t('env.message.deleteFailed'))
      }
    }
  }, [deleteTargetId, deleteEnvironment, t, success, showError])

  // 处理删除取消
  const handleDeleteCancel = useCallback(() => {
    setShowDeleteConfirm(false)
    setDeleteTargetId(null)
    setDeleteTargetAlias('')
  }, [])

  // 处理拖拽排序
  const handleDragEnd = useCallback(async (event: DragEndEvent) => {
    const { active, over } = event

    if (over && active.id !== over.id) {
      const envIds = environments.map(env => env.id)
      const activeIndex = envIds.indexOf(active.id as string)
      const overIndex = envIds.indexOf(over.id as string)
      
      if (activeIndex !== -1 && overIndex !== -1) {
        // 重新排列
        const newEnvIds = [...envIds]
        const [movedId] = newEnvIds.splice(activeIndex, 1)
        newEnvIds.splice(overIndex, 0, movedId)
        
        // 保存到后端
        try {
          await reorderEnvironments(newEnvIds)
        } catch (error) {
          console.error('Failed to reorder environments:', error)
          showError(t('titleBar.env.reorderFailed'))
        }
      }
    }
  }, [environments, reorderEnvironments, showError])

  // 处理添加环境
  const handleAddEnvironment = useCallback(async () => {
    try {
      let selectedPath: string | undefined

      if (window.pywebview?.api?.select_directory) {
        const response = await window.pywebview.api.select_directory()
        if (!response.success) {
          // 区分用户取消和真实错误
          // "No directory selected" 是用户主动取消，不需要提示
          if (response.error_message && response.error_message !== 'No directory selected') {
            showError(response.error_message)
          }
          return
        }
        if (!response.path) {
          return
        }
        selectedPath = response.path
        await new Promise(resolve => setTimeout(resolve, 300))
      } else {
        const path = prompt(t('titleBar.env.inputPathDev'), 'C:\\ComfyUI-New')
        if (!path) {
          return
        }
        selectedPath = path
      }

      await createEnvironment(selectedPath)
      success(t('env.message.createSuccess'))
    } catch (error) {
      console.error('Failed to create environment:', error)
      const errorMessage = error instanceof Error ? error.message : t('env.message.createFailed')
      showError(errorMessage)
    }
  }, [createEnvironment, t, success, showError])

  // 处理环境按钮鼠标悬停
  const handleEnvMouseEnter = useCallback((envId: string, event: React.MouseEvent<HTMLButtonElement>) => {
    const rect = event.currentTarget.getBoundingClientRect()
    setHoveredEnvId(envId)
    setHoverCardPosition({
      x: rect.left,
      y: rect.bottom
    })
  }, [])

  // 处理环境按钮鼠标离开
  const handleEnvMouseLeave = useCallback(() => {
    setHoveredEnvId(null)
    setHoverCardPosition(undefined)
  }, [])

  // 获取悬停环境的详细信息
  const getHoveredEnvInfo = useCallback((): EnvironmentDetailInfo | null => {
    if (!hoveredEnvId) return null
    
    const env = environments.find(e => e.id === hoveredEnvId)
    if (!env) return null

    return {
      path: env.general?.comfyuiPath || '',  // 使用完整路径
      alias: env.alias,
      version: env.version,
      envType: env.envType,
      commitHash: env.versionInfo?.commitHash,
      isDev: env.versionInfo?.isDev,
      lastUpdated: env.versionInfo?.lastUpdated,
      pythonVersion: env.dependencies?.pythonVersion,
      pytorchVersion: env.dependencies?.pytorchVersion,
      cudaVersion: env.dependencies?.cudaVersion,
    }
  }, [hoveredEnvId, environments])

  return (
    <>
      <div 
        className="relative z-10 flex select-none items-center justify-end border-b border-border bg-card px-2"
        style={{ height: `${titleBarHeight}px` }}
      >
        {/* 左侧：窗口拖动区域 */}
        <div 
          className={cn("h-full flex-1", (isFullscreen || isMaximized) ? "pywebview-no-drag" : "pywebview-drag-region")}
          onMouseDown={isMaximized ? handleDragRegionMouseDown : undefined}
          onDoubleClick={handleTitleBarDoubleClick}
        />
        
        {/* 环境列表区域 */}
        <div className="pywebview-no-drag flex items-center gap-1">
          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            onDragEnd={handleDragEnd}
            modifiers={[restrictHorizontalMovement]}
          >
            <SortableContext
              items={environments.map(env => env.id)}
              strategy={horizontalListSortingStrategy}
            >
              <div className="flex items-center gap-1">
                {environments.length > 0 ? (
                  <>
                    {environments.map((env) => (
                      <SortableEnvButton
                        key={env.id}
                        env={env}
                        isActive={env.id === currentEnvId}
                        titleBarHeight={titleBarHeight}
                        fontScale={fontScale}
                        titleBarStyle={titleBarStyle}
                        onSwitch={handleSwitch}
                        onDelete={handleDeleteClick}
                        onMouseEnter={handleEnvMouseEnter}
                        onMouseLeave={handleEnvMouseLeave}
                      />
                    ))}
                    
                    {/* 添加环境按钮 */}
                    <Button
                      onClick={handleAddEnvironment}
                      variant="ghost"
                      className="flex items-center gap-1 whitespace-nowrap px-2"
                      style={{ 
                        fontSize: `${Math.round(12 * fontScale)}px`,
                        height: titleBarStyle === 'enhanced' ? undefined : `${Math.round(28 * fontScale)}px`,
                        paddingTop: titleBarStyle === 'enhanced' ? `${Math.max(2, titleBarHeight * 0.1)}px` : '2px',
                        paddingBottom: titleBarStyle === 'enhanced' ? `${Math.max(2, titleBarHeight * 0.1)}px` : '2px'
                      }}
                      aria-label={t('titleBar.env.addEnv')}
                      title={t('titleBar.env.addEnv')}
                    >
                      <Plus size={Math.round(12 * fontScale)} />
                      <span>{t('common.add')}</span>
                    </Button>
                  </>
                ) : (
                  <Button
                    onClick={handleAddEnvironment}
                    className="flex items-center gap-1 whitespace-nowrap px-2"
                    style={{ 
                      fontSize: `${Math.round(12 * fontScale)}px`,
                      height: titleBarStyle === 'enhanced' ? undefined : `${Math.round(28 * fontScale)}px`,
                      paddingTop: titleBarStyle === 'enhanced' ? `${Math.max(2, titleBarHeight * 0.1)}px` : '2px',
                      paddingBottom: titleBarStyle === 'enhanced' ? `${Math.max(2, titleBarHeight * 0.1)}px` : '2px'
                    }}
                    aria-label={t('titleBar.env.addEnv')}
                    title={t('titleBar.env.addEnv')}
                  >
                    <Plus size={Math.round(12 * fontScale)} />
                    <span>{t('titleBar.env.addEnv')}</span>
                  </Button>
                )}
              </div>
            </SortableContext>
          </DndContext>
        </div>
        
        {/* 中间：窗口拖动区域 */}
        <div 
          className={cn((isFullscreen || isMaximized) ? "pywebview-no-drag" : "pywebview-drag-region")} 
          style={{ width: '8px', height: '100%' }}
          onMouseDown={isMaximized ? handleDragRegionMouseDown : undefined}
          onDoubleClick={handleTitleBarDoubleClick}
        />
        
        {/* 右侧：控制按钮区域 */}
        <div className="pywebview-no-drag flex items-center gap-1">
          {/* 重启按钮 */}
          <Button
            onClick={handleRestartComfyUI}
            disabled={!currentEnvId}
            variant="ghost"
            className={cn(
              "flex items-center justify-center rounded-md border shadow-sm",
              "border-warning/50 bg-warning/10 text-warning",
              "hover:bg-warning/20 hover:border-warning",
              !currentEnvId && "opacity-50"
            )}
            style={{ 
              width: titleBarStyle === 'enhanced' ? 'auto' : `${Math.round(28 * fontScale)}px`,
              height: `${Math.round(28 * fontScale)}px`,
              minWidth: `${Math.round(28 * fontScale)}px`,
              fontSize: `${Math.round(12 * fontScale)}px`,
              padding: titleBarStyle === 'enhanced' ? '0 8px' : 0,
              gap: titleBarStyle === 'enhanced' ? '4px' : 0
            }}
            title={t('titleBar.comfyui.restart')}
            aria-label={t('titleBar.comfyui.restart')}
          >
            <RotateCw size={Math.round(14 * fontScale)} className={isStarting ? 'animate-spin' : ''} />
            {titleBarStyle === 'enhanced' && <span>{t('titleBar.comfyui.restart')}</span>}
          </Button>

          {/* 启动/停止按钮 */}
          <Button
            onClick={handleToggleComfyUI}
            disabled={!currentEnvId}
            variant="ghost"
            className={cn(
              "flex items-center justify-center rounded-md border shadow-sm",
              !currentEnvId
                ? "opacity-50"
                : (isComfyUIRunning || isStarting)
                  ? "border-danger/50 bg-danger/10 text-danger hover:bg-danger/20 hover:border-danger"
                  : "border-success/50 bg-success/10 text-success hover:bg-success/20 hover:border-success"
            )}
            style={{ 
              width: titleBarStyle === 'enhanced' ? 'auto' : `${Math.round(28 * fontScale)}px`,
              height: `${Math.round(28 * fontScale)}px`,
              minWidth: `${Math.round(28 * fontScale)}px`,
              fontSize: `${Math.round(12 * fontScale)}px`,
              padding: titleBarStyle === 'enhanced' ? '0 8px' : 0,
              gap: titleBarStyle === 'enhanced' ? '4px' : 0
            }}
            title={(isComfyUIRunning || isStarting) ? t('titleBar.comfyui.stop') : t('titleBar.comfyui.start')}
            aria-label={(isComfyUIRunning || isStarting) ? t('titleBar.comfyui.stop') : t('titleBar.comfyui.start')}
          >
            {(isComfyUIRunning || isStarting) ? (
              <>
                <Square size={Math.round(14 * fontScale)} />
                {titleBarStyle === 'enhanced' && <span>{t('titleBar.comfyui.stop')}</span>}
              </>
            ) : (
              <>
                <Play size={Math.round(14 * fontScale)} />
                {titleBarStyle === 'enhanced' && <span>{t('titleBar.comfyui.start')}</span>}
              </>
            )}
          </Button>

          {/* 分隔线 */}
          <div className="mx-1 w-px bg-border" style={{ height: `${Math.round(16 * fontScale)}px` }} />

          <LanguageToggle />
          <ThemeToggle />
          
          {/* 分隔线 */}
          <div className="mx-1 w-px bg-border" style={{ height: `${Math.round(16 * fontScale)}px` }} />
          
          <Button
            onClick={handleMinimize}
            variant="ghost"
            size="icon"
            className="text-muted-foreground hover:text-foreground"
            style={{ 
              width: `${Math.max(28, titleBarHeight * 0.8)}px`,
              height: `${Math.max(28, titleBarHeight * 0.8)}px`
            }}
            aria-label={t('titleBar.window.minimize')}
            title={t('titleBar.window.minimize')}
          >
            <Minus size={Math.round(14 * fontScale)} />
          </Button>
          <Button
            onClick={handleToggleMaximize}
            variant="ghost"
            size="icon"
            className="text-muted-foreground hover:text-foreground"
            style={{ 
              width: `${Math.max(28, titleBarHeight * 0.8)}px`,
              height: `${Math.max(28, titleBarHeight * 0.8)}px`
            }}
            aria-label={isMaximized ? t('titleBar.window.restore') : t('titleBar.window.maximize')}
            title={isMaximized ? t('titleBar.window.restore') : t('titleBar.window.maximize')}
          >
            {isMaximized ? <Minimize2 size={Math.round(14 * fontScale)} /> : <Maximize2 size={Math.round(14 * fontScale)} />}
          </Button>
          <Button
            onClick={handleToggleFullscreen}
            variant="ghost"
            size="icon"
            className="text-muted-foreground hover:text-foreground"
            style={{ 
              width: `${Math.max(28, titleBarHeight * 0.8)}px`,
              height: `${Math.max(28, titleBarHeight * 0.8)}px`
            }}
            aria-label={isFullscreen ? t('titleBar.window.exitFullscreen') : t('titleBar.window.workspaceFullscreen')}
            title={isFullscreen ? t('titleBar.window.exitFullscreen') : t('titleBar.window.workspaceFullscreen')}
          >
            <Maximize size={Math.round(14 * fontScale)} />
          </Button>
          <Button
            onClick={handleClose}
            variant="ghost"
            size="icon"
            className="text-muted-foreground hover:bg-destructive hover:text-destructive-foreground"
            style={{ 
              width: `${Math.max(28, titleBarHeight * 0.8)}px`,
              height: `${Math.max(28, titleBarHeight * 0.8)}px`
            }}
            aria-label={t('titleBar.window.close')}
            title={t('titleBar.window.close')}
          >
            <X size={Math.round(14 * fontScale)} />
          </Button>
        </div>
      </div>

      {/* 删除确认对话框 */}
      {showDeleteConfirm && (
        <DeleteConfirmDialog
          alias={deleteTargetAlias}
          onConfirm={handleDeleteConfirm}
          onCancel={handleDeleteCancel}
        />
      )}

      {/* 关闭确认对话框 */}
      <CloseConfirmDialog
        open={showCloseConfirm}
        onOpenChange={handleCloseConfirmOpenChange}
        onClose={handleCloseConfirm}
        onMinimize={handleMinimizeConfirm}
      />

      {/* 环境悬停卡片 */}
      {hoveredEnvId && (
        <EnvironmentHoverCard
          info={getHoveredEnvInfo()!}
          isVisible={!!hoveredEnvId}
          position={hoverCardPosition}
        />
      )}
    </>
  )
}
