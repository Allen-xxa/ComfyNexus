/**
 * 提示词详情面板
 *
 * 右侧常驻面板：完整展示正向/反向提示词与生成参数，不再用弹框。
 * 编辑与新建也在这个面板内完成（切换成表单态）。
 */

import { useCallback, useState } from 'react'
import {
  Check,
  Copy,
  Pencil,
  Plus,
  Star,
  Trash2,
  Workflow,
  ImageOff
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/Button'
import { PromptInlineEditor } from './PromptInlineEditor'
import { useTranslation } from 'react-i18next'
import type {
  Prompt,
  PromptCategory,
  PromptInput,
  PromptParams
} from '@/stores/usePromptStore'

export type PromptPanelMode = 'view' | 'edit' | 'create'

interface PromptDetailPanelProps {
  prompt: Prompt | null
  categories: PromptCategory[]
  mode: PromptPanelMode
  onStartCreate: () => void
  onStartEdit: (prompt: Prompt) => void
  onCancelEdit: () => void
  onSave: (data: PromptInput) => Promise<boolean>
  onCopy: (text: string, type: 'positive' | 'negative') => void
  onToggleFavorite: (id: string) => void
  onDelete: (prompt: Prompt) => void
}

/** 可复制的提示词区块 */
function PromptBlock({
  label,
  text,
  tone,
  emptyText,
  onCopy
}: {
  label: string
  text: string
  tone: 'positive' | 'negative'
  emptyText: string
  onCopy: (text: string, type: 'positive' | 'negative') => void
}) {
  const { t } = useTranslation()
  const [copied, setCopied] = useState(false)

  const handleCopy = useCallback(() => {
    if (!text) return
    onCopy(text, tone)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }, [text, tone, onCopy])

  return (
    <section className="rounded-lg border border-border-subtle bg-card">
      <header className="flex items-center gap-2 border-b border-border-subtle px-3.5 py-2">
        <span
          className={cn(
            'size-1.5 rounded-full',
            tone === 'positive' ? 'bg-success' : 'bg-danger'
          )}
        />
        <h3 className="text-xs font-semibold text-foreground">{label}</h3>
        {text && (
          <Button
            variant="ghost"
            size="sm"
            className="ml-auto h-6 gap-1 px-2 text-[11px] text-muted-foreground hover:text-foreground"
            onClick={handleCopy}
          >
            {copied ? <Check className="size-3" /> : <Copy className="size-3" />}
            {copied ? t('prompt.detail.copied') : t('prompt.detail.copy')}
          </Button>
        )}
      </header>
      <div className="px-3.5 py-3">
        {text ? (
          <p className="whitespace-pre-wrap break-words font-mono text-[12.5px] leading-relaxed text-foreground">
            {text}
          </p>
        ) : (
          <p className="text-xs italic text-muted-foreground/70">{emptyText}</p>
        )}
      </div>
    </section>
  )
}

/** 参数表单项 */
function ParamItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-md bg-muted/50 px-2.5 py-1.5">
      <dt className="text-[10px] uppercase tracking-wide text-muted-foreground/80">{label}</dt>
      <dd className="truncate font-mono text-[12px] text-foreground" title={value}>
        {value}
      </dd>
    </div>
  )
}

