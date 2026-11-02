import { useEffect, useCallback, useRef } from 'react'
import { useAppUpdateStore } from '@/stores/useAppUpdateStore'
import { useSettingsStore } from '@/stores/useSettingsStore'

const CHECK_INTERVAL = 10 * 60 * 1000 // 10 分钟
const INITIAL_DELAY = 2000 // 启动后 2 秒

export function useAutoUpdateCheck() {
  const { 
    hasUpdate, 
    updateInfo, 
    isChecking, 
    setHasUpdate, 
    setChecking,
    hasViewed
  } = useAppUpdateStore()

  // 尊重「系统设置 → 启动时检查更新」开关。
  // 该开关此前只存不读，导致无论是否关闭都会在启动后自动检查更新。
  const autoUpdate = useSettingsStore((state) => state.systemSettings?.autoUpdate ?? false)
  
  const isCheckingRef = useRef(isChecking)
  const hasCheckedRef = useRef(false)
  // 记录上一次的开关状态，用于在「关 → 开」时允许重新发起一次检查
  const prevAutoUpdateRef = useRef(autoUpdate)

  useEffect(() => {
    isCheckingRef.current = isChecking
  }, [isChecking])

  const checkForUpdate = useCallback(async () => {
    if (isCheckingRef.current) {
      console.log('[AutoUpdateCheck] 正在检查中，跳过')
      return
    }
    
    const api = (window as any).pywebview?.api
    if (!api) {
      console.log('[AutoUpdateCheck] API not available')
      return
    }

    setChecking(true)
    
    try {
      const result = await api.check_for_update()
      
      if (result.success && result.has_update) {
        setHasUpdate(true, {
          currentVersion: result.current_version,
          latestVersion: result.latest_version,
          downloadUrl: result.download_url,
          releaseNotes: result.release_notes,
          publishedAt: result.published_at,
          fileSize: result.file_size
        })
        console.log('[AutoUpdateCheck] 发现新版本:', result.latest_version)
      } else {
        setHasUpdate(false, null)
        console.log('[AutoUpdateCheck] 已是最新版本')
      }
    } catch (error) {
      console.error('[AutoUpdateCheck] 检查更新失败:', error)
      setHasUpdate(false, null)
    } finally {
      setChecking(false)
    }
  }, [setHasUpdate, setChecking])

  useEffect(() => {
    if (!autoUpdate) {
      console.log('[AutoUpdateCheck] 启动时检查更新已关闭，跳过启动检查与定时轮询')
      return
    }

    // 开关由「关」变「开」时重置标记，让用户可以立即触发一次检查
    if (prevAutoUpdateRef.current !== autoUpdate) {
      prevAutoUpdateRef.current = autoUpdate
      hasCheckedRef.current = false
    }

    if (hasCheckedRef.current) {
      return
    }
    hasCheckedRef.current = true

    let waitInterval: ReturnType<typeof setInterval> | null = null
    let waitTimeout: ReturnType<typeof setTimeout> | null = null
    let initialTimer: ReturnType<typeof setTimeout> | null = null
    let periodicInterval: ReturnType<typeof setInterval> | null = null

    const startPeriodicCheck = () => {
      if (periodicInterval) return
      periodicInterval = setInterval(() => {
        console.log('[AutoUpdateCheck] 定时检查更新...')
        checkForUpdate()
      }, CHECK_INTERVAL)
    }

    const api = (window as any).pywebview?.api
    if (!api) {
      console.log('[AutoUpdateCheck] Waiting for API...')

      waitInterval = setInterval(() => {
        if ((window as any).pywebview?.api) {
          if (waitInterval) {
            clearInterval(waitInterval)
            waitInterval = null
          }
          checkForUpdate()
          startPeriodicCheck()
        }
      }, 500)

      waitTimeout = setTimeout(() => {
        if (waitInterval) {
          clearInterval(waitInterval)
          waitInterval = null
        }
      }, 10000)
    } else {
      initialTimer = setTimeout(() => {
        checkForUpdate()
        startPeriodicCheck()
      }, INITIAL_DELAY)
    }

    // 开关关闭或组件卸载时，必须同时清理启动检查与定时轮询
    return () => {
      if (waitInterval) clearInterval(waitInterval)
      if (waitTimeout) clearTimeout(waitTimeout)
      if (initialTimer) clearTimeout(initialTimer)
      if (periodicInterval) clearInterval(periodicInterval)
    }
  }, [checkForUpdate, autoUpdate])

  return {
    hasUpdate,
    updateInfo,
    isChecking,
    hasViewed,
    checkForUpdate
  }
}
