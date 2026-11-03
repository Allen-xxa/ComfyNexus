/**
 * useAssetStore 二级筛选区测试
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { useAssetStore } from '../useAssetStore'
import type { Asset } from '@/mocks/asset'

const DAY = 86400000

const createAsset = (id: string, overrides: Partial<Asset> = {}): Asset => ({
  id,
  filename: `${id}.png`,
  filePath: `D:/gallery/${id}.png`,
  thumbnailPath: null,
  type: 'image',
  width: 100,
  height: 100,
  size: 100,
  createdAt: new Date(Date.now() - 400 * DAY).toISOString(),
  hasWorkflow: false,
  isFavorite: false,
  categoryId: null,
  ...overrides
})

const assets = [
  createAsset('a', { type: 'image', model: 'FLUX\\flux2Klein9B_v10.safetensors', rating: 4, hasWorkflow: true }),
  createAsset('b', { type: 'video', model: 'FLUX\\flux2Klein9B_v10.safetensors', size: 300 }),
  createAsset('c', { type: 'image', model: 'qwen_image_2.1_bf16.safetensors', rating: 2, size: 100 }),
  createAsset('d', {
    type: 'image',
    model: 'qwen_image_2.1_bf16.safetensors',
    rating: 5,
    size: 200,
    createdAt: new Date().toISOString()
  }),
  createAsset('e', { type: 'image', size: 50, tags: ['海报'], description: '周末稿' })
]

const visibleIds = () => useAssetStore.getState().getFilteredAssets().map((asset) => asset.id)

describe('useAssetStore 二级筛选', () => {
  beforeEach(() => {
    useAssetStore.setState({
      assets,
      categories: [],
      selectedCategoryId: 'all',
      searchQuery: '',
      typeFilter: [],
      onlyWithWorkflow: false,
      modelFilter: [],
      dateFilter: 'all',
      ratingFilter: 'all',
      sortBy: 'name',
      sortDir: 'asc',
      showFoldersInList: false
    })
  })

  it('类型多选在空选择时不过滤，选中后只保留对应类型', () => {
    expect(visibleIds()).toEqual(['a', 'b', 'c', 'd', 'e'])

    useAssetStore.getState().toggleTypeFilter('video')
    expect(visibleIds()).toEqual(['b'])

    useAssetStore.getState().toggleTypeFilter('image')
    expect(visibleIds()).toEqual(['a', 'b', 'c', 'd', 'e'])

    useAssetStore.getState().toggleTypeFilter('video')
    expect(visibleIds()).toEqual(['a', 'c', 'd', 'e'])
  })

  it('含工作流开关只看 hasWorkflow', () => {
    useAssetStore.getState().setOnlyWithWorkflow(true)
    expect(visibleIds()).toEqual(['a'])
  })

  it('模型多选按模型原串匹配，未选中的模型被排除', () => {
    useAssetStore.getState().toggleModelFilter('qwen_image_2.1_bf16.safetensors')
    expect(visibleIds()).toEqual(['c', 'd'])

    useAssetStore.getState().toggleModelFilter('FLUX\\flux2Klein9B_v10.safetensors')
    expect(visibleIds()).toEqual(['a', 'b', 'c', 'd'])

    useAssetStore.getState().toggleModelFilter('qwen_image_2.1_bf16.safetensors')
    expect(visibleIds()).toEqual(['a', 'b'])
  })

  it('时间区间按自然日回推，旧资产被排除', () => {
    expect(visibleIds()).toEqual(['a', 'b', 'c', 'd', 'e'])

    useAssetStore.getState().setDateFilter('week')
    expect(visibleIds()).toEqual(['d'])

    useAssetStore.getState().setDateFilter('all')
    expect(visibleIds()).toEqual(['a', 'b', 'c', 'd', 'e'])
  })

  it('星级按"至少 N 星"理解，0 档单独表示未评分', () => {
    useAssetStore.getState().setRatingFilter('3')
    expect(visibleIds()).toEqual(['a', 'd'])

    useAssetStore.getState().setRatingFilter('0')
    expect(visibleIds()).toEqual(['b', 'e'])
  })

  it('排序方向可切换', () => {
    useAssetStore.getState().setSortBy('size')
    expect(useAssetStore.getState().sortDir).toBe('desc')
    expect(visibleIds()).toEqual(['b', 'd', 'a', 'c', 'e'])

    useAssetStore.getState().setSortDir('asc')
    expect(visibleIds()).toEqual(['e', 'a', 'c', 'd', 'b'])

    useAssetStore.getState().setSortBy('rating')
    expect(useAssetStore.getState().sortDir).toBe('desc')
    expect(visibleIds()).toEqual(['d', 'a', 'c', 'b', 'e'])
  })

  it('搜索覆盖标签与备注，标签不再是独立筛选项也能被找到', () => {
    useAssetStore.getState().setSearchQuery('海报')
    expect(visibleIds()).toEqual(['e'])

    useAssetStore.getState().setSearchQuery('周末稿')
    expect(visibleIds()).toEqual(['e'])
  })

  it('模型选项按资产数倒序，无模型的资产不计入', () => {
    expect(useAssetStore.getState().getModelOptions()).toEqual([
      { model: 'FLUX\\flux2Klein9B_v10.safetensors', count: 2 },
      { model: 'qwen_image_2.1_bf16.safetensors', count: 2 }
    ])
  })

  it('清除筛选复位所有属性条件，但保留搜索词与分类', () => {
    useAssetStore.getState().toggleTypeFilter('video')
    useAssetStore.getState().setOnlyWithWorkflow(true)
    useAssetStore.getState().setDateFilter('month')
    useAssetStore.getState().setRatingFilter('4')
    useAssetStore.getState().setSearchQuery('关键词')
    useAssetStore.setState({ selectedCategoryId: 'favorites' })
    expect(useAssetStore.getState().hasAttributeFilter()).toBe(true)

    useAssetStore.getState().clearAttributeFilters()

    expect(useAssetStore.getState().hasAttributeFilter()).toBe(false)
    expect(useAssetStore.getState().typeFilter).toEqual([])
    expect(useAssetStore.getState().searchQuery).toBe('关键词')
    expect(useAssetStore.getState().selectedCategoryId).toBe('favorites')
  })
})
