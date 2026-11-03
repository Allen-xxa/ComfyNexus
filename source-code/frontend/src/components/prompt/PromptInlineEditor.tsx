/**
 * 提示词内联编辑器
 *
 * 详情面板里的编辑态表单，字段与原先的弹窗编辑器一致，但不再套 Dialog——
 * 直接在右侧面板里改，省掉「打开弹窗 → 改 → 保存 → 关闭」的往返。
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { Camera, Loader2, X } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Textarea } from '@/components/ui/Textarea'
import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/NativeSelect'
import {
  EMPTY_PROMPT_PARAMS,
  usePromptStore,
  type Prompt,
  type PromptCategory,
  type PromptInput,
  type PromptParams
} from '@/stores/usePromptStore'
import { useTranslation } from 'react-i18next'

interface PromptInlineEditorProps {
  initial: Prompt | null
  categories: PromptCategory[]
  onSave: (data: PromptInput) => Promise<boolean>
  onCancel: () => void
}

interface FormData {
  name: string
  positivePrompt: string
  negativePrompt: string
  previewImage: string
  remark: string
  categoryId: string
  params: PromptParams
}

const emptyForm = (categoryId = ''): FormData => ({
  name: '',
  positivePrompt: '',
  negativePrompt: '',
  previewImage: '',
  remark: '',
  categoryId,
  params: { ...EMPTY_PROMPT_PARAMS }
})

export function PromptInlineEditor({
  initial,
  categories,
  onSave,
  onCancel
}: PromptInlineEditorProps) {
  const { t } = useTranslation()
  const uploadImage = usePromptStore((state) => state.uploadImage)

  const availableCategories = categories.filter((c) => c.id !== 'all' && c.id !== 'favorites')
  const defaultCategoryId = availableCategories[0]?.id ?? ''

  const [formData, setFormData] = useState<FormData>(() => emptyForm(defaultCategoryId))
  const [tagsInput, setTagsInput] = useState('')
  const [isUploading, setIsUploading] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (initial) {
      setFormData({
        name: initial.name,
        positivePrompt: initial.positivePrompt,
        negativePrompt: initial.negativePrompt,
        previewImage: initial.previewImage,
        remark: initial.remark,
        categoryId: initial.categoryId,
        params: { ...EMPTY_PROMPT_PARAMS, ...(initial.params || {}) }
      })
      setTagsInput(initial.tags.join(', '))
    } else {
      setFormData(emptyForm(defaultCategoryId))
      setTagsInput('')
    }
    // 只在切换目标时重置表单，分类列表变化不应该冲掉正在编辑的内容
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initial?.id])

  const updateField = useCallback(<K extends keyof FormData>(field: K, value: FormData[K]) => {
    setFormData((prev) => ({ ...prev, [field]: value }))
  }, [])

  const updateParam = useCallback(<K extends keyof PromptParams>(field: K, value: PromptParams[K]) => {
    setFormData((prev) => ({ ...prev, params: { ...prev.params, [field]: value } }))
  }, [])

  /** 数字输入框：留空视为"不填"，写入 null */
  const handleNumberParam = useCallback(
    (field: 'steps' | 'cfg' | 'seed' | 'width' | 'height') =>
      (e: React.ChangeEvent<HTMLInputElement>) => {
        const raw = e.target.value.trim()
        updateParam(field, raw === '' ? null : (Number(raw) as never))
      },
    [updateParam]
  )

  const handleImageSelect = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    if (file.size > 5 * 1024 * 1024) {
      toast.error(t('prompt.toast.imageSizeExceeded'))
      return
    }
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
      toast.error(t('prompt.toast.imageFormatInvalid'))
      return
    }

    setIsUploading(true)
    const reader = new FileReader()
    reader.onload = async () => {
      const imagePath = await uploadImage(reader.result as string, file.name)
      if (imagePath) {
        updateField('previewImage', imagePath)
        toast.success(t('prompt.toast.imageUploadSuccess'))
      } else {
        toast.error(t('prompt.toast.imageUploadFailed'))
      }
      setIsUploading(false)
    }
    reader.onerror = () => {
      toast.error(t('prompt.toast.imageReadFailed'))
      setIsUploading(false)
    }
    reader.readAsDataURL(file)

    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }, [uploadImage, updateField, t])

  const handleSave = useCallback(async () => {
    if (!formData.categoryId || formData.categoryId === 'all' || formData.categoryId === 'favorites') {
      toast.error(t('prompt.toast.selectCategory'))
      return
    }
    setIsSaving(true)
    try {
      await onSave({
        ...formData,
        tags: tagsInput.split(',').map((tag) => tag.trim()).filter(Boolean)
      })
    } finally {
      setIsSaving(false)
    }
  }, [formData, tagsInput, onSave, t])

  const categoryOptions = availableCategories.flatMap((cat) => {
    const options = [{ value: cat.id, label: cat.name }]
    cat.children?.forEach((child) => {
      options.push({ value: child.id, label: `　${child.name}` })
    })
    return options
  })

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 space-y-5 overflow-y-auto p-5">
        <div className="flex gap-4">
          <input
            ref={fileInputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            className="hidden"
            onChange={handleImageSelect}
          />
          {formData.previewImage ? (
            <div className="relative h-32 w-24 flex-shrink-0 overflow-hidden rounded-lg border border-border-subtle bg-muted">
              <img
                src={formData.previewImage}
                alt={t('prompt.editor.uploadPreview')}
                className="size-full object-cover"
              />
              <Button
                variant="ghost"
                size="icon"
                className="absolute right-0.5 top-0.5 size-6 rounded-full bg-background/80 text-muted-foreground hover:bg-danger hover:text-primary-foreground"
                onClick={() => updateField('previewImage', '')}
              >
                <X className="size-3.5" />
              </Button>
            </div>
          ) : (
            <Button
              variant="ghost"
              disabled={isUploading}
              className="flex h-32 w-24 flex-shrink-0 cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed border-primary/50 bg-muted text-center transition-colors hover:bg-primary/5 disabled:opacity-50"
              onClick={() => fileInputRef.current?.click()}
            >
              {isUploading ? (
                <Loader2 className="size-5 animate-spin text-primary" />
              ) : (
                <>
                  <Camera className="mb-1 size-5 text-primary" />
                  <span className="text-[10px] leading-tight text-muted-foreground">
                    {t('prompt.editor.uploadPreview')}
                  </span>
                </>
              )}
            </Button>
          )}

          <div className="flex-1 space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor="inline-name">{t('prompt.editor.nameLabel')}</Label>
              <Input
                id="inline-name"
                value={formData.name}
                onChange={(e) => updateField('name', e.target.value)}
                placeholder={t('prompt.editor.namePlaceholder')}
              />
            </div>
            <div className="flex gap-3">
              <div className="flex-1 space-y-1.5">
                <Label>{t('prompt.editor.categoryLabel')}</Label>
                <NativeSelect
                  value={formData.categoryId}
                  onValueChange={(value) => updateField('categoryId', value)}
                >
                  {categoryOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </NativeSelect>
              </div>
              <div className="flex-1 space-y-1.5">
                <Label>{t('prompt.editor.tagsLabel')}</Label>
                <Input
                  value={tagsInput}
                  onChange={(e) => setTagsInput(e.target.value)}
                  placeholder={t('prompt.editor.tagsPlaceholder')}
                />
              </div>
            </div>
          </div>
        </div>

        <div className="space-y-1.5">
          <Label className="text-success">{t('prompt.editor.positiveLabel')}</Label>
          <Textarea
            value={formData.positivePrompt}
            onChange={(e) => updateField('positivePrompt', e.target.value)}
            placeholder={t('prompt.editor.positivePlaceholder')}
            rows={4}
            className="font-mono text-[13px] leading-relaxed"
          />
        </div>

        <div className="space-y-1.5">
          <Label className="text-danger">{t('prompt.editor.negativeLabel')}</Label>
          <Textarea
            value={formData.negativePrompt}
            onChange={(e) => updateField('negativePrompt', e.target.value)}
            placeholder={t('prompt.editor.negativePlaceholder')}
            rows={2}
            className="font-mono text-[13px] leading-relaxed"
          />
        </div>

        <div className="space-y-1.5">
          <Label>{t('prompt.editor.remarkLabel')}</Label>
          <Textarea
            value={formData.remark}
            onChange={(e) => updateField('remark', e.target.value)}
            placeholder={t('prompt.editor.remarkPlaceholder')}
            rows={2}
          />
        </div>

        <div className="rounded-lg border border-border-subtle bg-muted/40 p-4">
          <div className="mb-3 flex items-baseline justify-between">
            <Label className="text-sm font-medium">{t('prompt.editor.paramsTitle')}</Label>
            <span className="text-[11px] text-muted-foreground">{t('prompt.editor.paramsHint')}</span>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="inline-model">{t('prompt.editor.modelLabel')}</Label>
              <Input
                id="inline-model"
                value={formData.params.model}
                onChange={(e) => updateParam('model', e.target.value)}
                placeholder={t('prompt.editor.modelPlaceholder')}
                className="font-mono text-xs"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="inline-sampler">{t('prompt.editor.samplerLabel')}</Label>
              <Input
                id="inline-sampler"
                value={formData.params.sampler}
                onChange={(e) => updateParam('sampler', e.target.value)}
                placeholder={t('prompt.editor.samplerPlaceholder')}
                className="font-mono text-xs"
              />
            </div>
          </div>

          <div className="mt-3 grid grid-cols-4 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="inline-steps">{t('prompt.editor.stepsLabel')}</Label>
              <Input
                id="inline-steps"
                type="number"
                min={1}
                value={formData.params.steps ?? ''}
                onChange={handleNumberParam('steps')}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="inline-cfg">{t('prompt.editor.cfgLabel')}</Label>
              <Input
                id="inline-cfg"
                type="number"
                step="0.1"
                min={0}
                value={formData.params.cfg ?? ''}
                onChange={handleNumberParam('cfg')}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="inline-width">{t('prompt.editor.widthLabel')}</Label>
              <Input
                id="inline-width"
                type="number"
                min={1}
                value={formData.params.width ?? ''}
                onChange={handleNumberParam('width')}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="inline-height">{t('prompt.editor.heightLabel')}</Label>
              <Input
                id="inline-height"
                type="number"
                min={1}
                value={formData.params.height ?? ''}
                onChange={handleNumberParam('height')}
              />
            </div>
          </div>

          <div className="mt-3 grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="inline-seed">{t('prompt.editor.seedLabel')}</Label>
              <Input
                id="inline-seed"
                type="number"
                min={0}
                value={formData.params.seed ?? ''}
                onChange={handleNumberParam('seed')}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="inline-scheduler">{t('prompt.editor.schedulerLabel')}</Label>
              <Input
                id="inline-scheduler"
                value={formData.params.scheduler}
                onChange={(e) => updateParam('scheduler', e.target.value)}
                placeholder={t('prompt.editor.schedulerPlaceholder')}
                className="font-mono text-xs"
              />
            </div>
          </div>

          <div className="mt-3 space-y-1.5">
            <div className="flex items-baseline justify-between gap-3">
              <Label htmlFor="inline-workflow">{t('prompt.editor.workflowLabel')}</Label>
              <span className="shrink-0 text-[11px] text-muted-foreground">
                {t('prompt.editor.workflowHint')}
              </span>
            </div>
            <Input
              id="inline-workflow"
              value={formData.params.workflowName}
              onChange={(e) => updateParam('workflowName', e.target.value)}
              placeholder={t('prompt.editor.workflowPlaceholder')}
              className="font-mono text-xs"
            />
            {formData.params.workflowPath && (
              <p
                className="truncate font-mono text-[10px] text-muted-foreground"
                title={formData.params.workflowPath}
              >
                {formData.params.workflowPath}
              </p>
            )}
          </div>
        </div>
      </div>

      <div className="flex flex-shrink-0 items-center justify-end gap-2 border-t border-border-subtle bg-surface px-5 py-3">
        <Button variant="outline" onClick={onCancel} disabled={isSaving}>
          {t('prompt.editor.cancel')}
        </Button>
        <Button onClick={handleSave} disabled={isSaving}>
          {isSaving ? <Loader2 className="size-4 animate-spin" /> : null}
          {t('prompt.editor.save')}
        </Button>
      </div>
    </div>
  )
}
