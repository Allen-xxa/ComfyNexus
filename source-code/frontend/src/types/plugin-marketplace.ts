/**
 * 插件市场类型定义
 * 
 * 该文件定义了插件市场功能所需的所有前端类型
 * 与后端 backend/src/core/marketplace/models.py 保持一致
 */

// ==================== 枚举类型 ====================

/**
 * 安装阶段枚举
 */
export enum InstallStage {
  CLONING = 'cloning',                    // 正在克隆仓库
  CHECKING_DEPS = 'checking_deps',        // 正在检查依赖
  INSTALLING_DEPS = 'installing_deps',    // 正在安装依赖
  SUCCESS = 'success',                    // 安装成功
  FAILED = 'failed'                       // 安装失败
}

/**
 * 安装状态枚举
 */
export enum InstallStatus {
  PENDING = 'pending',      // 等待中
  RUNNING = 'running',      // 运行中
  SUCCESS = 'success',      // 成功
  FAILED = 'failed'         // 失败
}

/**
 * 依赖冲突类型枚举
 */
export enum ConflictType {
  VERSION_MISMATCH = 'version_mismatch',  // 版本不匹配
  MISSING = 'missing'                     // 缺失依赖
}

/**
 * 冲突严重程度枚举
 */
export enum ConflictSeverity {
  WARNING = 'warning',  // 警告级别
  ERROR = 'error'       // 错误级别
}

// ==================== 核心数据模型 ====================

/**
 * 统一的插件数据模型
 * 
 * 该模型整合了来自不同数据源（官方 API 和 Manager 数据库）的插件信息
 */
export interface Plugin {
  name: string                    // 插件名称
  description: string             // 简介
  repository: string              // GitHub 仓库地址
  version_tag: string             // 版本标识（tag 或 commit hash）
  updated_at: string              // 更新时间（ISO 8601 格式，精确到秒）
  node_count: number              // 节点数量
  is_installed: boolean           // 是否已安装（兼容旧字段，已安装或已禁用时为 true）
  install_status: InstallStatusType  // 安装状态：not_installed / installed / disabled
  author: string                  // 作者
  stars: number                   // GitHub stars
  downloads: number               // 下载次数
  tags: string[]                  // 标签
}

export type InstallStatusType = 'not_installed' | 'installed' | 'disabled'

/**
 * 依赖包信息
 * 
 * 表示插件所需的 Python 依赖包及其版本要求
 */
export interface Dependency {
  package: string          // 包名
  version_spec: string     // 版本要求（如 ">=1.0.0", "==2.3.4", "~=1.5"）
}

/**
 * 依赖冲突信息
 * 
 * 表示插件依赖与当前环境已安装包之间的冲突
 */
export interface DependencyConflict {
  package: string                    // 包名
  required_version: string           // 插件要求的版本
  installed_version: string          // 已安装的版本
  conflict_type: ConflictType        // 冲突类型
  severity: ConflictSeverity         // 严重程度
}

/**
 * 安装任务信息
 * 
 * 跟踪插件安装过程的状态和进度
 */
export interface InstallTask {
  task_id: string                    // 任务 ID（唯一标识）
  plugin_name: string                // 插件名称
  github_url: string                 // GitHub 地址
  stage: InstallStage                // 当前阶段
  progress: number                   // 进度（0-100）
  current_package: string            // 当前安装的包
  status: InstallStatus              // 状态
  error_message: string              // 错误信息
  log_path: string                   // 日志文件路径
  started_at: string | null          // 开始时间（ISO 8601 格式）
  finished_at: string | null         // 完成时间（ISO 8601 格式）
}

/**
 * 插件市场配置
 * 
 * 存储插件市场的配置选项
 */
export interface PluginMarketplaceConfig {
  auto_install_deps: boolean         // 是否自动安装依赖
  cache_duration: number             // 缓存有效期（秒），默认 24 小时
  request_timeout: number            // 网络请求超时时间（秒）
  max_retries: number                // 最大重试次数
}

// ==================== API 响应类型 ====================

/**
 * 基础 API 响应接口
 */
export interface BaseResponse {
  success: boolean
  error_code?: number
  error_message?: string
}

/**
 * 插件列表响应
 */
export interface PluginListResponse extends BaseResponse {
  plugins?: Plugin[]
  /** 数据来源：本地缓存或网络 */
  source?: 'cache' | 'network'
  /** 数据是否来自已过期的缓存（需要后台刷新） */
  stale?: boolean
  /** 缓存写入时间戳（秒） */
  cached_at?: number
  /** 非致命提示，如"网络获取失败，已展示本地缓存" */
  warning?: string
}

/**
 * 推荐插件列表响应
 */
export interface RecommendedPluginsResponse extends BaseResponse {
  plugins?: Plugin[]
}

/**
 * 搜索插件响应
 */
export interface SearchPluginsResponse extends BaseResponse {
  plugins?: Plugin[]
}

/**
 * 安装插件响应
 */
export interface InstallPluginResponse extends BaseResponse {
  task_id?: string
  message?: string
}

/**
 * 依赖冲突检查响应
 */
export interface CheckDependenciesResponse extends BaseResponse {
  conflicts?: DependencyConflict[]
  has_conflicts?: boolean
}

/**
 * 安装进度响应
 */
export interface InstallProgressResponse extends BaseResponse {
  task?: InstallTask
}

/**
 * 刷新插件列表响应
 */
export interface RefreshPluginsResponse extends BaseResponse {
  message?: string
  plugins?: Plugin[]
  source?: 'cache' | 'network'
  stale?: boolean
  cached_at?: number
  warning?: string
}

/**
 * 配置响应
 */
