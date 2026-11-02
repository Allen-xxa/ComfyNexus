/**
 * 插件市场主容器组件
 * 
 * 功能：
 * - 选项卡切换（插件库）
 * - 顶部功能区（手动刷新按钮、自动安装依赖开关）
 * - 安装流程协调
 * - 错误处理
 * 
 * 采用 Glassmorphism 风格
 */

import React, { useState, useEffect, useCallback, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { AlertCircle, ArrowUpDown, RefreshCw, ShoppingCart } from 'lucide-react'
import { PluginLibraryTab } from './PluginLibraryTab'
import { InstallProgressModal } from './InstallProgressModal'
import { Plugin, PluginMarketplaceState, SortMode } from '@/types/plugin-marketplace'
import { useSettingsStore } from '@/stores/useSettingsStore'
import { eventBus, EVENTS } from '@/utils/eventBus'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/Button'
import { Switch } from '@/components/ui/Switch'

export const PluginMarketplace: React.FC = () => {
  const { t } = useTranslation()
  const { systemSettings, updateSystemSettings } = useSettingsStore()
  
  const [state, setState] = useState<PluginMarketplaceState>({
    activeTab: 'library',
    autoInstallDeps: systemSettings.autoInstallDeps,
    isRefreshing: false,
    installingPluginName: null,
    currentTaskId: null,
    showProgressModal: false
  })

  const [sortMode, setSortMode] = useState<SortMode>('default')

  const sortModeLabels: Record<SortMode, string> = {
    default: t('plugin.marketplace.sortDefault'),
    stars: t('plugin.marketplace.sortStars'),
    updated: t('plugin.marketplace.sortUpdated')
  }

  const [currentPlugin, setCurrentPlugin] = useState<Plugin | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showConfirmDialog, setShowConfirmDialog] = useState<boolean>(false)

  const pluginLibraryTabRef = useRef<{ 
    refresh: () => Promise<void>
    updateInstallationStatus: () => void
  } | null>(null)

  useEffect(() => {
    setState(prev => ({
      ...prev,
      autoInstallDeps: systemSettings.autoInstallDeps
    }))
  }, [systemSettings.autoInstallDeps])

  const handleRefresh = useCallback(async () => {
    setState(prev => ({ ...prev, isRefreshing: true }))
    
    try {
      // 手动刷新走真实网络请求，完成后才收起转圈
      await pluginLibraryTabRef.current?.refresh()
    } finally {
      setState(prev => ({ ...prev, isRefreshing: false }))
    }
  }, [])

  const handleSortCycle = useCallback(() => {
    setSortMode(prev => {
      const cycle: SortMode[] = ['default', 'stars', 'updated']
      const idx = cycle.indexOf(prev)
      return cycle[(idx + 1) % cycle.length]
    })
  }, [])

  const handleAutoInstallDepsChange = useCallback((checked: boolean) => {
    if (!checked) {
      setShowConfirmDialog(true)
      return
    }
    
    setState(prev => ({ ...prev, autoInstallDeps: checked }))
    updateSystemSettings({ autoInstallDeps: checked })
  }, [updateSystemSettings])
  
  const handleConfirmDisableAutoInstall = useCallback(() => {
    setState(prev => ({ ...prev, autoInstallDeps: false }))
    updateSystemSettings({ autoInstallDeps: false })
    setShowConfirmDialog(false)
  }, [updateSystemSettings])
  
  const handleCancelDisableAutoInstall = useCallback(() => {
    setShowConfirmDialog(false)
  }, [])

  const handleInstallStart = useCallback((plugin: Plugin) => {
    if (state.installingPluginName !== null) {
      setError(t('plugin.installingOther'))
      return
    }

    setCurrentPlugin(plugin)
    setState(prev => ({
      ...prev,
      installingPluginName: plugin.name,
      showProgressModal: true
    }))
    setError(null)
  }, [state.installingPluginName])

  const handleInstallComplete = useCallback((_success: boolean) => {
  }, [])

  const handleCloseProgressModal = useCallback(() => {
    setState(prev => ({
      ...prev,
      installingPluginName: null,
      currentTaskId: null,
      showProgressModal: false
    }))

    setCurrentPlugin(null)
    pluginLibraryTabRef.current?.updateInstallationStatus?.()
    eventBus.emit(EVENTS.PLUGIN_INSTALLED)
  }, [])

  useEffect(() => {
    if (error) {
      const timer = setTimeout(() => setError(null), 5000)
      return () => clearTimeout(timer)
    }
  }, [error])

  return (
    <div className="flex size-full flex-col overflow-hidden bg-background">
      <div className="shrink-0 px-10 pb-6 pt-10">
        <div className="flex items-center justify-between gap-6">
          <div className="flex flex-col gap-1">
            <h1 className="flex items-center gap-3 text-2xl font-bold tracking-wide text-content-primary">
              <ShoppingCart className="size-7 text-primary" />
              {t('plugin.market')}
            </h1>
            <p className="text-sm text-content-secondary">{t("plugin.discoverAndInstall")}</p>
          </div>

          <div className="flex items-center gap-6">
            <Button
              onClick={handleSortCycle}
              disabled={state.installingPluginName !== null}
              variant="outline"
              size="sm"
              className="gap-1.5"
            >
              <ArrowUpDown className="size-3.5" />
              {sortModeLabels[sortMode]}
            </Button>

            <label className="flex items-center gap-2.5 cursor-pointer select-none">
              <span className="text-sm font-medium text-content-secondary transition-colors hover:text-content-primary">
                {t('pluginMarket.autoInstallDeps')}
              </span>
              <Switch
                checked={state.autoInstallDeps}
                onCheckedChange={handleAutoInstallDepsChange}
                disabled={state.installingPluginName !== null}
              />
            </label>
            
            <Button
              onClick={handleRefresh}
              disabled={state.isRefreshing || state.installingPluginName !== null}
              variant="outline"
              className="gap-2"
            >
              <RefreshCw className={cn('w-4 h-4', state.isRefreshing && 'animate-spin')} />
              {t('pluginMarket.refreshList')}
            </Button>
          </div>
        </div>

        {error && (
          <div className="mt-4 flex items-center gap-2 rounded-lg border border-danger/20 bg-danger/10 p-3 text-danger">
            <AlertCircle className="size-4" />
            <span className="text-sm">{error}</span>
          </div>
        )}
      </div>

      <div className="flex min-h-0 flex-1 flex-col overflow-hidden px-10 pb-10">
        <PluginLibraryTab
          ref={pluginLibraryTabRef}
          autoInstallDeps={state.autoInstallDeps}
          onInstallStart={handleInstallStart}
          installingPluginName={state.installingPluginName}
          sortMode={sortMode}
        />
      </div>

      {currentPlugin && (
        <InstallProgressModal
          isOpen={state.showProgressModal}
          pluginName={currentPlugin.name}
          githubUrl={currentPlugin.repository}
          autoInstallDeps={state.autoInstallDeps}
          onClose={handleCloseProgressModal}
          onInstallComplete={handleInstallComplete}
        />
      )}
      
      {showConfirmDialog && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center">
          <div className="bg-black/50 fixed inset-0" onClick={handleCancelDisableAutoInstall} />
          
          <div className="relative z-[60] w-full max-w-md rounded-xl border border-border bg-surface p-6 shadow-lg">
            <div className="mb-4 flex items-start gap-4">
              <div className="flex size-12 shrink-0 items-center justify-center rounded-full bg-warning/10">
                <AlertCircle className="size-6 text-warning" />
              </div>
              <div className="flex-1">
                <h3 className="mb-2 text-lg font-semibold text-content-primary">
                  {t('plugin.confirmDisableAuto.title')}
                </h3>
                <div className="space-y-2 text-sm text-content-secondary">
                  <p>
                    {t('plugin.confirmDisableAuto.description')}
                  </p>
                  <p className="font-medium text-warning">
                    ⚠️ {t('plugin.confirmDisableAuto.warning')}
                  </p>
                </div>
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <Button
                onClick={handleCancelDisableAutoInstall}
                variant="outline"
              >
                {t('common.cancel')}
              </Button>
              <Button
                onClick={handleConfirmDisableAutoInstall}
                variant="destructive"
              >
                {t('plugin.confirmDisableAuto.confirm')}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

PluginMarketplace.displayName = 'PluginMarketplace'

export default PluginMarketplace
