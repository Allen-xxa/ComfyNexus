/**
 * 插件库选项卡组件
 * 
 * 显示全量插件列表，支持搜索、过滤和分页加载
 * 采用 Glassmorphism 风格
 */

import React, { useState, useEffect, useCallback, useRef, useMemo, forwardRef, useImperativeHandle } from 'react'
import { useTranslation } from 'react-i18next'
import { Loader2, Search, AlertCircle, ChevronLeft, ChevronRight, ExternalLink, Download, Check, Ban, Clock } from 'lucide-react'
import { VirtualPluginGrid } from './VirtualPluginGrid'
import { pluginMarketplaceService } from '@/services/pluginMarketplaceService'
import { Plugin, PluginLibraryTabProps, InstallStatusType } from '@/types/plugin-marketplace'
import { Input } from '@/components/ui/Input'
import { Button } from '@/components/ui/Button'
import { useEnvStore } from '@/stores/useEnvStore'

interface PluginLibraryTabState {
  plugins: Plugin[]
  filteredPlugins: Plugin[]
  searchKeyword: string
  githubUrl: string
  currentPage: number
  pageSize: number
  isLoading: boolean
  error: string | null
  selectedPlugin: Plugin | null
}

/** 缓存状态：用于顶部提示条 */
interface CacheState {
  /** 数据是否来自已过期的缓存 */
  stale: boolean
  /** 缓存写入时间戳（秒），0 表示没有缓存信息 */
  cachedAt: number
  /** 是否正在后台更新 */
  refreshing: boolean
  /** 非致命提示 */
  warning?: string
}

