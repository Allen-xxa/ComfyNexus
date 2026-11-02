/**
 * 插件市场 API 服务层
 * 
 * 该服务层封装了所有与插件市场相关的 API 调用，
 * 使用 pywebview.api 与后端通信。
 * 
 * 在开发环境中，如果 API 不可用，会自动使用 mock 数据。
 * 
 * 职责：
 * 1. 封装所有 API 调用方法
 * 2. 统一错误处理
 * 3. 类型安全的请求和响应
 * 4. 日志记录
 * 5. 开发环境 mock 数据支持
 */

import {
  PluginListResponse,
  RecommendedPluginsResponse,
  SearchPluginsResponse,
  InstallPluginResponse,
  CheckDependenciesResponse,
  InstallProgressResponse,
  RefreshPluginsResponse,
  ErrorCode,
  ERROR_MESSAGES,
  InstallStatus,
  InstallStage
} from '../types/plugin-marketplace'
import { mockPlugins } from '../mocks/pluginMarketplace'

// ==================== 类型定义 ====================

/**
 * 插件市场 API 方法接口
 * 
 * 这些方法由后端 MarketplaceControllerBridge 提供
 * 注意：这些方法应该已经在 bridge.ts 的 PyWebViewAPI 中定义
 */
interface PluginMarketplaceAPI {
  marketplace_get_plugins: (use_cache: boolean) => Promise<any>
  marketplace_get_recommended_plugins: (use_cache: boolean) => Promise<any>
  marketplace_search_plugins: (keyword: string) => Promise<any>
  marketplace_refresh_plugins: () => Promise<any>
  marketplace_install_plugin: (github_url: string, auto_install_deps: boolean) => Promise<any>
  marketplace_check_dependencies: (github_url: string) => Promise<any>
  marketplace_get_install_progress: (task_id: string) => Promise<any>
  marketplace_cancel_installation: (task_id: string) => Promise<any>
  marketplace_get_installed_plugins_status: () => Promise<any>
}

// ==================== 工具函数 ====================

/**
 * 检查 pywebview API 是否可用
 * 
 * @returns 如果 API 可用返回 true，否则返回 false
 */
function isPyWebViewAvailable(): boolean {
  return typeof window !== 'undefined' && 
         window.pywebview !== undefined && 
         window.pywebview.api !== undefined
}

/**
 * 检查是否为开发环境
 * 
 * @returns 如果是开发环境返回 true
 */
function isDevelopment(): boolean {
  return import.meta.env.DEV
}

/**
 * 获取 pywebview API 实例
 * 
 * @returns pywebview API 实例，如果不可用返回 null
 */
function getAPI(): PluginMarketplaceAPI | null {
  if (!isPyWebViewAvailable()) {
    return null
  }
  return window.pywebview!.api as unknown as PluginMarketplaceAPI
}

/**
 * 统一的错误处理函数
 * 
 * @param error - 错误对象
 * @param context - 错误上下文（用于日志）
 * @returns 格式化的错误响应
 */
function handleError(error: any, context: string): { success: false; error_message: string; error_code: ErrorCode } {
  console.error(`[PluginMarketplaceService] ${context} 失败:`, error)
  
  if (error.error_code && ERROR_MESSAGES[error.error_code as ErrorCode]) {
    return {
      success: false,
      error_message: ERROR_MESSAGES[error.error_code as ErrorCode],
      error_code: error.error_code
    }
  }
  
  const errorMessage = error.message || error.error || error.toString()
  return {
    success: false,
    error_message: errorMessage,
    error_code: ErrorCode.UNKNOWN_ERROR
  }
}

/**
 * 验证响应格式
 * 
 * @param response - API 响应
 * @returns 如果响应格式有效返回 true
 */
function isValidResponse(response: any): boolean {
  return response !== null && 
         response !== undefined && 
         typeof response === 'object' &&
         'success' in response
}

// ==================== Mock 数据处理 ====================

/**
 * 模拟网络延迟
 */
const mockDelay = (ms: number = 300) => new Promise(resolve => setTimeout(resolve, ms))

/**
 * 获取 mock 插件列表
 */
function getMockPlugins(): PluginListResponse {
  console.log('[PluginMarketplaceService] 使用 mock 数据')
  return {
    success: true,
    plugins: mockPlugins
  }
}

/**
 * 获取 mock 已安装插件状态
 */
