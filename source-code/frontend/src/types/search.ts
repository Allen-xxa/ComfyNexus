/**
 * 搜索相关类型定义
 */

/**
 * 搜索引擎类型
 */
export type SearchProvider = 'duckduckgo' | 'google' | 'tavily'

/**
 * 搜索结果接口
 */
export interface SearchResult {
  title: string
  url: string
  snippet: string
  source: SearchProvider
}

/**
 * 搜索配置接口
 */
export interface SearchConfig {
  enabled: boolean
  provider: SearchProvider
  max_results: number
  timeout: number
  providers: {
    duckduckgo: {
      enabled: boolean
    }
    google: {
      enabled: boolean
      api_key: string
      search_engine_id: string
    }
    tavily: {
      enabled: boolean
      api_key: string
      search_depth?: string
    }
  }
}

/**
 * 搜索测试结果接口
 */
export interface SearchTestResult {
  success: boolean
  message: string
  latency?: number
}
