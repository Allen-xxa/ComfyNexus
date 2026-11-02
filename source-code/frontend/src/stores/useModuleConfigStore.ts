/**
 * 模块配置状态管理
 */

import { create } from 'zustand'
import { MODULE_REGISTRY, type ModuleConfig, type ModuleConfigData } from '@/types/module'
import { isDevelopment } from '@/utils/pywebview'

interface ModuleConfigState {
  // 状态
  modules: Record<string, ModuleConfig>
  loading: boolean
  
  // 方法
  loadConfig: () => Promise<void>
  saveConfig: () => Promise<boolean>
  toggleModule: (moduleId: string) => void
  resetConfig: () => Promise<void>
  isModuleEnabled: (moduleId: string) => boolean
  getEnabledModules: () => string[]
  updateModuleOrder: (moduleId: string, newOrder: number) => void
  reorderModules: (activeId: string, overId: string) => void
}

export const useModuleConfigStore = create<ModuleConfigState>((set, get) => ({
  modules: {},
  loading: false,
  
  /**
   * 从后端加载配置
   */
  loadConfig: async () => {
    set({ loading: true })
    try {
      // 在开发环境下，使用默认配置（所有非核心模块默认启用）
      if (isDevelopment()) {
        console.log('[useModuleConfigStore] 开发环境，使用默认配置')
        const defaultModules: Record<string, ModuleConfig> = {}
        
        Object.keys(MODULE_REGISTRY).forEach(id => {
          defaultModules[id] = { 
            enabled: true, 
            order: MODULE_REGISTRY[id].order 
          }
        })
        
        set({
          modules: defaultModules,
          loading: false
        })
        return
      }
      
      // 生产环境：直接调用 API（main.tsx 已经确保 API 就绪）
      const config: ModuleConfigData = await window.pywebview.api.get_module_config()
      set({
        modules: config.modules,
        loading: false
      })
    } catch (error) {
      console.error('[useModuleConfigStore] 加载配置失败:', error)
      // 使用默认配置 - 所有模块默认启用
      const defaultModules: Record<string, ModuleConfig> = {}
      
      Object.keys(MODULE_REGISTRY).forEach(id => {
        defaultModules[id] = { 
          enabled: true, 
          order: MODULE_REGISTRY[id].order 
        }
      })
      
      set({
        modules: defaultModules,
        loading: false
      })
    }
  },
  
  /**
   * 保存配置到后端
   */
  saveConfig: async () => {
    const { modules } = get()
    try {
      const config: ModuleConfigData = {
        version: '1.0.0',
        preset: 'custom',
        modules,
        ui: {
          theme: 'dark',
          language: 'zh-CN'
        }
      }
      const success = await window.pywebview.api.save_module_config(config)
      return success
    } catch (error) {
      console.error('保存配置失败:', error)
      return false
    }
  },
  
  /**
   * 切换模块启用状态
   */
  toggleModule: (moduleId: string) => {
    // 核心模块不可禁用（硬编码）
    const coreModuleIds = ['home', 'system-settings', 'about']
    if (coreModuleIds.includes(moduleId)) {
      console.warn(`核心模块 ${moduleId} 不可禁用`)
      return
    }
    
    set((state) => {
      const newModules = { ...state.modules }
      newModules[moduleId] = {
        ...newModules[moduleId],
        enabled: !newModules[moduleId].enabled
      }
      
      return { modules: newModules }
    })
  },
  
  /**
   * 重置配置为默认值
   */
  resetConfig: async () => {
    try {
      const config = await window.pywebview.api.reset_module_config()
      if (config && config.modules) {
        set({ modules: config.modules })
      }
    } catch (error) {
      console.error('重置配置失败:', error)
    }
  },
  
  /**
   * 检查模块是否启用
   */
  isModuleEnabled: (moduleId: string) => {
    // 核心模块始终启用（硬编码，不检测配置文件）
    const coreModuleIds = ['home', 'system-settings', 'about']
    if (coreModuleIds.includes(moduleId)) {
      return true
    }
    return get().modules[moduleId]?.enabled ?? false
  },
  
  /**
   * 获取已启用模块列表
   */
  getEnabledModules: () => {
    const { modules } = get()
    return Object.keys(modules).filter(id => modules[id].enabled)
  },
  
  /**
   * 更新单个模块的顺序
   */
  updateModuleOrder: (moduleId: string, newOrder: number) => {
    set((state) => {
      const newModules = { ...state.modules }
      newModules[moduleId] = {
        ...newModules[moduleId],
        order: newOrder
      }
      return { modules: newModules }
    })
  },
  
  /**
   * 重新排序模块（拖拽后调用）
   */
  reorderModules: (activeId: string, overId: string) => {
    set((state) => {
      const newModules = { ...state.modules }
      
      // 获取所有已启用模块并按 order 排序
      const enabledModuleIds = Object.keys(newModules)
        .filter(id => newModules[id].enabled)
        .sort((a, b) => newModules[a].order - newModules[b].order)
      
      // 找到拖动的模块和目标模块的索引
      const activeIndex = enabledModuleIds.indexOf(activeId)
      const overIndex = enabledModuleIds.indexOf(overId)
      
      if (activeIndex === -1 || overIndex === -1) {
        return state
      }
      
      // 重新排列数组
      const reorderedIds = [...enabledModuleIds]
      const [movedItem] = reorderedIds.splice(activeIndex, 1)
      reorderedIds.splice(overIndex, 0, movedItem)
      
      // 更新所有模块的 order
      reorderedIds.forEach((id, index) => {
        newModules[id] = {
          ...newModules[id],
          order: index + 1
        }
      })
      
      return { modules: newModules }
    })
  }
}))
