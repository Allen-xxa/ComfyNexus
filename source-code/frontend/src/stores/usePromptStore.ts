/**
 * 提示词管理状态管理
 * 
 * 负责管理提示词配方和分类，包括：
 * - 加载和保存提示词/分类
 * - 创建、更新、删除提示词/分类
 * - 批量操作和收藏管理
 * - 图片上传
 */

import { create } from 'zustand'
import { mockPrompts, mockCategories } from '@/mocks/prompt'
import type { CategoryIconName } from '@/mocks/prompt'

/**
 * 生成参数（决定这条配方能否被复现）
 */
export interface PromptParams {
  model: string
  sampler: string
  scheduler: string
  steps: number | null
  cfg: number | null
  seed: number | null
  width: number | null
  height: number | null
  duration: number | null
  assetType: string
  sourceAssetId: string
}

export const EMPTY_PROMPT_PARAMS: PromptParams = {
  model: '',
  sampler: '',
  scheduler: '',
  steps: null,
  cfg: null,
  seed: null,
  width: null,
  height: null,
  duration: null,
  assetType: '',
  sourceAssetId: ''
}

/**
 * 提示词配方接口
 */
export interface Prompt {
  id: string
  name: string
  positivePrompt: string
  negativePrompt: string
  previewImage: string
  remark: string
  categoryId: string
  tags: string[]
  createdAt: string
  updatedAt: string
  isFavorite: boolean
  usageCount?: number
  params: PromptParams
}

/**
 * 分类接口
 */
export interface PromptCategory {
  id: string
  name: string
  icon: CategoryIconName
  parentId: string | null
  sortOrder: number
  isSystem: boolean
  children?: PromptCategory[]
}

/**
 * 后端 API 响应接口（snake_case）
 */
interface PromptResponse {
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
  usage_count?: number
  model?: string
  sampler?: string
  scheduler?: string
  steps?: number | null
  cfg?: number | null
  seed?: number | null
  width?: number | null
  height?: number | null
  duration?: number | null
  asset_type?: string
  source_asset_id?: string
}

/**
 * 后端分类响应接口（snake_case）
 */
interface CategoryResponse {
  id: string
  name: string
  icon: string
  parent_id: string | null
  sort_order: number
  is_system: boolean
  children?: CategoryResponse[]
}

/**
 * 提示词输入接口（创建/更新时使用）
 */
export interface PromptInput {
  name: string
  positivePrompt: string
  categoryId?: string
  negativePrompt?: string
  previewImage?: string
  remark?: string
  tags?: string[]
  params?: PromptParams
}

/**
 * 分类输入接口（创建/更新时使用）
 */
export interface CategoryInput {
  name: string
  icon?: string
  parentId?: string | null
}

/**
 * 筛选标签接口
 */
export interface FilterTag {
  id: string
  name: string
}

/**
 * Prompt Store 状态接口
 */
interface PromptStore {
  prompts: Prompt[]
  categories: PromptCategory[]
  filterTags: FilterTag[]
  selectedPrompt: Prompt | null
  selectedCategoryId: string
  selectedPromptIds: string[]
  isBatchMode: boolean
  searchQuery: string
  activeFilterTag: string
  isLoading: boolean
  error: string | null
  
  loadData: () => Promise<void>
  loadPrompts: () => Promise<void>
  loadCategories: () => Promise<void>
  
  setSelectedPrompt: (prompt: Prompt | null) => void
  setSelectedCategoryId: (categoryId: string) => void
  setActiveFilterTag: (tagId: string) => void
  setSearchQuery: (query: string) => void
  toggleBatchMode: () => void
  setBatchMode: (mode: boolean) => void
  togglePromptSelection: (id: string) => void
  setSelectedPromptIds: (ids: string[]) => void
  selectAllPrompts: () => void
  clearSelection: () => void
  
  createPrompt: (data: PromptInput) => Promise<{ prompt: Prompt | null; error?: string }>
  updatePrompt: (id: string, updates: Partial<PromptInput>) => Promise<boolean>
  deletePrompt: (id: string) => Promise<boolean>
  deleteSelectedPrompts: () => Promise<boolean>
  toggleFavorite: (id: string) => Promise<boolean>
  moveSelectedToCategory: (categoryId: string) => Promise<boolean>
  movePromptsToCategory: (promptIds: string[], categoryId: string) => Promise<boolean>
  uploadImage: (fileData: string, filename?: string) => Promise<string | null>
  
