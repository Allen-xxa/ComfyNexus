/**
 * 卡片网格组件
 */

import { useCallback, useRef, useImperativeHandle, forwardRef } from 'react'
import { PromptCard } from './PromptCard'
import { useTranslation } from 'react-i18next'
import type { Prompt } from '@/stores/usePromptStore'

export interface PromptGridRef {
  getCardRefs: () => Map<string, HTMLDivElement>
}

interface PromptGridProps {
  prompts: Prompt[]
  selectedPromptIds: string[]
  isBatchMode: boolean
  activePromptId?: string | null
  onSelectPrompt: (id: string) => void
  onActivatePrompt?: (prompt: Prompt) => void
  onEditPrompt: (prompt: Prompt) => void
  onCopyPrompt: (text: string, type: 'positive' | 'negative') => void
  onToggleFavorite: (id: string) => void
  onDeletePrompt: (id: string) => void
  onHoverPrompt?: (prompt: Prompt | null) => void
}

export const PromptGrid = forwardRef<PromptGridRef, PromptGridProps>(function PromptGrid(
  {
    prompts,
    selectedPromptIds,
    isBatchMode,
    activePromptId,
    onSelectPrompt,
    onActivatePrompt,
    onEditPrompt,
    onCopyPrompt,
    onToggleFavorite,
    onDeletePrompt,
    onHoverPrompt
  },
  ref
) {
  const { t } = useTranslation()
  const cardRefsRef = useRef<Map<string, HTMLDivElement>>(new Map())

  useImperativeHandle(ref, () => ({
    getCardRefs: () => cardRefsRef.current
  }), [])

  const setCardRef = useCallback((id: string) => (el: HTMLDivElement | null) => {
    if (el) {
      cardRefsRef.current.set(id, el)
    } else {
      cardRefsRef.current.delete(id)
    }
  }, [])

  const handleSelect = useCallback((id: string) => {
    onSelectPrompt(id)
  }, [onSelectPrompt])

  const handleEdit = useCallback((prompt: Prompt) => {
    onEditPrompt(prompt)
  }, [onEditPrompt])

  const handleCopy = useCallback((text: string, type: 'positive' | 'negative') => {
    onCopyPrompt(text, type)
  }, [onCopyPrompt])

  const handleToggleFavorite = useCallback((id: string) => {
    onToggleFavorite(id)
  }, [onToggleFavorite])

  const handleDelete = useCallback((id: string) => {
    onDeletePrompt(id)
  }, [onDeletePrompt])

  const handleHover = useCallback((prompt: Prompt | null) => {
    onHoverPrompt?.(prompt)
  }, [onHoverPrompt])

  if (prompts.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center">
        <p className="text-muted-foreground">{t('prompt.card.noPrompts')}</p>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-[repeat(auto-fit,minmax(400px,1fr))] gap-4">
      {prompts.map((prompt) => (
        <PromptCard
          key={prompt.id}
          ref={setCardRef(prompt.id)}
          prompt={prompt}
          isSelected={selectedPromptIds.includes(prompt.id)}
          isBatchMode={isBatchMode}
          isActive={activePromptId === prompt.id}
          selectedPromptIds={selectedPromptIds}
          onSelect={handleSelect}
          onActivate={onActivatePrompt}
          onEdit={handleEdit}
          onCopy={handleCopy}
          onToggleFavorite={handleToggleFavorite}
          onDelete={handleDelete}
          onHover={handleHover}
        />
      ))}
    </div>
  )
})
