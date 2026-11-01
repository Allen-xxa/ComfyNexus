/**
 * useAPIConfigStore 单元测试
 * 
 * 测试 API 配置状态管理的所有功能：
 * - 状态初始化
 * - 加载配置列表
 * - 获取配置详情
 * - 创建配置
 * - 更新配置
 * - 删除配置
 * - 设置默认配置
 * - 测试配置连接
 * - 错误处理
 * 
 * 验证需求：1.1, 3.1, 3.2, 3.4
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useAPIConfigStore } from '@/stores/useAPIConfigStore'
import type { APIConfig, APIConfigInput } from '@/stores/useAPIConfigStore'

// Mock pywebview API
const mockPywebviewAPI = {
  ai_list_configs: vi.fn(),
  ai_get_config_detail: vi.fn(),
  ai_create_config: vi.fn(),
  ai_update_config: vi.fn(),
  ai_delete_config: vi.fn(),
  ai_set_default_config: vi.fn(),
  ai_test_config: vi.fn(),
  ai_test_connection: vi.fn(),
  ai_get_available_models: vi.fn(),
}

// 设置全局 window.pywebview
beforeEach(() => {
  // @ts-expect-error - 测试环境需要模拟全局对象
  global.window = {
    pywebview: {
      api: mockPywebviewAPI
    }
  }
  
  // 清除所有 mock
  vi.clearAllMocks()
  
  // 重置 store 状态
  const store = useAPIConfigStore.getState()
  store.configs = []
  store.currentConfig = null
  store.defaultConfigId = null
  store.isLoading = false
  store.error = null
})

describe('useAPIConfigStore - 状态初始化', () => {
  it('应该有正确的初始状态', () => {
    const store = useAPIConfigStore.getState()
    
    expect(store.configs).toEqual([])
    expect(store.currentConfig).toBeNull()
    expect(store.defaultConfigId).toBeNull()
    expect(store.isLoading).toBe(false)
    expect(store.error).toBeNull()
  })
  
  it('应该提供所有必需的方法', () => {
    const store = useAPIConfigStore.getState()
    
    expect(typeof store.loadConfigs).toBe('function')
    expect(typeof store.getConfig).toBe('function')
    expect(typeof store.createConfig).toBe('function')
    expect(typeof store.updateConfig).toBe('function')
    expect(typeof store.deleteConfig).toBe('function')
    expect(typeof store.setDefaultConfig).toBe('function')
    expect(typeof store.testConfig).toBe('function')
    expect(typeof store.setCurrentConfig).toBe('function')
    expect(typeof store.clearError).toBe('function')
  })
})

describe('useAPIConfigStore - loadConfigs', () => {
  it('应该成功加载配置列表', async () => {
    const mockConfigs = [
      {
        id: 'config-1',
        alias: '工作账号',
        provider: 'openai',
        api_key_masked: 'sk-t******t-1',
        has_api_key: true,
        base_url: 'https://api.openai.com/v1',
        model: 'gpt-4',
        models: ['gpt-4', 'gpt-3.5-turbo'],
        extra: {},
        is_default: true,
        status: 'available',
        last_tested_at: '2024-01-01T00:00:00Z',
        last_test_latency: 123.45,
        usage_count: 10,
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z'
      },
      {
        id: 'config-2',
        alias: '个人账号',
        provider: 'openai',
        api_key_masked: '',
        has_api_key: false,
        base_url: 'https://api.openai.com/v1',
        model: 'gpt-3.5-turbo',
        models: ['gpt-4', 'gpt-3.5-turbo'],
        extra: {},
        is_default: false,
        status: 'untested',
        usage_count: 0,
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z'
      }
    ]
    
    mockPywebviewAPI.ai_list_configs.mockResolvedValue({
      success: true,
      configs: mockConfigs
    })
    
    const store = useAPIConfigStore.getState()
    await store.loadConfigs()
    
    const state = useAPIConfigStore.getState()
    
    expect(state.configs).toHaveLength(2)
    expect(state.configs[0].alias).toBe('工作账号')
    expect(state.configs[1].alias).toBe('个人账号')
    expect(state.defaultConfigId).toBe('config-1')
    expect(state.isLoading).toBe(false)
    expect(state.error).toBeNull()
    // 后端只下发掩码：前端 apiKey 字段即掩码，明文不进渲染进程
    expect(state.configs[0].apiKey).toBe('sk-t******t-1')
    expect(state.configs[0].hasApiKey).toBe(true)
    expect(state.configs[1].apiKey).toBe('')
    expect(state.configs[1].hasApiKey).toBe(false)
  })
  
  it('应该处理加载失败的情况', async () => {
    mockPywebviewAPI.ai_list_configs.mockResolvedValue({
      success: false,
      error_message: '数据库连接失败'
    })
    
    const store = useAPIConfigStore.getState()
    await store.loadConfigs()
    
    const state = useAPIConfigStore.getState()
    
    expect(state.configs).toEqual([])
    expect(state.isLoading).toBe(false)
    expect(state.error).toBe('数据库连接失败')
  })
  
  it('应该处理网络异常', async () => {
    mockPywebviewAPI.ai_list_configs.mockRejectedValue(new Error('网络错误'))
    
    const store = useAPIConfigStore.getState()
    await store.loadConfigs()
    
    const state = useAPIConfigStore.getState()
    
    expect(state.configs).toEqual([])
    expect(state.isLoading).toBe(false)
    expect(state.error).toContain('网络错误')
  })
  
  it('应该正确转换字段名（下划线转驼峰）', async () => {
    const mockConfigs = [
      {
        id: 'config-1',
        alias: '测试配置',
        provider: 'openai',
        api_key_masked: 'sk-t******test',
        has_api_key: true,
        base_url: 'https://api.openai.com/v1',
        model: 'gpt-4',
        models: ['gpt-4'],
        extra: {},
        is_default: true,
        status: 'available',
        last_tested_at: '2024-01-01T00:00:00Z',
        last_test_latency: 100.0,
        usage_count: 5,
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z'
      }
    ]
    
    mockPywebviewAPI.ai_list_configs.mockResolvedValue({
      success: true,
      configs: mockConfigs
    })
    
    const store = useAPIConfigStore.getState()
    await store.loadConfigs()
    
    const state = useAPIConfigStore.getState()
    const config = state.configs[0]
    
    // 验证字段名已转换为驼峰
    expect(config.apiKey).toBe('sk-t******test')
    expect(config.hasApiKey).toBe(true)
    expect(config.baseUrl).toBe('https://api.openai.com/v1')
    expect(config.isDefault).toBe(true)
    expect(config.lastTestedAt).toBe('2024-01-01T00:00:00Z')
    expect(config.lastTestLatency).toBe(100.0)
    expect(config.usageCount).toBe(5)
    expect(config.createdAt).toBe('2024-01-01T00:00:00Z')
    expect(config.updatedAt).toBe('2024-01-01T00:00:00Z')
  })
})

describe('useAPIConfigStore - getConfig', () => {
  it('应该成功获取配置详情', async () => {
    const mockConfig = {
      id: 'config-1',
      alias: '工作账号',
      provider: 'openai',
      api_key_masked: 'sk-t******t-1',
      has_api_key: true,
      base_url: 'https://api.openai.com/v1',
      model: 'gpt-4',
      models: ['gpt-4', 'gpt-3.5-turbo'],
      extra: {},
      is_default: true,
      status: 'available',
      last_tested_at: '2024-01-01T00:00:00Z',
      last_test_latency: 123.45,
      usage_count: 10,
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z'
    }
    
    mockPywebviewAPI.ai_get_config_detail.mockResolvedValue({
      success: true,
      config: mockConfig
    })
    
    const store = useAPIConfigStore.getState()
    const config = await store.getConfig('config-1')
    
    expect(config).not.toBeNull()
    expect(config?.id).toBe('config-1')
    expect(config?.alias).toBe('工作账号')
    expect(config?.apiKey).toBe('sk-t******t-1')
    expect(config?.hasApiKey).toBe(true)
    
    const state = useAPIConfigStore.getState()
    expect(state.currentConfig).toEqual(config)
    expect(state.isLoading).toBe(false)
    expect(state.error).toBeNull()
  })
  
  it('应该处理配置不存在的情况', async () => {
    mockPywebviewAPI.ai_get_config_detail.mockResolvedValue({
      success: false,
      error_message: '配置不存在'
    })
    
    const store = useAPIConfigStore.getState()
    const config = await store.getConfig('non-existent-id')
    
    expect(config).toBeNull()
    
    const state = useAPIConfigStore.getState()
    expect(state.currentConfig).toBeNull()
    expect(state.error).toBe('配置不存在')
  })
})

describe('useAPIConfigStore - createConfig', () => {
  it('应该成功创建配置', async () => {
    const newConfig: APIConfigInput = {
      alias: '新配置',
      provider: 'openai',
      apiKey: 'sk-new-key',
      baseUrl: 'https://api.openai.com/v1',
      model: 'gpt-4',
      models: ['gpt-4'],
      extra: {}
    }
    
    mockPywebviewAPI.ai_create_config.mockResolvedValue({
      success: true,
      config_id: 'new-config-id'
    })
    
    mockPywebviewAPI.ai_list_configs.mockResolvedValue({
      success: true,
      configs: []
    })
    
    const store = useAPIConfigStore.getState()
    const configId = await store.createConfig(newConfig)
    
    expect(configId).toBe('new-config-id')
    expect(mockPywebviewAPI.ai_create_config).toHaveBeenCalledWith({
      alias: '新配置',
      provider: 'openai',
      api_key: 'sk-new-key',
      base_url: 'https://api.openai.com/v1',
      model: 'gpt-4',
      models: ['gpt-4'],
      extra: {},
      use_system_proxy: false
    })
    
    // 验证创建后重新加载了配置列表
    expect(mockPywebviewAPI.ai_list_configs).toHaveBeenCalled()
  })
  
  it('应该处理创建失败的情况', async () => {
    const newConfig: APIConfigInput = {
      alias: '',
      provider: 'openai',
      apiKey: 'sk-key',
      model: 'gpt-4'
    }
    
    mockPywebviewAPI.ai_create_config.mockResolvedValue({
      success: false,
      error_message: '配置别名不能为空'
    })
    
    const store = useAPIConfigStore.getState()
    const configId = await store.createConfig(newConfig)
    
    expect(configId).toBeNull()
    
    const state = useAPIConfigStore.getState()
    expect(state.error).toBe('配置别名不能为空')
  })
  
  it('应该正确转换字段名（驼峰转下划线）', async () => {
    const newConfig: APIConfigInput = {
      alias: '测试',
      provider: 'openai',
      apiKey: 'sk-test',
      baseUrl: 'https://api.openai.com/v1',
      model: 'gpt-4'
    }
    
    mockPywebviewAPI.ai_create_config.mockResolvedValue({
      success: true,
      config_id: 'test-id'
    })
    
    mockPywebviewAPI.ai_list_configs.mockResolvedValue({
      success: true,
      configs: []
    })
    
    const store = useAPIConfigStore.getState()
    await store.createConfig(newConfig)
    
    // 验证传递给后端的数据使用下划线命名
    expect(mockPywebviewAPI.ai_create_config).toHaveBeenCalledWith({
      alias: '测试',
      provider: 'openai',
      api_key: 'sk-test',
      base_url: 'https://api.openai.com/v1',
      model: 'gpt-4',
      models: undefined,
      extra: undefined,
      use_system_proxy: false
    })
  })
})

describe('useAPIConfigStore - updateConfig', () => {
  it('应该成功更新配置', async () => {
    const updatedConfig: APIConfigInput = {
      alias: '更新后的配置',
      provider: 'openai',
      apiKey: 'sk-updated-key',
      baseUrl: 'https://api.openai.com/v1',
      model: 'gpt-4',
      models: ['gpt-4'],
      extra: {}
    }
    
    mockPywebviewAPI.ai_update_config.mockResolvedValue({
      success: true
    })
    
    mockPywebviewAPI.ai_list_configs.mockResolvedValue({
      success: true,
      configs: []
    })
    
    const store = useAPIConfigStore.getState()
    const success = await store.updateConfig('config-1', updatedConfig)
    
    expect(success).toBe(true)
    expect(mockPywebviewAPI.ai_update_config).toHaveBeenCalledWith('config-1', {
      alias: '更新后的配置',
      provider: 'openai',
      api_key: 'sk-updated-key',
      base_url: 'https://api.openai.com/v1',
      model: 'gpt-4',
      models: ['gpt-4'],
      extra: {},
      use_system_proxy: false
    })
    
    // 验证更新后重新加载了配置列表
    expect(mockPywebviewAPI.ai_list_configs).toHaveBeenCalled()
  })
  
  it('应该处理更新失败的情况', async () => {
    const updatedConfig: APIConfigInput = {
      alias: '更新配置',
      provider: 'openai',
      apiKey: 'sk-key',
      model: 'gpt-4'
    }
    
    mockPywebviewAPI.ai_update_config.mockResolvedValue({
      success: false,
      error_message: '配置不存在'
    })
    
    const store = useAPIConfigStore.getState()
    const success = await store.updateConfig('non-existent-id', updatedConfig)
    
    expect(success).toBe(false)
    
    const state = useAPIConfigStore.getState()
    expect(state.error).toBe('配置不存在')
  })
})

describe('useAPIConfigStore - 密钥掩码契约', () => {
  it('更新时 API Key 留空应不下发 api_key 字段', async () => {
    mockPywebviewAPI.ai_update_config.mockResolvedValue({ success: true })
    mockPywebviewAPI.ai_list_configs.mockResolvedValue({ success: true, configs: [] })
    
    const store = useAPIConfigStore.getState()
    await store.updateConfig('config-1', {
      alias: '仅改名',
      provider: 'openai',
      apiKey: '',
      model: 'gpt-4'
    })
    
    const payload = mockPywebviewAPI.ai_update_config.mock.calls[0][1]
    expect(payload).not.toHaveProperty('api_key')
  })
  
  it('测试已保存配置时应带 config_id 而不是密钥', async () => {
    mockPywebviewAPI.ai_test_connection.mockResolvedValue({
      success: true,
      message: '连接成功',
      latency: 12
    })
    
    const store = useAPIConfigStore.getState()
    await store.testConnection('openai', {
      id: 'config-1',
      alias: '工作账号',
      provider: 'openai',
      apiKey: '',
      model: 'gpt-4'
    })
    
    const payload = mockPywebviewAPI.ai_test_connection.mock.calls[0][1]
    expect(payload.config_id).toBe('config-1')
    expect(payload).not.toHaveProperty('api_key')
  })
  
  it('测试连接时表单里有新密钥才下发 api_key', async () => {
    mockPywebviewAPI.ai_test_connection.mockResolvedValue({
      success: true,
      message: '连接成功',
      latency: 12
    })
    
    const store = useAPIConfigStore.getState()
    await store.testConnection('openai', {
      alias: '新配置',
      provider: 'openai',
      apiKey: 'sk-typed-by-user',
      model: 'gpt-4'
    })
    
    const [, payload] = mockPywebviewAPI.ai_test_connection.mock.calls[0]
    expect(payload.api_key).toBe('sk-typed-by-user')
    expect(payload).not.toHaveProperty('config_id')
  })
  
  it('获取模型列表应把 configId 传给后端', async () => {
    mockPywebviewAPI.ai_get_available_models.mockResolvedValue({
      success: true,
      models: ['gpt-4']
    })
    
    const store = useAPIConfigStore.getState()
    const models = await store.getAvailableModels('openai', {
      apiKey: 'sk-t******key',
      configId: 'config-1'
    })
    
    expect(models).toEqual(['gpt-4'])
    const [, payload] = mockPywebviewAPI.ai_get_available_models.mock.calls[0]
    expect(payload.config_id).toBe('config-1')
  })
})

describe('useAPIConfigStore - deleteConfig', () => {
  it('应该成功删除配置', async () => {
    mockPywebviewAPI.ai_delete_config.mockResolvedValue({
      success: true
    })
    
    mockPywebviewAPI.ai_list_configs.mockResolvedValue({
      success: true,
      configs: []
    })
    
    const store = useAPIConfigStore.getState()
    const success = await store.deleteConfig('config-1')
    
    expect(success).toBe(true)
    expect(mockPywebviewAPI.ai_delete_config).toHaveBeenCalledWith('config-1')
    
    // 验证删除后重新加载了配置列表
    expect(mockPywebviewAPI.ai_list_configs).toHaveBeenCalled()
  })
  
  it('应该处理删除失败的情况', async () => {
    mockPywebviewAPI.ai_delete_config.mockResolvedValue({
      success: false,
      error_message: '配置不存在'
    })
    
    const store = useAPIConfigStore.getState()
    const success = await store.deleteConfig('non-existent-id')
    
    expect(success).toBe(false)
    
    const state = useAPIConfigStore.getState()
    expect(state.error).toBe('配置不存在')
  })
})

describe('useAPIConfigStore - setDefaultConfig', () => {
  it('应该成功设置默认配置', async () => {
    mockPywebviewAPI.ai_set_default_config.mockResolvedValue({
      success: true
    })
    
    mockPywebviewAPI.ai_list_configs.mockResolvedValue({
      success: true,
      configs: []
    })
    
    const store = useAPIConfigStore.getState()
    const success = await store.setDefaultConfig('config-1')
    
    expect(success).toBe(true)
    expect(mockPywebviewAPI.ai_set_default_config).toHaveBeenCalledWith('config-1')
    
    // 验证设置后重新加载了配置列表
    expect(mockPywebviewAPI.ai_list_configs).toHaveBeenCalled()
  })
  
  it('应该处理设置失败的情况', async () => {
    mockPywebviewAPI.ai_set_default_config.mockResolvedValue({
      success: false,
      error_message: '配置不存在'
    })
    
    const store = useAPIConfigStore.getState()
    const success = await store.setDefaultConfig('non-existent-id')
    
    expect(success).toBe(false)
    
    const state = useAPIConfigStore.getState()
    expect(state.error).toBe('配置不存在')
  })
})

describe('useAPIConfigStore - testConfig', () => {
  it('应该成功测试配置（可用）', async () => {
    mockPywebviewAPI.ai_test_config.mockResolvedValue({
      success: true,
      available: true,
      latency: 123.45,
      message: '连接成功'
    })
    
    mockPywebviewAPI.ai_list_configs.mockResolvedValue({
      success: true,
      configs: []
    })
    
    const store = useAPIConfigStore.getState()
    const result = await store.testConfig('config-1')
    
    expect(result.success).toBe(true)
    expect(result.available).toBe(true)
    expect(result.latency).toBe(123.45)
    expect(result.message).toBe('连接成功')
    expect(mockPywebviewAPI.ai_test_config).toHaveBeenCalledWith('config-1')
    
    // 验证测试后重新加载了配置列表
    expect(mockPywebviewAPI.ai_list_configs).toHaveBeenCalled()
  })
  
  it('应该成功测试配置（不可用）', async () => {
    mockPywebviewAPI.ai_test_config.mockResolvedValue({
      success: true,
      available: false,
      message: '连接失败'
    })
    
    mockPywebviewAPI.ai_list_configs.mockResolvedValue({
      success: true,
      configs: []
    })
    
    const store = useAPIConfigStore.getState()
    const result = await store.testConfig('config-1')
    
    expect(result.success).toBe(true)
    expect(result.available).toBe(false)
    expect(result.message).toBe('连接失败')
  })
  
  it('应该处理测试失败的情况', async () => {
    mockPywebviewAPI.ai_test_config.mockResolvedValue({
      success: false,
      error_message: '配置不存在'
    })
    
    const store = useAPIConfigStore.getState()
    const result = await store.testConfig('non-existent-id')
    
    expect(result.success).toBe(false)
    expect(result.available).toBe(false)
    expect(result.errorMessage).toBe('配置不存在')
    
    const state = useAPIConfigStore.getState()
    expect(state.error).toBe('配置不存在')
  })
  
  it('应该处理测试异常', async () => {
    mockPywebviewAPI.ai_test_config.mockRejectedValue(new Error('网络超时'))
    
    const store = useAPIConfigStore.getState()
    const result = await store.testConfig('config-1')
    
    expect(result.success).toBe(false)
    expect(result.available).toBe(false)
    expect(result.errorMessage).toContain('网络超时')
  })
})

describe('useAPIConfigStore - 辅助方法', () => {
  it('setCurrentConfig 应该正确设置当前配置', () => {
    const mockConfig: APIConfig = {
      id: 'config-1',
      alias: '测试配置',
      provider: 'openai',
      apiKey: 'sk-test',
      baseUrl: 'https://api.openai.com/v1',
      model: 'gpt-4',
      models: ['gpt-4'],
      extra: {},
      isDefault: false,
      status: 'untested',
      usageCount: 0,
      createdAt: '2024-01-01T00:00:00Z',
      updatedAt: '2024-01-01T00:00:00Z'
    }
    
    const store = useAPIConfigStore.getState()
    store.setCurrentConfig(mockConfig)
    
    const state = useAPIConfigStore.getState()
    expect(state.currentConfig).toEqual(mockConfig)
  })
  
  it('setCurrentConfig 应该能够清除当前配置', () => {
    const store = useAPIConfigStore.getState()
    store.setCurrentConfig(null)
    
    const state = useAPIConfigStore.getState()
    expect(state.currentConfig).toBeNull()
  })
  
  it('clearError 应该清除错误信息', () => {
    const store = useAPIConfigStore.getState()
    
    // 先设置错误
    useAPIConfigStore.setState({ error: '测试错误' })
    expect(useAPIConfigStore.getState().error).toBe('测试错误')
    
    // 清除错误
    store.clearError()
    
    const state = useAPIConfigStore.getState()
    expect(state.error).toBeNull()
  })
})

describe('useAPIConfigStore - 状态更新正确性', () => {
  it('加载配置时应该正确更新 isLoading 状态', async () => {
    let resolvePromise: (value: any) => void
    const promise = new Promise((resolve) => {
      resolvePromise = resolve
    })
    
    mockPywebviewAPI.ai_list_configs.mockReturnValue(promise)
    
    const store = useAPIConfigStore.getState()
    const loadPromise = store.loadConfigs()
    
    // 加载中
    await new Promise(resolve => setTimeout(resolve, 0))
    expect(useAPIConfigStore.getState().isLoading).toBe(true)
    
    // 完成加载
    resolvePromise!({ success: true, configs: [] })
    await loadPromise
    
    expect(useAPIConfigStore.getState().isLoading).toBe(false)
  })
  
  it('操作失败时应该保留错误信息', async () => {
    mockPywebviewAPI.ai_create_config.mockResolvedValue({
      success: false,
      error_message: '验证失败'
    })
    
    const store = useAPIConfigStore.getState()
    await store.createConfig({
      alias: '',
      provider: 'openai',
      apiKey: 'sk-key',
      model: 'gpt-4'
    })
    
    const state = useAPIConfigStore.getState()
    expect(state.error).toBe('验证失败')
    expect(state.isLoading).toBe(false)
  })
  
  it('成功操作后应该清除错误信息', async () => {
    // 先设置错误
    useAPIConfigStore.setState({ error: '之前的错误' })
    
    mockPywebviewAPI.ai_list_configs.mockResolvedValue({
      success: true,
      configs: []
    })
    
    const store = useAPIConfigStore.getState()
    await store.loadConfigs()
    
    const state = useAPIConfigStore.getState()
    expect(state.error).toBeNull()
  })
})

describe('useAPIConfigStore - searchConfigs', () => {
  beforeEach(() => {
    // 设置测试数据
    const mockConfigs: APIConfig[] = [
      {
        id: 'config-1',
        alias: '工作账号',
        provider: 'openai',
        apiKey: 'sk-test-1',
        baseUrl: 'https://api.openai.com/v1',
        model: 'gpt-4',
        models: ['gpt-4'],
        extra: {},
        isDefault: true,
        status: 'available',
        usageCount: 10,
        createdAt: '2024-01-01T00:00:00Z',
        updatedAt: '2024-01-01T00:00:00Z'
      },
      {
        id: 'config-2',
        alias: '个人账号',
        provider: 'openai',
        apiKey: 'sk-test-2',
        baseUrl: 'https://api.openai.com/v1',
        model: 'gpt-3.5-turbo',
        models: ['gpt-3.5-turbo'],
        extra: {},
        isDefault: false,
        status: 'untested',
        usageCount: 0,
        createdAt: '2024-01-01T00:00:00Z',
        updatedAt: '2024-01-01T00:00:00Z'
      },
      {
        id: 'config-3',
        alias: 'XFlow 配置',
        provider: 'xflow',
        apiKey: 'xf-test-key',
        model: 'gpt-4',
        models: ['gpt-4'],
        extra: {},
        isDefault: false,
        status: 'available',
        usageCount: 5,
        createdAt: '2024-01-01T00:00:00Z',
        updatedAt: '2024-01-01T00:00:00Z'
      },
      {
        id: 'config-4',
        alias: '测试配置',
        provider: 'spark',
        apiKey: 'spark-key',
        model: 'spark-v3',
        models: ['spark-v3'],
        extra: {},
        isDefault: false,
        status: 'untested',
        usageCount: 0,
        createdAt: '2024-01-01T00:00:00Z',
        updatedAt: '2024-01-01T00:00:00Z'
      }
    ]
    
    useAPIConfigStore.setState({ configs: mockConfigs })
  })
  
  it('应该根据别名搜索配置（不区分大小写）', () => {
    const store = useAPIConfigStore.getState()
    
    // 搜索 "工作"
    const results1 = store.searchConfigs('工作')
    expect(results1).toHaveLength(1)
    expect(results1[0].alias).toBe('工作账号')
    
    // 搜索 "账号"（匹配多个）
    const results2 = store.searchConfigs('账号')
    expect(results2).toHaveLength(2)
    expect(results2.map(c => c.alias)).toContain('工作账号')
    expect(results2.map(c => c.alias)).toContain('个人账号')
    
    // 搜索 "测试"
    const results3 = store.searchConfigs('测试')
    expect(results3).toHaveLength(1)
    expect(results3[0].alias).toBe('测试配置')
  })
  
  it('应该根据服务商名称搜索配置（不区分大小写）', () => {
    const store = useAPIConfigStore.getState()
    
    // 搜索 "openai"
    const results1 = store.searchConfigs('openai')
    expect(results1).toHaveLength(2)
    expect(results1.every(c => c.provider === 'openai')).toBe(true)
    
    // 搜索 "OPENAI"（大写，应该不区分大小写）
    const results2 = store.searchConfigs('OPENAI')
    expect(results2).toHaveLength(2)
    
    // 搜索 "xflow"
    const results3 = store.searchConfigs('xflow')
    expect(results3).toHaveLength(1)
    expect(results3[0].provider).toBe('xflow')
    
    // 搜索 "spark"
    const results4 = store.searchConfigs('spark')
    expect(results4).toHaveLength(1)
    expect(results4[0].provider).toBe('spark')
  })
  
  it('应该匹配别名或服务商名称中包含关键词的配置', () => {
    const store = useAPIConfigStore.getState()
    
    // 搜索 "flow"（匹配 xflow 服务商和 XFlow 配置别名）
    const results = store.searchConfigs('flow')
    expect(results).toHaveLength(1)
    expect(results[0].alias).toBe('XFlow 配置')
    expect(results[0].provider).toBe('xflow')
  })
  
  it('空搜索关键词应该返回所有配置', () => {
    const store = useAPIConfigStore.getState()
    
    // 空字符串
    const results1 = store.searchConfigs('')
    expect(results1).toHaveLength(4)
    
    // 只有空格
    const results2 = store.searchConfigs('   ')
    expect(results2).toHaveLength(4)
  })
  
  it('搜索无结果应该返回空数组', () => {
    const store = useAPIConfigStore.getState()
    
    const results = store.searchConfigs('不存在的关键词')
    expect(results).toHaveLength(0)
    expect(results).toEqual([])
  })
  
  it('搜索应该不区分大小写', () => {
    const store = useAPIConfigStore.getState()
    
    // 小写搜索
    const results1 = store.searchConfigs('xflow')
    expect(results1).toHaveLength(1)
    
    // 大写搜索
    const results2 = store.searchConfigs('XFLOW')
    expect(results2).toHaveLength(1)
    
    // 混合大小写搜索
    const results3 = store.searchConfigs('XFlow')
    expect(results3).toHaveLength(1)
    
    // 验证结果相同
    expect(results1[0].id).toBe(results2[0].id)
    expect(results2[0].id).toBe(results3[0].id)
  })
})

describe('useAPIConfigStore - filterByProvider', () => {
  beforeEach(() => {
    // 设置测试数据
    const mockConfigs: APIConfig[] = [
      {
        id: 'config-1',
        alias: '工作账号',
        provider: 'openai',
        apiKey: 'sk-test-1',
        model: 'gpt-4',
        models: ['gpt-4'],
        extra: {},
        isDefault: true,
        status: 'available',
        usageCount: 10,
        createdAt: '2024-01-01T00:00:00Z',
        updatedAt: '2024-01-01T00:00:00Z'
      },
      {
        id: 'config-2',
        alias: '个人账号',
        provider: 'openai',
        apiKey: 'sk-test-2',
        model: 'gpt-3.5-turbo',
        models: ['gpt-3.5-turbo'],
        extra: {},
        isDefault: false,
        status: 'untested',
        usageCount: 0,
        createdAt: '2024-01-01T00:00:00Z',
        updatedAt: '2024-01-01T00:00:00Z'
      },
      {
        id: 'config-3',
        alias: 'XFlow 配置',
        provider: 'xflow',
        apiKey: 'xf-test-key',
        model: 'gpt-4',
        models: ['gpt-4'],
        extra: {},
        isDefault: false,
        status: 'available',
        usageCount: 5,
        createdAt: '2024-01-01T00:00:00Z',
        updatedAt: '2024-01-01T00:00:00Z'
      },
      {
        id: 'config-4',
        alias: '测试配置',
        provider: 'spark',
        apiKey: 'spark-key',
        model: 'spark-v3',
        models: ['spark-v3'],
        extra: {},
        isDefault: false,
        status: 'untested',
        usageCount: 0,
        createdAt: '2024-01-01T00:00:00Z',
        updatedAt: '2024-01-01T00:00:00Z'
      }
    ]
    
    useAPIConfigStore.setState({ configs: mockConfigs })
  })
  
  it('应该只返回指定服务商的配置', () => {
    const store = useAPIConfigStore.getState()
    
    // 筛选 openai
    const results1 = store.filterByProvider('openai')
    expect(results1).toHaveLength(2)
    expect(results1.every(c => c.provider === 'openai')).toBe(true)
    
    // 筛选 xflow
    const results2 = store.filterByProvider('xflow')
    expect(results2).toHaveLength(1)
    expect(results2[0].provider).toBe('xflow')
    
    // 筛选 spark
    const results3 = store.filterByProvider('spark')
    expect(results3).toHaveLength(1)
    expect(results3[0].provider).toBe('spark')
  })
  
  it('空服务商名称应该返回所有配置', () => {
    const store = useAPIConfigStore.getState()
    
    // 空字符串
    const results1 = store.filterByProvider('')
    expect(results1).toHaveLength(4)
    
    // 只有空格
    const results2 = store.filterByProvider('   ')
    expect(results2).toHaveLength(4)
  })
  
  it('筛选不存在的服务商应该返回空数组', () => {
    const store = useAPIConfigStore.getState()
    
    const results = store.filterByProvider('不存在的服务商')
    expect(results).toHaveLength(0)
    expect(results).toEqual([])
  })
  
  it('筛选结果应该包含该服务商的所有配置', () => {
    const store = useAPIConfigStore.getState()
    
    const results = store.filterByProvider('openai')
    expect(results).toHaveLength(2)
    
    // 验证包含所有 openai 配置
    const aliases = results.map(c => c.alias)
    expect(aliases).toContain('工作账号')
    expect(aliases).toContain('个人账号')
  })
})

describe('useAPIConfigStore - 搜索和筛选组合使用', () => {
  beforeEach(() => {
    // 设置测试数据
    const mockConfigs: APIConfig[] = [
      {
        id: 'config-1',
        alias: '工作账号',
        provider: 'openai',
        apiKey: 'sk-test-1',
        model: 'gpt-4',
        models: ['gpt-4'],
        extra: {},
        isDefault: true,
        status: 'available',
        usageCount: 10,
        createdAt: '2024-01-01T00:00:00Z',
        updatedAt: '2024-01-01T00:00:00Z'
      },
      {
        id: 'config-2',
        alias: '个人账号',
        provider: 'openai',
        apiKey: 'sk-test-2',
        model: 'gpt-3.5-turbo',
        models: ['gpt-3.5-turbo'],
        extra: {},
        isDefault: false,
        status: 'untested',
        usageCount: 0,
        createdAt: '2024-01-01T00:00:00Z',
        updatedAt: '2024-01-01T00:00:00Z'
      },
      {
        id: 'config-3',
        alias: '工作专用',
        provider: 'xflow',
        apiKey: 'xf-test-key',
        model: 'gpt-4',
        models: ['gpt-4'],
        extra: {},
        isDefault: false,
        status: 'available',
        usageCount: 5,
        createdAt: '2024-01-01T00:00:00Z',
        updatedAt: '2024-01-01T00:00:00Z'
      }
    ]
    
    useAPIConfigStore.setState({ configs: mockConfigs })
  })
  
  it('应该能够先筛选再搜索', () => {
    const store = useAPIConfigStore.getState()
    
    // 先筛选 openai
    const filtered = store.filterByProvider('openai')
    expect(filtered).toHaveLength(2)
    
    // 在筛选结果中搜索 "工作"
    const searchResults = filtered.filter(config => {
      const lowerQuery = '工作'.toLowerCase()
      return config.alias.toLowerCase().includes(lowerQuery) || 
             config.provider.toLowerCase().includes(lowerQuery)
    })
    
    expect(searchResults).toHaveLength(1)
    expect(searchResults[0].alias).toBe('工作账号')
    expect(searchResults[0].provider).toBe('openai')
  })
  
  it('应该能够先搜索再筛选', () => {
    const store = useAPIConfigStore.getState()
    
    // 先搜索 "工作"
    const searched = store.searchConfigs('工作')
    expect(searched).toHaveLength(2)
    
    // 在搜索结果中筛选 openai
    const filterResults = searched.filter(config => config.provider === 'openai')
    
    expect(filterResults).toHaveLength(1)
    expect(filterResults[0].alias).toBe('工作账号')
    expect(filterResults[0].provider).toBe('openai')
  })
})
