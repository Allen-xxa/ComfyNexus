/**
 * PyWebView Bridge API 类型定义
 */

import type { ModuleConfigData } from './module'
import type { 
  EnvironmentConfig,
  EnvironmentListResponse,
  EnvironmentResponse,
  EnvironmentScanResult,
  DependenciesResponse,
  DirectorySelectResponse,
  ConfigExportResponse,
  ConfigImportResponse
} from './environment'
import type {
  FolderShortcutsResponse,
  FolderShortcut,
  FolderOperationResponse,
  FolderValidationResponse,
  FolderBrowseResponse,
  SystemMonitorDataResponse,
  ComfyUIStatusResponse
} from './home'
import type {
  VersionInfo,
  RemoteInfo
} from './version'
import type {
  CheckProcessResult,
  KillProcessResult
} from './process'
import type {
  PluginsResponse,
  DependenciesResponse as PluginDependenciesResponse,
  UpdateInfoResponse,
  BranchesResponse,
  BatchUpdateResponse,
  ConflictsResponse,
  PluginUpdateResponse,
  DependencyInstallResponse,
  ApiResponse,
} from './plugin'

export interface AppInfo {
  version: string;
  env: string;
}

export interface PyWebViewAPI {
  // 应用相关 API
  ping: () => Promise<{ status: string }>;
  getAppInfo: () => Promise<AppInfo>;
  closeApp: () => Promise<void>;
  minimizeApp: () => Promise<void>;
  maximizeApp: () => Promise<void>;
  toggleFullscreen: () => Promise<void>;
  moveWindow: (x: number, y: number) => Promise<void>;
  resizeWindow: (width: number, height: number) => Promise<boolean>;
  open_url: (url: string) => Promise<{ success: boolean; message?: string; error?: string }>;
  get_installed_browsers: () => Promise<{ success: boolean; browsers?: Array<{ name: string; displayName: string; path: string }>; error?: string }>;
  
  // 模块配置 API
  get_module_config: () => Promise<ModuleConfigData>;
  save_module_config: (config: ModuleConfigData) => Promise<boolean>;
  reset_module_config: () => Promise<ModuleConfigData | null>;
  
  // 环境管理 API
  get_environments: () => Promise<EnvironmentListResponse>;
  add_environment: (path: string, name?: string, lang?: string) => Promise<EnvironmentResponse>;
  delete_environment: (env_id: string) => Promise<{ success: boolean; error_code?: number; error_message?: string }>;
  set_current_environment: (env_id: string) => Promise<{ success: boolean; error_code?: number; error_message?: string }>;
  update_environment: (env_id: string, config: EnvironmentConfig) => Promise<EnvironmentResponse>;
  scan_environment: (path: string, lang?: string) => Promise<EnvironmentScanResult>;
  get_dependencies: (env_id: string) => Promise<DependenciesResponse>;
  export_config: (env_id: string) => Promise<ConfigExportResponse>;
  import_config: (config_data: string) => Promise<ConfigImportResponse>;
  select_directory: () => Promise<DirectorySelectResponse>;
  select_file: (file_types?: string[]) => Promise<DirectorySelectResponse>;
  save_file_dialog: (default_name?: string, file_filter?: string) => Promise<{
    success: boolean
    path?: string
    error_message?: string
  }>;
  
  // 文件夹快捷方式 API
  get_folder_shortcuts: () => Promise<FolderShortcutsResponse>;
  save_folder_shortcuts: (shortcuts: FolderShortcut[]) => Promise<FolderOperationResponse>;
  open_folder: (path: string) => Promise<FolderOperationResponse>;
  validate_folder_path: (path: string) => Promise<FolderValidationResponse>;
  browse_folder: () => Promise<FolderBrowseResponse>;
  browse_folder_for_shortcut: () => Promise<FolderBrowseResponse>;
  
  // 系统监控 API
  get_system_monitor_data: () => Promise<SystemMonitorDataResponse>;
  
  // ComfyUI 管理 API
  get_comfyui_status: () => Promise<ComfyUIStatusResponse>;
  open_comfyui: () => Promise<FolderOperationResponse>;
  start_comfyui: (env_id: string) => Promise<FolderOperationResponse>;
  stop_comfyui: () => Promise<FolderOperationResponse>;
  
  // 版本管理 API
  get_versions: (versionType: string, page: number, pageSize: number, branch?: string | null, forceRefresh?: boolean) => Promise<{
    success: boolean
    versions: VersionInfo[]
    hasMore: boolean
  }>;
  get_current_version: () => Promise<{
    success: boolean
    version: VersionInfo
  }>;
  get_remote_info: () => Promise<{
    success: boolean
    remoteInfo: RemoteInfo
  }>;
  switch_version: (versionId: string, versionType: string, force?: boolean) => Promise<{
    success: boolean
    needDependencyUpdate: boolean
    message: string
    originalCommit?: string  // 原始 commit hash（用于回退）
    requires_force?: boolean  // 是否需要强制切换（本地有修改）
    stashed?: boolean  // 是否已暂存本地文件到 stash
  }>;
  rollback_version: (commitHash: string) => Promise<{
    success: boolean
    message: string
  }>;
  update_dependencies: () => Promise<{
    success: boolean
    message: string
    log_file?: string  // 日志文件路径（后端使用 snake_case）
  }>;
  restart_process: () => Promise<{
    success: boolean
    message: string
  }>;
  check_process_status: () => Promise<{
    success: boolean
    isRunning: boolean
    hasTask: boolean
  }>;
  update_remote_url: (url: string) => Promise<{
    success: boolean
    message: string
  }>;
  fix_git_ownership: () => Promise<{
    success: boolean
    message?: string
  }>;
  get_branches: () => Promise<{
    success: boolean
    current_branch: string
    local_branches: string[]
    remote_branches: string[]
    error?: string
  }>;
  switch_branch: (branchName: string) => Promise<{
    success: boolean
    message: string
  }>;
  