export function PromptDetailPanel({
  prompt,
  categories,
  mode,
  onStartCreate,
  onStartEdit,
  onCancelEdit,
  onSave,
  onCopy,
  onToggleFavorite,
  onDelete
}: PromptDetailPanelProps) {
  const { t } = useTranslation()
  const [paramsCopied, setParamsCopied] = useState(false)

  const handleCopyParams = useCallback(() => {
    if (!prompt) return
    const params = prompt.params
    const payload: Record<string, unknown> = {}
    const entries: [string, unknown][] = [
      ['model', params?.model],
      ['sampler', params?.sampler],
      ['scheduler', params?.scheduler],
      ['steps', params?.steps],
      ['cfg', params?.cfg],
      ['seed', params?.seed],
      ['width', params?.width],
      ['height', params?.height],
      ['duration', params?.duration],
      ['workflow', params?.workflowName]
    ]
    entries.forEach(([key, value]) => {
      if (value !== null && value !== undefined && value !== '') payload[key] = value
    })
    navigator.clipboard.writeText(JSON.stringify(payload, null, 2))
    setParamsCopied(true)
    setTimeout(() => setParamsCopied(false), 1500)
  }, [prompt])

  if (mode === 'create' || mode === 'edit') {
    return (
      <div className="flex h-full flex-col bg-surface">
        <header className="flex flex-shrink-0 items-center gap-2 border-b border-border-subtle px-5 py-3">
          <h2 className="text-sm font-semibold text-foreground">
            {mode === 'create' ? t('prompt.editor.addTitle') : t('prompt.editor.editTitle')}
          </h2>
        </header>
        <div className="min-h-0 flex-1">
          <PromptInlineEditor
            initial={mode === 'edit' ? prompt : null}
            categories={categories}
            onSave={onSave}
            onCancel={onCancelEdit}
          />
        </div>
      </div>
    )
  }

  if (!prompt) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 bg-surface px-8 text-center">
        <div className="flex size-12 items-center justify-center rounded-full bg-muted">
          <ImageOff className="size-5 text-muted-foreground/60" />
        </div>
        <div>
          <p className="text-sm font-medium text-foreground">{t('prompt.detail.emptyTitle')}</p>
          <p className="mt-1 text-xs text-muted-foreground">{t('prompt.detail.emptyHint')}</p>
        </div>
        <Button size="sm" onClick={onStartCreate}>
          <Plus className="size-4" />
          {t('prompt.toolbar.addPrompt')}
        </Button>
      </div>
    )
  }

  const params: PromptParams = prompt.params || ({} as PromptParams)
  const categoryName = (() => {
    const walk = (list: PromptCategory[]): string | null => {
      for (const item of list) {
        if (item.id === prompt.categoryId) return item.name
        if (item.children) {
          const found = walk(item.children)
          if (found) return found
        }
      }
      return null
    }
    return walk(categories) || t('prompt.category.all')
  })()

  const hasParams = Boolean(
    params.model || params.sampler || params.scheduler || params.steps != null ||
    params.cfg != null || params.seed != null || params.width != null || params.height != null
  )
  const sizeText = params.width && params.height ? `${params.width} × ${params.height}` : ''
  const durationText = params.duration ? `${params.duration}s` : ''

  return (
    <div className="flex h-full flex-col bg-surface">
      <header className="flex flex-shrink-0 items-start gap-4 border-b border-border-subtle px-5 py-4">
        <div className="relative size-20 flex-shrink-0 overflow-hidden rounded-lg border border-border-subtle bg-muted">
          {prompt.previewImage ? (
            <img
              src={prompt.previewImage}
              alt={prompt.name}
              className="size-full object-cover"
              draggable={false}
            />
          ) : (
            <div className="flex size-full items-center justify-center text-[10px] text-muted-foreground/60">
              {t('prompt.card.noPreview')}
            </div>
          )}
          {params.assetType === 'video' && (
            <span className="absolute bottom-0 left-0 rounded-tr bg-black/60 px-1 text-[9px] font-medium text-white">
              VIDEO
            </span>
          )}
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-start gap-2">
            <h2 className="min-w-0 flex-1 break-words text-base font-semibold text-foreground">
              {prompt.name}
            </h2>
            <div className="flex flex-shrink-0 items-center gap-1">
              <Button
                variant="ghost"
                size="sm"
                className="h-7 w-7 p-0"
                title={t('prompt.detail.favorite')}
                onClick={() => onToggleFavorite(prompt.id)}
              >
                <Star
                  className={cn(
                    'size-4',
                    prompt.isFavorite ? 'fill-warning text-warning' : 'text-muted-foreground'
                  )}
                />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="h-7 w-7 p-0"
                title={t('prompt.detail.edit')}
                onClick={() => onStartEdit(prompt)}
              >
                <Pencil className="size-4 text-muted-foreground" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="h-7 w-7 p-0 hover:bg-danger/10"
                title={t('prompt.detail.delete')}
                onClick={() => onDelete(prompt)}
              >
                <Trash2 className="size-4 text-muted-foreground hover:text-danger" />
              </Button>
            </div>
          </div>

          <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-[11px]">
            <span className="rounded bg-muted px-1.5 py-0.5 text-muted-foreground">
              {categoryName}
            </span>
            {prompt.tags.map((tag) => (
              <span
                key={tag}
                className="rounded border border-border-subtle px-1.5 py-0.5 text-muted-foreground"
              >
                {tag}
              </span>
            ))}
          </div>

          <p className="mt-2 text-[11px] text-muted-foreground/70">
            {t('prompt.detail.updatedAt')} {prompt.updatedAt?.replace('T', ' ').slice(0, 16)}
          </p>
        </div>
      </header>

      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4">
        <PromptBlock
          label={t('prompt.detail.positive')}
          text={prompt.positivePrompt}
          tone="positive"
          emptyText={t('prompt.detail.noPositive')}
          onCopy={onCopy}
        />

        <PromptBlock
          label={t('prompt.detail.negative')}
          text={prompt.negativePrompt}
          tone="negative"
          emptyText={t('prompt.detail.noNegative')}
          onCopy={onCopy}
        />

        <section className="rounded-lg border border-border-subtle bg-card">
          <header className="flex items-center gap-2 border-b border-border-subtle px-3.5 py-2">
            <h3 className="text-xs font-semibold text-foreground">{t('prompt.detail.params')}</h3>
            {hasParams && (
              <Button
                variant="ghost"
                size="sm"
                className="ml-auto h-6 gap-1 px-2 text-[11px] text-muted-foreground hover:text-foreground"
                onClick={handleCopyParams}
              >
                {paramsCopied ? <Check className="size-3" /> : <Copy className="size-3" />}
                {paramsCopied ? t('prompt.detail.copied') : t('prompt.detail.copyParams')}
              </Button>
            )}
          </header>
          <div className="px-3.5 py-3">
            {hasParams ? (
              <dl className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                {params.model && (
                  <ParamItem label={t('prompt.editor.modelLabel')} value={params.model} />
                )}
                {params.sampler && (
                  <ParamItem label={t('prompt.editor.samplerLabel')} value={params.sampler} />
                )}
                {params.scheduler && (
                  <ParamItem label={t('prompt.editor.schedulerLabel')} value={params.scheduler} />
                )}
                {params.steps != null && (
                  <ParamItem label={t('prompt.editor.stepsLabel')} value={String(params.steps)} />
                )}
                {params.cfg != null && (
                  <ParamItem label={t('prompt.editor.cfgLabel')} value={String(params.cfg)} />
                )}
                {params.seed != null && (
                  <ParamItem label={t('prompt.editor.seedLabel')} value={String(params.seed)} />
                )}
                {sizeText && (
                  <ParamItem
                    label={`${t('prompt.editor.widthLabel')} × ${t('prompt.editor.heightLabel')}`}
                    value={sizeText}
                  />
                )}
                {durationText && (
                  <ParamItem label={t('prompt.detail.duration')} value={durationText} />
                )}
              </dl>
            ) : (
              <p className="text-xs italic text-muted-foreground/70">{t('prompt.detail.noParams')}</p>
            )}
          </div>
        </section>

        <section className="rounded-lg border border-border-subtle bg-card">
          <header className="flex items-center gap-2 border-b border-border-subtle px-3.5 py-2">
            <Workflow className="size-3.5 text-muted-foreground" />
            <h3 className="text-xs font-semibold text-foreground">{t('prompt.detail.workflow')}</h3>
          </header>
          <div className="px-3.5 py-3">
            {params.workflowName || params.workflowPath ? (
              <div className="space-y-1">
                {params.workflowName && (
                  <p className="break-all font-mono text-[12px] text-foreground">
                    {params.workflowName}
                  </p>
                )}
                {params.workflowPath && (
                  <p className="break-all font-mono text-[10px] text-muted-foreground">
                    {params.workflowPath}
                  </p>
                )}
              </div>
            ) : (
              <p className="text-xs italic text-muted-foreground/70">{t('prompt.detail.noWorkflow')}</p>
            )}
          </div>
        </section>

        {prompt.remark && (
          <section className="rounded-lg border border-border-subtle bg-card">
            <header className="border-b border-border-subtle px-3.5 py-2">
              <h3 className="text-xs font-semibold text-foreground">{t('prompt.detail.remark')}</h3>
            </header>
            <p className="whitespace-pre-wrap break-words px-3.5 py-3 text-[12.5px] leading-relaxed text-foreground">
              {prompt.remark}
            </p>
          </section>
        )}
      </div>
    </div>
  )
}
