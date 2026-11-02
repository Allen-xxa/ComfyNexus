/**
 * 模块相关类型定义
 */

/**
 * 模块分类
 */
export type ModuleCategory = 'core' | 'management' | 'tool' | 'asset'

/**
 * 模块元数据
 */
export interface ModuleMetadata {
  id: string                    // 模块唯一标识
  name: string                  // 显示名称
  description: string           // 描述
  icon: string                  // Lucide 图标名称
  path: string                  // 路由路径
  component: string             // 组件名称
  category: ModuleCategory      // 分类
  isCore: boolean               // 是否为核心模块
  order: number                 // 显示顺序
  dependencies?: string[]       // 依赖的其他模块ID
}

/**
 * 模块配置
 */
export interface ModuleConfig {
  enabled: boolean              // 是否启用
  order: number                 // 显示顺序
}

/**
 * 完整的模块配置对象
 */
export interface ModuleConfigData {
  version: string
  preset: 'full' | 'minimal' | 'custom'
  modules: Record<string, ModuleConfig>
  ui: {
    theme: string
    language: string
  }
}

/**
 * 模块注册表
 * 包含所有模块的元数据
 */
export const MODULE_REGISTRY: Record<string, ModuleMetadata> = {
  'home': {
    id: 'home',
    name: '首页',
    description: '系统状态和创作者推荐',
    icon: 'Home',
    path: '/',
    component: 'HomePage',
    category: 'core',
    isCore: true,
    order: 1
  },
  'workspace': {
    id: 'workspace',
    name: '工作台',
    description: '在应用内使用 ComfyUI',
    icon: 'Monitor',
    path: '/workspace',
    component: 'WorkspacePage',
    category: 'tool',
    isCore: false,
    order: 2
  },
  'terminal': {
    id: 'terminal',
    name: '终端',
    description: '命令行终端',
    icon: 'Terminal',
    path: '/terminal',
    component: 'TerminalPage',
    category: 'tool',
    isCore: false,
    order: 3
  },
  'version-manage': {
    id: 'version-manage',
    name: '核心管理',
    description: 'ComfyUI 核心版本管理',
    icon: 'Cpu',
    path: '/version',
    component: 'VersionManagePage',
    category: 'management',
    isCore: false,
    order: 4
  },
  'plugin-manage': {
    id: 'plugin-manage',
    name: '插件管理',
    description: '已安装插件管理',
    icon: 'Puzzle',
    path: '/plugin',
    component: 'PluginManagePage',
    category: 'management',
    isCore: false,
    order: 5
  },
  'plugin-market': {
    id: 'plugin-market',
    name: '插件市场',
    description: '浏览和安装插件',
    icon: 'Store',
    path: '/plugin-market',
    component: 'PluginMarketPage',
    category: 'tool',
    isCore: false,
    order: 6
  },
  'dependency-manage': {
    id: 'dependency-manage',
    name: '依赖管理',
    description: 'Python 依赖包管理',
    icon: 'Package',
    path: '/dependency',
    component: 'DependencyManagePage',
    category: 'management',
    isCore: false,
    order: 7
  },
  'model-manage': {
    id: 'model-manage',
    name: 'LoRA 管理',
    description: 'LoRA 模型管理',
    icon: 'Box',
    path: '/model',
    component: 'ModelManagePage',
    category: 'asset',
    isCore: false,
    order: 8
  },
  'ai-assistant': {
    id: 'ai-assistant',
    name: 'AI 助手',
    description: 'AI 对话助手',
    icon: 'Bot',
    path: '/ai-assistant',
    component: 'AIAssistantPage',
    category: 'tool',
    isCore: false,
    order: 9
  },
  'workflow-manage': {
    id: 'workflow-manage',
    name: '工作流管理',
    description: '工作流编排和管理',
    icon: 'Workflow',
    path: '/workflow',
    component: 'WorkflowManagePage',
    category: 'asset',
    isCore: false,
    order: 10
  },
  'prompt-manage': {
    id: 'prompt-manage',
    name: '提示词管理',
    description: '提示词库管理',
    icon: 'FileText',
    path: '/prompt',
    component: 'PromptManagePage',
    category: 'asset',
    isCore: false,
    order: 11
  },
  'output-gallery': {
    id: 'output-gallery',
    name: '资产库',
    description: '生成图片浏览',
    icon: 'Image',
    path: '/gallery',
    component: 'OutputGalleryPage',
    category: 'asset',
    isCore: false,
    order: 12
  },
  'monitor-center': {
    id: 'monitor-center',
    name: '监控中心',
    description: '系统资源监控',
    icon: 'Activity',
    path: '/monitor',
    component: 'MonitorCenterPage',
    category: 'tool',
    isCore: false,
    order: 13
  },
  'env-manage': {
    id: 'env-manage',
    name: '环境设置',
    description: 'ComfyUI 环境配置',
    icon: 'FolderTree',
    path: '/env',
    component: 'EnvManagePage',
    category: 'management',
    isCore: false,
    order: 14
  },
  'system-settings': {
    id: 'system-settings',
    name: '系统设置',
    description: '应用配置和设置',
    icon: 'Settings',
    path: '/settings',
    component: 'SystemSettingsPage',
    category: 'core',
    isCore: true,
    order: 15
  },
  'about': {
    id: 'about',
    name: '关于',
    description: '关于 ComfyNexus',
    icon: 'Info',
    path: '/about',
    component: 'AboutPage',
    category: 'core',
    isCore: true,
    order: 16
  }
}