  // 系统代理 API
  get_system_proxy: () => Promise<{
    success: boolean
    message?: string
    enabled: boolean
    host: string
    port: string
  }>;
  
  // 系统设置 API
  get_settings: () => Promise<{
    success: boolean
    message?: string
    settings: {
      version: string
      general: {
        comfyuiStartupAction?: 'workspace' | 'browser' | 'none'
        selectedBrowser?: string  // 浏览器exe路径，空字符串表示系统默认
      }
      appearance: {
        theme: 'light' | 'dark'
        windowSize: string
      }
      language: {
        current: string
      }
      proxy: {
        enabled: boolean
        host: string
        port: string
      }
      warnings?: {
        devVersionWarning: boolean
        // 可以添加更多警告类型
      }
    }
  }>;
  
  update_settings: (updates: Record<string, any>) => Promise<{
    success: boolean
    message: string
    settings?: any
  }>;
  
  reset_settings: () => Promise<{
    success: boolean
    message: string
  }>;
  
  // GitHub 镜像加速 API
  get_github_mirror_settings: () => Promise<{
    success: boolean
    settings?: {
      enabled: boolean
      mode: string
      forcePreset: string | null
      statusText: string
      currentPreset: string
      isTesting: boolean
      verifySSL: boolean
      fallbackToDirect: boolean
      testResults: Record<string, Record<string, number>> | null
      lastTested: string | null
    }
    message?: string
  }>;
  update_github_mirror_settings: (updates: Record<string, unknown>) => Promise<{
    success: boolean
    message: string
  }>;
  start_github_mirror_speed_test: () => Promise<{
    success: boolean
    message: string
  }>;
  get_github_mirror_speed_test_status: () => Promise<{
    success: boolean
    isRunning: boolean
    progress: Array<{
      preset: string
      type: string
      latency: number
      timestamp: number
    }>
    results: Record<string, Record<string, number>> | null
  }>;
  get_github_mirror_presets: () => Promise<{
    success: boolean
    presets: Record<string, {
      name: string
      description: string
      github: string | null
      raw: string | null
      release: string | null
    }>
    message?: string
  }>;
  
  // PyPI 镜像源 API
  get_pypi_mirror_settings: () => Promise<{
    success: boolean
    settings?: {
      enabled: boolean
      mode: string
      forceSource: string | null
      statusText: string
      currentSource: string
      isTesting: boolean
      testResults: Record<string, number> | null
      lastTested: string | null
    }
    message?: string
  }>;
  update_pypi_mirror_settings: (updates: Record<string, unknown>) => Promise<{
    success: boolean
    message: string
  }>;
  start_pypi_mirror_speed_test: () => Promise<{
    success: boolean
    message: string
  }>;
  get_pypi_mirror_speed_test_status: () => Promise<{
    success: boolean
    isRunning: boolean
    progress: Array<{
      source: string
      latency: number
      timestamp: number
    }>
    results: Record<string, number> | null
  }>;
  
  get_github_releases: (owner?: string, repo?: string, per_page?: number) => Promise<{
    success: boolean
    releases?: Array<{
      id: number
      tag_name: string
      name: string
      body: string
      published_at: string
      html_url: string
      prerelease: boolean
      draft: boolean
    }>
    message?: string
  }>;
  
  get_last_commit_time: (owner: string, repo: string, branch?: string) => Promise<{
    success: boolean
    commit_date?: string
    commit_sha?: string
    message?: string
  }>;
  
  // 进程冲突检测 API
  check_comfyui_processes: () => Promise<CheckProcessResult>;
  kill_process: (pid: number) => Promise<KillProcessResult>;
  
  // 插件管理 API
  get_plugins: (useCache?: boolean) => Promise<PluginsResponse>;
  search_plugins: (keyword: string) => Promise<PluginsResponse>;
  refresh_plugins: () => Promise<PluginsResponse>;
  refresh_plugin_git_info: (pluginName: string) => Promise<{
    success: boolean;
    error?: string;
    plugin?: any;
  }>;
  get_refresh_progress: () => Promise<{
    success: boolean;
    is_updating: boolean;
    current: number;
    total: number;
    plugins?: any[];
    error?: string;
  }>;
  cancel_background_update: () => Promise<ApiResponse>;
  get_plugin_dependencies: (pluginName: string) => Promise<PluginDependenciesResponse>;
  install_dependency: (pluginName: string, pkg: string, version: string, pipOptions?: string[] | null) => Promise<DependencyInstallResponse>;
  open_log_file: (logFilePath: string) => Promise<ApiResponse>;
  update_plugin: (pluginName: string, force?: boolean) => Promise<PluginUpdateResponse>;
  update_all_plugins: (pythonPath?: string, maxWorkers?: number) => Promise<BatchUpdateResponse>;
  get_update_info: (pluginName: string) => Promise<UpdateInfoResponse>;
  switch_plugin_branch: (pluginName: string, branch: string, commitHash?: string, commitDate?: string) => Promise<ApiResponse>;
  get_plugin_branches: (pluginName: string) => Promise<BranchesResponse>;
  uninstall_plugin: (pluginName: string) => Promise<ApiResponse>;
  open_plugin_folder: (pluginName: string) => Promise<ApiResponse>;
  detect_plugin_conflicts: () => Promise<ConflictsResponse>;
  toggle_plugin_enabled: (pluginName: string, enabled: boolean) => Promise<ApiResponse>;
  switch_plugin_version: (pluginName: string, commitHash: string, commitDate?: string, behindCommits?: number, force?: boolean) => Promise<{
    success: boolean;
    message: string;
    plugin?: any;
    installed_deps?: { package: string; version: string; success: boolean; error?: string }[];
    failed_deps?: { package: string; version: string; success: boolean; error?: string }[];
  }>;
  set_plugin_remote_url: (pluginName: string, remoteUrl: string) => Promise<ApiResponse>;
  get_plugin_note: (pluginName: string) => Promise<ApiResponse & { note?: string | null }>;
  save_plugin_note: (pluginName: string, note: string) => Promise<ApiResponse>;
  get_all_plugin_notes: () => Promise<ApiResponse & { notes?: Record<string, string> }>;
  