  createCategory: (data: CategoryInput) => Promise<PromptCategory | null>
  updateCategory: (id: string, updates: Partial<CategoryInput>) => Promise<boolean>
  deleteCategory: (id: string) => Promise<boolean>
  
  exportPrompts: (promptIds?: string[]) => Promise<{ success: boolean; data?: unknown; error?: string }>
  importPrompts: (data: unknown) => Promise<{ 
    success: boolean
    importedCount?: number
    importedCategories?: number
    message?: string
    error?: string 
  }>
  
  refreshFilterTags: () => void
  clearError: () => void
  
  getFilteredPrompts: () => Prompt[]
  getPromptCount: () => number
}

/**
 * 检查是否在开发环境
 */
const isDevelopment = (): boolean => {
  return !window.pywebview || !window.pywebview.api
}

/**
 * 转换图片 URL
 * 将 local://images/xxx 转换为 /prompt/images/xxx
 */
const resolveImageUrl = (imageUrl: string): string => {
  if (!imageUrl) return ''
  
  if (imageUrl.startsWith('local://images/')) {
    return imageUrl.replace('local://images/', '/prompt/images/')
  }
  
  return imageUrl
}

/**
 * 转换后端提示词数据为前端格式
 */
const transformPrompt = (backendPrompt: PromptResponse): Prompt => ({
  id: backendPrompt.id,
  name: backendPrompt.name,
  positivePrompt: backendPrompt.positive_prompt,
  negativePrompt: backendPrompt.negative_prompt || '',
  previewImage: resolveImageUrl(backendPrompt.preview_image || ''),
  remark: backendPrompt.remark || '',
  categoryId: backendPrompt.category_id || '',
  tags: backendPrompt.tags || [],
  createdAt: backendPrompt.created_at,
  updatedAt: backendPrompt.updated_at,
  isFavorite: backendPrompt.is_favorite || false,
  params: {
    model: backendPrompt.model || '',
    sampler: backendPrompt.sampler || '',
    scheduler: backendPrompt.scheduler || '',
    steps: backendPrompt.steps ?? null,
    cfg: backendPrompt.cfg ?? null,
    seed: backendPrompt.seed ?? null,
    width: backendPrompt.width ?? null,
    height: backendPrompt.height ?? null,
    duration: backendPrompt.duration ?? null,
    assetType: backendPrompt.asset_type || '',
    sourceAssetId: backendPrompt.source_asset_id || ''
  }
})

/**
 * 前端参数对象转后端 snake_case
 */
export const toBackendParams = (params: PromptParams) => ({
  model: params.model,
  sampler: params.sampler,
  scheduler: params.scheduler,
  steps: params.steps,
  cfg: params.cfg,
  seed: params.seed,
  width: params.width,
  height: params.height,
  duration: params.duration,
  asset_type: params.assetType,
  source_asset_id: params.sourceAssetId
})

/**
 * 转换后端分类数据为前端格式
 */
const transformCategory = (backendCategory: CategoryResponse): PromptCategory => ({
  id: backendCategory.id,
  name: backendCategory.name,
  icon: (backendCategory.icon || 'folder') as CategoryIconName,
  parentId: backendCategory.parent_id,
  sortOrder: backendCategory.sort_order || 0,
  isSystem: backendCategory.is_system || false,
  children: backendCategory.children?.map(transformCategory)
})

/**
 * 获取分类及其所有子分类的 ID 列表
 */
const getChildCategoryIds = (categories: PromptCategory[], targetId: string): string[] => {
  const result: string[] = [targetId]
  
  const findChildren = (cats: PromptCategory[]) => {
    for (const cat of cats) {
      if (cat.parentId === targetId || result.includes(cat.parentId || '')) {
        if (!result.includes(cat.id)) {
          result.push(cat.id)
        }
      }
      if (cat.children && cat.children.length > 0) {
        findChildren(cat.children)
      }
    }
  }
  
  findChildren(categories)
  return result
}

/**
 * Prompt Store 实现
 */
