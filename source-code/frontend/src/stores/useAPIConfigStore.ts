/**
 * API 配置状态管理
 * 
 * 负责管理多个 API 配置，包括：
 * - 加载和保存配置
 * - 创建、更新、删除配置
 * - 设置默认配置
 * - 测试配置连接
 * 
 * 验证需求：1.1, 3.1, 3.2, 3.4, 4.1, 5.1
 */

import { create } from 'zustand'

/**
 * API 配置接口
 */
export interface APIConfig {
  id: string
  alias: string
  provider: string
  /**
   * 后端下发的 **掩码**（形如 `sk-******XjX9`），明文 API Key 不再进入前端。
   * 仅用于展示与"是否已配置"判断，不要当作可用密钥回传。
   */
  apiKey: string
  /** 数据库里是否保存了 API Key */
  hasApiKey: boolean
  baseUrl?: string
  model: string
  models: string[]
  extra: Record<string, any>
  isDefault: boolean
  status: 'available' | 'unavailable' | 'untested'
  lastTestedAt?: string
  lastTestLatency?: number
  usageCount: number
  useSystemProxy: boolean  // 是否使用系统代理
  createdAt: string
  updatedAt: string
}

/**
 * 后端 API 配置响应接口（snake_case）
 */
interface APIConfigResponse {
  id: string
  alias: string
  provider: string
  api_key_masked?: string
  has_api_key?: boolean
  base_url?: string
  model: string
  models: string[]
  extra: Record<string, any>
  is_default: boolean
  status: string
  last_tested_at?: string
  last_test_latency?: number
  usage_count: number
  use_system_proxy: boolean  // 后端使用 snake_case
  created_at: string
  updated_at: string
}

/**
 * 配置输入接口（创建/更新时使用）
 */
export interface APIConfigInput {
  /**
   * 已保存配置的 ID。
   * 对已存在配置做"测试连接/拉取模型"时带上它，后端会用库里的真实密钥执行，
   * 前端不再持有明文。
   */
  id?: string
  alias: string
  provider: string
  /** 用户新输入的明文密钥；留空表示"保持后端已保存的密钥不变" */
  apiKey: string
  baseUrl?: string
  model: string
  models?: string[]
  extra?: Record<string, any>
  useSystemProxy?: boolean  // 是否使用系统代理
}

/**
 * 测试结果接口
 */
export interface TestResult {
  success: boolean
  available: boolean
  latency?: number
  message: string
  errorMessage?: string
}

/**
 * API Config Store 状态接口
 */
interface APIConfigStore {
  // 状态
  configs: APIConfig[]                    // 配置列表
  currentConfig: APIConfig | null         // 当前编辑的配置
  defaultConfigId: string | null          // 默认配置 ID
  isLoading: boolean                      // 是否正在加载
  error: string | null                    // 错误信息
  cacheTimestamp: number | null           // 缓存时间戳（毫秒）
  
  // Actions
  loadConfigs: (forceRefresh?: boolean) => Promise<void>
  getConfig: (id: string) => Promise<APIConfig | null>
  createConfig: (config: APIConfigInput) => Promise<string | null>
  updateConfig: (id: string, config: APIConfigInput) => Promise<boolean>
  deleteConfig: (id: string) => Promise<boolean>
  setDefaultConfig: (id: string) => Promise<boolean>
  testConfig: (id: string) => Promise<TestResult>
  testConnection: (provider: string, config: APIConfigInput) => Promise<TestResult>
  getAvailableModels: (provider: string, config: { apiKey?: string; configId?: string; baseUrl?: string; useSystemProxy?: boolean }) => Promise<string[]>
  
  // 搜索和筛选方法
  searchConfigs: (query: string) => APIConfig[]
  filterByProvider: (provider: string) => APIConfig[]
  
  // 辅助方法
  setCurrentConfig: (config: APIConfig | null) => void
  clearError: () => void
  invalidateCache: () => void
}

/**
 * 检查是否在开发环境
 */
const isDevelopment = (): boolean => {
  return !window.pywebview || !window.pywebview.api
}

/**
 * 生成 Mock 配置数据（开发环境使用）
 */
