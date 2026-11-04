/**
 * useWorkflowStore 批量操作单元测试
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { act } from '@testing-library/react'
import { useWorkflowStore } from '../useWorkflowStore'
import * as workflowApi from '@/api/workflow'

vi.mock('@/api/workflow', () => ({
  workflowApi: {
    getWorkflows: vi.fn(),
    getFolders: vi.fn(),
    batchMoveToFolder: vi.fn(),
    batchToggleFavorite: vi.fn(),
    batchDeleteWorkflows: vi.fn()
  }
}))

describe('useWorkflowStore - 批量操作', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    
    useWorkflowStore.setState({
      workflows: [
        { id: 'workflow-1', name: '工作流1', isFavorite: false, folderId: null },
        { id: 'workflow-2', name: '工作流2', isFavorite: false, folderId: null },
        { id: 'workflow-3', name: '工作流3', isFavorite: true, folderId: 'folder-1' }
      ],
      selectedWorkflowIds: [],
      isBatchMode: false
    })
  })

  describe('setBatchMode', () => {
    it('should enable batch mode', () => {
      act(() => {
        useWorkflowStore.getState().setBatchMode(true)
      })

      expect(useWorkflowStore.getState().isBatchMode).toBe(true)
    })

    it('should disable batch mode and clear selection', () => {
      useWorkflowStore.setState({ selectedWorkflowIds: ['workflow-1', 'workflow-2'] })

      act(() => {
        useWorkflowStore.getState().setBatchMode(false)
      })

      expect(useWorkflowStore.getState().isBatchMode).toBe(false)
      expect(useWorkflowStore.getState().selectedWorkflowIds).toEqual([])
    })
  })

  describe('toggleWorkflowSelection', () => {
    it('should add workflow to selection', () => {
      act(() => {
        useWorkflowStore.getState().toggleWorkflowSelection('workflow-1')
      })

      expect(useWorkflowStore.getState().selectedWorkflowIds).toContain('workflow-1')
    })

    it('should remove workflow from selection', () => {
      useWorkflowStore.setState({ selectedWorkflowIds: ['workflow-1'] })

      act(() => {
        useWorkflowStore.getState().toggleWorkflowSelection('workflow-1')
      })

      expect(useWorkflowStore.getState().selectedWorkflowIds).not.toContain('workflow-1')
    })

    it('should enable batch mode when selecting', () => {
      act(() => {
        useWorkflowStore.getState().toggleWorkflowSelection('workflow-1')
      })

      expect(useWorkflowStore.getState().isBatchMode).toBe(true)
    })
  })

  describe('setSelectedWorkflowIds', () => {
    it('should set selected workflow ids', () => {
      act(() => {
        useWorkflowStore.getState().setSelectedWorkflowIds(['workflow-1', 'workflow-2'])
      })

      expect(useWorkflowStore.getState().selectedWorkflowIds).toEqual(['workflow-1', 'workflow-2'])
    })
  })

  describe('clearSelection', () => {
    it('should clear selection and disable batch mode', () => {
      useWorkflowStore.setState({
        selectedWorkflowIds: ['workflow-1', 'workflow-2'],
        isBatchMode: true
      })

      act(() => {
        useWorkflowStore.getState().clearSelection()
      })

      expect(useWorkflowStore.getState().selectedWorkflowIds).toEqual([])
      expect(useWorkflowStore.getState().isBatchMode).toBe(false)
    })
  })

  describe('batchMoveToFolder', () => {
    it('should call API and refresh workflows on success', async () => {
      vi.mocked(workflowApi.workflowApi.batchMoveToFolder).mockResolvedValue({
        success: true,
        movedCount: 2
      })
      vi.mocked(workflowApi.workflowApi.getWorkflows).mockResolvedValue([])
      vi.mocked(workflowApi.workflowApi.getFolders).mockResolvedValue([])

      let result: boolean
      await act(async () => {
        result = await useWorkflowStore.getState().batchMoveToFolder(
          ['workflow-1', 'workflow-2'],
          'folder-2'
        )
      })

      expect(workflowApi.workflowApi.batchMoveToFolder).toHaveBeenCalledWith(
        ['workflow-1', 'workflow-2'],
        'folder-2'
      )
      expect(result!).toBe(true)
    })

    it('should return false on API failure', async () => {
      vi.mocked(workflowApi.workflowApi.batchMoveToFolder).mockResolvedValue({
        success: false,
        movedCount: 0
      })

      let result: boolean
      await act(async () => {
        result = await useWorkflowStore.getState().batchMoveToFolder(
          ['workflow-1'],
          'folder-2'
        )
      })

      expect(result!).toBe(false)
    })

    it('should clear selection after successful move', async () => {
      useWorkflowStore.setState({ selectedWorkflowIds: ['workflow-1'] })
      vi.mocked(workflowApi.workflowApi.batchMoveToFolder).mockResolvedValue({
        success: true,
        movedCount: 1
      })
      vi.mocked(workflowApi.workflowApi.getWorkflows).mockResolvedValue([])
      vi.mocked(workflowApi.workflowApi.getFolders).mockResolvedValue([])

      await act(async () => {
        await useWorkflowStore.getState().batchMoveToFolder(['workflow-1'], 'folder-2')
      })

      expect(useWorkflowStore.getState().selectedWorkflowIds).toEqual([])
      expect(useWorkflowStore.getState().isBatchMode).toBe(false)
    })
  })

  describe('batchToggleFavorite', () => {
    it('should call API and refresh workflows on success', async () => {
      vi.mocked(workflowApi.workflowApi.batchToggleFavorite).mockResolvedValue({
        success: true
      })
      vi.mocked(workflowApi.workflowApi.getWorkflows).mockResolvedValue([])
      vi.mocked(workflowApi.workflowApi.getFolders).mockResolvedValue([])

      let result: boolean
      await act(async () => {
        result = await useWorkflowStore.getState().batchToggleFavorite(['workflow-1'])
      })

      expect(workflowApi.workflowApi.batchToggleFavorite).toHaveBeenCalledWith(['workflow-1'])
      expect(result!).toBe(true)
    })

    it('should return false on API failure', async () => {
      vi.mocked(workflowApi.workflowApi.batchToggleFavorite).mockResolvedValue({
        success: false
      })

      let result: boolean
      await act(async () => {
        result = await useWorkflowStore.getState().batchToggleFavorite(['workflow-1'])
      })

      expect(result!).toBe(false)
    })
  })

  describe('batchDeleteWorkflows', () => {
    it('should call API and remove workflows from state on success', async () => {
      vi.mocked(workflowApi.workflowApi.batchDeleteWorkflows).mockResolvedValue({
        success: true,
        deletedCount: 2
      })

      let result: boolean
      await act(async () => {
        result = await useWorkflowStore.getState().batchDeleteWorkflows([
          'workflow-1',
          'workflow-2'
        ])
      })

      expect(workflowApi.workflowApi.batchDeleteWorkflows).toHaveBeenCalledWith([
        'workflow-1',
        'workflow-2'
      ])
      expect(result!).toBe(true)

      const workflows = useWorkflowStore.getState().workflows
      expect(workflows.find((w) => w.id === 'workflow-1')).toBeUndefined()
      expect(workflows.find((w) => w.id === 'workflow-2')).toBeUndefined()
    })

    it('should clear selection after successful delete', async () => {
      useWorkflowStore.setState({ selectedWorkflowIds: ['workflow-1'] })
      vi.mocked(workflowApi.workflowApi.batchDeleteWorkflows).mockResolvedValue({
        success: true,
        deletedCount: 1
      })

      await act(async () => {
        await useWorkflowStore.getState().batchDeleteWorkflows(['workflow-1'])
      })

      expect(useWorkflowStore.getState().selectedWorkflowIds).toEqual([])
      expect(useWorkflowStore.getState().isBatchMode).toBe(false)
    })

    it('should return false on API failure', async () => {
      vi.mocked(workflowApi.workflowApi.batchDeleteWorkflows).mockResolvedValue({
        success: false,
        deletedCount: 0
      })

      let result: boolean
      await act(async () => {
        result = await useWorkflowStore.getState().batchDeleteWorkflows(['workflow-1'])
      })

      expect(result!).toBe(false)
    })
  })

  describe('viewMode', () => {
    it('切换视图偏好会同时更新状态和 localStorage', () => {
      act(() => {
        useWorkflowStore.getState().setViewMode('card')
      })

      expect(useWorkflowStore.getState().viewMode).toBe('card')
      expect(localStorage.setItem).toHaveBeenCalledWith('workflow-view-mode', 'card')

      act(() => {
        useWorkflowStore.getState().setViewMode('list')
      })

      expect(useWorkflowStore.getState().viewMode).toBe('list')
      expect(localStorage.setItem).toHaveBeenCalledWith('workflow-view-mode', 'list')
    })
  })
})
