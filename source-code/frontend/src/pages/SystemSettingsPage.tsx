/**
 * 系统设置页面
 */

import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { Settings, Palette, Wifi, Save, Puzzle, RotateCcw, Download, GitBranch, FileText, Languages, Database, Monitor } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent, Button, Input, Label } from '@/components/ui'
import { NativeSelect } from '@/components/ui/NativeSelect'
import { Switch } from '@/components/ui/Switch'
import { ModuleManagement } from '@/components/settings/ModuleManagement'
import { GitConcurrencySetting } from '@/components/settings/GitConcurrencySetting'
import { LoggingSettings } from '@/components/settings/LoggingSettings'
import { GitHubApiSetting } from '@/components/settings/GitHubApiSetting'
import { TranslationSettings } from '@/components/settings/TranslationSettings'
import { CacheManagement } from '@/components/settings/CacheManagement'
import { MirrorSettings } from '@/components/settings/MirrorSettings'
import { PyPIMirrorSettings } from '@/components/settings/PyPIMirrorSettings'
import { useWindowStore } from '@/stores/useWindowStore'
import { useWarningStore } from '@/stores/useWarningStore'
import { useSettingsStore } from '@/stores/useSettingsStore'
import { useTheme } from '@/hooks/useTheme'
import { cn } from '@/lib/utils'
import { toast } from '@/utils/toast'

type TabType = 'general' | 'appearance' | 'translation' | 'modules' | 'cache' | 'advanced'

const WINDOW_SIZES: Record<string, { width: number; height: number; label: string }> = {
  '3400x1800': { width: 3400, height: 1800, label: '3400×1800' },
  '1680x1080': { width: 1680, height: 1080, label: '1680×1080' },
  '1280x720': { width: 1280, height: 720, label: '1280×720' }
}

