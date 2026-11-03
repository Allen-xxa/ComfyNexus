import type { Workflow, WorkflowFolder, WorkflowInfoUpdate } from '@/types/workflow'

function getAPI() {
  // PyWebViewAPI 声明未覆盖本文件用到的 workflow_* 方法，只能按宽松句柄取用
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  if (typeof window !== 'undefined' && (window as any).pywebview) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return (window as any).pywebview.api
  }
  return null
}

export interface WorkflowConfig {
  version?: string
  use_global_path?: boolean
  global_path?: string
  env_paths?: Record<string, string>
}

export const workflowConfigApi = {
  getConfig: async (): Promise<WorkflowConfig | null> => {
    const api = getAPI()
    if (!api) return null
    try {
      const result = await api.workflow_get_config()
      if (result?.success) return result.config || {}
      return null
    } catch (error) {
      console.error('获取工作流配置失败:', error)
      return null
    }
  },

  updateConfig: async (updates: WorkflowConfig): Promise<boolean> => {
    const api = getAPI()
    if (!api) return false
    try {
      const result = await api.workflow_update_config(updates)
      return result?.success ?? false
    } catch (error) {
      console.error('更新工作流配置失败:', error)
      return false
    }
  },

  setEnvPath: async (envId: string, path: string): Promise<boolean> => {
    const api = getAPI()
    if (!api) return false
    try {
      const result = await api.workflow_set_env_path(envId, path)
      return result?.success ?? false
    } catch (error) {
      console.error('设置环境工作流目录失败:', error)
      return false
    }
  },

  setGlobalPath: async (path: string): Promise<boolean> => {
    const api = getAPI()
    if (!api) return false
    try {
      const result = await api.workflow_set_global_path(path)
      return result?.success ?? false
    } catch (error) {
      console.error('设置全局工作流目录失败:', error)
      return false
    }
  },

  setUseGlobalPath: async (useGlobal: boolean): Promise<boolean> => {
    const api = getAPI()
    if (!api) return false
    try {
      const result = await api.workflow_set_use_global_path(useGlobal)
      return result?.success ?? false
    } catch (error) {
      console.error('设置全局开关失败:', error)
      return false
    }
  },

  removeEnvPath: async (envId: string): Promise<boolean> => {
    const api = getAPI()
    if (!api) return false
    try {
      const result = await api.workflow_remove_env_path(envId)
      return result?.success ?? false
    } catch (error) {
      console.error('移除环境工作流目录失败:', error)
      return false
    }
  },

  initializeAllEnvPaths: async (): Promise<boolean> => {
    const api = getAPI()
    if (!api) return false
    try {
      const result = await api.workflow_initialize_all_env_paths()
      return result?.success ?? false
    } catch (error) {
      console.error('初始化环境工作流目录失败:', error)
      return false
    }
  }
}

