/**
 * 系统设置状态管理 Store
 */

import { create } from 'zustand'

interface VersionSettings {
  displayCount: number        // 默认显示数量
  showDevWarning: boolean     // 是否显示开发版警告
}

interface SystemSettings {
  // 通用设置
  configMode?: 'preset' | 'advanced'
  autoUpdate?: boolean
  comfyuiStartupAction?: 'workspace' | 'browser' | 'none'  // ComfyUI 启动后操作
  selectedBrowser?: string  // 浏览器exe路径，空字符串表示系统默认
  closeButtonAction?: 'close' | 'minimize' | 'ask'
  titleBarDoubleClickAction?: 'maximize' | 'fullscreen'  // 标题栏双击操作
  
  // 外观设置
  theme: 'light' | 'dark'
  windowSize: string
  titleBarStyle: 'normal' | 'enhanced'
  globalTextSelection?: boolean
  
  // 语言设置
  language: string
  
  // 代理设置
  proxyEnabled: boolean
  proxyHost: string
  proxyPort: string
  
  // 插件管理设置
  gitConcurrency: number  // Git 并发数，默认 10，范围 1-32
  hideDisabledPlugins: boolean  // 是否隐藏禁用的插件，默认 false
  
  // 插件市场设置
  autoInstallDeps: boolean  // 是否自动安装依赖，默认 true
  
  // 日志设置
  logLevel?: string  // 日志级别：DEBUG/INFO/WARNING/ERROR
  
  // GitHub API 设置
  githubApiEnabled?: boolean  // 是否启用 GitHub API Token
  githubApiToken?: string     // GitHub Personal Access Token
  
  // Git 设置
  gitMode?: 'mingit' | 'system' | 'custom'  // Git 模式
  gitCustomPath?: string                      // 自定义 Git 路径
  
  // 翻译设置
  translationProvider?: 'google' | 'llm'  // 翻译提供商
  translationLlmConfigId?: string          // LLM配置ID
  translationSourceLanguage?: string       // 源语言
  translationTargetLanguage?: string       // 目标语言
  
  // 版本管理设置
  autoTranslateChangelog?: boolean  // 是否自动翻译更新日志

  // WebView2 设置
  hardwareAcceleration?: boolean  // 是否启用硬件加速，默认 true
}

interface SettingsStore {
  // 版本管理设置（仍然使用 localStorage）
  versionSettings: VersionSettings
  
  // 系统设置（从后端加载）
  systemSettings: SystemSettings
  
  // 加载状态
  loading: boolean
  
  // 操作
  updateVersionSettings: (settings: Partial<VersionSettings>) => void
  updateSystemSettings: (settings: Partial<SystemSettings>) => Promise<void>
  loadSystemSettings: () => Promise<void>
  resetDevWarning: () => void
}

function mapCloseButtonAction(closeBehavior: { action?: string | null; dontAskAgain?: boolean } | undefined): 'close' | 'minimize' | 'ask' {
  if (!closeBehavior) return 'ask'
  const { action, dontAskAgain } = closeBehavior
  if (action === 'close' && dontAskAgain) return 'close'
  if (action === 'minimize' && dontAskAgain) return 'minimize'
  return 'ask'
}

