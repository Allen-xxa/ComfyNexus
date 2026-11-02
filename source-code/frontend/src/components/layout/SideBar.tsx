/**
 * 侧边栏组件 - 支持拖拽排序和收缩展开
 * 设计风格：渐变背景、悬浮滚动条、按压反馈、气泡提示
 * 支持深浅色主题切换
 */

import { useState, useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useLocation } from 'react-router-dom'
import * as Icons from 'lucide-react'
import { ChevronLeft, ChevronRight, X, ExternalLink, Copy, Github } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/Button'
import { Popover, PopoverTrigger, PopoverContent } from '@/components/ui/popover'
import { MODULE_REGISTRY, ModuleMetadata } from '@/types/module'
import { useModuleConfigStore } from '@/stores/useModuleConfigStore'
import { useNavigationGuard } from '@/contexts/NavigationGuardContext'
import { usePluginUpdateBadgeStore } from '@/stores/usePluginUpdateBadgeStore'
import { useAppUpdateStore } from '@/stores/useAppUpdateStore'
import { useEnvStore } from '@/stores/useEnvStore'
import { useProcessStore } from '@/stores/useProcessStore'
import { bridgeService } from '@/services/bridge'

import { useToast } from '@/hooks/useToast'
import { DndContext, closestCenter, KeyboardSensor, PointerSensor, useSensor, useSensors, DragEndEvent } from '@dnd-kit/core'
import { restrictToVerticalAxis, restrictToParentElement } from '@dnd-kit/modifiers'
import { SortableContext, sortableKeyboardCoordinates, verticalListSortingStrategy, useSortable } from '@dnd-kit/sortable'

const FIXED_MODULE_IDS = ['home', 'workspace', 'terminal']
const FOOTER_MODULE_IDS = ['env-manage', 'system-settings', 'about']

function SortableMenuItem({ 
  module, 
  isActive, 
  isCollapsed,
  updateCount,
  hasViewed,
  badgeEnabled,
  appHasUpdate,
  appHasViewed,
  onNavigate,
  showTooltip,
  hideTooltip
}: { 
  module: ModuleMetadata
  isActive: boolean
  isCollapsed: boolean
  updateCount: number
  hasViewed: boolean
  badgeEnabled: boolean
  appHasUpdate: boolean
  appHasViewed: boolean
  onNavigate: (path: string, moduleId: string) => void
  showTooltip: (text: string, y: number) => void
  hideTooltip: () => void
}) {
  const { t } = useTranslation()
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: module.id })

  const style = {
    transform: transform 
      ? `translate3d(0, ${transform.y}px, 0)` 
      : undefined,
    transition: isDragging ? 'none' : transition,
    zIndex: isDragging ? 50 : undefined,
  }

  const Icon = (Icons as unknown as Record<string, React.ComponentType<{ className?: string }>>)[module.icon] || Icons.Circle

  const shouldShowPluginBadge = badgeEnabled && module.id === 'plugin-manage' && updateCount > 0 && !hasViewed
  const shouldShowAppUpdateBadge = module.id === 'about' && appHasUpdate && !appHasViewed

  const moduleName = t(`nav.${module.id}`)
  
  const handleMouseEnter = (e: React.MouseEvent) => {
    if (isCollapsed) {
      const rect = e.currentTarget.getBoundingClientRect()
      showTooltip(moduleName, rect.top + rect.height / 2)
    }
  }

  return (
    <div 
      ref={setNodeRef} 
      style={style}
      {...attributes}
      {...listeners}
      className={cn(
        "relative group transition-all duration-200",
        isDragging && "z-50 opacity-50 scale-95"
      )}
    >
      <a
        onClick={() => onNavigate(module.path, module.id)}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={hideTooltip}
        className={cn(
          "flex items-center gap-3 px-3 py-2.5 rounded-lg cursor-pointer",
          "text-sm font-medium transition-all duration-200",
          "hover:bg-muted",
          "hover:text-foreground hover:translate-x-1",
          "active:scale-[0.96]",
          isCollapsed ? "w-11 h-11 justify-center !p-0 !gap-0 mx-auto hover:!translate-y-[-2px] hover:!translate-x-0" : "pr-4",
          isActive 
            ? "bg-surface-hover text-content-primary font-semibold" 
            : "text-muted-foreground",
          isDragging && "ring-2 ring-primary shadow-lg shadow-primary/30 bg-primary/10"
        )}
      >
        {isActive && (
          <div className="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-primary" />
        )}
        <div className="relative shrink-0">
          <Icon className={cn(
            "w-[18px] h-[18px] transition-transform duration-200",
            isActive && "scale-110"
          )} />
          
          {shouldShowPluginBadge && isCollapsed && (
            <span className="animate-in fade-in zoom-in-95 absolute -right-1 -top-1 flex size-4 items-center justify-center rounded-full border-2 border-background bg-destructive text-[10px] font-semibold text-destructive-foreground shadow-sm">
              {updateCount}
            </span>
          )}
          
          {shouldShowAppUpdateBadge && isCollapsed && (
            <span className="animate-in fade-in zoom-in-95 absolute -right-1 -top-1 flex size-2.5 items-center justify-center rounded-full border-2 border-background bg-success shadow-sm" />
          )}
        </div>
        
        {!isCollapsed && (
          <>
            <span className="flex-1 truncate">{moduleName}</span>
            
            {shouldShowPluginBadge && (
              <span className="animate-in fade-in zoom-in-95 ml-auto flex min-w-[20px] items-center justify-center rounded-full bg-destructive px-2 py-0.5 text-xs font-semibold text-destructive-foreground shadow-sm">
                {updateCount}
              </span>
            )}
            
            {shouldShowAppUpdateBadge && (
              <span className="animate-in fade-in zoom-in-95 ml-auto flex items-center justify-center rounded-full bg-success px-2 py-0.5 text-xs font-medium text-primary-foreground shadow-sm">
                {t('sidebar.newVersion')}
              </span>
            )}
          </>
        )}
      </a>
    </div>
  )
}