function getMockInstalledPluginsStatus(): { success: boolean; installed_plugins: string[]; disabled_plugins: string[] } {
  const installed: string[] = []
  const disabled: string[] = []
  
  mockPlugins.forEach(p => {
    const parts = p.repository.split('/')
    const pluginName = parts[parts.length - 1]
    
    if (p.install_status === 'disabled') {
      disabled.push(pluginName)
    } else if (p.is_installed) {
      installed.push(pluginName)
    }
  })
  
  return {
    success: true,
    installed_plugins: installed,
    disabled_plugins: disabled
  }
}

/**
 * 获取 mock 搜索结果
 */
function getMockSearchResults(keyword: string): SearchPluginsResponse {
  const filtered = mockPlugins.filter(p => 
    p.name.toLowerCase().includes(keyword.toLowerCase()) ||
    p.description.toLowerCase().includes(keyword.toLowerCase())
  )
  return {
    success: true,
    plugins: filtered
  }
}

// ==================== API 服务类 ====================

/**
 * 插件市场 API 服务
 * 
 * 提供所有插件市场相关的 API 调用方法
 * 在开发环境中，如果 API 不可用，会自动使用 mock 数据
 */
class PluginMarketplaceService {
  
  /**
   * 获取插件列表
   * 
   * @param useCache - 是否使用缓存（默认 true）
   * @returns 插件列表响应
   */
  async getPlugins(useCache: boolean = true): Promise<PluginListResponse> {
    try {
      console.log(`[PluginMarketplaceService] 获取插件列表，useCache=${useCache}`)
      
      const api = getAPI()
      
      // 如果 API 不可用，使用 mock 数据
      if (!api) {
        if (isDevelopment()) {
          await mockDelay(500)
          return getMockPlugins()
        }
        return {
          success: false,
          error_message: 'API 不可用，请确保在 pywebview 环境中运行',
          error_code: ErrorCode.API_UNAVAILABLE
        }
      }
      
      const response = await api.marketplace_get_plugins(useCache)
      
      if (!isValidResponse(response)) {
        throw new Error('无效的响应格式')
      }
      
      if (!response.success) {
        return {
          success: false,
          error_message: response.error || '获取插件列表失败',
          error_code: ErrorCode.UNKNOWN_ERROR
        }
      }
      
      return {
        success: true,
        plugins: response.plugins || [],
        source: response.source,
        stale: Boolean(response.stale),
        cached_at: response.cached_at,
        warning: response.warning
      }
    } catch (error) {
      return handleError(error, '获取插件列表')
    }
  }
  
  /**
   * 获取推荐插件列表
   */
  async getRecommendedPlugins(useCache: boolean = true): Promise<RecommendedPluginsResponse> {
    try {
      console.log(`[PluginMarketplaceService] 获取推荐插件列表，useCache=${useCache}`)
      
      const api = getAPI()
      
      if (!api) {
        if (isDevelopment()) {
          await mockDelay(300)
          return {
            success: true,
            plugins: mockPlugins.slice(0, 5)
          }
        }
        return {
          success: false,
          error_message: 'API 不可用',
          error_code: ErrorCode.API_UNAVAILABLE
        }
      }
      
      const response = await api.marketplace_get_recommended_plugins(useCache)
      
      if (!isValidResponse(response)) {
        throw new Error('无效的响应格式')
      }
      
      if (!response.success) {
        return {
          success: false,
          error_message: response.error || '获取推荐插件列表失败',
          error_code: ErrorCode.UNKNOWN_ERROR
        }
      }
      
      return {
        success: true,
        plugins: response.plugins || []
      }
    } catch (error) {
      return handleError(error, '获取推荐插件列表')
    }
  }
  
  /**
   * 搜索插件
   */
  async searchPlugins(keyword: string): Promise<SearchPluginsResponse> {
    try {
      console.log(`[PluginMarketplaceService] 搜索插件，关键词: ${keyword}`)
      
      if (!keyword || keyword.trim().length === 0) {
        return {
          success: false,
          error_message: '搜索关键词不能为空',
          error_code: ErrorCode.UNKNOWN_ERROR
        }
      }
      
      const api = getAPI()
      
      if (!api) {
        if (isDevelopment()) {
          await mockDelay(300)
          return getMockSearchResults(keyword)
        }
        return {
          success: false,
          error_message: 'API 不可用',
          error_code: ErrorCode.API_UNAVAILABLE
        }
      }
      
      const response = await api.marketplace_search_plugins(keyword.trim())
      
      if (!isValidResponse(response)) {
        throw new Error('无效的响应格式')
      }
      
      if (!response.success) {
        return {
          success: false,
          error_message: response.error || '搜索插件失败',
          error_code: ErrorCode.UNKNOWN_ERROR
        }
      }
      
      return {
        success: true,
        plugins: response.plugins || []
      }
    } catch (error) {
      return handleError(error, '搜索插件')
    }
  }
  