  // 插件市场 API
  get_recommended_plugins: (use_cache: boolean) => Promise<any>;
  install_plugin: (github_url: string, auto_install_deps: boolean) => Promise<any>;
  check_dependencies: (github_url: string) => Promise<any>;
  get_install_progress: (task_id: string) => Promise<any>;
  
  // AI 助手 API
  ai_create_topic: (name?: string) => Promise<{
    success: boolean
    topic?: {
      id: string
      name: string
      created_at: string
      updated_at: string
    }
    error_message?: string
  }>;
  
  ai_get_topics: () => Promise<{
    success: boolean
    topics?: Array<{
      id: string
      name: string
      created_at: string
      updated_at: string
      message_count?: number
    }>
    error_message?: string
  }>;
  
  ai_delete_topic: (topicId: string) => Promise<{
    success: boolean
    error_message?: string
  }>;
  
  ai_rename_topic: (topicId: string, name: string) => Promise<{
    success: boolean
    error_message?: string
  }>;
  
  ai_send_message_with_config: (
    topicId: string,
    content: string,
    configId: string,
    deepThinking?: boolean,
    webSearchEnabled?: boolean,
    systemPrompt?: string | null,
    files?: any[]
  ) => Promise<{
    success: boolean
    message_id?: string
    ai_message_id?: string
    topic_id?: string  // 实际的话题 ID（如果临时话题被转换）
    error_message?: string
  }>;
  
  ai_get_messages: (
    topicId: string,
    limit?: number,
    offset?: number
  ) => Promise<{
    success: boolean
    messages?: Array<{
      id: string
      role: 'user' | 'assistant'
      content: string
      timestamp: string
      model?: string
    }>
    total?: number
    error_message?: string
  }>;
  
  ai_clear_messages: (topicId: string) => Promise<{
    success: boolean
    error_message?: string
  }>;
  
  // 多配置管理 API
  // 注意：后端只下发掩码（api_key_masked）与 has_api_key，不再回传明文 api_key
  ai_list_configs: () => Promise<{
    success: boolean
    configs?: Array<{
      id: string
      alias: string
      provider: string
      model: string
      api_key_masked?: string
      has_api_key?: boolean
      is_default: boolean
      status: string
      last_tested_at?: string
      usage_count: number
      created_at: string
      updated_at: string
    }>
    error_message?: string
  }>;
  
  ai_get_config_detail: (configId: string) => Promise<{
    success: boolean
    config?: {
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
      created_at: string
      updated_at: string
    }
    error_message?: string
  }>;
  
  ai_create_config: (config: any) => Promise<{
    success: boolean
    config_id?: string
    error_message?: string
  }>;
  
  ai_update_config: (configId: string, config: any) => Promise<{
    success: boolean
    error_message?: string
  }>;
  
  ai_delete_config: (configId: string) => Promise<{
    success: boolean
    error_message?: string
  }>;
  
  ai_set_default_config: (configId: string) => Promise<{
    success: boolean
    error_message?: string
  }>;
  
  ai_test_config: (configId: string) => Promise<{
    success: boolean
    available: boolean
    latency?: number
    message: string
    error_message?: string
  }>;
  
  // config 可含 config_id：留空或传掩码时由后端用已保存的密钥补齐
  ai_test_connection: (provider: string, config: any) => Promise<{
    success: boolean
    message?: string
    latency?: number
    error_message?: string
  }>;
  
  // 搜索相关API
  ai_get_search_config: () => Promise<{
    success: boolean
    config?: any
    error?: string
  }>;
  
  ai_update_search_config: (config: any) => Promise<{
    success: boolean
    error?: string
  }>;
  
  ai_test_search_connection: (provider: string, config: any) => Promise<{
    success: boolean
    message: string
    latency?: number
  }>;
  
  ai_stop_generation: (topicId: string) => Promise<{
    success: boolean
    error_message?: string
  }>;
  
  ai_export_chat: (topicId: string, format: 'json' | 'markdown') => Promise<{
    success: boolean
    content?: string
    format?: string
    error_message?: string
  }>;
  
  ai_get_available_models: (provider: string, config: any) => Promise<{
    success: boolean
    models?: string[]
    from_cache?: boolean
    error_message?: string
  }>;
  
  // 模型选择器 API
  ai_get_default_config: () => Promise<{
    success: boolean
    config_id?: string | null
    error_message?: string
  }>;
  
  ai_set_topic_config: (topicId: string, configId: string) => Promise<{
    success: boolean
    error_message?: string
  }>;
  
  ai_get_topic_config: (topicId: string) => Promise<{
    success: boolean
    config_id?: string | null
    error_message?: string
  }>;
  
  // 系统提示词管理 API
  ai_get_system_prompts: () => Promise<{
    success: boolean
    presets?: Array<{
      id: string
      name: string
      content: string
      created_at: string
      updated_at: string
    }>
    error_message?: string
  }>;
  
  ai_create_system_prompt: (name: string, content: string) => Promise<{
    success: boolean
    preset?: {
      id: string
      name: string
      content: string
      created_at: string
      updated_at: string
    }
    error_message?: string
  }>;
  
  ai_update_system_prompt: (presetId: string, name: string, content: string) => Promise<{
    success: boolean
    error_message?: string
  }>;
  
  ai_delete_system_prompt: (presetId: string) => Promise<{
    success: boolean
    error_message?: string
  }>;
  
  ai_set_active_system_prompt: (topicId: string, presetId: string | null) => Promise<{
    success: boolean
    error_message?: string
  }>;
  
