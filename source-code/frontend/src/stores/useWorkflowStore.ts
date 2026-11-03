/**
 * 工作流管理状态管理
 */

import { create } from 'zustand'
import i18n from '@/i18n'
import type { Workflow, WorkflowFolder, WorkflowInfoUpdate } from '@/types/workflow'
import { workflowApi } from '@/api/workflow'

export interface WorkflowFilterTag {
  id: string
  name: string
}

const extractFilterTags = (workflows: Workflow[]): WorkflowFilterTag[] => {
  const tagSet = new Set<string>()
  workflows.forEach(workflow => {
    workflow.tags?.forEach(tag => {
      if (tag && tag.trim()) {
        tagSet.add(tag.trim())
      }
    })
  })
  const tags = Array.from(tagSet).sort()
  return [
    { id: 'all', name: i18n.t('workflow.filterTag.all') },
    ...tags.map(tag => ({ id: tag, name: tag }))
  ]
}

interface WorkflowStore {
  workflows: Workflow[]
  selectedWorkflow: Workflow | null
  isLoading: boolean
  searchQuery: string
  filterType: 'all' | 'favorites' | 'folder'
  selectedFolderId: string | null
  folders: WorkflowFolder[]
  selectedWorkflowIds: string[]
  isBatchMode: boolean
  filterTags: WorkflowFilterTag[]
  activeFilterTag: string

  setWorkflows: (workflows: Workflow[]) => void
  setSelectedWorkflow: (workflow: Workflow | null) => void
  addWorkflow: (workflow: Workflow) => void
  deleteWorkflow: (id: string) => Promise<void>
  updateWorkflow: (id: string, updates: Partial<Workflow>) => void
  refreshWorkflows: () => Promise<void>
  toggleFavorite: (id: string) => Promise<void>
  updateWorkflowInfo: (id: string, info: WorkflowInfoUpdate) => Promise<Workflow | null>
  setSearchQuery: (query: string) => void
  setFilterType: (type: 'all' | 'favorites' | 'folder') => void
  setSelectedFolderId: (folderId: string | null) => void
  addFolder: (name: string, parentId?: string) => Promise<WorkflowFolder | null>
  deleteFolder: (id: string, moveContentsToRoot?: boolean) => Promise<boolean>
  updateFolder: (id: string, updates: Partial<WorkflowFolder>) => Promise<boolean>
  reloadAfterFolderChange: () => Promise<void>
  moveWorkflowToFolder: (workflowId: string, folderId: string | null) => Promise<void>
  setActiveFilterTag: (tagId: string) => void

  setBatchMode: (mode: boolean) => void
  toggleWorkflowSelection: (id: string) => void
  setSelectedWorkflowIds: (ids: string[]) => void
  clearSelection: () => void
  batchMoveToFolder: (workflowIds: string[], folderId: string | null) => Promise<boolean>
  batchToggleFavorite: (workflowIds: string[]) => Promise<boolean>
  batchDeleteWorkflows: (workflowIds: string[]) => Promise<boolean>

  getFilteredWorkflows: () => Workflow[]
}

