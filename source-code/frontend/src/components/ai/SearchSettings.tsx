/**
 * 搜索设置组件
 * 
 * 功能：
 * - 搜索引擎选择（DuckDuckGo/Google）
 * - Google API 配置
 * - 测试连接
 * - 高级设置
 */

import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchStore } from '@/stores/useSearchStore'
import { Dialog, DialogContent, DialogTitle, DialogDescription } from '@/components/ui/dialog'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Label } from '@/components/ui/label'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Globe, CheckCircle, XCircle, ExternalLink, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { SearchConfig } from '@/types/search'

interface SearchSettingsProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

/**
 * 搜索设置组件
 */
export function SearchSettings({ open, onOpenChange }: SearchSettingsProps) {
  const { t } = useTranslation()
  const { config, loadConfig, updateConfig, testConnection } = useSearchStore()
  
  // 本地状态
  const [localConfig, setLocalConfig] = useState<SearchConfig | null>(null)
  const [loading, setLoading] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<{
    success: boolean
    message: string
    latency?: number
  } | null>(null)
  
  // 加载配置
  useEffect(() => {
    if (open && !config) {
      loadConfig()
    }
    if (config) {
      setLocalConfig({ ...config })
    }
  }, [open, config, loadConfig])
  
  // 重置测试结果
  useEffect(() => {
    if (!open) {
      setTestResult(null)
    }
  }, [open])
  
  /**
   * 保存配置
   */
  const handleSave = async () => {
    if (!localConfig) return
    
    setLoading(true)
    try {
      const success = await updateConfig(localConfig)
      if (success) {
        onOpenChange(false)
      }
    } finally {
      setLoading(false)
    }
  }
  
  /**
   * 测试连接
   */
  const handleTest = async () => {
    if (!localConfig) return
    
    setTesting(true)
    setTestResult(null)
    try {
      const result = await testConnection(
        localConfig.provider,
        localConfig.providers[localConfig.provider]
      )
      setTestResult(result)
    } finally {
      setTesting(false)
    }
  }
  
  /**
   * 更新配置字段
   */
  const updateField = (path: string, value: any) => {
    if (!localConfig) return
    
    const newConfig = { ...localConfig }
    const keys = path.split('.')
    let current: any = newConfig
    
    for (let i = 0; i < keys.length - 1; i++) {
      current = current[keys[i]]
    }
    
    current[keys[keys.length - 1]] = value
    setLocalConfig(newConfig)
    
    // 清除测试结果
    setTestResult(null)
  }
  
  if (!localConfig) {
    return null
  }
  
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md overflow-hidden rounded-lg bg-surface p-0 shadow-xl">
        {/* 标题栏 */}
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <DialogTitle className="text-lg font-semibold text-foreground">
            联网搜索设置
          </DialogTitle>
        </div>
        
        {/* 内容区域 */}
        <div className="space-y-4 px-5 py-4">
          <DialogDescription className="text-sm text-muted-foreground">
            配置联网搜索服务，让 AI 助手能够搜索互联网获取最新信息
          </DialogDescription>
        
          <div className="space-y-6 py-4">
          {/* 搜索引擎选择 */}
          <div className="space-y-3">
            <Label className="text-base font-semibold">{t("ai.searchEngine")}</Label>
            <div className="space-y-2">
              {/* DuckDuckGo */}
              <div 
                className={cn(
                  "flex items-start space-x-3 p-4 rounded-lg border transition-colors cursor-pointer",
                  localConfig.provider === 'duckduckgo'
                    ? "border-primary bg-primary/5"
                    : "border-border hover:border-primary/50"
                )}
                onClick={() => updateField('provider', 'duckduckgo')}
              >
                {/* eslint-disable-next-line no-restricted-syntax */}
                <input
                  type="radio"
                  name="provider"
                  value="duckduckgo"
                  checked={localConfig.provider === 'duckduckgo'}
                  onChange={() => updateField('provider', 'duckduckgo')}
                  className="mt-1"
                />
                <div className="flex-1">
                  <div className="font-semibold text-foreground">
                    DuckDuckGo
                    <span className="ml-2 rounded-full bg-success/10 px-2 py-0.5 text-xs text-success">
                      免费
                    </span>
                  </div>
                  <div className="mt-1 text-sm text-muted-foreground">
                    完全免费，无需配置，开箱即用
                  </div>
                </div>
              </div>
              
              {/* Google Custom Search */}
              <div 
                className={cn(
                  "flex items-start space-x-3 p-4 rounded-lg border transition-colors cursor-pointer",
                  localConfig.provider === 'google'
                    ? "border-primary bg-primary/5"
                    : "border-border hover:border-primary/50"
                )}
                onClick={() => updateField('provider', 'google')}
              >
                {/* eslint-disable-next-line no-restricted-syntax */}
                <input
                  type="radio"
                  name="provider"
                  value="google"
                  checked={localConfig.provider === 'google'}
                  onChange={() => updateField('provider', 'google')}
                  className="mt-1"
                />
                <div className="flex-1">
                  <div className="font-semibold text-foreground">
                    Google Custom Search
                    <span className="ml-2 rounded-full bg-primary/10 px-2 py-0.5 text-xs text-primary">
                      需要 API Key
                    </span>
                  </div>
                  <div className="mt-1 text-sm text-muted-foreground">
                    每天 100 次免费额度，需要配置 API Key
                  </div>
                </div>
              </div>
              
              {/* Tavily */}
              <div 
                className={cn(
                  "flex items-start space-x-3 p-4 rounded-lg border transition-colors cursor-pointer",
                  localConfig.provider === 'tavily'
                    ? "border-primary bg-primary/5"
                    : "border-border hover:border-primary/50"
                )}
                onClick={() => updateField('provider', 'tavily')}
              >
                {/* eslint-disable-next-line no-restricted-syntax */}
                <input
                  type="radio"
                  name="provider"
                  value="tavily"
                  checked={localConfig.provider === 'tavily'}
                  onChange={() => updateField('provider', 'tavily')}
                  className="mt-1"
                />
                <div className="flex-1">
                  <div className="font-semibold text-foreground">
                    Tavily
                    <span className="ml-2 rounded-full bg-primary/10 px-2 py-0.5 text-xs text-primary">
                      推荐
                    </span>
                  </div>
                  <div className="mt-1 text-sm text-muted-foreground">
                    面向 AI 的搜索 API，结果已抽取正文，每月 1000 次免费额度
                  </div>
                </div>
              </div>
            </div>
          </div>

          {localConfig.provider === 'google' && (
            <div className="space-y-4 rounded-lg border border-border bg-muted p-4">
              <div className="space-y-2">
                <Label htmlFor="api-key">API Key</Label>
                <Input
                  id="api-key"
                  type="password"
                  placeholder={t("common.placeholder.googleApiKey")}
                  value={localConfig.providers.google.api_key}
                  onChange={(e) => updateField('providers.google.api_key', e.target.value)}
                />
                <p className="text-xs text-muted-foreground">
                  <a
                    href="https://console.cloud.google.com/apis/credentials"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-primary hover:underline"
                  >
                    获取 API Key
                    <ExternalLink className="size-3" />
                  </a>
                  {' '}· 需要启用 Custom Search API
                </p>
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="search-engine-id">Search Engine ID</Label>
                <Input
                  id="search-engine-id"
                  placeholder={t("common.placeholder.searchEngineId")}
                  value={localConfig.providers.google.search_engine_id}
                  onChange={(e) => updateField('providers.google.search_engine_id', e.target.value)}
                />
                <p className="text-xs text-muted-foreground">
                  <a
                    href="https://programmablesearchengine.google.com/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-primary hover:underline"
                  >
                    创建搜索引擎
                    <ExternalLink className="size-3" />
                  </a>
                  {' '}· 获取 Search Engine ID
                </p>
              </div>
            </div>
          )}
          
          {/* Tavily 配置 */}
          {localConfig.provider === 'tavily' && (
            <div className="space-y-4 rounded-lg border border-border bg-muted p-4">
              <div className="space-y-2">
                <Label htmlFor="tavily-api-key">API Key</Label>
                <Input
                  id="tavily-api-key"
                  type="password"
                  placeholder="tvly-..."
                  value={localConfig.providers.tavily?.api_key ?? ''}
                  onChange={(e) => updateField('providers.tavily.api_key', e.target.value)}
                />
                <p className="text-xs text-muted-foreground">
                  <a
                    href="https://app.tavily.com/home"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-primary hover:underline"
                  >
                    获取 Tavily API Key
                    <ExternalLink className="size-3" />
                  </a>
                  {' '}· 注册后可在控制台复制，格式为 tvly- 开头
                </p>
              </div>
            </div>
          )}
          
          {/* 高级设置 */}
          <div className="space-y-4">
            <Label className="text-base font-semibold">{t("ai.advancedSettings")}</Label>
            
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="max-results">{t("ai.maxResults")}</Label>
                <Input
                  id="max-results"
                  type="number"
                  min="1"
                  max="10"
                  value={localConfig.max_results}
                  onChange={(e) => updateField('max_results', parseInt(e.target.value))}
                />
                <p className="text-xs text-muted-foreground">
                  每次搜索返回的结果数量（1-10）
                </p>
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="timeout">{t("ai.timeoutSeconds")}</Label>
                <Input
                  id="timeout"
                  type="number"
                  min="5"
                  max="60"
                  value={localConfig.timeout}
                  onChange={(e) => updateField('timeout', parseInt(e.target.value))}
                />
                <p className="text-xs text-muted-foreground">
                  搜索请求的超时时间（5-60秒）
                </p>
              </div>
            </div>
          </div>
          
          {/* 测试结果 */}
          {testResult && (
            <Alert className={cn(
              testResult.success
                ? 'border-success/30 bg-success/10'
                : 'border-danger/30 bg-danger/10'
            )}>
              <div className="flex items-start gap-2">
                {testResult.success ? (
                  <CheckCircle className="mt-0.5 size-5 shrink-0 text-success" />
                ) : (
                  <XCircle className="mt-0.5 size-5 shrink-0 text-danger" />
                )}
                <AlertDescription className={cn(
                  'text-sm',
                  testResult.success
                    ? 'text-success'
                    : 'text-danger'
                )}>
                  {testResult.message}
                  {testResult.latency && (
                    <span className="ml-2 text-xs opacity-75">
                      ({testResult.latency}ms)
                    </span>
                  )}
                </AlertDescription>
              </div>
            </Alert>
          )}
          </div>
        </div>
        
        {/* 底部按钮 */}
        <div className="flex items-center justify-between border-t border-border px-5 py-4">
          <Button
            variant="outline"
            onClick={handleTest}
            disabled={testing || loading}
          >
            {testing ? (
              <>
                <Loader2 className="mr-2 size-4 animate-spin" />
                测试中...
              </>
            ) : (
              <>
                <Globe className="mr-2 size-4" />
                测试连接
              </>
            )}
          </Button>
          
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              onClick={() => onOpenChange(false)}
              disabled={loading}
            >
              取消
            </Button>
            <Button
              onClick={handleSave}
              disabled={loading || testing}
            >
              {loading ? (
                <>
                  <Loader2 className="mr-2 size-4 animate-spin" />
                  保存中...
                </>
              ) : (
                '保存'
              )}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
