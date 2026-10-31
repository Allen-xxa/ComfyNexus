/**
 * 话题列表组件
 * 
 * 功能：
 * - 显示所有话题列表
 * - 新建话题
 * - 切换话题
 * - 删除话题
 * - 重命名话题（双击编辑）
 * 
 * 验证需求：2.1, 2.2, 2.3, 2.4
 */

import React, { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useTopicStore } from '@/stores/useTopicStore'
import { useAIStore } from '@/stores/useAIStore'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Plus, Trash2, MessageSquare, Upload, Pencil } from 'lucide-react'
import { cn } from '@/lib/utils'
import { ExportDialog } from './ExportDialog'
import { DeleteTopicDialog } from './DeleteTopicDialog'

/**
 * 话题列表组件
 */
export const TopicList: React.FC = () => {
  const { t } = useTranslation()
  const {
    topics,
    currentTopicId,
    isLoading,
    createTopic,
    deleteTopic,
    renameTopic,
    setCurrentTopicId,
    loadTopics
  } = useTopicStore()
  
  const { setCurrentTopicId: setAICurrentTopicId, loadMessages } = useAIStore()
  
  // 编辑状态
  const [editingTopicId, setEditingTopicId] = useState<string | null>(null)
  const [editingName, setEditingName] = useState('')
  
  // 导出对话框状态
  const [exportingTopicId, setExportingTopicId] = useState<string | null>(null)
  const [showExportDialog, setShowExportDialog] = useState(false)
  
  // 删除确认对话框状态
  const [deletingTopicId, setDeletingTopicId] = useState<string | null>(null)
  const [showDeleteDialog, setShowDeleteDialog] = useState(false)
  
  // 组件挂载时加载话题列表
  useEffect(() => {
    const initTopics = async () => {
      await loadTopics()
      // 加载完话题列表后，如果有当前话题，加载其消息
      const currentId = useTopicStore.getState().currentTopicId
      if (currentId) {
        // 检查 AI store 是否正在生成中（来自日志推送等场景）
        // 如果是，跳过 loadMessages 以避免覆盖 sendMessage 已添加的消息
        const aiState = useAIStore.getState()
        if (aiState.currentTopicId === currentId && (aiState.isLoading || aiState.isGenerating)) {
          console.log('[TopicList] AI 正在生成中，跳过加载消息')
          return
        }
        await loadMessages(currentId)
      }
    }
    initTopics()
    
    // 监听话题标题更新事件
    const handleTitleUpdated = ((event: CustomEvent) => {
      const { topic_id, new_title } = event.detail
      console.log('[TopicList] 收到标题更新事件:', topic_id, new_title)
      
      // 重新加载话题列表以获取最新标题
      loadTopics()
    }) as EventListener
    
    window.addEventListener('topic_title_updated', handleTitleUpdated)
    
    // 清理事件监听器
    return () => {
      window.removeEventListener('topic_title_updated', handleTitleUpdated)
    }
  }, [loadTopics, loadMessages])
  
  /**
   * 处理新建话题
   */
  const handleCreateTopic = async () => {
    const newTopic = await createTopic()
    if (newTopic) {
      // 同步到 AI Store
      setAICurrentTopicId(newTopic.id)
      // 加载新话题的消息（应该是空的）
      await loadMessages(newTopic.id)
    }
  }
  
  /**
   * 处理切换话题
   */
  const handleSelectTopic = async (topicId: string) => {
    setCurrentTopicId(topicId)
    setAICurrentTopicId(topicId)
    // 加载该话题的历史消息
    await loadMessages(topicId)
  }
  
  /**
   * 处理导出话题
   */
  const handleExportTopic = (topicId: string, e: React.MouseEvent) => {
    e.stopPropagation() // 阻止事件冒泡
    setExportingTopicId(topicId)
    setShowExportDialog(true)
  }
  
  /**
   * 处理删除话题
   */
  const handleDeleteTopic = async (topicId: string, e: React.MouseEvent) => {
    e.stopPropagation() // 阻止事件冒泡
    
    // 检查是否设置了不再提示
    const hideConfirm = sessionStorage.getItem('hideDeleteTopicConfirm') === 'true'
    
    if (hideConfirm) {
      // 直接删除，不显示对话框
      const success = await deleteTopic(topicId)
      if (success) {
        // 切换到新的当前话题并加载消息
        const newCurrentTopicId = useTopicStore.getState().currentTopicId
        if (newCurrentTopicId) {
          setAICurrentTopicId(newCurrentTopicId)
          await loadMessages(newCurrentTopicId)
        }
      }
    } else {
      // 显示删除确认对话框
      setDeletingTopicId(topicId)
      setShowDeleteDialog(true)
    }
  }
  
  /**
   * 确认删除话题
   */
  const handleConfirmDelete = async () => {
    if (!deletingTopicId) return
    
    const success = await deleteTopic(deletingTopicId)
    if (success) {
      // 切换到新的当前话题并加载消息
      const newCurrentTopicId = useTopicStore.getState().currentTopicId
      if (newCurrentTopicId) {
        setAICurrentTopicId(newCurrentTopicId)
        await loadMessages(newCurrentTopicId)
      }
    }
    
    setDeletingTopicId(null)
  }
  
  /**
   * 处理双击开始编辑
   */
  const handleDoubleClick = (topicId: string, currentName: string) => {
    setEditingTopicId(topicId)
    setEditingName(currentName)
  }
  
  /**
   * 处理重命名提交
   */
  const handleRenameSubmit = async () => {
    if (!editingTopicId || !editingName.trim()) {
      setEditingTopicId(null)
      return
    }
    
    const success = await renameTopic(editingTopicId, editingName.trim())
    if (success) {
      setEditingTopicId(null)
      setEditingName('')
    }
  }
  
  /**
   * 处理重命名取消
   */
  const handleRenameCancel = () => {
    setEditingTopicId(null)
    setEditingName('')
  }
  
  /**
   * 处理输入框按键
   */
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleRenameSubmit()
    } else if (e.key === 'Escape') {
      handleRenameCancel()
    }
  }
  
  return (
    <div className="flex h-full flex-col">
      {/* 头部：新建话题按钮 */}
      <div className="border-b border-border p-4">
        <Button
          onClick={handleCreateTopic}
          disabled={isLoading}
          className="bg-plugin-primary hover:bg-plugin-primary-dark w-full shadow-sm transition-all duration-200 hover:shadow-md"
          variant="default"
        >
          <Plus className="mr-2 size-4" />
          {t("ai.createTopic")}
        </Button>
      </div>
      
      {/* 话题列表 */}
      <ScrollArea className="flex-1">
        <div className="space-y-1 p-2">
          {topics.length === 0 ? (
            <div className="py-8 text-center text-muted-foreground">
              <MessageSquare className="mx-auto mb-2 size-12 opacity-50" />
              <p className="text-sm">{t("ai.noTopics")}</p>
              <p className="mt-1 text-xs">{t("ai.clickToCreateTopic")}</p>
            </div>
          ) : (
            topics.map((topic) => (
              <div
                key={topic.id}
                className={cn(
                  'group relative flex items-start gap-2 px-3 py-2.5 rounded-lg cursor-pointer transition-all duration-200',
                  'hover:bg-muted',
                  currentTopicId === topic.id && 'bg-plugin-primary/10 dark:bg-plugin-primary/20 border border-plugin-primary/30'
                )}
                onClick={() => handleSelectTopic(topic.id)}
                onDoubleClick={() => handleDoubleClick(topic.id, topic.name)}
              >
                {/* 话题图标 */}
                <MessageSquare className={cn(
                  "w-4 h-4 flex-shrink-0 mt-0.5",
                  currentTopicId === topic.id ? "text-plugin-primary" : "text-muted-foreground"
                )} />
                
                {/* 话题名称或编辑输入框 */}
                {editingTopicId === topic.id ? (
                  <Input
                    value={editingName}
                    onChange={(e) => setEditingName(e.target.value)}
                    onBlur={handleRenameSubmit}
                    onKeyDown={handleKeyDown}
                    className="h-6 text-sm"
                    autoFocus
                    onClick={(e) => e.stopPropagation()}
                  />
                ) : (
                  <div className="min-w-0 flex-1">
                    <p className={cn(
                      "text-sm font-medium line-clamp-2 leading-relaxed",
                      currentTopicId === topic.id ? "text-plugin-primary" : "text-foreground"
                    )}>
                      {topic.name}
                    </p>
                    {topic.message_count !== undefined && (
                      <p className="mt-0.5 text-xs text-muted-foreground">
                        {t("ai.messageCount", { count: topic.message_count })}
                      </p>
                    )}
                  </div>
                )}
                
                {/* 操作按钮（悬停时显示） */}
                {editingTopicId !== topic.id && (
                  <div className="flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                    {/* 重命名按钮：双击话题名同样可进入编辑，此处提供可见入口 */}
                    <Button
                      variant="ghost"
                      size="sm"
                      className="hover:bg-muted-foreground/10 size-6 p-0"
                      onClick={(e) => {
                        e.stopPropagation()
                        handleDoubleClick(topic.id, topic.name)
                      }}
                      title="重命名"
                    >
                      <Pencil className="text-muted-foreground size-3" />
                    </Button>
                    
                    {/* 导出按钮 */}
                    {(topic.message_count ?? 0) > 0 && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="hover:bg-blue-100 dark:hover:bg-blue-900/30 size-6 p-0"
                        onClick={(e) => handleExportTopic(topic.id, e)}
                        title={t("common.title.exportConversation")}
                      >
                        <Upload className="text-blue-600 dark:text-blue-400 size-3" />
                      </Button>
                    )}
                    
                    {/* 删除按钮 */}
                    <Button
                      variant="ghost"
                      size="sm"
                      className="hover:bg-red-100 dark:hover:bg-red-900/30 size-6 p-0"
                      onClick={(e) => handleDeleteTopic(topic.id, e)}
                      title={t("common.title.deleteTopic")}
                    >
                      <Trash2 className="text-red-600 dark:text-red-400 size-3" />
                    </Button>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </ScrollArea>
      
      {/* 底部提示 */}
      <div className="border-t border-border p-2">
        <p className="text-center text-xs text-muted-foreground">
          {t("ai.doubleClickToRename")}
        </p>
      </div>
      
      {/* 导出对话框 */}
      {exportingTopicId && (
        <ExportDialog
          open={showExportDialog}
          onOpenChange={setShowExportDialog}
          topicId={exportingTopicId}
          topicName={topics.find(t => t.id === exportingTopicId)?.name || ''}
        />
      )}
      
      {/* 删除确认对话框 */}
      {deletingTopicId && (
        <DeleteTopicDialog
          open={showDeleteDialog}
          onOpenChange={setShowDeleteDialog}
          onConfirm={handleConfirmDelete}
          topicName={topics.find(t => t.id === deletingTopicId)?.name || '此话题'}
        />
      )}
    </div>
  )
}
