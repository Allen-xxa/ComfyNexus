/**
 * API 配置表单视图组件
 * 
 * 用于创建和编辑 API 配置，提供以下功能：
 * - 表单布局（别名、服务商、API Key、模型等）
 * - 服务商选择器
 * - 模型选择器
 * - 服务商特定字段动态显示（讯飞星火、Ollama 等）
 * - 表单验证（别名、API Key、模型、Base URL 等）
 * - 操作按钮（保存、取消、测试连接）
 * 
 * 验证需求：1.2, 2.1, 2.2, 2.3, 3.1, 3.2, 3.6, 4.1, 12.1, 13.1, 13.2, 13.3, 13.4
 */

import React, { useState, useEffect, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { useAPIConfigStore, APIConfigInput, TestResult } from '@/stores/useAPIConfigStore'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card'
import { Loading } from '@/components/ui/Loading'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/Select'
import { 
  Save, 
  X, 
  TestTube, 
  AlertCircle,
  CheckCircle,
  Loader2,
  RefreshCw
} from 'lucide-react'

/**
 * 服务商信息接口
 */
interface ProviderInfo {
  id: string
  name: string
  requiresApiKey: boolean
  supportsBaseUrl: boolean
  extraFields?: {
    name: string
    label: string
    type: 'text' | 'password'
    required: boolean
    placeholder?: string
  }[]
}

/**
 * 服务商配置列表
 */
const PROVIDERS: ProviderInfo[] = [
  {
    id: 'xflow',
    name: 'xFlow（推荐）',
    requiresApiKey: true,
    supportsBaseUrl: true
  },
  {
    id: 'zhipu',
    name: '智谱 AI',
    requiresApiKey: true,
    supportsBaseUrl: true
  },
  {
    id: 'volcengine',
    name: '火山引擎（豆包）',
    requiresApiKey: true,
    supportsBaseUrl: true
  },
  {
    id: 'iflow',
    name: 'iFlow（心流）',
    requiresApiKey: true,
    supportsBaseUrl: true
  },
  {
    id: 'ollama',
    name: 'Ollama（本地模型）',
    requiresApiKey: false,
    supportsBaseUrl: true
  },
  {
    id: 'custom-openai',
    name: '通用 OpenAI API',
    requiresApiKey: true,
    supportsBaseUrl: true
  }
]

/**
 * 表单错误接口
 */
interface FormErrors {
  alias?: string
  provider?: string
  apiKey?: string
  baseUrl?: string
  model?: string
  [key: string]: string | undefined
}

/**
 * 组件 Props
 */
interface APIConfigFormViewProps {
  configId?: string  // 编辑时传入配置 ID
  onSave?: () => void
  onCancel?: () => void
}

/**
 * API 配置表单视图组件
 */
export const APIConfigFormView: React.FC<APIConfigFormViewProps> = ({
  configId,
  onSave,
  onCancel
}) => {
  // 从 Store 获取状态和方法
  const {
    currentConfig,
    isLoading,
    error,
    getConfig,
    createConfig,
    updateConfig,
    testConnection,
    getAvailableModels,
    clearError
  } = useAPIConfigStore()
  
  // 表单状态
  const [alias, setAlias] = useState('')
  const [provider, setProvider] = useState(configId ? '' : 'xflow')
  const [apiKey, setApiKey] = useState('')
  // 编辑模式下后端只回传掩码：记录"库里是否已有密钥 + 掩码"，用于占位提示和"留空即不变"校验
  const [hasSavedApiKey, setHasSavedApiKey] = useState(false)
  const [savedApiKeyMask, setSavedApiKeyMask] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [model, setModel] = useState('')
  const [extraFields, setExtraFields] = useState<Record<string, string>>({})
  const [useSystemProxy, setUseSystemProxy] = useState(false)  // 新增：是否使用系统代理  
  // UI 状态
  const [errors, setErrors] = useState<FormErrors>({})
  const [isTesting, setIsTesting] = useState(false)
  const [testResult, setTestResult] = useState<TestResult | null>(null)
  const [isSaving, setIsSaving] = useState(false)
  const [isFetchingModels, setIsFetchingModels] = useState(false)
  const [fetchModelsError, setFetchModelsError] = useState<string | null>(null)
  
  const { t } = useTranslation()

  // 是否为编辑模式
  const isEditMode = !!configId

  // 获取当前选择的服务商信息
  const selectedProviderInfo = useMemo(() => {
    return PROVIDERS.find(p => p.id === provider)
  }, [provider])
  
  // 获取当前服务商的常用模型列表
  const [availableModels, setAvailableModels] = useState<string[]>([])
  
  /**
   * API Key 是否视为"未填写"
   *
   * 编辑模式下库里已存密钥时，输入框留空表示"保持原密钥不变"（后端也只在该字段
   * 非空时才覆盖），因此不能按"未填写"处理。
   */
  const isApiKeyMissing = (): boolean => {
    if (!selectedProviderInfo?.requiresApiKey) return false
    if (apiKey.trim()) return false
    return !(isEditMode && hasSavedApiKey)
  }
  
  /**
   * 加载配置数据（编辑模式）
   */
  useEffect(() => {
    console.log('[APIConfigFormView] useEffect 触发, configId:', configId)
    if (configId) {
      console.log('[APIConfigFormView] 编辑模式：加载配置', configId)
      loadConfigData()
    } else {
      console.log('[APIConfigFormView] 创建模式：初始化表单')
      resetForm()
    }
  }, [configId])
  
  /**
   * 加载配置数据
   */
  const loadConfigData = async () => {
    if (!configId) return
    
    const config = await getConfig(configId)
    if (config) {
      console.log('[APIConfigFormView] 配置加载成功，填充表单')
      console.log('[APIConfigFormView] 配置详情:', config)
      console.log('[APIConfigFormView] useSystemProxy 值:', config.useSystemProxy)
      setAlias(config.alias)
      setProvider(config.provider)
      // 不再把密钥（哪怕是掩码）填进输入框：留空 = 保持后端已保存的密钥不变
      setApiKey('')
      setHasSavedApiKey(config.hasApiKey)
      setSavedApiKeyMask(config.apiKey || '')
      setBaseUrl(config.baseUrl || '')
      setModel(config.model)
      setExtraFields(config.extra || {})
      setUseSystemProxy(config.useSystemProxy || false)  // 新增：加载代理设置
      console.log('[APIConfigFormView] useSystemProxy 状态已设置为:', config.useSystemProxy || false)
    }
  }
  
  /**
   * 重置表单
   */
  const resetForm = () => {
    console.log('[APIConfigFormView] 重置表单')
    setAlias('')
    setProvider('xflow')
    setApiKey('')
    setHasSavedApiKey(false)
    setSavedApiKeyMask('')
    setBaseUrl('')
    setModel('')
    setExtraFields({})
    setUseSystemProxy(false)  // 新增：重置代理设置
    setErrors({})
    setTestResult(null)
    clearError()
  }
  
  /**
   * 验证表单
   * 验证需求：2.2, 2.3, 13.1, 13.2, 13.3, 13.4
   */
  const validateForm = (): boolean => {
    console.log('[APIConfigFormView] 验证表单')
    const newErrors: FormErrors = {}
    
    // 验证别名
    if (!alias || alias.trim() === '') {
      newErrors.alias = t('ai.configForm.errors.aliasRequired')
    } else if (alias.length > 50) {
      newErrors.alias = t('ai.configForm.errors.aliasTooLong')
    }

    // 验证服务商
    if (!provider) {
      newErrors.provider = t('ai.configForm.errors.providerRequired')
    }

    // 验证 API Key（Ollama 除外；编辑模式留空表示沿用已保存的密钥）
    if (isApiKeyMissing()) {
      newErrors.apiKey = t('ai.configForm.errors.apiKeyRequired')
    }

    // 验证 Base URL 格式
    if (baseUrl && baseUrl.trim() !== '') {
      try {
        new URL(baseUrl)
      } catch {
        newErrors.baseUrl = t('ai.configForm.errors.baseUrlInvalid')
      }
    }

    // 验证模型
    if (!model || model.trim() === '') {
      newErrors.model = t('ai.configForm.errors.modelRequired')
    }
    
    // 验证服务商特定字段
    if (selectedProviderInfo?.extraFields) {
      for (const field of selectedProviderInfo.extraFields) {
        if (field.required && (!extraFields[field.name] || extraFields[field.name].trim() === '')) {
          newErrors[field.name] = `${field.label} 不能为空`
        }
      }
    }
    
    setErrors(newErrors)
    
    const isValid = Object.keys(newErrors).length === 0
    console.log('[APIConfigFormView] 表单验证结果:', isValid ? '通过' : '失败', newErrors)
    
    return isValid
  }
  
  /**
   * 处理服务商变化
   * 验证需求：12.5
   */
  const handleProviderChange = (newProvider: string) => {
    console.log('[APIConfigFormView] 服务商变化:', newProvider)
    setProvider(newProvider)
    
    // 清空模型选择
    setModel('')
    
    // 清空服务商特定字段
    setExtraFields({})
    
    // 清空相关错误
    setErrors(prev => {
      const newErrors = { ...prev }
      delete newErrors.provider
      delete newErrors.model
      return newErrors
    })
  }
  
  /**
   * 处理额外字段变化
   */
  const handleExtraFieldChange = (fieldName: string, value: string) => {
    setExtraFields(prev => ({
      ...prev,
      [fieldName]: value
    }))
    
    // 清空该字段的错误
    setErrors(prev => {
      const newErrors = { ...prev }
      delete newErrors[fieldName]
      return newErrors
    })
  }
  
  /**
   * 处理刷新模型列表
   */
  const handleRefreshModels = async () => {
    console.log('[APIConfigFormView] 刷新模型列表')
    
    // 验证是否选择了服务商
    if (!provider) {
      console.log('[APIConfigFormView] 未选择服务商，无法刷新模型列表')
      setFetchModelsError('请先选择服务商')
      return
    }
    
    // 验证是否填写了 API Key（Ollama 与"沿用已保存密钥"的编辑模式除外）
    if (isApiKeyMissing()) {
      console.log('[APIConfigFormView] 未填写 API Key，无法刷新模型列表')
      setFetchModelsError('请先填写 API Key')
      return
    }
    
    setIsFetchingModels(true)
    setFetchModelsError(null)
    
    try {
      // 调用 Store 方法获取模型列表（编辑模式带 configId，密钥由后端补齐）
      const models = await getAvailableModels(provider, {
        apiKey: apiKey.trim(),
        configId,
        baseUrl: baseUrl.trim() || undefined,
        useSystemProxy: useSystemProxy  // 传递代理设置
      })
      
      // 检查是否获取到模型
      if (models.length === 0) {
        console.log('[APIConfigFormView] 未获取到模型列表，提示用户手动输入')
        setFetchModelsError('该服务商不支持自动获取模型列表，请手动输入模型名称')
        setAvailableModels([])
      } else {
        // 更新可用模型列表
        setAvailableModels(models)
        console.log('[APIConfigFormView] 模型列表刷新成功，共', models.length, '个模型')
      }
      
    } catch (error) {
      console.error('[APIConfigFormView] 刷新模型列表失败:', error)
      setFetchModelsError(error instanceof Error ? error.message : '刷新模型列表失败，请手动输入模型名称')
      setAvailableModels([])
    } finally {
      setIsFetchingModels(false)
    }
  }
  
  /**
   * 处理保存
   * 验证需求：3.2
   */
  const handleSave = async () => {
    console.log('[APIConfigFormView] 保存配置')
    console.log('[APIConfigFormView] useSystemProxy 状态值:', useSystemProxy)
    
    // 验证表单
    if (!validateForm()) {
      console.log('[APIConfigFormView] 表单验证失败，取消保存')
      return
    }
    
    setIsSaving(true)
    
    // 构建配置数据
    const configData: APIConfigInput = {
      alias: alias.trim(),
      provider,
      apiKey: apiKey.trim(),
      baseUrl: baseUrl.trim() || undefined,
      model: model.trim(),
      models: availableModels,
      extra: Object.keys(extraFields).length > 0 ? extraFields : undefined,
      useSystemProxy  // 新增：包含代理设置
    }
    
    console.log('[APIConfigFormView] 配置数据:', {
      ...configData,
      apiKey: configData.apiKey ? '表单输入' : '留空（沿用已保存）',  // 脱敏
    })
    console.log('[APIConfigFormView] configData.useSystemProxy:', configData.useSystemProxy)
    
    try {
      let success = false
      
      if (isEditMode && configId) {
        // 更新配置
        console.log('[APIConfigFormView] 更新配置:', configId)
        success = await updateConfig(configId, configData)
      } else {
        // 创建配置
        console.log('[APIConfigFormView] 创建配置')
        const newConfigId = await createConfig(configData)
        success = !!newConfigId
      }
      
      if (success) {
        console.log('[APIConfigFormView] 配置保存成功')
        
        // 调用回调
        if (onSave) {
          onSave()
        }
      } else {
        console.error('[APIConfigFormView] 配置保存失败')
      }
    } catch (error) {
      console.error('[APIConfigFormView] 保存配置异常:', error)
    } finally {
      setIsSaving(false)
    }
  }
  
  /**
   * 处理取消
   * 验证需求：3.6
   */
  const handleCancel = () => {
    console.log('[APIConfigFormView] 取消编辑')
    
    // 调用回调
    if (onCancel) {
      onCancel()
    }
  }
  
  /**
   * 解析错误信息，提取用户友好的内容
   */
  const parseErrorMessage = (errorMessage: string): string => {
    if (!errorMessage) return '连接失败，请检查配置'
    
    try {
      // 尝试解析 JSON 错误信息
      const jsonMatch = errorMessage.match(/\{.*\}/)
      if (jsonMatch) {
        const errorObj = JSON.parse(jsonMatch[0])
        
        // 优先提取 error.message（最详细的错误描述）
        if (errorObj.error && errorObj.error.message) {
          const msg = errorObj.error.message
          // 如果是英文错误信息，尝试翻译关键部分
          if (msg.includes('does not exist or you do not have access')) {
            const modelMatch = msg.match(/model or endpoint ([\w-]+)/)
            const modelName = modelMatch ? modelMatch[1] : '指定的模型'
            return `模型 ${modelName} 不存在或您没有访问权限，请检查模型名称和 API Key 配置`
          }
          return msg
        }
        
        // 其次提取 message 字段
        if (errorObj.message) {
          return errorObj.message
        }
        
        // 提取 error 字符串
        if (errorObj.error && typeof errorObj.error === 'string') {
          return errorObj.error
        }
        
        // 处理特定错误代码
        if (errorObj.code) {
          switch (errorObj.code) {
            case 'InvalidEndpointOrModelNotFound':
              return '模型或端点不存在，或您没有访问权限。请检查模型名称和 API Key 配置'
            case 'invalid_api_key':
              return 'API Key 无效，请检查配置'
            case 'insufficient_quota':
              return '账户余额不足或配额已用完'
            case 'rate_limit_exceeded':
              return '请求频率超限，请稍后重试'
            default:
              if (errorObj.error && errorObj.error.type) {
                return `错误类型: ${errorObj.error.type}`
              }
              return `错误代码: ${errorObj.code}`
          }
        }
      }
      
      // 处理常见错误模式
      if (errorMessage.includes('404')) {
        if (errorMessage.includes('model') || errorMessage.includes('endpoint')) {
          return '模型或端点不存在，或您没有访问权限。请检查模型名称、Base URL 和 API Key 配置'
        }
        return '请求的资源不存在，请检查 Base URL 配置'
      }
      
      if (errorMessage.includes('401') || errorMessage.includes('403')) {
        return 'API Key 无效或权限不足，请检查配置'
      }
      
      if (errorMessage.includes('timeout') || errorMessage.includes('超时')) {
        return '连接超时，请检查网络连接或代理设置'
      }
      
      if (errorMessage.includes('network') || errorMessage.includes('网络')) {
        return '网络错误，请检查网络连接或代理设置'
      }
      
      if (errorMessage.includes('Connection refused') || errorMessage.includes('连接被拒绝')) {
        return '无法连接到服务器，请检查 Base URL 或服务是否运行'
      }
      
      // 如果错误信息太长，截取前200个字符
      if (errorMessage.length > 200) {
        return errorMessage.substring(0, 200) + '...'
      }
      
      return errorMessage
      
    } catch (_e) {
      // JSON 解析失败，返回原始错误信息（截取）
      if (errorMessage.length > 200) {
        return errorMessage.substring(0, 200) + '...'
      }
      return errorMessage
    }
  }
  
  /**
   * 处理测试连接
   * 验证需求：4.1, 4.2, 4.3
   */
  const handleTestConnection = async () => {
    console.log('[APIConfigFormView] 测试连接')
    console.log('[APIConfigFormView] useSystemProxy 当前状态:', useSystemProxy)
    
    // 验证表单
    if (!validateForm()) {
      console.log('[APIConfigFormView] 表单验证失败，取消测试')
      return
    }
    
    setIsTesting(true)
    setTestResult(null)
    
    // 构建配置数据
    const configData: APIConfigInput = {
      id: configId,  // 编辑模式：密钥留空时由后端用该 ID 从库里补齐
      alias: alias.trim(),
      provider,
      apiKey: apiKey.trim(),
      baseUrl: baseUrl.trim() || undefined,
      model: model.trim(),
      models: availableModels,
      extra: Object.keys(extraFields).length > 0 ? extraFields : undefined,
      useSystemProxy  // 新增：包含代理设置
    }
    
    console.log('[APIConfigFormView] 配置数据:', {
      ...configData,
      apiKey: configData.apiKey ? '表单输入' : '留空（沿用已保存）',  // 脱敏
      useSystemProxy: configData.useSystemProxy
    })
    
    try {
      // 使用 testConnection 方法直接测试配置（不保存）
      console.log('[APIConfigFormView] 使用 testConnection 测试配置（不保存）')
      const result = await testConnection(provider, configData)
      
      // 解析错误信息
      if (!result.available && result.errorMessage) {
        result.errorMessage = parseErrorMessage(result.errorMessage)
      }
      
      setTestResult(result)
    } catch (error) {
      console.error('[APIConfigFormView] 测试连接异常:', error)
      const errorMessage = error instanceof Error ? error.message : '未知错误'
      setTestResult({
        success: false,
        available: false,
        message: '测试连接失败',
        errorMessage: parseErrorMessage(errorMessage)
      })
    } finally {
      setIsTesting(false)
    }
  }
  
  /**
   * 清除字段错误
   */
  const clearFieldError = (fieldName: keyof FormErrors) => {
    setErrors(prev => {
      const newErrors = { ...prev }
      delete newErrors[fieldName]
      return newErrors
    })
  }
  
  // 加载状态
  if (isLoading && isEditMode && !currentConfig) {
    return (
      <div className="flex h-96 items-center justify-center">
        <Loading size="lg" text={t('ai.loadingConfig')} />
      </div>
    )
  }
  
  return (
    <div className="h-full overflow-y-auto p-6">
      <Card className="mx-auto w-full max-w-3xl">
        <CardHeader>
          <CardTitle>
            {isEditMode ? t('ai.editConfig') : t('ai.addConfig')}
          </CardTitle>
          <CardDescription>
            {isEditMode 
              ? t('ai.modifyConfigDesc') 
              : t('ai.createConfigDesc')}
          </CardDescription>
        </CardHeader>
        
        <CardContent className="space-y-6">
        {/* 错误提示 */}
        {error && (
          <div className="flex items-center gap-2 rounded-md bg-destructive/10 p-3 text-destructive">
            <AlertCircle className="size-4 shrink-0" />
            <p className="text-sm">{error}</p>
          </div>
        )}
        
        {/* 测试结果提示 */}
        {testResult && (
          <div className={`flex items-center gap-2 rounded-md p-3 ${
            testResult.available 
              ? 'bg-success/10 text-success' 
              : 'bg-danger/10 text-danger'
          }`}>
            {testResult.available ? (
              <CheckCircle className="size-4 shrink-0" />
            ) : (
              <AlertCircle className="size-4 shrink-0" />
            )}
            <div className="flex-1">
              <p className="text-sm font-medium">{testResult.message}</p>
              {testResult.latency && (
                <p className="mt-1 text-xs">{t('ai.responseLatency')}: {testResult.latency.toFixed(2)} ms</p>
              )}
              {testResult.errorMessage && (
                <p className="mt-1 text-xs">{testResult.errorMessage}</p>
              )}
            </div>
          </div>
        )}
        
        {/* 表单字段 */}
        <div className="space-y-4">
          {/* 配置别名 */}
          <div className="space-y-2">
            <Label htmlFor="alias" className="required">
              配置别名 <span className="text-destructive">*</span>
            </Label>
            <Input
              id="alias"
              type="text"
              placeholder={t("common.placeholder.aliasExample")}
              value={alias}
              onChange={(e) => {
                setAlias(e.target.value)
                clearFieldError('alias')
              }}
              maxLength={50}
              className={errors.alias ? 'border-destructive' : ''}
            />
            {errors.alias && (
              <p className="text-sm text-destructive">{errors.alias}</p>
            )}
            <p className="text-xs text-muted-foreground">
              为配置设置一个易于识别的名称（最多 50 个字符）
            </p>
          </div>
          
          {/* 服务商选择 */}
          <div className="space-y-2">
            <Label htmlFor="provider" className="required">
              服务商 <span className="text-destructive">*</span>
            </Label>
            <Select value={provider} onValueChange={handleProviderChange}>
              <SelectTrigger id="provider" className={errors.provider ? 'border-destructive' : ''}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {PROVIDERS.map((p) => (
                  <SelectItem key={p.id} value={p.id}>
                    {p.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {errors.provider && (
              <p className="text-sm text-destructive">{errors.provider}</p>
            )}
            {provider === 'xflow' && (
              <p className="text-xs text-muted-foreground">
                还没有 xFlow 账号？
                <a
                  href="https://api.xflow.cc/register?aff=mSG6"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="ml-1 text-primary underline underline-offset-2 hover:text-primary-hover"
                  onClick={(e) => {
                    e.preventDefault()
                    window.open('https://api.xflow.cc/register?aff=mSG6', '_blank')
                  }}
                >
                  点击注册 →
                </a>
              </p>
            )}
          </div>
          
          {/* API Key（Ollama 除外） */}
          {selectedProviderInfo?.requiresApiKey && (
            <div className="space-y-2">
              <Label htmlFor="apiKey" className="required">
                API Key <span className="text-destructive">*</span>
              </Label>
              <Input
                id="apiKey"
                type="password"
                placeholder={
                  isEditMode && hasSavedApiKey
                    ? `已保存 ${savedApiKeyMask}，留空表示不修改`
                    : t("common.placeholder.apiKey")
                }
                value={apiKey}
                onChange={(e) => {
                  setApiKey(e.target.value)
                  clearFieldError('apiKey')
                }}
                className={errors.apiKey ? 'border-destructive' : ''}
              />
              {errors.apiKey && (
                <p className="text-sm text-destructive">{errors.apiKey}</p>
              )}
              <p className="text-xs text-muted-foreground">
                {isEditMode && hasSavedApiKey
                  ? 'API Key 加密保存在本机，界面不再显示原文；留空即沿用已保存的密钥'
                  : 'API Key 将被加密保存在本机，保存后界面不再显示原文'}
              </p>
            </div>
          )}
          
          {/* 服务商特定字段（如讯飞星火的 App ID 和 API Secret） */}
          {selectedProviderInfo?.extraFields?.map((field) => (
            <div key={field.name} className="space-y-2">
              <Label htmlFor={field.name} className={field.required ? 'required' : ''}>
                {field.label} {field.required && <span className="text-destructive">*</span>}
              </Label>
              <Input
                id={field.name}
                type={field.type}
                placeholder={field.placeholder}
                value={extraFields[field.name] || ''}
                onChange={(e) => handleExtraFieldChange(field.name, e.target.value)}
                className={errors[field.name] ? 'border-destructive' : ''}
              />
              {errors[field.name] && (
                <p className="text-sm text-destructive">{errors[field.name]}</p>
              )}
            </div>
          ))}
          
          {/* Base URL（仅 Ollama 和通用 OpenAI API 显示） */}
          {(provider === 'ollama' || provider === 'custom-openai') && (
            <div className="space-y-2">
              <Label htmlFor="baseUrl">
                Base URL
              </Label>
              <Input
                id="baseUrl"
                type="text"
                placeholder={
                  provider === 'ollama'
                    ? 'http://127.0.0.1:11434'
                    : '例如：https://api.openai.com/v1'
                }
                value={baseUrl}
                onChange={(e) => {
                  setBaseUrl(e.target.value)
                  clearFieldError('baseUrl')
                }}
                className={errors.baseUrl ? 'border-destructive' : ''}
              />
              {errors.baseUrl && (
                <p className="text-sm text-destructive">{errors.baseUrl}</p>
              )}
              <p className="text-xs text-muted-foreground">
                {provider === 'ollama'
                  ? '留空使用默认地址：http://127.0.0.1:11434'
                  : '自定义 API 端点地址，留空使用默认地址'}
              </p>
            </div>
          )}
          
          {/* 模型选择 */}
          <div className="space-y-2">
            <Label htmlFor="model" className="required">
              模型 <span className="text-destructive">*</span>
            </Label>
            
            {/* 刷新模型错误提示 */}
            {fetchModelsError && (
              <div className="flex items-center gap-2 rounded-md bg-warning/10 p-2 text-sm text-warning">
                <AlertCircle className="size-4 shrink-0" />
                <p>{fetchModelsError}</p>
              </div>
            )}
            
            <div className="flex gap-2">
              <Select 
                value={model} 
                onValueChange={(value) => {
                  setModel(value)
                  clearFieldError('model')
                }}
                disabled={!provider}
              >
                <SelectTrigger 
                  id="model" 
                  className={`flex-1 ${errors.model ? 'border-destructive' : ''}`}
                >
                  <SelectValue placeholder={provider ? t('ai.selectModel') : t('ai.selectProviderFirst')} />
                </SelectTrigger>
                <SelectContent>
                  {availableModels.length > 0 ? (
                    availableModels.map((m) => (
                      <SelectItem key={m} value={m}>
                        {m}
                      </SelectItem>
                    ))
                  ) : (
                    <SelectItem value="custom" disabled>
                      {t('ai.noPresetModels')}
                    </SelectItem>
                  )}
                </SelectContent>
              </Select>
              
              {/* 刷新按钮 */}
              <Button
                type="button"
                variant="outline"
                size="icon"
                onClick={handleRefreshModels}
                disabled={!provider || isFetchingModels}
                title={t("common.title.fetchModels")}
              >
                {isFetchingModels ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  <RefreshCw className="size-4" />
                )}
              </Button>
              
              <Input
                type="text"
                placeholder={t("common.placeholder.customModel")}
                value={model}
                onChange={(e) => {
                  setModel(e.target.value)
                  clearFieldError('model')
                }}
                className={`flex-1 ${errors.model ? 'border-destructive' : ''}`}
                disabled={!provider}
              />
            </div>
            {errors.model && (
              <p className="text-sm text-destructive">{errors.model}</p>
            )}
            <p className="text-xs text-muted-foreground">
              从列表选择或手动输入模型名称，点击刷新按钮从 API 获取最新模型列表
            </p>
          </div>
          
          {/* 使用系统代理 */}
          <div className="space-y-2">
            <div className="flex items-center space-x-2">
              {/* eslint-disable-next-line no-restricted-syntax */}
              <input
                type="checkbox"
                id="useSystemProxy"
                checked={useSystemProxy}
                onChange={(e) => {
                  console.log('[APIConfigFormView] 复选框变化:', e.target.checked)
                  setUseSystemProxy(e.target.checked)
                  console.log('[APIConfigFormView] useSystemProxy 状态将设置为:', e.target.checked)
                }}
                className="border-gray-300 size-4 rounded text-primary focus:ring-primary"
              />
              <Label htmlFor="useSystemProxy" className="cursor-pointer font-normal">
                使用系统代理
              </Label>
            </div>
            <p className="text-xs text-muted-foreground">
              通过系统设置中的代理访问 API（需要在系统设置中配置代理）
            </p>
          </div>
        </div>
        
        {/* 操作按钮 */}
        <div className="flex items-center justify-between border-t pt-4">
          <div className="flex gap-2">
            {/* 测试连接按钮 */}
            <Button
              variant="outline"
              onClick={handleTestConnection}
              disabled={isTesting || isSaving || !provider}
            >
              {isTesting ? (
                <>
                  <Loader2 className="mr-2 size-4 animate-spin" />
                  测试中...
                </>
              ) : (
                <>
                  <TestTube className="mr-2 size-4" />
                  测试连接
                </>
              )}
            </Button>
          </div>
          
          <div className="flex gap-2">
            {/* 取消按钮 */}
            <Button
              variant="outline"
              onClick={handleCancel}
              disabled={isSaving}
            >
              <X className="mr-2 size-4" />
              取消
            </Button>
            
            {/* 保存按钮 */}
            <Button
              variant="default"
              onClick={handleSave}
              disabled={isSaving || isTesting}
            >
              {isSaving ? (
                <>
                  <Loader2 className="mr-2 size-4 animate-spin" />
                  保存中...
                </>
              ) : (
                <>
                  <Save className="mr-2 size-4" />
                  保存配置
                </>
              )}
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
    </div>
  )
}

/**
 * 默认导出
 */
export default APIConfigFormView