function MenuItem({ 
  module, 
  isActive, 
  isCollapsed,
  appHasUpdate,
  appHasViewed,
  onNavigate,
  showTooltip,
  hideTooltip,
  showCloseButton,
  onClose
}: { 
  module: ModuleMetadata
  isActive: boolean
  isCollapsed: boolean
  appHasUpdate?: boolean
  appHasViewed?: boolean
  onNavigate: (path: string, moduleId: string) => void
  showTooltip: (text: string, y: number) => void
  hideTooltip: () => void
  showCloseButton?: boolean
  onClose?: () => void
}) {
  const { t } = useTranslation()
  const Icon = (Icons as unknown as Record<string, React.ComponentType<{ className?: string }>>)[module.icon] || Icons.Circle
  const moduleName = t(`nav.${module.id}`)
  
  const shouldShowAppUpdateBadge = module.id === 'about' && appHasUpdate && !appHasViewed

  const handleMouseEnter = (e: React.MouseEvent) => {
    if (isCollapsed) {
      const rect = e.currentTarget.getBoundingClientRect()
      showTooltip(moduleName, rect.top + rect.height / 2)
    }
  }

  return (
    <div className="group relative">
      <a
        onClick={() => onNavigate(module.path, module.id)}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={hideTooltip}
        className={cn(
          "flex items-center gap-3 px-3 py-2.5 rounded-lg cursor-pointer",
          "text-sm font-medium transition-all duration-200",
          "hover:bg-muted",
          "hover:text-foreground hover:translate-x-1",
          "active:scale-[0.96]",
          isCollapsed ? "w-11 h-11 justify-center !p-0 !gap-0 mx-auto hover:!translate-y-[-2px] hover:!translate-x-0" : "",
          isActive 
            ? "bg-surface-hover text-content-primary font-semibold" 
            : "text-muted-foreground"
        )}
      >
        {isActive && (
          <div className="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-primary" />
        )}
        <div className="relative shrink-0">
          <Icon className={cn(
            "w-[18px] h-[18px] transition-transform duration-200",
            isActive && "scale-110"
          )} />
          
          {shouldShowAppUpdateBadge && isCollapsed && (
            <span className="animate-in fade-in zoom-in-95 absolute -right-1 -top-1 flex size-2.5 items-center justify-center rounded-full border-2 border-background bg-success shadow-sm" />
          )}
        </div>
        
        {!isCollapsed && (
          <>
            <span className="flex-1 truncate">{moduleName}</span>
            
            {shouldShowAppUpdateBadge && (
              <span className="animate-in fade-in zoom-in-95 ml-auto flex items-center justify-center rounded-full bg-success px-2 py-0.5 text-xs font-medium text-primary-foreground shadow-sm">
                {t('sidebar.newVersion')}
              </span>
            )}
          </>
        )}
      </a>
      
      {/* 关闭工作台按钮 - 幽灵按钮样式，默认隐藏，悬停显示 */}
      {showCloseButton && !isCollapsed && (
        <Button
          onClick={(e) => {
            e.stopPropagation()
            onClose?.()
          }}
          variant="ghost"
          size="icon"
          className="absolute right-1 top-1/2 z-10 size-6 -translate-y-1/2 rounded-md text-muted-foreground opacity-0 transition-opacity duration-200 hover:bg-muted hover:text-foreground group-hover:opacity-100"
          title={t('workspace.closeWorkspace')}
        >
          <X className="size-4" />
        </Button>
      )}
    </div>
  )
}

