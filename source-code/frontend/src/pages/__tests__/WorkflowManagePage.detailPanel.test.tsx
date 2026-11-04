/**
 * 工作流页面：紧凑列表与右侧常驻详情面板的联动
 *
 * 页面无法在纯浏览器里跑真实数据（工作流来自 pywebview），所以这里用 store 替身
 * 验证三件容易被改坏的事：默认进列表视图、选中行驱动详情面板、切到卡片视图后仍是同一份数据。
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import WorkflowManagePage from '../WorkflowManagePage'
import { useWorkflowStore } from '@/stores/useWorkflowStore'
import { useEnvStore } from '@/stores/useEnvStore'

vi.mock('@/stores/useEnvStore')
vi.mock('@/stores/useWorkflowStore')

// ReactFlow 和依赖面板各自有重依赖，本页测试只关心列表与面板的联动。
// 节点图替身把 rawData.id 透出，用来判定面板当前加载的是哪个工作流。
vi.mock('@/components/workflow/WorkflowGraph', () => ({
  WorkflowGraph: ({ data }: { data?: { id?: string } }) => (
    <div data-testid="workflow-graph" data-workflow={data?.id} />
  )
}))
vi.mock('@/components/workflow/DependencyPanel', () => ({
  DependencyPanel: () => <div data-testid="dependency-panel" />
}))

vi.mock('@/api/workflow', () => ({
  workflowApi: {
    exportWorkflow: vi.fn().mockResolvedValue(null),
    checkPluginsStatus: vi.fn().mockResolvedValue({}),
    importWorkflow: vi.fn()
  }
}))

vi.mock('@/utils/workflowParser', () => ({
  loadNodeTypeMap: vi.fn().mockResolvedValue(undefined),
  loadLocalNodeMap: vi.fn().mockResolvedValue(undefined),
  getWorkflowStats: vi.fn().mockReturnValue(null)
}))

function makeWorkflow(id: string, overrides: Partial<{ name: string; rawData: unknown }> = {}) {
  return {
    id,
    name: overrides.name ?? `工作流 ${id}`,
    description: `说明 ${id}`,
    nodes: 5,
    createdAt: '2026-01-01T00:00:00Z',
    updatedAt: '2026-01-02T00:00:00Z',
    tags: ['标签'],
    folderId: null,
    rawData: { id, nodes: [], links: [] },
    ...overrides
  }
}

let storeState: Record<string, unknown>

beforeEach(() => {
  storeState = {
    isLoading: false,
    workflows: [makeWorkflow('a'), makeWorkflow('b')],
    folders: [],
    filterType: 'all',
    selectedFolderId: null,
    setFilterType: vi.fn(),
    setSelectedFolderId: vi.fn(),
    viewMode: 'list',
    setViewMode: vi.fn((mode: string) => {
      storeState.viewMode = mode
    }),
    getFilteredWorkflows: () => storeState.workflows,
    refreshWorkflows: vi.fn().mockResolvedValue(undefined),
    deleteWorkflow: vi.fn(),
    toggleFavorite: vi.fn(),
    updateWorkflowInfo: vi.fn(),
    addWorkflow: vi.fn(),
    selectedWorkflowIds: [],
    isBatchMode: false,
    toggleWorkflowSelection: vi.fn(),
    clearSelection: vi.fn(),
    batchToggleFavorite: vi.fn(),
    batchDeleteWorkflows: vi.fn(),
    setBatchMode: vi.fn(),
    addFolder: vi.fn(),
    updateFolder: vi.fn(),
    deleteFolder: vi.fn(),
    filterTags: [],
    activeFilterTag: 'all',
    setActiveFilterTag: vi.fn()
  }

  vi.mocked(useEnvStore).mockImplementation((selector: unknown) => {
    const envState = { currentEnvId: 'env-1', environments: [{ id: 'env-1' }] }
    return selector ? (selector as (s: unknown) => unknown)(envState) : envState
  })

  const mockedStore = vi.mocked(useWorkflowStore)
  mockedStore.mockImplementation((selector: unknown) => {
    return selector ? (selector as (s: unknown) => unknown)(storeState) : storeState
  })
  // zustand -store 上的静态方法在替身上不存在，页面用到时补上最小实现
  Object.assign(mockedStore, {
    getState: () => storeState,
    setState: (updater: (s: Record<string, unknown>) => Record<string, unknown>) =>
      Object.assign(storeState, updater(storeState))
  })
})

const rowIds = (container: HTMLElement) =>
  Array.from(container.querySelectorAll('[data-workflow-card]')).map(
    (el) => el.getAttribute('data-workflow-card')
  )

// 详情面板当前加载的是哪个工作流：行名和面板头部都会显示名字，只有节点图替身能区分
const panelWorkflowId = () =>
  screen.getByTestId('workflow-graph').getAttribute('data-workflow')

// 面板挂载时会异步预热节点映射表，渲染放在 act 里等它落地，避免 act 警告
async function mountPage() {
  let rendered!: ReturnType<typeof render>
  await act(async () => {
    rendered = render(<WorkflowManagePage />)
  })
  return rendered
}

describe('WorkflowManagePage 列表 + 详情面板', () => {
  it('默认紧凑列表视图，第一项自动进入详情面板', async () => {
    const { container } = await mountPage()

    expect(rowIds(container)).toEqual(['a', 'b'])
    // 卡片视图独有的"分析"按钮不应出现
    expect(screen.queryByText('分析')).not.toBeInTheDocument()
    expect(panelWorkflowId()).toBe('a')
    expect(screen.getByTestId('dependency-panel')).toBeInTheDocument()
  })

  it('点击另一行把详情面板切到该工作流', async () => {
    const { container } = await mountPage()

    fireEvent.click(container.querySelector('[data-workflow-card="b"]') as Element)

    expect(panelWorkflowId()).toBe('b')
    expect(container.querySelector('[data-workflow-card="b"]')?.className).toContain('bg-primary/10')
  })

  it('批量模式下点击行改为勾选，不动详情面板', async () => {
    storeState.isBatchMode = true
    const { container } = await mountPage()

    fireEvent.click(container.querySelector('[data-workflow-card="b"]') as Element)

    expect(storeState.toggleWorkflowSelection).toHaveBeenCalledWith('b')
    expect(panelWorkflowId()).toBe('a')
  })

  it('切到卡片视图后仍渲染同一批工作流', async () => {
    const { container, rerender } = await mountPage()

    fireEvent.click(screen.getByTitle('卡片网格'))
    expect(storeState.setViewMode).toHaveBeenCalledWith('card')

    // store 是替身，没有订阅机制，手动重渲染以取到新的 viewMode
    await act(async () => {
      rerender(<WorkflowManagePage />)
    })

    expect(rowIds(container)).toEqual(['a', 'b'])
    // 卡片视图独有的"分析"按钮：每张卡片各一个
    expect(screen.getAllByText('分析')).toHaveLength(2)
  })
})