  /**
   * 刷新插件列表
   */
  async refreshPlugins(): Promise<RefreshPluginsResponse> {
    try {
      console.log('[PluginMarketplaceService] 刷新插件列表')
      
      const api = getAPI()
      
      if (!api) {
        if (isDevelopment()) {
          await mockDelay(500)
          return {
            success: true,
            message: '刷新成功（mock）'
          }
        }
        return {
          success: false,
          error_message: 'API 不可用',
          error_code: ErrorCode.API_UNAVAILABLE
        }
      }
      
      const response = await api.marketplace_refresh_plugins()
      
      if (!isValidResponse(response)) {
        throw new Error('无效的响应格式')
      }
      
      if (!response.success) {
        return {
          success: false,
          error_message: response.error || '刷新插件列表失败',
          error_code: ErrorCode.UNKNOWN_ERROR
        }
      }
      
      return {
        success: true,
        message: response.message || '刷新成功',
        plugins: response.plugins || [],
        source: response.source,
        stale: Boolean(response.stale),
        cached_at: response.cached_at,
        warning: response.warning
      }
    } catch (error) {
      return handleError(error, '刷新插件列表')
    }
  }
  
  /**
   * 安装插件
   */
  async installPlugin(
    githubUrl: string,
    autoInstallDeps: boolean = true
  ): Promise<InstallPluginResponse> {
    try {
      console.log(`[PluginMarketplaceService] 安装插件: ${githubUrl}, autoInstallDeps=${autoInstallDeps}`)
      
      if (!githubUrl || !githubUrl.startsWith('https://') || !githubUrl.includes('github.com/')) {
        return {
          success: false,
          error_message: '无效的 GitHub 地址，必须是包含 github.com 的 HTTPS 地址',
          error_code: ErrorCode.INVALID_URL
        }
      }
      
      const api = getAPI()
      
      if (!api) {
        if (isDevelopment()) {
          await mockDelay(1000)
          return {
            success: true,
            task_id: `mock-task-${Date.now()}`,
            message: '安装任务已启动（mock）'
          }
        }
        return {
          success: false,
          error_message: 'API 不可用',
          error_code: ErrorCode.API_UNAVAILABLE
        }
      }
      
      const response = await api.marketplace_install_plugin(githubUrl, autoInstallDeps)
      
      if (!isValidResponse(response)) {
        throw new Error('无效的响应格式')
      }
      
      if (!response.success) {
        return {
          success: false,
          error_message: response.error || '安装插件失败',
          error_code: response.error_code || ErrorCode.UNKNOWN_ERROR
        }
      }
      
      return {
        success: true,
        task_id: response.task_id,
        message: response.message || '安装任务已启动'
      }
    } catch (error) {
      return handleError(error, '安装插件')
    }
  }
  
  /**
   * 检查插件依赖冲突
   */
  async checkDependencies(githubUrl: string): Promise<CheckDependenciesResponse> {
    try {
      console.log(`[PluginMarketplaceService] 检查依赖冲突: ${githubUrl}`)
      
      if (!githubUrl || !githubUrl.startsWith('https://') || !githubUrl.includes('github.com/')) {
        return {
          success: false,
          error_message: '无效的 GitHub 地址',
          error_code: ErrorCode.INVALID_URL
        }
      }
      
      const api = getAPI()
      
      if (!api) {
        if (isDevelopment()) {
          await mockDelay(300)
          return {
            success: true,
            has_conflicts: false,
            conflicts: []
          }
        }
        return {
          success: false,
          error_message: 'API 不可用',
          error_code: ErrorCode.API_UNAVAILABLE
        }
      }
      
      const response = await api.marketplace_check_dependencies(githubUrl)
      
      if (!isValidResponse(response)) {
        throw new Error('无效的响应格式')
      }
      
      if (!response.success) {
        return {
          success: false,
          error_message: response.error || '检查依赖冲突失败',
          error_code: ErrorCode.UNKNOWN_ERROR
        }
      }
      
      return {
        success: true,
        has_conflicts: response.has_conflicts || false,
        conflicts: response.conflicts || []
      }
    } catch (error) {
      return handleError(error, '检查依赖冲突')
    }
  }
  