  ai_get_active_system_prompt: (topicId: string) => Promise<{
    success: boolean
    preset_id?: string | null
    error_message?: string
  }>;
  
  // 文件处理 API
  ai_process_file: (
    file_data: string,
    file_name: string,
    file_type: string,
    file_size: number
  ) => Promise<{
    success: boolean
    file_id: string
    processed_data: {
      type: 'image' | 'document'
      content: string
      content_type: 'base64' | 'text'
      thumbnail?: string
      metadata: Record<string, any>
    }
    error_message?: string
  }>;
  
  ai_get_model_capabilities: (provider: string, model: string) => Promise<{
    success: boolean
    capabilities?: {
      supports_vision: boolean
      supports_files: boolean
      max_file_size?: number
      supported_file_types?: string[]
    }
    error_message?: string
  }>;
  
  // 图片保存 API
  save_image_with_dialog: (image_url: string, suggested_filename?: string) => Promise<{
    success: boolean
    message: string
    saved_path?: string
    error_code?: string
  }>;
  
  // 依赖管理 API
  // 注意：这些 API 不需要 envId 参数，控制器内部会自动获取当前环境
  dependency_detect_cuda_version: () => Promise<{
    success: boolean
    cuda_version: string | null
    error_message?: string
  }>;
  
  dependency_fetch_pytorch_versions: (cudaVersion: string) => Promise<{
    success: boolean
    versions: string[]
    error_message?: string
  }>;
  
  dependency_install_pytorch: (
    version: string,
    cudaVersion: string,
    mirrorSource: string
  ) => Promise<{
    success: boolean
    log_file: string
    error_message?: string
  }>;
  
  dependency_search_package: (
    packageName: string,
    mirrorSource: string
  ) => Promise<{
    success: boolean
    package_info?: {
      name: string
      latest_version: string
      description: string
      author: string
      homepage: string
    }
    error_message?: string
  }>;
  
  dependency_get_installed_version: (
    packageName: string
  ) => Promise<{
    success: boolean
    version: string | null
    installed: boolean
    error_message?: string
  }>;
  
  dependency_fetch_package_versions: (
    packageName: string,
    mirrorSource: string
  ) => Promise<{
    success: boolean
    versions: string[]
    error_message?: string
  }>;
  
  dependency_install_package: (
    packageName: string,
    version: string,
    mode: 'dry-run' | 'install',
    mirrorSource: string
  ) => Promise<{
    success: boolean
    log_file: string
    error_message?: string
  }>;
  
  dependency_uninstall_package: (
    packageName: string
  ) => Promise<{
    success: boolean
    log_file: string
    error_message?: string
  }>;
  
  dependency_install_from_requirements: (
    filePath: string,
    mode: 'dry-run' | 'install',
    mirrorSource: string
  ) => Promise<{
    success: boolean
    log_file: string
    error_message?: string
  }>;
  
  dependency_select_file: (
    fileTypes: string
  ) => Promise<{
    success: boolean
    file_path?: string
    file_type?: 'requirements' | 'whl'
    error_message?: string
  }>;
  
  dependency_analyze_requirements_file: (
    filePath: string
  ) => Promise<{
    success: boolean
    data?: {
      total: number
      installed: number
      not_installed: number
      conflicts: number
      dependencies: Array<{
        name: string
        required_version: string
        installed_version: string | null
        status: 'installed' | 'not_installed' | 'version_mismatch'
      }>
    }
    error_message?: string
  }>;
  
  dependency_install_whl: (
    filePath: string
  ) => Promise<{
    success: boolean
    log_file: string
    error_message?: string
  }>;
  
  dependency_open_terminal: () => Promise<{
    success: boolean
    error_message?: string
  }>;
  
  dependency_detect_environment: () => Promise<{
    success: boolean
    env_info?: {
      windows_version: string
      gpu: { model: string; vram: string }
      cpu: { model: string; ram: string }
      python: { version: string; path: string }
      cuda: { version: string }
      dependencies: { [key: string]: string }
    }
    error_message?: string
  }>;
  
  dependency_analyze_logs_with_ai: (
    logs: string,
    apiConfigId: string
  ) => Promise<{
    success: boolean
    content?: string
    done?: boolean
    topic_id?: string
    error_message?: string
  }>;
  
  // 依赖扫描与管理 API
  dependency_scan_dependencies: () => Promise<{
    success: boolean
    data?: {
      core: Array<{
        package_name: string
        version_spec: string
        source: string
        source_file: string
      }>
      plugins: Record<string, Array<{
        package_name: string
        version_spec: string
        source: string
        source_file: string
      }>>
    }
    error_message?: string
  }>;
  
  dependency_check_package_status: (packageName: string) => Promise<{
    success: boolean
    data?: {
      installed: boolean
      version: string | null
      location: string | null
    }
    error_message?: string
  }>;
  
  dependency_check_all_status: (packages: string[]) => Promise<{
    success: boolean
    data?: Record<string, {
      installed: boolean
      version: string | null
    }>
    error_message?: string
  }>;
  
  dependency_get_plugins: () => Promise<{
    success: boolean
    data?: Array<{
      name: string
      path: string
      has_requirements: boolean
      dependency_count: number
    }>
    error_message?: string
  }>;
  
  // 依赖冲突分析 API
  dependency_check_pipdeptree: () => Promise<{
    success: boolean
    installed: boolean
    version?: string
    error_message?: string
  }>;
  
  dependency_install_pipdeptree: () => Promise<{
    success: boolean
    message: string
    error_message?: string
  }>;
  
  dependency_analyze_dependencies: () => Promise<{
    success: boolean
    data?: {
      tree: any[]
      conflicts: any[]
      stats: {
        totalPackages: number
        totalConflicts: number
        maxDepth: number
        versionConflicts: number
        circularDependencies: number
      }
    }
    error_message?: string
    timestamp?: string
  }>;
  
