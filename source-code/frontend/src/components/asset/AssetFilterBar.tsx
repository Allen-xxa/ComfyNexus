/**
 * 资产库二级筛选区
 *
 * 顶部工具栏负责"怎么看"（视图、尺寸、刷新、导入），这一行负责"看哪些"：
 * 类型、是否含工作流、星级下限、时间区间、模型多选、排序字段与方向。
 * 筛选结果同时驱动瀑布流、网格和影院模式的底部轨道，三者共用 getFilteredAssets。
 */

import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  ArrowDownAZ,
  ArrowUpAZ,
  CalendarDays,
  ChevronDown,
  Cpu,
  Film,
  Image as ImageIcon,
  RotateCcw,
  Search,
  Star,
  Workflow
} from 'lucide-react'
import { Button, Input, Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Checkbox } from '@/components/ui/checkbox'
import { useAssetStore, type AssetDateFilter, type SortBy } from '@/stores/useAssetStore'
import { cn } from '@/lib/utils'

const TYPE_OPTIONS = [
  { value: 'image', icon: ImageIcon },
  { value: 'video', icon: Film }
] as const

const RATING_OPTIONS = ['all', '0', '1', '2', '3', '4', '5'] as const

const RATING_LABELS = {
  all: 'allRatings',
  '0': 'unrated',
  '1': 'min1star',
  '2': 'min2stars',
  '3': 'min3stars',
  '4': 'min4stars',
  '5': 'min5stars'
} as const

const DATE_OPTIONS: AssetDateFilter[] = ['all', 'today', 'week', 'month', 'quarter']

const SORT_OPTIONS: SortBy[] = ['createdAt', 'name', 'size', 'rating']

/** 模型串形如 `FLUX\flux2Klein9BTrue_v10Fp8.safetensors`，列表里只显示去掉目录和后缀的名字 */
const modelDisplayName = (model: string): string => {
  const base = model.split(/[\\/]/).pop() ?? model
  return base.replace(/\.(safetensors|ckpt|pt|pth|bin|pkl)$/i, '')
}

