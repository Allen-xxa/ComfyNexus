/**
 * useAssetStore 文件管理器模式测试
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useAssetStore } from '../useAssetStore'
import type { Asset, AssetCategory } from '@/mocks/asset'

const createAsset = (id: string, categoryId: string | null, filename = `${id}.png`): Asset => ({
  id,
  filename,
  filePath: `D:/gallery/${filename}`,
  thumbnailPath: null,
  type: 'image',
  width: 100,
  height: 100,
  size: 100,
  createdAt: '2026-01-01T00:00:00.000Z',
  hasWorkflow: false,
  isFavorite: false,
  categoryId,
  thumbnail: `/gallery/thumbnail/${id}`,
  url: `/gallery/asset/${id}`
})

const categories: AssetCategory[] = [
  { id: 'all', name: '全部', isSystem: true, parentId: null, sortOrder: 0 },
  { id: 'favorites', name: '收藏', isSystem: true, parentId: null, sortOrder: 1 },
  { id: 'parent', name: 'Parent', isSystem: false, parentId: null, sortOrder: 2, folderPath: 'Parent' },
  { id: 'child', name: 'Child', isSystem: false, parentId: 'parent', sortOrder: 0, folderPath: 'Parent/Child' }
]

const assets = [
  createAsset('root-asset', null, 'root.png'),
  createAsset('parent-asset', 'parent', 'parent.png'),
  createAsset('child-asset', 'child', 'child.png')
]

describe('useAssetStore file manager mode', () => {
  beforeEach(() => {
    vi.mocked(localStorage.setItem).mockClear()
    useAssetStore.setState({
      assets,
      categories,
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
      sortBy: 'name',
      sortDir: 'asc',
      scanProgress: null,
      isStoppingScan: false,
      _pollingInterval: null,
      thumbnailSize: 250,
      showFoldersInList: false
    })
  })

  it('关闭目录显示时保持原有聚合子分类资产行为', () => {
    useAssetStore.setState({ selectedCategoryId: 'parent', showFoldersInList: false })

    const result = useAssetStore.getState().getFilteredAssets()

    expect(result.map((asset) => asset.id)).toEqual(['child-asset', 'parent-asset'])
  })

  it('开启目录显示后只返回当前目录直属资产', () => {
    useAssetStore.setState({ selectedCategoryId: 'parent', showFoldersInList: true })

    const result = useAssetStore.getState().getFilteredAssets()

    expect(result.map((asset) => asset.id)).toEqual(['parent-asset'])
  })

  it('开启目录显示后列表条目按文件夹优先排列', () => {
    useAssetStore.setState({ selectedCategoryId: 'parent', showFoldersInList: true })

    const items = useAssetStore.getState().getGalleryItems()

    expect(items.map((item) => item.kind)).toEqual(['folder', 'asset'])
    expect(items[0]).toMatchObject({ kind: 'folder', category: { id: 'child' } })
    expect(items[1]).toMatchObject({ kind: 'asset', asset: { id: 'parent-asset' } })
  })

  it('全部目录在文件管理器模式下仍保持聚合资产视图', () => {
    useAssetStore.setState({ selectedCategoryId: 'all', showFoldersInList: true })

    const items = useAssetStore.getState().getGalleryItems()

    expect(items.map((item) => item.kind)).toEqual(['asset', 'asset', 'asset'])
    expect(items.map((item) => item.kind === 'asset' ? item.asset.id : '')).toEqual([
      'child-asset',
      'parent-asset',
      'root-asset'
    ])
  })

  it('资产属性筛选启用时不混入文件夹条目', () => {
    useAssetStore.setState({
      selectedCategoryId: 'parent',
      showFoldersInList: true,
      typeFilter: ['image']
    })

    const items = useAssetStore.getState().getGalleryItems()

    expect(items.every((item) => item.kind === 'asset')).toBe(true)
  })

  it('收藏目录在文件管理器模式下不显示文件夹', () => {
    useAssetStore.setState({
      selectedCategoryId: 'favorites',
      showFoldersInList: true,
      assets: [
        { ...assets[0], isFavorite: true },
        { ...assets[1], isFavorite: false },
        { ...assets[2], isFavorite: true }
      ]
    })

    const items = useAssetStore.getState().getGalleryItems()

    expect(items.every((item) => item.kind === 'asset')).toBe(true)
    expect(items).toHaveLength(2)
  })

  it('切换文件管理器模式会清空批量选择', () => {
    useAssetStore.setState({ selectedAssetIds: ['parent-asset'], isBatchMode: true })

    useAssetStore.getState().setShowFoldersInList(true)

    expect(useAssetStore.getState().selectedAssetIds).toEqual([])
    expect(useAssetStore.getState().isBatchMode).toBe(false)
    expect(localStorage.setItem).toHaveBeenCalledWith('asset-show-folders-in-list', 'true')
  })
})