  dependency_export_analysis_report: (
    format: 'json' | 'markdown',
    tree: any[],
    conflicts: any[]
  ) => Promise<{
    success: boolean
    file_path?: string
    content?: string
    error_message?: string
  }>;
  
  dependency_fix_conflict: (
    conflictData: {
      id: string
      type: string
      packageName: string
      installedVersion: string
      requiredVersion: string
      source: string
    },
    mirrorSource: string
  ) => Promise<{
    success: boolean
    log_file?: string
    error_message?: string
  }>;

  // ===== Rescue 模式 API =====
  rescue_list_snapshots: () => Promise<{
    success: boolean
    snapshots?: Array<{
      filePath: string
      name: string
      backupOption: 'deps_only' | 'plugins_only' | 'all'
      note: string
      createdAt: string
      fileSize: number
    }>
    error_message?: string
  }>;

  rescue_create_snapshot: (
    name: string,
    backupOption: string,
    includeGit: boolean,
    note: string
  ) => Promise<{
    success: boolean
    error_message?: string
  }>;

  rescue_delete_snapshot: (snapshotPath: string) => Promise<{
    success: boolean
    error_message?: string
  }>;

  rescue_update_snapshot: (
    snapshotPath: string,
    name: string,
    note: string
  ) => Promise<{
    success: boolean
    snapshot_info?: {
      filePath: string
      name: string
      backupOption: string
      note: string
      createdAt: string
      fileSize: number
    }
    error_message?: string
  }>;

  rescue_compute_diff: (snapshotPath: string) => Promise<{
    success: boolean
    diff_result?: {
      dependencies: {
        added: Array<{ name: string; version: string }>
        removed: Array<{ name: string; version: string }>
        changed: Array<{ name: string; current: string; snapshot: string }>
      }
      plugins: {
        added: string[]
        removed: string[]
      }
    }
    error_message?: string
  }>;

  rescue_smart_rollback: (snapshotPath: string) => Promise<{
    success: boolean
    report?: {
      totalItems: number
      succeeded: number
      failed: number
      failures: Array<{ item: string; error: string }>
    }
    error_message?: string
  }>;

  rescue_direct_restore: (snapshotPath: string, mode: string) => Promise<{
    success: boolean
    error_message?: string
  }>;

  rescue_check_process: () => Promise<{
    success: boolean
    running?: boolean
    pid?: number
    error_message?: string
  }>;

  // ========== 提示词库 API ==========

  prompt_get_all: () => Promise<{
    success: boolean
    prompts?: Array<{
      id: string
      name: string
      positive_prompt: string
      negative_prompt: string
      preview_image: string
      remark: string
      category_id: string
      tags: string[]
      created_at: string
      updated_at: string
      is_favorite: boolean
    }>
    error_message?: string
  }>;

  prompt_create: (
    name: string,
    positive_prompt: string,
    category_id?: string,
    negative_prompt?: string,
    preview_image?: string,
    remark?: string,
    tags?: string[]
  ) => Promise<{
    success: boolean
    prompt?: {
      id: string
      name: string
      positive_prompt: string
      negative_prompt: string
      preview_image: string
      remark: string
      category_id: string
      tags: string[]
      created_at: string
      updated_at: string
      is_favorite: boolean
    }
    error_message?: string
  }>;

  prompt_update: (
    prompt_id: string,
    name?: string,
    positive_prompt?: string,
    category_id?: string,
    negative_prompt?: string,
    preview_image?: string,
    remark?: string,
    tags?: string[]
  ) => Promise<{
    success: boolean
    error_message?: string
  }>;

  prompt_delete: (prompt_id: string) => Promise<{
    success: boolean
    error_message?: string
  }>;

  prompt_batch_delete: (prompt_ids: string[]) => Promise<{
    success: boolean
    deleted_count?: number
    error_message?: string
  }>;

  prompt_batch_move: (prompt_ids: string[], category_id: string) => Promise<{
    success: boolean
    moved_count?: number
    error_message?: string
  }>;

  prompt_toggle_favorite: (prompt_id: string) => Promise<{
    success: boolean
    is_favorite?: boolean
    error_message?: string
  }>;

  prompt_upload_image: (file_data: number[], filename?: string) => Promise<{
    success: boolean
    image_path?: string
    error_message?: string
  }>;

  prompt_export: (prompt_ids: string[] | null) => Promise<{
    success: boolean
    data?: {
      version: string
      exported_at: string
      prompts: Array<{
        id: string
        name: string
        positive_prompt: string
        negative_prompt: string
        preview_image: string
        remark: string
        category_id: string
        tags: string[]
      }>
      categories: Array<{
        id: string
        name: string
        icon: string
      }>
    }
    error_message?: string
  }>;

  prompt_import: (data: unknown, merge: boolean) => Promise<{
    success: boolean
    imported_count?: number
    imported_categories?: number
    skipped_count?: number
    message?: string
    error_message?: string
  }>;

  category_get_all: () => Promise<{
    success: boolean
    categories?: Array<{
      id: string
      name: string
      icon: string
      parent_id: string | null
      sort_order: number
      is_system: boolean
      children?: Array<{
        id: string
        name: string
        icon: string
        parent_id: string | null
        sort_order: number
        is_system: boolean
      }>
    }>
    error_message?: string
  }>;

  category_create: (
    name: string,
    icon?: string,
    parent_id?: string | null
  ) => Promise<{
    success: boolean
    category?: {
      id: string
      name: string
      icon: string
      parent_id: string | null
      sort_order: number
      is_system: boolean
    }
    error_message?: string
  }>;

  category_update: (
    category_id: string,
    name?: string,
    icon?: string,
    sort_order?: number
  ) => Promise<{
    success: boolean
    error_message?: string
  }>;

  category_delete: (category_id: string) => Promise<{
    success: boolean
    error_message?: string
  }>;

  // ========== 工作流管理 API ==========