  /**
   * 获取安装进度
   */
  async getInstallProgress(taskId: string): Promise<InstallProgressResponse> {
    try {
      console.log(`[PluginMarketplaceService] 获取安装进度: ${taskId}`)
      
      if (!taskId || taskId.trim().length === 0) {
        return {
          success: false,
          error_message: '任务 ID 不能为空',
          error_code: ErrorCode.UNKNOWN_ERROR
        }
      }
      
      const api = getAPI()
      
      if (!api) {
        if (isDevelopment()) {
          await mockDelay(200)
          return {
            success: true,
            task: {
              task_id: taskId,
              plugin_name: 'Mock Plugin',
              github_url: 'https://github.com/mock/plugin',
              stage: InstallStage.SUCCESS,
              progress: 100,
              current_package: '',
              status: InstallStatus.SUCCESS,
              error_message: '',
              log_path: '',
              started_at: new Date().toISOString(),
              finished_at: new Date().toISOString()
            }
          }
        }
        return {
          success: false,
          error_message: 'API 不可用',
          error_code: ErrorCode.API_UNAVAILABLE
        }
      }
      
      const response = await api.marketplace_get_install_progress(taskId)
      
      if (!isValidResponse(response)) {
        throw new Error('无效的响应格式')
      }
      
      if (!response.success) {
        return {
          success: false,
          error_message: response.error || '获取安装进度失败',
          error_code: ErrorCode.UNKNOWN_ERROR
        }
      }
      
      return {
        success: true,
        task: response.progress || response.task
      }
    } catch (error) {
      return handleError(error, '获取安装进度')
    }
  }
  
  /**
   * 取消正在进行的安装任务
   */
  async cancelInstallation(taskId: string): Promise<{ success: boolean; message?: string; error_message?: string; error_code?: ErrorCode }> {
    try {
      console.log(`[PluginMarketplaceService] 取消安装任务: ${taskId}`)
      
      if (!taskId || taskId.trim().length === 0) {
        return {
          success: false,
          error_message: '任务 ID 不能为空',
          error_code: ErrorCode.UNKNOWN_ERROR
        }
      }
      
      const api = getAPI()
      
      if (!api) {
        if (isDevelopment()) {
          await mockDelay(200)
          return {
            success: true,
            message: '安装已取消（mock）'
          }
        }
        return {
          success: false,
          error_message: 'API 不可用',
          error_code: ErrorCode.API_UNAVAILABLE
        }
      }
      
      const response = await api.marketplace_cancel_installation(taskId)
      
      if (!isValidResponse(response)) {
        throw new Error('无效的响应格式')
      }
      
      if (!response.success) {
        return {
          success: false,
          error_message: response.error || '取消安装失败',
          error_code: ErrorCode.UNKNOWN_ERROR
        }
      }
      
      return {
        success: true,
        message: response.message || '安装已取消'
      }
    } catch (error) {
      return handleError(error, '取消安装')
    }
  }
  
  /**
   * 获取当前环境下已安装插件的状态
   */
  async getInstalledPluginsStatus(): Promise<{ 
    success: boolean; 
    installed_plugins: string[]; 
    disabled_plugins: string[];
    error_message?: string; 
    error_code?: ErrorCode 
  }> {
    try {
      console.log('[PluginMarketplaceService] 获取已安装插件状态')
      
      const api = getAPI()
      
      if (!api) {
        if (isDevelopment()) {
          await mockDelay(300)
          return getMockInstalledPluginsStatus()
        }
        return {
          success: false,
          installed_plugins: [],
          disabled_plugins: [],
          error_message: 'API 不可用',
          error_code: ErrorCode.API_UNAVAILABLE
        }
      }
      
      const response = await api.marketplace_get_installed_plugins_status()
      
      if (!isValidResponse(response)) {
        throw new Error('无效的响应格式')
      }
      
      if (!response.success) {
        return {
          success: false,
          installed_plugins: [],
          disabled_plugins: [],
          error_message: response.error || '获取已安装插件状态失败',
          error_code: ErrorCode.UNKNOWN_ERROR
        }
      }
      
      return {
        success: true,
        installed_plugins: response.installed_plugins || [],
        disabled_plugins: response.disabled_plugins || []
      }
    } catch (error) {
      console.error('[PluginMarketplaceService] 获取已安装插件状态失败:', error)
      
      return {
        success: false,
        installed_plugins: [],
        disabled_plugins: [],
        error_message: error instanceof Error ? error.message : '获取已安装插件状态失败',
        error_code: ErrorCode.UNKNOWN_ERROR
      }
    }
  }
  
  /**
   * 检查 API 是否可用
   */
  isAvailable(): boolean {
    return isPyWebViewAvailable() || isDevelopment()
  }
}

// ==================== 导出 ====================

export const pluginMarketplaceService = new PluginMarketplaceService()

export { PluginMarketplaceService }

export { isPyWebViewAvailable, getAPI, handleError, isValidResponse, isDevelopment }