export const usePromptStore = create<PromptStore>((set, get) => ({
  prompts: [],
  categories: [],
  filterTags: [],
  selectedPrompt: null,
  selectedCategoryId: 'all',
  selectedPromptIds: [],
  isBatchMode: false,
  searchQuery: '',
  activeFilterTag: 'all',
  isLoading: false,
  error: null,

  /**
   * 加载所有数据（提示词和分类）
   */
  loadData: async () => {
    console.log('[usePromptStore] 加载所有数据')
    set({ isLoading: true, error: null })
    
    try {
      await Promise.all([
        get().loadPrompts(),
        get().loadCategories()
      ])
      
      get().refreshFilterTags()
      
      set({ isLoading: false })
      console.log('[usePromptStore] 数据加载完成')
    } catch (error) {
      console.error('[usePromptStore] 加载数据异常:', error)
      set({
        isLoading: false,
        error: `加载数据异常: ${error}`
      })
    }
  },

  /**
   * 加载提示词列表
   */
  loadPrompts: async () => {
    console.log('[usePromptStore] 加载提示词列表')
    
    try {
      if (isDevelopment()) {
        console.log('[usePromptStore] 开发环境：使用 Mock 数据')
        await new Promise(resolve => setTimeout(resolve, 300))
        set({ prompts: mockPrompts })
        return
      }
      
      const response = await window.pywebview.api.prompt_get_all()
      
      if (!response.success || !response.prompts) {
        console.error('[usePromptStore] 加载提示词失败:', response.error_message)
        set({ error: response.error_message || '加载提示词失败' })
        return
      }
      
      const prompts = (response.prompts as PromptResponse[]).map(transformPrompt)
      set({ prompts })
      
      console.log('[usePromptStore] 提示词加载成功，共', prompts.length, '个')
    } catch (error) {
      console.error('[usePromptStore] 加载提示词异常:', error)
      set({ error: `加载提示词异常: ${error}` })
    }
  },

  /**
   * 加载分类列表
   */
  loadCategories: async () => {
    console.log('[usePromptStore] 加载分类列表')
    
    try {
      if (isDevelopment()) {
        console.log('[usePromptStore] 开发环境：使用 Mock 分类数据')
        await new Promise(resolve => setTimeout(resolve, 200))
        set({ categories: mockCategories })
        return
      }
      
      const response = await window.pywebview.api.category_get_all()
      
      if (!response.success || !response.categories) {
        console.error('[usePromptStore] 加载分类失败:', response.error_message)
        set({ error: response.error_message || '加载分类失败' })
        return
      }
      
      const categories = (response.categories as CategoryResponse[]).map(transformCategory)
      set({ categories })
      
      console.log('[usePromptStore] 分类加载成功，共', categories.length, '个')
    } catch (error) {
      console.error('[usePromptStore] 加载分类异常:', error)
      set({ error: `加载分类异常: ${error}` })
    }
  },

  setSelectedPrompt: (prompt) => set({ selectedPrompt: prompt }),

  setSelectedCategoryId: (categoryId) => set({ selectedCategoryId: categoryId }),

  setActiveFilterTag: (tagId) => set({ activeFilterTag: tagId }),

  setSearchQuery: (query) => set({ searchQuery: query }),

  toggleBatchMode: () => set((state) => ({
    isBatchMode: !state.isBatchMode,
    selectedPromptIds: state.isBatchMode ? [] : state.selectedPromptIds
  })),

  setBatchMode: (mode) => set({ isBatchMode: mode }),

  togglePromptSelection: (id) => set((state) => ({
    selectedPromptIds: state.selectedPromptIds.includes(id)
      ? state.selectedPromptIds.filter((i) => i !== id)
      : [...state.selectedPromptIds, id]
  })),

  setSelectedPromptIds: (ids) => set({ selectedPromptIds: ids }),

  selectAllPrompts: () => set({
    selectedPromptIds: get().getFilteredPrompts().map((p) => p.id)
  }),

  clearSelection: () => set({ selectedPromptIds: [] }),

  /**
   * 创建提示词
   */
  createPrompt: async (data) => {
    console.log('[usePromptStore] 创建提示词:', data.name)
    
    try {
      if (!data.name || data.name.trim() === '') {
        set({ error: '配方名称不能为空' })
        return { prompt: null, error: '配方名称不能为空' }
      }
      
      if (!data.positivePrompt || data.positivePrompt.trim() === '') {
        set({ error: '正向提示词不能为空' })
        return { prompt: null, error: '正向提示词不能为空' }
      }
      
      set({ isLoading: true, error: null })
      
      if (isDevelopment()) {
        console.log('[usePromptStore] 开发环境：使用 Mock 创建')
        await new Promise(resolve => setTimeout(resolve, 500))
        
        const newPrompt: Prompt = {
          id: `mock-${Date.now()}`,
          name: data.name.trim(),
          positivePrompt: data.positivePrompt.trim(),
          negativePrompt: data.negativePrompt || '',
          previewImage: data.previewImage || '',
          remark: data.remark || '',
          categoryId: data.categoryId || '',
          tags: data.tags || [],
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
          isFavorite: false,
          params: data.params || { ...EMPTY_PROMPT_PARAMS }
        }
        
        set((state) => ({
          prompts: [newPrompt, ...state.prompts],
          isLoading: false
        }))
        
        get().refreshFilterTags()
        return { prompt: newPrompt }
      }
      
      const response = await window.pywebview.api.prompt_create(
        data.name.trim(),
        data.positivePrompt.trim(),
        data.categoryId || '',
        data.negativePrompt || '',
        data.previewImage || '',
        data.remark || '',
        data.tags || [],
        toBackendParams(data.params || EMPTY_PROMPT_PARAMS)
      )
      
      if (!response.success || !response.prompt) {
        console.error('[usePromptStore] 创建提示词失败:', response.error_message)
        set({
          isLoading: false,
          error: response.error_message || '创建提示词失败'
        })
        return { prompt: null, error: response.error_message || '创建提示词失败' }
      }
      
      const newPrompt = transformPrompt(response.prompt as PromptResponse)
      
      set((state) => ({
        prompts: [newPrompt, ...state.prompts],
        isLoading: false
      }))
      
      get().refreshFilterTags()
      console.log('[usePromptStore] 提示词创建成功:', newPrompt.id)
      return { prompt: newPrompt }
      
    } catch (error) {
      console.error('[usePromptStore] 创建提示词异常:', error)
      set({
        isLoading: false,
        error: `创建提示词异常: ${error}`
      })
      return { prompt: null, error: `创建提示词异常: ${error}` }
    }
  },

  /**
   * 更新提示词
   */
  updatePrompt: async (id, updates) => {
    console.log('[usePromptStore] 更新提示词:', id)
    
    try {
      set({ isLoading: true, error: null })
      
      if (isDevelopment()) {
        console.log('[usePromptStore] 开发环境：使用 Mock 更新')
        await new Promise(resolve => setTimeout(resolve, 500))
        
        set((state) => ({
          prompts: state.prompts.map((p) =>
            p.id === id ? { ...p, ...updates, updatedAt: new Date().toISOString() } : p
          ),
          selectedPrompt: state.selectedPrompt?.id === id
            ? { ...state.selectedPrompt, ...updates }
            : state.selectedPrompt,
          isLoading: false
        }))
        
        return true
      }
      
      const response = await window.pywebview.api.prompt_update(
        id,
        updates.name,
        updates.positivePrompt,
        updates.categoryId,
        updates.negativePrompt,
        updates.previewImage,
        updates.remark,
        updates.tags,
        updates.params ? toBackendParams(updates.params) : undefined
      )
      
      if (!response.success) {
        console.error('[usePromptStore] 更新提示词失败:', response.error_message)
        set({
          isLoading: false,
          error: response.error_message || '更新提示词失败'
        })
        return false
      }
      
      await get().loadPrompts()
      get().refreshFilterTags()
      set({ isLoading: false })
      
      console.log('[usePromptStore] 提示词更新成功')
      return true
      
    } catch (error) {
      console.error('[usePromptStore] 更新提示词异常:', error)
      set({
        isLoading: false,
        error: `更新提示词异常: ${error}`
      })
      return false
    }
  },

  /**
   * 删除提示词
   */
  deletePrompt: async (id) => {
    console.log('[usePromptStore] 删除提示词:', id)
    
    try {
      set({ isLoading: true, error: null })
      
      if (isDevelopment()) {
        console.log('[usePromptStore] 开发环境：使用 Mock 删除')
        await new Promise(resolve => setTimeout(resolve, 500))
        
        set((state) => ({
          prompts: state.prompts.filter((p) => p.id !== id),
          selectedPrompt: state.selectedPrompt?.id === id ? null : state.selectedPrompt,
          selectedPromptIds: state.selectedPromptIds.filter((i) => i !== id),
          isLoading: false
        }))
        
        return true
      }
      
      const response = await window.pywebview.api.prompt_delete(id)
      
      if (!response.success) {
        console.error('[usePromptStore] 删除提示词失败:', response.error_message)
        set({
          isLoading: false,
          error: response.error_message || '删除提示词失败'
        })
        return false
      }
      
      set((state) => ({
        prompts: state.prompts.filter((p) => p.id !== id),
        selectedPrompt: state.selectedPrompt?.id === id ? null : state.selectedPrompt,
        selectedPromptIds: state.selectedPromptIds.filter((i) => i !== id),
        isLoading: false
      }))
      
      get().refreshFilterTags()
      console.log('[usePromptStore] 提示词删除成功')
      return true
      
    } catch (error) {
      console.error('[usePromptStore] 删除提示词异常:', error)
      set({
        isLoading: false,
        error: `删除提示词异常: ${error}`
      })
      return false
    }
  },

  /**
   * 批量删除提示词
   */
  deleteSelectedPrompts: async () => {
    const { selectedPromptIds } = get()
    if (selectedPromptIds.length === 0) return false
    
    console.log('[usePromptStore] 批量删除提示词:', selectedPromptIds.length, '个')
    
    try {
      set({ isLoading: true, error: null })
      
      if (isDevelopment()) {
        console.log('[usePromptStore] 开发环境：使用 Mock 批量删除')
        await new Promise(resolve => setTimeout(resolve, 500))
        
        set((state) => ({
          prompts: state.prompts.filter((p) => !selectedPromptIds.includes(p.id)),
          selectedPromptIds: [],
          isLoading: false
        }))
        
        get().refreshFilterTags()
        return true
      }
      
      const response = await window.pywebview.api.prompt_batch_delete(selectedPromptIds)
      
      if (!response.success) {
        console.error('[usePromptStore] 批量删除失败:', response.error_message)
        set({
          isLoading: false,
          error: response.error_message || '批量删除失败'
        })
        return false
      }
      
      set((state) => ({
        prompts: state.prompts.filter((p) => !selectedPromptIds.includes(p.id)),
        selectedPromptIds: [],
        isLoading: false
      }))
      
      get().refreshFilterTags()
      console.log('[usePromptStore] 批量删除成功，删除', response.deleted_count, '个')
      return true
      
    } catch (error) {
      console.error('[usePromptStore] 批量删除异常:', error)
      set({
        isLoading: false,
        error: `批量删除异常: ${error}`
      })
      return false
    }
  },

  /**
   * 切换收藏状态
   */
  toggleFavorite: async (id) => {
    console.log('[usePromptStore] 切换收藏状态:', id)
    
    try {
      if (isDevelopment()) {
        console.log('[usePromptStore] 开发环境：使用 Mock 切换收藏')
        await new Promise(resolve => setTimeout(resolve, 300))
        
        set((state) => ({
          prompts: state.prompts.map((p) =>
            p.id === id ? { ...p, isFavorite: !p.isFavorite } : p
          )
        }))
        
        return true
      }
      
      const response = await window.pywebview.api.prompt_toggle_favorite(id)
      
      if (!response.success) {
        console.error('[usePromptStore] 切换收藏失败:', response.error_message)
        set({ error: response.error_message || '切换收藏失败' })
        return false
      }
      
      set((state) => ({
        prompts: state.prompts.map((p) =>
          p.id === id ? { ...p, isFavorite: response.is_favorite ?? false } : p
        )
      }))
      
      console.log('[usePromptStore] 收藏状态切换成功:', response.is_favorite)
      return true
      
    } catch (error) {
      console.error('[usePromptStore] 切换收藏异常:', error)
      set({ error: `切换收藏异常: ${error}` })
      return false
    }
  },

  /**
   * 批量移动到分类
   */
  moveSelectedToCategory: async (categoryId) => {
    const { selectedPromptIds } = get()
    if (selectedPromptIds.length === 0) return false
    
    console.log('[usePromptStore] 批量移动到分类:', categoryId)
    
    try {
      set({ isLoading: true, error: null })
      
      if (isDevelopment()) {
        console.log('[usePromptStore] 开发环境：使用 Mock 批量移动')
        await new Promise(resolve => setTimeout(resolve, 500))
        
        set((state) => ({
          prompts: state.prompts.map((p) =>
            selectedPromptIds.includes(p.id)
              ? { ...p, categoryId, updatedAt: new Date().toISOString() }
              : p
          ),
          selectedPromptIds: [],
          isBatchMode: false,
          isLoading: false
        }))
        
        return true
      }
      
      const response = await window.pywebview.api.prompt_batch_move(selectedPromptIds, categoryId)
      
      if (!response.success) {
        console.error('[usePromptStore] 批量移动失败:', response.error_message)
        set({
          isLoading: false,
          error: response.error_message || '批量移动失败'
        })
        return false
      }
      
      set((state) => ({
        prompts: state.prompts.map((p) =>
          selectedPromptIds.includes(p.id)
            ? { ...p, categoryId, updatedAt: new Date().toISOString() }
            : p
        ),
        selectedPromptIds: [],
        isBatchMode: false,
        isLoading: false
      }))
      
      console.log('[usePromptStore] 批量移动成功，移动', response.moved_count, '个')
      return true
      
    } catch (error) {
      console.error('[usePromptStore] 批量移动异常:', error)
      set({
        isLoading: false,
        error: `批量移动异常: ${error}`
      })
      return false
    }
  },

  /**
   * 移动指定提示词到分类
   */
  movePromptsToCategory: async (promptIds, categoryId) => {
    if (promptIds.length === 0) return false
    
    console.log('[usePromptStore] 移动提示词到分类:', promptIds.length, '个 ->', categoryId)
    
    try {
      set({ isLoading: true, error: null })
      
      if (isDevelopment()) {
        console.log('[usePromptStore] 开发环境：使用 Mock 移动')
        await new Promise(resolve => setTimeout(resolve, 500))
        
        set((state) => ({
          prompts: state.prompts.map((p) =>
            promptIds.includes(p.id)
              ? { ...p, categoryId, updatedAt: new Date().toISOString() }
              : p
          ),
          isLoading: false
        }))
        
        return true
      }
      
      const response = await window.pywebview.api.prompt_batch_move(promptIds, categoryId)
      
      if (!response.success) {
        console.error('[usePromptStore] 移动失败:', response.error_message)
        set({
          isLoading: false,
          error: response.error_message || '移动失败'
        })
        return false
      }
      
      set((state) => ({
        prompts: state.prompts.map((p) =>
          promptIds.includes(p.id)
            ? { ...p, categoryId, updatedAt: new Date().toISOString() }
            : p
        ),
        isLoading: false
      }))
      
      console.log('[usePromptStore] 移动成功')
      return true
      
    } catch (error) {
      console.error('[usePromptStore] 移动异常:', error)
      set({
        isLoading: false,
        error: `移动异常: ${error}`
      })
      return false
    }
  },

  /**
   * 上传图片
   */
  uploadImage: async (fileData, filename) => {
    console.log('[usePromptStore] 上传图片:', filename)
    
    try {
      if (isDevelopment()) {
        console.log('[usePromptStore] 开发环境：使用 Mock 上传')
        await new Promise(resolve => setTimeout(resolve, 500))
        return `mock://images/${filename || Date.now()}.jpg`
      }
      
      const fileDataArray = Array.from(fileData, c => c.charCodeAt(0))
      
      const response = await window.pywebview.api.prompt_upload_image(fileDataArray, filename)
      
      if (!response.success || !response.image_path) {
        console.error('[usePromptStore] 上传图片失败:', response.error_message)
        set({ error: response.error_message || '上传图片失败' })
        return null
      }
      
      const imagePath = resolveImageUrl(response.image_path)
      console.log('[usePromptStore] 图片上传成功:', imagePath)
      return imagePath
      
    } catch (error) {
      console.error('[usePromptStore] 上传图片异常:', error)
      set({ error: `上传图片异常: ${error}` })
      return null
    }
  },

  /**
   * 创建分类
   */
  createCategory: async (data) => {
    console.log('[usePromptStore] 创建分类:', data.name)
    
    try {
      if (!data.name || data.name.trim() === '') {
        set({ error: '分类名称不能为空' })
        return null
      }
      
      set({ isLoading: true, error: null })
      
      if (isDevelopment()) {
        console.log('[usePromptStore] 开发环境：使用 Mock 创建分类')
        await new Promise(resolve => setTimeout(resolve, 500))
        
        const newCategory: PromptCategory = {
          id: `mock-${Date.now()}`,
          name: data.name.trim(),
          icon: (data.icon || 'folder') as CategoryIconName,
          parentId: data.parentId || null,
          sortOrder: 0,
          isSystem: false
        }
        
        set((state) => ({
          categories: [...state.categories, newCategory],
          isLoading: false
        }))
        
        return newCategory
      }
      
      const response = await window.pywebview.api.category_create(
        data.name.trim(),
        data.icon || 'folder',
        data.parentId || null
      )
      
      if (!response.success || !response.category) {
        console.error('[usePromptStore] 创建分类失败:', response.error_message)
        set({
          isLoading: false,
          error: response.error_message || '创建分类失败'
        })
        return null
      }
      
      const newCategory = transformCategory(response.category as CategoryResponse)
      
      set((state) => ({
        categories: [...state.categories, newCategory],
        isLoading: false
      }))
      
      console.log('[usePromptStore] 分类创建成功:', newCategory.id)
      return newCategory
      
    } catch (error) {
      console.error('[usePromptStore] 创建分类异常:', error)
      set({
        isLoading: false,
        error: `创建分类异常: ${error}`
      })
      return null
    }
  },

  /**
   * 更新分类
   */
  updateCategory: async (id, updates) => {
    console.log('[usePromptStore] 更新分类:', id)
    
    try {
      set({ isLoading: true, error: null })
      
      if (isDevelopment()) {
        console.log('[usePromptStore] 开发环境：使用 Mock 更新分类')
        await new Promise(resolve => setTimeout(resolve, 500))
        
        set((state) => ({
          categories: state.categories.map((c) =>
            c.id === id ? { 
              ...c, 
              ...(updates.name && { name: updates.name }),
              ...(updates.icon && { icon: updates.icon as CategoryIconName }),
              ...(updates.parentId !== undefined && { parentId: updates.parentId })
            } : c
          ),
          isLoading: false
        }))
        
        return true
      }
      
      const response = await window.pywebview.api.category_update(
        id,
        updates.name,
        updates.icon,
        undefined
      )
      
      if (!response.success) {
        console.error('[usePromptStore] 更新分类失败:', response.error_message)
        set({
          isLoading: false,
          error: response.error_message || '更新分类失败'
        })
        return false
      }
      
      await get().loadCategories()
      set({ isLoading: false })
      
      console.log('[usePromptStore] 分类更新成功')
      return true
      
    } catch (error) {
      console.error('[usePromptStore] 更新分类异常:', error)
      set({
        isLoading: false,
        error: `更新分类异常: ${error}`
      })
      return false
    }
  },

  /**
   * 删除分类
   */
  deleteCategory: async (id) => {
    console.log('[usePromptStore] 删除分类:', id)
    
    if (id === 'all' || id === 'favorites') {
      set({ error: '系统分类不可删除' })
      return false
    }
    
    try {
      set({ isLoading: true, error: null })
      
      if (isDevelopment()) {
        console.log('[usePromptStore] 开发环境：使用 Mock 删除分类')
        await new Promise(resolve => setTimeout(resolve, 500))
        
        set((state) => ({
          categories: state.categories.filter((c) => c.id !== id),
          selectedCategoryId: state.selectedCategoryId === id ? 'all' : state.selectedCategoryId,
          isLoading: false
        }))
        
        return true
      }
      
      const response = await window.pywebview.api.category_delete(id)
      
      if (!response.success) {
        console.error('[usePromptStore] 删除分类失败:', response.error_message)
        set({
          isLoading: false,
          error: response.error_message || '删除分类失败'
        })
        return false
      }
      
      await get().loadCategories()
      await get().loadPrompts()
      
      set((state) => ({
        selectedCategoryId: state.selectedCategoryId === id ? 'all' : state.selectedCategoryId,
        isLoading: false
      }))
      
      console.log('[usePromptStore] 分类删除成功')
      return true
      
    } catch (error) {
      console.error('[usePromptStore] 删除分类异常:', error)
      set({
        isLoading: false,
        error: `删除分类异常: ${error}`
      })
      return false
    }
  },

  /**
   * 导出提示词
   */
  exportPrompts: async (promptIds) => {
    console.log('[usePromptStore] 导出提示词:', promptIds?.length || '全部')
    
    try {
      set({ isLoading: true, error: null })
      
      if (isDevelopment()) {
        console.log('[usePromptStore] 开发环境：使用 Mock 导出')
        await new Promise(resolve => setTimeout(resolve, 500))
        
        const prompts = promptIds
          ? get().prompts.filter(p => promptIds.includes(p.id))
          : get().prompts
        
        const data = {
          version: '1.0',
          exported_at: new Date().toISOString(),
          prompts: prompts.map(p => ({
            id: p.id,
            name: p.name,
            positive_prompt: p.positivePrompt,
            negative_prompt: p.negativePrompt,
            preview_image: p.previewImage,
            remark: p.remark,
            category_id: p.categoryId,
            tags: p.tags
          }))
        }
        
        set({ isLoading: false })
        return { success: true, data }
      }
      
      const response = await window.pywebview.api.prompt_export(promptIds || null)
      
      if (!response.success) {
        console.error('[usePromptStore] 导出失败:', response.error_message)
        set({
          isLoading: false,
          error: response.error_message || '导出失败'
        })
        return { success: false, error: response.error_message || '导出失败' }
      }
      
      set({ isLoading: false })
      console.log('[usePromptStore] 导出成功')
      return { success: true, data: response.data }
      
    } catch (error) {
      console.error('[usePromptStore] 导出异常:', error)
      set({
        isLoading: false,
        error: `导出异常: ${error}`
      })
      return { success: false, error: `导出异常: ${error}` }
    }
  },

  /**
   * 导入提示词
   */
  importPrompts: async (data) => {
    console.log('[usePromptStore] 导入提示词')
    
    try {
      set({ isLoading: true, error: null })
      
      if (isDevelopment()) {
        console.log('[usePromptStore] 开发环境：使用 Mock 导入')
        await new Promise(resolve => setTimeout(resolve, 500))
        
        const importData = data as { prompts?: unknown[], categories?: unknown[] }
        const count = importData.prompts?.length || 0
        const catCount = importData.categories?.length || 0
        
        set({ isLoading: false })
        return { 
          success: true, 
          importedCount: count, 
          importedCategories: catCount,
          message: `成功导入 ${count} 条提示词${catCount > 0 ? `，${catCount} 个分类` : ''}`
        }
      }
      
      const response = await window.pywebview.api.prompt_import(data, true)
      
      if (!response.success) {
        console.error('[usePromptStore] 导入失败:', response.error_message)
        set({
          isLoading: false,
          error: response.error_message || '导入失败'
        })
        return { success: false, error: response.error_message || '导入失败' }
      }
      
      await get().loadPrompts()
      await get().loadCategories()
      get().refreshFilterTags()
      
      set({ isLoading: false })
      
      console.log('[usePromptStore] 导入成功:', response.imported_count, '条提示词,', response.imported_categories, '个分类')
      return { 
        success: true, 
        importedCount: response.imported_count, 
        importedCategories: response.imported_categories || 0,
        message: response.message 
      }
      
    } catch (error) {
      console.error('[usePromptStore] 导入异常:', error)
      set({
        isLoading: false,
        error: `导入异常: ${error}`
      })
      return { success: false, error: `导入异常: ${error}` }
    }
  },

  /**
   * 刷新筛选标签（从提示词中动态生成）
   */
  refreshFilterTags: () => {
    const { prompts } = get()
    const tagSet = new Set<string>()
    
    prompts.forEach(p => {
      p.tags.forEach(tag => tagSet.add(tag))
    })
    
    const filterTags: FilterTag[] = [
      { id: 'all', name: '全部' },
      ...Array.from(tagSet).map(tag => ({
        id: tag.toLowerCase(),
        name: tag
      }))
    ]
    
    set({ filterTags })
    console.log('[usePromptStore] 筛选标签刷新完成，共', filterTags.length, '个')
  },

  /**
   * 清除错误信息
   */
  clearError: () => {
    set({ error: null })
  },

  /**
   * 获取筛选后的提示词列表
   */
  getFilteredPrompts: () => {
    const state = get()
    let filtered = state.prompts

    if (state.searchQuery) {
      const query = state.searchQuery.toLowerCase()
      filtered = filtered.filter((p) =>
        p.name.toLowerCase().includes(query) ||
        p.positivePrompt.toLowerCase().includes(query) ||
        p.negativePrompt.toLowerCase().includes(query) ||
        p.remark.toLowerCase().includes(query) ||
        p.tags.some((tag) => tag.toLowerCase().includes(query))
      )
    }

    if (state.selectedCategoryId === 'favorites') {
      filtered = filtered.filter((p) => p.isFavorite)
    } else if (state.selectedCategoryId !== 'all') {
      const categoryIds = getChildCategoryIds(state.categories, state.selectedCategoryId)
      filtered = filtered.filter((p) => categoryIds.includes(p.categoryId))
    }

    if (state.activeFilterTag !== 'all') {
      filtered = filtered.filter((p) =>
        p.tags.some((tag) => tag.toLowerCase() === state.activeFilterTag.toLowerCase())
      )
    }

    return filtered
  },

  /**
   * 获取提示词数量
   */
  getPromptCount: () => get().prompts.length
}))