  get_workflows: () => Promise<{
    success: boolean
    workflows?: Array<{
      id: string
      name: string
      description: string
      preview?: string
      previews?: string[]
      nodes: number
      createdAt: string
      updatedAt: string
      tags: string[]
      isFavorite?: boolean
      folderId?: string
      rawData?: any
    }>
    error?: string
  }>;

  get_workflow: (filename: string) => Promise<{
    success: boolean
    workflow?: {
      id: string
      name: string
      description: string
      preview?: string
      previews?: string[]
      nodes: number
      createdAt: string
      updatedAt: string
      tags: string[]
      isFavorite?: boolean
      folderId?: string
      rawData?: any
    }
    error?: string
  }>;

  delete_workflow: (filename: string) => Promise<{
    success: boolean
    error?: string
  }>;

  import_workflow: (fileData: string, filename?: string) => Promise<{
    success: boolean
    workflow?: {
      id: string
      name: string
      description: string
      preview?: string
      previews?: string[]
      nodes: number
      createdAt: string
      updatedAt: string
      tags: string[]
      isFavorite?: boolean
      folderId?: string
      rawData?: any
    }
    error?: string
  }>;

  export_workflow: (filename: string) => Promise<{
    success: boolean
    content?: string
    filename?: string
    error?: string
  }>;

  update_workflow_info: (filename: string, info: {
    name?: string
    description?: string
    tags?: string[]
  }) => Promise<{
    success: boolean
    workflow?: {
      id: string
      name: string
      description: string
      preview?: string
      previews?: string[]
      nodes: number
      createdAt: string
      updatedAt: string
      tags: string[]
      isFavorite?: boolean
      folderId?: string
      rawData?: any
    }
    error?: string
  }>;

  toggle_favorite: (filename: string) => Promise<{
    success: boolean
    isFavorite?: boolean
    error?: string
  }>;

  get_workflow_folders: () => Promise<{
    success: boolean
    folders?: Array<{
      id: string
      name: string
      parentId?: string
      createdAt: string
      updatedAt: string
    }>
    error?: string
  }>;

  create_workflow_folder: (name: string, parentId?: string) => Promise<{
    success: boolean
    folder?: {
      id: string
      name: string
      parentId?: string
      createdAt: string
      updatedAt: string
    }
    error?: string
  }>;

  update_workflow_folder: (folderId: string, updates: {
    name?: string
    parentId?: string
  }) => Promise<{
    success: boolean
    folder?: {
      id: string
      name: string
      parentId?: string
      createdAt: string
      updatedAt: string
    }
    error?: string
  }>;

  delete_workflow_folder: (folderId: string) => Promise<{
    success: boolean
    error?: string
  }>;

  move_workflow_to_folder: (filename: string, folderId: string | null) => Promise<{
    success: boolean
    workflow?: {
      id: string
      name: string
      description: string
      preview?: string
      previews?: string[]
      nodes: number
      createdAt: string
      updatedAt: string
      tags: string[]
      isFavorite?: boolean
      folderId?: string
      rawData?: any
    }
    error?: string
  }>;

  check_plugins_status: (cnrIds: string[]) => Promise<{
    success: boolean
    status?: Record<string, 'installed' | 'missing' | 'unknown'>
    error?: string
  }>;

  upload_workflow_preview: (filename: string, imageData: string) => Promise<{
    success: boolean
    previewPath?: string
    error?: string
  }>;

  delete_workflow_preview: (filename: string, previewIndex: number) => Promise<{
    success: boolean
    error?: string
  }>;

  initialize_node_type_map_async: () => Promise<{
    success: boolean
    message?: string
    error?: string
  }>;

  // ========== 资产库 API ==========

  gallery_get_assets: () => Promise<{
    success: boolean
    assets?: Array<{
      id: string
      filename: string
      filePath: string
      thumbnailPath: string | null
      type: 'image' | 'video'
      width: number
      height: number
      size: number
      createdAt: string
      hasWorkflow: boolean
      isFavorite: boolean
      categoryId: string | null
      prompt?: string
      negativePrompt?: string
      model?: string
      sampler?: string
      steps?: number
      cfg?: number
      seed?: number
      duration?: number
    }>
    categories?: Array<{
      id: string
      name: string
      isSystem: boolean
      parentId: string | null
      sortOrder: number
      folderPath?: string
    }>
    settings?: {
      libraryPath: string
      lastScanTime: string | null
      nsfwAutoClassify: boolean
      nsfwThreshold: number
      nsfwAutoBlur: boolean
    }
    error_message?: string
  }>;

  gallery_get_asset: (assetId: string) => Promise<{
    success: boolean
    asset?: {
      id: string
      filename: string
      filePath: string
      thumbnailPath: string | null
      type: 'image' | 'video'
      width: number
      height: number
      size: number
      createdAt: string
      hasWorkflow: boolean
      isFavorite: boolean
      categoryId: string | null
      prompt?: string
      negativePrompt?: string
      model?: string
      sampler?: string
      steps?: number
      cfg?: number
      seed?: number
      duration?: number
    }
    error_message?: string
  }>;

  gallery_delete_asset: (assetId: string) => Promise<{
    success: boolean
    error_message?: string
  }>;

  gallery_batch_delete: (assetIds: string[]) => Promise<{
    success: boolean
    deleted_count?: number
    error_message?: string
  }>;

  gallery_toggle_favorite: (assetId: string) => Promise<{
    success: boolean
    is_favorite?: boolean
    error_message?: string
  }>;

  gallery_batch_favorite: (assetIds: string[], favorite: boolean) => Promise<{
    success: boolean
    updated_count?: number
    error_message?: string
  }>;

  gallery_get_settings: () => Promise<{
    success: boolean
    settings?: {
      libraryPath: string
      lastScanTime: string | null
      nsfwAutoClassify: boolean
      nsfwThreshold: number
      nsfwAutoBlur: boolean
    }
    error_message?: string
  }>;

