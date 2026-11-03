/**
 * 资产库瀑布流网格 - 横向瀑布流布局
 */

import { useRef, useCallback, forwardRef, useImperativeHandle, useMemo, useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useAssetStore } from '@/stores/useAssetStore'
import { AssetCard } from './AssetCard'
import { AssetFolderCard } from './AssetFolderCard'
import type { Asset } from '@/mocks/asset'

export interface AssetMasonryGridRef {
  getCardRefs: () => Map<string, HTMLDivElement>
}

interface AssetMasonryGridProps {
  onImageClick?: (asset: Asset) => void
  onImageDoubleClick?: (asset: Asset) => void
  /** 卡片上的「查看」入口，进入影院模式 */
  onView?: (asset: Asset) => void
  onImageContextMenu?: (e: React.MouseEvent, asset: Asset) => void
}

const SKELETON_HEIGHTS = [320, 280, 400, 350, 260, 380, 300, 420, 340, 290, 360, 310]
const GAP = 20

export const AssetMasonryGrid = forwardRef<AssetMasonryGridRef, AssetMasonryGridProps>(
  function AssetMasonryGrid({ onImageClick, onImageDoubleClick, onView, onImageContextMenu }, ref) {
    const { t } = useTranslation()
    const { 
      isLoading, 
      getFilteredAssets, 
      getGalleryItems,
      setSelectedCategoryId,
      clearSelection,
      setBatchMode,
      isBatchMode, 
      thumbnailSize
    } = useAssetStore()
    const cardRefs = useRef<Map<string, HTMLDivElement>>(new Map())
    const containerRef = useRef<HTMLDivElement>(null)
    const [columnCount, setColumnCount] = useState(4)

    useImperativeHandle(ref, () => ({
      getCardRefs: () => cardRefs.current
    }))

    const filteredAssets = getFilteredAssets()

    const galleryItems = getGalleryItems()

    const folderItems = galleryItems.filter((item) => item.kind === 'folder')

    const registerCardRef = useCallback((id: string, el: HTMLDivElement | null) => {
      if (el) {
        cardRefs.current.set(id, el)
      } else {
        cardRefs.current.delete(id)
      }
    }, [])

    useEffect(() => {
      const updateColumnCount = () => {
        if (containerRef.current) {
          const containerWidth = containerRef.current.offsetWidth - 48
          const count = Math.max(1, Math.floor((containerWidth + GAP) / (thumbnailSize + GAP)))
          setColumnCount(count)
        }
      }
      
      updateColumnCount()
      window.addEventListener('resize', updateColumnCount)
      return () => window.removeEventListener('resize', updateColumnCount)
    }, [thumbnailSize])

    const columns = useMemo(() => {
      const safeColumnCount = Math.max(1, columnCount)
      const result: Asset[][] = Array.from({ length: safeColumnCount }, () => [])
      const columnHeights: number[] = Array(safeColumnCount).fill(0)
      
      for (const asset of filteredAssets) {
        if (!asset || !asset.width || !asset.height) continue
        
        const minHeightIndex = columnHeights.indexOf(Math.min(...columnHeights))
        if (minHeightIndex >= 0 && result[minHeightIndex]) {
          result[minHeightIndex].push(asset)
          columnHeights[minHeightIndex] += asset.height / asset.width
        }
      }
      
      return result
    }, [filteredAssets, columnCount])

    const folderGridStyle = useMemo(() => ({
      gridTemplateColumns: `repeat(${Math.max(1, columnCount)}, minmax(0, 1fr))`
    }), [columnCount])

    const handleOpenFolder = useCallback((categoryId: string) => {
      clearSelection()
      setBatchMode(false)
      setSelectedCategoryId(categoryId)
    }, [clearSelection, setBatchMode, setSelectedCategoryId])

    const skeletonHeights = useMemo(() => SKELETON_HEIGHTS, [])

    if (isLoading) {
      return (
        <div ref={containerRef} className="flex gap-5 p-6">
          {Array.from({ length: columnCount }).map((_, colIndex) => (
            <div key={colIndex} className="flex flex-1 flex-col gap-5">
              {Array.from({ length: 3 }).map((_, i) => (
                <div
                  key={i}
                  className="rounded-lg bg-surface-active"
                  style={{ height: `${skeletonHeights[(colIndex * 3 + i) % skeletonHeights.length]}px` }}
                >
                  <div className="h-full animate-pulse rounded-lg bg-surface-active" />
                </div>
              ))}
            </div>
          ))}
        </div>
      )
    }

    if (filteredAssets.length === 0) {
      if (folderItems.length > 0) {
        return (
          <div ref={containerRef} className="p-6">
            <div className="grid gap-5" style={folderGridStyle}>
              {folderItems.map((item) => (
                <AssetFolderCard
                  key={item.category.id}
                  category={item.category}
                  assetCount={item.assetCount}
                  onOpen={handleOpenFolder}
                />
              ))}
            </div>
          </div>
        )
      }

      return (
        <div ref={containerRef} className="flex h-full items-center justify-center">
          <div className="text-center">
            <p className="text-muted-foreground">{t('asset.noAssets')}</p>
          </div>
        </div>
      )
    }

    return (
      <div ref={containerRef} className="p-6">
        {folderItems.length > 0 && (
          <div className="mb-6 grid gap-5" style={folderGridStyle}>
            {folderItems.map((item) => (
              <AssetFolderCard
                key={item.category.id}
                category={item.category}
                assetCount={item.assetCount}
                onOpen={handleOpenFolder}
              />
            ))}
          </div>
        )}

        {filteredAssets.length > 0 && (
          <div className="flex gap-5">
            {columns.map((column, colIndex) => (
              <div key={colIndex} className="flex flex-1 flex-col gap-5">
                {column.map((asset) => (
                  <AssetCard
                    key={asset.id}
                    asset={asset}
                    ref={(el) => registerCardRef(asset.id, el)}
                    onClick={() => onImageClick?.(asset)}
                    onDoubleClick={() => onImageDoubleClick?.(asset)}
                    onView={() => onView?.(asset)}
                    onContextMenu={(e) => onImageContextMenu?.(e, asset)}
                    isBatchMode={isBatchMode}
                  />
                ))}
              </div>
            ))}
          </div>
        )}
      </div>
    )
  }
)
