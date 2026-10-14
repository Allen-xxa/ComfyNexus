/**
 * 终端页面 - 显示 ComfyUI 实时日志
 */

import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { toast } from '@/utils/toast'
import { stripAnsi } from '@/utils/ansi'
import { AnsiLogMessage } from '@/components/common/AnsiLogMessage'
import { 
  Terminal, 
  Trash2, 
  Sparkles,
  ArrowDown,
  Copy,
  Languages,
  Loader2
} from 'lucide-react'
import { Button, Switch } from '@/components/ui'
import { useProcessStore } from '@/stores/useProcessStore'
import { useTopicStore } from '@/stores/useTopicStore'
import { useSystemPromptStore } from '@/stores/useSystemPromptStore'
import { useModelSelectorStore } from '@/stores/useModelSelectorStore'
import { useAIStore } from '@/stores/useAIStore'
import { useAPIConfigStore } from '@/stores/useAPIConfigStore'
import { ConfirmDialog } from '@/components/common/ConfirmDialog'

const MAX_LOG_LENGTH = 50000

interface Log {
  id: string
  timestamp: string
  level: 'INFO' | 'WARNING' | 'ERROR' | 'DEBUG'
  source: 'comfyui' | 'system'
  message: string
  isUpdate?: boolean
}

interface ContextMenuPosition {
  x: number
  y: number
  log: Log | null
}

interface ComfyNexusNamespace {
  logsCleared?: boolean
  skipHistoryLogs?: boolean
  logCache?: {
    getLogs: () => Log[]
    clear: () => void
  }
}

// 解析日志文件内容（提取到组件外部）
function parseLogContent(content: string): Log[] {
  const lines = content.split('\n')
  const logs: Log[] = []
  let currentLog: Log | null = null
  
  for (const line of lines) {
    // 跳过空行和分隔线
    if (!line.trim() || line.startsWith('=')) {
      continue
    }
    
    // 跳过日志文件元数据行
    if (line.startsWith('日志结束时间:') || line.startsWith('创建时间:')) {
      continue
    }
    
    // 匹配日志格式: [2024-01-29 12:00:00] [INFO] message
    const match = line.match(/^\[([^\]]+)\]\s*\[([^\]]+)\]\s*(.*)$/)
    
    if (match) {
      // 新的日志行，保存之前的日志
      if (currentLog) {
        logs.push(currentLog)
      }
      
      const [, timestamp, level, message] = match
      currentLog = {
        id: `${timestamp}-${Math.random()}`,
        timestamp,
        level: level as Log['level'],
        source: 'comfyui',
        message
      }
    } else if (currentLog) {
      // 没有时间戳的行，附加到当前日志（多行日志，如 Traceback）
      currentLog.message += '\n' + line
    }
  }
  
  // 保存最后一条日志
  if (currentLog) {
    logs.push(currentLog)
  }
  
  return logs
}