  gallery_save_settings: (libraryPath?: string) => Promise<{
    success: boolean
    error_message?: string
  }>;

  gallery_scan: (libraryPath?: string) => Promise<{
    success: boolean
    added?: number
    updated?: number
    removed?: number
    errors?: string[]
    error_message?: string
  }>;

  gallery_incremental_scan: (libraryPath?: string) => Promise<{
    success: boolean
    added?: number
    updated?: number
    removed?: number
    errors?: string[]
    error_message?: string
  }>;

  gallery_get_workflow: (assetId: string) => Promise<{
    success: boolean
    workflow?: object
    error_message?: string
  }>;

  gallery_export_workflow: (assetId: string) => Promise<{
    success: boolean
    workflow_path?: string
    workflow_name?: string
    error_message?: string
  }>;

  gallery_export_workflow_to_path: (assetId: string, savePath: string) => Promise<{
    success: boolean
    workflow_path?: string
    error_message?: string
  }>;

  gallery_open_location: (assetId: string) => Promise<{
    success: boolean
    error_message?: string
  }>;

  gallery_move_to_category: (assetIds: string[], categoryId?: string) => Promise<{
    success: boolean
    moved_count?: number
    error_message?: string
  }>;

  gallery_import: (paths: string[]) => Promise<{
    success: boolean
    imported_count?: number
    errors?: string[]
    error_message?: string
  }>;

  gallery_export_zip: (assetIds: string[]) => Promise<{
    success: boolean
    zip_path?: string
    error_message?: string
  }>;

  gallery_get_categories: () => Promise<{
    success: boolean
    categories?: Array<{
      id: string
      name: string
      isSystem: boolean
      parentId: string | null
      sortOrder: number
      folderPath?: string
    }>
    error_message?: string
  }>;

  gallery_create_category: (name: string, parentId?: string) => Promise<{
    success: boolean
    category?: {
      id: string
      name: string
      isSystem: boolean
      parentId: string | null
      sortOrder: number
      folderPath?: string
    }
    error_message?: string
  }>;

  gallery_update_category: (categoryId: string, name?: string) => Promise<{
    success: boolean
    category?: {
      id: string
      name: string
      isSystem: boolean
      parentId: string | null
      sortOrder: number
      folderPath?: string
    }
    error_message?: string
  }>;

  gallery_get_category_content_info: (categoryId: string) => Promise<{
    success: boolean
    asset_count?: number
    child_ids?: string[]
    child_count?: number
    error_message?: string
  }>;

  gallery_delete_category: (categoryId: string, cascade?: boolean) => Promise<{
    success: boolean
    deleted_categories?: number
    deleted_assets?: number
    error_message?: string
  }>;

  gallery_get_nsfw_status: () => Promise<{
    success: boolean
    model_available?: boolean
    nsfw_auto_classify?: boolean
    nsfw_threshold?: number
    nsfw_auto_blur?: boolean
    is_scanning?: boolean
    is_paused?: boolean
    error_message?: string
  }>;

  gallery_set_nsfw_enabled: (enabled: boolean) => Promise<{
    success: boolean
    error_message?: string
  }>;

  gallery_set_nsfw_threshold: (threshold: number) => Promise<{
    success: boolean
    error_message?: string
  }>;

  gallery_set_nsfw_auto_blur: (enabled: boolean) => Promise<{
    success: boolean
    error_message?: string
  }>;

  gallery_classify_all_images: () => Promise<{
    success: boolean
    total?: number
    message?: string
    error_message?: string
  }>;

  gallery_pause_nsfw_scan: () => Promise<{
    success: boolean
    error_message?: string
  }>;

  gallery_resume_nsfw_scan: () => Promise<{
    success: boolean
    error_message?: string
  }>;

  gallery_cancel_nsfw_scan: () => Promise<{
    success: boolean
    error_message?: string
  }>;

  gallery_start_background_scan: (libraryPath?: string) => Promise<{
    success: boolean
    message?: string
    error_message?: string
  }>;

  gallery_get_scan_status: () => Promise<{
    success: boolean
    scanning?: boolean
    stopping?: boolean
    progress?: {
      stage: 'scanning' | 'done'
      current: number
      total: number
      message: string
      assetData?: {
        id: string
        filename: string
        filePath: string
        thumbnailPath: string | null
        type: 'image' | 'video'
        width: number
        height: number
        size: number
        createdAt: string
        hasWorkflow: boolean
        isFavorite: boolean
        categoryId: string | null
        nsfwScore?: number
        nsfwLabel?: string
        tags?: string[]
      }
    }
    error_message?: string
  }>;

  gallery_stop_scan: () => Promise<{
    success: boolean
    error_message?: string
  }>;

  gallery_update_preview_blurred: (assetId: string, blurred: boolean) => Promise<{
    success: boolean
    asset?: {
      id: string
      filename: string
      filePath: string
      thumbnailPath: string | null
      type: 'image' | 'video'
      width: number
      height: number
      size: number
      createdAt: string
      hasWorkflow: boolean
      isFavorite: boolean
      categoryId: string | null
      nsfwScore?: number
      nsfwLabel?: string
      tags?: string[]
      previewBlurred: boolean
      description?: string
    }
    error_message?: string
  }>;

  gallery_update_asset_info: (
    assetId: string,
    filename?: string,
    description?: string,
    tags?: string[],
    rating?: number
  ) => Promise<{
    success: boolean
    asset?: {
      id: string
      filename: string
      filePath: string
      thumbnailPath: string | null
      type: 'image' | 'video'
      width: number
      height: number
      size: number
      createdAt: string
      hasWorkflow: boolean
      isFavorite: boolean
      categoryId: string | null
      nsfwScore?: number
      nsfwLabel?: string
      tags?: string[]
      previewBlurred: boolean
      description?: string
      rating?: number
    }
    error_message?: string
  }>;