const getMockConfigs = (): APIConfig[] => {
  return [
    {
      id: 'mock-config-1',
      alias: '工作账号',
      provider: 'openai',
      apiKey: 'sk-******ckey1',
      hasApiKey: true,
      baseUrl: 'https://api.openai.com/v1',
      model: 'gpt-4',
      models: ['gpt-4', 'gpt-3.5-turbo'],
      extra: {},
      isDefault: true,
      status: 'available',
      lastTestedAt: new Date().toISOString(),
      lastTestLatency: 123.45,
      usageCount: 10,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      useSystemProxy: false  // Mock 数据默认不使用代理
    },
    {
      id: 'mock-config-2',
      alias: '个人账号',
      provider: 'openai',
      apiKey: 'sk-******ckey2',
      hasApiKey: true,
      baseUrl: 'https://api.openai.com/v1',
      model: 'gpt-3.5-turbo',
      models: ['gpt-4', 'gpt-3.5-turbo'],
      extra: {},
      isDefault: false,
      status: 'untested',
      usageCount: 0,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      useSystemProxy: false  // Mock 数据默认不使用代理
    }
  ]
}

/**
 * API Config Store 实现
 */
export const useAPIConfigStore = create<APIConfigStore>((set, get) => ({
  // 初始状态
  configs: [],
  currentConfig: null,
  defaultConfigId: null,
  isLoading: false,
  error: null,
  cacheTimestamp: null,
  
  /**
   * 加载配置列表
   * 验证需求：1.1, 1.4, 10.2, 10.3, 10.4
   * 
   * @param forceRefresh 是否强制刷新（忽略缓存）
   * @returns Promise<void>
   */
  loadConfigs: async (forceRefresh = false) => {
    try {
      const state = get()
      
      // 检查缓存是否有效（5分钟内）
      const CACHE_DURATION = 5 * 60 * 1000 // 5分钟
      const now = Date.now()
      const isCacheValid = state.cacheTimestamp && (now - state.cacheTimestamp) < CACHE_DURATION
      
      // 如果缓存有效且不强制刷新，直接返回
      if (isCacheValid && !forceRefresh && state.configs.length > 0) {
        console.log('[useAPIConfigStore] 使用缓存的配置列表，缓存时间:', new Date(state.cacheTimestamp!).toLocaleTimeString())
        return
      }
      
      console.log('[useAPIConfigStore] 加载配置列表', forceRefresh ? '(强制刷新)' : '')
      set({ isLoading: true, error: null })
      
      // 开发环境使用 Mock 数据
      if (isDevelopment()) {
        console.log('[useAPIConfigStore] 开发环境：使用 Mock 数据')
        
        // 模拟延迟
        await new Promise(resolve => setTimeout(resolve, 300))
        
        const mockConfigs = getMockConfigs()
        const defaultConfig = mockConfigs.find(c => c.isDefault)
        
        set({
          configs: mockConfigs,
          defaultConfigId: defaultConfig?.id || null,
          isLoading: false,
          cacheTimestamp: now
        })
        
        console.log('[useAPIConfigStore] Mock 配置加载成功，共', mockConfigs.length, '个配置')
        return
      }
      
      // 生产环境：调用后端 API
      console.log('[useAPIConfigStore] 调用后端 API: ai_list_configs')
      const response = await window.pywebview.api.ai_list_configs()
      
      if (!response.success || !response.configs) {
        console.error('[useAPIConfigStore] 加载配置列表失败:', response.error_message)
        set({
          isLoading: false,
          error: response.error_message || '加载配置列表失败'
        })
        return
      }
      
      // 转换字段名（后端使用下划线，前端使用驼峰）
      const configs: APIConfig[] = (response.configs as APIConfigResponse[]).map((backendConfig) => ({
        id: backendConfig.id,
        alias: backendConfig.alias,
        provider: backendConfig.provider,
        apiKey: backendConfig.api_key_masked || '',
        hasApiKey: backendConfig.has_api_key ?? false,
        baseUrl: backendConfig.base_url,
        model: backendConfig.model,
        models: backendConfig.models || [],
        extra: backendConfig.extra || {},
        isDefault: backendConfig.is_default,
        status: backendConfig.status as 'available' | 'unavailable' | 'untested',
        lastTestedAt: backendConfig.last_tested_at,
        lastTestLatency: backendConfig.last_test_latency,
        usageCount: backendConfig.usage_count,
        createdAt: backendConfig.created_at,
        updatedAt: backendConfig.updated_at,
        useSystemProxy: backendConfig.use_system_proxy || false  // 使用类型化的字段
      }))
      
      const defaultConfig = configs.find(c => c.isDefault)
      
      set({
        configs,
        defaultConfigId: defaultConfig?.id || null,
        isLoading: false,
        cacheTimestamp: now
      })
      
      console.log('[useAPIConfigStore] 配置列表加载成功，共', configs.length, '个配置')
      
    } catch (error) {
      console.error('[useAPIConfigStore] 加载配置列表异常:', error)
      set({
        isLoading: false,
        error: `加载配置列表异常: ${error}`
      })
    }
  },
  
  /**
   * 获取配置详情
   * 验证需求：3.1
   * 
   * @param id 配置 ID
   * @returns Promise<APIConfig | null>
   */
  getConfig: async (id) => {
    try {
      console.log('[useAPIConfigStore] 获取配置详情:', id)
      set({ isLoading: true, error: null })
      
      // 开发环境从本地状态获取
      if (isDevelopment()) {
        console.log('[useAPIConfigStore] 开发环境：从本地状态获取')
        
        // 模拟延迟
        await new Promise(resolve => setTimeout(resolve, 200))
        
        const state = get()
        const config = state.configs.find(c => c.id === id) || null
        
        set({
          currentConfig: config,
          isLoading: false
        })
        
        if (config) {
          console.log('[useAPIConfigStore] 配置获取成功:', config.alias)
        } else {
          console.warn('[useAPIConfigStore] 配置不存在:', id)
        }
        
        return config
      }
      
      // 生产环境：调用后端 API
      console.log('[useAPIConfigStore] 调用后端 API: ai_get_config_detail')
      const response = await window.pywebview.api.ai_get_config_detail(id)
      
      if (!response.success || !response.config) {
        console.error('[useAPIConfigStore] 获取配置详情失败:', response.error_message)
        set({
          isLoading: false,
          error: response.error_message || '获取配置详情失败'
        })
        return null
      }
      
      // 转换字段名（使用类型断言）
      const backendConfig = response.config as APIConfigResponse
      console.log('[useAPIConfigStore] 后端配置数据:', backendConfig)
      console.log('[useAPIConfigStore] use_system_proxy 值:', backendConfig.use_system_proxy)
      
      const config: APIConfig = {
        id: backendConfig.id,
        alias: backendConfig.alias,
        provider: backendConfig.provider,
        apiKey: backendConfig.api_key_masked || '',
        hasApiKey: backendConfig.has_api_key ?? false,
        baseUrl: backendConfig.base_url,
        model: backendConfig.model,
        models: backendConfig.models || [],
        extra: backendConfig.extra || {},
        isDefault: backendConfig.is_default,
        status: backendConfig.status as 'available' | 'unavailable' | 'untested',
        lastTestedAt: backendConfig.last_tested_at,
        lastTestLatency: backendConfig.last_test_latency,
        usageCount: backendConfig.usage_count,
        createdAt: backendConfig.created_at,
        updatedAt: backendConfig.updated_at,
        useSystemProxy: backendConfig.use_system_proxy || false  // 修复：使用类型化的字段
      }
      
      console.log('[useAPIConfigStore] 转换后的配置:', config)
      console.log('[useAPIConfigStore] useSystemProxy 值:', config.useSystemProxy)
      
      set({
        currentConfig: config,
        isLoading: false
      })
      
      console.log('[useAPIConfigStore] 配置详情获取成功:', config.alias)
      return config
      
    } catch (error) {
      console.error('[useAPIConfigStore] 获取配置详情异常:', error)
      set({
        isLoading: false,
        error: `获取配置详情异常: ${error}`
      })
      return null
    }
  },
  
  /**
   * 创建新配置
   * 验证需求：1.2, 1.3, 3.2
   * 
   * @param config 配置输入数据
   * @returns Promise<string | null> 新创建的配置 ID，失败返回 null
   */
  createConfig: async (config) => {
    try {
      console.log('[useAPIConfigStore] 创建新配置:', config.alias)
      set({ isLoading: true, error: null })
      
      // 开发环境使用 Mock
      if (isDevelopment()) {
        console.log('[useAPIConfigStore] 开发环境：使用 Mock 创建')
        
        // 模拟延迟
        await new Promise(resolve => setTimeout(resolve, 500))
        
        // 生成新配置
        const newConfig: APIConfig = {
          id: `mock-config-${Date.now()}`,
          alias: config.alias,
          provider: config.provider,
          apiKey: config.apiKey,
          hasApiKey: !!config.apiKey,
          baseUrl: config.baseUrl,
          model: config.model,
          models: config.models || [],
          extra: config.extra || {},
          isDefault: false,
          status: 'untested',
          usageCount: 0,
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
          useSystemProxy: config.useSystemProxy || false  // 添加代理字段
        }
        
        const state = get()
        set({
          configs: [...state.configs, newConfig],
          isLoading: false
        })
        
        console.log('[useAPIConfigStore] Mock 配置创建成功:', newConfig.id)
        return newConfig.id
      }
      
      // 生产环境：调用后端 API
      console.log('[useAPIConfigStore] 调用后端 API: ai_create_config')
      console.log('[useAPIConfigStore] 配置数据:', { ...config, apiKey: config.apiKey ? '***' : 'empty' })
      console.log('[useAPIConfigStore] useSystemProxy 值:', config.useSystemProxy)
      
      // 转换字段名（前端驼峰转后端下划线）
      const requestData = {
        alias: config.alias,
        provider: config.provider,
        api_key: config.apiKey,
        base_url: config.baseUrl,
        model: config.model,
        models: config.models,
        extra: config.extra,
        use_system_proxy: config.useSystemProxy || false  // 添加代理字段
      }
      
      console.log('[useAPIConfigStore] 请求数据:', { ...requestData, api_key: requestData.api_key ? '***' : 'empty' })
      
      const response = await window.pywebview.api.ai_create_config(requestData)
      
      if (!response.success) {
        console.error('[useAPIConfigStore] 创建配置失败:', response.error_message)
        set({
          isLoading: false,
          error: response.error_message || '创建配置失败'
        })
        return null
      }
      
      // 使缓存失效并重新加载配置列表
      get().invalidateCache()
      await get().loadConfigs(true)
      
      console.log('[useAPIConfigStore] 配置创建成功:', response.config_id)
      return response.config_id || null
      
    } catch (error) {
      console.error('[useAPIConfigStore] 创建配置异常:', error)
      set({
        isLoading: false,
        error: `创建配置异常: ${error}`
      })
      return null
    }
  },
  
  /**
   * 更新配置
   * 验证需求：3.2
   * 
   * @param id 配置 ID
   * @param config 配置输入数据
   * @returns Promise<boolean> 是否更新成功
   */
  updateConfig: async (id, config) => {
    try {
      console.log('[useAPIConfigStore] 更新配置:', id)
      set({ isLoading: true, error: null })
      
      // 开发环境使用 Mock
      if (isDevelopment()) {
        console.log('[useAPIConfigStore] 开发环境：使用 Mock 更新')
        
        // 模拟延迟
        await new Promise(resolve => setTimeout(resolve, 500))
        
        const state = get()
        const configIndex = state.configs.findIndex(c => c.id === id)
        
        if (configIndex === -1) {
          console.error('[useAPIConfigStore] 配置不存在:', id)
          set({
            isLoading: false,
            error: '配置不存在'
          })
          return false
        }
        
        // 更新配置
        const updatedConfig: APIConfig = {
          ...state.configs[configIndex],
          alias: config.alias,
          provider: config.provider,
          // 留空表示沿用已保存的掩码（与后端"空值/掩码 = 不修改密钥"的语义一致）
          apiKey: config.apiKey || state.configs[configIndex].apiKey,
          hasApiKey: !!config.apiKey || state.configs[configIndex].hasApiKey,
          baseUrl: config.baseUrl,
          model: config.model,
          models: config.models || state.configs[configIndex].models,
          extra: config.extra || state.configs[configIndex].extra,
          updatedAt: new Date().toISOString()
        }
        
        const newConfigs = [...state.configs]
        newConfigs[configIndex] = updatedConfig
        
        set({
          configs: newConfigs,
          currentConfig: updatedConfig,
          isLoading: false
        })
        
        console.log('[useAPIConfigStore] Mock 配置更新成功')
        return true
      }
      
      // 生产环境：调用后端 API
      console.log('[useAPIConfigStore] 调用后端 API: ai_update_config')
      console.log('[useAPIConfigStore] 配置数据:', { ...config, apiKey: config.apiKey ? '***' : 'empty' })
      console.log('[useAPIConfigStore] useSystemProxy 值:', config.useSystemProxy)
      
      // 转换字段名
      const requestData: Record<string, unknown> = {
        alias: config.alias,
        provider: config.provider,
        base_url: config.baseUrl,
        model: config.model,
        models: config.models,
        extra: config.extra,
        use_system_proxy: config.useSystemProxy || false  // 添加代理字段
      }
      
      // API Key 留空 = 不修改：干脆不下发该字段，后端保持库里的原密钥
      if (config.apiKey && config.apiKey.trim()) {
        requestData.api_key = config.apiKey.trim()
      }
      
      console.log('[useAPIConfigStore] 请求数据:', { ...requestData, api_key: requestData.api_key ? '***' : 'unchanged' })
      
      const response = await window.pywebview.api.ai_update_config(id, requestData)
      
      if (!response.success) {
        console.error('[useAPIConfigStore] 更新配置失败:', response.error_message)
        set({
          isLoading: false,
          error: response.error_message || '更新配置失败'
        })
        return false
      }
      
      // 使缓存失效并重新加载配置列表
      get().invalidateCache()
      await get().loadConfigs(true)
      
      console.log('[useAPIConfigStore] 配置更新成功')
      return true
      
    } catch (error) {
      console.error('[useAPIConfigStore] 更新配置异常:', error)
      set({
        isLoading: false,
        error: `更新配置异常: ${error}`
      })
      return false
    }
  },
  
  /**
   * 删除配置
   * 验证需求：3.3, 3.4
   * 
   * @param id 配置 ID
   * @returns Promise<boolean> 是否删除成功
   */
  deleteConfig: async (id) => {
    try {
      console.log('[useAPIConfigStore] 删除配置:', id)
      set({ isLoading: true, error: null })
      
      // 开发环境使用 Mock
      if (isDevelopment()) {
        console.log('[useAPIConfigStore] 开发环境：使用 Mock 删除')
        
        // 模拟延迟
        await new Promise(resolve => setTimeout(resolve, 500))
        
        const state = get()
        const configToDelete = state.configs.find(c => c.id === id)
        
        if (!configToDelete) {
          console.error('[useAPIConfigStore] 配置不存在:', id)
          set({
            isLoading: false,
            error: '配置不存在'
          })
          return false
        }
        
        // 删除配置
        const newConfigs = state.configs.filter(c => c.id !== id)
        
        // 如果删除的是默认配置，清除默认配置 ID
        const newDefaultConfigId = configToDelete.isDefault ? null : state.defaultConfigId
        
        set({
          configs: newConfigs,
          defaultConfigId: newDefaultConfigId,
          currentConfig: state.currentConfig?.id === id ? null : state.currentConfig,
          isLoading: false
        })
        
        // 通知 ModelSelectorStore 处理配置删除
        const { useModelSelectorStore } = await import('./useModelSelectorStore')
        useModelSelectorStore.getState().handleConfigDeleted(id)
        
        console.log('[useAPIConfigStore] Mock 配置删除成功')
        return true
      }
      
      // 生产环境：调用后端 API
      console.log('[useAPIConfigStore] 调用后端 API: ai_delete_config')
      const response = await window.pywebview.api.ai_delete_config(id)
      
      if (!response.success) {
        console.error('[useAPIConfigStore] 删除配置失败:', response.error_message)
        set({
          isLoading: false,
          error: response.error_message || '删除配置失败'
        })
        return false
      }
      
      // 通知 ModelSelectorStore 处理配置删除
      // 这会清理默认配置标记和对话配置缓存
      const { useModelSelectorStore } = await import('./useModelSelectorStore')
      useModelSelectorStore.getState().handleConfigDeleted(id)
      
      // 使缓存失效并重新加载配置列表
      get().invalidateCache()
      await get().loadConfigs(true)
      
      console.log('[useAPIConfigStore] 配置删除成功')
      return true
      
    } catch (error) {
      console.error('[useAPIConfigStore] 删除配置异常:', error)
      set({
        isLoading: false,
        error: `删除配置异常: ${error}`
      })
      return false
    }
  },
  
  /**
   * 设置默认配置
   * 验证需求：5.1, 5.2
   * 
   * @param id 配置 ID
   * @returns Promise<boolean> 是否设置成功
   */
  setDefaultConfig: async (id) => {
    try {
      console.log('[useAPIConfigStore] 设置默认配置:', id)
      set({ isLoading: true, error: null })
      
      // 开发环境使用 Mock
      if (isDevelopment()) {
        console.log('[useAPIConfigStore] 开发环境：使用 Mock 设置默认')
        
        // 模拟延迟
        await new Promise(resolve => setTimeout(resolve, 300))
        
        const state = get()
        const configExists = state.configs.some(c => c.id === id)
        
        if (!configExists) {
          console.error('[useAPIConfigStore] 配置不存在:', id)
          set({
            isLoading: false,
            error: '配置不存在'
          })
          return false
        }
        
        // 更新所有配置的 isDefault 标记
        const newConfigs = state.configs.map(c => ({
          ...c,
          isDefault: c.id === id
        }))
        
        set({
          configs: newConfigs,
          defaultConfigId: id,
          isLoading: false
        })
        
        console.log('[useAPIConfigStore] Mock 默认配置设置成功')
        return true
      }
      
      // 生产环境：调用后端 API
      console.log('[useAPIConfigStore] 调用后端 API: ai_set_default_config')
      const response = await window.pywebview.api.ai_set_default_config(id)
      
      if (!response.success) {
        console.error('[useAPIConfigStore] 设置默认配置失败:', response.error_message)
        set({
          isLoading: false,
          error: response.error_message || '设置默认配置失败'
        })
        return false
      }
      
      // 使缓存失效并重新加载配置列表
      get().invalidateCache()
      await get().loadConfigs(true)
      
      console.log('[useAPIConfigStore] 默认配置设置成功')
      return true
      
    } catch (error) {
      console.error('[useAPIConfigStore] 设置默认配置异常:', error)
      set({
        isLoading: false,
        error: `设置默认配置异常: ${error}`
      })
      return false
    }
  },
  
  /**
   * 测试配置连接
   * 验证需求：4.1, 4.2, 4.3, 4.5
   * 
   * @param id 配置 ID
   * @returns Promise<TestResult> 测试结果
   */
  testConfig: async (id) => {
    try {
      console.log('[useAPIConfigStore] 测试配置连接:', id)
      set({ isLoading: true, error: null })
      
      // 开发环境使用 Mock
      if (isDevelopment()) {
        console.log('[useAPIConfigStore] 开发环境：使用 Mock 测试')
        
        // 模拟延迟
        await new Promise(resolve => setTimeout(resolve, 1000))
        
        const state = get()
        const config = state.configs.find(c => c.id === id)
        
        if (!config) {
          const result: TestResult = {
            success: false,
            available: false,
            message: '配置不存在',
            errorMessage: '配置不存在'
          }
          
          set({ isLoading: false, error: '配置不存在' })
          return result
        }
        
        // 模拟成功结果
        const result: TestResult = {
          success: true,
          available: true,
          latency: 123.45,
          message: '连接成功（Mock）'
        }
        
        // 更新配置状态
        const newConfigs = state.configs.map(c => 
          c.id === id 
            ? {
                ...c,
                status: 'available' as const,
                lastTestedAt: new Date().toISOString(),
                lastTestLatency: result.latency
              }
            : c
        )
        
        set({
          configs: newConfigs,
          isLoading: false
        })
        
        console.log('[useAPIConfigStore] Mock 连接测试成功')
        return result
      }
      
      // 生产环境：调用后端 API
      console.log('[useAPIConfigStore] 调用后端 API: ai_test_config')
      const response = await window.pywebview.api.ai_test_config(id)
      
      set({ isLoading: false })
      
      if (!response.success) {
        console.error('[useAPIConfigStore] 测试配置失败:', response.error_message)
        
        const result: TestResult = {
          success: false,
          available: false,
          message: response.message || '测试失败',
          errorMessage: response.error_message
        }
        
        set({ error: response.error_message || '测试配置失败' })
        return result
      }
      
      const result: TestResult = {
        success: true,
        available: response.available,
        latency: response.latency,
        message: response.message
      }
      
      // 使缓存失效并重新加载配置列表以获取更新后的状态
      get().invalidateCache()
      await get().loadConfigs(true)
      
      console.log('[useAPIConfigStore] 配置测试完成:', result.available ? '可用' : '不可用')
      return result
      
    } catch (error) {
      console.error('[useAPIConfigStore] 测试配置异常:', error)
      
      const result: TestResult = {
        success: false,
        available: false,
        message: '测试异常',
        errorMessage: `测试配置异常: ${error}`
      }
      
      set({
        isLoading: false,
        error: `测试配置异常: ${error}`
      })
      
      return result
    }
  },
  
  /**
   * 测试连接（不保存配置）
   * 用于在保存前测试配置是否有效
   * 
   * @param provider 服务商名称
   * @param config 配置数据
   * @returns Promise<TestResult> 测试结果
   */
  testConnection: async (provider, config) => {
    try {
      console.log('[useAPIConfigStore] 测试连接（不保存）:', provider)
      set({ isLoading: true, error: null })
      
      // 开发环境使用 Mock
      if (isDevelopment()) {
        console.log('[useAPIConfigStore] 开发环境：使用 Mock 测试')
        
        // 模拟延迟
        await new Promise(resolve => setTimeout(resolve, 1000))
        
        // 模拟成功结果
        const result: TestResult = {
          success: true,
          available: true,
          latency: 123.45,
          message: '连接成功（Mock）'
        }
        
        set({ isLoading: false })
        
        console.log('[useAPIConfigStore] Mock 连接测试成功')
        return result
      }
      
      // 生产环境：调用后端 API
      console.log('[useAPIConfigStore] 调用后端 API: ai_test_connection')
      console.log('[useAPIConfigStore] config.useSystemProxy 值:', config.useSystemProxy)
      
      // 构建请求参数（使用 snake_case，与后端期望的格式一致）
      const requestConfig: Record<string, any> = {}
      
      // 用户新输了密钥就带明文；留空则只带 config_id，由后端用库里的密钥测试
      if (config.apiKey && config.apiKey.trim()) {
        requestConfig.api_key = config.apiKey.trim()
      }
      if (config.id) {
        requestConfig.config_id = config.id
      }
      
      if (config.baseUrl) {
        requestConfig.base_url = config.baseUrl
      }
      
      if (config.model) {
        requestConfig.model = config.model
      }
      
      if (config.extra) {
        // 将 extra 字段展开到配置中
        Object.assign(requestConfig, config.extra)
      }
      
      // 添加代理设置
      if (config.useSystemProxy !== undefined) {
        requestConfig.use_system_proxy = config.useSystemProxy
        console.log('[useAPIConfigStore] 已添加 use_system_proxy 到请求:', config.useSystemProxy)
      } else {
        console.log('[useAPIConfigStore] config.useSystemProxy 为 undefined，未添加到请求')
      }
      
      console.log('[useAPIConfigStore] 最终请求配置:', {
        ...requestConfig,
        api_key: requestConfig.api_key ? '表单输入' : `沿用已保存(config_id=${config.id || '无'})`
      })
      
      const response = await window.pywebview.api.ai_test_connection(provider, requestConfig)
      
      set({ isLoading: false })
      
      if (!response.success) {
        console.error('[useAPIConfigStore] 测试连接失败:', response.error_message)
        
        const result: TestResult = {
          success: false,
          available: false,
          message: '连接失败',
          errorMessage: response.error_message
        }
        
        return result
      }
      
      const result: TestResult = {
        success: true,
        available: true,
        latency: response.latency,
        message: response.message || '连接成功'
      }
      
      console.log('[useAPIConfigStore] 连接测试成功')
      return result
      
    } catch (error) {
      console.error('[useAPIConfigStore] 测试连接异常:', error)
      
      const result: TestResult = {
        success: false,
        available: false,
        message: '测试异常',
        errorMessage: `测试连接异常: ${error}`
      }
      
      set({
        isLoading: false,
        error: `测试连接异常: ${error}`
      })
      
      return result
    }
  },
  
  /**
   * 获取可用模型列表
   * 验证需求：5.1, 5.2
   * 
   * @param provider 服务商名称
   * @param config 配置信息（apiKey 为表单明文或掩码；已保存配置传 configId，
   *               掩码/空值时由后端用库里的真实密钥拉取）
   * @returns Promise<string[]> 模型列表
   */
  getAvailableModels: async (provider, config) => {
    try {
      console.log('[useAPIConfigStore] 获取可用模型列表:', provider)
      
      // 开发环境使用 Mock
      if (isDevelopment()) {
        console.log('[useAPIConfigStore] 开发环境：返回空列表，提示手动输入')
        
        // 模拟延迟
        await new Promise(resolve => setTimeout(resolve, 800))
        
        // 返回空列表，让用户手动输入
        console.log('[useAPIConfigStore] Mock 环境：返回空模型列表')
        return []
      }
      
      // 生产环境：调用后端 API
      console.log('[useAPIConfigStore] 调用后端 API: ai_get_available_models')
      
      // 构建请求参数（使用 snake_case，与后端 Provider 期望的格式一致）
      const requestConfig = {
        // 掩码/空值时后端按 config_id 用库里的真实密钥执行，前端不再持有明文
        api_key: config.apiKey || '',
        config_id: config.configId || undefined,
        base_url: config.baseUrl || undefined,  // 如果为空字符串，传 undefined
        model: 'gpt-3.5-turbo',  // 提供一个默认模型（某些 Provider 可能需要）
        temperature: 0.7,
        max_tokens: 2048,
        use_system_proxy: config.useSystemProxy || false  // 传递代理设置
      }
      
      console.log('[useAPIConfigStore] 请求参数:', {
        provider,
        api_key: config.apiKey ? '***' : 'empty',
        config_id: config.configId || 'none',
        base_url: config.baseUrl || 'default'
      })
      
      const response = await window.pywebview.api.ai_get_available_models(provider, requestConfig)
      
      if (!response.success) {
        console.error('[useAPIConfigStore] 获取模型列表失败:', response.error_message)
        throw new Error(response.error_message || '获取模型列表失败')
      }
      
      const models = response.models || []
      console.log('[useAPIConfigStore] 模型列表获取成功，共', models.length, '个模型')
      
      return models
      
    } catch (error) {
      console.error('[useAPIConfigStore] 获取模型列表异常:', error)
      throw error
    }
  },
  
  /**
   * 设置当前编辑的配置
   * 
   * @param config 配置对象或 null
   */
  setCurrentConfig: (config) => {
    set({ currentConfig: config })
    console.log('[useAPIConfigStore] 当前配置已设置:', config?.alias || 'null')
  },
  
  /**
   * 清除错误信息
   */
  clearError: () => {
    set({ error: null })
    console.log('[useAPIConfigStore] 错误信息已清除')
  },
  
  /**
   * 使缓存失效
   * 验证需求：10.4
   * 
   * 在添加、修改、删除配置时调用，强制下次加载时重新请求数据
   */
  invalidateCache: () => {
    set({ cacheTimestamp: null })
    console.log('[useAPIConfigStore] 缓存已失效')
  },
  
  /**
   * 搜索配置
   * 根据关键词搜索配置的别名和服务商名称（不区分大小写）
   * 验证需求：8.1, 8.2
   * 
   * @param query 搜索关键词
   * @returns 匹配的配置列表
   */
  searchConfigs: (query) => {
    const state = get()
    
    // 如果搜索关键词为空，返回所有配置
    if (!query || query.trim() === '') {
      console.log('[useAPIConfigStore] 搜索关键词为空，返回所有配置')
      return state.configs
    }
    
    // 转换为小写进行不区分大小写的搜索
    const lowerQuery = query.toLowerCase().trim()
    
    // 搜索别名和服务商名称
    const results = state.configs.filter(config => {
      const aliasMatch = config.alias.toLowerCase().includes(lowerQuery)
      const providerMatch = config.provider.toLowerCase().includes(lowerQuery)
      return aliasMatch || providerMatch
    })
    
    console.log(`[useAPIConfigStore] 搜索 "${query}" 找到 ${results.length} 个配置`)
    return results
  },
  
  /**
   * 按服务商筛选配置
   * 验证需求：8.3
   * 
   * @param provider 服务商名称
   * @returns 指定服务商的配置列表
   */
  filterByProvider: (provider) => {
    const state = get()
    
    // 如果服务商为空，返回所有配置
    if (!provider || provider.trim() === '') {
      console.log('[useAPIConfigStore] 服务商为空，返回所有配置')
      return state.configs
    }
    
    // 筛选指定服务商的配置
    const results = state.configs.filter(config => config.provider === provider)
    
    console.log(`[useAPIConfigStore] 筛选服务商 "${provider}" 找到 ${results.length} 个配置`)
    return results
  }
}))
