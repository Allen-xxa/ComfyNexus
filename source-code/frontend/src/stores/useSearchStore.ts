/**
 * 搜索状态管理
 * 
 * 负责管理搜索配置和联网搜索开关状态
 */

import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { SearchConfig, SearchTestResult } from '@/types/search'

/**
 * 搜索 Store 状态接口
 */
interface SearchStore {
  // 配置
  config: SearchConfig | null
  
  // 联网搜索开关（按话题存储）
  webSearchEnabled: Record<string, boolean>
  
  // 加载配置
  loadConfig: () => Promise<void>
  
  // 更新配置
  updateConfig: (config: SearchConfig) => Promise<boolean>
  
  // 测试连接
  testConnection: (provider: string, config: any) => Promise<SearchTestResult>
  
  // 设置联网搜索开关
  setWebSearchEnabled: (topicId: string, enabled: boolean) => void
  
  // 获取联网搜索开关
  getWebSearchEnabled: (topicId: string) => boolean
}

/**
 * 检查是否在开发环境
 */
const isDevelopment = (): boolean => {
  return !window.pywebview || !window.pywebview.api
}

/**
 * 搜索 Store 实现
 */
export const useSearchStore = create<SearchStore>()(
  persist(
    (set, get) => ({
      config: null,
      webSearchEnabled: {},
      
      /**
       * 加载搜索配置
       */
      loadConfig: async () => {
        try {
          console.log('[useSearchStore] 加载搜索配置')
          
          // 开发环境使用 Mock
          if (isDevelopment()) {
            console.log('[useSearchStore] 开发环境：使用 Mock 配置')
            const mockConfig: SearchConfig = {
              enabled: true,
              provider: 'duckduckgo',
              max_results: 5,
              timeout: 10,
              providers: {
                duckduckgo: {
                  enabled: true
                },
                google: {
                  enabled: false,
                  api_key: '',
                  search_engine_id: ''
                },
                tavily: {
                  enabled: false,
                  api_key: '',
                  search_depth: 'basic'
                }
              }
            }
            set({ config: mockConfig })
            return
          }
          
          // 生产环境：调用后端 API
          const response = await window.pywebview.api.ai_get_search_config()
          
          if (response.success) {
            set({ config: response.config })
            console.log('[useSearchStore] 配置加载成功')
          } else {
            console.error('[useSearchStore] 加载配置失败:', response.error)
          }
        } catch (error) {
          console.error('[useSearchStore] 加载配置异常:', error)
        }
      },
      
      /**
       * 更新搜索配置
       */
      updateConfig: async (config: SearchConfig) => {
        try {
          console.log('[useSearchStore] 更新搜索配置')
          
          // 开发环境直接更新
          if (isDevelopment()) {
            console.log('[useSearchStore] 开发环境：直接更新配置')
            set({ config })
            return true
          }
          
          // 生产环境：调用后端 API
          const response = await window.pywebview.api.ai_update_search_config(config)
          
          if (response.success) {
            set({ config })
            console.log('[useSearchStore] 配置更新成功')
            return true
          } else {
            console.error('[useSearchStore] 更新配置失败:', response.error)
            return false
          }
        } catch (error) {
          console.error('[useSearchStore] 更新配置异常:', error)
          return false
        }
      },
      
      /**
       * 测试搜索引擎连接
       */
      testConnection: async (provider: string, config: any) => {
        try {
          console.log('[useSearchStore] 测试连接:', provider)
          
          // 开发环境返回 Mock 结果
          if (isDevelopment()) {
            console.log('[useSearchStore] 开发环境：返回 Mock 测试结果')
            await new Promise(resolve => setTimeout(resolve, 1000))
            return {
              success: true,
              message: '连接成功（开发环境模拟）',
              latency: 123
            }
          }
          
          // 生产环境：调用后端 API
          const response = await window.pywebview.api.ai_test_search_connection(provider, config)
          
          return {
            success: response.success,
            message: response.message,
            latency: response.latency
          }
        } catch (error) {
          console.error('[useSearchStore] 测试连接异常:', error)
          return {
            success: false,
            message: `测试失败: ${error}`
          }
        }
      },
      
      /**
       * 设置联网搜索开关
       */
      setWebSearchEnabled: (topicId: string, enabled: boolean) => {
        set((state) => ({
          webSearchEnabled: {
            ...state.webSearchEnabled,
            [topicId]: enabled
          }
        }))
        console.log('[useSearchStore] 设置联网搜索:', topicId, enabled)
      },
      
      /**
       * 获取联网搜索开关
       */
      getWebSearchEnabled: (topicId: string) => {
        return get().webSearchEnabled[topicId] || false
      }
    }),
    {
      name: 'search-storage',
      partialize: (state) => ({ 
        webSearchEnabled: state.webSearchEnabled 
      })
    }
  )
)
