/**
 * 资产库网格卡片视图
 *
 * 与瀑布流并存的第二种排布：等宽等高的规整卡片（方形缩略图 + 标题栏），
 * 用 react-window 虚拟滚动，只渲染可见区域，适合大量资产的浏览。
 */

import {
  forwardRef,
  useCallback,
  useImperativeHandle,
  useMemo,
  useRef
} from 'react'
import { useTranslation } from 'react-i18next'
import { Grid, useGridRef, type CellComponentProps } from 'react-window'
import { useAssetStore, type AssetGalleryItem } from '@/stores/useAssetStore'
import { useElementSize } from '@/hooks/useElementSize'
import { AssetCard } from './AssetCard'
import { AssetFolderCard } from './AssetFolderCard'
import type { Asset } from '@/mocks/asset'
import type { AssetMasonryGridRef } from './AssetMasonryGrid'

interface AssetGridViewProps {
  onImageClick?: (asset: Asset) => void
  onImageDoubleClick?: (asset: Asset) => void
  /** 卡片上的「查看」入口，进入影院模式 */
  onView?: (asset: Asset) => void
  onImageContextMenu?: (e: React.MouseEvent, asset: Asset) => void
}

interface CellData {
  items: Asset[]
  columnCount: number
  isBatchMode: boolean
  onImageClick?: (asset: Asset) => void
  onImageDoubleClick?: (asset: Asset) => void
  onView?: (asset: Asset) => void
  onImageContextMenu?: (e: React.MouseEvent, asset: Asset) => void
  registerCardRef: (id: string, el: HTMLDivElement | null) => void
}

const GAP = 12
const LABEL_HEIGHT = 34

export const AssetGridView = forwardRef<AssetMasonryGridRef, AssetGridViewProps>(
  function AssetGridView({ onImageClick, onImageDoubleClick, onView, onImageContextMenu }, ref) {
    const { t } = useTranslation()
    const {
      isLoading,
      getGalleryItems,
      thumbnailSize,
      isBatchMode,
      setSelectedCategoryId,
      clearSelection,
      setBatchMode
    } = useAssetStore()

    const cardRefs = useRef<Map<string, HTMLDivElement>>(new Map())
    const gridRef = useGridRef(null)
    const [measureRef, size] = useElementSize<HTMLDivElement>()

    useImperativeHandle(ref, () => ({
      getCardRefs: () => cardRefs.current
    }))

    const galleryItems = getGalleryItems()

    const folderItems = useMemo(
      () =>
        galleryItems.filter(
          (item): item is Extract<AssetGalleryItem, { kind: 'folder' }> => item.kind === 'folder'
        ),
      [galleryItems]
    )

    const assets = useMemo(
      () =>
        galleryItems
          .filter(
            (item): item is Extract<AssetGalleryItem, { kind: 'asset' }> => item.kind === 'asset'
          )
          .map((item) => item.asset),
      [galleryItems]
    )

    const columnCount = useMemo(() => {
      if (size.width <= 0) return 1
      return Math.max(2, Math.floor((size.width + GAP) / (thumbnailSize + GAP)))
    }, [size.width, thumbnailSize])

    // 列宽均分：每格左右各留半个间距，卡片尺寸因此完全一致
    const columnWidth = useMemo(
      () => Math.floor(size.width / columnCount),
      [size.width, columnCount]
    )

    // 缩略图为正方形，卡片高度 = 缩略图边长 + 标题栏
    const rowHeight = useMemo(() => columnWidth - GAP + LABEL_HEIGHT, [columnWidth])

    const registerCardRef = useCallback((id: string, el: HTMLDivElement | null) => {
      if (el) {
        cardRefs.current.set(id, el)
      } else {
        cardRefs.current.delete(id)
      }
    }, [])

    const handleOpenFolder = useCallback((categoryId: string) => {
      clearSelection()
      setBatchMode(false)
      setSelectedCategoryId(categoryId)
    }, [clearSelection, setBatchMode, setSelectedCategoryId])

    const cellData: CellData = useMemo(() => ({
      items: assets,
      columnCount,
      isBatchMode,
      onImageClick,
      onImageDoubleClick,
      onView,
      onImageContextMenu,
      registerCardRef
    }), [assets, columnCount, isBatchMode, onImageClick, onImageDoubleClick, onView, onImageContextMenu, registerCardRef])

    const CellComponent = useCallback(({ columnIndex, rowIndex, style }: CellComponentProps<CellData>) => {
      const index = rowIndex * cellData.columnCount + columnIndex
      if (index >= cellData.items.length) return null

      const asset = cellData.items[index]

      return (
        <div
          style={{
            ...style,
            paddingLeft: GAP / 2,
            paddingRight: GAP / 2,
            paddingTop: GAP / 2,
            paddingBottom: GAP / 2
          }}
        >
          <div className="size-full">
            <AssetCard
              variant="grid"
              asset={asset}
              ref={(el) => cellData.registerCardRef(asset.id, el)}
              isBatchMode={cellData.isBatchMode}
              onClick={() => cellData.onImageClick?.(asset)}
              onDoubleClick={() => cellData.onImageDoubleClick?.(asset)}
              onView={() => cellData.onView?.(asset)}
              onContextMenu={(e) => cellData.onImageContextMenu?.(e, asset)}
            />
          </div>
        </div>
      )
    }, [cellData])

    if (isLoading) {
      return (
        <div ref={measureRef} className="flex min-h-0 flex-1 flex-wrap content-start gap-3 p-3">
          {Array.from({ length: 12 }).map((_, index) => (
            <div
              key={index}
              className="animate-pulse rounded-lg bg-surface-active"
              style={{ width: thumbnailSize, height: thumbnailSize + LABEL_HEIGHT }}
            />
          ))}
        </div>
      )
    }

    if (assets.length === 0 && folderItems.length === 0) {
      return (
        <div ref={measureRef} className="flex min-h-0 flex-1 items-center justify-center">
          <p className="text-muted-foreground">{t('asset.noAssets')}</p>
        </div>
      )
    }

    const isMeasured = size.width > 0 && size.height > 0

    return (
      <div className="flex min-h-0 flex-1 flex-col">
        {folderItems.length > 0 && (
          <div className="grid shrink-0 grid-cols-[repeat(auto-fill,minmax(180px,1fr))] gap-3 p-3 pb-0">
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

        <div ref={measureRef} className="min-h-0 min-w-0 flex-1 p-3">
          {isMeasured && assets.length > 0 && (
            <Grid
              gridRef={gridRef}
              columnCount={columnCount}
              columnWidth={columnWidth}
              rowCount={Math.ceil(assets.length / columnCount)}
              rowHeight={rowHeight}
              defaultHeight={size.height}
              defaultWidth={size.width}
              overscanCount={2}
              cellComponent={CellComponent}
              cellProps={cellData}
              className="scrollbar-thin"
              style={{ overflowX: 'hidden' }}
            />
          )}
        </div>
      </div>
    )
  }
)

export default AssetGridView
