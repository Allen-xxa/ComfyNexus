/**
 * 模型选择器状态管理
 * 
 * 管理对话级别的模型配置选择和全局默认配置
 */

import { create } from 'zustand'
import { waitForAPI } from '../utils/pywebview'

interface ModelSelectorStore {
  // 状态
  activeConfigs: Map<string, string>  // topicId -> configId 映射
  defaultConfigId: string | null      // 默认配置 ID
  isLoading: boolean
  error: string | null
  
  // Actions
  loadDefaultConfig: () => Promise<void>
  setActiveConfig: (topicId: string, configId: string) => Promise<boolean>
  getActiveConfig: (topicId: string) => string | null
  setDefaultConfig: (configId: string) => Promise<boolean>
  clearDefaultConfig: () => Promise<boolean>
  getConfigForNewTopic: () => string | null
  handleConfigDeleted: (configId: string) => void
  
  // 内部方法
  _setLoading: (loading: boolean) => void
  _setError: (error: string | null) => void
}

export const useModelSelectorStore = create<ModelSelectorStore>((set, get) => ({
  // 初始状态
  activeConfigs: new Map(),
  defaultConfigId: null,
  isLoading: false,
  error: null,
  
  // 加载默认配置
  loadDefaultConfig: async () => {
    try {
      get()._setLoading(true)
      get()._setError(null)
      
      await waitForAPI()
      
      const response = await window.pywebview.api.ai_get_default_config()
      
      if (response.success && response.config_id) {
        set({ defaultConfigId: response.config_id })
        return
      }
      
      // 未设置默认配置时回退到已有配置。
      // 此前只要用户没手动点过「设为默认」，defaultConfigId 就恒为 null，
      // 导致终端日志分析等功能误报「请先配置 API 密钥」，即使配置本身可用。
      const listResult = await window.pywebview.api.ai_list_configs()
      if (listResult?.success && Array.isArray(listResult.configs) && listResult.configs.length > 0) {
        const preferred =
          listResult.configs.find((c: any) => c.status === 'available') ??
          listResult.configs.find((c: any) => c.is_default) ??
          listResult.configs[0]
        set({ defaultConfigId: preferred.id })
        return
      }
      
      set({ defaultConfigId: null })
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '获取默认配置失败'
      get()._setError(errorMessage)
      console.error('加载默认配置失败:', error)
    } finally {
      get()._setLoading(false)
    }
  },
  
  // 设置对话的激活配置
  setActiveConfig: async (topicId: string, configId: string): Promise<boolean> => {
    try {
      get()._setLoading(true)
      get()._setError(null)
      
      await waitForAPI()
      
      const response = await window.pywebview.api.ai_set_topic_config(topicId, configId)
      
      if (response.success) {
        // 更新本地缓存
        const newActiveConfigs = new Map(get().activeConfigs)
        newActiveConfigs.set(topicId, configId)
        set({ activeConfigs: newActiveConfigs })
        return true
      } else {
        throw new Error(response.error_message || '设置对话配置失败')
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '设置对话配置失败'
      get()._setError(errorMessage)
      console.error('设置对话配置失败:', error)
      return false
    } finally {
      get()._setLoading(false)
    }
  },
  
  // 获取对话的激活配置
  getActiveConfig: (topicId: string): string | null => {
    // 先从缓存中获取
    const cached = get().activeConfigs.get(topicId)
    if (cached) {
      return cached
    }
    
    // 缓存未命中，异步加载
    waitForAPI().then(async () => {
      try {
        const response = await window.pywebview.api.ai_get_topic_config(topicId)
        
        if (response.success && response.config_id) {
          // 更新缓存
          const newActiveConfigs = new Map(get().activeConfigs)
          newActiveConfigs.set(topicId, response.config_id)
          set({ activeConfigs: newActiveConfigs })
        }
      } catch (error) {
        console.error('获取对话配置失败:', error)
      }
    })
    
    // 返回 null（异步加载中）
    return null
  },
  
  // 设置默认配置
  setDefaultConfig: async (configId: string): Promise<boolean> => {
    try {
      get()._setLoading(true)
      get()._setError(null)
      
      await waitForAPI()
      
      const response = await window.pywebview.api.ai_set_default_config(configId)
      
      if (response.success) {
        set({ defaultConfigId: configId })
        return true
      } else {
        throw new Error(response.error_message || '设置默认配置失败')
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '设置默认配置失败'
      get()._setError(errorMessage)
      console.error('设置默认配置失败:', error)
      return false
    } finally {
      get()._setLoading(false)
    }
  },
  
  // 清除默认配置
  clearDefaultConfig: async (): Promise<boolean> => {
    try {
      get()._setLoading(true)
      get()._setError(null)
      
      // 调用后端 API 清除默认配置
      // 注意：这里假设 ai_set_default_config 可以接受 null 来清除
      // 如果后端没有专门的清除 API，可能需要添加
      set({ defaultConfigId: null })
      return true
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '清除默认配置失败'
      get()._setError(errorMessage)
      console.error('清除默认配置失败:', error)
      return false
    } finally {
      get()._setLoading(false)
    }
  },
  
  // 获取新对话应该使用的配置
  getConfigForNewTopic: (): string | null => {
    return get().defaultConfigId
  },
  
  // 处理配置被删除的情况
  handleConfigDeleted: (configId: string) => {
    // 如果删除的是默认配置，清除默认配置 ID
    if (get().defaultConfigId === configId) {
      set({ defaultConfigId: null })
    }
    
    // 清除所有使用该配置的对话缓存
    const newActiveConfigs = new Map(get().activeConfigs)
    for (const [topicId, activeConfigId] of newActiveConfigs.entries()) {
      if (activeConfigId === configId) {
        newActiveConfigs.delete(topicId)
      }
    }
    set({ activeConfigs: newActiveConfigs })
  },
  
  // 内部方法：设置加载状态
  _setLoading: (loading: boolean) => {
    set({ isLoading: loading })
  },
  
  // 内部方法：设置错误信息
  _setError: (error: string | null) => {
    set({ error })
  },
}))