export const PluginLibraryTab = forwardRef<{ refresh: () => Promise<void>; updateInstallationStatus: () => void }, PluginLibraryTabProps>(({
  autoInstallDeps,
  onInstallStart,
  installingPluginName,
  sortMode
}, ref) => {
  const { t } = useTranslation()
  const { currentEnvId } = useEnvStore()
  
  const [state, setState] = useState<PluginLibraryTabState>({
    plugins: [],
    filteredPlugins: [],
    searchKeyword: '',
    githubUrl: '',
    currentPage: 1,
    pageSize: 20,
    isLoading: false,
    error: null,
    selectedPlugin: null
  })

  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const [containerSize, setContainerSize] = useState({ width: 0, height: 0 })

  useEffect(() => {
    const container = scrollContainerRef.current
    if (!container) return

    const updateSize = () => {
      const rect = container.getBoundingClientRect()
      setContainerSize({
        width: Math.floor(rect.width),
        height: Math.floor(rect.height)
      })
    }

    updateSize()
    const resizeObserver = new ResizeObserver(updateSize)
    resizeObserver.observe(container)

    return () => resizeObserver.disconnect()
  }, [state.filteredPlugins.length])

  const [cacheState, setCacheState] = useState<CacheState>({
    stale: false,
    cachedAt: 0,
    refreshing: false
  })

  /**
   * 用新数据替换列表，但保留用户当前的搜索词和页码
   * （后台刷新完成时不应该把用户从第 5 页弹回第 1 页）
   */
  const applyPluginsPreservingView = useCallback((plugins: Plugin[]) => {
    setState(prev => {
      const keyword = String(prev.searchKeyword || '').trim().toLowerCase()
      const filtered = keyword
        ? plugins.filter(plugin => {
            const name = String(plugin.name || '').toLowerCase()
            const description = String(plugin.description || '').toLowerCase()
            return name.includes(keyword) || description.includes(keyword)
          })
        : plugins
      return { ...prev, plugins, filteredPlugins: filtered, isLoading: false }
    })
  }, [])

  /**
   * 后台拉取最新列表
   *
   * 拉取失败时后端会保留旧缓存并回传旧数据，所以这里不需要清空界面。
   */
  const refreshInBackground = useCallback(async () => {
    setCacheState(prev => ({ ...prev, refreshing: true, warning: undefined }))

    try {
      const result = await pluginMarketplaceService.refreshPlugins()
      const plugins = result.plugins || []

      if (result.success && plugins.length > 0) {
        applyPluginsPreservingView(plugins)
        setCacheState({
          stale: Boolean(result.stale),
          cachedAt: result.cached_at || 0,
          refreshing: false,
          warning: result.warning
        })
      } else {
        setCacheState(prev => ({
          ...prev,
          refreshing: false,
          warning: result.warning || result.error_message || t('plugin.marketplace.refreshFailedKeepCache')
        }))
      }
    } catch (error) {
      console.error('[PluginLibraryTab] 后台刷新插件列表失败:', error)
      setCacheState(prev => ({ ...prev, refreshing: false }))
    }
  }, [applyPluginsPreservingView, t])

  const loadPlugins = useCallback(async (useCache: boolean = true) => {
    setState(prev => ({ ...prev, isLoading: true, error: null }))

    try {
      const response = await pluginMarketplaceService.getPlugins(useCache)

      if (response.success && response.plugins) {
        setState(prev => ({
          ...prev,
          plugins: response.plugins || [],
          filteredPlugins: response.plugins || [],
          isLoading: false,
          currentPage: 1
        }))
        setCacheState({
          stale: Boolean(response.stale),
          cachedAt: response.cached_at || 0,
          refreshing: false,
          warning: response.warning
        })

        // 缓存已过期：先把旧列表展示出来，再静默拉新数据
        if (useCache && response.stale) {
          void refreshInBackground()
        }
      } else {
        setState(prev => ({
          ...prev,
          isLoading: false,
          error: response.error_message || t('plugin.marketplace.loadFailed')
        }))
      }
    } catch (_error) {
      setState(prev => ({
        ...prev,
        isLoading: false,
        error: t('plugin.marketplace.loadFailedRetry')
      }))
    }
  }, [refreshInBackground, t])

  useEffect(() => {
    loadPlugins(true)
  }, [loadPlugins])
  
  useEffect(() => {
    if (currentEnvId) {
      updateInstallationStatus()
    }
  }, [currentEnvId])

  const updateInstallationStatus = useCallback(async () => {
    try {
      const response = await pluginMarketplaceService.getInstalledPluginsStatus()
      
      if (!response.success) return
      
      const installedPluginNames = new Set(response.installed_plugins)
      const disabledPluginNames = new Set(response.disabled_plugins)
      
      setState(prev => {
        const updatedPlugins = prev.plugins.map(plugin => {
          const repoUrl = plugin.repository || ''
          const pluginName = repoUrl.split('/').pop()?.replace('.git', '') || ''
          const isDisabled = disabledPluginNames.has(pluginName)
          const isInstalled = installedPluginNames.has(pluginName)
          
          const installStatus: InstallStatusType = isDisabled ? 'disabled' : (isInstalled ? 'installed' : 'not_installed')
          
          return { 
            ...plugin, 
            is_installed: isInstalled || isDisabled,
            install_status: installStatus
          }
        })
        
        const updatedFilteredPlugins = prev.filteredPlugins.map(plugin => {
          const repoUrl = plugin.repository || ''
          const pluginName = repoUrl.split('/').pop()?.replace('.git', '') || ''
          const isDisabled = disabledPluginNames.has(pluginName)
          const isInstalled = installedPluginNames.has(pluginName)
          
          const installStatus: InstallStatusType = isDisabled ? 'disabled' : (isInstalled ? 'installed' : 'not_installed')
          
          return { 
            ...plugin, 
            is_installed: isInstalled || isDisabled,
            install_status: installStatus
          }
        })
        
        return { ...prev, plugins: updatedPlugins, filteredPlugins: updatedFilteredPlugins }
      })
    } catch (error) {
      console.error('[PluginLibraryTab] 更新插件安装状态失败:', error)
    }
  }, [])

  useImperativeHandle(ref, () => ({
    refresh: () => refreshInBackground(),
    updateInstallationStatus: () => updateInstallationStatus()
  }), [refreshInBackground, updateInstallationStatus])

  const handleSearch = useCallback(() => {
    const keywordStr = String(state.searchKeyword || '').trim().toLowerCase()

    if (!keywordStr) {
      setState(prev => ({ ...prev, filteredPlugins: prev.plugins, currentPage: 1 }))
      return
    }

    const filtered = state.plugins.filter(plugin => {
      const name = String(plugin.name || '').toLowerCase()
      const description = String(plugin.description || '').toLowerCase()
      return name.includes(keywordStr) || description.includes(keywordStr)
    })

    setState(prev => ({ ...prev, filteredPlugins: filtered, currentPage: 1 }))
  }, [state.searchKeyword, state.plugins])

  const handleSearchInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setState(prev => ({ ...prev, searchKeyword: e.target.value }))
  }

  const handleSearchKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') handleSearch()
  }

  const handleGithubUrlChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setState(prev => ({ ...prev, githubUrl: e.target.value }))
  }

  const handleInstallFromGithub = () => {
    const urlStr = String(state.githubUrl || '').trim()

    if (!urlStr) {
      setState(prev => ({ ...prev, error: t('plugin.marketplace.enterGithubUrl') }))
      return
    }

    if (!urlStr.startsWith('https://') || !urlStr.includes('github.com/')) {
      setState(prev => ({ ...prev, error: t('plugin.marketplace.invalidGithubUrl') }))
      return
    }

    const urlParts = urlStr.split('/')
    const pluginName = urlParts[urlParts.length - 1] || 'Unknown'
    
    const tempPlugin: Plugin = {
      name: pluginName,
      description: t('plugin.marketplace.installFromGithub'),
      repository: urlStr,
      version_tag: 'latest',
      updated_at: new Date().toISOString(),
      node_count: 0,
      is_installed: false,
      install_status: 'not_installed',
      author: '',
      stars: 0,
      downloads: 0,
      tags: []
    }

    onInstallStart(tempPlugin)
    setState(prev => ({ ...prev, githubUrl: '', error: null }))
  }

  const sortedPlugins = useMemo(() => {
    const list = [...state.filteredPlugins]
    switch (sortMode) {
      case 'stars':
        return list.sort((a, b) => b.stars - a.stars)
      case 'updated':
        return list.sort((a, b) =>
          new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
        )
      default:
        return list
    }
  }, [state.filteredPlugins, sortMode])

  const totalPages = Math.ceil(sortedPlugins.length / state.pageSize)

  const currentPagePlugins = useMemo(() => {
    const startIndex = (state.currentPage - 1) * state.pageSize
    return sortedPlugins.slice(startIndex, startIndex + state.pageSize)
  }, [sortedPlugins, state.currentPage, state.pageSize])

  const handlePreviousPage = useCallback(() => {
    setState(prev => ({ ...prev, currentPage: Math.max(1, prev.currentPage - 1) }))
    scrollContainerRef.current?.scrollTo({ top: 0, behavior: 'smooth' })
  }, [])

  const handleNextPage = useCallback(() => {
    setState(prev => ({ ...prev, currentPage: Math.min(totalPages, prev.currentPage + 1) }))
    scrollContainerRef.current?.scrollTo({ top: 0, behavior: 'smooth' })
  }, [totalPages])

  const handleGoToPage = useCallback((page: number) => {
    setState(prev => ({ ...prev, currentPage: Math.max(1, Math.min(totalPages, page)) }))
    scrollContainerRef.current?.scrollTo({ top: 0, behavior: 'smooth' })
  }, [totalPages])

  const visiblePlugins = currentPagePlugins

  const handlePluginInstall = (plugin: Plugin) => {
    onInstallStart(plugin)
  }

  const handleShowMore = useCallback((plugin: Plugin) => {
    setState(prev => ({ ...prev, selectedPlugin: plugin }))
  }, [])

  const handleCloseDialog = useCallback(() => {
    setState(prev => ({ ...prev, selectedPlugin: null }))
  }, [])

  const formatUpdateTime = (isoString: string): string => {
    try {
      if (!isoString || isoString === 'null' || isoString === 'undefined') return t('common.unknown')
      const date = new Date(String(isoString))
      if (isNaN(date.getTime())) return t('common.unknown')
      return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
    } catch { return t('common.unknown') }
  }

  /** 把缓存时间戳转成"3 小时前"这类相对时间 */
  const formatCacheAge = (timestamp: number): string => {
    if (!timestamp) return ''
    const seconds = Math.max(0, Math.floor(Date.now() / 1000 - timestamp))
    if (seconds < 60) return t('plugin.marketplace.cacheJustNow')

    const minutes = Math.floor(seconds / 60)
    if (minutes < 60) return t('plugin.marketplace.cacheMinutesAgo', { count: minutes })

    const hours = Math.floor(minutes / 60)
    if (hours < 24) return t('plugin.marketplace.cacheHoursAgo', { count: hours })

    return t('plugin.marketplace.cacheDaysAgo', { count: Math.floor(hours / 24) })
  }

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden">
      <div className="mb-4 shrink-0 space-y-4">
        <div className="rounded-xl border border-border bg-surface p-3">
          <div className="flex gap-3">
            <div className="flex min-w-0 gap-2" style={{ flexBasis: '33.333%' }}>
              <div className="flex min-w-0 flex-1 items-center gap-2 rounded-lg border border-border bg-muted px-3 py-2">
                <Search className="size-4 shrink-0 text-content-muted" />
                <Input
                  type="text"
                  placeholder={t("common.placeholder.searchNameDesc")}
                  value={state.searchKeyword}
                  onChange={handleSearchInputChange}
                  onKeyPress={handleSearchKeyPress}
                  className="min-w-0 flex-1 border-none bg-transparent text-sm text-content-primary outline-none placeholder:text-content-muted"
                />
                <Button
                  onClick={handleSearch}
                  disabled={state.isLoading}
                  variant="outline"
                  size="sm"
                  className="shrink-0"
                >
                  {t('common.search')}
                </Button>
              </div>
            </div>

            <div className="flex min-w-0 flex-1 gap-2">
              <div className="flex min-w-0 flex-1 items-center gap-2 rounded-lg border border-border bg-muted px-3 py-2">
                <ExternalLink className="size-4 shrink-0 text-content-muted" />
                <Input
                  type="text"
                  placeholder={t("common.placeholder.githubUrl")}
                  value={state.githubUrl}
                  onChange={handleGithubUrlChange}
                  className="min-w-0 flex-1 border-none bg-transparent text-sm text-content-primary outline-none placeholder:text-content-muted"
                />
                <Button
                  onClick={handleInstallFromGithub}
                  disabled={!state.githubUrl.trim() || installingPluginName !== null}
                  size="sm"
                  className="border-black/20 dark:border-white/10 flex shrink-0 items-center gap-1 border"
                >
                  <Download className="size-3" />
                  {t('common.install')}
                </Button>
              </div>
            </div>
          </div>
        </div>

        {state.searchKeyword.trim() && state.filteredPlugins.length !== state.plugins.length && (
          <div className="flex items-center justify-between gap-3 rounded-xl border border-border bg-surface p-3">
            <div className="flex min-w-0 flex-1 items-center gap-2">
              <Search className="size-4 shrink-0 text-primary" />
              <span className="text-sm font-medium text-content-primary">{t("plugin.searchKeyword")}:</span>
              <span className="truncate text-sm font-semibold text-primary">"{state.searchKeyword.trim()}"</span>
              <span className="shrink-0 text-sm text-content-secondary">{t('plugin.foundResults', { count: state.filteredPlugins.length })}</span>
            </div>
            <Button
              onClick={() => setState(prev => ({ ...prev, searchKeyword: '', filteredPlugins: prev.plugins, currentPage: 1 }))}
              variant="ghost"
              size="sm"
              className="text-content-secondary hover:text-primary"
            >
              {t('plugin.cancelSearch')}
            </Button>
          </div>
        )}

        {state.error && (
          <div className="flex items-center gap-2 rounded-lg border border-danger/20 bg-danger/10 p-3 text-danger">
            <AlertCircle className="size-4" />
            <span className="text-sm">{state.error}</span>
          </div>
        )}

        {cacheState.cachedAt > 0 && state.plugins.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-muted/60 px-3 py-2 text-xs text-content-secondary">
            <Clock className="size-3.5 shrink-0" />
            <span>
              {cacheState.stale
                ? t('plugin.marketplace.cacheStale', { time: formatCacheAge(cacheState.cachedAt) })
                : t('plugin.marketplace.cacheFresh', { time: formatCacheAge(cacheState.cachedAt) })}
            </span>
            {cacheState.refreshing && (
              <span className="flex items-center gap-1.5 text-primary">
                <Loader2 className="size-3 animate-spin" />
                {t('plugin.marketplace.refreshingInBackground')}
              </span>
            )}
            {cacheState.warning && (
              <span className="text-warning">{cacheState.warning}</span>
            )}
          </div>
        )}
      </div>

      {state.isLoading && state.plugins.length === 0 && (
        <div className="flex flex-col items-center justify-center rounded-xl border border-border bg-surface py-16">
          <Loader2 className="size-10 animate-spin text-primary" />
          <span className="mt-4 font-medium text-content-secondary">{t("plugin.loadingPluginList")}</span>
        </div>
      )}

      {!state.isLoading && state.filteredPlugins.length === 0 && state.plugins.length > 0 && (
        <div className="flex flex-col items-center justify-center rounded-xl border border-border bg-surface py-16">
          <div className="mb-4 flex size-16 items-center justify-center rounded-full bg-primary/10">
            <AlertCircle className="size-8 text-primary" />
          </div>
          <p className="text-base font-semibold text-content-primary">{t("plugin.noMatchingPlugins")}</p>
          <p className="mt-2 text-sm text-content-secondary">{t("plugin.tryOtherKeywords")}</p>
        </div>
      )}

      {!state.isLoading && state.plugins.length === 0 && (
        <div className="flex flex-col items-center justify-center rounded-xl border border-border bg-surface py-16">
          <div className="mb-4 flex size-16 items-center justify-center rounded-full bg-muted">
            <AlertCircle className="size-8 text-content-muted" />
          </div>
          <p className="text-base font-semibold text-content-primary">{t("plugin.noPluginData")}</p>
          <p className="mt-2 text-sm text-content-secondary">{t("plugin.retryOrCheckNetwork")}</p>
        </div>
      )}

      <div ref={scrollContainerRef} className="relative min-h-0 flex-1 overflow-hidden">
        {visiblePlugins.length > 0 && containerSize.width > 0 && containerSize.height > 0 ? (
          <VirtualPluginGrid
            plugins={visiblePlugins}
            autoInstallDeps={autoInstallDeps}
            onInstall={handlePluginInstall}
            installingPluginName={installingPluginName}
            width={containerSize.width}
            height={containerSize.height}
            onShowMore={handleShowMore}
          />
        ) : visiblePlugins.length > 0 ? (
          <div className="flex h-full items-center justify-center">
            <Loader2 className="size-8 animate-spin text-primary" />
          </div>
        ) : null}
      </div>

      {sortedPlugins.length > 0 && totalPages > 1 && (
        <div className="mt-4 flex shrink-0 items-center justify-between gap-4 rounded-xl border border-border bg-surface p-3">
          <div className="text-sm text-content-secondary">
            {t('plugin.marketplace.totalCount', { count: sortedPlugins.length })}，
            {t('plugin.marketplace.pageInfo', { current: state.currentPage, total: totalPages })}
          </div>

          <div className="flex items-center gap-1.5">
            <Button onClick={handlePreviousPage} disabled={state.currentPage === 1} variant="outline" size="icon" className="size-8 disabled:opacity-30">
              <ChevronLeft className="size-4" />
            </Button>

            {state.currentPage > 3 && (
              <>
                <Button onClick={() => handleGoToPage(1)} variant="outline" size="sm" className="size-8">1</Button>
                {state.currentPage > 4 && <span className="px-1 text-content-muted">...</span>}
              </>
            )}

            {Array.from({ length: totalPages }, (_, i) => i + 1)
              .filter(page => page >= state.currentPage - 2 && page <= state.currentPage + 2)
              .map(page => (
                <Button
                  key={page}
                  onClick={() => handleGoToPage(page)}
                  variant={state.currentPage === page ? "default" : "outline"}
                  size="sm"
                  className="size-8"
                >
                  {page}
                </Button>
              ))}

            {state.currentPage < totalPages - 2 && (
              <>
                {state.currentPage < totalPages - 3 && <span className="px-1 text-content-muted">...</span>}
                <Button onClick={() => handleGoToPage(totalPages)} variant="outline" size="sm" className="size-8">{totalPages}</Button>
              </>
            )}

            <Button onClick={handleNextPage} disabled={state.currentPage === totalPages} variant="outline" size="icon" className="size-8 disabled:opacity-30">
              <ChevronRight className="size-4" />
            </Button>
          </div>
        </div>
      )}

      {state.selectedPlugin && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center" onClick={handleCloseDialog}>
          <div className="bg-black/50 fixed inset-0" onClick={handleCloseDialog} />
          
          <div className="relative z-[60] w-full max-w-lg rounded-xl border border-border bg-surface shadow-lg" onClick={e => e.stopPropagation()}>
            <div className="border-b border-border p-6">
              <div className="flex items-start justify-between">
                <div className="flex flex-col gap-2">
                  <h2 className="text-lg font-bold text-content-primary">{state.selectedPlugin.name}</h2>
                  <div className="flex items-center gap-2">
                    {state.selectedPlugin.install_status === 'disabled' ? (
                      <span className="status-badge border border-warning/30 bg-warning/10 text-warning">
                        <Ban className="size-3" /> {t('plugin.marketplace.disabled')}
                      </span>
                    ) : state.selectedPlugin.is_installed ? (
                      <span className="status-badge badge-installed">
                        <Check className="size-3" /> {t('plugin.marketplace.installed')}
                      </span>
                    ) : null}
                    {state.selectedPlugin.repository && (
                      <a
                        href={state.selectedPlugin.repository}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="status-badge cursor-pointer border border-border bg-muted text-content-secondary hover:bg-surface-hover hover:text-content-primary"
                      >
                        <ExternalLink className="size-3" /> {t('plugin.marketplace.visitGithub')}
                      </a>
                    )}
                  </div>
                </div>
                <Button
                  onClick={handleCloseDialog}
                  variant="ghost"
                  size="icon"
                  className="size-8 rounded-full"
                >
                  ✕
                </Button>
              </div>
            </div>

            <div className="max-h-[50vh] overflow-y-auto p-6 text-sm leading-relaxed text-content-secondary">
              <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-content-muted">
                {t('plugin.fullPluginIntro')}
                <span className="h-px flex-1 bg-border" />
              </div>
              <p className="whitespace-pre-wrap">{state.selectedPlugin.description || t('plugin.noDescription')}</p>
            </div>

            <div className="flex items-center justify-between border-t border-border bg-muted/50 p-4">
              <div className="flex gap-6">
                <div className="flex flex-col gap-1">
                  <span className="text-xs text-content-muted">{t("plugin.author")}</span>
                  <span className="text-sm font-medium text-content-primary">{state.selectedPlugin.author || t('common.unknown')}</span>
                </div>
                <div className="flex flex-col gap-1">
                  <span className="text-xs text-content-muted">{t("plugin.updateTime")}</span>
                  <span className="font-mono text-sm font-medium text-content-primary">{formatUpdateTime(state.selectedPlugin.updated_at)}</span>
                </div>
                <div className="flex flex-col gap-1">
                  <span className="text-xs text-content-muted">{t("plugin.nodes")}</span>
                  <span className="font-mono text-sm font-medium text-content-primary">{state.selectedPlugin.node_count || 0}</span>
                </div>
                {state.selectedPlugin.stars > 0 && (
                  <div className="flex flex-col gap-1">
                    <span className="text-xs text-content-muted">{t('plugin.stars')}</span>
                    <span className="font-mono text-sm font-medium text-warning">⭐ {state.selectedPlugin.stars}</span>
                  </div>
                )}
              </div>
              
              <Button disabled variant="outline" size="sm" className="cursor-default text-xs opacity-60">
                {state.selectedPlugin.install_status === 'disabled' ? (
                  <span className="flex items-center gap-1">
                    <Ban className="size-3.5 text-warning" /> 
                    <span>{t('plugin.marketplace.disabled')}</span>
                  </span>
                ) : state.selectedPlugin.is_installed ? (
                  <span className="flex items-center gap-1">
                    <Check className="size-3.5 text-success" /> 
                    <span>{t('plugin.installed')}</span>
                  </span>
                ) : (
                  <span className="flex items-center gap-1">
                    <Download className="size-3.5" /> 
                    <span>{t('plugin.installPlugin')}</span>
                  </span>
                )}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
})

PluginLibraryTab.displayName = 'PluginLibraryTab'

export default PluginLibraryTab