export function SideBar() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const location = useLocation()
  const { success } = useToast()
  const [githubPopoverOpen, setGithubPopoverOpen] = useState(false)
  const { isModuleEnabled, modules, reorderModules, saveConfig } = useModuleConfigStore()
  const { currentEnvId } = useEnvStore()
  const markAsViewed = usePluginUpdateBadgeStore(state => state.markAsViewed)
  const badgeEnabled = usePluginUpdateBadgeStore(state => state.badgeEnabled)
  const badgeState = usePluginUpdateBadgeStore(state => state.badgeStates[currentEnvId || '__global__'])
  const updateCount = badgeState?.updateCount ?? 0
  const hasViewed = badgeState?.hasViewed ?? false
  const { hasUpdate: appHasUpdate, hasViewed: appHasViewed, markAsViewed: markAppUpdateAsViewed } = useAppUpdateStore()
  const { showWorkspaceIframe, setShowWorkspaceIframe } = useProcessStore()
  const [isCollapsed, setIsCollapsed] = useState(false)
  const [appVersion, setAppVersion] = useState('')
  const [tooltipText, setTooltipText] = useState('')
  const [tooltipY, setTooltipY] = useState(-999)
  const [tooltipVisible, setTooltipVisible] = useState(false)
  const tooltipTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  
  useEffect(() => {
    bridgeService.getAppVersion()
      .then(version => setAppVersion(version.trim()))
      .catch(() => setAppVersion(''))
  }, [])
  
  let canNavigate: (path: string) => boolean
  try {
    const guard = useNavigationGuard()
    canNavigate = guard.canNavigate
  } catch {
    canNavigate = () => true
  }
  
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        delay: 500,
        tolerance: 8,
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  )

  const enabledModules = Object.values(MODULE_REGISTRY)
    .filter(module => isModuleEnabled(module.id))
    .sort((a, b) => {
      const orderA = modules[a.id]?.order ?? a.order
      const orderB = modules[b.id]?.order ?? b.order
      return orderA - orderB
    })

  const fixedModules = enabledModules.filter(m => FIXED_MODULE_IDS.includes(m.id))
  const scrollableModules = enabledModules.filter(m => !FIXED_MODULE_IDS.includes(m.id) && !FOOTER_MODULE_IDS.includes(m.id))
  const footerModules = enabledModules.filter(m => FOOTER_MODULE_IDS.includes(m.id))

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event

    if (over && active.id !== over.id) {
      reorderModules(active.id as string, over.id as string)
      await saveConfig()
    }
  }

  const handleNavigate = (path: string, moduleId: string) => {
    if (moduleId === 'plugin-manage') {
      markAsViewed(currentEnvId)
    }
    
    if (moduleId === 'about') {
      markAppUpdateAsViewed()
    }
    
    if (canNavigate(path)) {
      navigate(path)
    }
  }

  const showTooltip = (text: string, y: number) => {
    if (tooltipTimeoutRef.current) {
      clearTimeout(tooltipTimeoutRef.current)
    }
    tooltipTimeoutRef.current = setTimeout(() => {
      setTooltipText(text)
      setTooltipY(y)
      setTooltipVisible(true)
    }, 150)
  }

  const hideTooltip = () => {
    if (tooltipTimeoutRef.current) {
      clearTimeout(tooltipTimeoutRef.current)
    }
    setTooltipVisible(false)
  }

  useEffect(() => {
    if (!isCollapsed) {
      hideTooltip()
    }
  }, [isCollapsed])

  return (
    <>
      <aside 
        className={cn(
          "shrink-0 flex flex-col relative z-10 overflow-hidden",
          "bg-card",
          "border-r border-border",
          "transition-all duration-300 ease-[cubic-bezier(0.25,0.8,0.25,1)]",
          isCollapsed ? "w-[68px]" : "w-[200px]"
        )}
      >
        <div 
          className={cn(
            "shrink-0 flex items-center gap-3 select-none pywebview-drag-region",
            "transition-all duration-300",
            isCollapsed ? "justify-center px-0 pt-6 pb-4 gap-0" : "justify-start px-[15px] pt-6 pb-4"
          )}
        >
          <div className="size-8 shrink-0 overflow-hidden rounded-lg">
            <img 
              src="/app-icon.png" 
              alt="ComfyNexus" 
              className="size-full object-cover"
            />
          </div>
          
          <div className={cn(
            "flex flex-col overflow-hidden transition-all duration-300",
            isCollapsed ? "max-w-0 opacity-0" : "max-w-[120px] opacity-100"
          )}>
            <span className="text-base font-bold tracking-wide text-foreground">ComfyNexus</span>
            <div className="mt-0.5 flex items-center gap-1.5">
              {appVersion && (
                <span className="text-[11px] font-medium text-muted-foreground opacity-70">{appVersion}</span>
              )}
              <Popover open={githubPopoverOpen} onOpenChange={setGithubPopoverOpen}>
                <PopoverTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="size-5 rounded p-0.5 transition-all hover:bg-accent"
                    title="GitHub"
                  >
                    <Github className="size-3.5" />
                  </Button>
                </PopoverTrigger>
                <PopoverContent align="start" side="bottom" className="min-w-[160px] p-1">
                  <button
                    type="button"
                    onClick={() => {
                      window.open('https://github.com/Allen-xxa/ComfyNexus', '_blank', 'noopener,noreferrer')
                      setGithubPopoverOpen(false)
                    }}
                    className="flex w-full items-center gap-2 rounded px-3 py-2 text-sm hover:bg-surface-active"
                  >
                    <ExternalLink className="size-4" />
                    {t('sidebar.visitGithub')}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      navigator.clipboard.writeText('https://github.com/Allen-xxa/ComfyNexus')
                      success(t('sidebar.linkCopied'))
                      setGithubPopoverOpen(false)
                    }}
                    className="flex w-full items-center gap-2 rounded px-3 py-2 text-sm hover:bg-surface-active"
                  >
                    <Copy className="size-4" />
                    {t('sidebar.copyLink')}
                  </button>
                </PopoverContent>
              </Popover>
            </div>
          </div>
        </div>

        <div className={cn(
          "shrink-0 relative flex flex-col gap-1 transition-all duration-300",
          isCollapsed ? "px-0 items-center pt-2.5" : "px-3 pt-2.5"
        )}>
          {fixedModules.map((module) => (
            <MenuItem
              key={module.id}
              module={module}
              isActive={location.pathname === module.path}
              isCollapsed={isCollapsed}
              onNavigate={handleNavigate}
              showTooltip={showTooltip}
              hideTooltip={hideTooltip}
              showCloseButton={module.id === 'workspace' && showWorkspaceIframe}
              onClose={() => setShowWorkspaceIframe(false)}
            />
          ))}
          
          <Button
            onClick={() => setIsCollapsed(!isCollapsed)}
            variant="outline"
            size="icon"
            className="absolute right-0 top-[calc(50%+60px)] h-11 w-[22px] -translate-y-1/2 rounded-l-lg rounded-r-none border-r-0 p-0 text-muted-foreground shadow-md hover:w-[26px] hover:text-foreground"
            title={isCollapsed ? t('sidebar.expand') : t('sidebar.collapse')}
          >
            {isCollapsed ? (
              <ChevronRight className="size-4 transition-transform duration-300" />
            ) : (
              <ChevronLeft className="size-4 transition-transform duration-300" />
            )}
          </Button>
        </div>

        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragEnd={handleDragEnd}
          modifiers={[restrictToVerticalAxis, restrictToParentElement]}
        >
          <SortableContext
            items={scrollableModules.map(m => m.id)}
            strategy={verticalListSortingStrategy}
          >
            <nav 
              className={cn(
                "flex-1 flex flex-col gap-1 overflow-y-auto py-4",
                "[&::-webkit-scrollbar]:w-1",
                "[&::-webkit-scrollbar-track]:bg-transparent",
                "[&::-webkit-scrollbar-thumb]:bg-transparent [&::-webkit-scrollbar-thumb]:rounded",
                "hover:[&::-webkit-scrollbar-thumb]:bg-muted-foreground/30",
                "[&::-webkit-scrollbar-thumb:hover]:bg-muted-foreground/50",
                "transition-all duration-300",
                isCollapsed ? "px-0 items-center" : "px-3"
              )}
            >
              {scrollableModules.map((module) => (
                <SortableMenuItem
                  key={module.id}
                  module={module}
                  isActive={location.pathname === module.path}
                  isCollapsed={isCollapsed}
                  updateCount={updateCount}
                  hasViewed={hasViewed}
                  badgeEnabled={badgeEnabled}
                  appHasUpdate={appHasUpdate}
                  appHasViewed={appHasViewed}
                  onNavigate={handleNavigate}
                  showTooltip={showTooltip}
                  hideTooltip={hideTooltip}
                />
              ))}
            </nav>
          </SortableContext>
        </DndContext>

        <div className={cn(
          "shrink-0",
          "border-t border-border",
          "bg-muted/50",
          "flex flex-col gap-1 transition-all duration-300",
          isCollapsed ? "px-0 items-center py-4" : "px-3 py-4"
        )}>
          {footerModules.map((module) => (
            <MenuItem
              key={module.id}
              module={module}
              isActive={location.pathname === module.path}
              isCollapsed={isCollapsed}
              appHasUpdate={appHasUpdate}
              appHasViewed={appHasViewed}
              onNavigate={handleNavigate}
              showTooltip={showTooltip}
              hideTooltip={hideTooltip}
            />
          ))}
        </div>
      </aside>

      <div 
        className={cn(
          "fixed left-[78px] z-[9999]",
          "bg-card",
          "text-foreground",
          "text-[13px] font-medium",
          "px-3 py-1.5 rounded-md",
          "pointer-events-none",
          "shadow-lg border border-border",
          "whitespace-nowrap tracking-wide",
          "transition-all duration-200 ease-[cubic-bezier(0.25,0.8,0.25,1)]",
          tooltipVisible 
            ? "opacity-100 visible translate-x-0" 
            : "opacity-0 invisible -translate-x-2"
        )}
        style={{ top: tooltipY, transform: `translateY(-50%) ${tooltipVisible ? 'translateX(0)' : 'translateX(-6px)'}` }}
      >
        {tooltipText}
        <div 
          className="absolute -left-1 top-1/2 -translate-y-1/2"
          style={{
            border: '4px solid transparent',
            borderRightColor: 'hsl(var(--background))'
          }}
        />
      </div>
    </>
  )
}
