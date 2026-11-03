/**
 * 资产库状态管理
 */

import { create } from 'zustand'
import i18n from '@/i18n'
import { mockAssets, mockAssetCategories } from '@/mocks/asset'
import type { Asset, AssetCategory, GallerySettings } from '@/mocks/asset'
import type { GalleryMovedAssetPath } from '@/types/bridge'

export type SortBy = 'name' | 'createdAt' | 'size' | 'rating'

export type SortDir = 'asc' | 'desc'

/** 按创建时间倒推的预设区间，'all' 表示不限 */
export type AssetDateFilter = 'all' | 'today' | 'week' | 'month' | 'quarter'

const DATE_FILTER_DAYS: Record<Exclude<AssetDateFilter, 'all'>, number> = {
  today: 1,
  week: 7,
  month: 30,
  quarter: 90
}

/** 区间按自然日起算：从今天 00:00 往回推 N-1 天的零点，避免"今天"随当前时刻漂移 */
const dateFilterThreshold = (filter: Exclude<AssetDateFilter, 'all'>): number => {
  const startOfToday = new Date()
  startOfToday.setHours(0, 0, 0, 0)
  return startOfToday.getTime() - (DATE_FILTER_DAYS[filter] - 1) * 86400000
}

/** 切换排序字段时的自然方向：名称正序，其余（时间/大小/星级）从大到小 */
const DEFAULT_SORT_DIR: Record<SortBy, SortDir> = {
  name: 'asc',
  createdAt: 'desc',
  size: 'desc',
  rating: 'desc'
}

export type AssetViewMode = 'masonry' | 'grid'

/** 分类是磁盘上的真实文件夹，失败原因（同名冲突等）由后端给出，直接透给用户 */
export interface CategoryOpResult {
  success: boolean
  error?: string
}

export type AssetGalleryItem =
  | { kind: 'folder'; category: AssetCategory; assetCount: number }
  | { kind: 'asset'; asset: Asset }

export interface ScanProgress {
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
    prompt?: string
    negativePrompt?: string
    nsfwScore?: number
    nsfwLabel?: string
    tags?: string[]
  }
}

interface AssetStore {
  assets: Asset[]
  categories: AssetCategory[]
  settings: GallerySettings | null
  selectedCategoryId: string
  selectedAssetIds: string[]
  searchQuery: string
  /** 空数组表示不限类型 */
  typeFilter: Asset['type'][]
  onlyWithWorkflow: boolean
  /** 空数组表示不限模型；取值直接用资产里的 model 原串，展示名由界面裁 */
  modelFilter: string[]
  dateFilter: AssetDateFilter
  ratingFilter: string
  isBatchMode: boolean
  isLoading: boolean
  isScanning: boolean
  error: string | null
  sortBy: SortBy
  sortDir: SortDir
  scanProgress: ScanProgress | null
  isStoppingScan: boolean
  _pollingInterval: ReturnType<typeof setInterval> | null
  thumbnailSize: number
  showFoldersInList: boolean
  viewMode: AssetViewMode

  loadData: () => Promise<void>
  refreshData: () => Promise<void>
  refreshCategories: () => Promise<void>
  scanLibrary: () => Promise<{ success: boolean; added?: number; updated?: number; removed?: number }>
  incrementalScanLibrary: () => Promise<{ success: boolean; added?: number; updated?: number; removed?: number }>
  startBackgroundScan: (libraryPath?: string) => Promise<{ success: boolean; message?: string }>
  getScanStatus: () => Promise<{ success: boolean; scanning?: boolean; stopping?: boolean; progress?: ScanProgress | null }>
  stopScan: () => Promise<boolean>
  pollScanProgress: () => void
  setSelectedCategoryId: (id: string) => void
  setSearchQuery: (query: string) => void
  toggleTypeFilter: (type: Asset['type']) => void
  setOnlyWithWorkflow: (value: boolean) => void
  toggleModelFilter: (model: string) => void
  setDateFilter: (value: AssetDateFilter) => void
  setSortDir: (dir: SortDir) => void
  clearAttributeFilters: () => void
  hasAttributeFilter: () => boolean
  getModelOptions: () => { model: string; count: number }[]
  setRatingFilter: (filter: string) => void
  toggleBatchMode: () => void
  setBatchMode: (mode: boolean) => void
  toggleAssetSelection: (id: string) => void
  setSelectedAssetIds: (ids: string[]) => void
  selectAllAssets: () => void
  clearSelection: () => void
  toggleFavorite: (id: string) => Promise<boolean>
  batchFavorite: (ids: string[], favorite: boolean) => Promise<boolean>
  deleteAssets: (ids: string[]) => Promise<boolean>
  openLocation: (id: string) => Promise<boolean>
  exportZip: (ids: string[]) => Promise<{ success: boolean; zipPath?: string }>
  importAssets: (paths: string[]) => Promise<{ success: boolean; importedCount?: number }>
  moveToCategory: (ids: string[], categoryId: string | null) => Promise<boolean>
  getSettings: () => Promise<GallerySettings | null>
  saveSettings: (libraryPath: string) => Promise<boolean>
  getWorkflow: (id: string) => Promise<{ success: boolean; workflow?: object }>
  exportWorkflow: (id: string) => Promise<{ success: boolean; workflowPath?: string; workflowName?: string; error_message?: string }>
  exportWorkflowToPath: (id: string, savePath: string) => Promise<{ success: boolean; workflowPath?: string; error_message?: string }>
  exportToPromptLibrary: (id: string, force?: boolean) => Promise<{ success: boolean; error_message?: string; prompt?: unknown }>
  setSortBy: (sortBy: SortBy) => void
  setShowFoldersInList: (show: boolean) => void
  setViewMode: (mode: AssetViewMode) => void
  getFilteredAssets: () => Asset[]
  getGalleryItems: () => AssetGalleryItem[]
  getNsfwStatus: () => Promise<{ success: boolean; modelAvailable?: boolean; nsfwAutoClassify?: boolean; nsfwThreshold?: number; nsfwAutoBlur?: boolean; isScanning?: boolean; isPaused?: boolean }>
  setNsfwEnabled: (enabled: boolean) => Promise<boolean>
  setNsfwThreshold: (threshold: number) => Promise<boolean>
  setNsfwAutoBlur: (enabled: boolean) => Promise<boolean>
  classifyAllImages: () => Promise<{ success: boolean; total?: number; message?: string }>
  pauseNsfwScan: () => Promise<boolean>
  resumeNsfwScan: () => Promise<boolean>
  cancelNsfwScan: () => Promise<boolean>
  updatePreviewBlurred: (assetId: string, blurred: boolean) => Promise<boolean>
  updateAssetInfo: (assetId: string, data: { filename?: string; description?: string; tags?: string[]; rating?: number }) => Promise<{ success: boolean; asset?: Asset; error_message?: string }>
  setThumbnailSize: (size: number) => void
  createCategory: (name: string, parentId?: string) => Promise<CategoryOpResult>
  updateCategory: (categoryId: string, name: string) => Promise<CategoryOpResult>
  moveCategory: (categoryId: string, parentId: string | null) => Promise<CategoryOpResult>
  deleteCategory: (categoryId: string, moveContentsToParent?: boolean) => Promise<CategoryOpResult>
  pushImageToComfyUI: (assetId: string) => Promise<{ success: boolean; filename?: string; error_message?: string }>
}