export default function SystemSettingsPage() {
  const { t, i18n } = useTranslation()
  const [activeTab, setActiveTab] = useState<TabType>('general')
  const windowSize = useWindowStore((state) => state.size)
  const setWindowSize = useWindowStore((state) => state.setSize)
  const loadWindowSize = useWindowStore((state) => state.loadSize)
  const { resetAllWarnings } = useWarningStore()
  const { systemSettings, updateSystemSettings, loadSystemSettings } = useSettingsStore()
  const { setTheme } = useTheme()
  
  const [settings, setSettings] = useState(systemSettings)
  const [installedBrowsers, setInstalledBrowsers] = useState<Array<{name: string, displayName: string, path: string}>>([])

  // 初始化时加载设置
  useEffect(() => {
    loadSystemSettings()
    loadWindowSize() // 加载窗口大小
    // 获取已安装的浏览器列表
    fetchBrowsers()
  }, [loadSystemSettings, loadWindowSize])

  // 当 systemSettings 从 store 更新时，同步到本地状态
  useEffect(() => {
    setSettings(systemSettings)
  }, [systemSettings])

  // 判断是否为自定义尺寸：值为 'custom' 或者不在预设选项中
  const isCustomSize = settings.windowSize === 'custom' || 
    (settings.windowSize && !WINDOW_SIZES[settings.windowSize] && settings.windowSize.includes('x'))
  
  const [customWidth, setCustomWidth] = useState('')
  const [customHeight, setCustomHeight] = useState('')
  
  // 当 settings.windowSize 变化时，同步更新自定义尺寸输入框
  useEffect(() => {
    if (settings.windowSize && settings.windowSize.includes('x') && !WINDOW_SIZES[settings.windowSize]) {
      const [w, h] = settings.windowSize.split('x')
      setCustomWidth(w || '')
      setCustomHeight(h || '')
    }
  }, [settings.windowSize])

  const parseCustomSize = (width: string, height: string): string | null => {
    const w = parseInt(width, 10)
    const h = parseInt(height, 10)
    if (w >= 800 && h >= 600) {
      return `${w}x${h}`
    }
    return null
  }

  // 获取已安装的浏览器列表
  const fetchBrowsers = async () => {
    try {
      const response = await window.pywebview?.api?.get_installed_browsers()
      if (response?.success && response?.browsers) {
        setInstalledBrowsers(response.browsers)
      }
    } catch (error) {
      console.error('Failed to fetch browsers:', error)
    }
  }

  const handleSave = async () => {
    try {
      console.log('[SystemSettingsPage] ===== 开始保存设置 =====')
      console.log('[SystemSettingsPage] 当前 settings 状态:', settings)
      console.log('[SystemSettingsPage] comfyuiStartupAction:', settings.comfyuiStartupAction)
      
      // 处理自定义窗口大小：在保存前转换为实际尺寸值
      let settingsToSave = { ...settings }
      if (isCustomSize) {
        const parsedSize = parseCustomSize(customWidth, customHeight)
        if (!parsedSize) {
          toast.error(t('settings.windowSize.invalidSize'))
          return
        }
        settingsToSave = { ...settingsToSave, windowSize: parsedSize }
      }
      
      // 1. 保存到后端文件
      await updateSystemSettings(settingsToSave)
      
      console.log('[SystemSettingsPage] updateSystemSettings 调用完成')
      
      // 2. 处理语言切换
      if (settingsToSave.language !== i18n.language) {
        i18n.changeLanguage(settingsToSave.language)
      }
      
      // 3. 处理窗口大小变更
      if (window.pywebview?.api && settingsToSave.windowSize !== windowSize) {
        let width: number, height: number
        
        if (isCustomSize) {
          const [w, h] = settingsToSave.windowSize.split('x')
          width = parseInt(w, 10)
          height = parseInt(h, 10)
        } else {
          const size = WINDOW_SIZES[settingsToSave.windowSize]
          if (!size) return
          width = size.width
          height = size.height
        }
        
        try {
          document.documentElement.style.transition = 'all 0.3s ease-in-out'
          
          const success = await window.pywebview.api.resizeWindow(width, height)
          if (success) {
            setWindowSize(settingsToSave.windowSize)
            setSettings(settingsToSave)
            
            setTimeout(() => {
              document.documentElement.style.transition = ''
            }, 300)
          }
        } catch (error) {
          console.error('改变窗口大小失败:', error)
          document.documentElement.style.transition = ''
        }
      }
      
      // 4. 检查 Git 路径是否变更，提示用户
      if (settingsToSave.gitMode !== systemSettings.gitMode || 
          settingsToSave.gitCustomPath !== systemSettings.gitCustomPath) {
        toast.info(t('settings.gitPath.restartRequired'))
      }
      
      // 4.5 检查硬件加速是否变更，提示用户需要重启
      if (settingsToSave.hardwareAcceleration !== systemSettings.hardwareAcceleration) {
        toast.info(t('settings.webview2.hardwareAcceleration.restartHint'))
      }
      
      // 5. 显示成功提示
      toast.success(t('settings.saveSuccess'))
    } catch (error) {
      console.error('保存设置失败:', error)
      toast.error(t('settings.saveFailed'))
    }
  }

  const handleGetSystemProxy = async () => {
    try {
      if (!window.pywebview?.api) {
        toast.error(t('common.apiUnavailable'))
        return
      }
      
      const result = await window.pywebview.api.get_system_proxy()
      
      if (result.success) {
        setSettings({
          ...settings,
          proxyHost: result.host,
          proxyPort: result.port
        })
        toast.success(t('settings.proxySettings.getSuccess'))
      } else {
        toast.error(result.message || t('settings.proxySettings.getFailed'))
      }
    } catch (error) {
      console.error('获取系统代理失败:', error)
      toast.error(t('settings.proxySettings.getFailed'))
    }
  }

  const handleTabChange = (tab: TabType) => {
    setActiveTab(tab)
  }

  const tabs: { id: TabType; label: string; icon: React.ReactNode }[] = [
    { id: 'general', label: t('settings.tabs.general'), icon: <Settings className="size-4" /> },
    { id: 'appearance', label: t('settings.tabs.appearance'), icon: <Palette className="size-4" /> },
    { id: 'translation', label: t('settings.tabs.translation'), icon: <Languages className="size-4" /> },
    { id: 'modules', label: t('settings.tabs.modules'), icon: <Puzzle className="size-4" /> },
    { id: 'cache', label: t('settings.tabs.cache'), icon: <Database className="size-4" /> },
    { id: 'advanced', label: t('settings.tabs.advanced'), icon: <GitBranch className="size-4" /> },
  ]

  return (
    <div className="container mx-auto space-y-6 p-6">
      {/* 固定顶部区域 */}
      <div className="sticky top-0 z-10 -mx-6 -mt-6 bg-background px-6 pb-4 pt-6">
        {/* 标题和按钮 */}
        <div className="mb-4 flex items-center justify-between">
          <h1 className="text-2xl font-bold">{t('settings.title')}</h1>
          {activeTab !== 'modules' && (
            <Button onClick={handleSave}>
              <Save className="mr-2 size-4" />
              {t('common.save')}
            </Button>
          )}
        </div>

        {/* 选项卡导航 */}
        <div className="flex gap-2 overflow-x-auto border-b border-border">
          {tabs.map((tab) => (
            <Button
              key={tab.id}
              onClick={() => handleTabChange(tab.id)}
              variant="ghost"
              className={cn(
                "rounded-none border-b-2 whitespace-nowrap",
                activeTab === tab.id
                  ? "border-primary text-primary"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              )}
            >
              {tab.icon}
              {tab.label}
            </Button>
          ))}
        </div>
      </div>

      {/* 选项卡内容 */}
      <div>
        {/* 通用设置 */}
        {activeTab === 'general' && (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {/* 左侧：通用设置 + 代理设置 */}
            <div className="space-y-6">
              {/* 通用设置 */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Settings className="size-5" />
                    {t('settings.general')}
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center justify-between gap-4">
                    <Label className="whitespace-nowrap text-sm font-medium">{t('settings.comfyuiStartupAction.label')}</Label>
                    <NativeSelect
                      value={settings.comfyuiStartupAction || 'workspace'}
                      onValueChange={(value) => {
                        console.log('[SystemSettingsPage] 下拉框值变更:', value)
                        const newSettings = { ...settings, comfyuiStartupAction: value as 'workspace' | 'browser' | 'none' }
                        console.log('[SystemSettingsPage] 新的 settings:', newSettings)
                        setSettings(newSettings)
                      }}
                      className="flex-1"
                    >
                      <option value="workspace">{t('settings.comfyuiStartupAction.workspace')}</option>
                      <option value="browser">{t('settings.comfyuiStartupAction.browser')}</option>
                      <option value="none">{t('settings.comfyuiStartupAction.none')}</option>
                    </NativeSelect>
                  </div>

                  {/* 浏览器选择（仅当选择浏览器启动时显示） */}
                  {settings.comfyuiStartupAction === 'browser' && (
                    <div className="flex items-center justify-between gap-4">
                      <Label className="whitespace-nowrap text-sm font-medium">{t('settings.selectedBrowser.label')}</Label>
                      <NativeSelect
                        value={settings.selectedBrowser || ''}
                        onValueChange={(value) => setSettings({ ...settings, selectedBrowser: value })}
                        className="flex-1"
                      >
                        <option value="">{t('settings.selectedBrowser.default')}</option>
                        {installedBrowsers.map((browser) => (
                          <option key={browser.name} value={browser.path}>
                            {browser.displayName}
                          </option>
                        ))}
                      </NativeSelect>
                    </div>
                  )}

                  {/* 语言设置 */}
                  <div className="flex items-center justify-between gap-4">
                    <Label className="whitespace-nowrap text-sm font-medium">{t('settings.language')}</Label>
                    <NativeSelect
                      value={settings.language}
                      onValueChange={(value) => setSettings({ ...settings, language: value })}
                      className="flex-1"
                    >
                      <option value="zh-CN">{t("settings.simplifiedChinese")}</option>
                      <option value="en-US">English</option>
                    </NativeSelect>
                  </div>

                  {/* 关闭按钮操作 */}
                  <div className="flex items-center justify-between gap-4">
                    <Label className="whitespace-nowrap text-sm font-medium">{t('settings.closeButtonAction.label')}</Label>
                    <NativeSelect
                      value={settings.closeButtonAction || 'ask'}
                      onValueChange={(value) => setSettings({ ...settings, closeButtonAction: value as 'close' | 'minimize' | 'ask' })}
                      className="flex-1"
                    >
                      <option value="ask">{t('settings.closeButtonAction.ask')}</option>
                      <option value="close">{t('settings.closeButtonAction.close')}</option>
                      <option value="minimize">{t('settings.closeButtonAction.minimize')}</option>
                    </NativeSelect>
                  </div>

                  {/* 标题栏双击操作 */}
                  <div className="flex items-center justify-between gap-4">
                    <Label className="whitespace-nowrap text-sm font-medium">{t('settings.titleBarDoubleClickAction.label')}</Label>
                    <NativeSelect
                      value={settings.titleBarDoubleClickAction || 'maximize'}
                      onValueChange={(value) => setSettings({ ...settings, titleBarDoubleClickAction: value as 'maximize' | 'fullscreen' })}
                      className="flex-1"
                    >
                      <option value="maximize">{t('settings.titleBarDoubleClickAction.maximize')}</option>
                      <option value="fullscreen">{t('settings.titleBarDoubleClickAction.fullscreen')}</option>
                    </NativeSelect>
                  </div>
                  
                  {/* 启动时检查更新 */}
                  <div className="flex items-start justify-between gap-4">
                    <div className="space-y-1">
                      <Label className="whitespace-nowrap text-sm font-medium">
                        {t('settings.autoUpdateOnStartup.label')}
                      </Label>
                      <p className="text-xs text-muted-foreground">
                        {t('settings.autoUpdateOnStartup.description')}
                      </p>
                    </div>
                    <Switch
                      aria-label={t('settings.autoUpdateOnStartup.label')}
                      checked={settings.autoUpdate ?? false}
                      onCheckedChange={(checked) => setSettings({ ...settings, autoUpdate: checked })}
                    />
                  </div>

                  {/* 重置所有重要提示 */}
                  <div className="border-t border-border pt-4">
                    <div className="flex items-center justify-between gap-4">
                      <Label className="whitespace-nowrap text-sm font-medium">{t('settings.resetWarnings.label')}</Label>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          resetAllWarnings()
                          toast.success(t('settings.resetWarnings.success'))
                        }}
                      >
                        <RotateCcw className="mr-2 size-4" />
                        {t('common.reset')}
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* 代理设置 */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Wifi className="size-5" />
                    {t('settings.proxy')}
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center justify-between">
                    <Label className="whitespace-nowrap text-sm font-medium">{t('settings.proxySettings.enabled')}</Label>
                    <Switch
                      checked={settings.proxyEnabled}
                      onCheckedChange={(checked) => setSettings({ ...settings, proxyEnabled: checked })}
                    />
                  </div>

                  {settings.proxyEnabled && (
                    <>
                      <div className="flex items-center gap-2">
                        <Label className="whitespace-nowrap text-sm font-medium">{t('settings.proxySettings.host')}</Label>
                        <Input
                          value={settings.proxyHost}
                          onChange={(e) => setSettings({ ...settings, proxyHost: e.target.value })}
                          placeholder="127.0.0.1"
                          className="flex-1"
                        />
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={handleGetSystemProxy}
                        >
                          <Download className="mr-2 size-4" />
                          {t('settings.proxySettings.getSystemProxy')}
                        </Button>
                      </div>
                      
                      <div className="flex items-center gap-2">
                        <Label className="whitespace-nowrap text-sm font-medium">{t('settings.proxySettings.port')}</Label>
                        <Input
                          value={settings.proxyPort}
                          onChange={(e) => setSettings({ ...settings, proxyPort: e.target.value })}
                          placeholder="7890"
                          className="flex-1"
                        />
                      </div>
                    </>
                  )}
                </CardContent>
              </Card>
            </div>

            {/* 右侧：镜像设置 */}
            <div className="space-y-6">
              {/* GitHub 镜像加速设置 */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <GitBranch className="size-5" />
                    {t('settings.mirror.title')}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <MirrorSettings />
                </CardContent>
              </Card>

              {/* PyPI 镜像加速设置 */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Database className="size-5" />
                    {t('settings.pypiMirror.title')}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <PyPIMirrorSettings />
                </CardContent>
              </Card>
            </div>
          </div>
        )}

        {/* 外观设置 */}
        {activeTab === 'appearance' && (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Palette className="size-5" />
                  {t('settings.appearance.title')}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* 主题 */}
                <div className="space-y-2">
                  <Label className="text-sm font-medium">{t('settings.theme')}</Label>
                  <NativeSelect
                    value={settings.theme}
                    onValueChange={(value) => {
                      const newTheme = value as 'light' | 'dark'
                      setSettings({ ...settings, theme: newTheme })
                      // 立即应用主题，无需等待保存
                      setTheme(newTheme)
                    }}
                  >
                    <option value="light">{t('settings.light')}</option>
                    <option value="dark">{t('settings.dark')}</option>
                  </NativeSelect>
                </div>

                {/* 标题栏样式 */}
                <div className="space-y-2">
                  <Label className="text-sm font-medium">{t('settings.titleBarStyle.label')}</Label>
                  <NativeSelect
                    value={settings.titleBarStyle || 'normal'}
                    onValueChange={(value) => {
                      setSettings({ ...settings, titleBarStyle: value as 'normal' | 'enhanced' })
                    }}
                  >
                    <option value="normal">{t('settings.titleBarStyle.normal')}</option>
                    <option value="enhanced">{t('settings.titleBarStyle.enhanced')}</option>
                  </NativeSelect>
                  <p className="text-xs text-muted-foreground">
                    {t('settings.titleBarStyle.hint')}
                  </p>
                </div>

                <div className="space-y-2">
                  <Label className="text-sm font-medium">{t('settings.windowSize.label')}</Label>
                  <NativeSelect
                    value={isCustomSize ? 'custom' : settings.windowSize}
                    onValueChange={(value) => {
                      if (value === 'custom') {
                        setSettings({ ...settings, windowSize: 'custom' })
                      } else {
                        setSettings({ ...settings, windowSize: value })
                      }
                    }}
                  >
                    <option value="3400x1800">3400×1800</option>
                    <option value="1680x1080">1680×1080</option>
                    <option value="1280x720">1280×720</option>
                    <option value="custom">{t('settings.windowSize.custom')}</option>
                  </NativeSelect>
                  
                  {isCustomSize && (
                    <div className="mt-2 flex items-center gap-1">
                      <Input
                        type="number"
                        value={customWidth}
                        onChange={(e) => setCustomWidth(e.target.value)}
                        placeholder={t('settings.windowSize.widthPlaceholder')}
                        min={800}
                        max={7680}
                        className="w-20 [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
                      />
                      <span className="text-sm text-muted-foreground">px</span>
                      <span className="mx-1 text-muted-foreground">×</span>
                      <Input
                        type="number"
                        value={customHeight}
                        onChange={(e) => setCustomHeight(e.target.value)}
                        placeholder={t('settings.windowSize.heightPlaceholder')}
                        min={600}
                        max={4320}
                        className="w-20 [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
                      />
                      <span className="text-sm text-muted-foreground">px</span>
                    </div>
                  )}
                  
                  <p className="text-xs text-muted-foreground">
                    {isCustomSize 
                      ? t('settings.windowSize.customHint')
                      : t('settings.windowSize.hint')}
                  </p>
                </div>

                <div className="border-t border-border pt-4">
                  <div className="flex items-center justify-between">
                    <div className="space-y-0.5">
                      <Label className="text-sm font-medium">{t('settings.globalTextSelection.label')}</Label>
                      <p className="text-xs text-muted-foreground">
                        {t('settings.globalTextSelection.hint')}
                      </p>
                    </div>
                    <Switch
                      checked={settings.globalTextSelection || false}
                      onCheckedChange={(checked) => setSettings({ ...settings, globalTextSelection: checked })}
                    />
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* 翻译设置 */}
        {activeTab === 'translation' && (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Languages className="size-5" />
                  {t('settings.translation.title')}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <TranslationSettings
                  provider={settings.translationProvider || 'google'}
                  llmConfigId={settings.translationLlmConfigId || ''}
                  onProviderChange={(provider) => setSettings({ ...settings, translationProvider: provider })}
                  onLlmConfigChange={(configId) => setSettings({ ...settings, translationLlmConfigId: configId })}
                />
              </CardContent>
            </Card>
          </div>
        )}

        {/* 高级设置 */}
        {activeTab === 'advanced' && (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {/* 左侧：全局Git设置 */}
            <div className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <GitBranch className="size-5" />
                    {t('settings.git.title')}
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-6">
                  {/* Git 并发设置 */}
                  <GitConcurrencySetting
                    value={settings.gitConcurrency}
                    onChange={(value) => setSettings({ ...settings, gitConcurrency: value })}
                  />
                  
                  {/* 分隔线 */}
                  <div className="border-t border-border" />
                  
                  {/* Git 路径设置 */}
                  <div className="space-y-2">
                    <Label className="text-sm font-medium">{t('settings.gitPath.label')}</Label>
                    <NativeSelect
                      value={settings.gitMode || 'mingit'}
                      onValueChange={(value) => setSettings({ ...settings, gitMode: value as 'mingit' | 'system' | 'custom' })}
                    >
                      <option value="mingit">{t('settings.gitPath.mingit')}</option>
                      <option value="system">{t('settings.gitPath.system')}</option>
                      <option value="custom">{t('settings.gitPath.custom')}</option>
                    </NativeSelect>
                    <p className="text-xs text-muted-foreground">
                      {t('settings.gitPath.hint')}
                    </p>
                  </div>
                  
                  {/* 自定义 Git 路径 */}
                  {settings.gitMode === 'custom' && (
                    <div className="space-y-2">
                      <Label className="text-sm font-medium">{t('settings.gitPath.customPath')}</Label>
                      <div className="flex gap-2">
                        <Input
                          value={settings.gitCustomPath || ''}
                          onChange={(e) => setSettings({ ...settings, gitCustomPath: e.target.value })}
                          placeholder={t('settings.gitPath.customPathPlaceholder')}
                          className="flex-1"
                        />
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={async () => {
                            try {
                              if (!window.pywebview?.api) {
                                return
                              }
                              const result = await window.pywebview.api.select_file(['git.exe (*.exe)'])
                              if (result.success && result.path) {
                                setSettings({ ...settings, gitCustomPath: result.path })
                              }
                            } catch (error) {
                              console.error('[SystemSettingsPage] 选择 Git 可执行文件失败:', error)
                            }
                          }}
                        >
                          {t('common.browse')}
                        </Button>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        {t('settings.gitPath.customPathHint')}
                      </p>
                    </div>
                  )}
                  
                  {/* 分隔线 */}
                  <div className="border-t border-border" />
                  
                  {/* GitHub API 设置 */}
                  <GitHubApiSetting
                    enabled={settings.githubApiEnabled || false}
                    token={settings.githubApiToken || ''}
                    onEnabledChange={(enabled) => setSettings({ ...settings, githubApiEnabled: enabled })}
                    onTokenChange={(token) => setSettings({ ...settings, githubApiToken: token })}
                  />
                </CardContent>
              </Card>

              {/* WebView2 设置 */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Monitor className="size-5" />
                    {t('settings.webview2.title')}
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div className="space-y-0.5">
                      <Label className="text-sm font-medium">
                        {t('settings.webview2.hardwareAcceleration.label')}
                      </Label>
                      <p className="text-xs text-muted-foreground">
                        {t('settings.webview2.hardwareAcceleration.hint')}
                      </p>
                    </div>
                    <Switch
                      checked={settings.hardwareAcceleration ?? true}
                      onCheckedChange={(checked) => setSettings({ ...settings, hardwareAcceleration: checked })}
                    />
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {t('settings.webview2.hardwareAcceleration.restartHint')}
                  </p>
                </CardContent>
              </Card>
            </div>

            {/* 右侧：日志设置 */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <FileText className="size-5" />
                  {t('settings.logging.title')}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <LoggingSettings
                  currentLevel={settings.logLevel || 'INFO'}
                  onLevelChange={(level) => setSettings({ ...settings, logLevel: level })}
                />
              </CardContent>
            </Card>
          </div>
        )}

        {/* 模块管理 */}
        {activeTab === 'modules' && (
          <ModuleManagement />
        )}

        {/* 缓存管理 */}
        {activeTab === 'cache' && (
          <div className="space-y-6">
            <div>
              <h2 className="text-xl font-semibold">{t('settings.cache.title')}</h2>
              <p className="text-sm text-muted-foreground">{t('settings.cache.description')}</p>
            </div>
            <CacheManagement />
          </div>
        )}
      </div>
    </div>
  )
}