  gallery_push_image_to_comfyui: (assetId: string) => Promise<{
    success: boolean
    filename?: string
    error_message?: string
  }>;

  gallery_export_to_prompt_library: (assetId: string) => Promise<{
    success: boolean
    error_message?: string
    prompt?: any
  }>;

  browse_files_for_shortcut: (options?: {
    title?: string
    file_types?: string[]
    multiple?: boolean
  }) => Promise<string[] | null>;

  get_monitor_data: () => Promise<{
    success: boolean
    data?: {
      cpu: { load: number; temp: number; power: number; freq: number; temp_available?: boolean }
      gpu: { load: number; temp: number; power: number; core_clock: number; gpu_available?: boolean }
      sys: {
        ram: { used: number; total: number; percent: number }
        vram: { used: number; total: number; percent: number }
        page: { used: number; total: number; percent: number }
      }
      net: { up: number; down: number }
      disks: Array<{ letter: string; name: string; used: number; total: number }>
    }
    error_message?: string
  }>;

  get_hardware_info: () => Promise<{
    success: boolean
    data?: {
      cpu: { name: string; cores: number; threads: number; vendor: string }
      gpu: { name: string; vendor: string; vram_total: number }
    }
    error_message?: string
  }>;

  get_network_interface_name: () => Promise<{
    success: boolean
    data?: string
    error_message?: string
  }>;

  get_hardware_monitor_status: () => Promise<{
    success: boolean
    data?: {
      available: boolean
      hasAdminPrivilege: boolean
      error?: string
    }
    error_message?: string
  }>;

  toggle_floating_window: (visible: boolean) => Promise<void>;

  get_floating_window_visible: () => Promise<{
    success: boolean
    visible: boolean
  }>;

  get_floating_window_settings: () => Promise<{
    success: boolean
    data: {
      opacity: number
      visibleItems: string[]
      itemOrder: string[]
    }
  }>;

  close_floating_window: () => Promise<{ success: boolean }>;

  resize_floating_window: (width: number, height: number) => Promise<{ success: boolean }>;

  floating_window_ready: (width?: number, height?: number) => Promise<{ success: boolean }>;

  update_floating_window_settings: (settings: {
    opacity: number
    visibleItems: string[]
    itemOrder: string[]
  }) => Promise<void>;
  
  // ========== 翻译 API ==========
  
  translate_text: (
    text: string,
    provider?: 'google' | 'llm',
    llm_config_id?: string,
    target_lang?: string
  ) => Promise<{
    success: boolean
    translated_text?: string
    provider?: string
    cached?: boolean
    error_message?: string
  }>;
  
  translate_batch: (
    items: { id: string; text: string }[],
    provider?: 'google' | 'llm',
    llm_config_id?: string,
    target_lang?: string
  ) => Promise<{
    success: boolean
    results: { id: string; translated: string; success: boolean; cached?: boolean; error?: string }[]
    provider?: string
    target_lang?: string
    error?: string
  }>;
  
  get_translation_settings: () => Promise<{
    success: boolean
    settings?: {
      provider: 'google' | 'llm'
      llmConfigId: string
      sourceLanguage: string
      targetLanguage: string
    }
  }>;
  
  update_translation_settings: (settings: {
    provider?: 'google' | 'llm'
    llmConfigId?: string
    sourceLanguage?: string
    targetLanguage?: string
  }) => Promise<{
    success: boolean
    message?: string
    settings?: {
      provider: 'google' | 'llm'
      llmConfigId: string
      sourceLanguage: string
      targetLanguage: string
    }
  }>;
  
  clear_translation_cache: () => Promise<{
    success: boolean
    message?: string
    deleted_count?: number
  }>;
  
  get_translation_cache_stats: () => Promise<{
    total_count?: number
    provider_counts?: Record<string, number>
    oldest_entry?: string
    newest_entry?: string
    cache_days?: number
    error?: string
  }>;
  
  // ========== 版本设置 API ==========
  
  get_version_settings: () => Promise<{
    success: boolean
    settings?: {
      autoTranslateChangelog: boolean
    }
    message?: string
  }>;
  
  update_version_settings: (settings: {
    autoTranslateChangelog?: boolean
  }) => Promise<{
    success: boolean
    message?: string
    settings?: {
      autoTranslateChangelog: boolean
    }
  }>;
  
  // ========== 缓存管理 API ==========
  
  get_cache_stats: () => Promise<{
    success: boolean
    data?: {
      caches: Array<{
        type: string
        name: string
        description: string
        size_bytes: number
        size_formatted: string
        file_count: number
        last_updated: string | null
        path: string
      }>
      total_size_bytes: number
      total_size_formatted: string
      total_file_count: number
    }
    error?: string
  }>;
  
  get_cache_types: () => Promise<{
    success: boolean
    data?: Array<{
      type: string
      name: string
      description: string
    }>
    error?: string
  }>;
  
  clear_cache: (cacheType: string) => Promise<{
    success: boolean
    data?: {
      type: string
      name: string
      cleared_size: number
      cleared_files: number
    }
    error?: string
  }>;
  
  clear_all_caches: () => Promise<{
    success: boolean
    data?: {
      results: Array<{
        success: boolean
        type: string
        name: string
        cleared_size: number
        cleared_files: number
        error?: string
      }>
      total_cleared_size: number
      total_cleared_size_formatted: string
      total_cleared_files: number
    }
    error?: string
  }>;
}

// 扩展 Window 接口
declare global {
  interface Window {
    pywebview: {
      api: PyWebViewAPI;
    };
  }
  
  // AI 消息片段事件
  interface WindowEventMap {
    ai_message_chunk: CustomEvent<{
      topic_id: string
      chunk: string
      done: boolean
    }>;
    topic_title_updated: CustomEvent<{
      topic_id: string
      new_title: string
    }>;
  }
}

export {}
