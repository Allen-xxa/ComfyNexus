/**
 * 主布局组件
 */

import { Suspense, useEffect, useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { TitleBar } from './TitleBar'
import { SideBar } from './SideBar'
import { ResizeHandles } from './ResizeHandles'
import { Loading } from '@/components/ui'
import { ProcessConflictDialog } from '@/components/process/ProcessConflictDialog'
import { WorkspaceFrame } from '@/components/workspace/WorkspaceFrame'
import { useProcessStore } from '@/stores/useProcessStore'
import { useFullscreenStore } from '@/stores/useFullscreenStore'
import { useChromeStore } from '@/stores/useChromeStore'

export function MainLayout() {
  const { t } = useTranslation()
  const location = useLocation()
  const isWorkspacePage = location.pathname === '/workspace'
  const { isFullscreen, syncFullscreenState } = useFullscreenStore()
  const navHidden = useChromeStore((state) => state.hidden.nav)
  const hideAllChrome = useChromeStore((state) => state.hideAll)
  const showAllChrome = useChromeStore((state) => state.showAll)
  
  // 全屏时标题栏是否显示（鼠标悬停时显示）
  const [showTitleBarInFullscreen, setShowTitleBarInFullscreen] = useState(false)
  
  // 从 useProcessStore 获取冲突检测相关状态和方法
  const {
    comfyUIStatus,
    showConflictDialog,
    conflictProcesses,
    hasPortConflict,
    targetPort,
    handleKillProcesses,
    handleContinue,
    handleCancel,
    loading,
    showWorkspaceIframe,
  } = useProcessStore()

  // 构建 ComfyUI URL
  // 新架构：直接加载 ComfyUI，不再使用反向代理
  // - ComfyUI 已启用 CORS，支持跨域请求
  // - 通过桥接插件（ComfyNexus_Bridge）实现与主窗口的通信
  // - WebSocket 直接连接到 ComfyUI
  // 只有端口可用且用户点击了启动工作台按钮时才显示 iframe
  const isPortAvailable = comfyUIStatus?.portAvailable ?? false
  const comfyUIUrl = isPortAvailable && showWorkspaceIframe
    ? (comfyUIStatus?.url || `http://127.0.0.1:${comfyUIStatus?.port || 8188}`)
    : null

  // 初始化时同步一次全屏状态，之后定期同步（但不会覆盖正在切换的状态）
  useEffect(() => {
    syncFullscreenState()
    const interval = setInterval(syncFullscreenState, 2000) // 改为2秒检查一次，减少频率
    return () => clearInterval(interval)
  }, [syncFullscreenState])

  // 全屏时重置标题栏显示状态
  useEffect(() => {
    if (!isFullscreen) {
      setShowTitleBarInFullscreen(false)
    }
  }, [isFullscreen])

  // 窗体全屏 = 收起影院的三块界面构件；退出全屏再放回
  useEffect(() => {
    if (isFullscreen) {
      hideAllChrome()
    } else {
      showAllChrome()
    }
  }, [isFullscreen, hideAllChrome, showAllChrome])

  // 决定是否显示标题栏
  const shouldShowTitleBar = !isFullscreen || showTitleBarInFullscreen

  return (
    <div className="flex h-screen bg-background">
      {/* 窗口大小调整手柄 */}
      <ResizeHandles />
      
      {/* 全屏时的顶部触发区域 - 用于捕获鼠标移动（覆盖在 iframe 之上） */}
      {isFullscreen && (
        <div
          className="pointer-events-auto fixed inset-x-0 top-0 z-40 h-[10px]"
          onMouseEnter={() => setShowTitleBarInFullscreen(true)}
          onMouseLeave={() => {
            setShowTitleBarInFullscreen(false)
          }}
        />
      )}

      {/* 侧边栏 - 由影院模式的界面构件开关控制，全屏时默认收起 */}
      {!navHidden && <SideBar />}

      {/* 右侧区域：标题栏 + 内容 */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* 自定义标题栏 - 只在右侧区域 */}
        <div
          className={`
            shrink-0 transition-transform duration-300 ease-in-out
            ${isFullscreen ? 'absolute inset-x-0 top-0 z-50' : ''}
            ${isFullscreen && !showTitleBarInFullscreen ? '-translate-y-full' : 'translate-y-0'}
          `}
          onMouseEnter={() => {
            if (isFullscreen) {
              setShowTitleBarInFullscreen(true)
            }
          }}
          onMouseLeave={() => {
            if (isFullscreen) {
              setShowTitleBarInFullscreen(false)
            }
          }}
        >
          {shouldShowTitleBar && <TitleBar />}
        </div>

        {/* 页面内容 */}
        <main className="relative flex-1 overflow-y-auto overflow-x-hidden bg-background">
          {/* 全局 WorkspaceFrame - ComfyUI 可用时始终存在，通过 CSS 控制显示 */}
          {/* 使用 visibility 而非 display，避免 iframe 隐藏时尺寸变为 0 导致 LiteGraph 节点位置错乱 */}
          {comfyUIUrl && (
            <div 
              className="absolute inset-0 z-10"
              style={{ 
                visibility: isWorkspacePage ? 'visible' : 'hidden',
                pointerEvents: isWorkspacePage ? 'auto' : 'none'
              }}
            >
              <WorkspaceFrame url={comfyUIUrl} />
            </div>
          )}
          
          {/* 页面内容 - 在工作台页面且 iframe 显示时隐藏 */}
          <div 
            className="h-full"
            style={{ 
              display: (isWorkspacePage && comfyUIUrl) ? 'none' : 'block' 
            }}
          >
            <Suspense fallback={
              <div className="flex h-full items-center justify-center">
                <Loading size="lg" text={t('common.loading')} />
              </div>
            }>
              <Outlet />
            </Suspense>
          </div>
        </main>
      </div>

      {/* 进程冲突对话框 */}
      <ProcessConflictDialog
        open={showConflictDialog}
        processes={conflictProcesses}
        hasPortConflict={hasPortConflict}
        targetPort={targetPort}
        onKillProcesses={handleKillProcesses}
        onContinue={handleContinue}
        onCancel={handleCancel}
        loading={loading}
      />
    </div>
  )
}