export const workflowApi = {
  getWorkflows: async (): Promise<Workflow[]> => {
    const api = getAPI()
    if (!api) {
      console.warn('pywebview API 不可用')
      return []
    }
    try {
      const result = await api.get_workflows()
      if (!result || !result.success) {
        console.error('获取工作流失败:', result?.error)
        return []
      }
      return result.workflows || []
    } catch (error) {
      console.error('获取工作流异常:', error)
      return []
    }
  },

  getWorkflow: async (id: string): Promise<Workflow | null> => {
    const api = getAPI()
    if (!api) {
      console.warn('pywebview API 不可用')
      return null
    }
    try {
      const result = await api.get_workflow(id)
      if (!result || !result.success) {
        console.error('获取工作流详情失败:', result?.error)
        return null
      }
      return result.workflow
    } catch (error) {
      console.error('获取工作流详情异常:', error)
      return null
    }
  },

  deleteWorkflow: async (id: string): Promise<boolean> => {
    const api = getAPI()
    if (!api) {
      console.warn('pywebview API 不可用')
      return false
    }
    try {
      const result = await api.delete_workflow(id)
      return result?.success ?? false
    } catch (error) {
      console.error('删除工作流异常:', error)
      return false
    }
  },

  importWorkflow: async (file: File): Promise<Workflow | null> => {
    const api = getAPI()
    if (!api) {
      console.warn('pywebview API 不可用')
      return null
    }
    try {
      const content = await file.text()
      const result = await api.import_workflow(content, file.name)
      if (!result || !result.success) {
        console.error('导入工作流失败:', result?.error)
        return null
      }
      return result.workflow
    } catch (error) {
      console.error('导入工作流异常:', error)
      return null
    }
  },

  exportWorkflow: async (id: string): Promise<string | null> => {
    const api = getAPI()
    if (!api) {
      console.warn('pywebview API 不可用')
      return null
    }
    try {
      const result = await api.export_workflow(id)
      if (!result || !result.success) {
        console.error('导出工作流失败:', result?.error)
        return null
      }
      return result.content
    } catch (error) {
      console.error('导出工作流异常:', error)
      return null
    }
  },

  updateWorkflowInfo: async (id: string, info: WorkflowInfoUpdate): Promise<Workflow | null> => {
    const api = getAPI()
    if (!api) {
      console.warn('pywebview API 不可用')
      return null
    }
    try {
      const result = await api.update_workflow_info(id, info)
      if (!result || !result.success) {
        console.error('更新工作流信息失败:', result?.error)
        return null
      }
      // 确保返回的 workflow 对象中必要字段存在
      const workflow = result.workflow
      if (workflow) {
        workflow.tags = workflow.tags || []
        workflow.description = workflow.description || ''
        workflow.previews = workflow.previews || []
        workflow.name = workflow.name || ''
      }
      return workflow
    } catch (error) {
      console.error('更新工作流信息异常:', error)
      return null
    }
  },

  toggleFavorite: async (id: string): Promise<{ isFavorite: boolean } | null> => {
    const api = getAPI()
    if (!api) {
      console.warn('pywebview API 不可用')
      return null
    }
    try {
      const result = await api.toggle_favorite(id)
      if (!result || !result.success) {
        console.error('切换收藏失败:', result?.error)
        return null
      }
      return { isFavorite: result.isFavorite }
    } catch (error) {
      console.error('切换收藏异常:', error)
      return null
    }
  },

  getFolders: async (): Promise<WorkflowFolder[]> => {
    const api = getAPI()
    if (!api) {
      console.warn('pywebview API 不可用')
      return []
    }
    try {
      const result = await api.get_workflow_folders()
      if (!result || !result.success) {
        console.error('获取文件夹失败:', result?.error)
        return []
      }
      return result.folders || []
    } catch (error) {
      console.error('获取文件夹异常:', error)
      return []
    }
  },

  createFolder: async (name: string, parentId?: string): Promise<WorkflowFolder | null> => {
    const api = getAPI()
    if (!api) {
      console.warn('pywebview API 不可用')
      return null
    }
    try {
      const result = await api.create_workflow_folder(name, parentId)
      if (!result || !result.success) {
        console.error('创建文件夹失败:', result?.error)
        return null
      }
      return result.folder
    } catch (error) {
      console.error('创建文件夹异常:', error)
      return null
    }
  },

  updateFolder: async (id: string, updates: Partial<WorkflowFolder>): Promise<WorkflowFolder | null> => {
    const api = getAPI()
    if (!api) {
      console.warn('pywebview API 不可用')
      return null
    }
    try {
      const result = await api.update_workflow_folder(id, updates)
      if (!result || !result.success) {
        console.error('更新文件夹失败:', result?.error)
        return null
      }
      return result.folder
    } catch (error) {
      console.error('更新文件夹异常:', error)
      return null
    }
  },

  deleteFolder: async (id: string, moveContentsToRoot = false): Promise<boolean> => {
    const api = getAPI()
    if (!api) {
      console.warn('pywebview API 不可用')
      return false
    }
    try {
      const result = await api.delete_workflow_folder(id, moveContentsToRoot)
      return result?.success ?? false
    } catch (error) {
      console.error('删除文件夹异常:', error)
      return false
    }
  },

  moveWorkflowToFolder: async (workflowId: string, folderId: string | null): Promise<Workflow | null> => {
    const api = getAPI()
    if (!api) {
      console.warn('pywebview API 不可用')
      return null
    }
    try {
      const result = await api.move_workflow_to_folder(workflowId, folderId)
      if (!result || !result.success) {
        console.error('移动工作流失败:', result?.error)
        return null
      }
      return result.workflow
    } catch (error) {
      console.error('移动工作流异常:', error)
      return null
    }
  },

  batchMoveToFolder: async (workflowIds: string[], folderId: string | null): Promise<{ success: boolean; movedCount: number }> => {
    const api = getAPI()
    if (!api) {
      console.warn('pywebview API 不可用')
      return { success: false, movedCount: 0 }
    }
    try {
      const result = await api.batch_move_workflows_to_folder(workflowIds, folderId)
      if (!result || !result.success) {
        console.error('批量移动工作流失败:', result?.error)
        return { success: false, movedCount: 0 }
      }
      return { success: true, movedCount: result.moved_count || 0 }
    } catch (error) {
      console.error('批量移动工作流异常:', error)
      return { success: false, movedCount: 0 }
    }
  },

  batchToggleFavorite: async (workflowIds: string[]): Promise<{ success: boolean }> => {
    const api = getAPI()
    if (!api) {
      console.warn('pywebview API 不可用')
      return { success: false }
    }
    try {
      const result = await api.batch_toggle_workflow_favorite(workflowIds)
      if (!result || !result.success) {
        console.error('批量切换收藏失败:', result?.error)
        return { success: false }
      }
      return { success: true }
    } catch (error) {
      console.error('批量切换收藏异常:', error)
      return { success: false }
    }
  },

  batchDeleteWorkflows: async (workflowIds: string[]): Promise<{ success: boolean; deletedCount: number }> => {
    const api = getAPI()
    if (!api) {
      console.warn('pywebview API 不可用')
      return { success: false, deletedCount: 0 }
    }
    try {
      const result = await api.batch_delete_workflows(workflowIds)
      if (!result || !result.success) {
        console.error('批量删除工作流失败:', result?.error)
        return { success: false, deletedCount: 0 }
      }
      return { success: true, deletedCount: result.deleted_count || 0 }
    } catch (error) {
      console.error('批量删除工作流异常:', error)
      return { success: false, deletedCount: 0 }
    }
  },

  checkPluginsStatus: async (plugins: Array<{githubUrl: string; name: string}>): Promise<Record<string, 'installed' | 'missing' | 'unknown'>> => {
    const api = getAPI()
    if (!api) {
      console.warn('pywebview API 不可用')
      return {}
    }
    try {
      console.log('checkPluginsStatus input:', plugins)
      const result = await api.check_plugins_status(plugins)
      console.log('checkPluginsStatus API result:', result)
      if (!result || !result.success) {
        console.error('检查插件状态失败:', result?.error)
        return {}
      }
      
      console.log('checkPluginsStatus final statusMap:', result.status)
      return result.status || {}
    } catch (error) {
      console.error('检查插件状态异常:', error)
      return {}
    }
  },

  getNodeTypeMap: async (): Promise<{
    preemptionMap: Record<string, string>
    rextMap: Record<string, string[]>
    patterns: [string, string][]
    pluginInfo: Record<string, { name: string; github_url: string; node_count: number }>
    localPlugins: Record<string, { name: string; github_url: string; enabled: boolean }>
    builtinNodes: Record<string, { category: string; display_name: string; description: string }>
    cnrIdMap: Record<string, string>
  } | null> => {
    const api = getAPI()
    if (!api) {
      console.warn('pywebview API 不可用')
      return null
    }
    try {
      const result = await api.get_node_type_map()
      if (!result || !result.success) {
        console.error('获取节点类型映射表失败:', result?.error)
        return null
      }
      return {
        preemptionMap: result.data?.preemption_map || {},
        rextMap: result.data?.rext_map || {},
        patterns: result.data?.patterns || [],
        pluginInfo: result.data?.plugin_info || {},
        localPlugins: result.data?.local_plugins || {},
        builtinNodes: result.data?.builtin_nodes || {},
        cnrIdMap: result.data?.cnr_id_map || {}
      }
    } catch (error) {
      console.error('获取节点类型映射表异常:', error)
      return null
    }
  },

  refreshNodeTypeMap: async (): Promise<{
    preemptionMap: Record<string, string>
    rextMap: Record<string, string[]>
    patterns: [string, string][]
    pluginInfo: Record<string, { name: string; github_url: string; node_count: number }>
  } | null> => {
    const api = getAPI()
    if (!api) {
      console.warn('pywebview API 不可用')
      return null
    }
    try {
      const result = await api.refresh_node_type_map()
      if (!result || !result.success) {
        console.error('刷新节点类型映射表失败:', result?.error)
        return null
      }
      return {
        preemptionMap: result.data?.preemption_map || {},
        rextMap: result.data?.rext_map || {},
        patterns: result.data?.patterns || [],
        pluginInfo: result.data?.plugin_info || {}
      }
    } catch (error) {
      console.error('刷新节点类型映射表异常:', error)
      return null
    }
  },

  scanLocalNodes: async (force: boolean = false): Promise<{
    success: boolean
    pluginCount: number
    nodeCount: number
    v1Count: number
    v3Count: number
    frontendCount: number
    elapsedSeconds: number
    error?: string
  } | null> => {
    const api = getAPI()
    if (!api) {
      console.warn('pywebview API 不可用')
      return null
    }
    try {
      const result = await api.scan_local_nodes(force)
      return result
    } catch (error) {
      console.error('扫描本地节点异常:', error)
      return { success: false, pluginCount: 0, nodeCount: 0, v1Count: 0, v3Count: 0, frontendCount: 0, elapsedSeconds: 0, error: String(error) }
    }
  },

  getLocalNodeMap: async (): Promise<{
    success: boolean
    data?: {
      version: number
      timestamp: number
      comfyuiPath: string
      nodes: Record<string, { nodeType: string; githubUrl: string; pluginName: string }>
      plugins: Record<string, { githubUrl: string | null; v1Count: number; v3Count: number; frontendCount: number }>
    }
    error?: string
  } | null> => {
    const api = getAPI()
    if (!api) {
      console.warn('pywebview API 不可用')
      return null
    }
    try {
      const result = await api.get_local_node_map()
      return result
    } catch (error) {
      console.error('获取本地节点映射表异常:', error)
      return { success: false, error: String(error) }
    }
  },

  getLocalScanStatus: async (): Promise<{
    success: boolean
    initialized: boolean
    hasCache: boolean
    needsRescan: boolean
    comfyuiPath?: string
    error?: string
  } | null> => {
    const api = getAPI()
    if (!api) {
      console.warn('pywebview API 不可用')
      return null
    }
    try {
      const result = await api.get_local_scan_status()
      return result
    } catch (error) {
      console.error('获取本地扫描状态异常:', error)
      return { success: false, initialized: false, hasCache: false, needsRescan: true, error: String(error) }
    }
  }
}