const isDevelopment = (): boolean => {
  return !window.pywebview || !window.pywebview.api
}

const getChildCategoryIds = (categories: AssetCategory[], targetId: string): string[] => {
  const result: string[] = [targetId]

  const findChildren = (cats: AssetCategory[]) => {
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

const flattenCategories = (categories: AssetCategory[]): AssetCategory[] => {
  const result: AssetCategory[] = []
  const seen = new Set<string>()

  const visit = (categoryList: AssetCategory[]) => {
    for (const category of categoryList) {
      if (!seen.has(category.id)) {
        result.push(category)
        seen.add(category.id)
      }
      if (category.children?.length) {
        visit(category.children)
      }
    }
  }

  visit(categories)
  return result
}

const getDirectChildCategories = (categories: AssetCategory[], selectedCategoryId: string): AssetCategory[] => {
  if (selectedCategoryId === 'favorites' || selectedCategoryId === 'uncategorized') {
    return []
  }

  const parentId = selectedCategoryId === 'all' ? null : selectedCategoryId
  return flattenCategories(categories)
    .filter((category) => {
      if (category.isSystem) return false
      return (category.parentId ?? null) === parentId
    })
    .sort((a, b) => {
      if (a.sortOrder !== b.sortOrder) return a.sortOrder - b.sortOrder
      return a.name.localeCompare(b.name)
    })
}

const getCategoryAssetCount = (assets: Asset[], categories: AssetCategory[], categoryId: string): number => {
  const categoryIds = getChildCategoryIds(categories, categoryId)
  return assets.filter((asset) => asset.categoryId && categoryIds.includes(asset.categoryId)).length
}

/** 分类改名/移动/删除会搬动磁盘目录，就地同步受影响资产，省掉一次整库重载 */
const applyMovedAssetPaths = (
  assets: Asset[],
  moved?: GalleryMovedAssetPath[]
): Asset[] => {
  if (!moved?.length) return assets
  const byId = new Map(moved.map((entry) => [entry.id, entry]))
  return assets.map((asset) => {
    const entry = byId.get(asset.id)
    if (!entry) return asset
    return {
      ...asset,
      filePath: entry.filePath,
      categoryId: entry.categoryId === undefined ? asset.categoryId : entry.categoryId
    }
  })
}

export const useAssetStore = create<AssetStore>((set, get) => ({
  assets: [],
  categories: [],
  settings: null,
  selectedCategoryId: 'all',
  selectedAssetIds: [],
  searchQuery: '',
  typeFilter: [],
  onlyWithWorkflow: false,
  modelFilter: [],
  dateFilter: 'all',
  ratingFilter: 'all',
  isBatchMode: false,
  isLoading: false,
  isScanning: false,
  error: null,
  sortBy: 'createdAt',
  sortDir: 'desc',
  scanProgress: null,
  isStoppingScan: false,
  _pollingInterval: null as NodeJS.Timeout | null,
  thumbnailSize: Number(localStorage.getItem('thumbnailSize')) || 250,
  showFoldersInList: localStorage.getItem('asset-show-folders-in-list') === 'true',
  viewMode: localStorage.getItem('asset-view-mode') === 'grid' ? 'grid' : 'masonry',

  loadData: async () => {
    console.log('[useAssetStore] 加载数据开始')
    console.log('[useAssetStore] isDevelopment:', isDevelopment())
    console.log('[useAssetStore] window.pywebview:', !!window.pywebview)
    console.log('[useAssetStore] window.pywebview.api:', !!window.pywebview?.api)
    
    set({ isLoading: true, error: null })

    try {
      if (isDevelopment()) {
        console.log('[useAssetStore] 开发环境：使用 Mock 数据')
        await new Promise((resolve) => setTimeout(resolve, 300))
        set({
          assets: mockAssets,
          categories: mockAssetCategories,
          settings: { libraryPath: '', lastScanTime: null, nsfwAutoClassify: false, nsfwThreshold: 0.6, nsfwAutoBlur: true },
          isLoading: false
        })
        return
      }

      console.log('[useAssetStore] 生产环境：调用后端 API gallery_get_assets')
      const result = await window.pywebview.api.gallery_get_assets()
      console.log('[useAssetStore] API 返回结果:', {
        success: result.success,
        assetsCount: result.assets?.length,
        categoriesCount: result.categories?.length,
        settings: result.settings,
        error: result.error_message
      })
      
      if (result.success) {
        // 计算 thumbnail 和 url 属性
        // thumbnail 使用 HTTP 服务器提供的缩略图端点
        const assetsWithThumbnail = (result.assets || []).map(asset => {
          const safeString = (value: unknown): string | undefined => {
            if (value === null || value === undefined) return undefined
            if (typeof value === 'string') return value
            if (typeof value === 'object') return JSON.stringify(value, null, 2)
            return String(value)
          }
          
          return {
            ...asset,
            prompt: safeString(asset.prompt),
            negativePrompt: safeString(asset.negativePrompt),
            thumbnail: `/gallery/thumbnail/${asset.id}`,
            url: `/gallery/asset/${asset.id}`
          }
        })
        
        console.log('[useAssetStore] 计算缩略图 URL，示例:', assetsWithThumbnail[0]?.thumbnail)
        
        set({
          assets: assetsWithThumbnail,
          categories: result.categories || [],
          settings: {
            libraryPath: result.settings?.libraryPath || '',
            lastScanTime: result.settings?.lastScanTime || null,
            nsfwAutoClassify: result.settings?.nsfwAutoClassify ?? false,
            nsfwThreshold: result.settings?.nsfwThreshold ?? 0.6,
            nsfwAutoBlur: result.settings?.nsfwAutoBlur ?? true
          },
          isLoading: false
        })
        console.log('[useAssetStore] 数据加载完成，资产数量:', result.assets?.length, '分类数量:', result.categories?.length)
      } else {
        console.error('[useAssetStore] API 返回失败:', result.error_message)
        set({
          isLoading: false,
          error: result.error_message || i18n.t('asset.error.loadFailed')
        })
      }
    } catch (error) {
      console.error('[useAssetStore] 加载数据异常:', error)
      set({
        isLoading: false,
        error: i18n.t('asset.error.loadException', { error: String(error) })
      })
    }
  },

  refreshData: async () => {
    console.log('[useAssetStore] 刷新数据')
    return get().loadData()
  },

  refreshCategories: async () => {
    console.log('[useAssetStore] 刷新分类数据')
    try {
      if (isDevelopment()) {
        console.log('[useAssetStore] 开发环境：跳过分类刷新')
        return
      }

      const result = await window.pywebview.api.gallery_get_categories()
      console.log('[useAssetStore] 获取分类结果:', result)
      
      if (result.success && result.categories) {
        set({ categories: result.categories })
        console.log('[useAssetStore] 分类数据已更新，数量:', result.categories.length)
      }
    } catch (error) {
      console.error('[useAssetStore] 刷新分类异常:', error)
    }
  },

  scanLibrary: async () => {
    console.log('[useAssetStore] 扫描资产库')
    set({ isScanning: true, error: null })

    try {
      if (isDevelopment()) {
        await new Promise((resolve) => setTimeout(resolve, 500))
        set({ isScanning: false })
        return { success: true, added: 0, updated: 0, removed: 0 }
      }

      const result = await window.pywebview.api.gallery_scan()
      set({ isScanning: false })

      if (result.success) {
        await get().loadData()
        return {
          success: true,
          added: result.added,
          updated: result.updated,
          removed: result.removed
        }
      }

      set({ error: result.error_message || i18n.t('asset.error.scanFailed') })
      return { success: false }
    } catch (error) {
      console.error('[useAssetStore] 扫描异常:', error)
      set({ isScanning: false, error: i18n.t('asset.error.scanException', { error: String(error) }) })
      return { success: false }
    }
  },

  incrementalScanLibrary: async () => {
    console.log('[useAssetStore] 增量扫描资产库')
    set({ isScanning: true, error: null })

    try {
      if (isDevelopment()) {
        await new Promise((resolve) => setTimeout(resolve, 300))
        set({ isScanning: false })
        return { success: true, added: 0, updated: 0, removed: 0 }
      }

      const result = await window.pywebview.api.gallery_incremental_scan()
      set({ isScanning: false })

      if (result.success) {
        await get().loadData()
        return {
          success: true,
          added: result.added,
          updated: result.updated,
          removed: result.removed
        }
      }

      set({ error: result.error_message || i18n.t('asset.error.scanFailed') })
      return { success: false }
    } catch (error) {
      console.error('[useAssetStore] 增量扫描异常:', error)
      set({ isScanning: false, error: i18n.t('asset.error.scanException', { error: String(error) }) })
      return { success: false }
    }
  },

  startBackgroundScan: async (libraryPath?: string) => {
    console.log('[useAssetStore] 启动后台扫描')
    set({ isScanning: true, scanProgress: null, error: null })

    try {
      if (isDevelopment()) {
        await new Promise((resolve) => setTimeout(resolve, 300))
        set({
          isScanning: true,
          scanProgress: { stage: 'scanning', current: 0, total: 10, message: i18n.t('asset.error.simulatingScan') }
        })
        return { success: true, message: '扫描任务已启动' }
      }

      const result = await window.pywebview.api.gallery_start_background_scan(libraryPath)
      if (result.success) {
        get().pollScanProgress()
      }
      return { success: result.success, message: result.message }
    } catch (error) {
      console.error('[useAssetStore] 启动后台扫描异常:', error)
      set({ isScanning: false, error: i18n.t('asset.error.startScanException', { error: String(error) }) })
      return { success: false, message: i18n.t('asset.error.startScanException', { error: String(error) }) }
    }
  },

  getScanStatus: async () => {
    try {
      if (isDevelopment()) {
        const progress = get().scanProgress
        return { success: true, scanning: !!progress, stopping: false, progress: progress ?? null }
      }

      const result = await window.pywebview.api.gallery_get_scan_status()
      return {
        success: result.success,
        scanning: result.scanning,
        stopping: result.stopping,
        progress: result.progress ?? null
      }
    } catch (error) {
      console.error('[useAssetStore] 获取扫描状态异常:', error)
      return { success: false, progress: null, error: i18n.t('asset.error.getScanStatusException') }
    }
  },

  stopScan: async () => {
    console.log('[useAssetStore] 停止扫描')
    set({ isStoppingScan: true })

    try {
      if (isDevelopment()) {
        set({ isScanning: false, scanProgress: null, isStoppingScan: false })
        return true
      }

      const result = await window.pywebview.api.gallery_stop_scan()
      if (result.success) {
        const checkStopped = async () => {
          const status = await get().getScanStatus()
          if (!status.scanning) {
            set({ isScanning: false, scanProgress: null, isStoppingScan: false })
            return true
          }
          return false
        }

        const pollInterval = setInterval(async () => {
          const stopped = await checkStopped()
          if (stopped) {
            clearInterval(pollInterval)
          }
        }, 500)
      }
      return result.success
    } catch (error) {
      console.error('[useAssetStore] 停止扫描异常:', error)
      set({ isStoppingScan: false })
      return false
    }
  },

  pollScanProgress: () => {
    const state = get()
    if (state._pollingInterval) {
      clearInterval(state._pollingInterval)
    }

    const poll = async () => {
      const status = await get().getScanStatus()
      
      if (status.progress) {
        set({ scanProgress: status.progress })
        
        if (status.progress.assetData) {
          const rawAsset = status.progress.assetData
          
          const safeString = (value: unknown): string | undefined => {
            if (value === null || value === undefined) return undefined
            if (typeof value === 'string') return value
            if (typeof value === 'object') return JSON.stringify(value, null, 2)
            return String(value)
          }
          
          const newAsset: Asset = {
            ...rawAsset,
            prompt: safeString(rawAsset.prompt),
            negativePrompt: safeString(rawAsset.negativePrompt),
            thumbnail: `/gallery/thumbnail/${rawAsset.id}`,
            url: `/gallery/asset/${rawAsset.id}`
          }
          set((state) => {
            const existingIndex = state.assets.findIndex((a: Asset) => a.id === newAsset.id)
            if (existingIndex >= 0) {
              const newAssets = [...state.assets]
              newAssets[existingIndex] = newAsset
              return { assets: newAssets }
            }
            return { assets: [...state.assets, newAsset] }
          })
        }
      }

      if (!status.scanning || status.progress?.stage === 'done') {
        const state = get()
        if (state._pollingInterval) {
          clearInterval(state._pollingInterval)
          set({ _pollingInterval: null })
        }
        set({ isScanning: false, isStoppingScan: false })
        
        if (status.progress?.stage === 'done') {
          console.log('[useAssetStore] 扫描完成，刷新数据')
          await get().loadData()
          await get().refreshCategories()
        }
      }
    }

    const interval = setInterval(poll, 500)
    set({ _pollingInterval: interval })
    poll()
  },

  setSelectedCategoryId: (id) => set({ selectedCategoryId: id }),

  setSearchQuery: (query) => set({ searchQuery: query }),

  toggleTypeFilter: (type) => set((state) => ({
    typeFilter: state.typeFilter.includes(type)
      ? state.typeFilter.filter((t) => t !== type)
      : [...state.typeFilter, type]
  })),

  setOnlyWithWorkflow: (value) => set({ onlyWithWorkflow: value }),

  toggleModelFilter: (model) => set((state) => ({
    modelFilter: state.modelFilter.includes(model)
      ? state.modelFilter.filter((m) => m !== model)
      : [...state.modelFilter, model]
  })),

  setDateFilter: (value) => set({ dateFilter: value }),

  setSortDir: (dir) => set({ sortDir: dir }),

  toggleBatchMode: () =>
    set((state) => ({
      isBatchMode: !state.isBatchMode,
      selectedAssetIds: state.isBatchMode ? [] : state.selectedAssetIds
    })),

  setBatchMode: (mode) => set({ isBatchMode: mode }),

  toggleAssetSelection: (id) =>
    set((state) => ({
      selectedAssetIds: state.selectedAssetIds.includes(id)
        ? state.selectedAssetIds.filter((i) => i !== id)
        : [...state.selectedAssetIds, id]
    })),

  setSelectedAssetIds: (ids) => set({ selectedAssetIds: ids }),

  selectAllAssets: () =>
    set({
      selectedAssetIds: get()
        .getFilteredAssets()
        .map((a) => a.id)
    }),

  clearSelection: () => set({ selectedAssetIds: [] }),

  toggleFavorite: async (id) => {
    console.log('[useAssetStore] 切换收藏状态:', id)

    try {
      if (isDevelopment()) {
        await new Promise((resolve) => setTimeout(resolve, 200))
        set((state) => ({
          assets: state.assets.map((a) => (a.id === id ? { ...a, isFavorite: !a.isFavorite } : a))
        }))
        return true
      }

      const result = await window.pywebview.api.gallery_toggle_favorite(id)
      if (result.success) {
        set((state) => ({
          assets: state.assets.map((a) =>
            a.id === id ? { ...a, isFavorite: result.is_favorite ?? false } : a
          )
        }))
        return true
      }
      return false
    } catch (error) {
      console.error('[useAssetStore] 切换收藏异常:', error)
      return false
    }
  },

  batchFavorite: async (ids, favorite) => {
    console.log('[useAssetStore] 批量收藏:', ids.length, favorite)

    try {
      if (isDevelopment()) {
        await new Promise((resolve) => setTimeout(resolve, 300))
        set((state) => ({
          assets: state.assets.map((a) =>
            ids.includes(a.id) ? { ...a, isFavorite: favorite } : a
          )
        }))
        return true
      }

      const result = await window.pywebview.api.gallery_batch_favorite(ids, favorite)
      if (result.success) {
        await get().loadData()
        return true
      }
      return false
    } catch (error) {
      console.error('[useAssetStore] 批量收藏异常:', error)
      return false
    }
  },

  deleteAssets: async (ids) => {
    console.log('[useAssetStore] 删除资产:', ids.length, '个')

    try {
      // 不切换 isLoading：列表已是就地移除，切骨架屏会让瀑布流整体卸载、滚动位置丢失。
      if (isDevelopment()) {
        await new Promise((resolve) => setTimeout(resolve, 300))
        set((state) => ({
          assets: state.assets.filter((a) => !ids.includes(a.id)),
          selectedAssetIds: state.selectedAssetIds.filter((id) => !ids.includes(id))
        }))
        return true
      }

      const result = await window.pywebview.api.gallery_batch_delete(ids)

      if (result.success) {
        set((state) => ({
          assets: state.assets.filter((a) => !ids.includes(a.id)),
          selectedAssetIds: state.selectedAssetIds.filter((id) => !ids.includes(id))
        }))
        return true
      }

      set({ error: result.error_message || i18n.t('asset.error.deleteFailed') })
      return false
    } catch (error) {
      console.error('[useAssetStore] 删除资产异常:', error)
      set({ error: i18n.t('asset.error.deleteException', { error: String(error) }) })
      return false
    }
  },

  openLocation: async (id) => {
    console.log('[useAssetStore] 打开文件位置:', id)

    try {
      if (isDevelopment()) {
        console.log('[useAssetStore] 开发环境：模拟打开文件位置')
        return true
      }

      const result = await window.pywebview.api.gallery_open_location(id)
      return result.success
    } catch (error) {
      console.error('[useAssetStore] 打开文件位置异常:', error)
      return false
    }
  },

  exportZip: async (ids) => {
    console.log('[useAssetStore] 导出 ZIP:', ids.length, '个')

    try {
      if (isDevelopment()) {
        await new Promise((resolve) => setTimeout(resolve, 500))
        return { success: true, zipPath: 'mock_export.zip' }
      }

      const result = await window.pywebview.api.gallery_export_zip(ids)
      return {
        success: result.success,
        zipPath: result.zip_path
      }
    } catch (error) {
      console.error('[useAssetStore] 导出 ZIP 异常:', error)
      return { success: false }
    }
  },

  importAssets: async (paths) => {
    console.log('[useAssetStore] 导入资产:', paths.length, '个路径')

    try {
      if (isDevelopment()) {
        await new Promise((resolve) => setTimeout(resolve, 500))
        return { success: true, importedCount: paths.length }
      }

      const result = await window.pywebview.api.gallery_import(paths)
      if (result.success) {
        await get().loadData()
        return {
          success: true,
          importedCount: result.imported_count
        }
      }
      return { success: false }
    } catch (error) {
      console.error('[useAssetStore] 导入资产异常:', error)
      return { success: false }
    }
  },

  moveToCategory: async (ids, categoryId) => {
    console.log('[useAssetStore] 移动到分类:', ids.length, categoryId)

    try {
      if (isDevelopment()) {
        await new Promise((resolve) => setTimeout(resolve, 300))
        set((state) => ({
          assets: state.assets.map((a) =>
            ids.includes(a.id) ? { ...a, categoryId } : a
          )
        }))
        return true
      }

      const result = await window.pywebview.api.gallery_move_to_category(ids, categoryId ?? undefined)
      if (result.success) {
        await get().loadData()
        return true
      }
      return false
    } catch (error) {
      console.error('[useAssetStore] 移动分类异常:', error)
      return false
    }
  },

  getSettings: async () => {
    try {
      if (isDevelopment()) {
        const defaultSettings = { libraryPath: '', lastScanTime: null, nsfwAutoClassify: false, nsfwThreshold: 0.6, nsfwAutoBlur: true }
        return defaultSettings
      }

      const result = await window.pywebview.api.gallery_get_settings()
      if (result.success && result.settings) {
        set({ settings: result.settings })
        return result.settings
      }

      const defaultSettings = { libraryPath: '', lastScanTime: null, nsfwAutoClassify: false, nsfwThreshold: 0.6, nsfwAutoBlur: true }
      set({ settings: defaultSettings })
      return defaultSettings
    } catch (error) {
      console.error('[useAssetStore] 获取设置异常:', error)
      return null
    }
  },

  saveSettings: async (libraryPath) => {
    console.log('[useAssetStore] 保存设置:', libraryPath)

    try {
      if (isDevelopment()) {
        set({ settings: { libraryPath, lastScanTime: null, nsfwAutoClassify: false, nsfwThreshold: 0.6, nsfwAutoBlur: true } })
        return true
      }

      const result = await window.pywebview.api.gallery_save_settings(libraryPath)
      if (result.success) {
        const currentSettings = get().settings
        set({ settings: { 
          libraryPath, 
          lastScanTime: currentSettings?.lastScanTime || null,
          nsfwAutoClassify: currentSettings?.nsfwAutoClassify || false,
          nsfwThreshold: currentSettings?.nsfwThreshold || 0.6,
          nsfwAutoBlur: currentSettings?.nsfwAutoBlur ?? true
        }})
        return true
      }
      return false
    } catch (error) {
      console.error('[useAssetStore] 保存设置异常:', error)
      return false
    }
  },

  getNsfwStatus: async () => {
    try {
      if (isDevelopment()) {
        return { success: true, modelAvailable: true, nsfwAutoClassify: false, nsfwThreshold: 0.6, nsfwAutoBlur: true, isScanning: false, isPaused: false }
      }

      const result = await window.pywebview.api.gallery_get_nsfw_status()
      return {
        success: result.success,
        modelAvailable: result.model_available,
        nsfwAutoClassify: result.nsfw_auto_classify,
        nsfwThreshold: result.nsfw_threshold,
        nsfwAutoBlur: result.nsfw_auto_blur,
        isScanning: result.is_scanning,
        isPaused: result.is_paused
      }
    } catch (error) {
      console.error('[useAssetStore] 获取 NSFW 状态异常:', error)
      return { success: false }
    }
  },

  setNsfwEnabled: async (enabled) => {
    console.log('[useAssetStore] 设置 NSFW 开关:', enabled)
    try {
      if (isDevelopment()) {
        set((state) => ({
          settings: state.settings ? { ...state.settings, nsfwAutoClassify: enabled } : null
        }))
        return true
      }

      const result = await window.pywebview.api.gallery_set_nsfw_enabled(enabled)
      if (result.success) {
        set((state) => ({
          settings: state.settings ? { ...state.settings, nsfwAutoClassify: enabled } : null
        }))
        return true
      }
      return false
    } catch (error) {
      console.error('[useAssetStore] 设置 NSFW 开关异常:', error)
      return false
    }
  },

  setNsfwThreshold: async (threshold) => {
    console.log('[useAssetStore] 设置 NSFW 阈值:', threshold)
    try {
      if (isDevelopment()) {
        set((state) => ({
          settings: state.settings ? { ...state.settings, nsfwThreshold: threshold } : null
        }))
        return true
      }

      const result = await window.pywebview.api.gallery_set_nsfw_threshold(threshold)
      if (result.success) {
        set((state) => ({
          settings: state.settings ? { ...state.settings, nsfwThreshold: threshold } : null
        }))
        return true
      }
      return false
    } catch (error) {
      console.error('[useAssetStore] 设置 NSFW 阈值异常:', error)
      return false
    }
  },

  setNsfwAutoBlur: async (enabled) => {
    console.log('[useAssetStore] 设置 NSFW 自动模糊:', enabled)
    try {
      if (isDevelopment()) {
        set((state) => ({
          settings: state.settings ? { ...state.settings, nsfwAutoBlur: enabled } : null
        }))
        return true
      }

      const result = await window.pywebview.api.gallery_set_nsfw_auto_blur(enabled)
      if (result.success) {
        set((state) => ({
          settings: state.settings ? { ...state.settings, nsfwAutoBlur: enabled } : null
        }))
        return true
      }
      return false
    } catch (error) {
      console.error('[useAssetStore] 设置 NSFW 自动模糊异常:', error)
      return false
    }
  },

  classifyAllImages: async () => {
    console.log('[useAssetStore] 开始全量 NSFW 分级')
    try {
      if (isDevelopment()) {
        return { success: true, total: 0, message: '开发环境模拟' }
      }

      const result = await window.pywebview.api.gallery_classify_all_images()
      return {
        success: result.success,
        total: result.total,
        message: result.message
      }
    } catch (error) {
      console.error('[useAssetStore] 全量分级异常:', error)
      return { success: false }
    }
  },

  pauseNsfwScan: async () => {
    try {
      if (isDevelopment()) {
        return true
      }
      const result = await window.pywebview.api.gallery_pause_nsfw_scan()
      return result.success
    } catch (error) {
      console.error('[useAssetStore] 暂停扫描异常:', error)
      return false
    }
  },

  resumeNsfwScan: async () => {
    try {
      if (isDevelopment()) {
        return true
      }
      const result = await window.pywebview.api.gallery_resume_nsfw_scan()
      return result.success
    } catch (error) {
      console.error('[useAssetStore] 恢复扫描异常:', error)
      return false
    }
  },

  cancelNsfwScan: async () => {
    try {
      if (isDevelopment()) {
        return true
      }
      const result = await window.pywebview.api.gallery_cancel_nsfw_scan()
      return result.success
    } catch (error) {
      console.error('[useAssetStore] 取消扫描异常:', error)
      return false
    }
  },

  updatePreviewBlurred: async (assetId: string, blurred: boolean) => {
    try {
      if (isDevelopment()) {
        set((state) => ({
          assets: state.assets.map((a) =>
            a.id === assetId ? { ...a, previewBlurred: blurred } : a
          )
        }))
        return true
      }

      const result = await window.pywebview.api.gallery_update_preview_blurred(assetId, blurred)
      if (result.success && result.asset) {
        set((state) => ({
          assets: state.assets.map((a) =>
            a.id === assetId
              ? { ...a, previewBlurred: result.asset!.previewBlurred }
              : a
          )
        }))
        return true
      }
      return false
    } catch (error) {
      console.error('[useAssetStore] 更新模糊预览状态异常:', error)
      return false
    }
  },

  getWorkflow: async (id) => {
    try {
      if (isDevelopment()) {
        return { success: false }
      }

      const result = await window.pywebview.api.gallery_get_workflow(id)
      return {
        success: result.success,
        workflow: result.workflow
      }
    } catch (error) {
      console.error('[useAssetStore] 获取工作流异常:', error)
      return { success: false }
    }
  },

  exportWorkflow: async (id) => {
    try {
      if (isDevelopment()) {
        return { success: true, workflowPath: 'mock_workflow.json', workflowName: 'Mock Workflow' }
      }

      const result = await window.pywebview.api.gallery_export_workflow(id)
      return {
        success: result.success,
        workflowPath: result.workflow_path,
        workflowName: result.workflow_name,
        error_message: result.error_message
      }
    } catch (error) {
      console.error('[useAssetStore] 导出工作流异常:', error)
      return { success: false, error_message: String(error) }
    }
  },

  exportWorkflowToPath: async (id, savePath) => {
    try {
      if (isDevelopment()) {
        return { success: true, workflowPath: savePath }
      }

      const result = await window.pywebview.api.gallery_export_workflow_to_path(id, savePath)
      return {
        success: result.success,
        workflowPath: result.workflow_path,
        error_message: result.error_message
      }
    } catch (error) {
      console.error('[useAssetStore] 导出工作流到路径异常:', error)
      return { success: false, error_message: String(error) }
    }
  },

  exportToPromptLibrary: async (id, force = false) => {
    try {
      if (isDevelopment()) {
        return { success: true }
      }

      const result = await window.pywebview.api.gallery_export_to_prompt_library(id, force)
      return result
    } catch (error) {
      console.error('[useAssetStore] 导出到提示词库异常:', error)
      return { success: false, error_message: String(error) }
    }
  },

  setSortBy: (sortBy) => set({ sortBy, sortDir: DEFAULT_SORT_DIR[sortBy] }),

  setShowFoldersInList: (show) => {
    localStorage.setItem('asset-show-folders-in-list', String(show))
    set({
      showFoldersInList: show,
      selectedAssetIds: [],
      isBatchMode: false
    })
  },

  setViewMode: (mode) => {
    localStorage.setItem('asset-view-mode', mode)
    set({ viewMode: mode })
  },

  hasAttributeFilter: () => {
    const state = get()
    return (
      state.typeFilter.length > 0 ||
      state.onlyWithWorkflow ||
      state.modelFilter.length > 0 ||
      state.dateFilter !== 'all' ||
      state.ratingFilter !== 'all'
    )
  },

  clearAttributeFilters: () => set({
    typeFilter: [],
    onlyWithWorkflow: false,
    modelFilter: [],
    dateFilter: 'all',
    ratingFilter: 'all'
  }),

  getModelOptions: () => {
    const counts = new Map<string, number>()
    for (const asset of get().assets) {
      if (!asset.model) continue
      counts.set(asset.model, (counts.get(asset.model) ?? 0) + 1)
    }
    return Array.from(counts, ([model, count]) => ({ model, count }))
      .sort((a, b) => b.count - a.count || a.model.localeCompare(b.model))
  },

  getFilteredAssets: () => {
    const state = get()
    let filtered = state.assets

    if (state.searchQuery) {
      const query = state.searchQuery.toLowerCase()
      filtered = filtered.filter(
        (a) =>
          a.filename.toLowerCase().includes(query) ||
          a.prompt?.toLowerCase().includes(query) ||
          a.model?.toLowerCase().includes(query) ||
          a.description?.toLowerCase().includes(query) ||
          a.tags?.some((tag) => tag.toLowerCase().includes(query))
      )
    }

    if (state.selectedCategoryId === 'favorites') {
      filtered = filtered.filter((a) => a.isFavorite)
    } else if (state.selectedCategoryId === 'uncategorized') {
      filtered = filtered.filter((a) => !a.categoryId)
    } else if (state.selectedCategoryId !== 'all') {
      if (state.showFoldersInList) {
        filtered = filtered.filter((a) => a.categoryId === state.selectedCategoryId)
      } else {
        const categoryIds = getChildCategoryIds(state.categories, state.selectedCategoryId)
        filtered = filtered.filter((a) => a.categoryId && categoryIds.includes(a.categoryId))
      }
    }

    if (state.typeFilter.length > 0) {
      filtered = filtered.filter((a) => state.typeFilter.includes(a.type))
    }

    if (state.onlyWithWorkflow) {
      filtered = filtered.filter((a) => a.hasWorkflow)
    }

    if (state.modelFilter.length > 0) {
      filtered = filtered.filter((a) => a.model && state.modelFilter.includes(a.model))
    }

    if (state.dateFilter !== 'all') {
      const from = dateFilterThreshold(state.dateFilter)
      filtered = filtered.filter((a) => new Date(a.createdAt).getTime() >= from)
    }

    if (state.ratingFilter !== 'all') {
      const target = parseInt(state.ratingFilter)
      // 0 是"未评级"这一档，其余按"至少 N 星"理解：评过 5 星的当然也想在 3 星筛选里看到
      filtered = target === 0
        ? filtered.filter((a) => (a.rating || 0) === 0)
        : filtered.filter((a) => (a.rating || 0) >= target)
    }

    const direction = state.sortDir === 'asc' ? 1 : -1
    filtered = [...filtered].sort((a, b) => {
      switch (state.sortBy) {
        case 'name':
          return direction * a.filename.localeCompare(b.filename)
        case 'size':
          return direction * (a.size - b.size)
        case 'rating':
          return direction * ((a.rating || 0) - (b.rating || 0))
        case 'createdAt':
        default:
          return direction * (new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime())
      }
    })

    return filtered
  },

  getGalleryItems: () => {
    const state = get()
    const assets = state.getFilteredAssets()

    if (!state.showFoldersInList) {
      return assets.map((asset) => ({ kind: 'asset', asset }))
    }

    if (
      state.selectedCategoryId === 'all' ||
      state.selectedCategoryId === 'favorites' ||
      state.selectedCategoryId === 'uncategorized'
    ) {
      return assets.map((asset) => ({ kind: 'asset', asset }))
    }

    const canShowFolders = !state.hasAttributeFilter()

    const query = state.searchQuery.trim().toLowerCase()
    const folders = canShowFolders
      ? getDirectChildCategories(state.categories, state.selectedCategoryId)
          .filter((category) => !query || category.name.toLowerCase().includes(query))
          .map((category) => ({
            kind: 'folder' as const,
            category,
            assetCount: getCategoryAssetCount(state.assets, state.categories, category.id)
          }))
      : []

    return [
      ...folders,
      ...assets.map((asset) => ({ kind: 'asset' as const, asset }))
    ]
  },

  updateAssetInfo: async (assetId, data) => {
    try {
      if (isDevelopment()) {
        const assets = get().assets
        const asset = assets.find(a => a.id === assetId)
        if (asset) {
          const updatedAsset = {
            ...asset,
            ...(data.filename !== undefined && { filename: data.filename }),
            ...(data.description !== undefined && { description: data.description }),
            ...(data.tags !== undefined && { tags: data.tags }),
            ...(data.rating !== undefined && { rating: data.rating })
          }
          const newAssets = assets.map(a => a.id === assetId ? updatedAsset : a)
          set({
            assets: newAssets
          })
          return { success: true, asset: updatedAsset }
        }
        return { success: false, error_message: i18n.t('asset.error.notFound') }
      }

      const result = await window.pywebview.api.gallery_update_asset_info(
        assetId,
        data.filename,
        data.description,
        data.tags,
        data.rating
      )

      if (result.success && result.asset) {
        const assets = get().assets
        const updatedAsset = {
          ...assets.find(a => a.id === assetId)!,
          ...result.asset
        }
        const newAssets = assets.map(a => a.id === assetId ? updatedAsset : a)
        set({
          assets: newAssets
        })
        return { success: true, asset: updatedAsset }
      }

      return { success: false, error_message: result.error_message }
    } catch (error) {
      console.error('[useAssetStore] 更新资产信息失败:', error)
      return { success: false, error_message: String(error) }
    }
  },

  setThumbnailSize: (size) => {
    localStorage.setItem('thumbnailSize', String(size))
    set({ thumbnailSize: size })
  },

  setRatingFilter: (filter) => set({ ratingFilter: filter }),

  createCategory: async (name, parentId) => {
    try {
      if (isDevelopment()) {
        const newCategory: AssetCategory = {
          id: `cat-${Date.now()}`,
          name,
          isSystem: false,
          parentId: parentId || null,
          sortOrder: get().categories.filter(c => !c.parentId).length
        }
        set((state) => ({ categories: [...state.categories, newCategory] }))
        return { success: true }
      }

      const result = await window.pywebview.api.gallery_create_category(name, parentId)
      if (result.success) {
        await get().refreshCategories()
        return { success: true }
      }
      return { success: false, error: result.error_message }
    } catch (error) {
      console.error('[useAssetStore] 创建分类异常:', error)
      return { success: false, error: String(error) }
    }
  },

  updateCategory: async (categoryId, name) => {
    try {
      if (isDevelopment()) {
        set((state) => ({
          categories: state.categories.map((c) => (c.id === categoryId ? { ...c, name } : c))
        }))
        return { success: true }
      }

      const result = await window.pywebview.api.gallery_update_category(categoryId, name)
      if (result.success) {
        set((state) => ({ assets: applyMovedAssetPaths(state.assets, result.asset_paths) }))
        await get().refreshCategories()
        return { success: true }
      }
      return { success: false, error: result.error_message }
    } catch (error) {
      console.error('[useAssetStore] 更新分类异常:', error)
      return { success: false, error: String(error) }
    }
  },

  moveCategory: async (categoryId, parentId) => {
    try {
      if (isDevelopment()) {
        set((state) => ({
          categories: state.categories.map((c) => (c.id === categoryId ? { ...c, parentId } : c))
        }))
        return { success: true }
      }

      const result = await window.pywebview.api.gallery_move_category(categoryId, parentId)
      if (result.success) {
        set((state) => ({ assets: applyMovedAssetPaths(state.assets, result.asset_paths) }))
        await get().refreshCategories()
        return { success: true }
      }
      return { success: false, error: result.error_message }
    } catch (error) {
      console.error('[useAssetStore] 移动分类异常:', error)
      return { success: false, error: String(error) }
    }
  },

  deleteCategory: async (categoryId, moveContentsToParent = true) => {
    try {
      if (isDevelopment()) {
        set((state) => ({
          categories: state.categories.filter((c) => c.id !== categoryId)
        }))
        return { success: true }
      }

      const result = await window.pywebview.api.gallery_delete_category(categoryId, moveContentsToParent)
      if (result.success) {
        set((state) => ({ assets: applyMovedAssetPaths(state.assets, result.asset_paths) }))
        await get().refreshCategories()
        return { success: true }
      }
      return { success: false, error: result.error_message }
    } catch (error) {
      console.error('[useAssetStore] 删除分类异常:', error)
      return { success: false, error: String(error) }
    }
  },

  pushImageToComfyUI: async (assetId: string) => {
    try {
      if (isDevelopment()) {
        return { success: true, filename: 'mock_image.png' }
      }

      const result = await window.pywebview.api.gallery_push_image_to_comfyui(assetId)
      return {
        success: result.success,
        filename: result.filename,
        error_message: result.error_message
      }
    } catch (error) {
      console.error('[useAssetStore] 推送图片到 ComfyUI 异常:', error)
      return { success: false, error_message: String(error) }
    }
  }
}))