export const useWorkflowStore = create<WorkflowStore>((set, get) => ({
  workflows: [],
  selectedWorkflow: null,
  isLoading: false,
  searchQuery: '',
  filterType: 'all',
  selectedFolderId: null,
  folders: [],
  selectedWorkflowIds: [],
  isBatchMode: false,
  filterTags: [],
  activeFilterTag: 'all',

  setWorkflows: (workflows) => set({ workflows, filterTags: extractFilterTags(workflows) }),

  setSelectedWorkflow: (workflow) => set({ selectedWorkflow: workflow }),

  addWorkflow: (workflow) => {
    set((state) => ({
      workflows: [workflow, ...state.workflows]
    }))
  },

  deleteWorkflow: async (id) => {
    const success = await workflowApi.deleteWorkflow(id)
    if (success) {
      set((state) => ({
        workflows: state.workflows.filter((w) => w.id !== id),
        selectedWorkflow: state.selectedWorkflow?.id === id ? null : state.selectedWorkflow,
        selectedWorkflowIds: state.selectedWorkflowIds.filter((wid) => wid !== id)
      }))
    }
  },

  updateWorkflow: (id, updates) => {
    set((state) => ({
      workflows: state.workflows.map((w) =>
        w.id === id ? { ...w, ...updates, updatedAt: new Date().toISOString() } : w
      )
    }))
  },

  refreshWorkflows: async () => {
    set({ isLoading: true })
    const [workflows, folders] = await Promise.all([
      workflowApi.getWorkflows(),
      workflowApi.getFolders()
    ])
    set({ workflows, folders, filterTags: extractFilterTags(workflows), isLoading: false })
  },

  toggleFavorite: async (id) => {
    const result = await workflowApi.toggleFavorite(id)
    if (result) {
      set((state) => ({
        workflows: state.workflows.map((w) =>
          w.id === id ? { ...w, isFavorite: result.isFavorite } : w
        )
      }))
    }
  },

  updateWorkflowInfo: async (id, info) => {
    const updated = await workflowApi.updateWorkflowInfo(id, info)
    if (updated) {
      const newWorkflows = get().workflows.map((w) =>
        w.id === id ? {
          ...w,
          name: updated.name ?? w.name,
          description: updated.description ?? w.description,
          tags: updated.tags ?? w.tags,
          previews: updated.previews ?? w.previews,
          preview: updated.preview ?? w.preview,
          nodes: updated.nodes ?? w.nodes,
          updatedAt: updated.updatedAt ?? w.updatedAt
        } : w
      )
      set({
        workflows: newWorkflows,
        filterTags: extractFilterTags(newWorkflows)
      })
      return updated
    }
    return null
  },

  setSearchQuery: (query) => set({ searchQuery: query }),

  setFilterType: (type) => set({ filterType: type, selectedFolderId: null }),

  setSelectedFolderId: (folderId) => {
    set({
      selectedFolderId: folderId,
      filterType: folderId ? 'folder' : 'all'
    })
  },

  // 文件夹增删改后从磁盘重载：文件夹 ID 由相对路径派生，重命名/移动会连带改变
  // 子级文件夹与其内工作流的路径，只有重新扫描才能反映真实结构。
  // 这里静默重载（不置 isLoading），避免每次操作都闪一次加载态。
  reloadAfterFolderChange: async () => {
    const [workflows, folders] = await Promise.all([
      workflowApi.getWorkflows(),
      workflowApi.getFolders()
    ])
    set({ workflows, folders, filterTags: extractFilterTags(workflows) })
  },

  addFolder: async (name, parentId) => {
    const folder = await workflowApi.createFolder(name, parentId)
    if (folder) {
      await get().reloadAfterFolderChange()
    }
    return folder
  },

  deleteFolder: async (id, moveContentsToRoot = false) => {
    const success = await workflowApi.deleteFolder(id, moveContentsToRoot)
    if (success) {
      await get().reloadAfterFolderChange()
      const { selectedFolderId } = get()
      if (selectedFolderId === id) {
        set({ selectedFolderId: null, filterType: 'all' })
      }
    }
    return success
  },

  updateFolder: async (id, updates) => {
    const updated = await workflowApi.updateFolder(id, updates)
    if (updated) {
      await get().reloadAfterFolderChange()
      return true
    }
    return false
  },

  moveWorkflowToFolder: async (workflowId, folderId) => {
    const updated = await workflowApi.moveWorkflowToFolder(workflowId, folderId)
    if (updated) {
      set((state) => ({
        workflows: state.workflows.map((w) =>
          w.id === workflowId ? updated : w
        )
      }))
    }
  },

  setActiveFilterTag: (tagId) => set({ activeFilterTag: tagId }),

  setBatchMode: (mode) => set({ isBatchMode: mode, selectedWorkflowIds: mode ? get().selectedWorkflowIds : [] }),

  toggleWorkflowSelection: (id) => {
    set((state) => {
      const isSelected = state.selectedWorkflowIds.includes(id)
      const newSelectedIds = isSelected
        ? state.selectedWorkflowIds.filter((wid) => wid !== id)
        : [...state.selectedWorkflowIds, id]
      return {
        selectedWorkflowIds: newSelectedIds,
        isBatchMode: newSelectedIds.length > 0 ? true : state.isBatchMode
      }
    })
  },

  setSelectedWorkflowIds: (ids) => set({ selectedWorkflowIds: ids }),

  clearSelection: () => set({ selectedWorkflowIds: [], isBatchMode: false }),

  batchMoveToFolder: async (workflowIds, folderId) => {
    const result = await workflowApi.batchMoveToFolder(workflowIds, folderId)
    if (result.success) {
      await get().refreshWorkflows()
      set({ selectedWorkflowIds: [], isBatchMode: false })
    }
    return result.success
  },

  batchToggleFavorite: async (workflowIds) => {
    const result = await workflowApi.batchToggleFavorite(workflowIds)
    if (result.success) {
      await get().refreshWorkflows()
    }
    return result.success
  },

  batchDeleteWorkflows: async (workflowIds) => {
    const result = await workflowApi.batchDeleteWorkflows(workflowIds)
    if (result.success) {
      set((state) => ({
        workflows: state.workflows.filter((w) => !workflowIds.includes(w.id)),
        selectedWorkflowIds: [],
        isBatchMode: false
      }))
    }
    return result.success
  },

  getFilteredWorkflows: () => {
    const { workflows, searchQuery, filterType, selectedFolderId, activeFilterTag } = get()

    let filtered = Array.isArray(workflows) ? workflows : []

    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      filtered = filtered.filter(
        (w) =>
          w?.name?.toLowerCase().includes(query) ||
          w?.description?.toLowerCase().includes(query) ||
          (Array.isArray(w?.tags) && w.tags.some((tag) => tag?.toLowerCase().includes(query)))
      )
    }

    if (filterType === 'favorites') {
      filtered = filtered.filter((w) => w?.isFavorite)
    } else if (filterType === 'folder' && selectedFolderId) {
      // 选中文件夹时包含其所有子文件夹内的工作流。
      // 文件夹 ID 基于相对路径（"folder:a/b"），子级 ID 一定是父级 ID 加 "/" 前缀。
      const prefix = `${selectedFolderId}/`
      filtered = filtered.filter(
        (w) => w?.folderId === selectedFolderId || (w?.folderId && w.folderId.startsWith(prefix))
      )
    }

    if (activeFilterTag !== 'all') {
      filtered = filtered.filter((w) => w?.tags?.includes(activeFilterTag))
    }

    return filtered
  }
}))
