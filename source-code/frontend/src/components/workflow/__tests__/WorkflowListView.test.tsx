/**
 * 工作流紧凑列表视图测试
 *
 * 覆盖列表特有的交互约定：普通模式单击驱动右侧详情、批量模式单击改为勾选、
 * 行内操作按钮不冒泡成选中、以及框选所需的 getCardRefs 注册。
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { WorkflowListView } from '../WorkflowListView'
import { DragProvider } from '../WorkflowDragContext'
import type { Workflow } from '@/types/workflow'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: { language: 'zh-CN' }
  })
}))

const makeWorkflow = (id: string, overrides: Partial<Workflow> = {}): Workflow => ({
  id,
  name: `wf-${id}`,
  description: `desc-${id}`,
  nodes: 3,
  createdAt: '2026-01-01T00:00:00Z',
  updatedAt: '2026-01-02T00:00:00Z',
  tags: ['tag-a'],
  ...overrides
})

const WORKFLOWS = [makeWorkflow('a'), makeWorkflow('b', { isFavorite: true })]

function renderList(props: Partial<React.ComponentProps<typeof WorkflowListView>> = {}) {
  const callbacks = {
    onSelectWorkflow: vi.fn(),
    onOpenDetail: vi.fn(),
    onExportWorkflow: vi.fn(),
    onDeleteWorkflow: vi.fn(),
    onToggleFavorite: vi.fn()
  }
  const listRef = { current: null }
  const utils = render(
    <DragProvider onDrop={() => undefined}>
      <WorkflowListView
        ref={listRef}
        workflows={WORKFLOWS}
        selectedWorkflowIds={[]}
        isBatchMode={false}
        onSelectWorkflow={callbacks.onSelectWorkflow}
        onOpenDetail={callbacks.onOpenDetail}
        onExportWorkflow={callbacks.onExportWorkflow}
        onDeleteWorkflow={callbacks.onDeleteWorkflow}
        onToggleFavorite={callbacks.onToggleFavorite}
        {...props}
      />
    </DragProvider>
  )
  return { ...utils, ...callbacks, listRef }
}

describe('WorkflowListView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('每个工作流渲染一行，行上带框选需要的 data-workflow-card', () => {
    const { container } = renderList()
    const rows = container.querySelectorAll('[data-workflow-card]')
    expect(rows).toHaveLength(2)
    expect(rows[0].getAttribute('data-workflow-card')).toBe('a')
    expect(rows[1].getAttribute('data-workflow-card')).toBe('b')
  })

  it('普通模式单击选中该行并交给详情面板，不进入勾选', () => {
    const { onOpenDetail, onSelectWorkflow } = renderList()
    fireEvent.click(screen.getByText('wf-a'))
    expect(onOpenDetail).toHaveBeenCalledWith(expect.objectContaining({ id: 'a' }))
    expect(onSelectWorkflow).not.toHaveBeenCalled()
  })

  it('批量模式单击改为勾选，不再切换详情', () => {
    const { onOpenDetail, onSelectWorkflow } = renderList({ isBatchMode: true })
    fireEvent.click(screen.getByText('wf-b'))
    expect(onSelectWorkflow).toHaveBeenCalledWith('b')
    expect(onOpenDetail).not.toHaveBeenCalled()
  })

  it('键盘 Enter 与鼠标单击等价', () => {
    const { onOpenDetail } = renderList()
    fireEvent.keyDown(screen.getByText('wf-a').closest('[data-workflow-card]') as Element, { key: 'Enter' })
    expect(onOpenDetail).toHaveBeenCalledWith(expect.objectContaining({ id: 'a' }))
  })

  it('当前选中行有高亮态，未选中行没有', () => {
    const { container } = renderList({ activeWorkflowId: 'a' })
    const rowA = container.querySelector('[data-workflow-card="a"]') as Element
    const rowB = container.querySelector('[data-workflow-card="b"]') as Element
    expect(rowA.className).toContain('bg-primary/10')
    expect(rowB.className).not.toContain('bg-primary/10')
  })

  it('行内操作按钮只执行自己的动作，不冒泡成选中', () => {
    const { onOpenDetail, onExportWorkflow, onToggleFavorite, onDeleteWorkflow } = renderList()
    const rowA = screen.getByText('wf-a').closest('[data-workflow-card]') as Element

    fireEvent.click(rowA.querySelector('[title="workflow.card.export"]') as Element)
    fireEvent.click(rowA.querySelector('[title="workflow.card.favorite"]') as Element)
    fireEvent.click(rowA.querySelector('[title="common.delete"]') as Element)

    expect(onExportWorkflow).toHaveBeenCalledWith(expect.objectContaining({ id: 'a' }))
    expect(onToggleFavorite).toHaveBeenCalledWith(expect.objectContaining({ id: 'a' }))
    expect(onDeleteWorkflow).toHaveBeenCalledWith(expect.objectContaining({ id: 'a' }))
    expect(onOpenDetail).not.toHaveBeenCalled()
  })

  it('getCardRefs 暴露行元素，供页面框选计算矩形', () => {
    const { listRef, container } = renderList()
    const refs = (listRef.current as unknown as { getCardRefs: () => Map<string, HTMLElement> }).getCardRefs()
    expect(Array.from(refs.keys()).sort()).toEqual(['a', 'b'])
    expect(refs.get('a')).toBe(container.querySelector('[data-workflow-card="a"]'))
  })
})