export default function TerminalPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { 
    loadComfyUIStatus
  } = useProcessStore()
  const [logs, setLogs] = useState<Log[]>([])
  const [allLogs, setAllLogs] = useState<Log[]>([]) // 保存所有日志
  const [autoScroll, setAutoScroll] = useState(true)
  const [showErrorsOnly, setShowErrorsOnly] = useState(false) // 是否只显示错误
  const [contextMenu, setContextMenu] = useState<ContextMenuPosition | null>(null)
  const [isLoading, setIsLoading] = useState(true) // 加载状态
  const [selectedText, setSelectedText] = useState<string>('') // 选中的文本
  const [isAIAnalyzing, setIsAIAnalyzing] = useState(false) // AI 分析状态
  const [noErrorConfirmOpen, setNoErrorConfirmOpen] = useState(false) // 无错误日志确认对话框
  const [batchConfirmOpen, setBatchConfirmOpen] = useState(false) // 分批推送确认对话框
  const [batchInfo, setBatchInfo] = useState<{ batchCount: number; totalLogs: number } | null>(null)
  const logContainerRef = useRef<HTMLDivElement>(null)
  const isAutoScrollingRef = useRef(false) // 标记是否正在自动滚动
  
  const getNamespace = useCallback((): ComfyNexusNamespace => {
    if (!(window as any).__COMFY_NEXUS__) {
      (window as any).__COMFY_NEXUS__ = {}
    }
    return (window as any).__COMFY_NEXUS__
  }, [])
  
  const isLogsCleared = useCallback(() => getNamespace().logsCleared || false, [getNamespace])
  const setLogsCleared = useCallback((cleared: boolean) => { getNamespace().logsCleared = cleared }, [getNamespace])
  const shouldSkipHistoryLogs = useCallback(() => getNamespace().skipHistoryLogs || false, [getNamespace])
  const setSkipHistoryLogs = useCallback((skip: boolean) => { getNamespace().skipHistoryLogs = skip }, [getNamespace])

  // 轮询 ComfyUI 状态（每 2 秒检查一次）
  useEffect(() => {
    console.log('[TerminalPage] 开始轮询 ComfyUI 状态')
    
    // 立即加载一次
    loadComfyUIStatus().catch(err => {
      console.error('[TerminalPage] 加载状态失败:', err)
    })
    
    // 设置轮询
    const interval = setInterval(() => {
      loadComfyUIStatus().catch(err => {
        console.error('[TerminalPage] 轮询状态失败:', err)
      })
    }, 2000)
    
    return () => {
      console.log('[TerminalPage] 停止轮询 ComfyUI 状态')
      clearInterval(interval)
    }
  }, [loadComfyUIStatus])

  // 注意：清屏逻辑已改为由 Store 在启动时主动触发（通过 'comfyui:clear-logs' 事件）
  // 不再依赖状态变化检测，避免时序问题

  // 从日志文件加载历史日志
  const loadHistoryLogs = useCallback(async () => {
    // 如果日志已被清空或跳过历史日志，不再加载
    if (isLogsCleared() || shouldSkipHistoryLogs()) {
      setIsLoading(false)
      return
    }
    
    try {
      setIsLoading(true)
      
      // 获取当前日志文件路径
      const result = await (window as any).pywebview.api.get_current_log_file()
      
      if (result.success && result.log_file_path) {
        // 读取日志文件内容
        const readResult = await (window as any).pywebview.api.read_log_file(result.log_file_path)
        
        if (readResult.success && readResult.content) {
          // 解析日志内容
          const parsedLogs = parseLogContent(readResult.content)
          // 合并日志：保留已有的实时日志，添加文件中的新日志
          // 使用时间戳去重，因为 ID 生成方式不同
          setAllLogs(prev => {
            const existingKeys = new Set(prev.map(log => `${log.timestamp}-${log.message.slice(0, 50)}`))
            const newLogs = parsedLogs.filter(log => !existingKeys.has(`${log.timestamp}-${log.message.slice(0, 50)}`))
            // 按时间戳排序
            const allLogs = [...prev, ...newLogs]
            allLogs.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
            return allLogs
          })
        }
      }
    } catch (error) {
      console.error('加载历史日志失败:', error)
    } finally {
      setIsLoading(false)
    }
  }, [isLogsCleared, shouldSkipHistoryLogs])

  // 初始加载历史日志
  useEffect(() => {
    loadHistoryLogs()
  }, [loadHistoryLogs])

  // 监听 ComfyUI 日志
  useEffect(() => {
    // 从全局缓存加载已有日志（如果日志未被清空）
    if (!isLogsCleared()) {
      const cachedLogs = getNamespace().logCache?.getLogs() || []
      if (cachedLogs.length > 0) {
        setAllLogs(cachedLogs)
      }
    }
    
    // 监听日志事件（由 main.tsx 中的全局回调触发）
    const handleLogReceived = (event: CustomEvent<Log>) => {
      const log = event.detail
      if (log.isUpdate) {
        // 更新现有日志（进度条）
        setAllLogs(prev => prev.map(item => 
          item.id === log.id ? { ...item, message: log.message, timestamp: log.timestamp } : item
        ))
      } else {
        // 添加新日志
        setAllLogs(prev => [...prev, log])
      }
    }

    // 监听清屏事件（由 Store 在启动时触发）
    const handleClearLogs = () => {
      console.log('[TerminalPage] 收到清屏事件，清空日志')
      setLogs([])
      setAllLogs([])
      // 标记日志已被清空
      setLogsCleared(true)
      // 跳过历史日志加载
      setSkipHistoryLogs(true)
      // 同时清空全局缓存
      getNamespace().logCache?.clear()
    }
    
    // 监听重新加载日志事件
    const handleReloadLogs = () => {
      console.log('[TerminalPage] 收到重新加载日志事件')
      // 重置清空标记，允许重新加载
      setLogsCleared(false)
      setSkipHistoryLogs(false)
      loadHistoryLogs()
    }
    
    window.addEventListener('comfyui:log-received', handleLogReceived as EventListener)
    window.addEventListener('comfyui:clear-logs', handleClearLogs)
    window.addEventListener('comfyui:reload-logs', handleReloadLogs)

    // 清理函数
    return () => {
      window.removeEventListener('comfyui:log-received', handleLogReceived as EventListener)
      window.removeEventListener('comfyui:clear-logs', handleClearLogs)
      window.removeEventListener('comfyui:reload-logs', handleReloadLogs)
    }
  }, [loadHistoryLogs, isLogsCleared, setLogsCleared, setSkipHistoryLogs])

  // 根据筛选条件更新显示的日志
  useEffect(() => {
    if (showErrorsOnly) {
      setLogs(allLogs.filter(log => log.level === 'ERROR'))
    } else {
      setLogs(allLogs)
    }
  }, [allLogs, showErrorsOnly])

  // 自动滚动
  useEffect(() => {
    if (autoScroll && logContainerRef.current) {
      // 标记开始自动滚动
      isAutoScrollingRef.current = true
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight
      
      // 滚动完成后重置标记（使用 setTimeout 确保滚动动画完成）
      setTimeout(() => {
        isAutoScrollingRef.current = false
      }, 100)
    }
  }, [logs, autoScroll])

  // 点击其他地方关闭右键菜单
  useEffect(() => {
    const handleClick = () => setContextMenu(null)
    document.addEventListener('click', handleClick)
    return () => document.removeEventListener('click', handleClick)
  }, [])

  // 监听文本选择
  useEffect(() => {
    const handleSelectionChange = () => {
      const selection = window.getSelection()
      const text = selection?.toString() || ''
      setSelectedText(text)
    }

    document.addEventListener('selectionchange', handleSelectionChange)
    return () => document.removeEventListener('selectionchange', handleSelectionChange)
  }, [])

  // 获取日志级别颜色
  const getLevelColor = (level: string) => {
    switch (level) {
      case 'ERROR':
        return 'text-danger'
      case 'WARNING':
        return 'text-warning'
      case 'DEBUG':
        return 'text-content-muted'
      default: // INFO - 使用次要文本色，不刺眼
        return 'text-content-secondary'
    }
  }

  // 获取日志行背景色
  const getLogBackground = (level: string) => {
    switch (level) {
      case 'ERROR':
        return 'bg-danger/10 hover:bg-danger/15 border-l-4 border-danger'
      case 'WARNING':
        return 'bg-warning/10 hover:bg-warning/15 border-l-4 border-warning'
      default:
        return 'hover:bg-muted/30'
    }
  }

  // 清空日志
  const handleClearLogs = () => {
    setLogs([])
    setAllLogs([])
    // 标记日志已被清空，防止重新加载
    setLogsCleared(true)
    // 跳过历史日志加载，只显示新日志
    setSkipHistoryLogs(true)
    // 同时清空全局缓存，防止切换页面后日志恢复
    getNamespace().logCache?.clear()
  }

  // 一键复制日志
  const handleCopyAllLogs = () => {
    // 根据筛选条件决定复制哪些日志
    const logsToCopy = showErrorsOnly 
      ? allLogs.filter(log => log.level === 'ERROR')
      : allLogs
    
    if (logsToCopy.length === 0) {
      toast.warning(showErrorsOnly ? t('terminal.noErrorLogsToCopy') : t('terminal.noLogsToCopy'))
      return
    }
    
    const logsText = logsToCopy
      .map(log => `[${log.timestamp}] [${log.level}] ${stripAnsi(log.message)}`)
      .join('\n')
    
    navigator.clipboard.writeText(logsText)
      .then(() => {
        toast.success(showErrorsOnly ? t('terminal.errorLogsCopied') : t('terminal.allLogsCopiedSuccess'))
      })
      .catch(err => {
        console.error('复制失败:', err)
        toast.error(t('terminal.copyFailed'))
      })
  }

  const splitLogsIntoBatches = useCallback((logs: Log[]): Log[][] => {
    const batches: Log[][] = []
    let currentBatch: Log[] = []
    let currentLength = 0
    
    for (const log of logs) {
      const logText = `[${log.timestamp}] ${log.message}`
      const logLength = logText.length
      
      if (currentLength + logLength > MAX_LOG_LENGTH && currentBatch.length > 0) {
        batches.push(currentBatch)
        currentBatch = []
        currentLength = 0
      }
      
      currentBatch.push(log)
      currentLength += logLength
    }
    
    if (currentBatch.length > 0) {
      batches.push(currentBatch)
    }
    
    return batches
  }, [])

  const analyzeLogs = useCallback(async (logs: Log[], isBatch = false, batchIndex = 0, totalBatches = 1, topicId?: string) => {
    try {
      setIsAIAnalyzing(true)
      
      const presets = useSystemPromptStore.getState().presets
      const comfyuiExpertPreset = presets.find(p => p.name === 'ComfyUI专家')
      
      await useModelSelectorStore.getState().loadDefaultConfig()
      const defaultConfigId = useModelSelectorStore.getState().defaultConfigId
      
      if (!defaultConfigId) {
        toast.error(t('terminal.noApiConfig'))
        setIsAIAnalyzing(false)
        return
      }
      
      let currentTopicId = topicId
      
      if (!currentTopicId) {
        const newTopic = await useTopicStore.getState().createTopic('日志分析')
        if (!newTopic) {
          toast.error(t('terminal.createTopicFailed'))
          setIsAIAnalyzing(false)
          return
        }
        currentTopicId = newTopic.id
        
        if (comfyuiExpertPreset) {
          await useSystemPromptStore.getState().setActivePreset(currentTopicId, comfyuiExpertPreset.id)
        }
        
        if (defaultConfigId) {
          await useModelSelectorStore.getState().setActiveConfig(currentTopicId, defaultConfigId)
        }
      }
      
      let provider = 'openai'
      let model = 'gpt-3.5-turbo'
      if (defaultConfigId) {
        const config = await useAPIConfigStore.getState().getConfig(defaultConfigId)
        if (config) {
          provider = config.provider
          model = config.model
        }
      }
      
      let promptPrefix = '以下是 ComfyUI 运行过程中的错误日志，请帮我分析原因并提供解决方案：\n\n'
      if (isBatch) {
        promptPrefix = `以下是 ComfyUI 运行过程中的错误日志（第 ${batchIndex + 1}/${totalBatches} 批），请帮我分析原因并提供解决方案：\n\n`
      }
      
      const logsText = logs.map(log => `[${log.timestamp}] ${stripAnsi(log.message)}`).join('\n')
      const messageContent = promptPrefix + logsText
      
      const systemPromptContent = comfyuiExpertPreset?.content || null
      
      useTopicStore.getState().setCurrentTopicId(currentTopicId)
      
      if (!isBatch || batchIndex === 0) {
        navigate('/ai-assistant')
      }
      
      useAIStore.getState().sendMessage(
        messageContent,
        currentTopicId,
        provider,
        model,
        defaultConfigId || undefined,
        false,
        false,
        systemPromptContent
      )
      
      return currentTopicId
    } catch (error) {
      console.error('AI 分析失败:', error)
      toast.error(t('terminal.aiAnalysisFailed'))
      return undefined
    } finally {
      setIsAIAnalyzing(false)
    }
  }, [t, navigate])

  const handleAIAnalyze = useCallback(async () => {
    const errorLogs = allLogs.filter(log => log.level === 'ERROR')
    
    if (errorLogs.length === 0) {
      setNoErrorConfirmOpen(true)
      return
    }
    
    const totalLength = errorLogs.reduce((sum, log) => sum + `[${log.timestamp}] ${log.message}`.length, 0)
    
    if (totalLength > MAX_LOG_LENGTH) {
      const batches = splitLogsIntoBatches(errorLogs)
      setBatchInfo({ batchCount: batches.length, totalLogs: errorLogs.length })
      setBatchConfirmOpen(true)
      return
    }
    
    await analyzeLogs(errorLogs)
  }, [allLogs, splitLogsIntoBatches, analyzeLogs])

  const handleBatchConfirm = useCallback(async () => {
    if (!batchInfo) return
    
    const errorLogs = allLogs.filter(log => log.level === 'ERROR')
    const batches = splitLogsIntoBatches(errorLogs)
    
    setBatchConfirmOpen(false)
    
    let topicId: string | undefined = undefined
    for (let i = 0; i < batches.length; i++) {
      topicId = await analyzeLogs(batches[i], true, i, batches.length, topicId)
      if (!topicId) break
      
      if (i < batches.length - 1) {
        await new Promise(resolve => setTimeout(resolve, 500))
      }
    }
  }, [batchInfo, allLogs, splitLogsIntoBatches, analyzeLogs])

  const handleNoErrorConfirm = useCallback(async () => {
    setNoErrorConfirmOpen(false)
    
    const totalLength = allLogs.reduce((sum, log) => sum + `[${log.timestamp}] ${log.message}`.length, 0)
    
    if (totalLength > MAX_LOG_LENGTH) {
      const batches = splitLogsIntoBatches(allLogs)
      setBatchInfo({ batchCount: batches.length, totalLogs: allLogs.length })
      setBatchConfirmOpen(true)
      return
    }
    
    await analyzeLogs(allLogs)
  }, [allLogs, splitLogsIntoBatches, analyzeLogs])

  // 右键菜单 - 复制
  const handleCopy = () => {
    if (selectedText) {
      navigator.clipboard.writeText(selectedText)
        .catch(err => {
          console.error('复制失败:', err)
          toast.error(t('terminal.copyFailed'))
        })
    } else {
      handleCopyAllLogs()
    }
    setContextMenu(null)
  }

  // 右键菜单 - 翻译
  const handleTranslate = (log: Log) => {
    // TODO: 调用翻译接口
    alert(`${t('terminal.translateDev')}\n${t('terminal.original')}: ${log.message}`)
    setContextMenu(null)
  }

  // 右键菜单 - 日志分析
  const handleContextAIAnalyze = useCallback(async () => {
    setContextMenu(null)

    if (!selectedText) {
      const totalLength = allLogs.reduce((sum, log) => sum + `[${log.timestamp}] ${log.message}`.length, 0)
      if (totalLength > MAX_LOG_LENGTH) {
        const batches = splitLogsIntoBatches(allLogs)
        setBatchInfo({ batchCount: batches.length, totalLogs: allLogs.length })
        setBatchConfirmOpen(true)
        return
      }
      await analyzeLogs(allLogs)
      return
    }

    try {
      setIsAIAnalyzing(true)

      const presets = useSystemPromptStore.getState().presets
      const comfyuiExpertPreset = presets.find(p => p.name === 'ComfyUI专家')

      await useModelSelectorStore.getState().loadDefaultConfig()
      const defaultConfigId = useModelSelectorStore.getState().defaultConfigId

      if (!defaultConfigId) {
        toast.error(t('terminal.noApiConfig'))
        setIsAIAnalyzing(false)
        return
      }

      const newTopic = await useTopicStore.getState().createTopic('日志分析')
      if (!newTopic) {
        toast.error(t('terminal.createTopicFailed'))
        setIsAIAnalyzing(false)
        return
      }

      const currentTopicId = newTopic.id

      if (comfyuiExpertPreset) {
        await useSystemPromptStore.getState().setActivePreset(currentTopicId, comfyuiExpertPreset.id)
      }
      if (defaultConfigId) {
        await useModelSelectorStore.getState().setActiveConfig(currentTopicId, defaultConfigId)
      }

      let provider = 'openai'
      let model = 'gpt-3.5-turbo'
      if (defaultConfigId) {
        const config = await useAPIConfigStore.getState().getConfig(defaultConfigId)
        if (config) {
          provider = config.provider
          model = config.model
        }
      }

      const promptPrefix = '以下是一段 ComfyUI 日志，请帮我分析并解释：\n\n'
      const messageContent = promptPrefix + selectedText
      const systemPromptContent = comfyuiExpertPreset?.content || null

      useTopicStore.getState().setCurrentTopicId(currentTopicId)
      navigate('/ai-assistant')

      useAIStore.getState().sendMessage(
        messageContent,
        currentTopicId,
        provider,
        model,
        defaultConfigId || undefined,
        false,
        false,
        systemPromptContent
      )
    } catch (error) {
      console.error('AI 分析失败:', error)
      toast.error(t('terminal.aiAnalysisFailed'))
    } finally {
      setIsAIAnalyzing(false)
    }
  }, [selectedText, handleAIAnalyze, t, navigate])

  // 右键菜单
  const handleContextMenu = (e: React.MouseEvent, log?: Log) => {
    e.preventDefault()
    
    // 如果有选中文本，显示复制选中文本的菜单
    // 否则显示单行日志的菜单
    setContextMenu({
      x: e.clientX,
      y: e.clientY,
      log: log || null
    })
  }

  // 滚动到底部
  const scrollToBottom = () => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight
      setAutoScroll(true)
    }
  }

  return (
    <div className="flex h-full flex-col bg-background">
      {/* 头部 - 使用更暗的表面色 */}
      <div className="border-b border-border-subtle bg-surface-active/50 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Terminal className="size-6 text-content-secondary" />
            <h1 className="text-xl font-bold text-content-primary">{t('terminal.title')}</h1>
          </div>
          
          <div className="flex items-center gap-4">
            {/* 自动滚动开关 */}
            <div className="flex items-center gap-2">
              <span className="text-sm text-content-secondary">{t("terminal.autoScroll")}</span>
              <Switch
                checked={autoScroll}
                onCheckedChange={setAutoScroll}
              />
            </div>

            {/* 错误日志开关 */}
            <div className="flex items-center gap-2">
              <span className="text-sm text-content-secondary">{t("terminal.errorLog")}</span>
              <Switch
                checked={showErrorsOnly}
                onCheckedChange={setShowErrorsOnly}
              />
            </div>

            {/* 分隔线 */}
            <div className="h-6 w-px bg-border"></div>

            {/* AI 分析 */}
            <Button
              variant="outline"
              size="sm"
              onClick={handleAIAnalyze}
              disabled={isAIAnalyzing}
              title={t("common.title.aiAnalyzeLog")}
            >
              {isAIAnalyzing ? (
                <Loader2 className="mr-2 size-4 animate-spin" />
              ) : (
                <Sparkles className="mr-2 size-4" />
              )}
              {isAIAnalyzing ? t('terminal.analyzing') : t('common.aiAnalyze')}
            </Button>

            {/* 一键复制日志 */}
            <Button
              variant="outline"
              size="sm"
              onClick={handleCopyAllLogs}
              title={showErrorsOnly ? t("common.title.copyErrorLogs") : t("common.title.copyAllLogs")}
            >
              <Copy className="mr-2 size-4" />
              {showErrorsOnly ? t('common.title.copyErrorLogs') : t('common.title.copyAllLogs')}
            </Button>

            {/* 清空 */}
            <Button
              variant="outline"
              size="sm"
              onClick={handleClearLogs}
              title={t("common.title.clearLogs")}
            >
              <Trash2 className="mr-2 size-4" />
              {t('common.clear')}
            </Button>
          </div>
        </div>
      </div>

      {/* 日志内容 */}
      <div 
        ref={logContainerRef}
        className="flex-1 select-text overflow-y-auto border-x border-border bg-[hsl(var(--bg-base))] p-6 font-mono text-sm"
        onScroll={(e) => {
          // 如果是自动滚动触发的 onScroll 事件，忽略
          if (isAutoScrollingRef.current) {
            return
          }
          
          // 只有用户手动滚动时才检测是否在底部
          const target = e.target as HTMLDivElement
          const isAtBottom = 
            target.scrollHeight - target.scrollTop - target.clientHeight < 10
          setAutoScroll(isAtBottom)
        }}
        onContextMenu={(e) => handleContextMenu(e)}
      >
        {isLoading ? (
          <div className="flex h-full items-center justify-center">
            <div className="text-center text-content-muted">
              <Terminal className="mx-auto mb-4 size-16 animate-pulse opacity-50" />
              <p>{t("terminal.loadingLogs")}</p>
            </div>
          </div>
        ) : logs.length === 0 ? (
          <div className="flex h-full items-center justify-center">
            <div className="text-center text-content-muted">
              <div className="relative mx-auto mb-4 size-16">
                <Terminal className="size-full opacity-30" strokeWidth={1.5} />
              </div>
              <p className="text-content-muted">{t("terminal.noLogs")}</p>
              <p className="mt-2 text-xs text-content-muted">{t("terminal.logsWillAppear")}</p>
            </div>
          </div>
        ) : (
          <div className="space-y-0.5">
            {logs.map((log) => (
              <div
                key={log.id}
                className={`cursor-pointer rounded px-4 transition-colors ${getLogBackground(log.level)}`}
                style={{ paddingTop: '2px', paddingBottom: '2px' }}
                onContextMenu={(e) => handleContextMenu(e, log)}
              >
                <div className="flex items-start gap-3">
                  <span className="whitespace-nowrap text-xs text-content-muted">
                    {log.timestamp}
                  </span>
                  <span className={`whitespace-nowrap text-xs font-medium ${getLevelColor(log.level)}`}>
                    [{log.level}]
                  </span>
                  <span className={`flex-1 whitespace-pre-wrap break-all ${getLevelColor(log.level)}`}>
                    <AnsiLogMessage message={log.message} />
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 右键菜单 */}
      {contextMenu && (
        <div
          className="fixed z-50 min-w-[160px] rounded-lg border border-border-subtle bg-surface-active py-2 shadow-lg"
          style={{
            left: `${contextMenu.x}px`,
            top: `${contextMenu.y}px`
          }}
          onClick={(e) => e.stopPropagation()}
        >
          <Button
            variant="ghost"
            className="flex w-full items-center justify-start gap-2 px-4 py-2 text-left text-sm hover:bg-muted"
            onClick={handleCopy}
          >
            <Copy className="size-4" />
            {selectedText ? t('terminal.copySelected') : t('common.copy')}
          </Button>
          <Button
            variant="ghost"
            className="flex w-full items-center justify-start gap-2 px-4 py-2 text-left text-sm hover:bg-muted"
            onClick={handleContextAIAnalyze}
            disabled={isAIAnalyzing}
          >
            <Sparkles className="size-4" />
            {selectedText ? t('terminal.analyzeSelectedLogs') : t('terminal.analyzeAllLogs')}
          </Button>
          {contextMenu.log && !selectedText && (
            <Button
              variant="ghost"
              className="flex w-full items-center justify-start gap-2 px-4 py-2 text-left text-sm hover:bg-muted"
              onClick={() => handleTranslate(contextMenu.log!)}
            >
              <Languages className="size-4" />
              {t('terminal.translate')}
            </Button>
          )}
        </div>
      )}

      {/* 底部状态栏 */}
      <div className="border-t border-border bg-surface-active/50 px-6 py-3">
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>
            {showErrorsOnly 
              ? t('terminal.errorLogsCount', { count: logs.length, total: allLogs.length })
              : t('terminal.totalLogsCount', { count: logs.length })
            }
          </span>
          {!autoScroll && (
            <Button
              onClick={scrollToBottom}
              variant="link"
              className="flex h-auto items-center gap-1 p-0 text-primary hover:underline"
            >
              <ArrowDown className="size-4" />
              {t('terminal.scrollToBottom')}
            </Button>
          )}
        </div>
      </div>

      {/* 无错误日志确认对话框 */}
      <ConfirmDialog
        open={noErrorConfirmOpen}
        onOpenChange={setNoErrorConfirmOpen}
        title={t('terminal.noErrorLogsTitle')}
        description={t('terminal.noErrorLogsDescription')}
        confirmText={t('terminal.pushAllLogs')}
        cancelText={t('common.cancel')}
        onConfirm={handleNoErrorConfirm}
        loading={isAIAnalyzing}
      />

      {/* 分批推送确认对话框 */}
      <ConfirmDialog
        open={batchConfirmOpen}
        onOpenChange={setBatchConfirmOpen}
        title={t('terminal.batchConfirmTitle')}
        description={t('terminal.batchConfirmDescription', { 
          batchCount: batchInfo?.batchCount || 0, 
          totalLogs: batchInfo?.totalLogs || 0 
        })}
        confirmText={t('terminal.confirmBatchPush')}
        cancelText={t('common.cancel')}
        onConfirm={handleBatchConfirm}
        loading={isAIAnalyzing}
      />
    </div>
  )
}