export const useSettingsStore = create<SettingsStore>((set, get) => ({
  // 初始状态
  versionSettings: {
    displayCount: 20,
    showDevWarning: true,
  },
  
  systemSettings: {
    configMode: 'preset',
    // 本仓库为二次开发分支，更新源仍指向原作者仓库，开启自动更新会覆盖本地修改，故默认关闭
    autoUpdate: false,
    comfyuiStartupAction: 'workspace',  // 默认在工作台打开
    selectedBrowser: '',  // 默认使用系统浏览器
    closeButtonAction: 'ask',
    titleBarDoubleClickAction: 'maximize',
    theme: 'light',
    windowSize: '1680x1080',
    titleBarStyle: 'normal',
    globalTextSelection: false,
    language: 'zh-CN',
    proxyEnabled: false,
    proxyHost: '',
    proxyPort: '',
    gitConcurrency: 10,  // 默认并发数为 10
    hideDisabledPlugins: false,  // 默认显示所有插件
    autoInstallDeps: true,  // 默认自动安装依赖
    logLevel: 'INFO',  // 默认日志级别为 INFO
    githubApiEnabled: false,  // 默认不启用 GitHub API Token
    githubApiToken: '',  // 默认无 Token
    gitMode: 'mingit',  // 默认使用内置 MinGit
    gitCustomPath: '',  // 默认无自定义路径
    translationProvider: 'google',  // 默认使用 Google 翻译
    translationLlmConfigId: '',  // 默认无 LLM 配置
    translationSourceLanguage: 'auto',  // 默认自动检测
    translationTargetLanguage: 'zh-CN',  // 默认翻译为中文
    autoTranslateChangelog: false,  // 默认不自动翻译更新日志
    hardwareAcceleration: true,  // 默认启用硬件加速
  },
  
  loading: false,
  
  // 更新版本设置（localStorage）
  updateVersionSettings: (settings) => {
    set((state) => ({
      versionSettings: {
        ...state.versionSettings,
        ...settings,
      },
    }))
    
    // 保存到 localStorage
    const newSettings = { ...get().versionSettings, ...settings }
    localStorage.setItem('comfynexus-version-settings', JSON.stringify(newSettings))
  },
  
  // 更新系统设置（后端文件）
  updateSystemSettings: async (settings) => {
    try {
      // 开发环境：直接更新本地状态
      if (!window.pywebview?.api) {
        console.log('[useSettingsStore] 开发环境：直接更新本地状态', settings)
        set((state) => ({
          systemSettings: {
            ...state.systemSettings,
            ...settings,
          },
        }))
        return
      }
      
      console.log('[useSettingsStore] ===== 开始更新设置 =====')
      console.log('[useSettingsStore] 接收到的 settings 参数:', settings)
      console.log('[useSettingsStore] comfyuiStartupAction 值:', settings.comfyuiStartupAction)
      
      // 构建更新数据
      const updates: Record<string, any> = {}
      
      // 处理 general 设置
      const generalUpdates: Record<string, any> = {}
      if ('configMode' in settings && settings.configMode !== undefined) {
        generalUpdates.configMode = settings.configMode
      }
      if ('autoUpdate' in settings && settings.autoUpdate !== undefined) {
        generalUpdates.autoUpdate = settings.autoUpdate
      }
      if ('comfyuiStartupAction' in settings && settings.comfyuiStartupAction !== undefined) {
        console.log('[useSettingsStore] 检测到 comfyuiStartupAction，值为:', settings.comfyuiStartupAction)
        generalUpdates.comfyuiStartupAction = settings.comfyuiStartupAction
      }
      if ('selectedBrowser' in settings && settings.selectedBrowser !== undefined) {
        generalUpdates.selectedBrowser = settings.selectedBrowser
      }
      if ('titleBarDoubleClickAction' in settings && settings.titleBarDoubleClickAction !== undefined) {
        generalUpdates.titleBarDoubleClickAction = settings.titleBarDoubleClickAction
      }
      if ('hardwareAcceleration' in settings && settings.hardwareAcceleration !== undefined) {
        generalUpdates.hardwareAcceleration = settings.hardwareAcceleration
      }
      if (Object.keys(generalUpdates).length > 0) {
        updates.general = generalUpdates
        console.log('[useSettingsStore] updates.general:', updates.general)
      }
      
      if ('theme' in settings || 'windowSize' in settings || 'titleBarStyle' in settings || 'globalTextSelection' in settings) {
        updates.appearance = {}
        if ('theme' in settings) updates.appearance.theme = settings.theme
        if ('windowSize' in settings) updates.appearance.windowSize = settings.windowSize
        if ('titleBarStyle' in settings) updates.appearance.titleBarStyle = settings.titleBarStyle
        if ('globalTextSelection' in settings) updates.appearance.globalTextSelection = settings.globalTextSelection
      }
      
      if ('language' in settings) {
        updates.language = { current: settings.language }
      }
      
      if ('proxyEnabled' in settings || 'proxyHost' in settings || 'proxyPort' in settings) {
        updates.proxy = {}
        if ('proxyEnabled' in settings) updates.proxy.enabled = settings.proxyEnabled
        if ('proxyHost' in settings) updates.proxy.host = settings.proxyHost
        if ('proxyPort' in settings) updates.proxy.port = settings.proxyPort
      }
      
      if ('gitConcurrency' in settings || 'hideDisabledPlugins' in settings) {
        updates.pluginManagement = {}
        if ('gitConcurrency' in settings) updates.pluginManagement.gitConcurrency = settings.gitConcurrency
        if ('hideDisabledPlugins' in settings) updates.pluginManagement.hideDisabledPlugins = settings.hideDisabledPlugins
      }
      
      if ('autoInstallDeps' in settings) {
        updates.pluginMarketplace = {
          autoInstallDeps: settings.autoInstallDeps
        }
      }
      
      if ('logLevel' in settings) {
        updates.logging = {
          level: settings.logLevel
        }
      }
      
      if ('githubApiEnabled' in settings || 'githubApiToken' in settings) {
        updates.github = {}
        if ('githubApiEnabled' in settings) updates.github.enabled = settings.githubApiEnabled
        if ('githubApiToken' in settings) updates.github.apiToken = settings.githubApiToken
      }
      
      if ('gitMode' in settings || 'gitCustomPath' in settings) {
        updates.git = {}
        if ('gitMode' in settings) updates.git.mode = settings.gitMode
        if ('gitCustomPath' in settings) updates.git.customPath = settings.gitCustomPath
      }
      
      if ('translationProvider' in settings || 'translationLlmConfigId' in settings || 'translationSourceLanguage' in settings || 'translationTargetLanguage' in settings) {
        updates.translation = {}
        if ('translationProvider' in settings) updates.translation.provider = settings.translationProvider
        if ('translationLlmConfigId' in settings) updates.translation.llmConfigId = settings.translationLlmConfigId
        if ('translationSourceLanguage' in settings) updates.translation.sourceLanguage = settings.translationSourceLanguage
        if ('translationTargetLanguage' in settings) updates.translation.targetLanguage = settings.translationTargetLanguage
      }
      
      if ('closeButtonAction' in settings) {
        const action = settings.closeButtonAction
        if (action === 'ask') {
          updates.closeBehavior = { action: null, dontAskAgain: false }
        } else {
          updates.closeBehavior = { action: action, dontAskAgain: true }
        }
      }
      
      if ('autoTranslateChangelog' in settings) {
        updates.versionSettings = {
          autoTranslateChangelog: settings.autoTranslateChangelog
        }
      }
      
      console.log('[useSettingsStore] 发送到后端的更新数据:', updates)
      
      // 调用后端 API
      const result = await window.pywebview.api.update_settings(updates)
      
      console.log('[useSettingsStore] 后端返回结果:', result)
      
      if (result.success) {
        // 更新本地状态
        set((state) => ({
          systemSettings: {
            ...state.systemSettings,
            ...settings,
          },
        }))
        console.log('[useSettingsStore] 本地状态已更新')
      } else {
        console.error('[useSettingsStore] 更新设置失败:', result.message)
      }
    } catch (error) {
      console.error('[useSettingsStore] 更新设置失败:', error)
    }
  },
  
  // 从后端加载系统设置
  loadSystemSettings: async () => {
    try {
      set({ loading: true })
      
      if (!window.pywebview?.api) {
        console.error('[useSettingsStore] API 不可用')
        set({ loading: false })
        return
      }
      
      console.log('[useSettingsStore] 开始加载系统设置')
      
      const result = await window.pywebview.api.get_settings()
      
      console.log('[useSettingsStore] 后端返回的设置:', result)
      
      if (result.success && result.settings) {
        const settings = result.settings
        
        console.log('[useSettingsStore] pluginManagement 配置:', (settings as any).pluginManagement)
        console.log('[useSettingsStore] hideDisabledPlugins 值:', (settings as any).pluginManagement?.hideDisabledPlugins)
        
        // 转换后端格式到前端格式
        set({
          systemSettings: {
            autoUpdate: settings.general?.autoUpdate ?? false,
            comfyuiStartupAction: settings.general?.comfyuiStartupAction || 'workspace',
            selectedBrowser: settings.general?.selectedBrowser || '',
            theme: settings.appearance?.theme || 'light',
            windowSize: settings.appearance?.windowSize || '1680x1080',
            titleBarStyle: (settings.appearance as any)?.titleBarStyle || 'normal',
            globalTextSelection: (settings.appearance as any)?.globalTextSelection ?? false,
            language: settings.language?.current || 'zh-CN',
            proxyEnabled: settings.proxy?.enabled || false,
            proxyHost: settings.proxy?.host || '',
            proxyPort: settings.proxy?.port || '',
            gitConcurrency: (settings as any).pluginManagement?.gitConcurrency ?? 10,
            hideDisabledPlugins: (settings as any).pluginManagement?.hideDisabledPlugins ?? false,
            autoInstallDeps: (settings as any).pluginMarketplace?.autoInstallDeps ?? true,
            logLevel: (settings as any).logging?.level || 'INFO',
            githubApiEnabled: (settings as any).github?.enabled ?? false,
            githubApiToken: (settings as any).github?.apiToken ?? '',
            gitMode: (settings as any).git?.mode ?? 'mingit',
            gitCustomPath: (settings as any).git?.customPath ?? '',
            translationProvider: (settings as any).translation?.provider || 'google',
            translationLlmConfigId: (settings as any).translation?.llmConfigId || '',
            translationSourceLanguage: (settings as any).translation?.sourceLanguage || 'auto',
            translationTargetLanguage: (settings as any).translation?.targetLanguage || 'zh-CN',
            closeButtonAction: mapCloseButtonAction((settings as any).closeBehavior),
            titleBarDoubleClickAction: (settings as any).general?.titleBarDoubleClickAction || 'maximize',
            autoTranslateChangelog: (settings as any).versionSettings?.autoTranslateChangelog ?? false,
            hardwareAcceleration: (settings as any).general?.hardwareAcceleration ?? true,
          },
          loading: false,
        })
        
        console.log('[useSettingsStore] 系统设置加载完成')
      } else {
        console.error('[useSettingsStore] 加载设置失败:', result.message)
        set({ loading: false })
      }
      
      // 从 localStorage 加载版本设置
      const versionSettingsStr = localStorage.getItem('comfynexus-version-settings')
      if (versionSettingsStr) {
        try {
          const versionSettings = JSON.parse(versionSettingsStr)
          set({ versionSettings })
        } catch (_e) {
          console.error('[useSettingsStore] 解析版本设置失败')
        }
      }
    } catch (error) {
      console.error('[useSettingsStore] 加载设置失败:', error)
      set({ loading: false })
    }
  },
  
  // 重置开发版警告（恢复显示）
  resetDevWarning: () => {
    set((state) => ({
      versionSettings: {
        ...state.versionSettings,
        showDevWarning: true,
      },
    }))
    
    // 保存到 localStorage
    const newSettings = { ...get().versionSettings, showDevWarning: true }
    localStorage.setItem('comfynexus-version-settings', JSON.stringify(newSettings))
  },
}))