export function AssetFilterBar() {
  const { t } = useTranslation()
  const {
    typeFilter,
    toggleTypeFilter,
    onlyWithWorkflow,
    setOnlyWithWorkflow,
    modelFilter,
    toggleModelFilter,
    dateFilter,
    setDateFilter,
    ratingFilter,
    setRatingFilter,
    sortBy,
    setSortBy,
    sortDir,
    setSortDir,
    hasAttributeFilter,
    clearAttributeFilters,
    getModelOptions,
    getFilteredAssets,
    assets
  } = useAssetStore()

  const [isModelOpen, setIsModelOpen] = useState(false)
  const [modelQuery, setModelQuery] = useState('')

  const modelOptions = getModelOptions()
  const filteredCount = getFilteredAssets().length
  const filtersActive = hasAttributeFilter()

  const query = modelQuery.trim().toLowerCase()
  const visibleModelOptions = !query
    ? modelOptions
    : modelOptions.filter(
        (option) =>
          option.model.toLowerCase().includes(query) ||
          modelDisplayName(option.model).toLowerCase().includes(query)
      )

  const modelTriggerLabel = modelFilter.length === 0
    ? t('asset.filter.modelAll')
    : t('asset.filter.modelSelected', { count: modelFilter.length })

  return (
    <div className="mt-3 flex flex-wrap items-center gap-2">
      <div className="flex items-center gap-1.5">
        {TYPE_OPTIONS.map(({ value, icon: Icon }) => {
          const active = typeFilter.includes(value)
          return (
            <Button
              key={value}
              variant="ghost"
              size="sm"
              onClick={() => toggleTypeFilter(value)}
              className={cn(
                'h-auto gap-1.5 rounded-full px-3 py-1 text-xs',
                active
                  ? 'bg-primary/15 text-primary hover:bg-primary/20'
                  : 'bg-surface-active text-muted-foreground hover:text-foreground'
              )}
            >
              <Icon className="size-3.5" />
              {t(`asset.filter.types.${value}`)}
            </Button>
          )
        })}
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setOnlyWithWorkflow(!onlyWithWorkflow)}
          className={cn(
            'h-auto gap-1.5 rounded-full px-3 py-1 text-xs',
            onlyWithWorkflow
              ? 'bg-primary/15 text-primary hover:bg-primary/20'
              : 'bg-surface-active text-muted-foreground hover:text-foreground'
          )}
        >
          <Workflow className="size-3.5" />
          {t('asset.filter.withWorkflow')}
        </Button>
      </div>

      <div className="mx-1 h-5 w-px bg-border/60" />

      <Select value={dateFilter} onValueChange={(value) => setDateFilter(value as AssetDateFilter)}>
        <SelectTrigger className="h-8 w-auto gap-1 px-3">
          <CalendarDays className="size-4" />
          <SelectValue placeholder={t('asset.filter.date')} />
        </SelectTrigger>
        <SelectContent>
          {DATE_OPTIONS.map((option) => (
            <SelectItem key={option} value={option}>
              {t(`asset.filter.dateOptions.${option}`)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select value={ratingFilter} onValueChange={setRatingFilter}>
        <SelectTrigger className="h-8 w-auto gap-1 px-3">
          <Star className="size-4" />
          <SelectValue placeholder={t('asset.ratingFilter')} />
        </SelectTrigger>
        <SelectContent>
          {RATING_OPTIONS.map((option) => (
            <SelectItem key={option} value={option}>
              {t(`asset.rating.${RATING_LABELS[option]}`)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Popover open={isModelOpen} onOpenChange={setIsModelOpen}>
        <PopoverTrigger asChild>
          <Button variant="outline" size="sm" className="h-8 gap-1 px-3 text-xs font-normal">
            <Cpu className="size-4" />
            {modelTriggerLabel}
            <ChevronDown className="size-4 opacity-60" />
          </Button>
        </PopoverTrigger>
        <PopoverContent align="start" className="w-72 p-0">
          <div className="flex items-center gap-2 border-b border-border/50 px-2.5 py-2">
            <Search className="size-3.5 shrink-0 text-muted-foreground" />
            <Input
              value={modelQuery}
              onChange={(e) => setModelQuery(e.target.value)}
              placeholder={t('asset.filter.modelSearchPlaceholder')}
              className="h-7 border-0 bg-transparent px-0 shadow-none focus-visible:ring-0"
            />
          </div>
          <div className="flex items-center justify-between px-3 py-1.5">
            <span className="text-xs text-muted-foreground">
              {t('asset.filter.modelSelectedCount', {
                selected: modelFilter.length,
                total: modelOptions.length
              })}
            </span>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => [...modelFilter].forEach(toggleModelFilter)}
              disabled={modelFilter.length === 0}
              className="h-6 px-2 text-xs"
            >
              {t('asset.filter.modelClear')}
            </Button>
          </div>
          <ScrollArea className="max-h-64">
            <div className="flex flex-col gap-0.5 px-1 pb-2">
              {visibleModelOptions.map(({ model, count }) => (
                <label
                  key={model}
                  title={model}
                  className="flex cursor-pointer items-center gap-2 rounded-sm px-2 py-1.5 text-sm hover:bg-surface-hover"
                >
                  <Checkbox
                    checked={modelFilter.includes(model)}
                    onCheckedChange={() => toggleModelFilter(model)}
                  />
                  <span className="min-w-0 flex-1 truncate">{modelDisplayName(model)}</span>
                  <span className="shrink-0 font-mono text-xs text-muted-foreground">{count}</span>
                </label>
              ))}
              {visibleModelOptions.length === 0 && (
                <div className="px-3 py-4 text-center text-xs text-muted-foreground">
                  {t('asset.filter.modelEmpty')}
                </div>
              )}
            </div>
          </ScrollArea>
        </PopoverContent>
      </Popover>

      <div className="mx-1 h-5 w-px bg-border/60" />

      <Select value={sortBy} onValueChange={(value) => setSortBy(value as SortBy)}>
        <SelectTrigger className="h-8 w-auto gap-1 px-3">
          <SelectValue placeholder={t('asset.sort')} />
        </SelectTrigger>
        <SelectContent>
          {SORT_OPTIONS.map((option) => (
            <SelectItem key={option} value={option}>
              {t(`asset.sortOptions.${option}`)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <Button
        variant="outline"
        size="icon"
        onClick={() => setSortDir(sortDir === 'asc' ? 'desc' : 'asc')}
        title={t(sortDir === 'asc' ? 'asset.filter.sortAsc' : 'asset.filter.sortDesc')}
        className="size-8"
      >
        {sortDir === 'asc' ? <ArrowUpAZ className="size-4" /> : <ArrowDownAZ className="size-4" />}
      </Button>

      {filtersActive && (
        <Button
          variant="ghost"
          size="sm"
          onClick={clearAttributeFilters}
          className="h-8 gap-1.5 px-3 text-xs text-muted-foreground hover:text-foreground"
        >
          <RotateCcw className="size-3.5" />
          {t('asset.filter.clear')}
        </Button>
      )}

      <div className="ml-auto text-xs text-muted-foreground">
        {t('asset.filter.resultCount', { shown: filteredCount, total: assets.length })}
      </div>
    </div>
  )
}