export interface MarketplaceConfigResponse extends BaseResponse {
  config?: PluginMarketplaceConfig
}

// ==================== 前端组件 Props 类型 ====================

/**
 * 插件卡片组件 Props
 */
export interface PluginCardProps {
  plugin: Plugin
  autoInstallDeps: boolean
  onInstall: (plugin: Plugin) => void
  isInstalling?: boolean
}

/**
 * 安装进度弹窗组件 Props
 */
export interface InstallProgressModalProps {
  isOpen: boolean
  pluginName: string
  githubUrl: string
  autoInstallDeps: boolean
  onClose: () => void
  onInstallComplete?: (success: boolean) => void
}

/**
 * 排序模式类型
 */
export type SortMode = 'default' | 'stars' | 'updated'

/**
 * 插件库选项卡组件 Props
 */
export interface PluginLibraryTabProps {
  autoInstallDeps: boolean
  onInstallStart: (plugin: Plugin) => void
  installingPluginName: string | null
  sortMode: SortMode
}

/**
 * 新手推荐选项卡组件 Props
 */
export interface RecommendedTabProps {
  autoInstallDeps: boolean
  onInstallStart: (plugin: Plugin) => void
  installingPluginName: string | null
}

// ==================== 前端状态类型 ====================

/**
 * 插件库选项卡状态
 */
export interface PluginLibraryTabState {
  plugins: Plugin[]
  filteredPlugins: Plugin[]
  searchKeyword: string
  githubUrl: string
  page: number
  hasMore: boolean
  isLoading: boolean
  error: string | null
}

/**
 * 新手推荐选项卡状态
 */
export interface RecommendedTabState {
  recommendedPlugins: Plugin[]
  isLoading: boolean
  error: string | null
}

/**
 * 安装进度弹窗状态
 */
export interface InstallProgressModalState {
  stage: InstallStage
  progress: number
  currentPackage: string
  errorMessage: string
  logPath: string
  conflictWarnings: DependencyConflict[]
  status: InstallStatus
}

/**
 * 插件市场主容器状态
 */
export interface PluginMarketplaceState {
  activeTab: 'library' | 'recommended'
  autoInstallDeps: boolean
  isRefreshing: boolean
  installingPluginName: string | null
  currentTaskId: string | null
  showProgressModal: boolean
}

// ==================== 工具类型 ====================

/**
 * 安装进度更新数据
 */
export interface ProgressUpdateData {
  stage: InstallStage
  progress: number
  message: string
  current_package?: string
}

/**
 * 错误信息
 */
export interface ErrorInfo {
  code: number
  message: string
  details?: string
}

/**
 * 分页参数
 */
export interface PaginationParams {
  page: number
  pageSize: number
}

/**
 * 搜索参数
 */
export interface SearchParams {
  keyword: string
  tags?: string[]
}

// ==================== 常量 ====================

/**
 * 插件市场常量
 */
export const PLUGIN_MARKETPLACE_CONSTANTS = {
  // 分页
  PAGE_SIZE: 30,
  COLUMNS_LARGE: 5,
  COLUMNS_MEDIUM: 4,
  COLUMNS_SMALL: 3,
  
  // 缓存
  CACHE_DURATION: 24 * 60 * 60 * 1000, // 24 小时（毫秒）
  
  // 超时
  REQUEST_TIMEOUT: 10000, // 10 秒（毫秒）
  
  // 轮询
  PROGRESS_POLL_INTERVAL: 500, // 500 毫秒
  
  // 防抖
  SEARCH_DEBOUNCE: 300, // 300 毫秒
  
  // 响应式断点
  BREAKPOINT_LARGE: 1200,
  BREAKPOINT_MEDIUM: 900,
} as const

/**
 * 错误代码
 */
export enum ErrorCode {
  NETWORK_ERROR = 1001,
  PARSE_ERROR = 1002,
  GIT_CLONE_FAILED = 1003,
  DEPENDENCY_INSTALL_FAILED = 1004,
  ENVIRONMENT_NOT_CONFIGURED = 1005,
  DISK_SPACE_INSUFFICIENT = 1006,
  DEPENDENCY_CONFLICT = 1007,
  CONCURRENT_INSTALL = 1008,
  INVALID_URL = 1009,
  PATH_TRAVERSAL = 1010,
  API_UNAVAILABLE = 1011,
  UNKNOWN_ERROR = 9999
}

/**
 * 错误消息映射
 */
export const ERROR_MESSAGES: Record<ErrorCode, string> = {
  [ErrorCode.NETWORK_ERROR]: '网络连接失败，请检查网络设置',
  [ErrorCode.PARSE_ERROR]: '数据格式错误，请稍后重试',
  [ErrorCode.GIT_CLONE_FAILED]: 'Git 克隆失败',
  [ErrorCode.DEPENDENCY_INSTALL_FAILED]: '依赖安装失败',
  [ErrorCode.ENVIRONMENT_NOT_CONFIGURED]: '请先配置 ComfyUI 环境',
  [ErrorCode.DISK_SPACE_INSUFFICIENT]: '磁盘空间不足，无法安装插件',
  [ErrorCode.DEPENDENCY_CONFLICT]: '检测到依赖冲突',
  [ErrorCode.CONCURRENT_INSTALL]: '正在安装其他插件，请稍后再试',
  [ErrorCode.INVALID_URL]: '无效的 GitHub 地址',
  [ErrorCode.PATH_TRAVERSAL]: '路径验证失败',
  [ErrorCode.API_UNAVAILABLE]: 'API 不可用，请确保在正确的环境中运行',
  [ErrorCode.UNKNOWN_ERROR]: '未知错误，请查看日志'
}
